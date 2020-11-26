#!/usr/bin/python3

import os
import subprocess
import sys

print("WASM_CXX: " + str(sys.argv))

inputfile = [x for x in sys.argv if x.endswith(".wasm")][0]
outputfile = [x for x in sys.argv if x.endswith(".so")][0]
print("Input: " + inputfile + " Outputfile: " + outputfile)

ret = subprocess.run(["cp", inputfile, outputfile], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

if ret.stdout:
    print(ret.stdout)

if ret.returncode != 0:
    print("Error")
    sys.exit(ret.returncode)

print("Success")
