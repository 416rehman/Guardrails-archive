// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
//! The architecture lint's graph rules (design/03 section 2): ARCH-001, ARCH-002, ARCH-004,
//! ARCH-005 and ARCH-006, read from `architecture.toml` and `cargo metadata`.

pub mod architecture;
pub mod error;
pub mod finding;
pub mod graph;
pub mod layer;
pub mod pattern;
mod rules;
#[cfg(test)]
mod testing;

pub use rules::check;

use architecture::Architecture;
use error::LintError;
use finding::Finding;

/// The four-part messages of `findings`, in order.
pub fn render(architecture: &Architecture, findings: &[Finding]) -> Result<String, LintError> {
    findings
        .iter()
        .map(|finding| {
            finding
                .render(&architecture.rule)
                .ok_or(LintError::MissingRuleText(finding.rule))
        })
        .collect()
}
