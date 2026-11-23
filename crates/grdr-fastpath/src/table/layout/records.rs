// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use core::fmt;

use super::codec::{
    copy_into_slice, slice_array, slice_u8, slice_u16, slice_u32, slice_u64, write_u16, write_u32,
    write_u64,
};
use super::{
    EXE_ENTRY_SIZE, FLOOR_ROW_SIZE, HOST_ENTRY_SIZE, PATH_ENTRY_SIZE, PORT_RANGE_SIZE,
    PROCESS_SCOPE_ENTRY_SIZE, REASON_ENTRY_SIZE,
};

mod sealed {
    pub trait Sealed {}
}

pub trait Record: sealed::Sealed + Copy + 'static {
    const SIZE: usize;

    fn decode_slice(bytes: &[u8]) -> Option<Self>;
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub struct FloorRow {
    pub action_class: u16,
    pub principal_kind: u8,
    pub outcome: u8,
    pub reason: u32,
    pub resource_classes: u64,
    pub required_labels: u64,
    pub forbidden_labels: u64,
    pub grant_digest: [u8; 32],
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct PathEntry {
    pub utf8_off: u32,
    pub utf16_off: u32,
    pub utf8_len: u16,
    pub utf16_len: u16,
    pub class_bit: u8,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub struct HostEntry {
    pub class_mask: u64,
    pub kind: u8,
    pub prefix_len: u8,
    pub port_lo: u16,
    pub port_hi: u16,
    pub name_len: u16,
    pub name_off: u32,
    pub addr: [u8; 16],
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub struct ExeEntry {
    pub digest: [u8; 32],
    pub class_mask: u64,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub struct ProcessScopeEntry {
    pub utf8_off: u32,
    pub utf16_off: u32,
    pub utf8_len: u16,
    pub utf16_len: u16,
    pub kind: u8,
    pub digest: [u8; 32],
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct PortRange {
    pub port_lo: u16,
    pub port_hi: u16,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct ReasonEntry {
    pub reason_off: u32,
    pub rule_off: u32,
    pub reason_len: u16,
    pub rule_len: u16,
}

impl sealed::Sealed for FloorRow {}
impl sealed::Sealed for PathEntry {}
impl sealed::Sealed for HostEntry {}
impl sealed::Sealed for ExeEntry {}
impl sealed::Sealed for ProcessScopeEntry {}
impl sealed::Sealed for PortRange {}
impl sealed::Sealed for ReasonEntry {}

impl FloorRow {
    pub fn encode(&self) -> [u8; FLOOR_ROW_SIZE] {
        let mut out = [0u8; FLOOR_ROW_SIZE];
        write_u16(&mut out, 0, self.action_class);
        out[2] = self.principal_kind;
        out[3] = self.outcome;
        write_u32(&mut out, 4, self.reason);
        write_u64(&mut out, 8, self.resource_classes);
        write_u64(&mut out, 16, self.required_labels);
        write_u64(&mut out, 24, self.forbidden_labels);
        let _ = copy_into_slice(&mut out, 32, &self.grant_digest);
        out
    }

    pub fn decode(bytes: &[u8; FLOOR_ROW_SIZE]) -> Self {
        Self::decode_raw(bytes)
    }

    fn decode_raw(bytes: &[u8]) -> Self {
        Self {
            action_class: slice_u16(bytes, 0).unwrap_or(0),
            principal_kind: slice_u8(bytes, 2).unwrap_or(0),
            outcome: slice_u8(bytes, 3).unwrap_or(0),
            reason: slice_u32(bytes, 4).unwrap_or(0),
            resource_classes: slice_u64(bytes, 8).unwrap_or(0),
            required_labels: slice_u64(bytes, 16).unwrap_or(0),
            forbidden_labels: slice_u64(bytes, 24).unwrap_or(0),
            grant_digest: slice_array::<32>(bytes, 32).unwrap_or([0; 32]),
        }
    }
}

impl Record for FloorRow {
    const SIZE: usize = FLOOR_ROW_SIZE;

    fn decode_slice(bytes: &[u8]) -> Option<Self> {
        let (chunk, _) = bytes.split_first_chunk::<FLOOR_ROW_SIZE>()?;
        Some(Self::decode(chunk))
    }
}

impl fmt::Debug for FloorRow {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("FloorRow")
            .field("action_class", &self.action_class)
            .field("principal_kind", &self.principal_kind)
            .field("outcome", &self.outcome)
            .field("reason", &self.reason)
            .field("resource_classes", &self.resource_classes)
            .field("required_labels", &self.required_labels)
            .field("forbidden_labels", &self.forbidden_labels)
            .field("grant_digest_len", &self.grant_digest.len())
            .finish()
    }
}

impl PathEntry {
    pub fn encode(&self) -> [u8; PATH_ENTRY_SIZE] {
        let mut out = [0u8; PATH_ENTRY_SIZE];
        write_u32(&mut out, 0, self.utf8_off);
        write_u32(&mut out, 4, self.utf16_off);
        write_u16(&mut out, 8, self.utf8_len);
        write_u16(&mut out, 10, self.utf16_len);
        out[12] = self.class_bit;
        out
    }

    pub fn decode(bytes: &[u8; PATH_ENTRY_SIZE]) -> Self {
        Self::decode_raw(bytes)
    }

    fn decode_raw(bytes: &[u8]) -> Self {
        Self {
            utf8_off: slice_u32(bytes, 0).unwrap_or(0),
            utf16_off: slice_u32(bytes, 4).unwrap_or(0),
            utf8_len: slice_u16(bytes, 8).unwrap_or(0),
            utf16_len: slice_u16(bytes, 10).unwrap_or(0),
            class_bit: slice_u8(bytes, 12).unwrap_or(0),
        }
    }
}

impl Record for PathEntry {
    const SIZE: usize = PATH_ENTRY_SIZE;

    fn decode_slice(bytes: &[u8]) -> Option<Self> {
        let (chunk, _) = bytes.split_first_chunk::<PATH_ENTRY_SIZE>()?;
        Some(Self::decode(chunk))
    }
}

impl HostEntry {
    pub fn encode(&self) -> [u8; HOST_ENTRY_SIZE] {
        let mut out = [0u8; HOST_ENTRY_SIZE];
        write_u64(&mut out, 0, self.class_mask);
        out[8] = self.kind;
        out[9] = self.prefix_len;
        write_u16(&mut out, 10, self.port_lo);
        write_u16(&mut out, 12, self.port_hi);
        write_u16(&mut out, 14, self.name_len);
        write_u32(&mut out, 16, self.name_off);
        let _ = copy_into_slice(&mut out, 24, &self.addr);
        out
    }

    pub fn decode(bytes: &[u8; HOST_ENTRY_SIZE]) -> Self {
        Self::decode_raw(bytes)
    }

    fn decode_raw(bytes: &[u8]) -> Self {
        Self {
            class_mask: slice_u64(bytes, 0).unwrap_or(0),
            kind: slice_u8(bytes, 8).unwrap_or(0),
            prefix_len: slice_u8(bytes, 9).unwrap_or(0),
            port_lo: slice_u16(bytes, 10).unwrap_or(0),
            port_hi: slice_u16(bytes, 12).unwrap_or(0),
            name_len: slice_u16(bytes, 14).unwrap_or(0),
            name_off: slice_u32(bytes, 16).unwrap_or(0),
            addr: slice_array::<16>(bytes, 24).unwrap_or([0; 16]),
        }
    }
}

impl Record for HostEntry {
    const SIZE: usize = HOST_ENTRY_SIZE;

    fn decode_slice(bytes: &[u8]) -> Option<Self> {
        let (chunk, _) = bytes.split_first_chunk::<HOST_ENTRY_SIZE>()?;
        Some(Self::decode(chunk))
    }
}

impl fmt::Debug for HostEntry {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("HostEntry")
            .field("class_mask", &self.class_mask)
            .field("kind", &self.kind)
            .field("prefix_len", &self.prefix_len)
            .field("port_lo", &self.port_lo)
            .field("port_hi", &self.port_hi)
            .field("name_len", &self.name_len)
            .field("name_off", &self.name_off)
            .field("addr_len", &self.addr.len())
            .finish()
    }
}

impl ExeEntry {
    pub fn encode(&self) -> [u8; EXE_ENTRY_SIZE] {
        let mut out = [0u8; EXE_ENTRY_SIZE];
        let _ = copy_into_slice(&mut out, 0, &self.digest);
        write_u64(&mut out, 32, self.class_mask);
        out
    }

    pub fn decode(bytes: &[u8; EXE_ENTRY_SIZE]) -> Self {
        Self::decode_raw(bytes)
    }

    fn decode_raw(bytes: &[u8]) -> Self {
        Self {
            digest: slice_array::<32>(bytes, 0).unwrap_or([0; 32]),
            class_mask: slice_u64(bytes, 32).unwrap_or(0),
        }
    }
}

impl Record for ExeEntry {
    const SIZE: usize = EXE_ENTRY_SIZE;

    fn decode_slice(bytes: &[u8]) -> Option<Self> {
        let (chunk, _) = bytes.split_first_chunk::<EXE_ENTRY_SIZE>()?;
        Some(Self::decode(chunk))
    }
}

impl fmt::Debug for ExeEntry {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("ExeEntry")
            .field("digest_len", &self.digest.len())
            .field("class_mask", &self.class_mask)
            .finish()
    }
}

impl ProcessScopeEntry {
    pub fn encode(&self) -> [u8; PROCESS_SCOPE_ENTRY_SIZE] {
        let mut out = [0u8; PROCESS_SCOPE_ENTRY_SIZE];
        write_u32(&mut out, 0, self.utf8_off);
        write_u32(&mut out, 4, self.utf16_off);
        write_u16(&mut out, 8, self.utf8_len);
        write_u16(&mut out, 10, self.utf16_len);
        out[12] = self.kind;
        let _ = copy_into_slice(&mut out, 16, &self.digest);
        out
    }

    pub fn decode(bytes: &[u8; PROCESS_SCOPE_ENTRY_SIZE]) -> Self {
        Self::decode_raw(bytes)
    }

    fn decode_raw(bytes: &[u8]) -> Self {
        Self {
            utf8_off: slice_u32(bytes, 0).unwrap_or(0),
            utf16_off: slice_u32(bytes, 4).unwrap_or(0),
            utf8_len: slice_u16(bytes, 8).unwrap_or(0),
            utf16_len: slice_u16(bytes, 10).unwrap_or(0),
            kind: slice_u8(bytes, 12).unwrap_or(0),
            digest: slice_array::<32>(bytes, 16).unwrap_or([0; 32]),
        }
    }
}

impl Record for ProcessScopeEntry {
    const SIZE: usize = PROCESS_SCOPE_ENTRY_SIZE;

    fn decode_slice(bytes: &[u8]) -> Option<Self> {
        let (chunk, _) = bytes.split_first_chunk::<PROCESS_SCOPE_ENTRY_SIZE>()?;
        Some(Self::decode(chunk))
    }
}

impl fmt::Debug for ProcessScopeEntry {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("ProcessScopeEntry")
            .field("utf8_off", &self.utf8_off)
            .field("utf16_off", &self.utf16_off)
            .field("utf8_len", &self.utf8_len)
            .field("utf16_len", &self.utf16_len)
            .field("kind", &self.kind)
            .field("digest_len", &self.digest.len())
            .finish()
    }
}

impl PortRange {
    pub fn encode(&self) -> [u8; PORT_RANGE_SIZE] {
        let mut out = [0u8; PORT_RANGE_SIZE];
        write_u16(&mut out, 0, self.port_lo);
        write_u16(&mut out, 2, self.port_hi);
        out
    }

    pub fn decode(bytes: &[u8; PORT_RANGE_SIZE]) -> Self {
        Self::decode_raw(bytes)
    }

    fn decode_raw(bytes: &[u8]) -> Self {
        Self {
            port_lo: slice_u16(bytes, 0).unwrap_or(0),
            port_hi: slice_u16(bytes, 2).unwrap_or(0),
        }
    }
}

impl Record for PortRange {
    const SIZE: usize = PORT_RANGE_SIZE;

    fn decode_slice(bytes: &[u8]) -> Option<Self> {
        let (chunk, _) = bytes.split_first_chunk::<PORT_RANGE_SIZE>()?;
        Some(Self::decode(chunk))
    }
}

impl ReasonEntry {
    pub fn encode(&self) -> [u8; REASON_ENTRY_SIZE] {
        let mut out = [0u8; REASON_ENTRY_SIZE];
        write_u32(&mut out, 0, self.reason_off);
        write_u32(&mut out, 4, self.rule_off);
        write_u16(&mut out, 8, self.reason_len);
        write_u16(&mut out, 10, self.rule_len);
        out
    }

    pub fn decode(bytes: &[u8; REASON_ENTRY_SIZE]) -> Self {
        Self::decode_raw(bytes)
    }

    fn decode_raw(bytes: &[u8]) -> Self {
        Self {
            reason_off: slice_u32(bytes, 0).unwrap_or(0),
            rule_off: slice_u32(bytes, 4).unwrap_or(0),
            reason_len: slice_u16(bytes, 8).unwrap_or(0),
            rule_len: slice_u16(bytes, 10).unwrap_or(0),
        }
    }
}

impl Record for ReasonEntry {
    const SIZE: usize = REASON_ENTRY_SIZE;

    fn decode_slice(bytes: &[u8]) -> Option<Self> {
        let (chunk, _) = bytes.split_first_chunk::<REASON_ENTRY_SIZE>()?;
        Some(Self::decode(chunk))
    }
}
