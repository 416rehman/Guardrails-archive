// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
//! ARCH-001's edge half and ARCH-002: what each workspace crate's direct edges may reach.

use crate::architecture::{Architecture, DependencyLimit, Linking};
use crate::finding::{Finding, RuleCode};
use crate::graph::{EdgeKind, Graph, Member};
use crate::layer::Layer;

/// One direct edge of a workspace crate.
struct Step<'a> {
    from: &'a str,
    from_layer: Layer,
    to: &'a str,
    to_is_member: bool,
    kind: EdgeKind,
}

impl Step<'_> {
    fn verb(&self) -> &'static str {
        match self.kind {
            EdgeKind::Normal => "depends on",
            EdgeKind::Build => "has a build dependency on",
            EdgeKind::Dev => "has a dev dependency on",
        }
    }

    fn depends(&self) -> String {
        format!("`{}` {} `{}`", self.from, self.verb(), self.to)
    }
}

pub fn check(architecture: &Architecture, graph: &Graph) -> Vec<Finding> {
    graph
        .members()
        .flat_map(|member| member_findings(architecture, graph, member))
        .collect()
}

fn member_findings(architecture: &Architecture, graph: &Graph, member: Member<'_>) -> Vec<Finding> {
    let Some(from_layer) = architecture.layer_of(member.name) else {
        return Vec::new();
    };
    graph
        .edges(member.index)
        .iter()
        .filter_map(|edge| {
            let target = graph.package(edge.to)?;
            let step = Step {
                from: member.name,
                from_layer,
                to: target.name.as_str(),
                to_is_member: target.is_member(),
                kind: edge.kind,
            };
            edge_finding(architecture, &step)
        })
        .collect()
}

fn edge_finding(architecture: &Architecture, step: &Step<'_>) -> Option<Finding> {
    if architecture.linking_of(step.to) == Some(&Linking::ObjectOnly) {
        return Some(layers(format!(
            "{}, a crate built to an object that is never a Cargo dependency.",
            step.depends()
        )));
    }
    if !step.kind.links() {
        return None;
    }
    if let Some(finding) = outside_dependency_limit(architecture, step) {
        return Some(finding);
    }
    if !step.to_is_member {
        return None;
    }
    let to_layer = architecture.layer_of(step.to)?;
    layer_finding(architecture, step, to_layer)
}

fn outside_dependency_limit(architecture: &Architecture, step: &Step<'_>) -> Option<Finding> {
    let entry = architecture.crates.get(step.from)?;
    let DependencyLimit::Only(allowed) = &entry.dependencies else {
        return None;
    };
    if allowed.iter().any(|name| name == step.to) {
        return None;
    }
    Some(layers(format!(
        "{}, which is not in its `dependencies` list in architecture.toml.",
        step.depends()
    )))
}

fn layer_finding(architecture: &Architecture, step: &Step<'_>, to_layer: Layer) -> Option<Finding> {
    let (from, to) = match (step.from_layer, to_layer) {
        (_, Layer::Tool) => {
            return Some(layers(format!(
                "{}, a tool crate, which may only be a dev dependency.",
                step.depends()
            )));
        }
        (Layer::Tool, _) => return None,
        (Layer::Numbered(from), Layer::Numbered(to)) => (from, to),
    };
    let described = |layer| architecture.describe_layer(layer);
    if to > from {
        return Some(layers(format!(
            "`{}` ({}) {} `{}` ({}).",
            step.from,
            described(step.from_layer),
            step.verb(),
            step.to,
            described(to_layer)
        )));
    }
    if to < from || architecture.same_layer_edge_allowed(step.from, step.to, to_layer) {
        return None;
    }
    if to_layer == architecture.arch002.layer {
        return Some(Finding::new(
            RuleCode::ADAPTERS,
            format!(
                "{}, and both are in {}.",
                step.depends(),
                described(to_layer)
            ),
        ));
    }
    Some(layers(format!(
        "{}, both in {}, and architecture.toml lists no such same-layer edge.",
        step.depends(),
        described(to_layer)
    )))
}

fn layers(what: String) -> Finding {
    Finding::new(RuleCode::LAYERS, what)
}
