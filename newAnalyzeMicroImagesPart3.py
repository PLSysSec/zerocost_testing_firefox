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

def getOverhead(base, other):
    return str(base/other)

def computeSummary64(summaryFile, parsed1, parsed2, parsed3, parsed5, parsed6):
    with open(summaryFile, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "Zerocost", "FullSave", "RegSave", "Lucet", "FullSaveWindows"])

        groups = getGroups(parsed1)
        for group in groups:
            zerocost_val = getMedian(parsed1, group)
            fullsave_val = getMedian(parsed2, group)
            regsave_val = getMedian(parsed3, group)
            lucet_val = getMedian(parsed5, group)
            fullsavewindows_val = getMedian(parsed6, group)

            writer.writerow([
                group,
                str(zerocost_val)        + " (" + getOverhead(zerocost_val       , zerocost_val) + ")",
                str(fullsave_val)        + " (" + getOverhead(fullsave_val       , zerocost_val) + ")",
                str(regsave_val)         + " (" + getOverhead(regsave_val        , zerocost_val) + ")",
                str(lucet_val)           + " (" + getOverhead(lucet_val          , zerocost_val) + ")",
                str(fullsavewindows_val) + " (" + getOverhead(fullsavewindows_val, zerocost_val) + ")"
            ])

def computeSummary32(summaryFile, parsed1, parsed2):
    with open(summaryFile, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "Stock", "SegmentSfi"])

        groups = getGroups(parsed1)
        for group in groups:
            stock_val = getMedian(parsed1, group)
            segmentsfi_val = getMedian(parsed2, group)

            writer.writerow([
                group,
                str(stock_val)        + " (" + getOverhead(stock_val             , stock_val) + ")",
                str(segmentsfi_val)   + " (" + getOverhead(segmentsfi_val        , stock_val) + ")"
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

    parsed1 = json.loads(read(inputFolderName, "zerocost_terminal_analysis.json"))["data"]
    parsed2 = json.loads(read(inputFolderName, "fullsave_terminal_analysis.json"))["data"]
    parsed3 = json.loads(read(inputFolderName, "regsave_terminal_analysis.json"))["data"]
    parsed5 = json.loads(read(inputFolderName, "lucet_terminal_analysis.json"))["data"]
    parsed6 = json.loads(read(inputFolderName, "fullsavewindows_terminal_analysis.json"))["data"]
    parsed7 = json.loads(read(inputFolderName, "stock32_terminal_analysis.json"))["data"]
    parsed8 = json.loads(read(inputFolderName, "segmentsfi_terminal_analysis.json"))["data"]

    computeSummary64(os.path.join(inputFolderName, "all_compare.dat"), parsed1, parsed2, parsed3, parsed5, parsed6)
    computeSummary32(os.path.join(inputFolderName, "all_compare32.dat"), parsed7, parsed8)

main()
