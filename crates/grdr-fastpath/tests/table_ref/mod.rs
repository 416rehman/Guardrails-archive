// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

mod body;
mod header;
mod reader;
mod strings;

type RuleFn = fn(&[u8]) -> Result<(), u8>;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RefVerdict {
    Accept,
    Reject { rule: u8, abi: bool },
}

pub fn validate_header(blob: &[u8]) -> RefVerdict {
    let rules: [RuleFn; 14] = [
        header::tv01,
        header::tv02,
        header::tv03,
        header::tv04,
        header::tv05,
        header::tv06,
        header::tv07,
        header::tv08,
        header::tv09,
        header::tv10,
        header::tv11,
        header::tv12,
        header::tv13,
        header::tv14,
    ];
    for check in rules {
        if let Err(rule) = check(blob) {
            return RefVerdict::Reject {
                rule,
                abi: rule == 3,
            };
        }
    }
    RefVerdict::Accept
}

pub fn validate(blob: &[u8]) -> RefVerdict {
    if let rej @ RefVerdict::Reject { .. } = validate_header(blob) {
        return rej;
    }
    let rules: [RuleFn; 19] = [
        body::tv15,
        body::tv16,
        body::tv17,
        strings::tv18,
        strings::tv19,
        strings::tv20,
        strings::tv21,
        strings::tv22,
        body::tv23,
        body::tv24,
        body::tv25,
        body::tv26,
        body::tv27,
        body::tv28,
        body::tv29,
        body::tv30,
        body::tv31,
        body::tv32,
        body::tv33,
    ];
    for check in rules {
        if let Err(rule) = check(blob) {
            return RefVerdict::Reject { rule, abi: false };
        }
    }
    RefVerdict::Accept
}

pub fn section_bounds_from_header(blob: &[u8]) -> Option<Vec<(usize, u64, u64)>> {
    if blob.len() < reader::HEADER_LEN {
        return None;
    }
    let mut out = Vec::new();
    for idx in 0..reader::SECTION_COUNT {
        let desc = reader::section_desc(blob, idx)?;
        if desc.count > 0 {
            let rec_size = reader::record_size(idx)?;
            let offset = u64::from(desc.offset);
            let len = u64::from(desc.count) * rec_size;
            out.push((idx, offset, len));
        }
    }
    Some(out)
}
