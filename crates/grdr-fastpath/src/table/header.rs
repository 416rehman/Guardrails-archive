// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use crate::layout::{
    ABI_MAX_ACTION_CLASS, HEADER_LEN, Header, MAGIC, MAX_ACTION_CLASS_BITS, STABLE_PREFIX_LEN,
    Section, TABLE_FORMAT, abi_version,
};

use super::Error;

const HEADER_PADDING_OFFSETS: [usize; 11] = [20, 21, 22, 23, 62, 63, 183, 220, 221, 222, 223];
const ARENA_SLOT_BYTES: usize = 8;

pub(super) fn validate_header(blob: &[u8]) -> Result<(Header, usize), Error> {
    if blob.len() < STABLE_PREFIX_LEN {
        return Err(Error::from_tv_rule(1));
    }
    let Some(magic_bytes) = blob.get(0..8) else {
        return Err(Error::from_tv_rule(1));
    };
    if magic_bytes != MAGIC {
        return Err(Error::from_tv_rule(2));
    }

    let Some(abi_min) = read_u32(blob, 12) else {
        return Err(Error::from_tv_rule(1));
    };
    if abi_min > abi_version() {
        return Err(Error::from_tv_rule(3));
    }

    let Some(table_format) = read_u32(blob, 8) else {
        return Err(Error::from_tv_rule(1));
    };
    if table_format != TABLE_FORMAT {
        return Err(Error::from_tv_rule(4));
    }

    let Some((header_bytes, _)) = blob.split_first_chunk::<HEADER_LEN>() else {
        return Err(Error::from_tv_rule(5));
    };
    let header = Header::decode(header_bytes);

    if u64::try_from(blob.len()).ok() != Some(u64::from(header.blob_len)) {
        return Err(Error::from_tv_rule(6));
    }
    if !padding_bytes_zero(header_bytes) {
        return Err(Error::from_tv_rule(7));
    }
    if !params_in_range(&header) {
        return Err(Error::from_tv_rule(8));
    }

    validate_directory(&header)?;

    let slot_count = usize::from(header.action_class_count)
        .checked_add(1)
        .ok_or_else(|| Error::from_tv_rule(8))?;
    let needed_arena = slot_count
        .checked_mul(ARENA_SLOT_BYTES)
        .ok_or_else(|| Error::from_tv_rule(8))?;

    Ok((header, needed_arena))
}

fn validate_directory(header: &Header) -> Result<(), Error> {
    for section in Section::ALL {
        let entry = header.section_entry(section);
        let len = section_byte_len(section, entry.count)?;
        if len > u64::from(u32::MAX) {
            return Err(Error::from_tv_rule(9));
        }
    }

    for section in Section::ALL {
        let entry = header.section_entry(section);
        if entry.count > 0 && (entry.offset & 7) != 0 {
            return Err(Error::from_tv_rule(10));
        }
    }

    let min_offset = u32::try_from(HEADER_LEN).map_err(|_| Error::from_tv_rule(11))?;
    for section in Section::ALL {
        let entry = header.section_entry(section);
        if entry.count == 0 {
            if entry.offset != 0 {
                return Err(Error::from_tv_rule(11));
            }
        } else if entry.offset < min_offset {
            return Err(Error::from_tv_rule(11));
        }
    }

    let blob_end = u64::from(header.blob_len);
    for section in Section::ALL {
        let entry = header.section_entry(section);
        if entry.count > 0 {
            let len = section_byte_len(section, entry.count)?;
            let end = u64::from(entry.offset)
                .checked_add(len)
                .ok_or_else(|| Error::from_tv_rule(12))?;
            if end > blob_end {
                return Err(Error::from_tv_rule(12));
            }
        }
    }

    let header_end = u64::try_from(HEADER_LEN).map_err(|_| Error::from_tv_rule(13))?;
    let mut prev_end = header_end;
    for section in Section::ALL {
        let entry = header.section_entry(section);
        if entry.count > 0 {
            let len = section_byte_len(section, entry.count)?;
            let start = u64::from(entry.offset);
            if start < prev_end {
                return Err(Error::from_tv_rule(13));
            }
            prev_end = start
                .checked_add(len)
                .ok_or_else(|| Error::from_tv_rule(13))?;
        }
    }

    let mut expected = header_end;
    for section in Section::ALL {
        let entry = header.section_entry(section);
        if entry.count > 0 {
            let aligned = align_up_8(expected).ok_or_else(|| Error::from_tv_rule(14))?;
            if u64::from(entry.offset) != aligned {
                return Err(Error::from_tv_rule(14));
            }
            let len = section_byte_len(section, entry.count)?;
            expected = aligned
                .checked_add(len)
                .ok_or_else(|| Error::from_tv_rule(14))?;
        }
    }
    if blob_end != expected {
        return Err(Error::from_tv_rule(14));
    }

    Ok(())
}

fn padding_bytes_zero(header_bytes: &[u8; HEADER_LEN]) -> bool {
    for idx in HEADER_PADDING_OFFSETS {
        if header_bytes.get(idx).copied() != Some(0) {
            return false;
        }
    }
    true
}

fn params_in_range(header: &Header) -> bool {
    if header.eval_cap == 0
        || header.action_class_count == 0
        || header.action_class_count > MAX_ACTION_CLASS_BITS
        || header.action_class_count > ABI_MAX_ACTION_CLASS
        || header.principal_kind_count == 0
        || header.path_max_units == 0
        || header.expiry_bundle_ns == 0
        || header.expiry_session_ns == 0
    {
        return false;
    }
    let Some(allowed_mask) = allowed_class_mask(header.action_class_count) else {
        return false;
    };
    (header.session_rule_classes & !allowed_mask) == 0
        && (header.loss_closed_classes & !allowed_mask) == 0
}

fn allowed_class_mask(action_class_count: u16) -> Option<u64> {
    let shift = u32::from(MAX_ACTION_CLASS_BITS).checked_sub(u32::from(action_class_count))?;
    let up_to_count = u64::MAX.checked_shr(shift)?;
    Some(up_to_count & !1u64)
}

fn section_byte_len(section: Section, count: u32) -> Result<u64, Error> {
    let rec_size = u64::try_from(section.record_size()).map_err(|_| Error::from_tv_rule(9))?;
    u64::from(count)
        .checked_mul(rec_size)
        .ok_or_else(|| Error::from_tv_rule(9))
}

fn align_up_8(val: u64) -> Option<u64> {
    let rem = val & 7;
    if rem == 0 {
        Some(val)
    } else {
        let pad = 8u64.checked_sub(rem)?;
        val.checked_add(pad)
    }
}

fn read_u32(bytes: &[u8], off: usize) -> Option<u32> {
    let tail = bytes.get(off..)?;
    let (chunk, _) = tail.split_first_chunk::<4>()?;
    Some(u32::from_le_bytes(*chunk))
}
