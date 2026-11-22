// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
mod confined;
mod content_parsers;
mod declarations;
mod layering;
#[cfg(test)]
mod tests;
mod walk;

use crate::architecture::Architecture;
use crate::finding::Finding;
use crate::graph::Graph;

/// Every finding of the graph rules, sorted by rule code and then by message, without repeats.
pub fn check(architecture: &Architecture, graph: &Graph) -> Vec<Finding> {
    let mut findings: Vec<Finding> = declarations::check(architecture, graph)
        .into_iter()
        .chain(layering::check(architecture, graph))
        .chain(content_parsers::check(architecture, graph))
        .chain(confined::check(architecture, graph))
        .collect();
    findings.sort();
    findings.dedup();
    findings
}
