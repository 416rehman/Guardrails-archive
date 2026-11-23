// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use super::reader::{
    ABI_MAX_ACTION_CLASS, ABI_V0_1, FORMAT_V1, HEADER_LEN, MAGIC, SECTION_COUNT, STABLE_PREFIX_LEN,
    record_size, section_desc, u8_at, u16_le, u32_le, u64_le,
};

pub fn tv01(blob: &[u8]) -> Result<(), u8> {
    if blob.len() < STABLE_PREFIX_LEN {
        return Err(1);
    }
    Ok(())
}

pub fn tv02(blob: &[u8]) -> Result<(), u8> {
    if blob.get(0..8) != Some(MAGIC.as_slice()) {
        return Err(2);
    }
    Ok(())
}

pub fn tv03(blob: &[u8]) -> Result<(), u8> {
    let Some(abi_min) = u32_le(blob, 12) else {
        return Err(3);
    };
    if abi_min > ABI_V0_1 {
        return Err(3);
    }
    Ok(())
}

pub fn tv04(blob: &[u8]) -> Result<(), u8> {
    let Some(format) = u32_le(blob, 8) else {
        return Err(4);
    };
    if format != FORMAT_V1 {
        return Err(4);
    }
    Ok(())
}

pub fn tv05(blob: &[u8]) -> Result<(), u8> {
    if blob.len() < HEADER_LEN {
        return Err(5);
    }
    Ok(())
}

pub fn tv06(blob: &[u8]) -> Result<(), u8> {
    let Some(raw_len) = u32_le(blob, 16) else {
        return Err(6);
    };
    if (blob.len() as u64) != u64::from(raw_len) {
        return Err(6);
    }
    Ok(())
}

pub fn tv07(blob: &[u8]) -> Result<(), u8> {
    const PADDING: [usize; 11] = [20, 21, 22, 23, 62, 63, 183, 220, 221, 222, 223];
    for idx in PADDING {
        if u8_at(blob, idx) != Some(0) {
            return Err(7);
        }
    }
    Ok(())
}

pub fn tv08(blob: &[u8]) -> Result<(), u8> {
    let eval_cap = u32_le(blob, 176).ok_or(8u8)?;
    let action_class_count = u16_le(blob, 180).ok_or(8u8)?;
    let principal_kind_count = u8_at(blob, 182).ok_or(8u8)?;
    let session_rule_classes = u64_le(blob, 184).ok_or(8u8)?;
    let expiry_bundle_ns = u64_le(blob, 200).ok_or(8u8)?;
    let expiry_session_ns = u64_le(blob, 208).ok_or(8u8)?;
    let path_max_units = u32_le(blob, 216).ok_or(8u8)?;
    let loss_closed_classes = u64_le(blob, 224).ok_or(8u8)?;

    if eval_cap == 0
        || action_class_count == 0
        || action_class_count > 63
        || action_class_count > ABI_MAX_ACTION_CLASS
        || principal_kind_count == 0
        || path_max_units == 0
        || expiry_bundle_ns == 0
        || expiry_session_ns == 0
    {
        return Err(8);
    }

    if has_disallowed_class_bits(session_rule_classes, action_class_count)
        || has_disallowed_class_bits(loss_closed_classes, action_class_count)
    {
        return Err(8);
    }
    Ok(())
}

pub fn tv09(blob: &[u8]) -> Result<(), u8> {
    for i in 0..SECTION_COUNT {
        let desc = section_desc(blob, i).ok_or(9u8)?;
        let rec_size = record_size(i).ok_or(9u8)?;
        let len = u64::from(desc.count) * rec_size;
        if len > u64::from(u32::MAX) {
            return Err(9);
        }
    }
    Ok(())
}

pub fn tv10(blob: &[u8]) -> Result<(), u8> {
    for i in 0..SECTION_COUNT {
        let desc = section_desc(blob, i).ok_or(10u8)?;
        if desc.count > 0 && desc.offset % 8 != 0 {
            return Err(10);
        }
    }
    Ok(())
}

pub fn tv11(blob: &[u8]) -> Result<(), u8> {
    for i in 0..SECTION_COUNT {
        let desc = section_desc(blob, i).ok_or(11u8)?;
        if desc.count == 0 {
            if desc.offset != 0 {
                return Err(11);
            }
        } else if (desc.offset as usize) < HEADER_LEN {
            return Err(11);
        }
    }
    Ok(())
}

pub fn tv12(blob: &[u8]) -> Result<(), u8> {
    let blob_len = u64::from(u32_le(blob, 16).ok_or(12u8)?);
    for i in 0..SECTION_COUNT {
        let desc = section_desc(blob, i).ok_or(12u8)?;
        if desc.count > 0 {
            let rec_size = record_size(i).ok_or(12u8)?;
            let len = u64::from(desc.count) * rec_size;
            let end = u64::from(desc.offset).checked_add(len).ok_or(12u8)?;
            if end > blob_len {
                return Err(12);
            }
        }
    }
    Ok(())
}

pub fn tv13(blob: &[u8]) -> Result<(), u8> {
    let mut prev_end = HEADER_LEN as u64;
    for i in 0..SECTION_COUNT {
        let desc = section_desc(blob, i).ok_or(13u8)?;
        if desc.count > 0 {
            let rec_size = record_size(i).ok_or(13u8)?;
            let start = u64::from(desc.offset);
            if start < prev_end {
                return Err(13);
            }
            prev_end = start + u64::from(desc.count) * rec_size;
        }
    }
    Ok(())
}

pub fn tv14(blob: &[u8]) -> Result<(), u8> {
    let blob_len = u64::from(u32_le(blob, 16).ok_or(14u8)?);
    let mut cursor = HEADER_LEN as u64;
    for i in 0..SECTION_COUNT {
        let desc = section_desc(blob, i).ok_or(14u8)?;
        if desc.count > 0 {
            let rec_size = record_size(i).ok_or(14u8)?;
            let aligned = (cursor + 7) & !7;
            if u64::from(desc.offset) != aligned {
                return Err(14);
            }
            cursor = aligned + u64::from(desc.count) * rec_size;
        }
    }
    if blob_len != cursor {
        return Err(14);
    }
    Ok(())
}

fn has_disallowed_class_bits(mask: u64, action_class_count: u16) -> bool {
    if (mask & 1) != 0 {
        return true;
    }
    for bit in (u32::from(action_class_count) + 1)..64 {
        if (mask >> bit) & 1 != 0 {
            return true;
        }
    }
    false
}
