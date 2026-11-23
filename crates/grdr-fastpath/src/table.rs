// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

mod body;
mod header;
mod strings;

use core::fmt;
use core::sync::atomic::AtomicU8;

use crate::layout::{Header, Section};

const ABI_TV_RULE: u8 = 3;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Error {
    Arg(ArgFault),
    Abi,
    Bundle(BundleFault),
    State,
    Changed,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ArgFault {
    Arena,
    ActionClass,
    PrincipalKind,
    Path,
    Destination,
    Reason,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum BundleFault {
    Rule(TvRule),
    EvalCap,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct TvRule(u8);

pub struct Tables<B, A> {
    blob: B,
    arena: A,
    #[expect(
        dead_code,
        reason = "read by RC1 in eval/classify/interest (#410, #412)"
    )]
    blob_len: usize,
    #[expect(
        dead_code,
        reason = "read by RC1 in eval/classify/interest (#410, #412)"
    )]
    arena_len: usize,
    header: Header,
    #[expect(
        dead_code,
        reason = "sticky changed flag read and stored by #410 and #412 per RFC 0005 R2.12a"
    )]
    changed: AtomicU8,
}

impl TvRule {
    pub fn number(self) -> u8 {
        self.0
    }
}

impl Error {
    pub(crate) fn from_tv_rule(rule: u8) -> Self {
        if rule == ABI_TV_RULE {
            Self::Abi
        } else {
            Self::Bundle(BundleFault::Rule(TvRule(rule)))
        }
    }

    pub fn rule(&self) -> Option<u8> {
        match self {
            Self::Abi => Some(ABI_TV_RULE),
            Self::Bundle(BundleFault::Rule(tv)) => Some(tv.number()),
            Self::Arg(_) | Self::Bundle(BundleFault::EvalCap) | Self::State | Self::Changed => None,
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Debug::fmt(self, f)
    }
}

impl core::error::Error for Error {}

impl<B, A> Tables<B, A> {
    pub fn header(&self) -> &Header {
        &self.header
    }

    pub fn storage(&self) -> (&B, &A) {
        (&self.blob, &self.arena)
    }

    pub fn into_parts(self) -> (B, A) {
        (self.blob, self.arena)
    }
}

impl<B, A> fmt::Debug for Tables<B, A> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Tables")
            .field(
                "floor_rows",
                &self.header.section_entry(Section::FloorRows).count,
            )
            .field(
                "path_entries",
                &self.header.section_entry(Section::PathClassifier).count,
            )
            .field(
                "host_entries",
                &self.header.section_entry(Section::HostClassifier).count,
            )
            .field(
                "exe_entries",
                &self.header.section_entry(Section::ExeClassifier).count,
            )
            .field(
                "reason_entries",
                &self.header.section_entry(Section::ReasonTable).count,
            )
            .field(
                "string_pool_bytes",
                &self.header.section_entry(Section::StringPool).count,
            )
            .finish()
    }
}

pub fn arena_size(blob: &[u8]) -> Result<usize, Error> {
    let (_, needed) = header::validate_header(blob)?;
    Ok(needed)
}

pub fn load<B, A>(blob: B, mut arena: A) -> Result<Tables<B, A>, Error>
where
    B: AsRef<[u8]>,
    A: AsRef<[u8]> + AsMut<[u8]>,
{
    let blob_bytes = blob.as_ref();
    let (header, needed_arena) = header::validate_header(blob_bytes)?;

    let blob_len = blob_bytes.len();
    {
        let arena_bytes = arena.as_mut();
        if arena_bytes.len() < needed_arena {
            return Err(Error::Arg(ArgFault::Arena));
        }
        body::validate_body(blob_bytes, &header)?;
        body::write_arena_index(blob_bytes, &header, arena_bytes, needed_arena)?;
    }

    Ok(Tables {
        blob,
        arena,
        blob_len,
        arena_len: needed_arena,
        header,
        changed: AtomicU8::new(0),
    })
}

pub(crate) fn section_bytes<'a>(blob: &'a [u8], header: &Header, section: Section) -> &'a [u8] {
    let entry = header.section_entry(section);
    if entry.count == 0 {
        return &[];
    }
    let Some(start) = usize::try_from(entry.offset).ok() else {
        return &[];
    };
    let Some(len) = usize::try_from(entry.count)
        .ok()
        .and_then(|c| c.checked_mul(section.record_size()))
    else {
        return &[];
    };
    let Some(end) = start.checked_add(len) else {
        return &[];
    };
    blob.get(start..end).unwrap_or(&[])
}
