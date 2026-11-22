// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use super::check;
use crate::architecture::{
    Confinement, Decoder, DependencyLimit, Linking, Presence, SameLayerEdge, SameLayerRule,
};
use crate::finding::RuleCode;
use crate::graph::{Declaration, EdgeKind, Privilege};
use crate::layer::Layer;
use crate::testing::{ADAPTERS, GraphBuilder, PROGRAMS, architecture, codes, list, patterns};

const CORE: Layer = Layer::Numbered(1);
const PORTS: Layer = Layer::Numbered(2);

#[test]
fn an_edge_to_a_higher_layer_is_arch_001() {
    let mut arch = architecture();
    list(&mut arch, "grdr-core", CORE);
    list(&mut arch, "grdr-store-local", ADAPTERS);
    let graph = GraphBuilder::new()
        .member("grdr-core", CORE, Privilege::None)
        .member("grdr-store-local", ADAPTERS, Privilege::None)
        .edge("grdr-core", "grdr-store-local", EdgeKind::Normal)
        .build();
    let findings = check(&arch, &graph);
    assert_eq!(codes(&findings), ["ARCH-001"]);
    assert_eq!(
        findings[0].what,
        "`grdr-core` (layer 1, core) depends on `grdr-store-local` (layer 3, adapters)."
    );
}

#[test]
fn a_build_edge_counts_and_a_dev_edge_does_not() {
    let mut arch = architecture();
    list(&mut arch, "grdr-core", CORE);
    list(&mut arch, "grdr-ports", PORTS);
    let build = GraphBuilder::new()
        .member("grdr-core", CORE, Privilege::None)
        .member("grdr-ports", PORTS, Privilege::None)
        .edge("grdr-core", "grdr-ports", EdgeKind::Build)
        .build();
    assert_eq!(codes(&check(&arch, &build)), ["ARCH-001"]);
    let dev = GraphBuilder::new()
        .member("grdr-core", CORE, Privilege::None)
        .member("grdr-ports", PORTS, Privilege::None)
        .edge("grdr-core", "grdr-ports", EdgeKind::Dev)
        .build();
    assert!(check(&arch, &dev).is_empty());
}

#[test]
fn a_same_layer_edge_passes_only_when_listed() {
    let mut arch = architecture();
    list(&mut arch, "grdr-wire", PORTS);
    list(&mut arch, "grdr-crypto", PORTS);
    let graph = |from: &str, to: &str| {
        GraphBuilder::new()
            .member("grdr-wire", PORTS, Privilege::None)
            .member("grdr-crypto", PORTS, Privilege::None)
            .edge(from, to, EdgeKind::Normal)
            .build()
    };
    let unlisted = check(&arch, &graph("grdr-crypto", "grdr-wire"));
    assert_eq!(codes(&unlisted), ["ARCH-001"]);
    assert!(unlisted[0].what.contains("lists no such same-layer edge"));
    arch.same_layer_edge.push(SameLayerEdge {
        from: "grdr-wire".to_owned(),
        to: "grdr-crypto".to_owned(),
        scope: None,
    });
    assert!(check(&arch, &graph("grdr-wire", "grdr-crypto")).is_empty());
    assert_eq!(
        codes(&check(&arch, &graph("grdr-crypto", "grdr-wire"))),
        ["ARCH-001"]
    );
}

#[test]
fn a_same_layer_rule_admits_every_crate_but_its_exceptions() {
    let mut arch = architecture();
    for name in ["grdr-model", "grdr-core", "grdr-fastpath"] {
        list(&mut arch, name, CORE);
    }
    arch.same_layer_rule.push(SameLayerRule {
        layer: CORE,
        to: "grdr-model".to_owned(),
        except: vec!["grdr-fastpath".to_owned()],
    });
    let graph = |from: &str| {
        GraphBuilder::new()
            .member("grdr-model", CORE, Privilege::None)
            .member("grdr-core", CORE, Privilege::None)
            .member("grdr-fastpath", CORE, Privilege::None)
            .edge(from, "grdr-model", EdgeKind::Normal)
            .build()
    };
    assert!(check(&arch, &graph("grdr-core")).is_empty());
    assert_eq!(codes(&check(&arch, &graph("grdr-fastpath"))), ["ARCH-001"]);
}

#[test]
fn a_non_dev_edge_to_a_tool_crate_is_arch_001_and_a_tool_crate_depends_on_anything() {
    let mut arch = architecture();
    list(&mut arch, "grdr-daemon", PROGRAMS);
    list(&mut arch, "grdr-archlint", Layer::Tool);
    let graph = |from: &str, to: &str, kind| {
        GraphBuilder::new()
            .member("grdr-daemon", PROGRAMS, Privilege::None)
            .member("grdr-archlint", Layer::Tool, Privilege::None)
            .edge(from, to, kind)
            .build()
    };
    let normal = check(
        &arch,
        &graph("grdr-daemon", "grdr-archlint", EdgeKind::Normal),
    );
    assert_eq!(codes(&normal), ["ARCH-001"]);
    assert!(normal[0].what.contains("a tool crate"));
    assert!(check(&arch, &graph("grdr-daemon", "grdr-archlint", EdgeKind::Dev)).is_empty());
    assert!(
        check(
            &arch,
            &graph("grdr-archlint", "grdr-daemon", EdgeKind::Normal)
        )
        .is_empty()
    );
}

#[test]
fn any_cargo_edge_to_an_object_only_crate_is_arch_001() {
    let mut arch = architecture();
    list(&mut arch, "grdr-daemon", PROGRAMS);
    list(&mut arch, "grdr-sensor-linux-bpf", ADAPTERS).linking = Linking::ObjectOnly;
    arch.crates
        .get_mut("grdr-sensor-linux-bpf")
        .unwrap()
        .presence = Presence::Outside {
        manifest: "bpf/grdr-sensor-linux-bpf/Cargo.toml".to_owned(),
    };
    for kind in [EdgeKind::Normal, EdgeKind::Build, EdgeKind::Dev] {
        let graph = GraphBuilder::new()
            .member("grdr-daemon", PROGRAMS, Privilege::None)
            .external("grdr-sensor-linux-bpf")
            .edge("grdr-daemon", "grdr-sensor-linux-bpf", kind)
            .build();
        let findings = check(&arch, &graph);
        assert_eq!(codes(&findings), ["ARCH-001"], "{kind:?}");
        assert!(findings[0].what.contains("never a Cargo dependency"));
    }
}

#[test]
fn a_dependency_outside_a_crates_dependencies_list_is_arch_001() {
    let mut arch = architecture();
    list(&mut arch, "grdr-fastpath", CORE).dependencies = DependencyLimit::Only(Vec::new());
    list(&mut arch, "grdr-fastpath-ffi", CORE).dependencies =
        DependencyLimit::Only(vec!["grdr-fastpath".to_owned()]);
    arch.same_layer_edge.push(SameLayerEdge {
        from: "grdr-fastpath-ffi".to_owned(),
        to: "grdr-fastpath".to_owned(),
        scope: None,
    });
    let graph = GraphBuilder::new()
        .member("grdr-fastpath", CORE, Privilege::None)
        .member("grdr-fastpath-ffi", CORE, Privilege::None)
        .external("libc")
        .edge("grdr-fastpath-ffi", "grdr-fastpath", EdgeKind::Normal)
        .edge("grdr-fastpath-ffi", "libc", EdgeKind::Normal)
        .edge("grdr-fastpath", "libc", EdgeKind::Build)
        .edge("grdr-fastpath", "libc", EdgeKind::Dev)
        .build();
    let findings = check(&arch, &graph);
    assert_eq!(codes(&findings), ["ARCH-001", "ARCH-001"]);
    assert!(
        findings
            .iter()
            .all(|finding| finding.what.contains("`dependencies` list"))
    );
}

#[test]
fn an_edge_between_two_adapters_is_arch_002() {
    let mut arch = architecture();
    list(&mut arch, "grdr-agents", ADAPTERS);
    list(&mut arch, "grdr-store-local", ADAPTERS);
    let graph = GraphBuilder::new()
        .member("grdr-agents", ADAPTERS, Privilege::None)
        .member("grdr-store-local", ADAPTERS, Privilege::None)
        .edge("grdr-agents", "grdr-store-local", EdgeKind::Normal)
        .build();
    assert_eq!(codes(&check(&arch, &graph)), ["ARCH-002"]);
}

#[test]
fn a_family_gives_its_layer_to_crates_it_matches() {
    let mut arch = architecture();
    arch.families.insert(
        patterns(&["grdr-sandbox-*"]).remove(0),
        crate::architecture::Family { layer: ADAPTERS },
    );
    list(&mut arch, "grdr-agents", ADAPTERS);
    let graph = GraphBuilder::new()
        .member("grdr-agents", ADAPTERS, Privilege::None)
        .member("grdr-sandbox-nono", ADAPTERS, Privilege::None)
        .edge("grdr-agents", "grdr-sandbox-nono", EdgeKind::Normal)
        .build();
    assert_eq!(codes(&check(&arch, &graph)), ["ARCH-002"]);
}

#[test]
fn a_crate_without_metadata_or_a_row_is_arch_001() {
    let mut arch = architecture();
    list(&mut arch, "grdr-core", CORE);
    let graph = GraphBuilder::new()
        .member_with("grdr-core", Declaration::Missing)
        .member("grdr-stray", CORE, Privilege::None)
        .build();
    let findings = check(&arch, &graph);
    assert_eq!(codes(&findings), ["ARCH-001", "ARCH-001"]);
    let text: Vec<&str> = findings
        .iter()
        .map(|finding| finding.what.as_str())
        .collect();
    assert!(
        text.iter()
            .any(|what| what.contains("`grdr-core` has no `[package.metadata.grdr]`"))
    );
    assert!(text.iter().any(|what| {
        what.contains("`grdr-stray` is a workspace crate that architecture.toml does not list")
    }));
}

#[test]
fn metadata_and_architecture_toml_must_agree() {
    let mut arch = architecture();
    list(&mut arch, "grdr-core", CORE);
    list(&mut arch, "grdr-mcp-proto", CORE).presence = Presence::Planned;
    list(&mut arch, "grdr-model", CORE);
    let graph = GraphBuilder::new()
        .member("grdr-core", PORTS, Privilege::None)
        .member("grdr-mcp-proto", CORE, Privilege::None)
        .member_with(
            "grdr-wire",
            Declaration::Invalid("unknown variant `root`".to_owned()),
        )
        .build();
    let findings = check(&arch, &graph);
    let text: Vec<&str> = findings
        .iter()
        .map(|finding| finding.what.as_str())
        .collect();
    assert_eq!(codes(&findings), ["ARCH-001"; 5]);
    assert!(
        text.iter()
            .any(|what| what.contains("`grdr-core` declares layer 2"))
    );
    assert!(
        text.iter()
            .any(|what| what.contains("`grdr-mcp-proto` is in the workspace"))
    );
    assert!(text.iter().any(|what| {
        what.contains("`grdr-wire` has a `[package.metadata.grdr]` table that does not parse")
    }));
    assert!(
        text.iter()
            .any(|what| what.contains("`grdr-wire` is a workspace crate"))
    );
    assert!(
        text.iter()
            .any(|what| what.contains("lists `grdr-model` as a created workspace crate"))
    );
}

fn arch004_architecture() -> crate::architecture::Architecture {
    let mut arch = architecture();
    for name in ["grdr-daemon", "grdr-hook", "grdr-engine", "grdr-updater"] {
        list(&mut arch, name, PROGRAMS);
    }
    list(&mut arch, "grdr-proto", Layer::Numbered(0));
    list(&mut arch, "grdr-update", ADAPTERS);
    arch.arch004.also_programs = vec!["grdr-hook".to_owned()];
    arch.arch004.content_parsers =
        patterns(&["grdr-core", "grdr-update", "rsigma-*", "serde_json"]);
    arch.arch004.decoder = vec![
        Decoder {
            name: "grdr-proto".to_owned(),
            decodes: "IPC frames".to_owned(),
            only_in: None,
            admits: Vec::new(),
        },
        Decoder {
            name: "grdr-update".to_owned(),
            decodes: "TUF metadata".to_owned(),
            only_in: Some(vec!["grdr-updater".to_owned()]),
            admits: patterns(&["serde_json"]),
        },
    ];
    arch
}

fn arch004_graph() -> GraphBuilder {
    GraphBuilder::new()
        .member("grdr-daemon", PROGRAMS, Privilege::Privileged)
        .member("grdr-hook", PROGRAMS, Privilege::Untrusted)
        .member("grdr-engine", PROGRAMS, Privilege::Sandboxed)
        .member("grdr-updater", PROGRAMS, Privilege::Privileged)
        .member("grdr-proto", Layer::Numbered(0), Privilege::None)
        .member("grdr-update", ADAPTERS, Privilege::None)
        .external("serde_json")
        .external("rsigma-eval")
        .external("glue")
}

#[test]
fn serde_json_under_grdr_daemon_is_arch_004_with_its_path() {
    let graph = arch004_graph()
        .edge("grdr-daemon", "glue", EdgeKind::Normal)
        .edge("glue", "serde_json", EdgeKind::Normal)
        .build();
    let findings = check(&arch004_architecture(), &graph);
    assert_eq!(codes(&findings), ["ARCH-004"]);
    assert_eq!(
        findings[0].what,
        "`grdr-daemon` is a privileged program, and its closure holds the content parser `serde_json`: grdr-daemon -> glue -> serde_json."
    );
}

#[test]
fn arch004_checks_also_programs_and_name_prefixes_but_not_other_programs() {
    let graph = arch004_graph()
        .edge("grdr-hook", "rsigma-eval", EdgeKind::Normal)
        .edge("grdr-engine", "serde_json", EdgeKind::Normal)
        .build();
    let findings = check(&arch004_architecture(), &graph);
    assert_eq!(codes(&findings), ["ARCH-004"]);
    assert!(
        findings[0]
            .what
            .starts_with("`grdr-hook` is a program ARCH-004 checks")
    );
}

#[test]
fn arch004_reads_normal_edges_only() {
    let graph = arch004_graph()
        .edge("grdr-daemon", "serde_json", EdgeKind::Build)
        .edge("grdr-daemon", "glue", EdgeKind::Dev)
        .edge("glue", "serde_json", EdgeKind::Normal)
        .build();
    assert!(check(&arch004_architecture(), &graph).is_empty());
}

#[test]
fn a_decoder_brings_only_what_it_admits_and_only_where_it_is_admitted() {
    let arch = arch004_architecture();
    let through_decoder = arch004_graph()
        .edge("grdr-updater", "grdr-update", EdgeKind::Normal)
        .edge("grdr-update", "serde_json", EdgeKind::Normal)
        .build();
    assert!(check(&arch, &through_decoder).is_empty());

    let also_direct = arch004_graph()
        .edge("grdr-updater", "grdr-update", EdgeKind::Normal)
        .edge("grdr-update", "serde_json", EdgeKind::Normal)
        .edge("grdr-updater", "serde_json", EdgeKind::Normal)
        .build();
    let findings = check(&arch, &also_direct);
    assert_eq!(codes(&findings), ["ARCH-004"]);
    assert!(findings[0].what.ends_with("grdr-updater -> serde_json."));

    let outside_only_in = arch004_graph()
        .edge("grdr-daemon", "grdr-update", EdgeKind::Normal)
        .build();
    let findings = check(&arch, &outside_only_in);
    assert_eq!(codes(&findings), ["ARCH-004"]);
    assert!(findings[0].what.contains("content parser `grdr-update`"));

    let not_admitted = arch004_graph()
        .edge("grdr-daemon", "grdr-proto", EdgeKind::Normal)
        .edge("grdr-proto", "serde_json", EdgeKind::Normal)
        .build();
    let findings = check(&arch, &not_admitted);
    assert_eq!(codes(&findings), ["ARCH-004"]);
    assert!(
        findings[0]
            .what
            .ends_with("grdr-daemon -> grdr-proto -> serde_json.")
    );
}

fn confined_architecture() -> crate::architecture::Architecture {
    let mut arch = architecture();
    list(&mut arch, "grdr-crypto", PORTS);
    list(&mut arch, "grdr-wire", PORTS);
    list(&mut arch, "grdr-daemon", PROGRAMS);
    arch.same_layer_edge.push(SameLayerEdge {
        from: "grdr-wire".to_owned(),
        to: "grdr-crypto".to_owned(),
        scope: None,
    });
    arch.confined.push(Confinement {
        rule: RuleCode::try_from("ARCH-006".to_owned()).unwrap(),
        what: "a cryptography crate".to_owned(),
        crates: patterns(&["ring", "aws-lc-*"]),
        only_under: vec!["grdr-crypto".to_owned()],
    });
    arch
}

#[test]
fn a_confined_crate_under_its_owner_passes() {
    let graph = GraphBuilder::new()
        .member("grdr-crypto", PORTS, Privilege::None)
        .member("grdr-wire", PORTS, Privilege::None)
        .member("grdr-daemon", PROGRAMS, Privilege::Privileged)
        .external("rustls")
        .external("aws-lc-rs")
        .edge("grdr-daemon", "grdr-wire", EdgeKind::Normal)
        .edge("grdr-wire", "grdr-crypto", EdgeKind::Normal)
        .edge("grdr-crypto", "rustls", EdgeKind::Normal)
        .edge("rustls", "aws-lc-rs", EdgeKind::Normal)
        .build();
    assert!(check(&confined_architecture(), &graph).is_empty());
}

#[test]
fn a_confined_crate_outside_its_owner_is_reported_at_the_crate_that_brings_it() {
    let graph = GraphBuilder::new()
        .member("grdr-crypto", PORTS, Privilege::None)
        .member("grdr-wire", PORTS, Privilege::None)
        .member("grdr-daemon", PROGRAMS, Privilege::Privileged)
        .external("rustls")
        .external("ring")
        .edge("grdr-daemon", "grdr-wire", EdgeKind::Normal)
        .edge("grdr-wire", "rustls", EdgeKind::Build)
        .edge("rustls", "ring", EdgeKind::Normal)
        .edge("grdr-daemon", "ring", EdgeKind::Dev)
        .build();
    let findings = check(&confined_architecture(), &graph);
    assert_eq!(codes(&findings), ["ARCH-006"]);
    assert_eq!(
        findings[0].what,
        "`grdr-wire` brings in `ring`, a cryptography crate, through grdr-wire -> rustls -> ring; it may appear only under `grdr-crypto`."
    );
}

#[test]
fn findings_come_out_sorted_by_code_then_text() {
    let mut arch = confined_architecture();
    list(&mut arch, "grdr-core", CORE);
    let graph = GraphBuilder::new()
        .member("grdr-crypto", PORTS, Privilege::None)
        .member("grdr-wire", PORTS, Privilege::None)
        .member("grdr-daemon", PROGRAMS, Privilege::Privileged)
        .member("grdr-core", CORE, Privilege::None)
        .external("ring")
        .edge("grdr-daemon", "ring", EdgeKind::Normal)
        .edge("grdr-core", "grdr-wire", EdgeKind::Normal)
        .edge("grdr-core", "grdr-daemon", EdgeKind::Normal)
        .build();
    let findings = check(&arch, &graph);
    assert_eq!(codes(&findings), ["ARCH-001", "ARCH-001", "ARCH-006"]);
    let mut sorted = findings.clone();
    sorted.sort();
    assert_eq!(findings, sorted);
}
