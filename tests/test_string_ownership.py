"""Compile repository sources against a tracking host, without Xcode release phases."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CASES = ("push", "narrow", "wide-utf8", "wide", "utf16", "getter", "callback", "scalar", "array")


def compile_source(command):
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        print(result.stdout)
    result.check_returncode()


class StringOwnershipTests(unittest.TestCase):
    def test_actual_sdk_and_wrappers(self):
        source = Path(os.environ.get("HL7_OWNERSHIP_SOURCE", ROOT)).resolve()
        with tempfile.TemporaryDirectory(prefix="hl7-ownership-") as directory:
            build = Path(directory)
            includes = [
                "-I" + str(source / path)
                for path in (".", "4D Plugin API", "4D Plugin API/Classes", "support", "include")
            ]
            objects = []
            for path in sorted((source / "hl7parser").glob("*.c")):
                obj = build / (path.stem + ".o")
                compile_source(["clang", "-c", str(path), *includes, "-o", str(obj)])
                objects.append(str(obj))
            executable = build / "string-ownership"
            compile_source([
                "clang++", "-std=c++11", "-Wno-multichar",
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                *includes, "-x", "objective-c++",
                str(source / "tests/string_ownership.cpp"),
                str(source / "4D Plugin API/4DPluginAPI.c"),
                str(source / "4D Plugin API/Classes/C_TEXT.cpp"),
                str(source / "4D Plugin API/Classes/ARRAY_TEXT.cpp"),
                str(source / "support/4DPlugin-JSON.cpp"),
                "-x", "none", *objects,
                "-framework", "Cocoa", "-framework", "CoreFoundation",
                "-framework", "CoreGraphics", "-o", str(executable),
            ])
            environment = dict(os.environ, UBSAN_OPTIONS="halt_on_error=1")
            for mode in ("allocated", "null"):
                for case in CASES:
                    with self.subTest(case=case, empty=mode):
                        subprocess.run([str(executable), case, mode], check=True, env=environment)


if __name__ == "__main__":
    unittest.main()
