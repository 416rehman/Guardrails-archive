// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
//! ARCH-001's half that reads declarations: every workspace crate has a
//! `[package.metadata.grdr]` table and a row in `architecture.toml`, and the two agree.

use crate::architecture::{Architecture, Presence};
use crate::finding::{Finding, RuleCode};
use crate::graph::{Declaration, Graph, Member};

pub fn check(architecture: &Architecture, graph: &Graph) -> Vec<Finding> {
    let mut findings: Vec<Finding> = graph
        .members()
        .flat_map(|member| member_findings(architecture, member))
        .collect();
    for (name, entry) in &architecture.crates {
        if entry.presence == Presence::Member && graph.member_named(name).is_none() {
            findings.push(finding(format!(
                "architecture.toml lists `{name}` as a created workspace crate, but the workspace has no such member."
            )));
        }
    }
    findings
}

fn member_findings(architecture: &Architecture, member: Member<'_>) -> Vec<Finding> {
    let name = member.name;
    let mut findings = Vec::new();
    let listed = architecture.layer_of(name);
    match (member.declaration, listed) {
        (Declaration::Missing, _) => findings.push(finding(format!(
            "`{name}` has no `[package.metadata.grdr]` table in its manifest."
        ))),
        (Declaration::Invalid(reason), _) => findings.push(finding(format!(
            "`{name}` has a `[package.metadata.grdr]` table that does not parse: {reason}."
        ))),
        (Declaration::Declared(metadata), Some(layer)) if metadata.layer != layer => {
            findings.push(finding(format!(
                "`{name}` declares layer {} in its manifest, but architecture.toml puts it in {}.",
                metadata.layer,
                architecture.describe_layer(layer)
            )));
        }
        (Declaration::Declared(_), _) => {}
    }
    if listed.is_none() {
        findings.push(finding(format!(
            "`{name}` is a workspace crate that architecture.toml does not list."
        )));
    }
    match architecture.crates.get(name).map(|entry| &entry.presence) {
        Some(Presence::Planned) => findings.push(finding(format!(
            "`{name}` is in the workspace, but architecture.toml marks it `created = false`."
        ))),
        Some(Presence::Outside { .. }) => findings.push(finding(format!(
            "`{name}` is in the workspace, but architecture.toml marks it `member = false`."
        ))),
        Some(Presence::Member) | None => {}
    }
    findings
}

fn finding(what: String) -> Finding {
    Finding::new(RuleCode::LAYERS, what)
}
