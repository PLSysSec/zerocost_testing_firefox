/* -*- indent-tabs-mode: nil; js-indent-level: 2 -*-*/
/* vim: set ts=8 sts=2 et sw=2 tw=80: */
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

// Time in ms before we start changing the sort order again after receiving a
// mousemove event.
const TIME_BEFORE_SORTING_AGAIN = 5000;

// How often we should add a sample to our buffer.
const BUFFER_SAMPLING_RATE_MS = 1000;

// The age of the oldest sample to keep.
const BUFFER_DURATION_MS = 10000;

// How often we should update
const UPDATE_INTERVAL_MS = 2000;

const MS_PER_NS = 1000000;
const NS_PER_S = 1000000000;

const ONE_GIGA = 1024 * 1024 * 1024;
const ONE_MEGA = 1024 * 1024;
const ONE_KILO = 1024;

const { Services } = ChromeUtils.import("resource://gre/modules/Services.jsm");

/**
 * Returns a Promise that's resolved after the next turn of the event loop.
 *
 * Just returning a resolved Promise would mean that any `then` callbacks
 * would be called right after the end of the current turn, so `setTimeout`
 * is used to delay Promise resolution until the next turn.
 *
 * In mochi tests, it's possible for this to be called after the
 * about:performance window has been torn down, which causes `setTimeout` to
 * throw an NS_ERROR_NOT_INITIALIZED exception. In that case, returning
 * `undefined` is fine.
 */
function wait(ms = 0) {
  try {
    let resolve;
    let p = new Promise(resolve_ => {
      resolve = resolve_;
    });
    setTimeout(resolve, ms);
    return p;
  } catch (e) {
    dump(
      "WARNING: wait aborted because of an invalid Window state in aboutPerformance.js.\n"
    );
    return undefined;
  }
}

/**
 * Utilities for dealing with state
 */
var State = {
  /**
   * Indexed by the number of minutes since the snapshot was taken.
   *
   * @type {Array<ApplicationSnapshot>}
   */
  _buffer: [],
  /**
   * The latest snapshot.
   *
   * @type ApplicationSnapshot
   */
  _latest: null,

  async _promiseSnapshot() {
    let date = Cu.now();
    let main = await ChromeUtils.requestProcInfo();
    main.date = date;

    let processes = new Map();
    processes.set(main.pid, main);
    for (let child of main.children) {
      child.date = date;
      processes.set(child.pid, child);
    }

    return { processes, date };
  },

  /**
   * Update the internal state.
   *
   * @return {Promise}
   */
  async update() {
    // If the buffer is empty, add one value for bootstraping purposes.
    if (!this._buffer.length) {
      this._latest = await this._promiseSnapshot();
      this._buffer.push(this._latest);
      await wait(BUFFER_SAMPLING_RATE_MS * 1.1);
    }

    let now = Cu.now();

    // If we haven't sampled in a while, add a sample to the buffer.
    let latestInBuffer = this._buffer[this._buffer.length - 1];
    let deltaT = now - latestInBuffer.date;
    if (deltaT > BUFFER_SAMPLING_RATE_MS) {
      this._latest = await this._promiseSnapshot();
      this._buffer.push(this._latest);
    }

    // If we have too many samples, remove the oldest sample.
    let oldestInBuffer = this._buffer[0];
    if (oldestInBuffer.date + BUFFER_DURATION_MS < this._latest.date) {
      this._buffer.shift();
    }
  },

  _getThreadDelta(cur, prev, deltaT) {
    let name = cur.name || "???";
    let result = {
      tid: cur.tid,
      name,
      // Total amount of CPU used, in ns (user).
      totalCpuUser: cur.cpuUser,
      slopeCpuUser: null,
      // Total amount of CPU used, in ns (kernel).
      totalCpuKernel: cur.cpuKernel,
      slopeCpuKernel: null,
      // Total amount of CPU used, in ns (user + kernel).
      totalCpu: cur.cpuUser + cur.cpuKernel,
      slopeCpu: null,
    };
    if (!prev) {
      return result;
    }
    if (prev.tid != cur.tid) {
      throw new Error("Assertion failed: A thread cannot change tid.");
    }
    result.slopeCpuUser = (cur.cpuUser - prev.cpuUser) / deltaT;
    result.slopeCpuKernel = (cur.cpuKernel - prev.cpuKernel) / deltaT;
    result.slopeCpu = result.slopeCpuKernel + result.slopeCpuUser;
    return result;
  },

  /**
   * Compute the delta between two process snapshots.
   *
   * @param {ProcessSnapshot} cur
   * @param {ProcessSnapshot?} prev
   */
  _getProcessDelta(cur, prev) {
    let result = {
      pid: cur.pid,
      childID: cur.childID,
      filename: cur.filename,
      totalVirtualMemorySize: cur.virtualMemorySize,
      deltaVirtualMemorySize: null,
      totalResidentSize: cur.residentSetSize,
      deltaResidentSize: null,
      totalCpuUser: cur.cpuUser,
      slopeCpuUser: null,
      totalCpuKernel: cur.cpuKernel,
      slopeCpuKernel: null,
      totalCpu: cur.cpuUser + cur.cpuKernel,
      slopeCpu: null,
      type: cur.type,
      origin: cur.origin || "",
      threads: null,
      displayRank: Control._getDisplayGroupRank(cur.type),
    };
    if (!prev) {
      result.threads = cur.threads.map(data =>
        this._getThreadDelta(data, null, null)
      );
      return result;
    }
    if (prev.pid != cur.pid) {
      throw new Error("Assertion failed: A process cannot change pid.");
    }
    let prevThreads = new Map();
    for (let thread of prev.threads) {
      prevThreads.set(thread.tid, thread);
    }
    let deltaT = (cur.date - prev.date) * MS_PER_NS;
    let threads = cur.threads.map(curThread => {
      let prevThread = prevThreads.get(curThread.tid);
      if (!prevThread) {
        return this._getThreadDelta(curThread);
      }
      return this._getThreadDelta(curThread, prevThread, deltaT);
    });
    result.deltaVirtualMemorySize =
      cur.virtualMemorySize - prev.virtualMemorySize;
    result.deltaResidentSize = cur.residentSetSize - prev.residentSetSize;
    result.slopeCpuUser = (cur.cpuUser - prev.cpuUser) / deltaT;
    result.slopeCpuKernel = (cur.cpuKernel - prev.cpuKernel) / deltaT;
    result.slopeCpu = result.slopeCpuUser + result.slopeCpuKernel;
    result.threads = threads;
    return result;
  },

  getCounters() {
    // We rebuild the maps during each iteration to make sure that
    // we do not maintain references to processes that have been
    // shutdown.

    let current = this._latest;
    let counters = [];

    for (let cur of current.processes.values()) {
      // Look for the oldest point of comparison
      let oldest = null;
      let delta;
      for (let index = 0; index <= this._buffer.length - 2; ++index) {
        oldest = this._buffer[index].processes.get(cur.pid);
        if (oldest) {
          // Found it!
          break;
        }
      }
      if (oldest) {
        // Existing process. Let's display slopes info.
        delta = this._getProcessDelta(cur, oldest);
      } else {
        // New process. Let's display basic info.
        delta = this._getProcessDelta(cur, null);
      }
      counters.push(delta);
    }

    return counters;
  },
};

var View = {
  _fragment: document.createDocumentFragment(),
  async commit() {
    let tbody = document.getElementById("process-tbody");

    // Force translation to happen before we insert the new content in the DOM
    // to avoid flicker when resizing.
    await document.l10n.translateFragment(this._fragment);

    while (tbody.firstChild) {
      tbody.firstChild.remove();
    }
    tbody.appendChild(this._fragment);
    this._fragment = document.createDocumentFragment();
  },
  insertAfterRow(row) {
    row.parentNode.insertBefore(this._fragment, row.nextSibling);
    this._fragment = document.createDocumentFragment();
  },

  /**
   * Append a row showing a single process (without its threads).
   *
   * @param {ProcessDelta} data The data to display.
   * @return {DOMElement} The row displaying the process.
   */
  appendProcessRow(data) {
    let row = document.createElement("tr");
    row.classList.add("process");

    if (data.isHung) {
      row.classList.add("hung");
    }

    // Column: type / twisty image
    {
      let content = data.origin ? `${data.origin} (${data.type})` : data.type;
      let elt = this._addCell(row, {
        content,
        classes: ["type"],
      });

      if (data.threads.length) {
        let img = document.createElement("span");
        img.classList.add("twisty", "process");
        if (data.isOpen) {
          img.classList.add("open");
        }
        elt.insertBefore(img, elt.firstChild);
      }
    }

    // Column: Resident size
    {
      let { formatedDelta, formatedValue } = this._formatMemoryAndDelta(
        data.totalResidentSize,
        data.deltaResidentSize
      );
      let content = formatedDelta
        ? `${formatedValue}${formatedDelta}`
        : formatedValue;
      this._addCell(row, {
        content,
        classes: ["totalResidentSize"],
      });
    }

    // Column: CPU: User and Kernel
    {
      let slope = this._formatPercentage(data.slopeCpu);
      let content = `${slope} (${(
        data.totalCpu / MS_PER_NS
      ).toLocaleString(undefined, { maximumFractionDigits: 0 })}ms)`;
      this._addCell(row, {
        content,
        classes: ["cpu"],
      });
    }

    // Column: pid
    this._addCell(row, {
      content: data.pid,
      classes: ["pid", "root"],
    });

    // Column: Number of threads
    this._addCell(row, {
      content: data.threads.length,
      classes: ["numberOfThreads"],
    });

    this._fragment.appendChild(row);
    return row;
  },

  /**
   * Append a row showing a single thread.
   *
   * @param {ThreadDelta} data The data to display.
   * @return {DOMElement} The row displaying the thread.
   */
  appendThreadRow(data) {
    let row = document.createElement("tr");
    row.classList.add("thread");

    // Column: filename
    this._addCell(row, {
      content: data.name,
      classes: ["name", "indent"],
    });

    // Column: Resident size (empty)
    this._addCell(row, {
      content: "",
      classes: ["totalResidentSize"],
    });

    // Column: CPU: User and Kernel
    {
      let slope = this._formatPercentage(data.slopeCpu);
      let text = `${slope} (${(
        data.totalCpu / MS_PER_NS
      ).toLocaleString(undefined, { maximumFractionDigits: 0 })} ms)`;
      this._addCell(row, {
        content: text,
        classes: ["cpu"],
      });
    }

    // Column: id
    this._addCell(row, {
      content: data.tid,
      classes: ["tid"],
    });

    // Column: Number of threads (empty)
    this._addCell(row, {
      content: "",
      classes: ["numberOfThreads"],
    });

    this._fragment.appendChild(row);
    return row;
  },

  _addCell(row, { content, classes }) {
    let elt = document.createElement("td");
    this._setTextAndTooltip(elt, content);
    elt.classList.add(...classes);
    row.appendChild(elt);
    return elt;
  },

  /**
   * Utility method to format an optional percentage.
   *
   * As a special case, we also handle `null`, which represents the case in which we do
   * not have sufficient information to compute a percentage.
   *
   * @param {Number?} value The value to format. Must be either `null` or a non-negative number.
   * A value of 1 means 100%. A value larger than 1 is possible as processes can use several
   * cores.
   * @return {String}
   */
  _formatPercentage(value) {
    if (value == null) {
      return "?";
    }
    if (value < 0 || typeof value != "number") {
      throw new Error(`Invalid percentage value ${value}`);
    }
    if (value == 0) {
      // Let's make sure that we do not confuse idle and "close to 0%",
      // otherwise this results in weird displays.
      return "idle";
    }
    // Now work with actual percentages.
    let percentage = value * 100;
    if (percentage < 0.01) {
      // Tiny percentage, let's display something more useful than "0".
      return "~0%";
    }
    if (percentage < 1) {
      // Still a small percentage, but it should fit within 2 digits.
      return `${percentage.toLocaleString(undefined, {
        maximumFractionDigits: 2,
      })}%`;
    }
    // For other percentages, just return a round number.
    return `${Math.round(percentage)}%`;
  },

  /**
   * Format a value representing an amount of memory.
   *
   * As a special case, we also handle `null`, which represents the case in which we do
   * not have sufficient information to compute an amount of memory.
   *
   * @param {Number?} value The value to format. Must be either `null` or a non-negative number.
   * @return { {unit: "GB" | "MB" | "KB" | B" | "?"}, amount: Number } The formated amount and its
   *  unit, which may be used for e.g. additional CSS formating.
   */
  _formatMemory(value) {
    if (value == null) {
      return { unit: "?", amount: 0 };
    }
    if (value < 0 || typeof value != "number") {
      throw new Error(`Invalid memory value ${value}`);
    }
    if (value >= ONE_GIGA) {
      return {
        unit: "GB",
        amount: Math.ceil((value / ONE_GIGA) * 100) / 100,
      };
    }
    if (value >= ONE_MEGA) {
      return {
        unit: "MB",
        amount: Math.ceil((value / ONE_MEGA) * 100) / 100,
      };
    }
    if (value >= ONE_KILO) {
      return {
        unit: "KB",
        amount: Math.ceil((value / ONE_KILO) * 100) / 100,
      };
    }
    return {
      unit: "B",
      amount: Math.round(value),
    };
  },

  /**
   * Format a value representing an amount of memory and a delta.
   *
   * @param {Number?} value The value to format. Must be either `null` or a non-negative number.
   * @param {Number?} value The delta to format. Must be either `null` or a non-negative number.
   * @return {
   *   {unitValue: "GB" | "MB" | "KB" | B" | "?"},
   *    formatedValue: string,
   *   {unitDelta: "GB" | "MB" | "KB" | B" | "?"},
   *    formatedDelta: string
   * }
   */
  _formatMemoryAndDelta(value, delta) {
    let formatedDelta;
    let unitDelta;
    if (delta == null) {
      formatedDelta == "";
      unitDelta = null;
    } else if (delta == 0) {
      formatedDelta = null;
      unitDelta = null;
    } else if (delta >= 0) {
      let { unit, amount } = this._formatMemory(delta);
      formatedDelta = ` (+${amount}${unit})`;
      unitDelta = unit;
    } else {
      let { unit, amount } = this._formatMemory(-delta);
      formatedDelta = ` (-${amount}${unit})`;
      unitDelta = unit;
    }
    let { unit: unitValue, amount } = this._formatMemory(value);
    return {
      unitValue,
      unitDelta,
      formatedDelta,
      formatedValue: `${amount}${unitValue}`,
    };
  },
  _setTextAndTooltip(elt, text, tooltip = text) {
    elt.textContent = text;
    elt.setAttribute("title", tooltip);
  },
};

var Control = {
  _openItems: new Set(),
  // The set of all processes reported as "hung" by the process hang monitor.
  //
  // type: Set<ChildID>
  _hungItems: new Set(),
  _sortColumn: null,
  _sortAscendent: true,
  _removeSubtree(row) {
    while (row.nextSibling && row.nextSibling.classList.contains("thread")) {
      row.nextSibling.remove();
    }
  },
  init() {
    this._initHangReports();

    let tbody = document.getElementById("process-tbody");
    tbody.addEventListener("click", event => {
      this._updateLastMouseEvent();

      // Handle showing or hiding subitems of a row.
      let target = event.target;
      if (target.classList.contains("twisty")) {
        let row = target.parentNode.parentNode;
        let id = row.process.pid;
        if (target.classList.toggle("open")) {
          this._openItems.add(id);
          this._showChildren(row);
          View.insertAfterRow(row);
        } else {
          this._openItems.delete(id);
          this._removeSubtree(row);
        }
        return;
      }

      // Handle selection changes
      let row = target.parentNode;
      if (this.selectedRow) {
        this.selectedRow.removeAttribute("selected");
      }
      if (row.windowId) {
        row.setAttribute("selected", "true");
        this.selectedRow = row;
      } else if (this.selectedRow) {
        this.selectedRow = null;
      }
    });

    tbody.addEventListener("mousemove", () => {
      this._updateLastMouseEvent();
    });

    window.addEventListener("visibilitychange", event => {
      if (!document.hidden) {
        this._updateDisplay(true);
      }
    });

    document
      .getElementById("process-thead")
      .addEventListener("click", async event => {
        if (!event.target.classList.contains("clickable")) {
          return;
        }

        if (this._sortColumn) {
          const td = document.getElementById(this._sortColumn);
          td.classList.remove("asc");
          td.classList.remove("desc");
        }

        const columnId = event.target.id;
        if (columnId == this._sortColumn) {
          // Reverse sorting order.
          this._sortAscendent = !this._sortAscendent;
        } else {
          this._sortColumn = columnId;
          this._sortAscendent = true;
        }

        if (this._sortAscendent) {
          event.target.classList.remove("desc");
          event.target.classList.add("asc");
        } else {
          event.target.classList.remove("asc");
          event.target.classList.add("desc");
        }

        await this._updateDisplay(true);
      });
  },
  _lastMouseEvent: 0,
  _updateLastMouseEvent() {
    this._lastMouseEvent = Date.now();
  },
  _initHangReports() {
    const PROCESS_HANG_REPORT_NOTIFICATION = "process-hang-report";

    // Receiving report of a hung child.
    // Let's store if for our next update.
    let hangReporter = report => {
      report.QueryInterface(Ci.nsIHangReport);
      this._hungItems.add(report.childID);
    };
    Services.obs.addObserver(hangReporter, PROCESS_HANG_REPORT_NOTIFICATION);

    // Don't forget to unregister the reporter.
    window.addEventListener(
      "unload",
      () => {
        Services.obs.removeObserver(
          hangReporter,
          PROCESS_HANG_REPORT_NOTIFICATION
        );
      },
      { once: true }
    );
  },
  async update() {
    await State.update();

    if (document.hidden) {
      return;
    }

    await wait(0);

    await this._updateDisplay();
  },

  // The force parameter can force a full update even when the mouse has been
  // moved recently.
  async _updateDisplay(force = false) {
    if (
      !force &&
      Date.now() - this._lastMouseEvent < TIME_BEFORE_SORTING_AGAIN
    ) {
      return;
    }

    let counters = State.getCounters();

    // Reset the selectedRow field and the _openItems set each time we redraw
    // to avoid keeping forever references to dead processes.
    let openItems = this._openItems;
    this._openItems = new Set();

    // Similarly, we reset `_hungItems`, based on the assumption that the process hang
    // monitor will inform us again before the next update. Since the process hang monitor
    // pings its clients about once per second and we update about once per 2 seconds
    // (or more if the mouse moves), we should be ok.
    let hungItems = this._hungItems;
    this._hungItems = new Set();

    counters = this._sortProcesses(counters);
    let previousRow = null;
    let previousProcess = null;
    for (let process of counters) {
      let isOpen = openItems.has(process.pid);
      process.isOpen = isOpen;

      let isHung = process.childID && hungItems.has(process.childID);
      process.isHung = isHung;

      let processRow = View.appendProcessRow(process, isOpen);
      processRow.process = process;

      let latestRow = processRow;
      if (isOpen) {
        this._openItems.add(process.pid);
        latestRow = this._showChildren(processRow);
      }
      if (
        this._sortColumn == null &&
        previousProcess &&
        previousProcess.displayRank != process.displayRank
      ) {
        // Add a separation between successive categories of processes.
        previousRow.classList.add("separate-from-next-process-group");
      }
      previousProcess = process;
      previousRow = latestRow;
    }

    await View.commit();
  },
  _showChildren(row) {
    let process = row.process;
    this._sortThreads(process.threads);
    let elt = row;
    for (let thread of process.threads) {
      // Enrich `elt` with a property `thread`, used for testing.
      elt = View.appendThreadRow(thread);
      elt.thread = thread;
    }
    return elt;
  },
  _sortThreads(threads) {
    return threads.sort((a, b) => {
      let order;
      switch (this._sortColumn) {
        case "column-name":
          order = a.name.localeCompare(b.name);
          break;
        case "column-cpu-total":
          order = b.totalCpu - a.totalCpu;
          if (order == 0) {
            order = b.totalCpu - a.totalCpu;
          }
          break;

        case "column-cpu-threads":
        case "column-memory-resident":
        case "column-type":
        case "column-pid":
        case null:
          order = b.tid - a.tid;
          break;
        default:
          throw new Error("Unsupported order: " + this._sortColumn);
      }
      if (!this._sortAscendent) {
        order = -order;
      }
      return order;
    });
  },
  _sortProcesses(counters) {
    return counters.sort((a, b) => {
      let order;
      switch (this._sortColumn) {
        case "column-pid":
          order = b.pid - a.pid;
          break;
        case "column-type":
          order = String(a.origin).localeCompare(b.origin);
          if (order == 0) {
            order = String(a.type).localeCompare(b.type);
          }
          break;
        case "column-name":
          order = String(a.name).localeCompare(b.name);
          break;
        case "column-cpu-total":
          order = b.totalCpu - a.totalCpu;
          if (order == 0) {
            order = b.totalCpu - a.totalCpu;
          }
          break;
        case "column-cpu-threads":
          order = b.threads.length - a.threads.length;
          break;
        case "column-memory-resident":
          order = b.totalResidentSize - a.totalResidentSize;
          break;
        case null:
          // Default order: classify processes by group.
          order = a.displayRank - b.displayRank;
          if (order == 0) {
            // Other processes are ordered by origin.
            order = String(a.name).localeCompare(b.name);
            if (order == 0) {
              // If we're running without Fission, many processes will have
              // the same origin, so differenciate with CPU use.
              order = b.slopeCpuUser - a.slopeCpuUser;
            }
          }
          break;
        default:
          throw new Error("Unsupported order: " + this._sortColumn);
      }
      if (!this._sortAscendent) {
        order = -order;
      }
      return order;
    });
  },

  // Assign a display rank to a process.
  //
  // The `browser` process comes first (rank 0).
  // Then comes web content (rank 1).
  // Then come special processes (minus preallocated) (rank 2).
  // Then come preallocated processes (rank 3).
  _getDisplayGroupRank(type) {
    switch (type) {
      // Browser comes first.
      case "browser":
        return 0;
      // Web content comes next.
      case "web":
      case "webIsolated":
      case "webLargeAllocation":
      case "withCoopCoep":
        return 1;
      // Preallocated processes come last.
      case "preallocated":
        return 3;
      // Other special processes before preallocated.
      default:
        return 2;
    }
  },
};

window.onload = async function() {
  Control.init();
  await Control.update();
  window.setInterval(() => Control.update(), UPDATE_INTERVAL_MS);
};
