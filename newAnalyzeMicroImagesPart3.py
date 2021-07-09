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
    raise RuntimeError("Group not found: " + group)

def getGroups(els):
    ret = []
    for el in els:
        group_name = el["Group"].split('/')[-1]
        ret = ret + [group_name]
    return ret

def getOverhead(base, other):
    return str(round(base/other, 3))

def computeSummaryWasm(summaryFile, parsed1, parsed2, parsed3, parsed4):
    with open(summaryFile, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "Zerocost", "FullSave", "RegSave", "Lucet"])

        groups = getGroups(parsed1)
        for group in groups:
            zerocost_val = getMedian(parsed1, group)
            fullsave_val = getMedian(parsed2, group)
            regsave_val = getMedian(parsed3, group)
            lucet_val = getMedian(parsed4, group)

            writer.writerow([
                group,
                str(zerocost_val)        + " (" + getOverhead(zerocost_val       , zerocost_val) + ")",
                str(fullsave_val)        + " (" + getOverhead(fullsave_val       , zerocost_val) + ")",
                str(regsave_val)         + " (" + getOverhead(regsave_val        , zerocost_val) + ")",
                str(lucet_val)           + " (" + getOverhead(lucet_val          , zerocost_val) + ")"
            ])

def computeSummary64(summaryFile, parsed1, parsed2):
    with open(summaryFile, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "Stock64", "IdealHeavy64"])

        groups = getGroups(parsed1)
        for group in groups:
            stock_val = getMedian(parsed1, group)
            mpk_val = getMedian(parsed2, group)

            writer.writerow([
                group,
                str(stock_val)  + " (" + getOverhead(stock_val  , stock_val) + ")",
                str(mpk_val) + " (" + getOverhead(mpk_val , stock_val) + ")",
            ])

def computeSummary32(summaryFile, parsed1, parsed2, parsed3, parsed4, parsed5):
    with open(summaryFile, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "Stock", "SegmentSFI", "IdealHeavy", "NaCl", "StockIndirect"])

        groups = getGroups(parsed1)
        for group in groups:
            stock_val = getMedian(parsed1, group)
            segmentsfi_val = getMedian(parsed2, group)
            mpk_val = getMedian(parsed3, group)
            nacl_val = getMedian(parsed4, group)
            stockindirect_val = getMedian(parsed5, group)

            writer.writerow([
                group,
                str(stock_val)  + " (" + getOverhead(stock_val  , stock_val) + ")",
                str(segmentsfi_val) + " (" + getOverhead(segmentsfi_val , stock_val) + ")",
                str(mpk_val) + " (" + getOverhead(mpk_val , stock_val) + ")",
                str(nacl_val) + " (" + getOverhead(nacl_val , stock_val) + ")",
                str(stockindirect_val) + " (" + getOverhead(stockindirect_val , stock_val) + ")",
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

    if os.path.exists(os.path.join(inputFolderName, "zerocost_terminal_analysis.json")):
        parsed1 = json.loads(read(inputFolderName, "zerocost_terminal_analysis.json"))["data"]
        parsed2 = json.loads(read(inputFolderName, "fullsave_terminal_analysis.json"))["data"]
        parsed3 = json.loads(read(inputFolderName, "regsave_terminal_analysis.json"))["data"]
        parsed4 = json.loads(read(inputFolderName, "lucet_terminal_analysis.json"))["data"]
        computeSummaryWasm(os.path.join(inputFolderName, "all_compareWasm.dat"), parsed1, parsed2, parsed3, parsed4)

    if os.path.exists(os.path.join(inputFolderName, "mpkfullsave_terminal_analysis.json")):
        parsed1 = json.loads(read(inputFolderName, "stock_terminal_analysis.json"))["data"]
        parsed2 = json.loads(read(inputFolderName, "mpkfullsave_terminal_analysis.json"))["data"]
        computeSummary64(os.path.join(inputFolderName, "all_compare64.dat"), parsed1, parsed2)

    if os.path.exists(os.path.join(inputFolderName, "segmentsfizerocost_terminal_analysis.json")):
        parsed1 = json.loads(read(inputFolderName, "stock32_terminal_analysis.json"))["data"]
        parsed2 = json.loads(read(inputFolderName, "segmentsfizerocost_terminal_analysis.json"))["data"]
        parsed3 = json.loads(read(inputFolderName, "mpkfullsave32_terminal_analysis.json"))["data"]
        parsed4 = json.loads(read(inputFolderName, "naclfullsave32_terminal_analysis.json"))["data"]
        parsed5 = json.loads(read(inputFolderName, "stockindirect32_terminal_analysis.json"))["data"]
        computeSummary32(os.path.join(inputFolderName, "all_compare32.dat"), parsed1, parsed2, parsed3, parsed4, parsed5)

main()
