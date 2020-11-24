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

gResLabel = {
    "1920" : "\\n1280p",
    "480" : "{0}\\n320p",
    "240" : "\\n135p",
    "width_10": "10",
    "width_20": "20",
    "width_30": "30",
    "width_60": "60",
    "width_120": "120",
    "width_240": "240",
    "width_480": "480",
    "width_960": "960",
    "width_1440": "1440",
    "width_1920": "1920",
}

def computeSummary(summaryFile, ext, parsed1, parsed2, parsed3, parsed4):
    with open(summaryFile, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "FullSave", "RegSave", "MPKFullSave"])
        for qual in ["best", "default", "none"]:
            for res, label in gResLabel.items():
                try:
                    group_suffix = qual + "_" + res + "." + ext
                    zerocost_val = getMedian(parsed1, group_suffix)
                    fullsave_val = getMedian(parsed2, group_suffix)
                    regsave_val = getMedian(parsed3, group_suffix)
                    mpkfullsave_val = getMedian(parsed4, group_suffix)
                    writer.writerow([ label.replace("{0}", qual),
                        fullsave_val/zerocost_val,
                        regsave_val/zerocost_val,
                        mpkfullsave_val/zerocost_val ])
                except:
                    pass

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

    parsed1 = json.loads(input1)["data"]
    parsed2 = json.loads(input2)["data"]
    parsed3 = json.loads(input3)["data"]
    parsed4 = json.loads(input4)["data"]

    computeSummary(os.path.join(inputFolderName, "jpeg_perf.dat"), "jpeg", parsed1, parsed2, parsed3, parsed4)
main()
