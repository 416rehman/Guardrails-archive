// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use std::fmt;

use cargo_metadata::PackageId;

use crate::finding::RuleCode;

/// Why the lint could not run. Each is exit 2; a broken rule is a finding, not an error.
#[derive(Debug)]
pub enum LintError {
    /// `cargo metadata` failed; its stderr is passed through unchanged.
    CargoMetadata {
        stderr: String,
    },
    CargoMetadataUnreadable(String),
    NoResolve,
    UnknownPackage(String),
    UnclassifiedEdge {
        from: String,
        to: String,
    },
    MissingRuleText(RuleCode),
}

impl LintError {
    pub fn from_cargo(error: cargo_metadata::Error) -> Self {
        match error {
            cargo_metadata::Error::CargoMetadata { stderr } => Self::CargoMetadata { stderr },
            other => Self::CargoMetadataUnreadable(other.to_string()),
        }
    }

    pub fn unclassified_edge(from: &PackageId, to: &PackageId) -> Self {
        Self::UnclassifiedEdge {
            from: from.repr.clone(),
            to: to.repr.clone(),
        }
    }
}

impl fmt::Display for LintError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::CargoMetadata { stderr } => f.write_str(stderr),
            Self::CargoMetadataUnreadable(detail) => {
                write!(f, "could not read the output of `cargo metadata`: {detail}")
            }
            Self::NoResolve => f.write_str("`cargo metadata` returned no dependency graph"),
            Self::UnknownPackage(id) => {
                write!(
                    f,
                    "`cargo metadata` names package `{id}` but does not list it"
                )
            }
            Self::UnclassifiedEdge { from, to } => write!(
                f,
                "`cargo metadata` gives the edge from `{from}` to `{to}` no known dependency kind"
            ),
            Self::MissingRuleText(code) => {
                write!(
                    f,
                    "architecture.toml has no `[rule.{code}]` row for a finding of {code}"
                )
            }
        }
    }
}
