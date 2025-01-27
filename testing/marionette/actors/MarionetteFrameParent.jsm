/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

("use strict");

const EXPORTED_SYMBOLS = ["MarionetteFrameParent"];

const { XPCOMUtils } = ChromeUtils.import(
  "resource://gre/modules/XPCOMUtils.jsm"
);

const { EventEmitter } = ChromeUtils.import(
  "resource://gre/modules/EventEmitter.jsm"
);

const { WebDriverError } = ChromeUtils.import(
  "chrome://marionette/content/error.js"
);
const { evaluate } = ChromeUtils.import(
  "chrome://marionette/content/evaluate.js"
);
const { Log } = ChromeUtils.import("chrome://marionette/content/log.js");

XPCOMUtils.defineLazyGetter(this, "logger", Log.get);

class MarionetteFrameParent extends JSWindowActorParent {
  constructor() {
    super();

    EventEmitter.decorate(this);
  }

  actorCreated() {
    logger.trace(`[${this.browsingContext.id}] Parent actor created`);
  }

  receiveMessage(msg) {
    const { name, data } = msg;

    switch (name) {
      case "MarionetteFrameChild:PageLoadEvent":
        this.emit("page-load-event", data);
        break;
    }
  }

  async sendQuery(name, data) {
    const serializedData = evaluate.toJSON(data);
    const result = await super.sendQuery(name, serializedData);

    if ("error" in result) {
      throw WebDriverError.fromJSON(result.error);
    } else {
      return evaluate.fromJSON(result.data);
    }
  }

  // Proxying methods for WebDriver commands
  // TODO: Maybe using a proxy class instead similar to proxy.js

  findElement(strategy, selector, opts) {
    return this.sendQuery("MarionetteFrameParent:findElement", {
      strategy,
      selector,
      opts,
    });
  }

  findElements(strategy, selector, opts) {
    return this.sendQuery("MarionetteFrameParent:findElements", {
      strategy,
      selector,
      opts,
    });
  }

  async getElementAttribute(webEl, name) {
    return this.sendQuery("MarionetteFrameParent:getElementAttribute", {
      name,
      webEl,
    });
  }

  async getElementProperty(webEl, name) {
    return this.sendQuery("MarionetteFrameParent:getElementProperty", {
      name,
      webEl,
    });
  }

  async switchToFrame(id) {
    const {
      browsingContextId,
    } = await this.sendQuery("MarionetteFrameParent:switchToFrame", { id });

    return {
      browsingContext: BrowsingContext.get(browsingContextId),
    };
  }

  async switchToParentFrame() {
    const { browsingContextId } = await this.sendQuery(
      "MarionetteFrameParent:switchToParentFrame"
    );

    return {
      browsingContext: BrowsingContext.get(browsingContextId),
    };
  }
}
