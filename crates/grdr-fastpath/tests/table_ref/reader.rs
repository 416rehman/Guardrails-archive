// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

pub const MAGIC: [u8; 8] = [0x89, 0x67, 0x72, 0x64, 0x72, 0x66, 0x70, 0x0A];
pub const FORMAT_V1: u32 = 1;
pub const ABI_V0_1: u32 = 0x0000_0001;
pub const ABI_MAX_ACTION_CLASS: u16 = 15;
pub const STABLE_PREFIX_LEN: usize = 20;
pub const HEADER_LEN: usize = 232;
pub const SECTION_COUNT: usize = 10;

pub const RECORD_SIZES: [u64; SECTION_COUNT] = [
    64, // 0: floor rows
    16, // 1: path classifier
    40, // 2: host classifier
    40, // 3: executable classifier
    48, // 4: interest process scope
    16, // 5: interest paths
    40, // 6: interest hosts
    4,  // 7: interest ports
    16, // 8: reason-code table
    1,  // 9: string pool
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SectionDesc {
    pub count: u32,
    pub offset: u32,
}

pub fn u8_at(blob: &[u8], off: usize) -> Option<u8> {
    blob.get(off).copied()
}

pub fn u16_le(blob: &[u8], off: usize) -> Option<u16> {
    let chunk = blob.get(off..)?.first_chunk::<2>()?;
    Some(u16::from_le_bytes(*chunk))
}

pub fn u32_le(blob: &[u8], off: usize) -> Option<u32> {
    let chunk = blob.get(off..)?.first_chunk::<4>()?;
    Some(u32::from_le_bytes(*chunk))
}

pub fn u64_le(blob: &[u8], off: usize) -> Option<u64> {
    let chunk = blob.get(off..)?.first_chunk::<8>()?;
    Some(u64::from_le_bytes(*chunk))
}

pub fn record_size(idx: usize) -> Option<u64> {
    RECORD_SIZES.get(idx).copied()
}

pub fn section_desc(blob: &[u8], idx: usize) -> Option<SectionDesc> {
    let base = 96usize.checked_add(idx.checked_mul(8)?)?;
    Some(SectionDesc {
        count: u32_le(blob, base)?,
        offset: u32_le(blob, base.checked_add(4)?)?,
    })
}

pub fn section_slice(blob: &[u8], idx: usize) -> &[u8] {
    let Some(desc) = section_desc(blob, idx) else {
        return &[];
    };
    if desc.count == 0 {
        return &[];
    }
    let Some(rec_size) = record_size(idx) else {
        return &[];
    };
    let start = desc.offset as usize;
    let Some(len) = (desc.count as usize).checked_mul(rec_size as usize) else {
        return &[];
    };
    let Some(end) = start.checked_add(len) else {
        return &[];
    };
    blob.get(start..end).unwrap_or(&[])
}

pub fn section_records(blob: &[u8], idx: usize) -> impl Iterator<Item = &[u8]> {
    let slice = section_slice(blob, idx);
    let rec_size = record_size(idx).unwrap_or(1) as usize;
    slice.chunks_exact(rec_size)
}
