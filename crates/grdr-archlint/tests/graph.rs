// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
mod common;

use std::path::Path;

use grdr_archlint::error::LintError;
use grdr_archlint::graph::{Declaration, EdgeKind, Graph, Privilege};
use grdr_archlint::layer::Layer;

fn edges_of(graph: &Graph, name: &str) -> Vec<(String, EdgeKind)> {
    let Some(member) = graph.member_named(name) else {
        return Vec::new();
    };
    let mut edges: Vec<(String, EdgeKind)> = graph
        .edges(member.index)
        .iter()
        .filter_map(|edge| Some((graph.package(edge.to)?.name.clone(), edge.kind)))
        .collect();
    edges.sort();
    edges
}

#[test]
fn the_graph_holds_every_edge_kind_feature_and_platform() {
    let graph = Graph::read(Some(&common::fixture_manifest("graph-kinds").unwrap())).unwrap();
    assert_eq!(
        edges_of(&graph, "grdr-a"),
        [
            ("grdr-b".to_owned(), EdgeKind::Normal),
            ("grdr-c".to_owned(), EdgeKind::Normal),
            ("grdr-c".to_owned(), EdgeKind::Build),
            ("grdr-d".to_owned(), EdgeKind::Dev),
            ("serde_json".to_owned(), EdgeKind::Normal),
        ]
    );
    let members: Vec<&str> = graph.members().map(|member| member.name).collect();
    assert_eq!(members.len(), 4);
    assert!(!members.contains(&"serde_json"));
}

#[test]
fn each_member_carries_its_declaration() {
    let graph = Graph::read(Some(&common::fixture_manifest("graph-kinds").unwrap())).unwrap();
    let declaration = |name| graph.member_named(name).unwrap().declaration;
    match declaration("grdr-a") {
        Declaration::Declared(metadata) => {
            assert_eq!(metadata.layer, Layer::Numbered(4));
            assert_eq!(metadata.privilege, Privilege::Privileged);
        }
        other => panic!("grdr-a: {other:?}"),
    }
    match declaration("grdr-d") {
        Declaration::Declared(metadata) => assert_eq!(metadata.layer, Layer::Tool),
        other => panic!("grdr-d: {other:?}"),
    }
    assert!(matches!(declaration("grdr-b"), Declaration::Missing));
    match declaration("grdr-c") {
        Declaration::Invalid(reason) => assert!(reason.contains("root"), "{reason}"),
        other => panic!("grdr-c: {other:?}"),
    }
}

#[test]
fn a_failing_cargo_metadata_passes_its_stderr_through() {
    let missing = Path::new(env!("CARGO_TARGET_TMPDIR")).join("no-such-workspace/Cargo.toml");
    match Graph::read(Some(&missing)) {
        Err(LintError::CargoMetadata { stderr }) => {
            assert!(stderr.contains("no-such-workspace"), "{stderr}");
        }
        other => panic!("{other:?}"),
    }
}
