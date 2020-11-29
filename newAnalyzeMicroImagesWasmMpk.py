#!/usr/bin/env python3

import math
import sys
import csv
import os
from urllib.parse import urlparse
import simplejson as json

def getMedian(els, group):
    for el in els:
        if group in el["Group"]:
            return float(el["Median"].replace(',', ''))
    raise RuntimeError("Group not found")

def getGroups(els):
    ret = []
    for el in els:
        group_name = el["Group"].split('/')[-1]
        ret = ret + [group_name]
    return ret

def computeSummary(summaryFile, ext, parsed1, parsed2, parsed3, parsed4, parsed5, parsed6):
    with open(summaryFile, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "FullSave", "Zerocost", "Transitions",
            "MPKFullSave", "MPK(no transitions)", "Wasm overhead over mpk full save",  "Wasm overhead over native", "Required Wasm overhead for MPK perf"])

        groups = getGroups(parsed1)
        for group in groups:
            zerocost_val = getMedian(parsed1, group)
            fullsave_val = getMedian(parsed2, group)
            regsave_val = getMedian(parsed3, group)
            mpkfullsave_val = getMedian(parsed4, group)
            lucet_val = getMedian(parsed5, group_suffix)
            fullsavewindows_val = getMedian(parsed6, group)

            transitions = fullsave_val - zerocost_val
            mpk_only = mpkfullsave_val - transitions
            wasm_mpkfull_overhead = zerocost_val / mpkfullsave_val
            wasm_native_overhead = zerocost_val / mpk_only
            required_wasm_overhead = mpkfullsave_val / mpk_only

            writer.writerow([
                group,
                fullsave_val,
                zerocost_val,
                transitions,
                mpkfullsave_val,
                mpk_only,
                wasm_mpkfull_overhead,
                wasm_native_overhead,
                required_wasm_overhead
            ])

def read(folder, filename):
    inputFileName1 = os.path.join(folder, filename)
    with open(inputFileName1) as f:
        input1 = f.read()
    return input1

def main():
    if len(sys.argv) < 2:
        print("Expected " + sys.argv[0] + " inputFolderName")
        exit(1)
    inputFolderName = sys.argv[1]

    input1 = read(inputFolderName, "zerocost_terminal_analysis.json")
    input2 = read(inputFolderName, "fullsave_terminal_analysis.json")
    input3 = read(inputFolderName, "regsave_terminal_analysis.json")
    input4 = read(inputFolderName, "mpkfullsave_terminal_analysis.json")
    input5 = read(inputFolderName, "lucet_terminal_analysis.json")
    input6 = read(inputFolderName, "fullsavewindows_terminal_analysis.json")

    parsed1 = json.loads(input1)["data"]
    parsed2 = json.loads(input2)["data"]
    parsed3 = json.loads(input3)["data"]
    parsed4 = json.loads(input4)["data"]
    parsed5 = json.loads(input5)["data"]
    parsed6 = json.loads(input6)["data"]

    computeSummary(os.path.join(inputFolderName, "wasm_mpk.dat"), "jpeg", parsed1, parsed2, parsed3, parsed4, parsed5, parsed6)

main()
