// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use crate::layout::{
    HOST_KIND_EXACT_NAME, HOST_KIND_IPV4_BLOCK, HOST_KIND_IPV6_BLOCK, HOST_KIND_WILDCARD_NAME,
    Header, HostEntry, NAME_MAX_BYTES, PROCESS_KIND_EXE_PATH_PATTERN, PROCESS_KIND_PACKAGE_ID,
    PROCESS_KIND_SIGNING_ID, PathEntry, ProcessScopeEntry, ReasonEntry, Record, Section,
};

use super::{Error, section_bytes};

const V4_MAPPED_PREFIX: [u8; 12] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xFF, 0xFF];
const NAT64_WKP_PREFIX: [u8; 12] = [0x00, 0x64, 0xFF, 0x9B, 0, 0, 0, 0, 0, 0, 0, 0];
const HOST_LABEL_MAX_BYTES: usize = 63;

pub(super) fn validate_pool_and_strings(blob: &[u8], header: &Header) -> Result<(), Error> {
    let pool = section_bytes(blob, header, Section::StringPool);
    validate_pool_tiling(blob, header, pool)?;
    validate_string_chars(blob, header, pool)?;
    validate_path_patterns(blob, header, pool)?;
    validate_host_names(blob, header, pool)?;
    validate_address_blocks(blob, header)?;
    Ok(())
}

fn validate_pool_tiling(blob: &[u8], header: &Header, pool: &[u8]) -> Result<(), Error> {
    let mut cursor: usize = 0;

    for chunk in section_bytes(blob, header, Section::PathClassifier)
        .as_chunks::<{ PathEntry::SIZE }>()
        .0
    {
        let entry = PathEntry::decode(chunk);
        take_utf8(&mut cursor, pool, entry.utf8_off, entry.utf8_len)?;
        take_utf16le(&mut cursor, pool, entry.utf16_off, entry.utf16_len)?;
    }

    for chunk in section_bytes(blob, header, Section::HostClassifier)
        .as_chunks::<{ HostEntry::SIZE }>()
        .0
    {
        let entry = HostEntry::decode(chunk);
        if entry.kind == HOST_KIND_EXACT_NAME || entry.kind == HOST_KIND_WILDCARD_NAME {
            take_utf8(&mut cursor, pool, entry.name_off, entry.name_len)?;
        }
    }

    for chunk in section_bytes(blob, header, Section::ProcessScope)
        .as_chunks::<{ ProcessScopeEntry::SIZE }>()
        .0
    {
        let entry = ProcessScopeEntry::decode(chunk);
        if matches!(
            entry.kind,
            PROCESS_KIND_EXE_PATH_PATTERN | PROCESS_KIND_SIGNING_ID | PROCESS_KIND_PACKAGE_ID
        ) {
            take_utf8(&mut cursor, pool, entry.utf8_off, entry.utf8_len)?;
            take_utf16le(&mut cursor, pool, entry.utf16_off, entry.utf16_len)?;
        }
    }

    for chunk in section_bytes(blob, header, Section::InterestPaths)
        .as_chunks::<{ PathEntry::SIZE }>()
        .0
    {
        let entry = PathEntry::decode(chunk);
        take_utf8(&mut cursor, pool, entry.utf8_off, entry.utf8_len)?;
        take_utf16le(&mut cursor, pool, entry.utf16_off, entry.utf16_len)?;
    }

    for chunk in section_bytes(blob, header, Section::InterestHosts)
        .as_chunks::<{ HostEntry::SIZE }>()
        .0
    {
        let entry = HostEntry::decode(chunk);
        if entry.kind == HOST_KIND_EXACT_NAME || entry.kind == HOST_KIND_WILDCARD_NAME {
            take_utf8(&mut cursor, pool, entry.name_off, entry.name_len)?;
        }
    }

    for chunk in section_bytes(blob, header, Section::ReasonTable)
        .as_chunks::<{ ReasonEntry::SIZE }>()
        .0
    {
        let entry = ReasonEntry::decode(chunk);
        take_utf8(&mut cursor, pool, entry.reason_off, entry.reason_len)?;
        take_utf8(&mut cursor, pool, entry.rule_off, entry.rule_len)?;
    }

    if cursor != pool.len() {
        return Err(Error::from_tv_rule(18));
    }
    Ok(())
}

fn take_utf8(cursor: &mut usize, pool: &[u8], off: u32, len: u16) -> Result<(), Error> {
    if len == 0 || usize::try_from(off).ok() != Some(*cursor) {
        return Err(Error::from_tv_rule(18));
    }
    let end = cursor
        .checked_add(usize::from(len))
        .ok_or_else(|| Error::from_tv_rule(18))?;
    if end > pool.len() {
        return Err(Error::from_tv_rule(18));
    }
    *cursor = end;
    Ok(())
}

fn take_utf16le(cursor: &mut usize, pool: &[u8], off: u32, units: u16) -> Result<(), Error> {
    if units == 0 {
        return Err(Error::from_tv_rule(18));
    }
    if (*cursor & 1) == 1 {
        if pool.get(*cursor).copied() != Some(0) {
            return Err(Error::from_tv_rule(18));
        }
        *cursor = cursor
            .checked_add(1)
            .ok_or_else(|| Error::from_tv_rule(18))?;
    }
    if usize::try_from(off).ok() != Some(*cursor) {
        return Err(Error::from_tv_rule(18));
    }
    let byte_len = usize::from(units)
        .checked_mul(2)
        .ok_or_else(|| Error::from_tv_rule(18))?;
    let end = cursor
        .checked_add(byte_len)
        .ok_or_else(|| Error::from_tv_rule(18))?;
    if end > pool.len() {
        return Err(Error::from_tv_rule(18));
    }
    *cursor = end;
    Ok(())
}

fn validate_string_chars(blob: &[u8], header: &Header, pool: &[u8]) -> Result<(), Error> {
    for section in [Section::PathClassifier, Section::InterestPaths] {
        for chunk in section_bytes(blob, header, section)
            .as_chunks::<{ PathEntry::SIZE }>()
            .0
        {
            let entry = PathEntry::decode(chunk);
            check_utf8_utf16_pair(
                pool,
                entry.utf8_off,
                entry.utf8_len,
                entry.utf16_off,
                entry.utf16_len,
            )?;
        }
    }

    for section in [Section::HostClassifier, Section::InterestHosts] {
        for chunk in section_bytes(blob, header, section)
            .as_chunks::<{ HostEntry::SIZE }>()
            .0
        {
            let entry = HostEntry::decode(chunk);
            if entry.kind == HOST_KIND_EXACT_NAME || entry.kind == HOST_KIND_WILDCARD_NAME {
                let bytes = pool_slice(pool, entry.name_off, usize::from(entry.name_len))
                    .ok_or_else(|| Error::from_tv_rule(19))?;
                if core::str::from_utf8(bytes).is_err() {
                    return Err(Error::from_tv_rule(19));
                }
            }
        }
    }

    for chunk in section_bytes(blob, header, Section::ProcessScope)
        .as_chunks::<{ ProcessScopeEntry::SIZE }>()
        .0
    {
        let entry = ProcessScopeEntry::decode(chunk);
        if matches!(
            entry.kind,
            PROCESS_KIND_EXE_PATH_PATTERN | PROCESS_KIND_SIGNING_ID | PROCESS_KIND_PACKAGE_ID
        ) {
            let text = check_utf8_utf16_pair(
                pool,
                entry.utf8_off,
                entry.utf8_len,
                entry.utf16_off,
                entry.utf16_len,
            )?;
            if (entry.kind == PROCESS_KIND_SIGNING_ID || entry.kind == PROCESS_KIND_PACKAGE_ID)
                && text.chars().any(is_disallowed_identity_char)
            {
                return Err(Error::from_tv_rule(19));
            }
        }
    }

    for chunk in section_bytes(blob, header, Section::ReasonTable)
        .as_chunks::<{ ReasonEntry::SIZE }>()
        .0
    {
        let entry = ReasonEntry::decode(chunk);
        let reason = pool_slice(pool, entry.reason_off, usize::from(entry.reason_len))
            .ok_or_else(|| Error::from_tv_rule(19))?;
        let rule = pool_slice(pool, entry.rule_off, usize::from(entry.rule_len))
            .ok_or_else(|| Error::from_tv_rule(19))?;
        if !is_visible_ascii(reason) || !is_visible_ascii(rule) {
            return Err(Error::from_tv_rule(19));
        }
    }

    Ok(())
}

fn check_utf8_utf16_pair(
    pool: &[u8],
    utf8_off: u32,
    utf8_len: u16,
    utf16_off: u32,
    utf16_len: u16,
) -> Result<&str, Error> {
    let bytes8 =
        pool_slice(pool, utf8_off, usize::from(utf8_len)).ok_or_else(|| Error::from_tv_rule(19))?;
    let text = core::str::from_utf8(bytes8).map_err(|_| Error::from_tv_rule(19))?;
    let byte_len16 = usize::from(utf16_len)
        .checked_mul(2)
        .ok_or_else(|| Error::from_tv_rule(19))?;
    let bytes16 = pool_slice(pool, utf16_off, byte_len16).ok_or_else(|| Error::from_tv_rule(19))?;
    let mut utf16_units = bytes16
        .as_chunks::<2>()
        .0
        .iter()
        .copied()
        .map(u16::from_le_bytes);
    if !text.encode_utf16().eq(&mut utf16_units) {
        return Err(Error::from_tv_rule(19));
    }
    Ok(text)
}

fn validate_path_patterns(blob: &[u8], header: &Header, pool: &[u8]) -> Result<(), Error> {
    for section in [Section::PathClassifier, Section::InterestPaths] {
        for chunk in section_bytes(blob, header, section)
            .as_chunks::<{ PathEntry::SIZE }>()
            .0
        {
            let entry = PathEntry::decode(chunk);
            check_path_pattern_bytes(pool, entry.utf8_off, entry.utf8_len)?;
        }
    }

    for chunk in section_bytes(blob, header, Section::ProcessScope)
        .as_chunks::<{ ProcessScopeEntry::SIZE }>()
        .0
    {
        let entry = ProcessScopeEntry::decode(chunk);
        if entry.kind == PROCESS_KIND_EXE_PATH_PATTERN {
            check_path_pattern_bytes(pool, entry.utf8_off, entry.utf8_len)?;
        }
    }

    Ok(())
}

fn check_path_pattern_bytes(pool: &[u8], off: u32, len: u16) -> Result<(), Error> {
    let bytes = pool_slice(pool, off, usize::from(len)).ok_or_else(|| Error::from_tv_rule(20))?;
    let text = core::str::from_utf8(bytes).map_err(|_| Error::from_tv_rule(20))?;
    if !is_valid_path_pattern(text) {
        return Err(Error::from_tv_rule(20));
    }
    Ok(())
}

fn is_valid_path_pattern(pattern: &str) -> bool {
    let (starts_slash, rest) = match pattern.strip_prefix('/') {
        Some(tail) => (true, tail),
        None => (false, pattern),
    };
    let mut segments = rest.split('/');
    let Some(first) = segments.next() else {
        return false;
    };
    if !starts_slash && first != "**" {
        return false;
    }
    if !is_valid_segment(first) {
        return false;
    }
    for seg in segments {
        if !is_valid_segment(seg) {
            return false;
        }
    }
    true
}

fn is_valid_segment(seg: &str) -> bool {
    if seg.is_empty() || seg == "." || seg == ".." {
        return false;
    }
    if seg == "**" {
        return true;
    }
    let bytes = seg.as_bytes();
    let mut i: usize = 0;
    while let Some(&b) = bytes.get(i) {
        if b == b'\\' {
            let Some(next_idx) = i.checked_add(1) else {
                return false;
            };
            let Some(&next) = bytes.get(next_idx) else {
                return false;
            };
            if !matches!(next, b'*' | b'?' | b'\\') {
                return false;
            }
            let Some(step) = i.checked_add(2) else {
                return false;
            };
            i = step;
        } else if b == b'*' {
            if let Some(next_idx) = i.checked_add(1)
                && bytes.get(next_idx) == Some(&b'*')
            {
                return false;
            }
            let Some(step) = i.checked_add(1) else {
                return false;
            };
            i = step;
        } else {
            let Some(step) = i.checked_add(1) else {
                return false;
            };
            i = step;
        }
    }
    true
}

fn validate_host_names(blob: &[u8], header: &Header, pool: &[u8]) -> Result<(), Error> {
    for section in [Section::HostClassifier, Section::InterestHosts] {
        for chunk in section_bytes(blob, header, section)
            .as_chunks::<{ HostEntry::SIZE }>()
            .0
        {
            let entry = HostEntry::decode(chunk);
            if entry.kind == HOST_KIND_EXACT_NAME || entry.kind == HOST_KIND_WILDCARD_NAME {
                let bytes = pool_slice(pool, entry.name_off, usize::from(entry.name_len))
                    .ok_or_else(|| Error::from_tv_rule(21))?;
                if !is_canonical_host_name(bytes) {
                    return Err(Error::from_tv_rule(21));
                }
            }
        }
    }
    Ok(())
}

fn is_canonical_host_name(bytes: &[u8]) -> bool {
    if bytes.is_empty() || bytes.len() > NAME_MAX_BYTES {
        return false;
    }
    let mut last_label: &[u8] = &[];
    for label in bytes.split(|&b| b == b'.') {
        if !is_valid_host_label(label) {
            return false;
        }
        last_label = label;
    }
    if last_label.iter().all(u8::is_ascii_digit) {
        return false;
    }
    if let Some(rest) = last_label.strip_prefix(b"0x")
        && !rest.is_empty()
        && rest.iter().all(|&b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
    {
        return false;
    }
    true
}

fn is_valid_host_label(label: &[u8]) -> bool {
    if label.is_empty() || label.len() > HOST_LABEL_MAX_BYTES {
        return false;
    }
    if label.first() == Some(&b'-') || label.last() == Some(&b'-') {
        return false;
    }
    label
        .iter()
        .all(|&b| matches!(b, b'a'..=b'z' | b'0'..=b'9' | b'-'))
}

fn validate_address_blocks(blob: &[u8], header: &Header) -> Result<(), Error> {
    for section in [Section::HostClassifier, Section::InterestHosts] {
        for chunk in section_bytes(blob, header, section)
            .as_chunks::<{ HostEntry::SIZE }>()
            .0
        {
            let entry = HostEntry::decode(chunk);
            if entry.kind == HOST_KIND_IPV4_BLOCK && !is_valid_ipv4_block(&entry) {
                return Err(Error::from_tv_rule(22));
            }
            if entry.kind == HOST_KIND_IPV6_BLOCK && !is_valid_ipv6_block(&entry) {
                return Err(Error::from_tv_rule(22));
            }
        }
    }
    Ok(())
}

fn is_valid_ipv4_block(entry: &HostEntry) -> bool {
    if entry.prefix_len > 32 {
        return false;
    }
    let Some(tail) = entry.addr.get(4..16) else {
        return false;
    };
    if tail.iter().any(|&b| b != 0) {
        return false;
    }
    let Some(v4_bytes) = entry.addr.first_chunk::<4>() else {
        return false;
    };
    let ip = u32::from_be_bytes(*v4_bytes);
    let host_mask = if entry.prefix_len == 32 {
        0
    } else {
        u32::MAX
            .checked_shr(u32::from(entry.prefix_len))
            .unwrap_or(0)
    };
    (ip & host_mask) == 0
}

fn is_valid_ipv6_block(entry: &HostEntry) -> bool {
    if entry.prefix_len > 128 {
        return false;
    }
    let ip = u128::from_be_bytes(entry.addr);
    let host_mask = if entry.prefix_len == 128 {
        0
    } else {
        u128::MAX
            .checked_shr(u32::from(entry.prefix_len))
            .unwrap_or(0)
    };
    if (ip & host_mask) != 0 {
        return false;
    }
    if entry.prefix_len >= 96
        && let Some(prefix96) = entry.addr.first_chunk::<12>()
        && (*prefix96 == V4_MAPPED_PREFIX || *prefix96 == NAT64_WKP_PREFIX)
    {
        return false;
    }
    true
}

fn is_disallowed_identity_char(ch: char) -> bool {
    matches!(
        ch,
        '\u{0000}'..='\u{001F}'
            | '\u{007F}'..='\u{009F}'
            | '\u{061C}'
            | '\u{200E}'..='\u{200F}'
            | '\u{202A}'..='\u{202E}'
            | '\u{2066}'..='\u{2069}'
    )
}

fn is_visible_ascii(bytes: &[u8]) -> bool {
    bytes.iter().all(|&b| (b'!'..=b'~').contains(&b))
}

fn pool_slice(pool: &[u8], off: u32, len: usize) -> Option<&[u8]> {
    let start = usize::try_from(off).ok()?;
    let end = start.checked_add(len)?;
    pool.get(start..end)
}
