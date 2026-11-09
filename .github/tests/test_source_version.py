import importlib.util
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("source_version", ROOT / ".github/scripts/source_version.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".source-tests-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.copy_source()
        self.current = source.read(self.root)
        parts = list(map(int, self.current.split(".")))
        parts[2] += 1
        self.drift = ".".join(map(str, parts))

    def copy_source(self):
        for path in source.SOURCE_PATHS:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, target)

    def plist(self, **values):
        path = self.root / source.PLIST
        data = plistlib.loads(path.read_bytes())
        data.update(values)
        path.write_bytes(plistlib.dumps(data))

    def snapshot(self):
        return {path: (self.root / path).read_bytes() for path in source.SOURCE_PATHS}

    def assert_rejected(self):
        before = self.snapshot()
        modes = {path: stat.S_IMODE((self.root / path).stat().st_mode)
                 for path in source.SOURCE_PATHS}
        for operation in (source.read, lambda root: source.bump("patch", root)):
            with self.assertRaises(ValueError):
                operation(self.root)
            self.assertEqual(before, self.snapshot())
            self.assertEqual(modes, {
                path: stat.S_IMODE((self.root / path).stat().st_mode)
                for path in source.SOURCE_PATHS
            })

    def test_live_metadata_and_all_bump_modes(self):
        parts = list(map(int, self.current.split(".")))
        self.assertEqual(source.SETTING_COUNT, 6)
        for mode, expected in (
            ("patch", [parts[0], parts[1], parts[2] + 1]),
            ("minor", [parts[0], parts[1] + 1, 0]),
            ("major", [parts[0] + 1, 0, 0]),
        ):
            with self.subTest(mode=mode):
                self.copy_source()
                expected = ".".join(map(str, expected))
                self.assertEqual(source.bump(mode, self.root), expected)
                self.assertEqual(source.read(self.root), expected)
                self.assertNotIn("CFBundleVersion",
                                 plistlib.loads((self.root / source.PLIST).read_bytes()))
                for key in source.KEYS:
                    self.assertEqual(source.text(self.root / source.PROJECT).count(
                        f"{key} = {expected};"), source.SETTING_COUNT)

    def test_stable_fixture_coordinated_contract(self):
        project = self.root / source.PROJECT
        project.write_text(
            ("MARKETING_VERSION = 3.2.1;\nCURRENT_PROJECT_VERSION = 3.2.1;\n") * source.SETTING_COUNT
        )
        self.plist(CFBundleShortVersionString="3.2.1", CFBundleVersion="3.2.1")
        (self.root / source.LOCALIZED).write_text(
            'CFBundleName = "HL7";\nCFBundleShortVersionString = "3.2.1";\n'
            'CFBundleGetInfoString = "HL7 version 3.2.1, Copyright 2022 miyako.";\n',
            encoding="utf-8-sig",
        )
        self.assertEqual(source.read(self.root), "3.2.1")
        self.assertEqual(source.bump("minor", self.root), "3.3.0")
        self.assertEqual(project.read_text().count("CURRENT_PROJECT_VERSION = 3.3.0;"),
                         source.SETTING_COUNT)
        self.assertEqual(plistlib.loads((self.root / source.PLIST).read_bytes())["CFBundleVersion"],
                         "3.3.0")
        self.plist(CFBundleShortVersionString="$(CURRENT_PROJECT_VERSION)")
        self.assertEqual(source.read(self.root), "3.3.0")

    def test_invalid_missing_extra_and_drifted_settings(self):
        path = self.root / source.PROJECT
        original = source.text(path)
        for key in source.KEYS:
            for bad in ("1.2", "14.3", "77", "v1.2.3", "01.2.3", "1.2.3-beta",
                        "$(UNKNOWN)", "", self.drift,
                        "$(CURRENT_PROJECT_VERSION)", "${CURRENT_PROJECT_VERSION}"):
                for count in (1, source.SETTING_COUNT):
                    with self.subTest(key=key, bad=bad, count=count):
                        path.write_text(original.replace(
                            f"{key} = {self.current};", f"{key} = {bad};", count))
                        self.assert_rejected()
            path.write_text(original.replace(f"{key} = {self.current};", "", 1))
            self.assert_rejected()
            path.write_text(original + f"\n{key} = {self.current};\n")
            self.assert_rejected()
            for malformed in (f"{key} = {self.current}", f"{key} nonsense"):
                path.write_text(original + "\n" + malformed + "\n")
                self.assert_rejected()
        for reference in source.REFERENCES:
            path.write_text(original.replace(
                f"MARKETING_VERSION = {self.current};", f'MARKETING_VERSION = "{reference}";'))
            self.assert_rejected()

    def test_quoted_and_unquoted_duplicate_project_keys_rejected(self):
        path = self.root / source.PROJECT
        original = path.read_bytes()
        for key in source.KEYS:
            for quoted in (False, True):
                for version in (self.current, self.drift):
                    with self.subTest(key=key, quoted=quoted, version=version):
                        name = f'"{key}"' if quoted else key
                        path.write_bytes(original + f"\n{name} \t= {version};\n".encode())
                        self.assert_rejected()

    def test_plist_invalid_missing_and_drift(self):
        for key in ("CFBundleShortVersionString", "CFBundleVersion"):
            for value in ("$(UNKNOWN)", "$(PRODUCT_NAME)", "", "invalid", 123,
                          self.drift, "1.2", "14.3", "7", "01.2.3", "v1.2.3"):
                with self.subTest(key=key, value=value):
                    self.copy_source()
                    self.plist(**{key: value})
                    self.assert_rejected()
        self.copy_source()
        path = self.root / source.PLIST
        data = plistlib.loads(path.read_bytes())
        del data["CFBundleShortVersionString"]
        path.write_bytes(plistlib.dumps(data))
        self.assert_rejected()
        path.write_bytes(plistlib.dumps([]))
        self.assert_rejected()

    def test_supported_references_preserved_and_literals_co_bumped(self):
        for reference in source.REFERENCES:
            for marketing_ref in ("$(MARKETING_VERSION)", "${MARKETING_VERSION}"):
                with self.subTest(reference=reference, marketing_ref=marketing_ref):
                    self.copy_source()
                    self.plist(CFBundleShortVersionString=reference, CFBundleVersion=reference)
                    path = self.root / source.PROJECT
                    path.write_text(source.SETTING.sub(
                        lambda m: f'{m[1]}"{marketing_ref}"{m[4]}'
                        if m[2] == "CURRENT_PROJECT_VERSION" else m[0], source.text(path)))
                    before = self.snapshot()
                    new = source.bump("patch", self.root)
                    self.assertEqual(source.read(self.root), new)
                    for name, original in before.items():
                        self.assertEqual((self.root / name).read_bytes(),
                                         original.replace(self.current.encode(), new.encode()))
        self.copy_source()
        self.plist(CFBundleVersion=self.current)
        new = source.bump("minor", self.root)
        self.assertEqual(plistlib.loads((self.root / source.PLIST).read_bytes())["CFBundleVersion"],
                         new)

    def test_duplicate_plist_keys_and_invalid_serialization_fail_closed(self):
        path = self.root / source.PLIST
        original = source.text(path)
        for key in ("CFBundleShortVersionString", "CFBundleVersion"):
            for value in (self.current, self.drift):
                with self.subTest(key=key, value=value):
                    self.copy_source()
                    if key == "CFBundleVersion":
                        self.plist(CFBundleVersion=self.current)
                    data = source.text(path)
                    path.write_text(data.replace(
                        "</dict>", f"<key>{key}</key><string>{value}</string>\n</dict>"))
                    self.assert_rejected()
        for malformed in (
            b"not a plist", original.replace("</dict>", "").encode(),
            original.replace("<string>" + self.current,
                             "<string>&#" + str(ord(self.current[0])) + ";" + self.current[1:]).encode(),
            plistlib.dumps(plistlib.loads(original.encode()), fmt=plistlib.FMT_BINARY),
        ):
            with self.subTest(serialization=malformed[:40]):
                self.copy_source()
                path.write_bytes(malformed)
                self.assert_rejected()

    def test_localized_validation(self):
        path = self.root / source.LOCALIZED
        original = source.text(path)
        for pattern in (source.LOCALIZED_SHORT, source.LOCALIZED_INFO):
            for bad in ("1.0", self.drift, "invalid", "", "$(UNKNOWN)", "$(MARKETING_VERSION)",
                        "${CURRENT_PROJECT_VERSION}", "01.2.3", "1.2.3-beta"):
                with self.subTest(pattern=pattern.pattern, bad=bad):
                    path.write_text(pattern.sub(lambda m: f"{m[1]}{bad}{m[3]}", original))
                    self.assert_rejected()
            path.write_text(pattern.sub("", original))
            self.assert_rejected()
        for key in ("CFBundleShortVersionString", "CFBundleGetInfoString"):
            path.write_text(original.replace(key, "UnknownKey"))
            self.assert_rejected()
            path.write_text(original + f'\n{key} = "{self.current}";\n')
            self.assert_rejected()
        for bad in ("Other Product", "Copyright 2016", "Copyright 2022 someone"):
            path.write_text(original.replace(
                "HL7" if bad == "Other Product" else
                "Copyright 2022" if bad == "Copyright 2016" else "Copyright 2022 miyako", bad))
            self.assert_rejected()

    def test_missing_source_files_rejected_without_writes(self):
        for name in source.SOURCE_PATHS:
            self.copy_source()
            (self.root / name).unlink()
            before = {p: ((self.root / p).read_bytes(), (self.root / p).stat().st_mode)
                      for p in source.SOURCE_PATHS if p != name}
            for operation in (source.read, lambda root: source.bump("patch", root)):
                with self.assertRaises(FileNotFoundError):
                    operation(self.root)
                self.assertEqual(before, {
                    p: ((self.root / p).read_bytes(), (self.root / p).stat().st_mode)
                    for p in before
                })
                self.assertFalse((self.root / name).exists())

    def test_localized_quoted_duplicate_keys_rejected_without_writes(self):
        path = self.root / source.LOCALIZED
        original = path.read_bytes()
        for key in ("CFBundleShortVersionString", "CFBundleGetInfoString"):
            for version in (self.current, self.drift):
                with self.subTest(key=key, version=version):
                    value = version if key == "CFBundleShortVersionString" else (
                        f"HL7 version {version}, Copyright 2022 miyako."
                    )
                    path.write_bytes(original + f'\n"{key}" \t= "{value}";\n'.encode())
                    self.assert_rejected()

    def test_byte_preserving_endings_bom_and_modes(self):
        for newline in ("\n", "\r", "\r\n", "mixed"):
            for bom in (b"", b"\xef\xbb\xbf"):
                with self.subTest(newline=newline, bom=bom):
                    self.copy_source()
                    originals = {}
                    for i, name in enumerate(source.SOURCE_PATHS):
                        path = self.root / name
                        lines = source.text(path).splitlines(keepends=True)
                        value = "".join(line.replace(
                            "\n", ("\r", "\r\n", "\n")[j % 3] if newline == "mixed" else newline
                        ) for j, line in enumerate(lines))
                        path.write_bytes(bom + value.encode())
                        path.chmod((0o755, 0o640, 0o644)[i])
                        originals[name] = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
                    new = source.bump("minor", self.root)
                    for name, (before, mode) in originals.items():
                        path = self.root / name
                        self.assertEqual(path.read_bytes(), before.replace(
                            self.current.encode(), new.encode()))
                        self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)

    def test_whitespace_and_quotes_preserved(self):
        for quoted in (False, True):
            self.copy_source()
            path = self.root / source.PROJECT
            old = self.current.encode()
            value = b'"' + old + b'"' if quoted else old
            before = path.read_bytes()
            for key in source.KEYS:
                before = before.replace(key.encode() + b" = " + old + b";",
                                        key.encode() + b" \t= \t" + value + b" \t;")
            path.write_bytes(before)
            localized = self.root / source.LOCALIZED
            localized.write_bytes(localized.read_bytes().replace(b" = ", b" \t= \t")
                                  .replace(b'";', b'" \t; \t'))
            snapshots = self.snapshot()
            new = source.bump("patch", self.root)
            for name, original in snapshots.items():
                self.assertEqual((self.root / name).read_bytes(), original.replace(old, new.encode()))

    def test_prebuilt_4d_schema_and_dependency_files_ignored(self):
        excluded = (
            "test/Plugins/HL7.bundle/Contents/Info.plist",
            "test/Plugins/HL7.bundle/Contents/Resources/English.lproj/InfoPlist.strings",
            "test/Plugins/HL7.bundle/Contents/manifest.json",
            "test/Plugins/HL7.bundle/Contents/Resources/manifest.json",
            "test/Plugins/HL7.bundle/Contents/Resources/constants.xlf",
            "test/Plugins/HL7.bundle/Contents/MacOS/HL7",
            "test/Plugins/HL7.bundle/Contents/Windows64/HL7.4DX",
            "test/Plugins/HL7.bundle/Contents/QuickLook/Thumbnail.png",
            "test/Data/data.4DD", "test/Data/data.journal", "test/Data/data.Match",
            "test/Project/test.4DProject", "test/Project/Sources/catalog.4DCatalog",
            "test/Project/Sources/settings.4DSettings",
            "manifest.json", "constants.json", "constants.xlf",
            "4D Plugin API/4DPluginAPI.h", "4D Plugin API/Classes/C_TYPES.h",
            "HL7.vcxproj", "HL7.vcxproj.filters", "HL7.sln",
            "4DPlugin-HL7.cpp", "4DPlugin-HL7.h", "support/4DPlugin-JSON.cpp",
            "hl7parser/parser.c", "include/hl7parser/parser.h",
            "include/json/version.h", "a/libjsoncpp.a", "lib/windows64/jsoncpp.lib",
        )
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            check=True, capture_output=True, text=True,
        ).stdout.rstrip("\0").split("\0")
        self.assertTrue(set(excluded).issubset(tracked))
        for name in excluded:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, path)
        before = {name: ((self.root / name).read_bytes(), (self.root / name).stat().st_mode)
                  for name in excluded}
        source.bump("major", self.root)
        self.assertEqual(before, {
            name: ((self.root / name).read_bytes(), (self.root / name).stat().st_mode)
            for name in excluded
        })

    def test_invalid_mode_and_cli_read_do_not_write(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            source.bump("other", self.root)
        output = subprocess.run(
            [sys.executable, str(ROOT / ".github/scripts/source_version.py")],
            cwd=self.root, check=True, capture_output=True, text=True,
        )
        self.assertEqual(output.stdout.strip(), self.current)
        self.assertEqual(before, self.snapshot())

    def test_original_authority_repair_preserves_all_other_bytes_and_modes(self):
        baseline = "38533629c48e67fe4b3d1ce48c4cea7f44597ee3"
        version = self.current.encode()
        for name in source.SOURCE_PATHS:
            original = subprocess.run(
                ["git", "show", f"{baseline}:{name}"], cwd=ROOT,
                check=True, capture_output=True,
            ).stdout
            if name == source.PROJECT:
                self.assertEqual(original.count(b"MARKETING_VERSION = 1.0.5;"), 6)
                self.assertEqual(original.count(b"CURRENT_PROJECT_VERSION = 1.0.3;"), 6)
                expected = original.replace(b"CURRENT_PROJECT_VERSION = 1.0.3;",
                                            b"CURRENT_PROJECT_VERSION = " + version + b";")
                expected = expected.replace(b"MARKETING_VERSION = 1.0.5;",
                                            b"MARKETING_VERSION = " + version + b";")
            elif name == source.LOCALIZED:
                self.assertEqual(original.count(b'"1.0.0"'), 1)
                self.assertEqual(original.count(b"HL7 version 1.0.0,"), 1)
                expected = original.replace(b'"1.0.0"', b'"' + version + b'"')
                expected = expected.replace(b"HL7 version 1.0.0,",
                                            b"HL7 version " + version + b",")
            else:
                self.assertEqual(original.count(b"<string>1.0.5</string>"), 1)
                expected = original.replace(b"<string>1.0.5</string>",
                                            b"<string>" + version + b"</string>")
                if self.current == "1.0.5":
                    self.assertEqual(expected, original)
            self.assertEqual((ROOT / name).read_bytes(), expected)
            mode = subprocess.run(
                ["git", "ls-tree", baseline, "--", str(name)], cwd=ROOT,
                check=True, capture_output=True, text=True,
            ).stdout.split()[0]
            self.assertEqual(stat.S_IMODE((ROOT / name).stat().st_mode), int(mode, 8) & 0o777)


if __name__ == "__main__":
    unittest.main()
