// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use grdr_fastpath::layout::{
    ABI_MAJOR, ABI_MAX_ACTION_CLASS, ABI_MINOR, ExeEntry, Expiry, FloorRow, HEADER_LEN, Header,
    HostEntry, MAGIC, NAME_MAX_BYTES, Nanos, PathEntry, PortRange, ProcessScopeEntry, ReasonEntry,
    Record, SECTION_COUNT, Section, SectionEntry, TABLE_FORMAT, abi_version, exe_lookup_steps,
    path_entry_steps, path_steps_from_pattern_lens, total_eval_cost,
};
use grdr_fastpath::{ArgFault, BundleFault, Error, Tables, arena_size, load};

#[test]
fn header_encode_decode_roundtrip() {
    let mut sections = [SectionEntry {
        count: 0,
        offset: 0,
    }; SECTION_COUNT];
    sections[Section::FloorRows.index()] = SectionEntry {
        count: 3,
        offset: 232,
    };
    sections[Section::StringPool.index()] = SectionEntry {
        count: 42,
        offset: 424,
    };

    let hdr = Header {
        magic: MAGIC,
        table_format: TABLE_FORMAT,
        abi_min: abi_version(),
        blob_len: 466,
        bundle_digest: [0xA5; 32],
        compiler_version_major: 0,
        compiler_version_minor: 1,
        compiler_version_patch: 7,
        effective_hash: [0x5A; 32],
        sections,
        eval_cap: 50_000,
        action_class_count: ABI_MAX_ACTION_CLASS,
        principal_kind_count: 2,
        session_rule_classes: 0b1010,
        path_fold_classes: 0b0101,
        expiry_bundle_ns: 60_000_000_000,
        expiry_session_ns: u64::MAX,
        path_max_units: 4096,
        loss_closed_classes: 0b0010,
    };

    let bytes = hdr.encode();
    assert_eq!(bytes.len(), HEADER_LEN);
    assert_eq!(&bytes[20..24], &[0; 4]);
    assert_eq!(&bytes[62..64], &[0; 2]);
    assert_eq!(bytes[183], 0);
    assert_eq!(&bytes[220..224], &[0; 4]);

    let decoded = Header::decode(&bytes);
    assert_eq!(decoded, hdr);
    assert_eq!(decoded.labels_bundle_tag(), u64::from_le_bytes([0xA5; 8]));
}

#[test]
fn records_encode_decode_and_sealed_sizes() {
    assert_eq!(FloorRow::SIZE, 64);
    assert_eq!(PathEntry::SIZE, 16);
    assert_eq!(HostEntry::SIZE, 40);
    assert_eq!(ExeEntry::SIZE, 40);
    assert_eq!(ProcessScopeEntry::SIZE, 48);
    assert_eq!(PortRange::SIZE, 4);
    assert_eq!(ReasonEntry::SIZE, 16);
    assert_eq!(NAME_MAX_BYTES, 253);
    assert_eq!(
        abi_version(),
        (u32::from(ABI_MAJOR) << 16) | u32::from(ABI_MINOR)
    );

    let row = FloorRow {
        action_class: 1,
        principal_kind: 2,
        outcome: 2,
        reason: 0,
        resource_classes: 0x0F,
        required_labels: 0x01,
        forbidden_labels: 0x02,
        grant_digest: [0x11; 32],
    };
    let row_bytes = row.encode();
    assert_eq!(FloorRow::decode(&row_bytes), row);
    assert_eq!(FloorRow::decode_slice(&row_bytes), Some(row));
    assert_eq!(FloorRow::decode_slice(&row_bytes[..63]), None);

    let path = PathEntry {
        utf8_off: 4,
        utf16_off: 16,
        utf8_len: 10,
        utf16_len: 10,
        class_bit: 7,
    };
    let path_bytes = path.encode();
    assert_eq!(&path_bytes[13..16], &[0; 3]);
    assert_eq!(PathEntry::decode(&path_bytes), path);

    let host = HostEntry {
        class_mask: 0x80,
        kind: 3,
        prefix_len: 24,
        port_lo: 80,
        port_hi: 443,
        name_len: 0,
        name_off: 0,
        addr: [192, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    };
    let host_bytes = host.encode();
    assert_eq!(&host_bytes[20..24], &[0; 4]);
    assert_eq!(HostEntry::decode(&host_bytes), host);

    let exe = ExeEntry {
        digest: [0x22; 32],
        class_mask: 0x10,
    };
    assert_eq!(ExeEntry::decode(&exe.encode()), exe);

    let proc_entry = ProcessScopeEntry {
        utf8_off: 10,
        utf16_off: 20,
        utf8_len: 8,
        utf16_len: 8,
        kind: 3,
        digest: [0; 32],
    };
    let proc_bytes = proc_entry.encode();
    assert_eq!(&proc_bytes[13..16], &[0; 3]);
    assert_eq!(ProcessScopeEntry::decode(&proc_bytes), proc_entry);

    let port = PortRange {
        port_lo: 8000,
        port_hi: 8443,
    };
    assert_eq!(PortRange::decode(&port.encode()), port);

    let reason = ReasonEntry {
        reason_off: 0,
        rule_off: 8,
        reason_len: 8,
        rule_len: 16,
    };
    let reason_bytes = reason.encode();
    assert_eq!(&reason_bytes[12..16], &[0; 4]);
    assert_eq!(ReasonEntry::decode(&reason_bytes), reason);
}

#[test]
fn expiry_nanos_and_cost_formula() {
    assert_eq!(Nanos::new(0), None);
    assert_eq!(Nanos::new(u64::MAX), None);
    let some_ns = Nanos::new(1_000).expect("valid nanos");
    assert_eq!(some_ns.get(), 1_000);

    assert_eq!(Expiry::from_header_ns(0), None);
    assert_eq!(Expiry::from_header_ns(u64::MAX), Some(Expiry::ScopeEnd));
    assert_eq!(Expiry::from_header_ns(1_000), Some(Expiry::After(some_ns)));
    assert_eq!(Expiry::ScopeEnd.to_header_ns(), u64::MAX);
    assert_eq!(Expiry::After(some_ns).to_header_ns(), 1_000);

    assert_eq!(path_entry_steps(4, 5), 30);
    assert_eq!(path_entry_steps(u64::MAX, 5), u64::MAX);
    assert_eq!(path_steps_from_pattern_lens(3, [2, 4]), 4 * 3 + 4 * 5);
    assert_eq!(exe_lookup_steps(0), 0);
    assert_eq!(exe_lookup_steps(1), 1);
    assert_eq!(exe_lookup_steps(2), 2);
    assert_eq!(exe_lookup_steps(3), 2);
    assert_eq!(exe_lookup_steps(4), 3);
    assert_eq!(exe_lookup_steps(u32::MAX), 32);
    assert_eq!(total_eval_cost(10, 20, 5, 3), 38);
    assert_eq!(total_eval_cost(10, u64::MAX, 1, 1), u64::MAX);
}

#[test]
fn arena_size_and_arena_short_error() {
    let empty_blob = include_bytes!("fixtures/table/valid_empty.bin");
    let needed = arena_size(empty_blob).expect("valid empty header");
    assert_eq!(needed, 8 * (usize::from(ABI_MAX_ACTION_CLASS) + 1));
    assert!(needed <= 8 * (usize::from(ABI_MAX_ACTION_CLASS) + 1));

    let mut short_arena = vec![0u8; needed - 1];
    assert_eq!(
        load(empty_blob.as_slice(), short_arena.as_mut_slice()).unwrap_err(),
        Error::Arg(ArgFault::Arena)
    );

    let mut exact_arena = vec![0xFFu8; needed];
    let tables = load(empty_blob.as_slice(), exact_arena.as_mut_slice()).expect("load valid");
    assert_eq!(tables.header().blob_len, HEADER_LEN as u32);
    let (b, a) = tables.storage();
    assert_eq!(b.len(), HEADER_LEN);
    assert_eq!(a.len(), needed);
    let (b2, a2) = tables.into_parts();
    assert_eq!(b2.len(), HEADER_LEN);
    assert_eq!(a2.len(), needed);
    assert!(a2.iter().all(|&byte| byte == 0));

    let mut bigger_arena = vec![0xAAu8; needed + 32];
    let tables_big = load(empty_blob.as_slice(), bigger_arena.as_mut_slice()).expect("load big");
    let (_, a_big) = tables_big.into_parts();
    assert!(a_big[..needed].iter().all(|&byte| byte == 0));
    assert!(a_big[needed..].iter().all(|&byte| byte == 0xAA));
}

#[test]
fn tables_is_send_and_sync_and_error_display() {
    fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<Tables<Box<[u8]>, Box<[u8]>>>();
    assert_send_sync::<Tables<&'static [u8], &'static mut [u8]>>();

    let err_abi = Error::Abi;
    assert_eq!(err_abi.rule(), Some(3));
    assert_eq!(format!("{err_abi}"), format!("{err_abi:?}"));

    let err_cap = Error::Bundle(BundleFault::EvalCap);
    assert_eq!(err_cap.rule(), None);
    assert_eq!(format!("{err_cap}"), format!("{err_cap:?}"));

    let err_state = Error::State;
    assert_eq!(err_state.rule(), None);
    let err_changed = Error::Changed;
    assert_eq!(err_changed.rule(), None);
    let err_arg = Error::Arg(ArgFault::Arena);
    assert_eq!(err_arg.rule(), None);

    let _: &dyn core::error::Error = &err_abi;
}
