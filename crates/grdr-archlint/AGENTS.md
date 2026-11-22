# grdr-archlint

layer: tool   privilege: none   renders: agent
surface: internal   squad: core   trust core: no (its data, `architecture.toml`, is)
stability: not applicable (internal crate)
design: docs/design/03-system-architecture-and-modularity.md section 2 and work item A2; ADR-0005, ADR-0010

## Purpose
The architecture lint's graph rules: ARCH-001, ARCH-002, ARCH-004, ARCH-005 and ARCH-006 of design/03 section 2, read from `cargo metadata` and `architecture.toml`. The scan rules (ARCH-003, ARCH-007 to ARCH-026) are #1582.

## Invariants
- No rule fact in code (P14): layers, same-layer edges, the ARCH-002 layer, the ARCH-004 program layer, content parsers and decoders, the `[[confined]]` lists and the why, fix and escape text of each message are rows of `architecture.toml`. A new banned crate, decoder or driver is a data change there.
- `cargo metadata` runs with every feature on and every target platform, so an optional or platform-only edge is never missed.
- Layer rules (ARCH-001, ARCH-002), `dependencies` lists and `[[confined]]` read normal and build edges; ARCH-004 reads normal edges only. Dev edges count only against a crate with `cargo_dependency = false`, which no edge of any kind may reach.
- ARCH-004 follows paths: a decoder admitted in a program may bring the parsers its `admits` names, and nothing else below it is exempt.
- Output is sorted by rule code, then by message, so two runs on the same graph print the same text.
- No panic path in non-test code: the workspace clippy deny lints (`unwrap_used`, `expect_used`, `panic`, `indexing_slicing` and the rest of the root table).
- No `unsafe`: the workspace lints forbid it.

## Allowed dependencies
Any layer (`layer = "tool"`); nothing depends on this crate except as a dev-dependency (ARCH-001). Third-party: `cargo_metadata` and `serde`, then `toml`, as admitted in `supply-chain/admissions.toml` (#1575); the lockfile rows must equal that record.

## How to test
- `cargo test --locked -p grdr-archlint`
- Oracle: the rule rows of design/03 section 2; each rule has unit tests over graphs built in `src/testing.rs`, and `tests/graph.rs` reads a fixture workspace through real `cargo metadata`.
- Fixture workspaces live under `tests/fixtures/` and are copied to the test temporary directory before `cargo metadata` runs, so no lockfile is written into the source tree.

## Data classes
Reads: build metadata only (`cargo metadata`, `architecture.toml`). Writes: findings to stdout. Logs: none.

## Limits
Bounds in limits.toml: none (the walks visit each package and decoder pair once).

## Do not
- Write a crate name, layer number or message text into a rule; add it to `architecture.toml`.
- Depend on this crate from a shipped crate (ARCH-001).
