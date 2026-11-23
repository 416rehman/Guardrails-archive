// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use grdr_fastpath::layout::{
    HEADER_LEN, Header, HostEntry, MAGIC, PathEntry, SECTION_COUNT, SectionEntry, TABLE_FORMAT,
    abi_version,
};
use grdr_fastpath::{arena_size, load};

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

#[test]
fn tv20_path_pattern_escape_and_globstar_edge_cases() {
    fn build_single_path_blob(pattern: &str) -> Vec<u8> {
        let mut pool = Vec::new();
        let u8o = pool.len() as u32;
        pool.extend_from_slice(pattern.as_bytes());
        let u8l = pattern.len() as u16;
        if pool.len() % 2 == 1 {
            pool.push(0);
        }
        let u16o = pool.len() as u32;
        let units: Vec<u16> = pattern.encode_utf16().collect();
        for u in &units {
            pool.extend_from_slice(&u.to_le_bytes());
        }
        let entry = PathEntry {
            utf8_off: u8o,
            utf16_off: u16o,
            utf8_len: u8l,
            utf16_len: units.len() as u16,
            class_bit: 0,
        }
        .encode();
        let sec1_off = HEADER_LEN as u32;
        let pool_off = sec1_off + 16;
        let mut hdr = empty_header(1);
        hdr.blob_len = pool_off + (pool.len() as u32);
        hdr.sections[1] = SectionEntry {
            count: 1,
            offset: sec1_off,
        };
        hdr.sections[9] = SectionEntry {
            count: pool.len() as u32,
            offset: pool_off,
        };
        let mut blob = Vec::new();
        blob.extend_from_slice(&hdr.encode());
        blob.extend_from_slice(&entry);
        blob.extend_from_slice(&pool);
        blob
    }

    for valid in [
        "/a",
        "/a/b",
        "/**",
        "**",
        "**/a",
        "**/.env",
        "**/..hidden",
        "/a/\\*/\\?/\\\\",
        "/a/\\**",
        "/a/*\\*",
        "/a/\\**b",
    ] {
        let blob = build_single_path_blob(valid);
        let mut arena = vec![0u8; arena_size(&blob).expect("arena_size")];
        assert!(
            load(blob.as_slice(), arena.as_mut_slice()).is_ok(),
            "expected valid path pattern: {valid}"
        );
    }

    for invalid in [
        "/", "//", "/a/", "/a//b", "/./a", "/a/.", "/a/..", "a/b", "**a", "/**a", "/a**", "/***",
        "/a/\\***", "/a\\", "/a/\\b", "/a/\\.", "\\**",
    ] {
        let blob = build_single_path_blob(invalid);
        let mut arena = vec![0u8; arena_size(&blob).expect("arena_size")];
        let err = load(blob.as_slice(), arena.as_mut_slice()).unwrap_err();
        assert_eq!(
            err.rule(),
            Some(20),
            "expected TV-20 for pattern: {invalid}"
        );
    }
}

#[test]
fn tv21_and_tv22_host_and_cidr_edge_cases() {
    fn build_single_host_blob(entry: HostEntry, name: Option<&str>) -> Vec<u8> {
        let pool = name.map(|s| s.as_bytes().to_vec()).unwrap_or_default();
        let sec2_off = HEADER_LEN as u32;
        let pool_off = sec2_off + 40;
        let mut hdr = empty_header(1);
        hdr.blob_len = if pool.is_empty() {
            pool_off
        } else {
            pool_off + (pool.len() as u32)
        };
        hdr.sections[2] = SectionEntry {
            count: 1,
            offset: sec2_off,
        };
        if !pool.is_empty() {
            hdr.sections[9] = SectionEntry {
                count: pool.len() as u32,
                offset: pool_off,
            };
        }
        let mut blob = Vec::new();
        blob.extend_from_slice(&hdr.encode());
        blob.extend_from_slice(&entry.encode());
        blob.extend_from_slice(&pool);
        blob
    }

    let make_name = |name: &str| HostEntry {
        class_mask: 1,
        kind: 1,
        prefix_len: 0,
        port_lo: 0,
        port_hi: 65535,
        name_len: name.len() as u16,
        name_off: 0,
        addr: [0; 16],
    };

    for valid_host in [
        "localhost",
        "api.example.com",
        "a-1.b2.test",
        "foo.123a",
        "foo.0x1g",
        &"a".repeat(63),
    ] {
        let blob = build_single_host_blob(make_name(valid_host), Some(valid_host));
        let mut arena = vec![0u8; arena_size(&blob).expect("arena_size")];
        assert!(
            load(blob.as_slice(), arena.as_mut_slice()).is_ok(),
            "expected valid host: {valid_host}"
        );
    }

    let too_long_host = format!(
        "{}.{}.{}.{}",
        "a".repeat(63),
        "b".repeat(63),
        "c".repeat(63),
        "d".repeat(62)
    );
    assert_eq!(too_long_host.len(), 254);

    for bad_host in [
        "Api.example.com",
        ".example.com",
        "example.com.",
        "a..b",
        "-a.com",
        "a-.com",
        "a_b.com",
        "127.0.0.1",
        "foo.123",
        "foo.0x7f",
        &"a".repeat(64),
        &too_long_host,
    ] {
        let blob = build_single_host_blob(make_name(bad_host), Some(bad_host));
        let mut arena = vec![0u8; arena_size(&blob).expect("arena_size")];
        let err = load(blob.as_slice(), arena.as_mut_slice()).unwrap_err();
        assert_eq!(err.rule(), Some(21), "expected TV-21 for host: {bad_host}");
    }

    for (kind, plen, addr) in [
        (3u8, 0u8, [0u8; 16]),
        (3, 32, [192, 0, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        (4, 0, [0; 16]),
        (
            4,
            64,
            [0x20, 0x01, 0x0d, 0xb8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ),
        (
            4,
            32,
            [0x00, 0x64, 0xFF, 0x9B, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ),
    ] {
        let entry = HostEntry {
            class_mask: 1,
            kind,
            prefix_len: plen,
            port_lo: 0,
            port_hi: 65535,
            name_len: 0,
            name_off: 0,
            addr,
        };
        let blob = build_single_host_blob(entry, None);
        let mut arena = vec![0u8; arena_size(&blob).expect("arena_size")];
        assert!(load(blob.as_slice(), arena.as_mut_slice()).is_ok());
    }

    for (kind, plen, addr) in [
        (3u8, 33u8, [0u8; 16]),
        (3, 24, [192, 0, 2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        (3, 24, [192, 0, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        (4, 129, [0; 16]),
        (
            4,
            64,
            [0x20, 0x01, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        ),
        (
            4,
            96,
            [0x00, 0x64, 0xFF, 0x9B, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ),
        (
            4,
            128,
            [0x00, 0x64, 0xFF, 0x9B, 0, 0, 0, 0, 0, 0, 0, 0, 192, 0, 2, 1],
        ),
    ] {
        let entry = HostEntry {
            class_mask: 1,
            kind,
            prefix_len: plen,
            port_lo: 0,
            port_hi: 65535,
            name_len: 0,
            name_off: 0,
            addr,
        };
        let blob = build_single_host_blob(entry, None);
        let mut arena = vec![0u8; arena_size(&blob).expect("arena_size")];
        let err = load(blob.as_slice(), arena.as_mut_slice()).unwrap_err();
        assert_eq!(err.rule(), Some(22));
    }
}
