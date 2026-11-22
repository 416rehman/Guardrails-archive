// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
//! ARCH-004 (ADR-0010): no content parser in the normal-dependency closure of a privileged
//! program or of `also_programs`, except what an admitted decoder brings with it.

use std::collections::BTreeSet;

use crate::architecture::Architecture;
use crate::finding::{Finding, RuleCode};
use crate::graph::{EdgeKind, Graph, Member, Privilege};
use crate::pattern::any_matches;
use crate::rules::walk::{Search, describe_path};

/// Who brought the crates below a point of the walk: the program itself, or the decoder at
/// that index of `arch004.decoder`, whose `admits` then apply.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
enum Carrier {
    Program,
    Decoder(usize),
}

/// What a crate the walk reaches is to the program being checked.
enum Reached {
    AdmittedDecoder(usize),
    Parser,
    Other,
}

/// Why a program is checked.
enum Checked {
    Privileged,
    Listed,
}

pub fn check(architecture: &Architecture, graph: &Graph) -> Vec<Finding> {
    let mut findings = Vec::new();
    for (member, checked) in checked_programs(architecture, graph) {
        findings.extend(program_findings(architecture, graph, member, &checked));
    }
    findings
}

fn checked_programs<'g>(
    architecture: &Architecture,
    graph: &'g Graph,
) -> Vec<(Member<'g>, Checked)> {
    let rule = &architecture.arch004;
    graph
        .members()
        .filter_map(|member| {
            let privileged = architecture.layer_of(member.name) == Some(rule.program_layer)
                && member
                    .declared()
                    .is_some_and(|metadata| metadata.privilege == Privilege::Privileged);
            if privileged {
                return Some((member, Checked::Privileged));
            }
            let listed = rule.also_programs.iter().any(|name| name == member.name);
            listed.then_some((member, Checked::Listed))
        })
        .collect()
}

fn program_findings(
    architecture: &Architecture,
    graph: &Graph,
    program: Member<'_>,
    checked: &Checked,
) -> Vec<Finding> {
    let mut search = Search::new((program.index, Carrier::Program));
    let mut parsers_reached = Vec::new();
    while let Some(state) = search.next() {
        let (node, carrier) = state;
        let normal_edges = graph
            .edges(node)
            .iter()
            .filter(|edge| edge.kind == EdgeKind::Normal);
        for edge in normal_edges {
            let Some(target) = graph.package(edge.to) else {
                continue;
            };
            match reached(architecture, program.name, carrier, &target.name) {
                Reached::AdmittedDecoder(index) => {
                    search.reach((edge.to, Carrier::Decoder(index)), state);
                }
                Reached::Other => search.reach((edge.to, carrier), state),
                Reached::Parser => parsers_reached.push((state, edge.to)),
            }
        }
    }
    let mut reported = BTreeSet::new();
    parsers_reached
        .into_iter()
        .filter(|(_, parser)| reported.insert(*parser))
        .filter_map(|(state, parser)| {
            let parser_name = graph.package(parser)?.name.as_str();
            let path = search.path(state).into_iter().map(|(index, _)| index);
            let path = describe_path(graph, path.chain([parser]));
            Some(parser_finding(program.name, checked, parser_name, &path))
        })
        .collect()
}

/// A parser the carrying decoder admits is `Other`: the walk goes on below it with the same
/// carrier.
fn reached(architecture: &Architecture, program: &str, carrier: Carrier, name: &str) -> Reached {
    let decoders = &architecture.arch004.decoder;
    let admitted_decoder = decoders
        .iter()
        .position(|decoder| decoder.name == name && decoder.admitted_in(program));
    if let Some(index) = admitted_decoder {
        return Reached::AdmittedDecoder(index);
    }
    if !architecture.is_content_parser(name) {
        return Reached::Other;
    }
    let admits = match carrier {
        Carrier::Program => false,
        Carrier::Decoder(index) => decoders
            .get(index)
            .is_some_and(|decoder| any_matches(&decoder.admits, name)),
    };
    if admits {
        Reached::Other
    } else {
        Reached::Parser
    }
}

fn parser_finding(program: &str, checked: &Checked, parser: &str, path: &str) -> Finding {
    let why_checked = match checked {
        Checked::Privileged => "a privileged program",
        Checked::Listed => "a program ARCH-004 checks through `also_programs`",
    };
    Finding::new(
        RuleCode::CONTENT_PARSERS,
        format!(
            "`{program}` is {why_checked}, and its closure holds the content parser `{parser}`: {path}."
        ),
    )
}
