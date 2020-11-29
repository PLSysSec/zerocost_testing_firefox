#!/usr/bin/python3

import os
import subprocess
import sys

print("WASM_CXX: " + str(sys.argv))
filtered_args = [x for x in sys.argv if not ("sysroot" in x or "wasm_to_mpk" in x)]
if "-Wl,--export-all" in filtered_args:
    filtered_args = [x.replace("-Wl,--export-all", "-shared") for x in filtered_args]
else:
    filtered_args += [ "-fPIC"]

filtered_args += [
    "-fno-asm", "-fno-asm-blocks", # avoid bypasses
    # need some form of shadow stack here. Safestack is not strong enough for mpk "-fsanitize=safe-stack"
    "-flto", "-fsanitize=cfi-icall", "-fsanitize-cfi-icall-generalize-pointers", "-fno-sanitize-cfi-cross-dso", # forward edge protection
    "-ftrivial-auto-var-init=zero", "-enable-trivial-auto-var-init-zero-knowing-it-will-be-removed-from-clang" # stack variable initialization
]

c = os.getenv("CXX")
if c is None:
    c = "clang++"
cmd = [c] + filtered_args

print("WASM_CXX cmd: " + str(cmd))

ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

if ret.stdout:
    print(ret.stdout)

if ret.returncode != 0:
    print("Error")
    sys.exit(ret.returncode)

print("Success")
