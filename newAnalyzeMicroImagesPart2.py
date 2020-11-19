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
    sys.exit("Unreachable")

def computeSummary(summaryFile, ext, parsed1, parsed2):
    with open(summaryFile, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "FullSave"])
        for qual in ["best", "default", "none"]:
            for res, label in {"1920" : "\\n1280p", "480" : "{0}\\n320p", "240" : "\\n135p"}.items():
                group_suffix = qual + "_" + res + "." + ext
                zerocost_val = getMedian(parsed1, group_suffix)
                fullsave_val = getMedian(parsed2, group_suffix)
                writer.writerow([ label.replace("{0}", qual), fullsave_val/zerocost_val ])

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

    parsed1 = json.loads(input1)["data"]
    parsed2 = json.loads(input2)["data"]

    computeSummary(os.path.join(inputFolderName, "jpeg_perf.dat"), "jpeg", parsed1, parsed2)
main()
