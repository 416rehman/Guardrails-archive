// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
//! The `[[confined]]` rules (ARCH-005, ARCH-006): listed crates appear only under the crates
//! `only_under` names. Each workspace crate answers for the third-party crates it brings in, so
//! the walk from it stops at other workspace crates, which answer for their own.

use std::collections::BTreeSet;

use crate::architecture::{Architecture, Confinement};
use crate::finding::Finding;
use crate::graph::{Graph, Member};
use crate::pattern::any_matches;
use crate::rules::walk::{Search, describe_path};

pub fn check(architecture: &Architecture, graph: &Graph) -> Vec<Finding> {
    architecture
        .confined
        .iter()
        .flat_map(|confinement| {
            graph
                .members()
                .filter(|member| {
                    !confinement
                        .only_under
                        .iter()
                        .any(|name| name == member.name)
                })
                .flat_map(|member| member_findings(graph, confinement, member))
        })
        .collect()
}

fn member_findings(graph: &Graph, confinement: &Confinement, member: Member<'_>) -> Vec<Finding> {
    let mut search = Search::new(member.index);
    let mut confined_reached = Vec::new();
    while let Some(node) = search.next() {
        let linked = graph.edges(node).iter().filter(|edge| edge.kind.links());
        for edge in linked {
            let Some(target) = graph.package(edge.to) else {
                continue;
            };
            if any_matches(&confinement.crates, &target.name) {
                confined_reached.push((node, edge.to));
            } else if !target.is_member() {
                search.reach(edge.to, node);
            }
        }
    }
    let mut reported = BTreeSet::new();
    confined_reached
        .into_iter()
        .filter(|(_, confined)| reported.insert(*confined))
        .filter_map(|(node, confined)| {
            let name = graph.package(confined)?.name.as_str();
            let path = describe_path(graph, search.path(node).into_iter().chain([confined]));
            Some(Finding::new(
                confinement.rule,
                format!(
                    "`{}` brings in `{name}`, {}, through {path}; it may appear only under {}.",
                    member.name,
                    confinement.what,
                    quoted_list(&confinement.only_under)
                ),
            ))
        })
        .collect()
}

fn quoted_list(names: &[String]) -> String {
    let quoted: Vec<String> = names.iter().map(|name| format!("`{name}`")).collect();
    quoted.join(", ")
}
