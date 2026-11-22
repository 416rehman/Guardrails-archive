"""Fixture trees for the tree-paths tests, written straight into git objects.

Each tree is built in a throwaway repository with git update-index --index-info, the stdin form of
--cacheinfo, so one index holds paths that differ only in case or carry any byte, on any host.
A path is a file unless it is given as (mode, path).
"""

import os
import subprocess
import tempfile

GIT_SETTINGS = ["-c", "core.ignorecase=false", "-c", "core.protectNTFS=false", "-c", "core.protectHFS=false"]
FILE = "100644"
SYMBOLIC_LINK = "120000"
SUBMODULE = "160000"
SUBMODULE_COMMIT = "5e" * 20

CLEAN = [b"README.md", b"Cargo.toml", b"rust-toolchain.toml", b"crates/a/Cargo.toml", b"crates/a/src/lib.rs"]

# Each seeded case, and the paths it must name.
SEEDED = {
    "case-variant-path": (CLEAN + [b"readme.md"], {b"README.md", b"readme.md"}),
    "case-variant-prefix": (CLEAN + [b"Crates/b/src/lib.rs"], {b"crates", b"Crates"}),
    "case-variant-nested-prefix": (CLEAN + [b"crates/A/x.rs"], {b"crates/a", b"crates/A"}),
    "byte-outside-ascii": (CLEAN + [b"docs/caf\xc3\xa9.md", b"docs/tab\there.md"],
                           {b"docs/caf\xc3\xa9.md", b"docs/tab\there.md"}),
    "toolchain-file-root": (CLEAN + [b"rust-toolchain"], {b"rust-toolchain"}),
    "toolchain-file-nested": (CLEAN + [b"crates/a/rust-toolchain"], {b"crates/a/rust-toolchain"}),
    "toolchain-file-variant": (CLEAN + [b"crates/a/Rust-Toolchain"], {b"crates/a/Rust-Toolchain"}),
    "tilde-digit-file": (CLEAN + [b"CARGO~1.TOM"], {b"CARGO~1.TOM"}),
    "tilde-digit-folder": (CLEAN + [b"crates/A~12/src/lib.rs"], {b"crates/A~12", b"crates/A~12/src/lib.rs"}),
    "symbolic-link": (CLEAN + [(SYMBOLIC_LINK, b"crates/b")], {b"crates/b"}),
    "symbolic-link-nested": (CLEAN + [(SYMBOLIC_LINK, b"crates/a/src/.cargo")], {b"crates/a/src/.cargo"}),
    "submodule": (CLEAN + [(SUBMODULE, b"crates/b")], {b"crates/b"}),
    "submodule-nested": (CLEAN + [(SUBMODULE, b"crates/a/src/v")], {b"crates/a/src/v"}),
}


def entry(item):
    return item if isinstance(item, tuple) else (FILE, item)


def path_of(item):
    return entry(item)[1]


class FixtureRepo:
    def __init__(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = self.scratch.name
        self.indexes = 0
        self.git("init", "-q")
        self.blob = self.git("hash-object", "-w", "--stdin", stdin=b"fixture\n").strip().decode("ascii")

    def git(self, *args, stdin=b"", index=None):
        environment = dict(os.environ)
        if index is not None:
            environment["GIT_INDEX_FILE"] = index
        result = subprocess.run(
            ["git", *GIT_SETTINGS, *args], cwd=self.root, input=stdin, env=environment,
            capture_output=True, check=True,
        )
        return result.stdout

    def tree(self, items, contents=None):
        """Write a tree of the items, plus a file with those bytes for each path in contents."""
        self.indexes += 1
        index = os.path.join(self.root, ".git", f"fixture-index-{self.indexes}")
        blobs = {path: self.git("hash-object", "-w", "--stdin", stdin=text).strip().decode("ascii")
                 for path, text in (contents or {}).items()}
        lines = []
        for mode, path in map(entry, [*items, *blobs]):
            target = SUBMODULE_COMMIT if mode == SUBMODULE else blobs.get(path, self.blob)
            lines.append(f"{mode} {target}\t".encode("ascii") + path + b"\0")
        self.git("update-index", "--add", "-z", "--index-info", stdin=b"".join(lines), index=index)
        return self.git("write-tree", index=index).strip().decode("ascii")

    def listed(self, tree):
        """git's own record of a tree: every (mode, path) ls-tree -r -t gives, folders included."""
        listing = self.git("ls-tree", "-r", "-t", "-z", tree)
        records = []
        for record in listing.split(b"\0"):
            if record:
                meta, _, path = record.partition(b"\t")
                records.append((meta.split(b" ")[0].decode("ascii"), path))
        return records

    def close(self):
        self.scratch.cleanup()
