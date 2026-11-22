// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::process;
use std::sync::atomic::{AtomicUsize, Ordering};

static COPIES: AtomicUsize = AtomicUsize::new(0);

/// Copies fixture workspace `name` to a fresh directory under the test temporary directory and
/// returns its manifest, so `cargo metadata` writes its lockfile there, not into the source tree,
/// and tests running at once never share a copy.
pub fn fixture_manifest(name: &str) -> io::Result<PathBuf> {
    let source = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name);
    let copy_number = COPIES.fetch_add(1, Ordering::Relaxed);
    let copy = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("fixtures")
        .join(format!("{name}-{}-{copy_number}", process::id()));
    if copy.exists() {
        fs::remove_dir_all(&copy)?;
    }
    copy_tree(&source, &copy)?;
    Ok(copy.join("Cargo.toml"))
}

fn copy_tree(from: &Path, to: &Path) -> io::Result<()> {
    fs::create_dir_all(to)?;
    for entry in fs::read_dir(from)? {
        let entry = entry?;
        let target = to.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_tree(&entry.path(), &target)?;
        } else {
            fs::copy(entry.path(), target)?;
        }
    }
    Ok(())
}
