// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use grdr_fastpath::layout::{
    ABI_MAX_ACTION_CLASS, ExeEntry, FloorRow, HEADER_LEN, Header, HostEntry, MAGIC,
    ProcessScopeEntry, ReasonEntry, SECTION_COUNT, SectionEntry, TABLE_FORMAT, abi_version,
};
use grdr_fastpath::{ArgFault, BundleFault, Error, arena_size, load};
use std::fs;
use std::path::PathBuf;

fn fixture_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("table")
}

fn empty_header(action_class_count: u16) -> Header {
    Header {
        magic: MAGIC,
        table_format: TABLE_FORMAT,
        abi_min: abi_version(),
        blob_len: HEADER_LEN as u32,
        bundle_digest: [0x11; 32],
        compiler_version_major: 0,
        compiler_version_minor: 1,
        compiler_version_patch: 0,
        effective_hash: [0x22; 32],
        sections: [SectionEntry {
            count: 0,
            offset: 0,
        }; SECTION_COUNT],
        eval_cap: 10_000,
        action_class_count,
        principal_kind_count: 2,
        session_rule_classes: 0,
        path_fold_classes: 0,
        expiry_bundle_ns: 1_000_000,
        expiry_session_ns: u64::MAX,
        path_max_units: 4096,
        loss_closed_classes: 0,
    }
}

fn read_arena_slot(arena: &[u8], class: usize) -> (u32, u32) {
    let base = class * 8;
    let start_chunk = arena
        .get(base..)
        .and_then(|s| s.first_chunk::<4>())
        .copied()
        .unwrap_or([0; 4]);
    let count_chunk = arena
        .get(base + 4..)
        .and_then(|s| s.first_chunk::<4>())
        .copied()
        .unwrap_or([0; 4]);
    (
        u32::from_le_bytes(start_chunk),
        u32::from_le_bytes(count_chunk),
    )
}

#[test]
fn fastpath_rule_variant() {
    let mut entries: Vec<PathBuf> = fs::read_dir(fixture_dir())
        .expect("read fixtures dir")
        .map(|e| e.expect("dir entry").path())
        .collect();
    entries.sort();

    let mut seen_rules = [false; 34];
    let mut seen_tv8_loss_closed = false;
    let mut seen_tv26_loss_closed = false;
    let mut valid_count = 0usize;

    for path in entries {
        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .expect("ascii filename");
        let bytes = fs::read(&path).expect("read fixture");

        if name.starts_with("valid_") {
            let needed = arena_size(&bytes).expect("valid fixture header");
            let mut arena = vec![0u8; needed];
            let tables = load(bytes.as_slice(), arena.as_mut_slice()).expect("valid fixture load");
            assert_eq!(tables.header().blob_len as usize, bytes.len());
            valid_count += 1;
        } else if let Some(rest) = name.strip_prefix("tv") {
            let prefix = rest.get(..2).expect("tvNN prefix");
            let rule_num: u8 = prefix.parse().expect("rule number prefix");
            let err = if rule_num <= 14 {
                let header_err = arena_size(&bytes).expect_err("header rule must fail arena_size");
                let mut arena = vec![0u8; 512];
                let load_err =
                    load(bytes.as_slice(), arena.as_mut_slice()).expect_err("must fail load");
                assert_eq!(
                    header_err, load_err,
                    "arena_size vs load mismatch on {name}"
                );
                load_err
            } else {
                let needed = arena_size(&bytes).expect("body fixture header must pass arena_size");
                let mut arena = vec![0u8; needed];
                load(bytes.as_slice(), arena.as_mut_slice()).expect_err("body rule must fail load")
            };

            if rule_num == 3 {
                assert_eq!(err, Error::Abi, "{name} must return Error::Abi");
            } else {
                match err {
                    Error::Bundle(BundleFault::Rule(tv)) => {
                        assert_eq!(tv.number(), rule_num, "wrong TV rule for {name}");
                    }
                    other => {
                        panic!("{name} returned {other:?} instead of Bundle(Rule({rule_num}))")
                    }
                }
            }
            assert_eq!(err.rule(), Some(rule_num), "Error::rule mismatch on {name}");

            if name.contains("tv08_loss_closed") {
                seen_tv8_loss_closed = true;
            }
            if name.contains("tv26_loss_closed") {
                seen_tv26_loss_closed = true;
            }
            seen_rules[usize::from(rule_num)] = true;
        } else {
            panic!("unexpected fixture {name}");
        }
    }

    assert!(valid_count >= 3, "expected valid fixtures");
    assert!(
        seen_tv8_loss_closed,
        "expected tv08 loss_closed_classes fixture"
    );
    assert!(
        seen_tv26_loss_closed,
        "expected tv26 loss_closed_classes fixture"
    );
    for (rule, &seen) in seen_rules.iter().enumerate().skip(1) {
        assert!(seen, "missing fixture for TV-{rule}");
    }
}

#[test]
fn valid_full_builds_exact_arena_row_index() {
    let bytes = include_bytes!("fixtures/table/valid_full.bin");
    let needed = arena_size(bytes).expect("arena_size");
    let mut arena = vec![0u8; needed];
    let tables = load(bytes.as_slice(), arena.as_mut_slice()).expect("load valid_full");
    assert_eq!(tables.header().action_class_count, 15);
    let (_, arena_view) = tables.into_parts();

    // valid_full has 2 rows in class 1, 1 row in class 2, 1 row in class 3, and 0 in classes 4..=15.
    assert_eq!(read_arena_slot(arena_view, 0), (0, 0));
    assert_eq!(read_arena_slot(arena_view, 1), (0, 2));
    assert_eq!(read_arena_slot(arena_view, 2), (2, 1));
    assert_eq!(read_arena_slot(arena_view, 3), (3, 1));
    for class in 4..=15 {
        assert_eq!(read_arena_slot(arena_view, class), (4, 0));
    }
}

#[test]
fn arena_index_places_empty_runs_between_populated_classes() {
    let mut pool = Vec::new();
    let reason = b"DENY_IT";
    let rule = b"base/p@1/r1";
    let reason_off = pool.len() as u32;
    pool.extend_from_slice(reason);
    let rule_off = pool.len() as u32;
    pool.extend_from_slice(rule);

    let reason_entry = ReasonEntry {
        reason_off,
        rule_off,
        reason_len: reason.len() as u16,
        rule_len: rule.len() as u16,
    }
    .encode();

    let row2 = FloorRow {
        action_class: 2,
        principal_kind: 0,
        outcome: 2,
        reason: 0,
        resource_classes: 0,
        required_labels: 0,
        forbidden_labels: 0,
        grant_digest: [0; 32],
    }
    .encode();
    let row5a = FloorRow {
        action_class: 5,
        principal_kind: 0,
        outcome: 2,
        reason: 0,
        resource_classes: 0,
        required_labels: 0,
        forbidden_labels: 0,
        grant_digest: [0; 32],
    }
    .encode();
    let row5b = FloorRow {
        action_class: 5,
        principal_kind: 1,
        outcome: 3,
        reason: 0,
        resource_classes: 0,
        required_labels: 0,
        forbidden_labels: 0,
        grant_digest: [0; 32],
    }
    .encode();

    let floor_off = HEADER_LEN as u32;
    let reason_sec_off = floor_off + 3 * 64;
    let pool_sec_off = reason_sec_off + 16;
    let total_len = pool_sec_off + (pool.len() as u32);

    let mut hdr = empty_header(6);
    hdr.blob_len = total_len;
    hdr.loss_closed_classes = (1 << 2) | (1 << 5);
    hdr.sections[0] = SectionEntry {
        count: 3,
        offset: floor_off,
    };
    hdr.sections[8] = SectionEntry {
        count: 1,
        offset: reason_sec_off,
    };
    hdr.sections[9] = SectionEntry {
        count: pool.len() as u32,
        offset: pool_sec_off,
    };

    let mut blob = Vec::with_capacity(total_len as usize);
    blob.extend_from_slice(&hdr.encode());
    blob.extend_from_slice(&row2);
    blob.extend_from_slice(&row5a);
    blob.extend_from_slice(&row5b);
    blob.extend_from_slice(&reason_entry);
    blob.extend_from_slice(&pool);

    let needed = arena_size(&blob).expect("arena_size");
    assert_eq!(needed, 8 * 7);
    let mut arena = vec![0u8; needed];
    let _tables = load(blob.as_slice(), arena.as_mut_slice()).expect("load");

    assert_eq!(read_arena_slot(&arena, 0), (0, 0));
    assert_eq!(read_arena_slot(&arena, 1), (0, 0));
    assert_eq!(read_arena_slot(&arena, 2), (0, 1));
    assert_eq!(read_arena_slot(&arena, 3), (1, 0));
    assert_eq!(read_arena_slot(&arena, 4), (1, 0));
    assert_eq!(read_arena_slot(&arena, 5), (1, 2));
    assert_eq!(read_arena_slot(&arena, 6), (3, 0));
}

#[test]
fn tv07_every_header_padding_byte_is_checked() {
    let base = empty_header(ABI_MAX_ACTION_CLASS).encode();
    for pad_idx in [20usize, 21, 22, 23, 62, 63, 183, 220, 221, 222, 223] {
        let mut blob = base;
        blob[pad_idx] = 0x01;
        assert_eq!(arena_size(&blob).unwrap_err().rule(), Some(7));
    }
}

#[test]
fn tv08_all_header_parameter_bounds_checked() {
    let mut hdr = empty_header(ABI_MAX_ACTION_CLASS);
    hdr.eval_cap = 0;
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let hdr = empty_header(0);
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let hdr = empty_header(ABI_MAX_ACTION_CLASS + 1);
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let hdr = empty_header(64);
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let mut hdr = empty_header(ABI_MAX_ACTION_CLASS);
    hdr.principal_kind_count = 0;
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let mut hdr = empty_header(ABI_MAX_ACTION_CLASS);
    hdr.path_max_units = 0;
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let mut hdr = empty_header(ABI_MAX_ACTION_CLASS);
    hdr.expiry_bundle_ns = 0;
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let mut hdr = empty_header(ABI_MAX_ACTION_CLASS);
    hdr.expiry_session_ns = 0;
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let mut hdr = empty_header(5);
    hdr.session_rule_classes = 1 << 0;
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let mut hdr = empty_header(5);
    hdr.session_rule_classes = 1 << 6;
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let mut hdr = empty_header(5);
    hdr.loss_closed_classes = 1 << 0;
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    let mut hdr = empty_header(5);
    hdr.loss_closed_classes = 1 << 6;
    assert_eq!(arena_size(&hdr.encode()).unwrap_err().rule(), Some(8));

    // Highest allowed bit (5) passes TV-8; path_fold_classes is unrestricted.
    let mut hdr = empty_header(5);
    hdr.session_rule_classes = 1 << 5;
    hdr.loss_closed_classes = 1 << 5;
    hdr.path_fold_classes = u64::MAX;
    assert!(arena_size(&hdr.encode()).is_ok());
}

#[test]
fn redacting_debug_leaks_no_digest_or_addr_bytes() {
    let secret_bytes: [u8; 32] = *b"SECRET_DIGEST_VALUE_DO_NOT_LEAK!";
    let secret_addr: [u8; 16] = *b"SECRET_IP_ADDR!!";
    let secret_hex_tag = "53454352"; // "SECR" in hex

    let mut hdr = empty_header(ABI_MAX_ACTION_CLASS);
    hdr.bundle_digest = secret_bytes;
    hdr.effective_hash = secret_bytes;
    let hdr_dbg = format!("{hdr:?}");
    assert!(!hdr_dbg.contains("SECRET"));
    assert!(!hdr_dbg.contains(secret_hex_tag));

    let row = FloorRow {
        action_class: 1,
        principal_kind: 0,
        outcome: 2,
        reason: 0,
        resource_classes: 0,
        required_labels: 0,
        forbidden_labels: 0,
        grant_digest: secret_bytes,
    };
    let row_dbg = format!("{row:?}");
    assert!(!row_dbg.contains("SECRET"));
    assert!(!row_dbg.contains(secret_hex_tag));

    let host = HostEntry {
        class_mask: 1,
        kind: 4,
        prefix_len: 128,
        port_lo: 80,
        port_hi: 80,
        name_len: 0,
        name_off: 0,
        addr: secret_addr,
    };
    let host_dbg = format!("{host:?}");
    assert!(!host_dbg.contains("SECRET"));
    assert!(!host_dbg.contains(secret_hex_tag));

    let exe = ExeEntry {
        digest: secret_bytes,
        class_mask: 1,
    };
    let exe_dbg = format!("{exe:?}");
    assert!(!exe_dbg.contains("SECRET"));
    assert!(!exe_dbg.contains(secret_hex_tag));

    let proc_entry = ProcessScopeEntry {
        utf8_off: 0,
        utf16_off: 0,
        utf8_len: 0,
        utf16_len: 0,
        kind: 1,
        digest: secret_bytes,
    };
    let proc_dbg = format!("{proc_entry:?}");
    assert!(!proc_dbg.contains("SECRET"));
    assert!(!proc_dbg.contains(secret_hex_tag));

    let mut blob_hdr = empty_header(ABI_MAX_ACTION_CLASS);
    blob_hdr.bundle_digest = secret_bytes;
    blob_hdr.effective_hash = secret_bytes;
    let blob = blob_hdr.encode();
    let needed = arena_size(&blob).expect("arena_size");
    let mut arena = vec![0u8; needed];
    let tables = load(blob.as_slice(), arena.as_mut_slice()).expect("load");
    let tables_dbg = format!("{tables:?}");
    assert!(!tables_dbg.contains("SECRET"));
    assert!(!tables_dbg.contains(secret_hex_tag));
}

#[test]
fn load_rejects_short_arena_with_arg_arena() {
    let bytes = include_bytes!("fixtures/table/valid_full.bin");
    let needed = arena_size(bytes).expect("arena_size");
    let mut short = vec![0u8; needed - 1];
    assert_eq!(
        load(bytes.as_slice(), short.as_mut_slice()).unwrap_err(),
        Error::Arg(ArgFault::Arena)
    );
}
