#!/usr/bin/python3

import os
import subprocess
import sys

print("WASM_CC: " + str(sys.argv))
filtered_args = [x for x in sys.argv if not ("sysroot" in x or "wasm_to_mpk" in x)]
if "-Wl,--export-all" in filtered_args:
    filtered_args = [x.replace("-Wl,--export-all", "-shared") for x in filtered_args]
else:
    filtered_args += [ "-fPIC"]

c = os.getenv("CC")
if c is None:
    c = "clang"
cmd = [c] + filtered_args

print("WASM_CC cmd: " + str(cmd))

ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

if ret.stdout:
    print(ret.stdout)

if ret.returncode != 0:
    print("Error")
    sys.exit(ret.returncode)

print("Success")
