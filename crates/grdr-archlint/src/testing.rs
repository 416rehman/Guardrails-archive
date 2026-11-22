// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use std::collections::BTreeMap;

use crate::architecture::{
    AdapterRule, Architecture, ContentParserRule, CrateEntry, DependencyLimit, Linking, Presence,
    ToolDependencies, ToolDependents, ToolRule,
};
use crate::finding::{Finding, RuleCode, RuleText};
use crate::graph::{
    Declaration, Edge, EdgeKind, Graph, GrdrMetadata, Membership, Package, Privilege,
};
use crate::layer::Layer;
use crate::pattern::NamePattern;

pub const PROGRAMS: Layer = Layer::Numbered(4);
pub const ADAPTERS: Layer = Layer::Numbered(3);

pub struct GraphBuilder {
    packages: Vec<Package>,
    outgoing: Vec<Vec<Edge>>,
}

/// The layer table of design/03 section 2 with no crates listed yet.
pub fn architecture() -> Architecture {
    let layers = [
        ("0", "schema"),
        ("1", "core"),
        ("2", "ports and shared libraries"),
        ("3", "adapters"),
        ("4", "programs"),
        ("tool", "test and tool crates"),
    ];
    let rule = [1, 2, 4, 5, 6].map(|number| {
        let code = RuleCode::try_from(format!("ARCH-{number:03}")).unwrap();
        let text = RuleText {
            why: format!("why {code}"),
            fix: format!("fix {code}"),
            escape: format!("escape {code}"),
        };
        (code, text)
    });
    Architecture {
        layers: layers
            .into_iter()
            .map(|(key, name)| (key.to_owned(), name.to_owned()))
            .collect(),
        tool: ToolRule {
            depends_on: ToolDependencies::AnyLayer,
            dependents_only_as: ToolDependents::DevOnly,
        },
        crates: BTreeMap::new(),
        families: BTreeMap::new(),
        same_layer_rule: Vec::new(),
        same_layer_edge: Vec::new(),
        arch002: AdapterRule { layer: ADAPTERS },
        arch004: ContentParserRule {
            program_layer: PROGRAMS,
            also_programs: Vec::new(),
            content_parsers: Vec::new(),
            decoder: Vec::new(),
        },
        confined: Vec::new(),
        rule: BTreeMap::from(rule),
    }
}

pub fn list<'a>(
    architecture: &'a mut Architecture,
    name: &str,
    layer: Layer,
) -> &'a mut CrateEntry {
    architecture
        .crates
        .entry(name.to_owned())
        .or_insert(CrateEntry {
            layer,
            presence: Presence::Member,
            linking: Linking::Cargo,
            dependencies: DependencyLimit::Unlimited,
        })
}

pub fn patterns(names: &[&str]) -> Vec<NamePattern> {
    names
        .iter()
        .map(|name| NamePattern::try_from((*name).to_owned()).unwrap())
        .collect()
}

pub fn codes(findings: &[Finding]) -> Vec<String> {
    findings
        .iter()
        .map(|finding| finding.rule.to_string())
        .collect()
}

impl GraphBuilder {
    pub fn new() -> Self {
        Self {
            packages: Vec::new(),
            outgoing: Vec::new(),
        }
    }

    pub fn member(self, name: &str, layer: Layer, privilege: Privilege) -> Self {
        let metadata = GrdrMetadata { layer, privilege };
        self.package(name, Membership::Member(Declaration::Declared(metadata)))
    }

    pub fn member_with(self, name: &str, declaration: Declaration) -> Self {
        self.package(name, Membership::Member(declaration))
    }

    pub fn external(self, name: &str) -> Self {
        self.package(name, Membership::External)
    }

    pub fn edge(mut self, from: &str, to: &str, kind: EdgeKind) -> Self {
        let to = self.index(to);
        let from = self.index(from);
        self.outgoing[from].push(Edge { to, kind });
        self
    }

    pub fn build(self) -> Graph {
        Graph::from_parts(self.packages, self.outgoing)
    }

    fn package(mut self, name: &str, membership: Membership) -> Self {
        self.packages.push(Package {
            name: name.to_owned(),
            membership,
        });
        self.outgoing.push(Vec::new());
        self
    }

    fn index(&self, name: &str) -> usize {
        self.packages
            .iter()
            .position(|package| package.name == name)
            .unwrap()
    }
}
