// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

#[path = "table_ref/mod.rs"]
mod table_ref;

use std::fs;
use std::path::PathBuf;
use table_ref::{RefVerdict, section_bounds_from_header, validate, validate_header};

fn fixture_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("table")
}

#[test]
fn reference_validator_matches_all_fixtures() {
    let mut entries: Vec<PathBuf> = fs::read_dir(fixture_dir())
        .expect("read fixtures dir")
        .map(|e| e.expect("dir entry").path())
        .collect();
    entries.sort();

    let mut seen_rules = [false; 34];
    let mut valid_count = 0usize;

    for path in entries {
        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .expect("ascii filename");
        let bytes = fs::read(&path).expect("read fixture");

        if name.starts_with("valid_") {
            assert_eq!(
                validate_header(&bytes),
                RefVerdict::Accept,
                "header rejected {name}"
            );
            assert_eq!(validate(&bytes), RefVerdict::Accept, "body rejected {name}");
            let bounds = section_bounds_from_header(&bytes).expect("header bounds");
            for &(idx, off, len) in &bounds {
                assert!(
                    off >= 232 && off + len <= bytes.len() as u64,
                    "section {idx} out of bounds in {name}"
                );
            }
            valid_count += 1;
        } else if let Some(rest) = name.strip_prefix("tv") {
            let prefix = rest.get(..2).expect("tvNN prefix");
            let num: u8 = prefix.parse().expect("rule number prefix");
            let expected = RefVerdict::Reject {
                rule: num,
                abi: num == 3,
            };
            assert_eq!(
                validate(&bytes),
                expected,
                "fixture {name} expected TV-{num}"
            );
            if num <= 14 {
                assert_eq!(
                    validate_header(&bytes),
                    expected,
                    "header fixture {name} expected TV-{num}"
                );
            } else {
                assert_eq!(
                    validate_header(&bytes),
                    RefVerdict::Accept,
                    "body fixture {name} failed header"
                );
            }
            seen_rules[usize::from(num)] = true;
        } else {
            panic!("unexpected fixture filename: {name}");
        }
    }

    assert!(valid_count >= 3, "expected at least 3 valid fixtures");
    for (rule, &seen) in seen_rules.iter().enumerate().skip(1) {
        assert!(seen, "missing fixture for TV-{rule}");
    }
}
