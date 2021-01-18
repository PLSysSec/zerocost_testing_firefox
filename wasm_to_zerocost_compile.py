#!/usr/bin/python3

import os
import subprocess
import sys
import pathlib

def compile(is_cpp, is_32_bit, args):
    currdir = pathlib.Path(__file__).parent.absolute()
    builds_path = os.path.join(currdir, "ffbuilds")
    if not os.path.isdir(builds_path):
        builds_path = "/mnt/sata/ffbuilds/"
    compiler_path = os.path.join(builds_path, "zerocost_llvm_install")
    compiler_lib_path = os.path.join(compiler_path, "lib/clang/12.0.0/")

    compiler = os.path.join(compiler_path, "bin/clang")
    if is_cpp:
        compiler = compiler + "++"

    print("wasm_to_zerocost: " + str(args))
    filtered_args = [x for x in args if not ("sysroot" in x or "wasm_to_" in x)]

    if is_32_bit:
        filtered_args += ["-m32"]

    if "-Wl,--export-all" in filtered_args:
        filtered_args = [x.replace("-Wl,--export-all", "-shared") for x in filtered_args]
    else:
        filtered_args += [ "-fPIC"]

    cfi_lib = compiler_lib_path
    if is_32_bit:
        cfi_lib = os.path.join(cfi_lib, "lib/linux/libclang_rt.cfi-i386.a")
    else:
        cfi_lib = os.path.join(cfi_lib, "lib/linux/libclang_rt.cfi-x86_64.a")

    filtered_args += [
        "-fno-asm", "-fno-asm-blocks", "-Werror=return-type", # avoid easy bypasses
        "-fsanitize=safe-stack", "-fstack-clash-protection", # Safe stack
        "-flto", "-fuse-ld=gold", # Clang flags needed for cfi and maybe other passes
        "-fsanitize=cfi-icall", "-fsanitize-cfi-canonical-jump-tables", "-fsanitize-cfi-cross-dso", # forward edge protection
        cfi_lib, # clang cfi runtime library
        "-ftrivial-auto-var-init=zero", "-enable-trivial-auto-var-init-zero-knowing-it-will-be-removed-from-clang" # stack variable initialization
    ]

    cmd = [compiler] + filtered_args

    print("wasm_to_zerocost cmd: " + str(cmd))

    ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

    if ret.stdout:
        print(ret.stdout)

    if ret.returncode != 0:
        print("Error")
        sys.exit(ret.returncode)

    print("Success")
