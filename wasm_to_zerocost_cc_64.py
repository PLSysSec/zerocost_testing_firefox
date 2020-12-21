#!/usr/bin/python3

import os
import subprocess
import sys

compiler_path = "/usr/lib/llvm-11/lib/clang/11.0.0/"

print("WASM_CC: " + str(sys.argv))
filtered_args = [x for x in sys.argv if not ("sysroot" in x or "wasm_to_mpk" in x)]
if "-Wl,--export-all" in filtered_args:
    filtered_args = [x.replace("-Wl,--export-all", "-shared") for x in filtered_args]
else:
    filtered_args += [ "-fPIC"]

filtered_args += [
    "-fno-asm", "-fno-asm-blocks", # avoid easy bypasses
    "-fsanitize=safe-stack", "-fstack-clash-protection", # Safe stack
    "-flto", "-fuse-ld=lld", # Clang flags needed for cfi and maybe other passes
    "-fsanitize=cfi-icall", "-fsanitize-cfi-canonical-jump-tables", "-fsanitize-cfi-cross-dso", # forward edge protection
    compiler_path + "lib/linux/libclang_rt.cfi-x86_64.a", # clang cfi runtime library
    "-ftrivial-auto-var-init=zero", "-enable-trivial-auto-var-init-zero-knowing-it-will-be-removed-from-clang" # stack variable initialization
]

c = os.getenv("CC")
if c is None:
    c = "clang-11"
cmd = [c] + filtered_args

print("WASM_CC cmd: " + str(cmd))

ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

if ret.stdout:
    print(ret.stdout)

if ret.returncode != 0:
    print("Error")
    sys.exit(ret.returncode)

print("Success")
