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

def computeSummary(summaryFile, parsed1, parsed2, parsed3, parsed5, parsed6):
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
                str(zerocost_val)        + " (" + str(zerocost_val        / zerocost_val) + ")",
                str(fullsave_val)        + " (" + str(fullsave_val        / zerocost_val) + ")",
                str(regsave_val)         + " (" + str(regsave_val         / zerocost_val) + ")",
                str(lucet_val)           + " (" + str(lucet_val           / zerocost_val) + ")",
                str(fullsavewindows_val) + " (" + str(fullsavewindows_val / zerocost_val) + ")"
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
    input5 = read(inputFolderName, "lucet_terminal_analysis.json")
    input6 = read(inputFolderName, "fullsavewindows_terminal_analysis.json")

    parsed1 = json.loads(input1)["data"]
    parsed2 = json.loads(input2)["data"]
    parsed3 = json.loads(input3)["data"]
    parsed5 = json.loads(input5)["data"]
    parsed6 = json.loads(input6)["data"]

    computeSummary(os.path.join(inputFolderName, "all_compare.dat"), parsed1, parsed2, parsed3, parsed5, parsed6)

main()
