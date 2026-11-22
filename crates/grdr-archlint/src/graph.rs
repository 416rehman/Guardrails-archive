// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use std::collections::{BTreeSet, HashMap, HashSet};
use std::path::Path;

use cargo_metadata::{CargoOpt, DependencyKind, Metadata, MetadataCommand, Node, PackageId};
use serde::Deserialize;

use crate::error::LintError;
use crate::layer::Layer;

const METADATA_TABLE: &str = "grdr";

/// The dependency graph of a workspace, from `cargo metadata` with every feature on and every
/// target platform included.
#[derive(Debug)]
pub struct Graph {
    packages: Vec<Package>,
    outgoing: Vec<Vec<Edge>>,
}

#[derive(Debug)]
pub struct Package {
    pub name: String,
    pub membership: Membership,
}

/// A workspace member as the rules see it.
#[derive(Clone, Copy, Debug)]
pub struct Member<'a> {
    pub index: usize,
    pub name: &'a str,
    pub declaration: &'a Declaration,
}

#[derive(Debug)]
pub enum Membership {
    Member(Declaration),
    External,
}

/// A workspace crate's `[package.metadata.grdr]` table.
#[derive(Debug)]
pub enum Declaration {
    Missing,
    Invalid(String),
    Declared(GrdrMetadata),
}

#[derive(Debug, Deserialize)]
pub struct GrdrMetadata {
    pub layer: Layer,
    pub privilege: Privilege,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Privilege {
    Privileged,
    Sandboxed,
    Untrusted,
    None,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum EdgeKind {
    Normal,
    Build,
    Dev,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Edge {
    pub to: usize,
    pub kind: EdgeKind,
}

impl Graph {
    pub fn read(manifest_path: Option<&Path>) -> Result<Self, LintError> {
        let mut command = MetadataCommand::new();
        command.features(CargoOpt::AllFeatures);
        if let Some(path) = manifest_path {
            command.manifest_path(path);
        }
        let metadata = command.exec().map_err(LintError::from_cargo)?;
        Self::from_metadata(&metadata)
    }

    pub fn from_metadata(metadata: &Metadata) -> Result<Self, LintError> {
        let index: HashMap<&PackageId, usize> = metadata
            .packages
            .iter()
            .enumerate()
            .map(|(position, package)| (&package.id, position))
            .collect();
        let members: HashSet<&PackageId> = metadata.workspace_members.iter().collect();
        let packages = metadata
            .packages
            .iter()
            .map(|package| Package {
                name: package.name.as_ref().to_owned(),
                membership: if members.contains(&package.id) {
                    Membership::Member(Declaration::read(package.metadata.get(METADATA_TABLE)))
                } else {
                    Membership::External
                },
            })
            .collect();
        let resolve = metadata.resolve.as_ref().ok_or(LintError::NoResolve)?;
        let mut outgoing = vec![Vec::new(); metadata.packages.len()];
        for node in &resolve.nodes {
            let from = position(&index, &node.id)?;
            let edges = node_edges(&index, node)?;
            if let Some(slot) = outgoing.get_mut(from) {
                *slot = edges;
            }
        }
        Ok(Self { packages, outgoing })
    }

    #[cfg(test)]
    pub fn from_parts(packages: Vec<Package>, outgoing: Vec<Vec<Edge>>) -> Self {
        Self { packages, outgoing }
    }

    /// Workspace members, in `cargo metadata` order.
    pub fn members(&self) -> impl Iterator<Item = Member<'_>> {
        self.packages
            .iter()
            .enumerate()
            .filter_map(|(index, package)| match &package.membership {
                Membership::Member(declaration) => Some(Member {
                    index,
                    name: package.name.as_str(),
                    declaration,
                }),
                Membership::External => None,
            })
    }

    pub fn package(&self, index: usize) -> Option<&Package> {
        self.packages.get(index)
    }

    pub fn edges(&self, index: usize) -> &[Edge] {
        self.outgoing.get(index).map_or(&[], Vec::as_slice)
    }

    pub fn member_named(&self, name: &str) -> Option<Member<'_>> {
        self.members().find(|member| member.name == name)
    }
}

impl Package {
    pub fn is_member(&self) -> bool {
        matches!(self.membership, Membership::Member(_))
    }
}

impl Member<'_> {
    pub fn declared(&self) -> Option<&GrdrMetadata> {
        match self.declaration {
            Declaration::Declared(metadata) => Some(metadata),
            Declaration::Missing | Declaration::Invalid(_) => None,
        }
    }
}

impl Declaration {
    fn read<'a, V>(table: Option<&'a V>) -> Self
    where
        &'a V: serde::Deserializer<'a>,
        <&'a V as serde::Deserializer<'a>>::Error: std::fmt::Display,
    {
        match table {
            None => Self::Missing,
            Some(table) => match GrdrMetadata::deserialize(table) {
                Ok(metadata) => Self::Declared(metadata),
                Err(error) => Self::Invalid(error.to_string()),
            },
        }
    }
}

impl EdgeKind {
    fn from_cargo(kind: DependencyKind) -> Option<Self> {
        match kind {
            DependencyKind::Normal => Some(Self::Normal),
            DependencyKind::Build => Some(Self::Build),
            DependencyKind::Development => Some(Self::Dev),
            DependencyKind::Unknown => None,
        }
    }

    /// Normal and build edges put the target in the crate's build; dev edges only in its tests.
    pub fn links(self) -> bool {
        matches!(self, Self::Normal | Self::Build)
    }
}

fn position(index: &HashMap<&PackageId, usize>, id: &PackageId) -> Result<usize, LintError> {
    index
        .get(id)
        .copied()
        .ok_or_else(|| LintError::UnknownPackage(id.repr.clone()))
}

/// One edge per dependency kind, so a crate that is both a normal and a build dependency gives
/// two.
fn node_edges(index: &HashMap<&PackageId, usize>, node: &Node) -> Result<Vec<Edge>, LintError> {
    let mut edges = BTreeSet::new();
    for dependency in &node.deps {
        let to = position(index, &dependency.pkg)?;
        let unclassified = || LintError::unclassified_edge(&node.id, &dependency.pkg);
        if dependency.dep_kinds.is_empty() {
            return Err(unclassified());
        }
        for info in &dependency.dep_kinds {
            let kind = EdgeKind::from_cargo(info.kind).ok_or_else(unclassified)?;
            edges.insert(Edge { to, kind });
        }
    }
    Ok(edges.into_iter().collect())
}
