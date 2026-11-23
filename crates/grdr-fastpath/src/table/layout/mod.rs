// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

mod codec;
mod cost;
mod records;

use core::fmt;

use codec::{
    copy_into_slice, slice_array, slice_u8, slice_u16, slice_u32, slice_u64, write_u16, write_u32,
    write_u64,
};

pub use cost::{exe_lookup_steps, path_entry_steps, path_steps_from_pattern_lens, total_eval_cost};
pub use records::{
    ExeEntry, FloorRow, HostEntry, PathEntry, PortRange, ProcessScopeEntry, ReasonEntry, Record,
};

pub const MAGIC: [u8; 8] = [0x89, b'g', b'r', b'd', b'r', b'f', b'p', 0x0A];
pub const TABLE_FORMAT: u32 = 1;
pub const STABLE_PREFIX_LEN: usize = 20;
pub const HEADER_LEN: usize = 232;
pub const SECTION_COUNT: usize = 10;
pub const NAME_MAX_BYTES: usize = 253;

pub const ABI_MAJOR: u16 = 0;
pub const ABI_MINOR: u16 = 1;
pub const ABI_MAX_ACTION_CLASS: u16 = 15;
pub const MAX_ACTION_CLASS_BITS: u16 = 63;

pub const FLOOR_ROW_SIZE: usize = 64;
pub const PATH_ENTRY_SIZE: usize = 16;
pub const HOST_ENTRY_SIZE: usize = 40;
pub const EXE_ENTRY_SIZE: usize = 40;
pub const PROCESS_SCOPE_ENTRY_SIZE: usize = 48;
pub const PORT_RANGE_SIZE: usize = 4;
pub const REASON_ENTRY_SIZE: usize = 16;
pub const STRING_POOL_UNIT_SIZE: usize = 1;

pub const PRINCIPAL_ANY: u8 = 0;
pub const PRINCIPAL_SESSION: u8 = 1;
pub const PRINCIPAL_PROCESS: u8 = 2;

pub const VERDICT_PASS: u8 = 1;
pub const VERDICT_DENY: u8 = 2;
pub const VERDICT_STEP_UP: u8 = 3;

pub const OUTCOME_DENY: u8 = 2;
pub const OUTCOME_STEP_UP: u8 = 3;

pub const HOST_KIND_EXACT_NAME: u8 = 1;
pub const HOST_KIND_WILDCARD_NAME: u8 = 2;
pub const HOST_KIND_IPV4_BLOCK: u8 = 3;
pub const HOST_KIND_IPV6_BLOCK: u8 = 4;
pub const HOST_KIND_ANY: u8 = 5;

pub const PROCESS_KIND_EXE_DIGEST: u8 = 1;
pub const PROCESS_KIND_EXE_PATH_PATTERN: u8 = 2;
pub const PROCESS_KIND_SIGNING_ID: u8 = 3;
pub const PROCESS_KIND_PACKAGE_ID: u8 = 4;

pub const fn abi_version() -> u32 {
    let [maj0, maj1] = ABI_MAJOR.to_le_bytes();
    let [min0, min1] = ABI_MINOR.to_le_bytes();
    u32::from_le_bytes([min0, min1, maj0, maj1])
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Section {
    FloorRows = 0,
    PathClassifier = 1,
    HostClassifier = 2,
    ExeClassifier = 3,
    ProcessScope = 4,
    InterestPaths = 5,
    InterestHosts = 6,
    InterestPorts = 7,
    ReasonTable = 8,
    StringPool = 9,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct SectionEntry {
    pub count: u32,
    pub offset: u32,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Nanos(u64);

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Expiry {
    ScopeEnd,
    After(Nanos),
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub struct Header {
    pub magic: [u8; 8],
    pub table_format: u32,
    pub abi_min: u32,
    pub blob_len: u32,
    pub bundle_digest: [u8; 32],
    pub compiler_version_major: u16,
    pub compiler_version_minor: u16,
    pub compiler_version_patch: u16,
    pub effective_hash: [u8; 32],
    pub sections: [SectionEntry; SECTION_COUNT],
    pub eval_cap: u32,
    pub action_class_count: u16,
    pub principal_kind_count: u8,
    pub session_rule_classes: u64,
    pub path_fold_classes: u64,
    pub expiry_bundle_ns: u64,
    pub expiry_session_ns: u64,
    pub path_max_units: u32,
    pub loss_closed_classes: u64,
}

impl Section {
    pub const ALL: [Self; SECTION_COUNT] = [
        Self::FloorRows,
        Self::PathClassifier,
        Self::HostClassifier,
        Self::ExeClassifier,
        Self::ProcessScope,
        Self::InterestPaths,
        Self::InterestHosts,
        Self::InterestPorts,
        Self::ReasonTable,
        Self::StringPool,
    ];

    pub const fn index(self) -> usize {
        match self {
            Self::FloorRows => 0,
            Self::PathClassifier => 1,
            Self::HostClassifier => 2,
            Self::ExeClassifier => 3,
            Self::ProcessScope => 4,
            Self::InterestPaths => 5,
            Self::InterestHosts => 6,
            Self::InterestPorts => 7,
            Self::ReasonTable => 8,
            Self::StringPool => 9,
        }
    }

    pub const fn record_size(self) -> usize {
        match self {
            Self::FloorRows => FLOOR_ROW_SIZE,
            Self::PathClassifier => PATH_ENTRY_SIZE,
            Self::HostClassifier => HOST_ENTRY_SIZE,
            Self::ExeClassifier => EXE_ENTRY_SIZE,
            Self::ProcessScope => PROCESS_SCOPE_ENTRY_SIZE,
            Self::InterestPaths => PATH_ENTRY_SIZE,
            Self::InterestHosts => HOST_ENTRY_SIZE,
            Self::InterestPorts => PORT_RANGE_SIZE,
            Self::ReasonTable => REASON_ENTRY_SIZE,
            Self::StringPool => STRING_POOL_UNIT_SIZE,
        }
    }
}

impl SectionEntry {
    pub fn encode(&self) -> [u8; 8] {
        let mut out = [0u8; 8];
        write_u32(&mut out, 0, self.count);
        write_u32(&mut out, 4, self.offset);
        out
    }

    pub fn decode(bytes: &[u8; 8]) -> Self {
        Self {
            count: slice_u32(bytes, 0).unwrap_or(0),
            offset: slice_u32(bytes, 4).unwrap_or(0),
        }
    }
}

impl Nanos {
    pub const fn new(ns: u64) -> Option<Self> {
        if ns == 0 || ns == u64::MAX {
            None
        } else {
            Some(Self(ns))
        }
    }

    pub const fn get(self) -> u64 {
        self.0
    }
}

impl Expiry {
    pub const fn from_header_ns(raw: u64) -> Option<Self> {
        if raw == 0 {
            None
        } else if raw == u64::MAX {
            Some(Self::ScopeEnd)
        } else {
            Some(Self::After(Nanos(raw)))
        }
    }

    pub const fn to_header_ns(self) -> u64 {
        match self {
            Self::ScopeEnd => u64::MAX,
            Self::After(ns) => ns.get(),
        }
    }
}

impl Header {
    pub fn encode(&self) -> [u8; HEADER_LEN] {
        let mut out = [0u8; HEADER_LEN];
        let _ = copy_into_slice(&mut out, 0, &self.magic);
        write_u32(&mut out, 8, self.table_format);
        write_u32(&mut out, 12, self.abi_min);
        write_u32(&mut out, 16, self.blob_len);
        let _ = copy_into_slice(&mut out, 24, &self.bundle_digest);
        write_u16(&mut out, 56, self.compiler_version_major);
        write_u16(&mut out, 58, self.compiler_version_minor);
        write_u16(&mut out, 60, self.compiler_version_patch);
        let _ = copy_into_slice(&mut out, 64, &self.effective_hash);
        let mut dir_off = 96usize;
        for entry in self.sections {
            let _ = copy_into_slice(&mut out, dir_off, &entry.encode());
            dir_off = dir_off.saturating_add(8);
        }
        write_u32(&mut out, 176, self.eval_cap);
        write_u16(&mut out, 180, self.action_class_count);
        out[182] = self.principal_kind_count;
        write_u64(&mut out, 184, self.session_rule_classes);
        write_u64(&mut out, 192, self.path_fold_classes);
        write_u64(&mut out, 200, self.expiry_bundle_ns);
        write_u64(&mut out, 208, self.expiry_session_ns);
        write_u32(&mut out, 216, self.path_max_units);
        write_u64(&mut out, 224, self.loss_closed_classes);
        out
    }

    pub fn decode(bytes: &[u8; HEADER_LEN]) -> Self {
        Self::decode_raw(bytes)
    }

    pub fn labels_bundle_tag(&self) -> u64 {
        slice_u64(&self.bundle_digest, 0).unwrap_or(0)
    }

    pub const fn section_entry(&self, section: Section) -> SectionEntry {
        let [s0, s1, s2, s3, s4, s5, s6, s7, s8, s9] = self.sections;
        match section {
            Section::FloorRows => s0,
            Section::PathClassifier => s1,
            Section::HostClassifier => s2,
            Section::ExeClassifier => s3,
            Section::ProcessScope => s4,
            Section::InterestPaths => s5,
            Section::InterestHosts => s6,
            Section::InterestPorts => s7,
            Section::ReasonTable => s8,
            Section::StringPool => s9,
        }
    }

    fn decode_raw(bytes: &[u8]) -> Self {
        let mut sections = [SectionEntry {
            count: 0,
            offset: 0,
        }; SECTION_COUNT];
        let mut dir_off = 96usize;
        for slot in &mut sections {
            if let Some(chunk) = slice_array::<8>(bytes, dir_off) {
                *slot = SectionEntry::decode(&chunk);
            }
            dir_off = dir_off.saturating_add(8);
        }

        Self {
            magic: slice_array::<8>(bytes, 0).unwrap_or([0; 8]),
            table_format: slice_u32(bytes, 8).unwrap_or(0),
            abi_min: slice_u32(bytes, 12).unwrap_or(0),
            blob_len: slice_u32(bytes, 16).unwrap_or(0),
            bundle_digest: slice_array::<32>(bytes, 24).unwrap_or([0; 32]),
            compiler_version_major: slice_u16(bytes, 56).unwrap_or(0),
            compiler_version_minor: slice_u16(bytes, 58).unwrap_or(0),
            compiler_version_patch: slice_u16(bytes, 60).unwrap_or(0),
            effective_hash: slice_array::<32>(bytes, 64).unwrap_or([0; 32]),
            sections,
            eval_cap: slice_u32(bytes, 176).unwrap_or(0),
            action_class_count: slice_u16(bytes, 180).unwrap_or(0),
            principal_kind_count: slice_u8(bytes, 182).unwrap_or(0),
            session_rule_classes: slice_u64(bytes, 184).unwrap_or(0),
            path_fold_classes: slice_u64(bytes, 192).unwrap_or(0),
            expiry_bundle_ns: slice_u64(bytes, 200).unwrap_or(0),
            expiry_session_ns: slice_u64(bytes, 208).unwrap_or(0),
            path_max_units: slice_u32(bytes, 216).unwrap_or(0),
            loss_closed_classes: slice_u64(bytes, 224).unwrap_or(0),
        }
    }
}

impl fmt::Debug for Header {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Header")
            .field("table_format", &self.table_format)
            .field("abi_min", &self.abi_min)
            .field("blob_len", &self.blob_len)
            .field("bundle_digest_len", &self.bundle_digest.len())
            .field(
                "compiler_version",
                &(
                    self.compiler_version_major,
                    self.compiler_version_minor,
                    self.compiler_version_patch,
                ),
            )
            .field("effective_hash_len", &self.effective_hash.len())
            .field("sections", &self.sections)
            .field("eval_cap", &self.eval_cap)
            .field("action_class_count", &self.action_class_count)
            .field("principal_kind_count", &self.principal_kind_count)
            .field("session_rule_classes", &self.session_rule_classes)
            .field("path_fold_classes", &self.path_fold_classes)
            .field("expiry_bundle_ns", &self.expiry_bundle_ns)
            .field("expiry_session_ns", &self.expiry_session_ns)
            .field("path_max_units", &self.path_max_units)
            .field("loss_closed_classes", &self.loss_closed_classes)
            .finish()
    }
}
