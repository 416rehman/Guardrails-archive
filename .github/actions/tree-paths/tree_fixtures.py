"""Fixture trees for the tree-paths tests, written straight into git objects.

Each tree is built in a throwaway repository with git update-index --index-info, the stdin form of
--cacheinfo, so one index holds paths that differ only in case or carry any byte, on any host.
"""

import os
import subprocess
import tempfile

GIT_SETTINGS = ["-c", "core.ignorecase=false", "-c", "core.protectNTFS=false", "-c", "core.protectHFS=false"]

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
}


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

    def tree(self, paths):
        """Write a tree holding the paths, each a file, and return its id."""
        self.indexes += 1
        index = os.path.join(self.root, ".git", f"fixture-index-{self.indexes}")
        entries = b"".join(f"100644 {self.blob}\t".encode("ascii") + path + b"\0" for path in paths)
        self.git("update-index", "--add", "-z", "--index-info", stdin=entries, index=index)
        return self.git("write-tree", index=index).strip().decode("ascii")

    def listed(self, tree):
        """git's own record of a tree: every path ls-tree -r -t gives, folders included."""
        listing = self.git("ls-tree", "-r", "-t", "-z", tree)
        return [entry.partition(b"\t")[2] for entry in listing.split(b"\0") if entry]

    def close(self):
        self.scratch.cleanup()
