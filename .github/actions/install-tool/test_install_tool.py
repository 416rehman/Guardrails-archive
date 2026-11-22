# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: The Guardrails ADR Authors
"""Tests for install_tool.py and minisign.py: python3 -I .github/actions/install-tool/test_install_tool.py [-k <name>]

Signature: the golden buf release files in supply-chain/fixtures/install-tool/buf-<version>/, made by
minisign with Buf's release key, and seeded mutations of them; a case that needs a valid signature over
other content uses a key the test makes with OpenSSL. Installer: seeded pins built from the real
supply-chain/build-tools.toml and served by a local fake opener. InstallerRealArchive: the pinned
archives, fetched over https through the installer's own checks, read against the system tar.
ProxyName: every name in [install]. NoBuildFetch: the tracked tree (git ls-files) and the seeded
copies in supply-chain/fixtures/install-tool/no-build-fetch.toml. CheckRelease: a fake gh runner.
"""

import ast
import base64
import contextlib
import dataclasses
import email.message
import fnmatch
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest
import unittest.mock
import urllib.request
import urllib.response

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import install_tool
import minisign

ROOT = HERE.parents[2]
PINS = ROOT / "supply-chain" / "build-tools.toml"
FIXTURES = ROOT / "supply-chain" / "fixtures" / "install-tool"
REAL = tomllib.loads(PINS.read_text(encoding="utf-8"))
INSTALL = REAL["install"]
BUF = REAL["tool"]["buf"]
PLUGIN = REAL["tool"]["protoc-gen-connect-openapi"]
GOLDEN = FIXTURES / f"buf-{BUF['version']}"
SEEDS = tomllib.loads((FIXTURES / "no-build-fetch.toml").read_text(encoding="utf-8"))
OPENSSL = ["openssl"]
HOST = "linux-x86_64"
SEEDED_TOOL = "seeded"
SEEDED_ASSET = "seeded-asset"
SEEDED_ARCHIVE = "seeded-asset.tar.gz"
SEEDED_MEMBER = "seeded"
SEEDED_VERSION = "v1.2.3"
SEEDED_CHECKSUMS = "checksums.txt"
TEST_KEY_ID = bytes(range(1, 9))
TEST_TRUSTED = b"timestamp:1\tfilename:checksums.txt"

FETCHES = [re.compile(pattern, re.I) for pattern in (
    r"releases/download", r"buf\.build", r"bufbuild/buf-action", r"bufbuild/buf-setup-action",
    r"buf\s+registry\s+login", r"\bgo\s+(?:install|run)\b[^\n]*(?:bufbuild/buf|protoc-gen-connect-openapi)",
)]
BUF_CONFIG_FETCHES = [re.compile(r"^\s*(?:-\s*)?remote\s*:", re.M), re.compile(r"^\s*deps\s*:", re.M)]
SCANNED_NAMES = ("build.rs", "Cargo.toml", "package.json", "pnpm-workspace.yaml")


@dataclasses.dataclass
class Case:
    table: dict
    files: dict
    install: dict | None = dataclasses.field(default_factory=lambda: dict(INSTALL))
    responses: dict = dataclasses.field(default_factory=dict)
    tool: str = SEEDED_TOOL


@dataclasses.dataclass
class Outcome:
    code: int
    stdout: str
    stderr: str
    left: list
    requests: list


@dataclasses.dataclass(frozen=True)
class TestKey:
    secret: pathlib.Path
    public: bytes

    def text(self, key_id=TEST_KEY_ID):
        return base64.b64encode(b"Ed" + key_id + self.public).decode("ascii")

    def sign(self, message):
        folder = self.secret.parent
        (folder / "message").write_bytes(message)
        run_openssl("pkeyutl", "-sign", "-rawin", "-inkey", self.secret, "-in", folder / "message",
                    "-out", folder / "signature")
        return (folder / "signature").read_bytes()

    def signature_file(self, data, trusted=TEST_TRUSTED):
        signature = self.sign(hashlib.blake2b(data, digest_size=64).digest())
        global_signature = self.sign(signature + trusted)
        return b"\n".join([
            b"untrusted comment: test key", base64.b64encode(b"ED" + TEST_KEY_ID + signature),
            b"trusted comment: " + trusted, base64.b64encode(global_signature),
        ]) + b"\n"


class FakeRelease(urllib.request.HTTPSHandler):
    # Ahead of urllib's own handlers, so a plain http hop is served here too and only the
    # installer's redirect check can refuse it.
    handler_order = urllib.request.HTTPSHandler.handler_order - 1

    def __init__(self, responses):
        super().__init__()
        self.responses = responses
        self.requests = []

    def http_open(self, req):
        return self.https_open(req)

    def https_open(self, req):
        self.requests.append(req.full_url)
        status, headers, body = self.responses.get(req.full_url, (404, {}, b""))
        message = email.message.Message()
        for name, value in headers.items():
            message[name] = value
        response = urllib.response.addinfourl(io.BytesIO(body), message, req.full_url, status)
        response.msg = "fake"
        return response


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def run_openssl(*arguments):
    return subprocess.run([*OPENSSL, *map(str, arguments)], capture_output=True, check=True).stdout


def make_test_key(folder):
    secret = folder / "secret.pem"
    run_openssl("genpkey", "-algorithm", "ed25519", "-out", secret)
    der = run_openssl("pkey", "-in", secret, "-pubout", "-outform", "DER")
    return TestKey(secret, der[-32:])


def toml_value(value):
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{key} = {toml_value(item)}" for key, item in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(map(toml_value, value)) + "]"
    return json.dumps(value)


def pins_text(case):
    lines = [] if case.install is None else ["[install]", *(f"{k} = {toml_value(v)}" for k, v in case.install.items())]
    lines += [f"[tool.{case.tool}]", *(f"{k} = {toml_value(v)}" for k, v in case.table.items())]
    return "\n".join(lines) + "\n"


def url(table, name):
    return install_tool.DOWNLOAD.format(source=table["source"], version=table["version"], name=name)


def print_own_bytes(command, timeout):
    return subprocess.CompletedProcess(command, 0, pathlib.Path(command[0]).read_bytes(), b"")


def tar_gz(*members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, kind, data in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(data)
            info.linkname = "" if kind == tarfile.REGTYPE else "elsewhere"
            archive.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
    return buffer.getvalue()


def seeded_case(binary=SEEDED_MEMBER, body=b"seeded 1.2.3\n", archive=None):
    asset_name = SEEDED_ASSET if archive is None else SEEDED_ARCHIVE
    asset = body if archive is None else archive
    checksums = f"{'0' * 64}  other-asset\n{sha256(asset)}  {asset_name}\n".encode("ascii")
    row = {"file": asset_name, "size": len(asset), "sha256": sha256(asset), "binary": binary}
    if archive is not None:
        row |= {"member": SEEDED_MEMBER, "member_size": len(body)}
    table = {
        "version": SEEDED_VERSION, "licence": "MIT", "source": "https://github.com/example/seeded",
        "version_flag": "--version", "checksums": SEEDED_CHECKSUMS, "checksums_size": len(checksums),
        "checksums_sha256": sha256(checksums), "assets": {HOST: row},
    }
    return Case(table, {SEEDED_CHECKSUMS: checksums, asset_name: asset})


def signed(case, key, signature=None):
    data = signature or key.signature_file(case.files[SEEDED_CHECKSUMS])
    case.table |= {"signature": "checksums.txt.minisig", "signature_size": len(data), "minisign_key": key.text()}
    case.files["checksums.txt.minisig"] = data
    return case


def archived(body=b"seeded 1.2.3\n", members=None):
    return seeded_case(body=body, archive=tar_gz(*(members or [(SEEDED_MEMBER, tarfile.REGTYPE, body)])))


def run_case(case, folder, host=HOST, run=print_own_bytes):
    pins = folder / "pins.toml"
    pins.write_text(pins_text(case), encoding="utf-8")
    responses = {url(case.table, name): (200, {}, data) for name, data in case.files.items()} | case.responses
    fake = FakeRelease(responses)
    runtime = install_tool.Runtime(pins, host, install_tool.opener(fake), run, OPENSSL)
    dest = folder / "bin"
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = install_tool.main(["install_tool.py", case.tool, "--dest", str(dest)], runtime)
    left = sorted(os.listdir(dest)) if dest.exists() else []
    return Outcome(code, stdout.getvalue(), stderr.getvalue(), left, fake.requests)


def flip(data, at):
    return data[:at] + bytes([data[at] ^ 1]) + data[at + 1:]


def with_line(data, number, line):
    lines = data.split(b"\n")
    lines[number] = line
    return b"\n".join(lines)


def reencoded(data, number, change):
    raw = base64.b64decode(data.split(b"\n")[number])
    return with_line(data, number, base64.b64encode(change(raw)))


def scanned(path):
    parts = path.split("/")
    if path.startswith(".github/actions/install-tool/"):
        return False
    return (
        (len(parts) == 3 and path.startswith(".github/workflows/") and path.endswith(".yml"))
        or path.startswith((".github/actions/", ".cargo/"))
        or parts[-1] in SCANNED_NAMES
        or fnmatch.fnmatchcase(parts[-1], "buf*.yaml")
    )


def build_fetch_problems(root, paths):
    problems = []
    for path in filter(scanned, paths):
        content = (root / path).read_bytes().decode("utf-8", "replace")
        patterns = FETCHES + (BUF_CONFIG_FETCHES if fnmatch.fnmatchcase(path.split("/")[-1], "buf*.yaml") else [])
        problems += [f"{path}: {pattern.pattern}" for pattern in patterns if pattern.search(content)]
    return problems


def mixed_case(name):
    return "".join(letter.upper() if at % 2 else letter for at, letter in enumerate(name))


def non_canonical(line):
    alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    last = alphabet.index(line[-3])
    return line[:-3] + alphabet[last ^ 1:(last ^ 1) + 1] + line[-2:]


def reports_pinned_version(command, timeout):
    return subprocess.CompletedProcess(command, 0, f"seeded {PLUGIN['version']}\n".encode("ascii"), b"")


def make_link(link, target):
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))


def real_archive_case(key):
    def test(self):
        self.check_row(key)
    return test


def release_listing(table):
    listed = [{"name": table["checksums"], "size": table["checksums_size"], "digest": f"sha256:{table['checksums_sha256']}"}]
    listed += [{"name": row["file"], "size": row["size"], "digest": f"sha256:{row['sha256']}"}
               for row in table["assets"].values()]
    if "signature" in table:
        listed.append({"name": table["signature"], "size": table["signature_size"], "digest": "sha256:" + "0" * 64})
    return listed


def changed_entry(name, key, change):
    return lambda listed: [dict(entry, **{key: change(entry[key])}) if entry["name"] == name else entry for entry in listed]


def gh_printing(listed):
    stdout = json.dumps({"assets": listed}).encode("utf-8")
    return lambda command, timeout: subprocess.CompletedProcess(command, 0, stdout, b"")


class Offline(unittest.TestCase):
    def setUp(self):
        refuse = unittest.mock.patch.object(socket.socket, "connect", side_effect=AssertionError("a test opened a connection"))
        refuse.start()
        self.addCleanup(refuse.stop)


class Folder(Offline):
    def setUp(self):
        super().setUp()
        self.folder = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, True)

    def run_in(self, case, **options):
        folder = pathlib.Path(tempfile.mkdtemp(dir=self.folder))
        return folder, run_case(case, folder, **options)

    def assert_refused(self, case, code, **options):
        _, outcome = self.run_in(case, **options)
        self.assertEqual(outcome.code, 1, outcome.stderr)
        self.assertTrue(outcome.stderr.startswith(f"::error::{code} "), outcome.stderr)
        self.assertEqual(outcome.left, [], outcome.stderr)
        self.assertEqual(outcome.stdout, "")
        return outcome

    def assert_installs(self, case, **options):
        folder, outcome = self.run_in(case, **options)
        self.assertEqual(outcome.code, 0, outcome.stderr)
        binary = case.table["assets"][options.get("host", HOST)]["binary"]
        self.assertEqual(outcome.left, [binary])
        self.assertTrue(outcome.stdout.startswith(f"installed {case.tool} {case.table['version']} "), outcome.stdout)
        return folder / "bin" / binary


class SignatureTest(Folder):
    def setUp(self):
        super().setUp()
        self.pin = install_tool.validate("buf", BUF, INSTALL)
        self.data = (GOLDEN / BUF["checksums"]).read_bytes()
        self.signature = (GOLDEN / BUF["signature"]).read_bytes()

    def check(self, data, signature, pin=None):
        install_tool.check_signature(pin or self.pin, data, signature, OPENSSL)

    def assert_signature_refused(self, data, signature, pin=None, openssl=OPENSSL):
        with self.assertRaises(install_tool.Refusal) as refused:
            install_tool.check_signature(pin or self.pin, data, signature, openssl)
        self.assertEqual(refused.exception.code, "GRDR-SUPPLY-0008")
        return refused.exception.reason

    def test_golden_files_verify_with_the_pinned_key(self):
        self.check(self.data, self.signature)

    def test_golden_files_follow_the_pin(self):
        self.assertEqual((sha256(self.data), len(self.data)), (BUF["checksums_sha256"], BUF["checksums_size"]))
        self.assertEqual(len(self.signature), BUF["signature_size"])
        for platform_key, row in BUF["assets"].items():
            with self.subTest(platform=platform_key):
                self.assertEqual(install_tool.listed_digest(self.data, row["file"], "-"), row["sha256"])

    def test_seeded_signatures_are_refused(self):
        key = minisign.read_public_key(BUF["minisign_key"])
        other_key = base64.b64encode(b"Ed" + key.key_id + flip(key.key, 0)).decode("ascii")
        cases = {
            "flipped byte in the checksum file": (flip(self.data, 0), self.signature, None),
            "flipped byte in the signature": (self.data, reencoded(self.signature, 1, lambda raw: flip(raw, 20)), None),
            "flipped byte in the trusted comment": (self.data, flip(self.signature, self.signature.index(b"timestamp:") + 10), None),
            "flipped byte in the global signature": (self.data, reencoded(self.signature, 3, lambda raw: flip(raw, 5)), None),
            "legacy Ed algorithm": (self.data, reencoded(self.signature, 1, lambda raw: b"Ed" + raw[2:]), None),
            "another key id": (self.data, reencoded(self.signature, 1, lambda raw: raw[:2] + flip(raw, 2)[2:10] + raw[10:]), None),
            "same key id with other key bytes": (self.data, self.signature, dataclasses.replace(
                self.pin, minisign=dataclasses.replace(self.pin.minisign, key=other_key))),
            "a fifth line": (self.data, self.signature + b"untrusted comment: more\n", None),
            "non-canonical base64": (self.data, with_line(self.signature, 3, non_canonical(self.signature.split(b"\n")[3])), None),
        }
        for name, (data, signature, pin) in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual((data, signature, pin), (self.data, self.signature, None))
                self.assert_signature_refused(data, signature, pin)

    def test_a_valid_signature_naming_another_file_is_refused(self):
        key = make_test_key(self.folder)
        pin = dataclasses.replace(self.pin, minisign=dataclasses.replace(self.pin.minisign, key=key.text()))
        named = TEST_TRUSTED.replace(b"checksums.txt", BUF["checksums"].encode("ascii"))
        self.check(self.data, key.signature_file(self.data, named), pin)
        other = key.signature_file(self.data, named.replace(BUF["checksums"].encode("ascii"), b"other.txt"))
        self.assertIn("does not name", self.assert_signature_refused(self.data, other, pin))

    def test_an_openssl_older_than_3_is_refused(self):
        fake = [sys.executable, "-I", "-c", "print('LibreSSL 3.3.6')"]
        self.assertIn("OpenSSL 3", self.assert_signature_refused(self.data, self.signature, openssl=fake))


class InstallerTest(Folder):
    def test_controls_install(self):
        self.assert_installs(seeded_case())
        self.assert_installs(archived())
        self.assert_installs(signed(seeded_case(), make_test_key(self.folder)))
        redirected = seeded_case()
        target = url(redirected.table, SEEDED_ASSET)
        redirected.responses = {target: (302, {"Location": target + "-moved"}, b""),
                                target + "-moved": (200, {}, redirected.files[SEEDED_ASSET])}
        self.assert_installs(redirected)

    def test_only_verify_builds_a_verified_value(self):
        tree = ast.parse((HERE / "install_tool.py").read_text(encoding="utf-8"))
        builders = [function.name for function in ast.walk(tree) if isinstance(function, ast.FunctionDef)
                    for call in ast.walk(function) if isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name) and call.func.id == "Verified"]
        self.assertEqual(builders, ["verify"])

    def test_malformed_or_missing_pins_are_refused_before_any_request(self):
        def changed(key, value=None, row_key=None):
            case = seeded_case()
            target = case.table if row_key is None else case.table["assets"][HOST]
            if value is None:
                del target[key if row_key is None else row_key]
            else:
                target[key if row_key is None else row_key] = value
            return case
        cases = {
            "missing checksums_sha256": (changed("checksums_sha256"), "GRDR-SUPPLY-0003"),
            "missing row sha256": (changed(None, row_key="sha256"), "GRDR-SUPPLY-0003"),
            "malformed digest": (changed("checksums_sha256", "AB" * 32), "GRDR-SUPPLY-0002"),
            "source on another host": (changed("source", "https://example.com/example/seeded"), "GRDR-SUPPLY-0002"),
            "source over http": (changed("source", "http://github.com/example/seeded"), "GRDR-SUPPLY-0002"),
            "source with a path": (changed("source", "https://github.com/example/seeded/x"), "GRDR-SUPPLY-0002"),
            "file name with a folder": (changed(None, "x/seeded-asset", "file"), "GRDR-SUPPLY-0002"),
            "file name with ..": (changed(None, "..seeded-asset", "file"), "GRDR-SUPPLY-0002"),
            "size that is not positive": (changed(None, 0, "size"), "GRDR-SUPPLY-0002"),
            "unknown row key": (changed(None, "x", "membr"), "GRDR-SUPPLY-0002"),
        }
        for name, (case, code) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.assert_refused(case, code).requests, [])

    def test_an_unpinned_platform_is_refused(self):
        outcome = self.assert_refused(seeded_case(), "GRDR-SUPPLY-0005", host="plan9-mips")
        self.assertIn(HOST, outcome.stderr)

    def test_fetch_failures_are_refused(self):
        plain_hop = "http://example.com/seeded-asset"

        def served(change):
            case = seeded_case()
            body = case.files[SEEDED_ASSET]
            case.responses = {url(case.table, SEEDED_ASSET): change(body), plain_hop: (200, {}, body)}
            return case
        cases = {
            "http redirect hop": served(lambda body: (302, {"Location": plain_hop}, b"")),
            "oversize body": served(lambda body: (200, {}, body + b"x")),
            "undersize body": served(lambda body: (200, {}, body[:-1])),
            "status 404": served(lambda body: (404, {}, body)),
            "status 203": served(lambda body: (203, {}, body)),
        }
        for name, case in cases.items():
            with self.subTest(case=name):
                self.assert_refused(case, "GRDR-SUPPLY-0006")

    def test_digest_and_checksum_line_failures_are_refused(self):
        def checksums(lines):
            case = seeded_case()
            data = "".join(f"{line}\n" for line in lines).encode("ascii")
            case.files[SEEDED_CHECKSUMS] = data
            case.table |= {"checksums_size": len(data), "checksums_sha256": sha256(data)}
            return case
        pinned = seeded_case().table["assets"][HOST]["sha256"]
        tampered = seeded_case()
        tampered.files[SEEDED_CHECKSUMS] = flip(tampered.files[SEEDED_CHECKSUMS], 0)
        swapped = seeded_case()
        swapped.files[SEEDED_ASSET] = flip(swapped.files[SEEDED_ASSET], 0)
        cases = {
            "checksum file digest": tampered,
            "missing checksum line": checksums([f"{pinned}  other-asset"]),
            "duplicated checksum line": checksums([f"{pinned}  {SEEDED_ASSET}", f"{pinned} *{SEEDED_ASSET}"]),
            "different checksum line": checksums([f"{'1' * 64}  {SEEDED_ASSET}"]),
            "asset digest": swapped,
        }
        for name, case in cases.items():
            with self.subTest(case=name):
                self.assert_refused(case, "GRDR-SUPPLY-0007")

    def test_archive_failures_are_refused(self):
        body = b"seeded 1.2.3\n"
        regular = (SEEDED_MEMBER, tarfile.REGTYPE, body)
        cases = {
            "member missing": archived(members=[("other", tarfile.REGTYPE, body)]),
            "member duplicated": archived(members=[regular, regular]),
            "symlink member": archived(members=[(SEEDED_MEMBER, tarfile.SYMTYPE, body)]),
            "hardlink member": archived(members=[(SEEDED_MEMBER, tarfile.LNKTYPE, body)]),
            "../ path": archived(members=[(f"../{SEEDED_MEMBER}", tarfile.REGTYPE, body)]),
            "absolute path": archived(members=[(f"/{SEEDED_MEMBER}", tarfile.REGTYPE, body)]),
            "wrong size": archived(members=[(SEEDED_MEMBER, tarfile.REGTYPE, body + b"x")]),
        }
        for name, case in cases.items():
            with self.subTest(case=name):
                self.assert_refused(case, "GRDR-SUPPLY-0009")

    def test_a_link_or_folder_at_the_target_is_refused(self):
        for kind in ("link", "folder"):
            with self.subTest(kind=kind):
                folder = pathlib.Path(tempfile.mkdtemp(dir=self.folder))
                target = folder / "bin" / SEEDED_MEMBER
                target.parent.mkdir()
                elsewhere = folder / "elsewhere"
                elsewhere.mkdir()
                make_link(target, elsewhere) if kind == "link" else target.mkdir()
                outcome = run_case(seeded_case(), folder)
                self.assertEqual(outcome.code, 1, outcome.stderr)
                self.assertTrue(outcome.stderr.startswith("::error::GRDR-SUPPLY-0009 "), outcome.stderr)
                self.assertEqual(outcome.left, [SEEDED_MEMBER])
                self.assertEqual(list(elsewhere.iterdir()), [])

    def test_a_binary_that_reports_another_version_is_removed(self):
        self.assert_refused(seeded_case(body=b"seeded 1.2.30\n"), "GRDR-SUPPLY-0010")
        self.assert_refused(seeded_case(body=b"seeded 9.9.9\n"), "GRDR-SUPPLY-0010")

        def cannot_run(command, timeout):
            raise OSError("not an executable")
        self.assert_refused(seeded_case(), "GRDR-SUPPLY-0010", run=cannot_run)


class InstallerRealArchiveTest(Folder):
    @classmethod
    def setUpClass(cls):
        cls.pin = install_tool.validate("protoc-gen-connect-openapi", PLUGIN, INSTALL)
        cls.store = pathlib.Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.store, True)
        fetch = install_tool.opener()
        for row in cls.pin.rows.values():
            fetched = install_tool.fetch(cls.pin, row, fetch)
            install_tool.verify(fetched, OPENSSL)
            (cls.store / cls.pin.checksums.name).write_bytes(fetched.checksums)
            (cls.store / row.asset.name).write_bytes(fetched.asset)

    def check_row(self, key):
        row = self.pin.rows[key]
        tar = shutil.which("tar")
        self.assertIsNotNone(tar, "a system tar is the reference")
        data = (self.store / row.asset.name).read_bytes()
        printed = subprocess.run([tar, "-xOzf", row.asset.name, row.member.name], cwd=self.store,
                                 capture_output=True, check=True).stdout
        self.assertEqual(install_tool.archive_member(data, row.member, row.asset.name), printed)
        self.assertEqual(len(printed), row.member.size)
        files = {self.pin.checksums.name: (self.store / self.pin.checksums.name).read_bytes(), row.asset.name: data}
        run = install_tool.run_command if key == install_tool.host_platform() else reports_pinned_version
        installed = self.assert_installs(Case(PLUGIN, files, tool=self.pin.tool), host=key, run=run)
        self.assertEqual(installed.read_bytes(), printed)


for row_key in PLUGIN["assets"]:
    setattr(InstallerRealArchiveTest, f"test_{row_key.replace('-', '_')}", real_archive_case(row_key))


class ProxyNameTest(Folder):
    def test_every_refused_name_is_refused_before_any_request(self):
        variants = [
            spelled + suffix
            for name in INSTALL["refused_binaries"]
            for spelled in (name, name.upper(), mixed_case(name))
            for suffix in ("", ".exe", ".EXE")
        ] + [prefix + "x" for prefix in INSTALL["refused_binary_prefixes"]]
        for binary in variants:
            with self.subTest(binary=binary):
                self.assertEqual(self.assert_refused(seeded_case(binary=binary), "GRDR-SUPPLY-0002").requests, [])

    def test_install_without_either_name_list_is_refused(self):
        for key in ("refused_binaries", "refused_binary_prefixes"):
            with self.subTest(missing=key):
                case = seeded_case()
                del case.install[key]
                self.assert_refused(case, "GRDR-SUPPLY-0003")
        missing = seeded_case()
        missing.install = None
        self.assert_refused(missing, "GRDR-SUPPLY-0003")

    def test_a_name_list_entry_not_of_its_form_is_refused(self):
        first = INSTALL["refused_binaries"][0]
        for entries in ([], [first, 1], [first + "\n"], [first.upper()]):
            with self.subTest(entries=entries):
                case = seeded_case()
                case.install["refused_binaries"] = entries
                self.assert_refused(case, "GRDR-SUPPLY-0002")

    def test_the_pinned_names_pass_and_install(self):
        for binary in ("buf", "buf.exe", "protoc-gen-connect-openapi", "protoc-gen-connect-openapi.exe"):
            with self.subTest(binary=binary):
                self.assert_installs(seeded_case(binary=binary))


class NoBuildFetchTest(Offline):
    def test_the_tracked_tree_passes(self):
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        paths = [path for path in listed.decode("utf-8").split("\0") if path]
        self.assertGreater(len([path for path in paths if scanned(path)]), 0)
        self.assertEqual(build_fetch_problems(ROOT, paths), [])

    def test_each_seeded_copy_fails_naming_its_file(self):
        for group, expected in (("case", True), ("control", False)):
            for seed in SEEDS[group]:
                with self.subTest(case=seed["name"]), tempfile.TemporaryDirectory() as folder:
                    path = pathlib.Path(folder) / seed["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(seed["text"], encoding="utf-8")
                    problems = build_fetch_problems(pathlib.Path(folder), [seed["path"]])
                    self.assertEqual(bool(problems), expected, problems)
                    self.assertTrue(all(problem.startswith(f"{seed['path']}: ") for problem in problems))


class CheckReleaseTest(Offline):
    def check(self, tool, run):
        return install_tool.check_release(install_tool.validate(tool, REAL["tool"][tool], INSTALL), run)

    def test_the_matching_listing_passes(self):
        for tool in ("buf", "protoc-gen-connect-openapi"):
            with self.subTest(tool=tool):
                line = self.check(tool, gh_printing(release_listing(REAL["tool"][tool])))
                self.assertEqual(line, f"release matches {tool} {REAL['tool'][tool]['version']}")

    def test_a_seeded_listing_is_refused_naming_the_file(self):
        asset, checksums, signature = BUF["assets"][HOST]["file"], BUF["checksums"], BUF["signature"]
        other_digest = "sha256:" + "1" * 64
        cases = {
            "pinned asset missing": (asset, lambda listed: [entry for entry in listed if entry["name"] != asset]),
            "pinned asset duplicated": (asset, lambda listed: listed + [entry for entry in listed if entry["name"] == asset]),
            "asset with another size": (asset, changed_entry(asset, "size", lambda size: size + 1)),
            "asset with another digest": (asset, changed_entry(asset, "digest", lambda digest: other_digest)),
            "checksum file with another digest": (checksums, changed_entry(checksums, "digest", lambda digest: other_digest)),
            "signature with another size": (signature, changed_entry(signature, "size", lambda size: size + 1)),
        }
        for name, (file, change) in cases.items():
            with self.subTest(case=name), self.assertRaises(install_tool.Refusal) as refused:
                self.check("buf", gh_printing(change(release_listing(BUF))))
            self.assertEqual((refused.exception.code, refused.exception.file), ("GRDR-SUPPLY-0007", file))
            self.assertIn(file, refused.exception.reason)

    def test_a_failing_gh_is_refused(self):
        def missing(command, timeout):
            raise FileNotFoundError(command[0])
        cases = {
            "gh missing": missing,
            "gh exiting 1": lambda command, timeout: subprocess.CompletedProcess(command, 1, b"", b""),
            "output that is not JSON": lambda command, timeout: subprocess.CompletedProcess(command, 0, b"assets", b""),
            "JSON without assets": lambda command, timeout: subprocess.CompletedProcess(command, 0, b'{"tagName": "v1"}', b""),
        }
        for name, run in cases.items():
            with self.subTest(case=name), self.assertRaises(install_tool.Refusal) as refused:
                self.check("buf", run)
            self.assertEqual(refused.exception.code, "GRDR-SUPPLY-0006")


if __name__ == "__main__":
    unittest.main()
