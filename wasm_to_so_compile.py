#!/usr/bin/python3

#!/usr/bin/python3

import os
import subprocess
import sys
import pathlib

def compile(is_cpp, is_32_bit, args):
    currdir = pathlib.Path(__file__).parent.absolute()
    builds_path = os.path.join(currdir, "..", "ffbuilds")
    if not os.path.isdir(builds_path):
        builds_path = "/mnt/sata/ffbuilds/"
    compiler_path = os.path.join(builds_path, "zerocost_llvm_install")

    compiler = os.path.join(compiler_path, "bin/clang")
    if is_cpp:
        compiler = compiler + "++"

    print("wasm_to_so: " + str(args))
    filtered_args = [x for x in args if not ("sysroot" in x or "wasm_to_" in x)]

    if is_32_bit:
        filtered_args += ["-m32"]

    if "-Wl,--export-all" in filtered_args:
        filtered_args = [x.replace("-Wl,--export-all", "-shared") for x in filtered_args]
    else:
        filtered_args += [ "-fPIC"]

    cmd = [compiler] + filtered_args

    print("wasm_to_so cmd: " + str(cmd))

    ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

    if ret.stdout:
        print(ret.stdout)

    if ret.returncode != 0:
        print("Error")
        sys.exit(ret.returncode)

    print("Success")
