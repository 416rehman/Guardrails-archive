// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

pub(super) fn slice_array<const N: usize>(bytes: &[u8], off: usize) -> Option<[u8; N]> {
    let tail = bytes.get(off..)?;
    let (chunk, _) = tail.split_first_chunk::<N>()?;
    Some(*chunk)
}

pub(super) fn slice_u8(bytes: &[u8], off: usize) -> Option<u8> {
    bytes.get(off).copied()
}

pub(super) fn slice_u16(bytes: &[u8], off: usize) -> Option<u16> {
    slice_array::<2>(bytes, off).map(u16::from_le_bytes)
}

pub(super) fn slice_u32(bytes: &[u8], off: usize) -> Option<u32> {
    slice_array::<4>(bytes, off).map(u32::from_le_bytes)
}

pub(super) fn slice_u64(bytes: &[u8], off: usize) -> Option<u64> {
    slice_array::<8>(bytes, off).map(u64::from_le_bytes)
}

pub(super) fn copy_into_slice(dst: &mut [u8], off: usize, src: &[u8]) -> Option<()> {
    let end = off.checked_add(src.len())?;
    let target = dst.get_mut(off..end)?;
    target.copy_from_slice(src);
    Some(())
}

pub(super) fn write_u16(dst: &mut [u8], off: usize, val: u16) {
    let _ = copy_into_slice(dst, off, &val.to_le_bytes());
}

pub(super) fn write_u32(dst: &mut [u8], off: usize, val: u32) {
    let _ = copy_into_slice(dst, off, &val.to_le_bytes());
}

pub(super) fn write_u64(dst: &mut [u8], off: usize, val: u64) {
    let _ = copy_into_slice(dst, off, &val.to_le_bytes());
}
