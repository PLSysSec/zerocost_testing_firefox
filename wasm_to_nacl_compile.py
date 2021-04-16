#!/usr/bin/python3

import os
import subprocess
import sys
import pathlib

def compile(is_cpp, is_32_bit, args):
    currdir = pathlib.Path(__file__).parent.absolute()
    nacl_src_path = os.path.join(currdir, "..", "Sandboxing_NaCl")
    compiler_path = os.path.join(nacl_src_path, "native_client/toolchain/linux_x86/pnacl_newlib_raw/bin/")
    nacl_wrapper_path = os.path.join(nacl_src_path, "native_client/src/trusted/dyn_ldr/dyn_ldr_sandbox_init.c")

    compiler_c = os.path.join(compiler_path, "i686-nacl-clang")
    compiler = compiler_c
    if is_cpp:
        compiler = compiler + "++"

    print("wasm_to_nacl: " + str(args))


    if any("lucet_sandbox_wrapper.c" in x for x in args):
        print("compiling wrapper")
        output_flag = args.index("-o")
        output_name = args[output_flag+1]

        cmd = [compiler_c, nacl_wrapper_path, "-O3", "-I" + nacl_src_path, "-c", "-o", output_name ]

        if is_32_bit:
            cmd += ["-m32"]
    else:
        filtered_args = [x for x in args if not ("sysroot" in x or "wasm_to_" in x)]

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
