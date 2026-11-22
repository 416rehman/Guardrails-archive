# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: The Guardrails ADR Authors
"""Install one release-asset build tool by digest.

Usage: python3 -I .github/actions/install-tool/install_tool.py <tool> --dest <dir>
       python3 -I .github/actions/install-tool/install_tool.py <tool> --check-release

The first form reads [tool.<tool>] and [install] from supply-chain/build-tools.toml, fetches the
checksum file, its minisign signature when one is pinned, and this host's asset from
<source>/releases/download/<version>/, checks every size and digest and the signature, takes the
binary out of an archive row by name, writes it to <dir> and runs it with version_flag. It prints
`installed <tool> <version> <platform> sha256:<asset sha256>`. The second form compares every
pinned file, size and digest with `gh release view` (GH_TOKEN from the environment).

A refusal exits 1 with `::error::GRDR-SUPPLY-<nnnn> <tool> <platform> <file>: <reason>` on stderr,
prints no downloaded bytes and leaves no file in <dir>. Codes 0005 to 0010 stay literals until
issue #1829 registers them.
"""

import dataclasses
import hashlib
import http.client
import io
import json
import os
import pathlib
import platform
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import typing
import urllib.error
import urllib.parse
import urllib.request
import zlib

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "pins")]

import minisign
import read_pins

PINS = HERE.parents[2] / "supply-chain" / "build-tools.toml"
MALFORMED = "GRDR-SUPPLY-0002"
MISSING = "GRDR-SUPPLY-0003"
UNREADABLE = "GRDR-SUPPLY-0004"
NO_ROW = "GRDR-SUPPLY-0005"
FETCH = "GRDR-SUPPLY-0006"
DIGEST_MISMATCH = "GRDR-SUPPLY-0007"
SIGNATURE = "GRDR-SUPPLY-0008"
ARCHIVE = "GRDR-SUPPLY-0009"
VERSION = "GRDR-SUPPLY-0010"

# Assets come from GitHub releases only: `source` names the repository and `gh` checks the pins.
SOURCE = re.compile(rf"https://github\.com/(?P<repository>{read_pins.FORMS['repository'].pattern})")
DOWNLOAD = "{source}/releases/download/{version}/{name}"
RELEASE_VIEW = ["gh", "release", "view"]
VERSION_FORM = read_pins.FORMS["version"]
DIGEST = re.compile(r"[0-9a-f]{64}")
PLAIN_NAME = re.compile(r"(?!.*\.\.)[A-Za-z0-9_+][A-Za-z0-9._+-]*")
MEMBER_NAME = re.compile(r"(?!.*\.\.)[A-Za-z0-9_+][A-Za-z0-9._+-]*(?:/[A-Za-z0-9_+][A-Za-z0-9._+-]*)*")
LOWER_NAME = re.compile(r"[a-z0-9][a-z0-9._-]*")
PLATFORM_KEY = re.compile(r"[a-z0-9]+-[a-z0-9_]+")
VERSION_FLAG = re.compile(r"--?[a-z][a-z-]*")
MINISIGN_KEY = re.compile(r"RW[A-Za-z0-9+/]{54}")
CHECKSUM_LINE = re.compile(r"(?P<digest>\S+) [ *](?P<name>.+)")
SIGNATURE_KEYS = ("signature", "signature_size", "minisign_key")
ROW_KEYS = {"file", "size", "sha256", "binary", "member", "member_size"}
SYSTEMS = {"Darwin": "macos"}
MACHINES = {"AMD64": "x86_64", "aarch64": "arm64"}
WINDOWS_SUFFIX = ".exe"
EXECUTABLE_MODE = 0o755
REGULAR_MEMBER = (tarfile.REGTYPE, tarfile.AREGTYPE)
USAGE = "usage: install_tool.py <tool> --dest <dir> | install_tool.py <tool> --check-release"


class Refusal(Exception):
    def __init__(self, code, reason, file="-"):
        super().__init__(f"{code} {reason}")
        self.code, self.reason, self.file = code, reason, file


@dataclasses.dataclass(frozen=True)
class Download:
    name: str
    size: int


@dataclasses.dataclass(frozen=True)
class Member:
    name: str
    size: int


@dataclasses.dataclass(frozen=True)
class Row:
    platform: str
    asset: Download
    sha256: str
    binary: str
    member: Member | None  # None when the asset is the binary itself.


@dataclasses.dataclass(frozen=True)
class Minisign:
    signature: Download
    key: str


@dataclasses.dataclass(frozen=True)
class Pin:
    tool: str
    version: str
    source: str
    repository: str
    version_flag: str
    timeout: int
    checksums: Download
    checksums_sha256: str
    minisign: Minisign | None  # None when the release publishes no signature.
    rows: dict[str, Row]


@dataclasses.dataclass(frozen=True)
class Fetched:
    pin: Pin
    row: Row
    checksums: bytes
    signature: bytes | None  # Present exactly when pin.minisign is.
    asset: bytes


@dataclasses.dataclass(frozen=True)
class Verified:
    pin: Pin
    row: Row
    content: bytes


@dataclasses.dataclass(frozen=True)
class Installed:
    pin: Pin
    row: Row
    path: str


@dataclasses.dataclass(frozen=True)
class Runtime:
    pins: pathlib.Path
    host: str
    open_url: typing.Callable
    run: typing.Callable
    openssl: list[str]


class HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise Refusal(FETCH, f"an HTTP {code} redirect leaves https")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_install(path):
    try:
        with open(path, "rb") as pins:
            install = tomllib.load(pins).get("install")
    except (OSError, ValueError, RecursionError) as error:
        raise Refusal(UNREADABLE, f"cannot read {path}: {type(error).__name__}") from None
    if not isinstance(install, dict):
        raise Refusal(MISSING, f"{path} has no [install] table")
    return install


def load(path, tool):
    try:
        table = read_pins.read_tool(path, tool)
        read_pins.check_one_line(tool, table)
    except read_pins.Refusal as refusal:
        code, _, reason = str(refusal).partition(" ")
        raise Refusal(code, reason) from None
    return table, read_install(path)


def required(table, key, where):
    if key not in table:
        raise Refusal(MISSING, f"{where} has no {key}")
    return table[key]


def text(table, key, form, where):
    value = required(table, key, where)
    if not isinstance(value, str) or not form.fullmatch(value):
        raise Refusal(MALFORMED, f"{where} {key} is not of its form")
    return value


def size(table, key, where):
    value = required(table, key, where)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Refusal(MALFORMED, f"{where} {key} is not a positive integer")
    return value


def names(table, key, where):
    value = required(table, key, where)
    if not isinstance(value, list) or not value:
        raise Refusal(MALFORMED, f"{where} {key} is not a non-empty list")
    if not all(isinstance(name, str) and LOWER_NAME.fullmatch(name) for name in value):
        raise Refusal(MALFORMED, f"{where} {key} holds an entry that is not a lower-case plain name")
    return tuple(value)


def stem(binary):
    return (binary[:-len(WINDOWS_SUFFIX)] if binary.lower().endswith(WINDOWS_SUFFIX) else binary).lower()


def is_toolchain_name(binary, refused, prefixes):
    name = stem(binary)
    return name in refused or any(name.startswith(prefix) and len(name) > len(prefix) for prefix in prefixes)


def read_row(platform_key, row, refused, where):
    where = f"{where} assets {platform_key}"
    if not PLATFORM_KEY.fullmatch(platform_key) or not isinstance(row, dict):
        raise Refusal(MALFORMED, f"{where} is not a platform row")
    if set(row) - ROW_KEYS:
        raise Refusal(MALFORMED, f"{where} holds {sorted(set(row) - ROW_KEYS)!a}")
    binary = text(row, "binary", PLAIN_NAME, where)
    if is_toolchain_name(binary, *refused):
        raise Refusal(MALFORMED, f"{where} binary is named like a toolchain command in [install]")
    has_member = "member" in row or "member_size" in row
    member = Member(text(row, "member", MEMBER_NAME, where), size(row, "member_size", where)) if has_member else None
    asset = Download(text(row, "file", PLAIN_NAME, where), size(row, "size", where))
    return Row(platform_key, asset, text(row, "sha256", DIGEST, where), binary, member)


def read_minisign(table, where):
    if not any(key in table for key in SIGNATURE_KEYS):
        return None
    signature = Download(text(table, "signature", PLAIN_NAME, where), size(table, "signature_size", where))
    return Minisign(signature, text(table, "minisign_key", MINISIGN_KEY, where))


def validate(tool, table, install):
    refused = (names(install, "refused_binaries", "[install]"), names(install, "refused_binary_prefixes", "[install]"))
    timeout = size(install, "timeout_seconds", "[install]")
    where = f"[tool.{tool}]"
    source = text(table, "source", SOURCE, where)
    assets = required(table, "assets", where)
    if not isinstance(assets, dict) or not assets:
        raise Refusal(MALFORMED, f"{where} assets is not a table of platform rows")
    return Pin(
        tool=tool,
        version=text(table, "version", VERSION_FORM, where),
        source=source,
        repository=SOURCE.fullmatch(source)["repository"],
        version_flag=text(table, "version_flag", VERSION_FLAG, where),
        timeout=timeout,
        checksums=Download(text(table, "checksums", PLAIN_NAME, where), size(table, "checksums_size", where)),
        checksums_sha256=text(table, "checksums_sha256", DIGEST, where),
        minisign=read_minisign(table, where),
        rows={key: read_row(key, row, refused, where) for key, row in assets.items()},
    )


def host_platform():
    system, machine = platform.system(), platform.machine()
    return f"{SYSTEMS.get(system, system.lower())}-{MACHINES.get(machine, machine.lower())}"


def select(pin, host):
    if host not in pin.rows:
        raise Refusal(NO_ROW, f"no row for {host}; rows: {', '.join(sorted(pin.rows))}")
    return pin.rows[host]


def read_bounded(stream, size_limit):
    data = bytearray()
    while len(data) <= size_limit:
        chunk = stream.read(size_limit + 1 - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def download(pin, item, open_url):
    url = DOWNLOAD.format(source=pin.source, version=pin.version, name=item.name)
    try:
        with open_url(url, pin.timeout) as response:
            if response.status != 200:
                raise Refusal(FETCH, f"HTTP status {response.status}")
            data = read_bounded(response, item.size)
    except Refusal as refusal:
        raise Refusal(refusal.code, refusal.reason, item.name) from None
    except urllib.error.HTTPError as error:
        raise Refusal(FETCH, f"HTTP status {error.code}", item.name) from None
    except (OSError, http.client.HTTPException, ValueError) as error:
        raise Refusal(FETCH, f"the request failed: {type(error).__name__}", item.name) from None
    if len(data) != item.size:
        raise Refusal(FETCH, f"the body is not the pinned {item.size} bytes", item.name)
    return data


def fetch(pin, row, open_url):
    checksums = download(pin, pin.checksums, open_url)
    signature = None if pin.minisign is None else download(pin, pin.minisign.signature, open_url)
    return Fetched(pin, row, checksums, signature, download(pin, row.asset, open_url))


def listed_digest(checksums, name, file):
    try:
        lines = checksums.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        raise Refusal(DIGEST_MISMATCH, "the checksum file is not UTF-8", file) from None
    found = [line for line in map(CHECKSUM_LINE.fullmatch, lines) if line and line["name"] == name]
    if len(found) != 1:
        raise Refusal(DIGEST_MISMATCH, f"the checksum file has {len(found)} lines for {name}", file)
    return found[0]["digest"]


def archive_member(data, member, file):
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            found = [info for info in archive if info.name == member.name]
            if len(found) != 1:
                raise Refusal(ARCHIVE, f"the archive has {len(found)} members named {member.name}", file)
            if found[0].type not in REGULAR_MEMBER or found[0].size != member.size:
                raise Refusal(ARCHIVE, f"{member.name} is not a regular file of {member.size} bytes", file)
            content = read_bounded(archive.extractfile(found[0]), member.size)
    except (tarfile.TarError, OSError, EOFError, zlib.error) as error:
        raise Refusal(ARCHIVE, f"the archive cannot be read: {type(error).__name__}", file) from None
    if len(content) != member.size:
        raise Refusal(ARCHIVE, f"{member.name} is not {member.size} bytes", file)
    return content


def check_signature(pin, checksums, signature, openssl):
    try:
        minisign.verify(pin.minisign.key, checksums, signature, pin.checksums.name, openssl, pin.timeout)
    except minisign.SignatureRefused as refused:
        raise Refusal(SIGNATURE, str(refused), pin.minisign.signature.name) from None


def verify(fetched, openssl):
    pin, row = fetched.pin, fetched.row
    if sha256(fetched.checksums) != pin.checksums_sha256:
        raise Refusal(DIGEST_MISMATCH, "the checksum file's sha256 is not the pinned one", pin.checksums.name)
    if pin.minisign is not None:
        check_signature(pin, fetched.checksums, fetched.signature, openssl)
    if listed_digest(fetched.checksums, row.asset.name, pin.checksums.name) != row.sha256:
        raise Refusal(DIGEST_MISMATCH, "the checksum file lists another sha256", row.asset.name)
    if sha256(fetched.asset) != row.sha256:
        raise Refusal(DIGEST_MISMATCH, "the asset's sha256 is not the pinned one", row.asset.name)
    content = fetched.asset if row.member is None else archive_member(fetched.asset, row.member, row.asset.name)
    return Verified(pin, row, content)


def write_binary(verified, dest):
    target = os.path.join(dest, verified.row.binary)
    file = verified.row.asset.name
    try:
        os.makedirs(dest, exist_ok=True)
        if os.path.lexists(target) and not stat.S_ISREG(os.lstat(target).st_mode):
            raise Refusal(ARCHIVE, f"{verified.row.binary} in --dest is a link or not a regular file", file)
        handle, temporary = tempfile.mkstemp(dir=dest, prefix=f".{verified.row.binary}.")
        try:
            with os.fdopen(handle, "wb") as written:
                written.write(verified.content)
            if os.name != "nt":
                os.chmod(temporary, EXECUTABLE_MODE)
            os.replace(temporary, target)
        finally:
            if os.path.lexists(temporary):
                os.unlink(temporary)
    except OSError as error:
        raise Refusal(ARCHIVE, f"cannot write {verified.row.binary} to --dest: {type(error).__name__}", file) from None
    return target


def install(verified, dest, run):
    path = write_binary(verified, dest)
    pin = verified.pin
    bare = pin.version.removeprefix("v")
    try:
        result = run([path, pin.version_flag], pin.timeout)
        printed = result.stdout.decode("utf-8", "replace") if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        printed = ""
    if re.search(rf"(?<![0-9.]){re.escape(bare)}(?![0-9.])", printed) is None:
        reason = f"{verified.row.binary} {pin.version_flag} does not report {bare}"
        try:
            os.unlink(path)
        except OSError:
            raise Refusal(VERSION, f"{reason}, and it could not be removed", verified.row.asset.name) from None
        raise Refusal(VERSION, f"{reason}; removed", verified.row.asset.name)
    return Installed(pin, verified.row, path)


def release_assets(pin, run):
    command = [*RELEASE_VIEW, pin.version, "--repo", pin.repository, "--json", "assets"]
    try:
        result = run(command, pin.timeout)
        if result.returncode != 0:
            raise ValueError(result.returncode)
        listing = json.loads(result.stdout)
        if not isinstance(listing, dict) or not isinstance(listing.get("assets"), list):
            raise ValueError("no assets list")
        return [(asset["name"], asset["size"], asset.get("digest")) for asset in listing["assets"]]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        raise Refusal(FETCH, "gh release view gave no asset list") from None


def listing_problem(listed, name, pinned_size, digest):
    found = [(size, listed_digest) for listed_name, size, listed_digest in listed if listed_name == name]
    if len(found) != 1:
        return f"GitHub lists {name} {len(found)} times"
    if found[0][0] != pinned_size:
        return f"GitHub lists {name} with another size"
    if digest is not None and found[0][1] != digest:
        return f"GitHub lists {name} with another digest"
    return None


def check_release(pin, run):
    listed = release_assets(pin, run)
    expected = {pin.checksums.name: (pin.checksums.size, f"sha256:{pin.checksums_sha256}")}
    expected |= {row.asset.name: (row.asset.size, f"sha256:{row.sha256}") for row in pin.rows.values()}
    if pin.minisign is not None:
        expected[pin.minisign.signature.name] = (pin.minisign.signature.size, None)
    for name, (pinned_size, digest) in expected.items():
        problem = listing_problem(listed, name, pinned_size, digest)
        if problem is not None:
            raise Refusal(DIGEST_MISMATCH, problem, name)
    return f"release matches {pin.tool} {pin.version}"


def install_tool(tool, dest, runtime):
    pin = validate(tool, *load(runtime.pins, tool))
    row = select(pin, runtime.host)
    installed = install(verify(fetch(pin, row, runtime.open_url), runtime.openssl), dest, runtime.run)
    return f"installed {tool} {pin.version} {installed.row.platform} sha256:{installed.row.sha256}"


def main(argv, runtime):
    tool = argv[1] if len(argv) > 1 and PLAIN_NAME.fullmatch(argv[1]) else "-"
    try:
        match argv[1:]:
            case [_, "--dest", dest] if tool != "-":
                line = install_tool(tool, dest, runtime)
            case [_, "--check-release"] if tool != "-":
                line = check_release(validate(tool, *load(runtime.pins, tool)), runtime.run)
            case _:
                raise Refusal(MISSING, USAGE)
    except Refusal as refusal:
        print(f"::error::{refusal.code} {tool} {runtime.host} {refusal.file}: {refusal.reason}", file=sys.stderr)
        return 1
    print(line)
    return 0


def run_command(command, timeout):
    return subprocess.run(command, capture_output=True, timeout=timeout, check=False)


def opener(*handlers):
    director = urllib.request.build_opener(HttpsOnlyRedirect, *handlers)
    return lambda url, timeout: director.open(url, timeout=timeout)


def default_runtime():
    return Runtime(pins=PINS, host=host_platform(), open_url=opener(), run=run_command, openssl=["openssl"])


if __name__ == "__main__":
    sys.exit(main(sys.argv, default_runtime()))
