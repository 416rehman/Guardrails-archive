// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use super::reader::{
    HEADER_LEN, SECTION_COUNT, record_size, section_desc, section_records, section_slice, u8_at,
    u16_le, u32_le, u64_le,
};
use super::strings::pool_bytes;

pub fn tv15(blob: &[u8]) -> Result<(), u8> {
    let mut cursor = HEADER_LEN;
    for i in 0..SECTION_COUNT {
        let desc = section_desc(blob, i).ok_or(15u8)?;
        if desc.count > 0 {
            let rec_size = record_size(i).ok_or(15u8)?;
            let start = desc.offset as usize;
            let gap = blob.get(cursor..start).ok_or(15u8)?;
            if gap.iter().any(|&b| b != 0) {
                return Err(15);
            }
            cursor = start + (desc.count as usize) * (rec_size as usize);
        }
    }
    let tail = blob.get(cursor..).ok_or(15u8)?;
    if tail.iter().any(|&b| b != 0) {
        return Err(15);
    }
    Ok(())
}

pub fn tv16(blob: &[u8]) -> Result<(), u8> {
    for rec in section_records(blob, 2).chain(section_records(blob, 6)) {
        let kind = u8_at(rec, 8).ok_or(16u8)?;
        if !(1..=5).contains(&kind) {
            return Err(16);
        }
    }
    for rec in section_records(blob, 4) {
        let kind = u8_at(rec, 12).ok_or(16u8)?;
        if !(1..=4).contains(&kind) {
            return Err(16);
        }
    }
    Ok(())
}

pub fn tv17(blob: &[u8]) -> Result<(), u8> {
    for rec in section_records(blob, 1) {
        if rec.get(13..16) != Some(&[0, 0, 0]) {
            return Err(17);
        }
    }
    for rec in section_records(blob, 2) {
        if !host_unused_fields_zero(rec, false) {
            return Err(17);
        }
    }
    for rec in section_records(blob, 4) {
        if rec.get(13..16) != Some(&[0, 0, 0]) {
            return Err(17);
        }
        let kind = u8_at(rec, 12).ok_or(17u8)?;
        if kind == 1 && rec.get(0..12).is_none_or(|s| s.iter().any(|&b| b != 0)) {
            return Err(17);
        }
        if (2..=4).contains(&kind) && rec.get(16..48).is_none_or(|s| s.iter().any(|&b| b != 0)) {
            return Err(17);
        }
    }
    for rec in section_records(blob, 5) {
        if u8_at(rec, 12) != Some(0) || rec.get(13..16) != Some(&[0, 0, 0]) {
            return Err(17);
        }
    }
    for rec in section_records(blob, 6) {
        if !host_unused_fields_zero(rec, true) {
            return Err(17);
        }
    }
    for rec in section_records(blob, 8) {
        if rec.get(12..16) != Some(&[0, 0, 0, 0]) {
            return Err(17);
        }
    }
    Ok(())
}

pub fn tv23(blob: &[u8]) -> Result<(), u8> {
    for rec in section_records(blob, 2).chain(section_records(blob, 6)) {
        if u16_le(rec, 10).ok_or(23u8)? > u16_le(rec, 12).ok_or(23u8)? {
            return Err(23);
        }
    }
    for rec in section_records(blob, 7) {
        if u16_le(rec, 0).ok_or(23u8)? > u16_le(rec, 2).ok_or(23u8)? {
            return Err(23);
        }
    }
    Ok(())
}

pub fn tv24(blob: &[u8]) -> Result<(), u8> {
    for rec in section_records(blob, 1) {
        if u8_at(rec, 12).ok_or(24u8)? > 63 {
            return Err(24);
        }
    }
    for rec in section_records(blob, 2) {
        if u64_le(rec, 0).ok_or(24u8)? == 0 {
            return Err(24);
        }
    }
    for rec in section_records(blob, 3) {
        if u64_le(rec, 32).ok_or(24u8)? == 0 {
            return Err(24);
        }
    }
    Ok(())
}

pub fn tv25(blob: &[u8]) -> Result<(), u8> {
    let mut prev: Option<&[u8]> = None;
    for rec in section_records(blob, 3) {
        let digest = rec.get(0..32).ok_or(25u8)?;
        if digest.iter().all(|&b| b == 0) {
            return Err(25);
        }
        if let Some(p) = prev
            && p >= digest
        {
            return Err(25);
        }
        prev = Some(digest);
    }
    for rec in section_records(blob, 4) {
        if u8_at(rec, 12) == Some(1) && rec.get(16..48).is_none_or(|d| d.iter().all(|&b| b == 0)) {
            return Err(25);
        }
    }
    Ok(())
}

pub fn tv26(blob: &[u8]) -> Result<(), u8> {
    let action_class_count = u16_le(blob, 180).ok_or(26u8)?;
    let loss_closed_classes = u64_le(blob, 224).ok_or(26u8)?;
    for rec in section_records(blob, 0) {
        let class = u16_le(rec, 0).ok_or(26u8)?;
        if class == 0 || class > action_class_count {
            return Err(26);
        }
        if (loss_closed_classes & (1u64 << u32::from(class))) == 0 {
            return Err(26);
        }
    }
    Ok(())
}

pub fn tv27(blob: &[u8]) -> Result<(), u8> {
    let mut prev: Option<(u16, u32, &[u8])> = None;
    for rec in section_records(blob, 0) {
        let key = (
            u16_le(rec, 0).ok_or(27u8)?,
            u32_le(rec, 4).ok_or(27u8)?,
            rec,
        );
        if let Some(p) = prev
            && p >= key
        {
            return Err(27);
        }
        prev = Some(key);
    }
    Ok(())
}

pub fn tv28(blob: &[u8]) -> Result<(), u8> {
    let principal_kind_count = u8_at(blob, 182).ok_or(28u8)?;
    for rec in section_records(blob, 0) {
        if u8_at(rec, 2).ok_or(28u8)? > principal_kind_count {
            return Err(28);
        }
    }
    Ok(())
}

pub fn tv29(blob: &[u8]) -> Result<(), u8> {
    for rec in section_records(blob, 0) {
        let outcome = u8_at(rec, 3).ok_or(29u8)?;
        if outcome != 2 && outcome != 3 {
            return Err(29);
        }
    }
    Ok(())
}

pub fn tv30(blob: &[u8]) -> Result<(), u8> {
    let reason_count = section_desc(blob, 8).ok_or(30u8)?.count;
    for rec in section_records(blob, 0) {
        if u32_le(rec, 4).ok_or(30u8)? >= reason_count {
            return Err(30);
        }
    }
    Ok(())
}

pub fn tv31(blob: &[u8]) -> Result<(), u8> {
    for rec in section_records(blob, 0) {
        let req = u64_le(rec, 16).ok_or(31u8)?;
        let forb = u64_le(rec, 24).ok_or(31u8)?;
        if (req & forb) != 0 {
            return Err(31);
        }
    }
    Ok(())
}

pub fn tv32(blob: &[u8]) -> Result<(), u8> {
    let mut reachable = 0u64;
    for rec in section_records(blob, 1) {
        let bit = u8_at(rec, 12).ok_or(32u8)?;
        reachable |= 1u64 << u32::from(bit);
    }
    for rec in section_records(blob, 2) {
        reachable |= u64_le(rec, 0).ok_or(32u8)?;
    }
    for rec in section_records(blob, 3) {
        reachable |= u64_le(rec, 32).ok_or(32u8)?;
    }
    for rec in section_records(blob, 0) {
        let needed = u64_le(rec, 8).ok_or(32u8)?;
        if (needed & !reachable) != 0 {
            return Err(32);
        }
    }
    Ok(())
}

pub fn tv33(blob: &[u8]) -> Result<(), u8> {
    let pool = section_slice(blob, 9);
    let mut prev: Option<&[u8]> = None;
    for rec in section_records(blob, 8) {
        let rule_id = pool_bytes(
            pool,
            u32_le(rec, 4).ok_or(33u8)?,
            u16_le(rec, 10).ok_or(33u8)?,
        )
        .ok_or(33u8)?;
        if let Some(p) = prev
            && p >= rule_id
        {
            return Err(33);
        }
        prev = Some(rule_id);
    }
    Ok(())
}

fn host_unused_fields_zero(rec: &[u8], is_interest: bool) -> bool {
    if is_interest && u64_le(rec, 0) != Some(0) {
        return false;
    }
    if rec.get(20..24) != Some(&[0, 0, 0, 0]) {
        return false;
    }
    let Some(kind) = u8_at(rec, 8) else {
        return false;
    };
    let prefix_zero = u8_at(rec, 9) == Some(0);
    let name_fields_zero = rec.get(14..20) == Some(&[0; 6]);
    let addr_zero = rec.get(24..40) == Some(&[0; 16]);
    match kind {
        1 | 2 => prefix_zero && addr_zero,
        3 | 4 => name_fields_zero,
        5 => prefix_zero && name_fields_zero && addr_zero,
        _ => false,
    }
}
