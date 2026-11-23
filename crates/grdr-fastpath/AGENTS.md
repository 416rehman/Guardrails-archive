# grdr-fastpath

layer: 1   privilege: none   renders: none
surface: public   squad: core   trust core: yes
stability: none yet (surfaces.toml arrives with #1122)
design: docs/design/03-system-architecture-and-modularity.md section 2; notes: none yet (first content #20)

## Purpose
The `no_std` table evaluator over the compiled floor table and the shim fail-safe table, and the bounded hook-field scanner, over fixed-layout canonical little-endian inputs (design/03 sections 1 and 2; `spec/host-contract/tables.md`). It never parses in general, allocates or starts threads.

## Invariants
- Dependency edges: none yet. Every edge goes to a lower layer or is a same-layer edge of `architecture.toml` (`cargo metadata`; ARCH-001 once #1580 lands).
- No I/O, async runtime, clock or randomness; takes `now` and `entropy` (ARCH-003, ADR-0006).
- Builds for `wasm32-unknown-unknown` (ARCH-003): `cargo check --locked --target wasm32-unknown-unknown -p grdr-fastpath`.
- Checked or saturating arithmetic: `#![deny(clippy::arithmetic_side_effects)]` at the crate root (ADR-0022).
- No panic path in non-test code: the workspace clippy deny lints (`unwrap_used`, `expect_used`, `panic`, `indexing_slicing` and the rest of the root table).
- No `unsafe`: the workspace lints forbid it.
- Formats no text a person or an agent reads (`renders = "none"`).
- `#![no_std]` with no dependencies (`cargo metadata`).
- Trust core: `crates/grdr-fastpath/**` in security/trust-core.paths.

## Allowed dependencies
None: it has no dependencies (design/03 section 2).

## Where things are
| Path | What |
|---|---|
| `src/lib.rs` | Crate root (`no_std`, `forbid(unsafe_code)`), exports `layout` and `table` APIs |
| `src/table.rs` | `arena_size`, `load`, `Tables`, `Error`, `ArgFault`, `BundleFault`, `TvRule` |
| `src/table/layout/` | Canonical wire layout (`Header`, `Section`, records, `encode`/`decode`, cost functions) |
| `src/table/header.rs` | Header validation (`TV-1` to `TV-14`) |
| `src/table/strings.rs` | String pool, path patterns, canonical hostnames, and IP CIDR validation (`TV-18` to `TV-22`) |
| `src/table/body.rs` | Body section ordering, invariants, and run-index validation (`TV-15` to `TV-33`) |
| `tests/table_ref/` | Independent D-63 reference validator written directly from `spec/host-contract/tables.md` |
| `tests/fixtures/table/` | Valid blobs and isolated per-rule breaking fixtures (`TV-1` to `TV-33`) |
| `tests/table_*.rs` | Header, rule, differential, and mutation test suites (`table_header`, `table_rules`, `table_diff`, `table_mutate`) |

## How to test
- `cargo test --locked -p grdr-fastpath`
- Oracle: independent reference validator under `tests/table_ref/` (`table_diff`, `table_rules`).
- Fuzz and differential targets: deterministic differential and mutation suites in `tests/table_diff.rs` and `tests/table_mutate.rs` (run with `PROPTEST_CASES=1000000` and `--ignored soak` for 1M-case soaks).

## Data classes
Reads: `spec/host-contract/tables.md` section 14 (`public`, `operator`, `sensitive`); strings, patterns, hostnames, and buffers are treated as potentially `sensitive` and redacted in all `Debug` output. Writes: per-action-class `(start, count)` `u32` run index into caller arena (`public`). Logs: `LogSafe` only; no panic strings or raw host values escape.

## Limits
Bounds in limits.toml: none yet (limits.toml arrives with #279).

## Do not
- None recorded yet.
