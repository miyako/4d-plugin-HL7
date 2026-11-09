"""Execute native-step wiring with stubs, never native compilers or signing."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILD = (ROOT / ".github/workflows/release.yml").read_text()
BUMP = (ROOT / ".github/workflows/bump-version.yml").read_text()


def step(name):
    match = re.search(
        rf"      - name: {re.escape(name)}\n(.*?)(?=\n      - |\Z)", BUILD, re.S
    )
    if not match:
        raise AssertionError(f"Missing step: {name}")
    script = match[1].split("        run: |\n", 1)[1]
    script = "\n".join(line[10:] for line in script.splitlines())
    return script.replace("${{ env.PRODUCT_NAME }}", "HL7").replace(
        "${{ env.BASE_DIR }}", "test"
    ).replace("${{ env.MACOS_DEPLOYMENT_TARGET }}", "11.0").replace(
        "${{ needs.version.outputs.version }}", "3.2.1"
    )


class WiringTests(unittest.TestCase):
    def test_manual_immutable_source_and_cross_branch_serialization(self):
        self.assertRegex(BUILD, r"(?m)^name: Build$")
        for workflow in (BUILD, BUMP):
            events = workflow.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
            self.assertNotRegex(events, r"(?m)^  (push|pull_request|workflow_call|schedule):")
            for checkout in workflow.split("uses: actions/checkout@v4")[1:]:
                self.assertIn("ref: ${{ github.sha }}", checkout.split("\n      - ", 1)[0])
            self.assertNotIn("refs/heads/main", workflow)
            self.assertNotIn("github.ref == ", workflow)
        self.assertEqual(BUILD.count("uses: actions/checkout@v4"), 3)
        self.assertEqual(BUILD.split("\non:\n")[1].split("\npermissions:")[0].strip(),
                         "workflow_dispatch:")
        self.assertIn("group: release-publication\n  cancel-in-progress: false", BUILD)
        self.assertIn('test "$REF_TYPE" = branch', BUMP)
        self.assertIn('bump --sha "$SELECTED_SHA" --branch "$SELECTED_BRANCH" --mode "$MODE"', BUMP)
        self.assertIn("ref: ${{ github.sha }}\n          fetch-depth: 0", BUMP)
        self.assertNotIn("git tag", BUMP)
        self.assertNotIn("workflow run", BUMP)
        self.assertIn("preflight --sha", BUILD)
        self.assertIn('publish --sha "$SELECTED_SHA" "$ZIP_PATH" "$DMG_PATH"', BUILD)
        self.assertNotIn("softprops", BUILD)
        self.assertNotIn("inputs.", BUILD)

    def test_native_contract_and_secrets_retained(self):
        original = subprocess.run(
            ["git", "show", "38533629c48e67fe4b3d1ce48c4cea7f44597ee3:.github/workflows/release.yml"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
        self.assertEqual(set(re.findall(r"secrets\.([A-Z_]+)", original)),
                         set(re.findall(r"secrets\.([A-Z_]+)", BUILD)))
        for fragment in (
            "runs-on: windows-latest", "runs-on: macos-latest",
            "uses: microsoft/setup-msbuild@v2",
            'msbuild "%PRODUCT_NAME%.sln" /p:Configuration=Release /p:Platform=x64 '
            "/p:PlatformToolset=v143 /p:WindowsTargetPlatformVersion=10.0 /m",
            "MACOS_DEPLOYMENT_TARGET: '11.0'", "BASE_DIR: test",
            "name: windows-binaries",
            "ARCHS=\"arm64 x86_64\"", "ONLY_ACTIVE_ARCH=NO",
            "-configuration Default", "CODE_SIGNING_ALLOWED=NO",
            'CONFIGURATION_BUILD_DIR="$PWD/$PLUGINS_DIR"',
            "codesign --verify --deep --strict --verbose=2",
            "codesign --verbose --deep --timestamp --force --options=runtime",
            'ditto -c -k --keepParent "$BUNDLE_PATH" "$ZIP_PATH"',
            'hdiutil create -format UDBZ -volname "$PRODUCT" -srcfolder "$BUNDLE_PATH" "$DMG_PATH"',
            'xcrun stapler staple "$DMG_PATH"',
        ):
            self.assertIn(fragment, original)
            self.assertIn(fragment, BUILD)
        self.assertLess(BUILD.index("preflight --sha"), BUILD.index("name: setup MSBuild"))
        self.assertLess(BUILD.index('xcrun stapler validate "$DMG_PATH"'),
                        BUILD.index("publish --sha"))
        self.assertIn("Contents/Windows64/${{ env.PRODUCT_NAME }}.4DX", BUILD)
        self.assertIn("if-no-files-found: error", BUILD)


class NativeStubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".native-stubs-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "stubs"
        self.bin.mkdir()
        self.log = self.root / "commands.jsonl"
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        RUNNER_TEMP=str(self.root), GITHUB_ENV=str(self.root / "env"),
                        KEYCHAIN_PATH="test-keychain", BUNDLE_PATH="test/Plugins/HL7.bundle",
                        LOG=str(self.log))
        stub = f"""#!{sys.executable}
import json, os
from pathlib import Path
import sys
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["LOG"], "a") as log:
    log.write(json.dumps([name, args]) + "\\n")
if os.environ.get("FAIL_TOOL") == name:
    sys.exit(1)
if name == "xcodebuild":
    Path("test/Plugins").mkdir(parents=True, exist_ok=True)
    if os.environ.get("OMIT_MAC") != "1":
        p = Path("test/Plugins/HL7.bundle/Contents/MacOS/HL7")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fresh-selected-source")
elif name == "security":
    print('1) TEST "Developer ID Application: Stub"')
elif name == "ditto":
    Path(args[-1]).write_bytes(b"zip")
elif name == "hdiutil":
    Path(args[-1]).write_bytes(b"dmg")
elif name == "xcrun" and args[:2] == ["notarytool", "submit"]:
    status = os.environ.get("NOTARY_STATUS", "Accepted")
    if os.environ.get("INVALID_DMG") == "1" and args[2].endswith(".dmg"):
        status = "Invalid"
    if status == "malformed":
        print("not JSON")
    else:
        print(json.dumps({{"status": status}}))
"""
        for name in ("xcodebuild", "lipo", "security", "codesign", "ditto", "hdiutil", "xcrun"):
            path = self.bin / name
            path.write_text(stub)
            path.chmod(0o755)

    def run_step(self, name, **env):
        return subprocess.run(
            ["bash", "-c", step(name)], cwd=self.root, env=dict(self.env, **env),
            capture_output=True, text=True,
        )

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_mac_build_removes_stale_products_and_incremental_cache(self):
        stale = self.root / "test/Plugins/HL7.bundle/Contents/MacOS/HL7"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"stale")
        cache = self.root / "build/HL7.build/stale.o"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"stale")
        result = self.run_step("build macOS plugin (universal)")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stale.read_bytes(), b"fresh-selected-source")
        self.assertFalse(cache.exists())
        self.assertEqual(self.calls()[0][0], "xcodebuild")
        self.assertEqual(self.calls()[0][1][-2:], ["clean", "build"])
        self.assertEqual(self.run_step("verify universal binary").returncode, 0)
        self.assertEqual(self.calls()[-1], [
            "lipo", ["-verify_arch", "arm64", "x86_64", "test/Plugins/HL7.bundle/Contents/MacOS/HL7"]
        ])
        self.assertNotEqual(self.run_step("verify universal binary", FAIL_TOOL="lipo").returncode, 0)

    def test_missing_mac_output_and_build_failure_stop(self):
        (self.root / "test/Plugins").mkdir(parents=True)
        self.assertEqual(self.run_step("build macOS plugin (universal)", OMIT_MAC="1").returncode, 0)
        self.assertNotEqual(self.run_step("verify universal binary").returncode, 0)
        self.assertNotEqual(self.run_step("build macOS plugin (universal)",
                                         FAIL_TOOL="xcodebuild").returncode, 0)

    def test_exact_windows_merge_rejects_recursive_decoy(self):
        decoy = self.root / "winbuild/old/HL7.4DX"
        decoy.parent.mkdir(parents=True)
        decoy.write_bytes(b"stale")
        self.assertNotEqual(self.run_step("merge Windows binaries into the bundle").returncode, 0)
        exact = self.root / "winbuild/HL7.4DX"
        exact.write_bytes(b"fresh")
        result = self.run_step("merge Windows binaries into the bundle")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "test/Plugins/HL7.bundle/Contents/Windows64/HL7.4DX")
                         .read_bytes(), b"fresh")

    def test_codesign_failure_is_fatal(self):
        self.assertEqual(self.run_step("codesign").returncode, 0)
        self.assertNotEqual(self.run_step("codesign", FAIL_TOOL="codesign").returncode, 0)
        self.assertIn(["codesign", ["--verify", "--deep", "--strict", "--verbose=2",
                                   "test/Plugins/HL7.bundle"]], self.calls())

    def test_notary_acceptance_both_assets_and_staple_validation(self):
        for status in ("Invalid", "In Progress", "malformed"):
            with self.subTest(status=status):
                result = self.run_step("package, notarize & staple", NOTARY_STATUS=status)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(["xcrun", ["stapler", "staple", "HL7-3.2.1.dmg"]], self.calls())
                self.log.unlink()
        self.assertNotEqual(self.run_step("package, notarize & staple",
                                         INVALID_DMG="1").returncode, 0)
        self.assertNotIn(["xcrun", ["stapler", "staple", "HL7-3.2.1.dmg"]], self.calls())
        self.log.unlink()
        result = self.run_step("package, notarize & staple")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(calls[-2:], [
            ["xcrun", ["stapler", "staple", "HL7-3.2.1.dmg"]],
            ["xcrun", ["stapler", "validate", "HL7-3.2.1.dmg"]],
        ])
        submits = [args for name, args in calls if name == "xcrun" and args[0] == "notarytool"]
        self.assertEqual(len(submits), 2)
        for args in submits:
            self.assertIn("--wait", args)
            self.assertEqual(args[-2:], ["--output-format", "json"])
        self.assertNotEqual(self.run_step("package, notarize & staple", FAIL_TOOL="xcrun").returncode, 0)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell required for Windows step proofs")
    def test_windows_cleanup_removes_stale_output_before_build(self):
        for name in ("test/Plugins/HL7.bundle/Contents/Windows64/HL7.4DX",
                     "test/Plugins/Default/stale", "Objs/Release/stale.obj"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"stale")
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-Command", step("clean stale outputs")],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "test/Plugins/HL7.bundle").exists())
        self.assertFalse((self.root / "Objs").exists())

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell required for Windows step proofs")
    def test_windows_exact_output_rejects_missing_empty_and_decoy(self):
        script = step("verify exact Windows output")
        path = self.root / "test/Plugins/HL7.bundle/Contents/Windows64/HL7.4DX"
        decoy = self.root / "old/Plugins/HL7.4DX"
        decoy.parent.mkdir(parents=True)
        decoy.write_bytes(b"stale")
        for value in (None, b"", b"fresh"):
            if value is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
                cwd=self.root, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode == 0, value == b"fresh", result.stderr)


if __name__ == "__main__":
    unittest.main()
