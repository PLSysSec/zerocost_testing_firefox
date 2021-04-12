#!/usr/bin/python3

import os
import subprocess
import sys
import pathlib

def compile(is_cpp, is_32_bit, args):
    currdir = pathlib.Path(__file__).parent.absolute()
    nacl_src_path = os.path.join(currdir, "..", "rlbox_nacl_sandbox/build_release/_deps/modnacl-src")
    compiler_path = os.path.join(nacl_src_path, "native_client/toolchain/linux_x86/pnacl_newlib_raw/bin/")
    nacl_wrapper_path = os.path.join(nacl_src_path, "native_client/src/trusted/dyn_ldr/dyn_ldr_sandbox_init.c")

    compiler = os.path.join(compiler_path, "i686-nacl-clang")
    if is_cpp:
        compiler = compiler + "++"

    print("wasm_to_nacl: " + str(args))
    filtered_args = [x for x in args if not ("sysroot" in x or "wasm_to_" in x)]

    def replace_wrapper(s):
        if "lucet_sandbox_wrapper.c" in s:
            return nacl_wrapper_path
        else:
            return s

    filtered_args = [replace_wrapper(x) for x in filtered_args]
    if nacl_wrapper_path in filtered_args:
        filtered_args += ["-I" + nacl_src_path ]

    if is_32_bit:
        filtered_args += ["-m32"]

    if is_cpp:
        filtered_args += ["-std=c++11"]

    filtered_args = [x for x in filtered_args if not ("-Wl,--export-all" in x)]

    cmd = [compiler] + filtered_args

    print("wasm_to_nacl cmd: " + str(cmd))

    ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

    if ret.stdout:
        print(ret.stdout)

    if ret.returncode != 0:
        print("Error")
        sys.exit(ret.returncode)

    print("Success")
