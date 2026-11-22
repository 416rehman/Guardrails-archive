// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use std::collections::BTreeMap;
use std::fmt;

use serde::Deserialize;

use crate::finding::{RuleCode, RuleText};
use crate::layer::Layer;
use crate::pattern::{NamePattern, any_matches};

/// `architecture.toml`: the layer table, the same-layer edges and the rule data of design/03
/// section 2.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Architecture {
    pub layers: BTreeMap<String, String>,
    pub tool: ToolRule,
    pub crates: BTreeMap<String, CrateEntry>,
    #[serde(default)]
    pub families: BTreeMap<NamePattern, Family>,
    #[serde(default)]
    pub same_layer_rule: Vec<SameLayerRule>,
    #[serde(default)]
    pub same_layer_edge: Vec<SameLayerEdge>,
    pub arch002: AdapterRule,
    pub arch004: ContentParserRule,
    #[serde(default)]
    pub confined: Vec<Confinement>,
    pub rule: BTreeMap<RuleCode, RuleText>,
}

/// How tool crates sit in the graph. Each key takes the one value the lint implements, so data
/// that asks for another fails to load instead of being ignored.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ToolRule {
    pub depends_on: ToolDependencies,
    pub dependents_only_as: ToolDependents,
}

#[derive(Debug, Deserialize)]
pub enum ToolDependencies {
    #[serde(rename = "any")]
    AnyLayer,
}

/// Dev edges never link, so a tool crate reached only by them is never in a program.
#[derive(Debug, Deserialize)]
pub enum ToolDependents {
    #[serde(rename = "dev")]
    DevOnly,
}

#[derive(Debug, Deserialize)]
#[serde(try_from = "CrateRow")]
pub struct CrateEntry {
    pub layer: Layer,
    pub presence: Presence,
    pub linking: Linking,
    pub dependencies: DependencyLimit,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Presence {
    /// `created = false`: design/03 names the crate, the workspace does not have it yet.
    Planned,
    Member,
    /// `member = false`: outside the workspace, at `manifest`.
    Outside {
        manifest: String,
    },
}

#[derive(Debug, PartialEq, Eq)]
pub enum Linking {
    Cargo,
    /// `cargo_dependency = false`: built to an object another crate loads, so no crate may take
    /// a Cargo dependency on it.
    ObjectOnly,
}

#[derive(Debug, PartialEq, Eq)]
pub enum DependencyLimit {
    Unlimited,
    /// `dependencies = [...]`: the only crates its normal and build edges may reach.
    Only(Vec<String>),
}

/// The row as written; `CrateEntry` is what it means.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct CrateRow {
    layer: Layer,
    created: bool,
    member: Option<bool>,
    manifest: Option<String>,
    cargo_dependency: Option<bool>,
    dependencies: Option<Vec<String>>,
}

#[derive(Debug, PartialEq, Eq)]
pub struct CrateRowError(&'static str);

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Family {
    pub layer: Layer,
}

/// Every crate of `layer`, except those in `except`, may depend on `to`.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SameLayerRule {
    pub layer: Layer,
    pub to: String,
    #[serde(default)]
    pub except: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SameLayerEdge {
    pub from: String,
    pub to: String,
    pub scope: Option<String>,
}

/// ARCH-002: crates of `layer` never depend on each other.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AdapterRule {
    pub layer: Layer,
}

/// ARCH-004 (ADR-0010): the closures of the privileged crates of `program_layer`, and of
/// `also_programs`, hold no content parser except through an admitted decoder.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContentParserRule {
    pub program_layer: Layer,
    #[serde(default)]
    pub also_programs: Vec<String>,
    pub content_parsers: Vec<NamePattern>,
    #[serde(default)]
    pub decoder: Vec<Decoder>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Decoder {
    #[serde(rename = "crate")]
    pub name: String,
    pub decodes: String,
    /// The programs whose closure may hold it; absent means every closure ARCH-004 checks.
    pub only_in: Option<Vec<String>>,
    /// The content parsers it may bring with it.
    #[serde(default)]
    pub admits: Vec<NamePattern>,
}

/// Crates that may appear only under the crates `only_under` names (ARCH-005, ARCH-006).
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Confinement {
    pub rule: RuleCode,
    pub what: String,
    pub crates: Vec<NamePattern>,
    pub only_under: Vec<String>,
}

impl Architecture {
    /// The layer of a crate: its own row, else the first family whose pattern it matches.
    pub fn layer_of(&self, name: &str) -> Option<Layer> {
        if let Some(entry) = self.crates.get(name) {
            return Some(entry.layer);
        }
        self.families
            .iter()
            .find(|(pattern, _)| pattern.matches(name))
            .map(|(_, family)| family.layer)
    }

    pub fn linking_of(&self, name: &str) -> Option<&Linking> {
        self.crates.get(name).map(|entry| &entry.linking)
    }

    /// "layer 1, core", from the `[layers]` table.
    pub fn describe_layer(&self, layer: Layer) -> String {
        let key = layer.to_string();
        match self.layers.get(&key) {
            Some(name) => format!("layer {key}, {name}"),
            None => format!("layer {key}"),
        }
    }

    pub fn same_layer_edge_allowed(&self, from: &str, to: &str, layer: Layer) -> bool {
        let listed = self
            .same_layer_edge
            .iter()
            .any(|edge| edge.from == from && edge.to == to);
        let by_rule = self.same_layer_rule.iter().any(|rule| {
            rule.layer == layer && rule.to == to && !rule.except.iter().any(|name| name == from)
        });
        listed || by_rule
    }

    pub fn is_content_parser(&self, name: &str) -> bool {
        any_matches(&self.arch004.content_parsers, name)
    }
}

impl Decoder {
    pub fn admitted_in(&self, program: &str) -> bool {
        match &self.only_in {
            Some(programs) => programs.iter().any(|name| name == program),
            None => true,
        }
    }
}

impl TryFrom<CrateRow> for CrateEntry {
    type Error = CrateRowError;

    fn try_from(row: CrateRow) -> Result<Self, Self::Error> {
        let presence = match (row.created, row.member, row.manifest) {
            (false, None, None) => Presence::Planned,
            (false, _, _) => {
                return Err(CrateRowError(
                    "a crate with `created = false` takes no `member` or `manifest`",
                ));
            }
            (true, None | Some(true), None) => Presence::Member,
            (true, Some(false), Some(manifest)) => Presence::Outside { manifest },
            (true, Some(false), None) => {
                return Err(CrateRowError(
                    "a crate with `member = false` needs `manifest`",
                ));
            }
            (true, _, Some(_)) => {
                return Err(CrateRowError(
                    "only a crate with `member = false` takes `manifest`",
                ));
            }
        };
        let linking = match row.cargo_dependency {
            None | Some(true) => Linking::Cargo,
            Some(false) => Linking::ObjectOnly,
        };
        let dependencies = match row.dependencies {
            None => DependencyLimit::Unlimited,
            Some(names) => DependencyLimit::Only(names),
        };
        Ok(Self {
            layer: row.layer,
            presence,
            linking,
            dependencies,
        })
    }
}

impl fmt::Display for CrateRowError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.0)
    }
}
