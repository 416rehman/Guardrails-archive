// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use super::reader::{section_records, section_slice, u8_at, u16_le, u32_le};

pub fn tv18(blob: &[u8]) -> Result<(), u8> {
    let pool = section_slice(blob, 9);
    let mut pos: usize = 0;

    for rec in section_records(blob, 1) {
        take_utf8(
            &mut pos,
            pool,
            u32_le(rec, 0).ok_or(18u8)?,
            u16_le(rec, 8).ok_or(18u8)?,
        )?;
        take_utf16(
            &mut pos,
            pool,
            u32_le(rec, 4).ok_or(18u8)?,
            u16_le(rec, 10).ok_or(18u8)?,
        )?;
    }
    for rec in section_records(blob, 2) {
        let kind = u8_at(rec, 8).ok_or(18u8)?;
        if kind == 1 || kind == 2 {
            take_utf8(
                &mut pos,
                pool,
                u32_le(rec, 16).ok_or(18u8)?,
                u16_le(rec, 14).ok_or(18u8)?,
            )?;
        }
    }
    for rec in section_records(blob, 4) {
        let kind = u8_at(rec, 12).ok_or(18u8)?;
        if (2..=4).contains(&kind) {
            take_utf8(
                &mut pos,
                pool,
                u32_le(rec, 0).ok_or(18u8)?,
                u16_le(rec, 8).ok_or(18u8)?,
            )?;
            take_utf16(
                &mut pos,
                pool,
                u32_le(rec, 4).ok_or(18u8)?,
                u16_le(rec, 10).ok_or(18u8)?,
            )?;
        }
    }
    for rec in section_records(blob, 5) {
        take_utf8(
            &mut pos,
            pool,
            u32_le(rec, 0).ok_or(18u8)?,
            u16_le(rec, 8).ok_or(18u8)?,
        )?;
        take_utf16(
            &mut pos,
            pool,
            u32_le(rec, 4).ok_or(18u8)?,
            u16_le(rec, 10).ok_or(18u8)?,
        )?;
    }
    for rec in section_records(blob, 6) {
        let kind = u8_at(rec, 8).ok_or(18u8)?;
        if kind == 1 || kind == 2 {
            take_utf8(
                &mut pos,
                pool,
                u32_le(rec, 16).ok_or(18u8)?,
                u16_le(rec, 14).ok_or(18u8)?,
            )?;
        }
    }
    for rec in section_records(blob, 8) {
        take_utf8(
            &mut pos,
            pool,
            u32_le(rec, 0).ok_or(18u8)?,
            u16_le(rec, 8).ok_or(18u8)?,
        )?;
        take_utf8(
            &mut pos,
            pool,
            u32_le(rec, 4).ok_or(18u8)?,
            u16_le(rec, 10).ok_or(18u8)?,
        )?;
    }

    if pos != pool.len() {
        return Err(18);
    }
    Ok(())
}

pub fn tv19(blob: &[u8]) -> Result<(), u8> {
    let pool = section_slice(blob, 9);

    for rec in section_records(blob, 1).chain(section_records(blob, 5)) {
        let s8 = pool_utf8(
            pool,
            u32_le(rec, 0).ok_or(19u8)?,
            u16_le(rec, 8).ok_or(19u8)?,
        )
        .ok_or(19u8)?;
        let s16 = pool_utf16(
            pool,
            u32_le(rec, 4).ok_or(19u8)?,
            u16_le(rec, 10).ok_or(19u8)?,
        )
        .ok_or(19u8)?;
        if s8 != s16 {
            return Err(19);
        }
    }

    for rec in section_records(blob, 2).chain(section_records(blob, 6)) {
        let kind = u8_at(rec, 8).ok_or(19u8)?;
        if kind == 1 || kind == 2 {
            let _ = pool_utf8(
                pool,
                u32_le(rec, 16).ok_or(19u8)?,
                u16_le(rec, 14).ok_or(19u8)?,
            )
            .ok_or(19u8)?;
        }
    }

    for rec in section_records(blob, 4) {
        let kind = u8_at(rec, 12).ok_or(19u8)?;
        if (2..=4).contains(&kind) {
            let s8 = pool_utf8(
                pool,
                u32_le(rec, 0).ok_or(19u8)?,
                u16_le(rec, 8).ok_or(19u8)?,
            )
            .ok_or(19u8)?;
            let s16 = pool_utf16(
                pool,
                u32_le(rec, 4).ok_or(19u8)?,
                u16_le(rec, 10).ok_or(19u8)?,
            )
            .ok_or(19u8)?;
            if s8 != s16 {
                return Err(19);
            }
            if (kind == 3 || kind == 4) && s8.chars().any(is_disallowed_identity_char) {
                return Err(19);
            }
        }
    }

    for rec in section_records(blob, 8) {
        let reason = pool_bytes(
            pool,
            u32_le(rec, 0).ok_or(19u8)?,
            u16_le(rec, 8).ok_or(19u8)?,
        )
        .ok_or(19u8)?;
        let rule = pool_bytes(
            pool,
            u32_le(rec, 4).ok_or(19u8)?,
            u16_le(rec, 10).ok_or(19u8)?,
        )
        .ok_or(19u8)?;
        if reason.iter().any(|&b| !(b'!'..=b'~').contains(&b))
            || rule.iter().any(|&b| !(b'!'..=b'~').contains(&b))
        {
            return Err(19);
        }
    }

    Ok(())
}

pub fn tv20(blob: &[u8]) -> Result<(), u8> {
    let pool = section_slice(blob, 9);
    for rec in section_records(blob, 1).chain(section_records(blob, 5)) {
        let pattern = pool_utf8(
            pool,
            u32_le(rec, 0).ok_or(20u8)?,
            u16_le(rec, 8).ok_or(20u8)?,
        )
        .ok_or(20u8)?;
        if !is_valid_path_pattern(pattern) {
            return Err(20);
        }
    }
    for rec in section_records(blob, 4) {
        if u8_at(rec, 12) == Some(2) {
            let pattern = pool_utf8(
                pool,
                u32_le(rec, 0).ok_or(20u8)?,
                u16_le(rec, 8).ok_or(20u8)?,
            )
            .ok_or(20u8)?;
            if !is_valid_path_pattern(pattern) {
                return Err(20);
            }
        }
    }
    Ok(())
}

pub fn tv21(blob: &[u8]) -> Result<(), u8> {
    let pool = section_slice(blob, 9);
    for rec in section_records(blob, 2).chain(section_records(blob, 6)) {
        let kind = u8_at(rec, 8).ok_or(21u8)?;
        if kind == 1 || kind == 2 {
            let name = pool_bytes(
                pool,
                u32_le(rec, 16).ok_or(21u8)?,
                u16_le(rec, 14).ok_or(21u8)?,
            )
            .ok_or(21u8)?;
            if !is_canonical_host_name(name) {
                return Err(21);
            }
        }
    }
    Ok(())
}

pub fn tv22(blob: &[u8]) -> Result<(), u8> {
    for rec in section_records(blob, 2).chain(section_records(blob, 6)) {
        let kind = u8_at(rec, 8).ok_or(22u8)?;
        let prefix_len = u8_at(rec, 9).ok_or(22u8)?;
        let addr = rec.get(24..40).ok_or(22u8)?;
        if kind == 3 {
            let v4 = addr.get(0..4).ok_or(22u8)?;
            let tail = addr.get(4..16).ok_or(22u8)?;
            if prefix_len > 32
                || tail.iter().any(|&b| b != 0)
                || !host_bits_zero(v4, prefix_len, 32)
            {
                return Err(22);
            }
        } else if kind == 4 {
            if prefix_len > 128 || !host_bits_zero(addr, prefix_len, 128) {
                return Err(22);
            }
            if prefix_len >= 96 && is_mapped_or_nat64_prefix(addr) {
                return Err(22);
            }
        }
    }
    Ok(())
}

pub(super) fn pool_bytes(pool: &[u8], off: u32, len: u16) -> Option<&[u8]> {
    let start = off as usize;
    let end = start.checked_add(len as usize)?;
    pool.get(start..end)
}

fn take_utf8(pos: &mut usize, pool: &[u8], off: u32, len: u16) -> Result<(), u8> {
    if len == 0 || (off as usize) != *pos {
        return Err(18);
    }
    let end = pos.checked_add(len as usize).ok_or(18u8)?;
    if end > pool.len() {
        return Err(18);
    }
    *pos = end;
    Ok(())
}

fn take_utf16(pos: &mut usize, pool: &[u8], off: u32, units: u16) -> Result<(), u8> {
    if units == 0 {
        return Err(18);
    }
    if *pos % 2 == 1 {
        if pool.get(*pos) != Some(&0) {
            return Err(18);
        }
        *pos += 1;
    }
    if (off as usize) != *pos {
        return Err(18);
    }
    let byte_len = (units as usize) * 2;
    let end = pos.checked_add(byte_len).ok_or(18u8)?;
    if end > pool.len() {
        return Err(18);
    }
    *pos = end;
    Ok(())
}

fn pool_utf8(pool: &[u8], off: u32, len: u16) -> Option<&str> {
    std::str::from_utf8(pool_bytes(pool, off, len)?).ok()
}

fn pool_utf16(pool: &[u8], off: u32, units: u16) -> Option<String> {
    let start = off as usize;
    let byte_len = (units as usize).checked_mul(2)?;
    let end = start.checked_add(byte_len)?;
    let bytes = pool.get(start..end)?;
    let (chunks, _) = bytes.as_chunks::<2>();
    let code_units = chunks.iter().copied().map(u16::from_le_bytes);
    char::decode_utf16(code_units)
        .collect::<Result<String, _>>()
        .ok()
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

fn is_valid_path_pattern(pattern: &str) -> bool {
    let segments: Vec<&str> = if let Some(rest) = pattern.strip_prefix('/') {
        rest.split('/').collect()
    } else {
        let segs: Vec<&str> = pattern.split('/').collect();
        if segs.first().copied() != Some("**") {
            return false;
        }
        segs
    };

    for seg in segments {
        if seg.is_empty() || seg == "." || seg == ".." {
            return false;
        }
        if seg == "**" {
            continue;
        }
        if !is_valid_non_globstar_segment(seg.as_bytes()) {
            return false;
        }
    }
    true
}

fn is_valid_non_globstar_segment(bytes: &[u8]) -> bool {
    let mut i = 0usize;
    while let Some(&b) = bytes.get(i) {
        match b {
            b'\\' => {
                let Some(&next) = bytes.get(i + 1) else {
                    return false;
                };
                if !matches!(next, b'*' | b'?' | b'\\') {
                    return false;
                }
                i += 2;
            }
            b'*' => {
                if bytes.get(i + 1) == Some(&b'*') {
                    return false;
                }
                i += 1;
            }
            _ => {
                i += 1;
            }
        }
    }
    true
}

fn is_canonical_host_name(bytes: &[u8]) -> bool {
    if bytes.is_empty() || bytes.len() > 253 {
        return false;
    }
    let labels: Vec<&[u8]> = bytes.split(|&b| b == b'.').collect();
    for label in &labels {
        if label.is_empty() || label.len() > 63 {
            return false;
        }
        if label.first() == Some(&b'-') || label.last() == Some(&b'-') {
            return false;
        }
        if !label
            .iter()
            .all(|&b| matches!(b, b'a'..=b'z' | b'0'..=b'9' | b'-'))
        {
            return false;
        }
    }
    let Some(&last) = labels.last() else {
        return false;
    };
    if last.iter().all(|b| b.is_ascii_digit()) {
        return false;
    }
    if let Some(rest) = last.strip_prefix(b"0x")
        && !rest.is_empty()
        && rest.iter().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
    {
        return false;
    }
    true
}

fn host_bits_zero(addr: &[u8], prefix_len: u8, total_bits: u8) -> bool {
    for bit in (prefix_len as usize)..(total_bits as usize) {
        let Some(&byte) = addr.get(bit / 8) else {
            return false;
        };
        let shift = 7 - (bit % 8);
        if ((byte >> shift) & 1) != 0 {
            return false;
        }
    }
    true
}

fn is_mapped_or_nat64_prefix(addr: &[u8]) -> bool {
    const V4_MAPPED: [u8; 12] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xFF, 0xFF];
    const NAT64_WKP: [u8; 12] = [0x00, 0x64, 0xFF, 0x9B, 0, 0, 0, 0, 0, 0, 0, 0];
    addr.get(0..12) == Some(V4_MAPPED.as_slice()) || addr.get(0..12) == Some(NAT64_WKP.as_slice())
}
