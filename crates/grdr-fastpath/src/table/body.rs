// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use crate::layout::{
    ExeEntry, FLOOR_ROW_SIZE, FloorRow, HEADER_LEN, HOST_KIND_ANY, HOST_KIND_EXACT_NAME,
    HOST_KIND_IPV4_BLOCK, HOST_KIND_IPV6_BLOCK, HOST_KIND_WILDCARD_NAME, Header, HostEntry,
    MAX_ACTION_CLASS_BITS, OUTCOME_DENY, OUTCOME_STEP_UP, PROCESS_KIND_EXE_DIGEST,
    PROCESS_KIND_EXE_PATH_PATTERN, PROCESS_KIND_PACKAGE_ID, PROCESS_KIND_SIGNING_ID, PathEntry,
    PortRange, ProcessScopeEntry, ReasonEntry, Section,
};

use super::strings::validate_pool_and_strings;
use super::{Error, section_bytes};

use crate::layout::Record;

pub(super) fn validate_body(blob: &[u8], header: &Header) -> Result<(), Error> {
    validate_inter_section_padding(blob, header)?;
    validate_record_kinds(blob, header)?;
    validate_record_padding_and_unused(blob, header)?;
    validate_pool_and_strings(blob, header)?;
    validate_port_ranges(blob, header)?;
    validate_classifier_classes(blob, header)?;
    validate_exe_and_proc_digests(blob, header)?;
    validate_floor_rows(blob, header)?;
    validate_reason_order(blob, header)?;
    Ok(())
}

pub(super) fn write_arena_index(
    blob: &[u8],
    header: &Header,
    arena: &mut [u8],
    needed_arena: usize,
) -> Result<(), Error> {
    let target = arena
        .get_mut(..needed_arena)
        .ok_or(Error::Arg(super::ArgFault::Arena))?;

    let mut row_iter = section_bytes(blob, header, Section::FloorRows)
        .as_chunks::<FLOOR_ROW_SIZE>()
        .0
        .iter()
        .map(FloorRow::decode)
        .peekable();
    let mut row_cursor: u32 = 0;

    let mut slots = target.as_chunks_mut::<8>().0.iter_mut();
    let Some(slot0) = slots.next() else {
        return Err(Error::Arg(super::ArgFault::Arena));
    };
    *slot0 = [0u8; 8];

    for class in 1..=header.action_class_count {
        let Some(slot) = slots.next() else {
            return Err(Error::Arg(super::ArgFault::Arena));
        };
        let start = row_cursor;
        while let Some(row) = row_iter.peek() {
            if row.action_class != class {
                break;
            }
            row_iter.next();
            row_cursor = row_cursor
                .checked_add(1)
                .ok_or_else(|| Error::from_tv_rule(27))?;
        }
        let count = row_cursor
            .checked_sub(start)
            .ok_or_else(|| Error::from_tv_rule(27))?;
        write_slot(slot, start, count);
    }

    Ok(())
}

fn write_slot(slot: &mut [u8; 8], start: u32, count: u32) {
    let [s0, s1, s2, s3] = start.to_le_bytes();
    let [c0, c1, c2, c3] = count.to_le_bytes();
    *slot = [s0, s1, s2, s3, c0, c1, c2, c3];
}

fn validate_inter_section_padding(blob: &[u8], header: &Header) -> Result<(), Error> {
    let mut cursor = HEADER_LEN;
    for section in Section::ALL {
        let entry = header.section_entry(section);
        if entry.count == 0 {
            continue;
        }
        let start = usize::try_from(entry.offset).map_err(|_| Error::from_tv_rule(15))?;
        let gap = blob
            .get(cursor..start)
            .ok_or_else(|| Error::from_tv_rule(15))?;
        if gap.iter().any(|&b| b != 0) {
            return Err(Error::from_tv_rule(15));
        }
        let rec_len = usize::try_from(entry.count)
            .ok()
            .and_then(|c| c.checked_mul(section.record_size()))
            .ok_or_else(|| Error::from_tv_rule(15))?;
        cursor = start
            .checked_add(rec_len)
            .ok_or_else(|| Error::from_tv_rule(15))?;
    }
    let tail = blob.get(cursor..).ok_or_else(|| Error::from_tv_rule(15))?;
    if tail.iter().any(|&b| b != 0) {
        return Err(Error::from_tv_rule(15));
    }
    Ok(())
}

fn validate_record_kinds(blob: &[u8], header: &Header) -> Result<(), Error> {
    for section in [Section::HostClassifier, Section::InterestHosts] {
        for chunk in section_bytes(blob, header, section)
            .as_chunks::<{ HostEntry::SIZE }>()
            .0
        {
            let entry = HostEntry::decode(chunk);
            if !(HOST_KIND_EXACT_NAME..=HOST_KIND_ANY).contains(&entry.kind) {
                return Err(Error::from_tv_rule(16));
            }
        }
    }

    for chunk in section_bytes(blob, header, Section::ProcessScope)
        .as_chunks::<{ ProcessScopeEntry::SIZE }>()
        .0
    {
        let entry = ProcessScopeEntry::decode(chunk);
        if !(PROCESS_KIND_EXE_DIGEST..=PROCESS_KIND_PACKAGE_ID).contains(&entry.kind) {
            return Err(Error::from_tv_rule(16));
        }
    }
    Ok(())
}

fn validate_record_padding_and_unused(blob: &[u8], header: &Header) -> Result<(), Error> {
    for chunk in section_bytes(blob, header, Section::PathClassifier)
        .as_chunks::<{ PathEntry::SIZE }>()
        .0
    {
        if chunk.get(13..16) != Some(&[0, 0, 0]) {
            return Err(Error::from_tv_rule(17));
        }
    }

    for chunk in section_bytes(blob, header, Section::HostClassifier)
        .as_chunks::<{ HostEntry::SIZE }>()
        .0
    {
        if !host_record_unused_zero(chunk, false) {
            return Err(Error::from_tv_rule(17));
        }
    }

    for chunk in section_bytes(blob, header, Section::ProcessScope)
        .as_chunks::<{ ProcessScopeEntry::SIZE }>()
        .0
    {
        if !process_scope_unused_zero(chunk) {
            return Err(Error::from_tv_rule(17));
        }
    }

    for chunk in section_bytes(blob, header, Section::InterestPaths)
        .as_chunks::<{ PathEntry::SIZE }>()
        .0
    {
        if chunk.get(12..16) != Some(&[0, 0, 0, 0]) {
            return Err(Error::from_tv_rule(17));
        }
    }

    for chunk in section_bytes(blob, header, Section::InterestHosts)
        .as_chunks::<{ HostEntry::SIZE }>()
        .0
    {
        if !host_record_unused_zero(chunk, true) {
            return Err(Error::from_tv_rule(17));
        }
    }

    for chunk in section_bytes(blob, header, Section::ReasonTable)
        .as_chunks::<{ ReasonEntry::SIZE }>()
        .0
    {
        if chunk.get(12..16) != Some(&[0, 0, 0, 0]) {
            return Err(Error::from_tv_rule(17));
        }
    }

    Ok(())
}

fn host_record_unused_zero(chunk: &[u8; HostEntry::SIZE], is_interest: bool) -> bool {
    let entry = HostEntry::decode(chunk);
    if is_interest && entry.class_mask != 0 {
        return false;
    }
    if chunk.get(20..24) != Some(&[0, 0, 0, 0]) {
        return false;
    }
    match entry.kind {
        HOST_KIND_EXACT_NAME | HOST_KIND_WILDCARD_NAME => {
            entry.prefix_len == 0 && entry.addr == [0; 16]
        }
        HOST_KIND_IPV4_BLOCK | HOST_KIND_IPV6_BLOCK => entry.name_len == 0 && entry.name_off == 0,
        HOST_KIND_ANY => {
            entry.name_len == 0
                && entry.name_off == 0
                && entry.prefix_len == 0
                && entry.addr == [0; 16]
        }
        _ => false,
    }
}

fn process_scope_unused_zero(chunk: &[u8; ProcessScopeEntry::SIZE]) -> bool {
    let entry = ProcessScopeEntry::decode(chunk);
    if chunk.get(13..16) != Some(&[0, 0, 0]) {
        return false;
    }
    match entry.kind {
        PROCESS_KIND_EXE_DIGEST => {
            entry.utf8_off == 0
                && entry.utf16_off == 0
                && entry.utf8_len == 0
                && entry.utf16_len == 0
        }
        PROCESS_KIND_EXE_PATH_PATTERN | PROCESS_KIND_SIGNING_ID | PROCESS_KIND_PACKAGE_ID => {
            entry.digest == [0; 32]
        }
        _ => false,
    }
}

fn validate_port_ranges(blob: &[u8], header: &Header) -> Result<(), Error> {
    for section in [Section::HostClassifier, Section::InterestHosts] {
        for chunk in section_bytes(blob, header, section)
            .as_chunks::<{ HostEntry::SIZE }>()
            .0
        {
            let entry = HostEntry::decode(chunk);
            if entry.port_lo > entry.port_hi {
                return Err(Error::from_tv_rule(23));
            }
        }
    }

    for chunk in section_bytes(blob, header, Section::InterestPorts)
        .as_chunks::<{ PortRange::SIZE }>()
        .0
    {
        let entry = PortRange::decode(chunk);
        if entry.port_lo > entry.port_hi {
            return Err(Error::from_tv_rule(23));
        }
    }
    Ok(())
}

fn validate_classifier_classes(blob: &[u8], header: &Header) -> Result<(), Error> {
    let max_bit = u8::try_from(MAX_ACTION_CLASS_BITS).map_err(|_| Error::from_tv_rule(24))?;
    for chunk in section_bytes(blob, header, Section::PathClassifier)
        .as_chunks::<{ PathEntry::SIZE }>()
        .0
    {
        let entry = PathEntry::decode(chunk);
        if entry.class_bit > max_bit {
            return Err(Error::from_tv_rule(24));
        }
    }
    for chunk in section_bytes(blob, header, Section::HostClassifier)
        .as_chunks::<{ HostEntry::SIZE }>()
        .0
    {
        let entry = HostEntry::decode(chunk);
        if entry.class_mask == 0 {
            return Err(Error::from_tv_rule(24));
        }
    }
    for chunk in section_bytes(blob, header, Section::ExeClassifier)
        .as_chunks::<{ ExeEntry::SIZE }>()
        .0
    {
        let entry = ExeEntry::decode(chunk);
        if entry.class_mask == 0 {
            return Err(Error::from_tv_rule(24));
        }
    }
    Ok(())
}

fn validate_exe_and_proc_digests(blob: &[u8], header: &Header) -> Result<(), Error> {
    let mut prev: Option<[u8; 32]> = None;
    for chunk in section_bytes(blob, header, Section::ExeClassifier)
        .as_chunks::<{ ExeEntry::SIZE }>()
        .0
    {
        let entry = ExeEntry::decode(chunk);
        if entry.digest == [0; 32] {
            return Err(Error::from_tv_rule(25));
        }
        if let Some(p) = prev
            && p >= entry.digest
        {
            return Err(Error::from_tv_rule(25));
        }
        prev = Some(entry.digest);
    }

    for chunk in section_bytes(blob, header, Section::ProcessScope)
        .as_chunks::<{ ProcessScopeEntry::SIZE }>()
        .0
    {
        let entry = ProcessScopeEntry::decode(chunk);
        if entry.kind == PROCESS_KIND_EXE_DIGEST && entry.digest == [0; 32] {
            return Err(Error::from_tv_rule(25));
        }
    }
    Ok(())
}

fn validate_floor_rows(blob: &[u8], header: &Header) -> Result<(), Error> {
    let floor_chunks = section_bytes(blob, header, Section::FloorRows)
        .as_chunks::<FLOOR_ROW_SIZE>()
        .0;
    let reason_count = header.section_entry(Section::ReasonTable).count;

    for chunk in floor_chunks {
        let row = FloorRow::decode(chunk);
        if row.action_class == 0 || row.action_class > header.action_class_count {
            return Err(Error::from_tv_rule(26));
        }
        let bit = 1u64
            .checked_shl(u32::from(row.action_class))
            .ok_or_else(|| Error::from_tv_rule(26))?;
        if (header.loss_closed_classes & bit) == 0 {
            return Err(Error::from_tv_rule(26));
        }
    }

    let mut prev_key: Option<(u16, u32, [u8; FLOOR_ROW_SIZE])> = None;
    for raw in floor_chunks {
        let row = FloorRow::decode(raw);
        let key = (row.action_class, row.reason, *raw);
        if let Some(prev) = prev_key
            && prev >= key
        {
            return Err(Error::from_tv_rule(27));
        }
        prev_key = Some(key);
    }

    for chunk in floor_chunks {
        let row = FloorRow::decode(chunk);
        if row.principal_kind > header.principal_kind_count {
            return Err(Error::from_tv_rule(28));
        }
    }

    for chunk in floor_chunks {
        let row = FloorRow::decode(chunk);
        if row.outcome != OUTCOME_DENY && row.outcome != OUTCOME_STEP_UP {
            return Err(Error::from_tv_rule(29));
        }
    }

    for chunk in floor_chunks {
        let row = FloorRow::decode(chunk);
        if row.reason >= reason_count {
            return Err(Error::from_tv_rule(30));
        }
    }

    for chunk in floor_chunks {
        let row = FloorRow::decode(chunk);
        if (row.required_labels & row.forbidden_labels) != 0 {
            return Err(Error::from_tv_rule(31));
        }
    }

    let reachable_classes = reachable_resource_classes(blob, header)?;
    for chunk in floor_chunks {
        let row = FloorRow::decode(chunk);
        if (row.resource_classes & !reachable_classes) != 0 {
            return Err(Error::from_tv_rule(32));
        }
    }

    Ok(())
}

fn reachable_resource_classes(blob: &[u8], header: &Header) -> Result<u64, Error> {
    let mut reachable = 0u64;
    for chunk in section_bytes(blob, header, Section::PathClassifier)
        .as_chunks::<{ PathEntry::SIZE }>()
        .0
    {
        let entry = PathEntry::decode(chunk);
        let bit = 1u64
            .checked_shl(u32::from(entry.class_bit))
            .ok_or_else(|| Error::from_tv_rule(32))?;
        reachable |= bit;
    }
    for chunk in section_bytes(blob, header, Section::HostClassifier)
        .as_chunks::<{ HostEntry::SIZE }>()
        .0
    {
        let entry = HostEntry::decode(chunk);
        reachable |= entry.class_mask;
    }
    for chunk in section_bytes(blob, header, Section::ExeClassifier)
        .as_chunks::<{ ExeEntry::SIZE }>()
        .0
    {
        let entry = ExeEntry::decode(chunk);
        reachable |= entry.class_mask;
    }
    Ok(reachable)
}

fn validate_reason_order(blob: &[u8], header: &Header) -> Result<(), Error> {
    let pool = section_bytes(blob, header, Section::StringPool);
    let mut prev: Option<&[u8]> = None;
    for chunk in section_bytes(blob, header, Section::ReasonTable)
        .as_chunks::<{ ReasonEntry::SIZE }>()
        .0
    {
        let entry = ReasonEntry::decode(chunk);
        let start = usize::try_from(entry.rule_off).map_err(|_| Error::from_tv_rule(33))?;
        let end = start
            .checked_add(usize::from(entry.rule_len))
            .ok_or_else(|| Error::from_tv_rule(33))?;
        let rule_id = pool
            .get(start..end)
            .ok_or_else(|| Error::from_tv_rule(33))?;
        if let Some(p) = prev
            && p >= rule_id
        {
            return Err(Error::from_tv_rule(33));
        }
        prev = Some(rule_id);
    }
    Ok(())
}
