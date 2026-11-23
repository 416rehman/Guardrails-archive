RFC: 0022
Title: grdr.common.v1alpha1 ErrorDetail and ErrorClass, and Code::detail() in grdr-schema (amends RFC 0007)
Author: chief-architect
Harness: antigravity
Model: Gemini 4 Neon
State: Review
Design issue: #1851
Spine: P1, P2, P8, P9, P14, P17, D-15, D-35, D-39, D-60, D-61, D-63, D-66, D-69
Surfaces: proto/grdr/common/v1alpha1/error.proto, crates/grdr-schema/enums.toml, crates/grdr-schema/src/codes/detail.rs (grdr_schema::codes::Code::detail, From<&Code>, From<Code>), grdr_proto::grdr::common::v1alpha1::{ErrorClass, ErrorDetail}
Decision record: none yet

Comments go on the design issue, so commenting needs no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

## Summary

This RFC specifies the wire protobuf contract `proto/grdr/common/v1alpha1/error.proto` (`ErrorClass` and `ErrorDetail`), registers `ErrorClass` as a closed enum in `crates/grdr-schema/enums.toml`, defines `Code::detail(&self) -> grdr_proto::grdr::common::v1alpha1::ErrorDetail` (plus `From<&Code>` and `From<Code>`) inside `crates/grdr-schema/src/codes/detail.rs`, and coordinates with [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md), [RFC 0007](./0007-grdr-model-and-grdr-schema-slice-0-surface.md), [RFC 0016](./0016-health-condition-registry.md), and [RFC 0017](./0017-grdr-strings-language-token-runtime.md) to unblock `#280`, `#1384`, and `#1853`.

Every field of `ErrorDetail` is tagged `[(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL]` and derived deterministically from a sealed `grdr_schema::codes::Code` with zero caller arguments. The RFC explicitly resolves `#1851` Questions 1 to 4, settles RFC 0007 Decision Constraint 2c (rejecting `component`, `rule_id`, and `bound_name` fields on `ErrorDetail`), amends RFC 0007 across six points (same-layer edge to `grdr-proto`, single allocating exception `Code::detail()`, `layout` admission for `codes/detail.rs`, unknown/unspecified `ErrorClass` fallback to `internal`, whole-string ASCII plus pinned-namespace wire-code validation, and `security/trust-core.paths`), prepares both SP-1 (`#368`) candidate codec shapes while holding implementation binding on `#368`, and keeps `serde_json` out of normal dependencies (`ARCH-004`).

## Motivation

Guardrails separates stable machine-readable error identifiers from locale rendering and dynamic context (`design/04` section 1, `design/23` section 3, `D-15`, `P8`):

1. **Single wire representation (`P17`).** Connect RPC status details (`google.rpc.ErrorInfo` + `ErrorDetail`), CLI `--json` `error` envelopes, desktop/tray IPC, and broker error responses need one schema for structured error metadata so wire surfaces do not invent divergent error structs.
2. **Offline, locale-deferred tokens (`D-66`, `D-69`).** Privileged binaries and wire boundaries emit language token identifiers (`code.<area>_<nnnn>.message`, `code.<area>_<nnnn>.fix`) and host-free doc anchors (`codes/<PREFIX>-<AREA>-<NNNN>`) rather than pre-rendered prose or hard-coded URLs.
3. **Completion of RFC 0007 deferred seams.** [RFC 0007](./0007-grdr-model-and-grdr-schema-slice-0-surface.md) adopted the Rust `Code`, `CodeEntry`, and `ErrorClass` surface while leaving `#280` and `#1851` as explicit placeholders because `grdr.common.v1alpha1.options`, `enums.toml`, and `grdr-proto` codec selection did not yet exist. [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md) ([ADR-0052](../docs/decisions/ADR-0052-grdr-common-v1alpha1-options-and-sp1-crates-adopted-by-rfc-0006.md)), [RFC 0016](./0016-health-condition-registry.md) ([ADR-0050](../docs/decisions/ADR-0050-health-condition-registry-adopted-by-rfc-0016.md)), and [RFC 0017](./0017-grdr-strings-language-token-runtime.md) ([ADR-0055](../docs/decisions/ADR-0055-grdr-strings-language-token-runtime-adopted-by-rfc-0017.md)) now provide those building blocks, allowing `#1851` to close the wire-to-Rust error boundary before `#280`, `#1384`, and `#1853` implement against it.

## Design

### 1. Protobuf schema `proto/grdr/common/v1alpha1/error.proto` (R1)

`#280` creates `proto/grdr/common/v1alpha1/error.proto` under `package grdr.common.v1alpha1` (`syntax = "proto3"`). The file imports only `"grdr/common/v1alpha1/options.proto"` as a non-public import ([RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md) R1, R4, SL10; never `google/protobuf/descriptor.proto`). Concise proto comments on `ErrorClass` and `ErrorDetail` serve as generated reference prose (`design/34` section 2).

```protobuf
syntax = "proto3";

package grdr.common.v1alpha1;

import "grdr/common/v1alpha1/options.proto";

// Operational error category used by callers, retries, and breakers.
// Closed enum: ERROR_CLASS_UNSPECIFIED (0) and any unrecognised wire tag
// outside 1..=5 MUST be handled as ERROR_CLASS_INTERNAL (never retried).
enum ErrorClass {
  ERROR_CLASS_UNSPECIFIED = 0;
  ERROR_CLASS_INPUT = 1 [(grdr.common.v1alpha1.wire_name) = "input"];
  ERROR_CLASS_POLICY = 2 [(grdr.common.v1alpha1.wire_name) = "policy"];
  ERROR_CLASS_RETRYABLE = 3 [(grdr.common.v1alpha1.wire_name) = "retryable"];
  ERROR_CLASS_FATAL = 4 [(grdr.common.v1alpha1.wire_name) = "fatal"];
  ERROR_CLASS_INTERNAL = 5 [(grdr.common.v1alpha1.wire_name) = "internal"];
}

// Structured error metadata projected deterministically from a registered
// grdr_schema::codes::Code. Every field carries structural telemetry only.
message ErrorDetail {
  reserved 900 to 999;

  // Stable namespace-prefixed error code, such as "GRDR-CFG-0007".
  string code = 1 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];

  // Stable UPPER_SNAKE reason identifier matching ErrorInfo.reason.
  string reason = 2 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];

  // Operational action class derived from the code's registry definition.
  ErrorClass class = 3 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];

  // Language token key for the user-facing summary message.
  string message_token = 4 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];

  // Language token key for the suggested remediation step.
  string fix_token = 5 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];

  // Host-free documentation path anchor ("codes/<PREFIX>-<AREA>-<NNNN>").
  string docs_anchor = 6 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
}
```

RFC 0006 schema-lint rules hold verbatim:
- **Closed enum (`SL05`, `SL12`):** `ErrorClass` declares no `_OTHER = 99` value and is listed in `crates/grdr-schema/enums.toml` as a closed enum.
- **`(grdr.common.v1alpha1.wire_name)` (`R12`, `SL04`):** Value `0` (`ERROR_CLASS_UNSPECIFIED`) sets no `wire_name`; values `1..=5` set `"input"`, `"policy"`, `"retryable"`, `"fatal"`, and `"internal"`, matching `grdr_schema::codes::ErrorClass::as_str()` identically.
- **`(grdr.common.v1alpha1.data_class)` (`SL01`):** Every field `1..=6` carries explicit `[(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL]`.
- **`(grdr.common.v1alpha1.content_kind)` (`SL02`):** Intentionally omitted on all six fields because RFC 0006 `SL02` restricts `content_kind` strictly to `DATA_CLASS_CONTENT` fields. None of the six fields holds event content, user text, secrets, or path payloads, so `grdr_schema::capture` passes all six structural fields across telemetry and diagnostics without withholding or redaction.
- **Reserved seal band (`SL06`, `D-35`, `D-39`):** `reserved 900 to 999;` matches `design/04` section 1 rule 5 and satisfies `SL06` (no declared field in `900..=999`).
- **Lint & descriptor parity:** `buf lint` (`STANDARD` + `WIRE_JSON`, `disallow_comment_ignores: true`), `buf breaking`, `grdr-schema-lint` (`SL01..SL13`), and regenerated `crates/grdr-proto/descriptors/proto.binpb` (plus `capture.rs` / `registry.rs`) must pass clean in `#280`.

### 2. Canonical ProtoJSON profile and zero-`serde_json` runtime edge (R2)

Consistent with `design/04` section 15 and `#280` R5:
- **Encoding:** Canonical ProtoJSON renders `ErrorDetail` with lowerCamelCase keys (`code`, `reason`, `class`, `messageToken`, `fixToken`, `docsAnchor`). `class` encodes using `(grdr.common.v1alpha1.wire_name)` strings (`"input"`, `"policy"`, `"retryable"`, `"fatal"`, `"internal"`). `ERROR_CLASS_UNSPECIFIED (0)` omits `class` (or decodes from absent/`null`/`0`/`"ERROR_CLASS_UNSPECIFIED"`), and an unknown non-zero integer `i32` preserves its numeric value rather than coercing to a label.
- **Decoding:** ProtoJSON decoders accept both lowerCamelCase and snake_case field keys, and accept `(wire_name)` strings, proto enum names (`ERROR_CLASS_*`), or numeric `i32` values for `class`.
- **No `serde_json` normal edge (`ARCH-004`, [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md) R28):** Neither `grdr-proto` nor `grdr-schema` may add `serde_json` or any JSON parser as a normal or build dependency. Privileged closures (`grdr-daemon`, `grdr-updater`, `grdr-approve`) must remain free of `content_parsers` (`ARCH-004`). `#280`'s `error_detail_json` test uses `serde_json` (already recorded in `supply-chain/admissions.toml`) strictly inside `[dev-dependencies]` alongside `buf convert` JSON fixtures. Runtime JSON emission for HTTP/Connect gateways and CLI `--json` sits in unprivileged layer 3/4 consumers reading `ErrorDetail`.

### 3. `Code::detail()` and `From` conversions in `grdr-schema` (Question 4, R3)

**Question 4 decision:** `Code::detail()` lives on `grdr_schema::codes::Code` in `crates/grdr-schema/src/codes/detail.rs` (declared as private `mod detail;` inside `crates/grdr-schema/src/codes.rs`), alongside `impl From<&Code> for grdr_proto::grdr::common::v1alpha1::ErrorDetail` and `impl From<Code> for grdr_proto::grdr::common::v1alpha1::ErrorDetail`.

Why `grdr-schema` owns `Code::detail()` rather than `grdr-proto`:
1. `architecture.toml` already lists the same-layer dependency `grdr-schema -> grdr-proto`, whereas `grdr-proto` has `depends_on = []` (zero workspace dependencies) and holds generated protobuf definitions only (`design/04` section 1).
2. Putting `Code::detail()` in `grdr-proto` would reverse the dependency graph, violate `grdr-proto`'s generated-only contract, and hit Rust's orphan rules (forcing callers to import an extension trait instead of calling `code.detail()`).
3. Declaring `mod detail;` directly in `codes.rs` (sibling to `registry`, `table`, and `types`, NOT nested under `codes::registry`) preserves `Code` and `CodeEntry` struct-expression sealing via `codes::generated::Seal` without widening `Seal`'s visibility (`RFC 0007` section 2).

Public API contract in `crates/grdr-schema/src/codes/detail.rs`:

```rust
use grdr_proto::grdr::common::v1alpha1::{ErrorClass as WireErrorClass, ErrorDetail};

impl Code {
    /// Returns the wire-safe structural detail projected solely from this registered code.
    #[must_use]
    pub fn detail(&self) -> ErrorDetail { ... }
}

impl From<&Code> for ErrorDetail {
    fn from(code: &Code) -> Self {
        code.detail()
    }
}

impl From<Code> for ErrorDetail {
    fn from(code: Code) -> Self {
        code.detail()
    }
}
```

Field projection (total, zero caller strings, `#1851` AC-3):

| `ErrorDetail` field | Derived value from `let entry = self.entry();` | Contract guarantee |
|---|---|---|
| `code` | `self.as_str().to_owned()` | `<PREFIX>-<AREA>-<NNNN>` from `brand/brand.toml [identity] namespace` + area + 4 ASCII digits |
| `reason` | `entry.reason().to_owned()` | Stable `UPPER_SNAKE` reason token matching `google.rpc.ErrorInfo.reason` |
| `class` | Exhaustive match on `self.class()` (`codes::ErrorClass`) to `WireErrorClass` `1..=5` | Never emits `ERROR_CLASS_UNSPECIFIED (0)`; zero wildcard `_` arm |
| `message_token` | `entry.message_token().to_owned()` | Lowercase `code.<area>_<nnnn>.message` (`RFC 0007` section 3, `RFC 0017` parity) |
| `fix_token` | `entry.fix_token().to_owned()` | Lowercase `code.<area>_<nnnn>.fix` (`RFC 0007` section 3, `RFC 0017` parity) |
| `docs_anchor` | `entry.anchor().to_owned()` | Host-free `codes/<PREFIX>-<AREA>-<NNNN>` (`RFC 0007` section 3) |

**Token naming correction for `#280`:** `#280` AC-1 currently gives a pre-RFC-0007 example `"code.GRDR-CFG-0007.message"`. `RFC 0007` section 3 and `RFC 0017` bind `CodeEntry::message_token()` and `CodeEntry::fix_token()` to `"code.<area>_<nnnn>.message"` and `"code.<area>_<nnnn>.fix"` (for example `"code.cfg_0007.message"` and `"code.cfg_0007.fix"`). `#280` must align its specification and assertions with `CodeEntry::message_token()` and `CodeEntry::fix_token()` verbatim.

**Infallibility and lints:** Because `Code` is sealed to valid compiled active entries (`Seal`) and the five `codes::ErrorClass` variants map exhaustively to tags `1..=5`, `Code::detail(&self)` is total and infallible (no `Result`, no panic path, no indexing, no `unsafe`, and `#![deny(clippy::arithmetic_side_effects)]` passes).

**Dual SP-1 codec preparation (`#368` hold, `#1851` AC-9):** `#368` (SP-1) is open at review time, so `#280` holds final codec binding until `#368` closes. Crucially, the public signature `Code::detail(&self) -> grdr_proto::grdr::common::v1alpha1::ErrorDetail` is **identical** under both SP-1 candidates (`sp1-buffa` and `sp1-prost`), with `grdr-schema` defining zero Cargo features of its own (`manifests` / `RFC 0007`):
- **If `sp1-buffa` wins:** `WireErrorClass` is wrapped in `buffa::EnumValue<WireErrorClass>` (`buffa::EnumValue::from(wire_class)` in `detail.rs`), and the `ErrorDetail` struct literal ends with `..Default::default()` for buffa's unknown-fields/cached-size slots.
- **If `sp1-prost` wins:** `ErrorDetail::class` is `i32` (`wire_class as i32` in `detail.rs`), paired with prost's typed enum helpers (`set_class` / `class()`), and unit tests verify the remaining fields match `1..=6` with no divergence.

### 4. Single definition of `ErrorClass` across Rust and proto (Question 1, `P17`, R4)

**Question 1 decision:** Because `grdr-schema` depends on `grdr-proto`, generating `proto` from `grdr-schema` or `codes::ErrorClass` from `proto` at `build.rs` time would introduce a workspace dependency cycle or violate RFC 0006's zero-`build.rs` invariant on `grdr-schema`. Parity is instead enforced by a two-part mechanism (`P17`):

1. **Compile-time forward exhaustiveness (`codes/detail.rs`):** `match self.class()` enumerates every variant of `grdr_schema::codes::ErrorClass` (`Input`, `Policy`, `Retryable`, `Fatal`, `Internal`) with no wildcard `_` arm. Adding or renaming a variant in `codes::ErrorClass` immediately breaks `grdr-schema` compilation until mapped.
2. **Closed-enum registration and descriptor parity test (`enums.toml` + `tests/error_detail.rs`):**
   - `crates/grdr-schema/enums.toml` registers `grdr.common.v1alpha1.ErrorClass` as closed (`SL05`, `SL12`), blocking unreviewed wire additions or `_OTHER = 99` leaks.
   - `crates/grdr-schema/tests/error_detail.rs` asserts a strict bijection between `codes::ErrorClass::VARIANTS` and the `grdr_schema::registry` descriptor metadata generated from `proto.binpb` (`RFC 0006` R13a / `#2095`):
     - Total enum values in `grdr.common.v1alpha1.ErrorClass` equal `codes::ErrorClass::VARIANTS.len() + 1` (tags `0..=5`, no extra tag).
     - Tag `0` (`ERROR_CLASS_UNSPECIFIED`) carries no `wire_name`.
     - Each `v` in `codes::ErrorClass::VARIANTS` maps 1:1 to a distinct non-zero tag `1..=5` whose descriptor `(grdr.common.v1alpha1.wire_name)` equals `v.as_str()`, and whose `Code::detail()` output matches round-trip wire encoding/decoding.
     - Under closed-enum codegen (such as `sp1-buffa`), a reverse `match` helper in `tests/error_detail.rs` enumerates all variants of generated `pb::ErrorClass` with no wildcard arm so any extra proto value fails test compilation immediately.

Sequencing note: if `#280` merges before `#2095` materialises `grdr_schema::registry`, `#280` checks exhaustive Rust mapping, `enums.toml` entry, and wire tag assertions for `1..=5`, and `#2095` activates the descriptor-metadata bijection check in `tests/error_detail.rs`.

### 5. Unknown `ErrorClass` handling and wire-code validation (Question 2, R5)

**Unknown or unspecified `ErrorClass` on the wire (`#280` R6, `P9`):**
- Wire codecs MUST preserve unrecognised non-zero `ErrorClass` integers on decode and re-encode (`buffa::EnumValue::Unknown(n)` or prost `i32` field; numeric `i32` in ProtoJSON).
- Every behavioural consumer that dispatches on `ErrorDetail.class` (`grdr-ports::retry::faults_peer` under [RFC 0008](./0008-clock-entropy-and-the-retry-executor.md), Connect/HTTP clients, CLI, MCP broker, desktop/tray notifications, export mappers) MUST treat both `ERROR_CLASS_UNSPECIFIED (0)` and any unknown integer `i32` outside `1..=5` as `internal` (`codes::ErrorClass::Internal`, wire name `"internal"`):
  - **Never retried:** automatic retry loops MUST NOT classify `0` or unknown `ErrorClass` integers as `retryable`.
  - **Never success:** absence of a known class never degrades into success or ignores the error.
  - **Accounted as internal defect:** surfaces as an internal/peer protocol mismatch.
- **Amends RFC 0007 section 3 & section 12:** RFC 0007 sections 3 and 12 stated that unknown error class words default to `fatal` when interpreting untrusted/newer class metadata. This RFC amends RFC 0007 so unknown or unspecified wire `ErrorClass` values (`0` or unrecognised `i32`) MUST map to `internal` (`P9`), preserving `fatal` exclusively for confirmed domain failures (`ERROR_CLASS_FATAL = 4`) while keeping `ConnectCode` and `ErrorClass` orthogonal (RFC 0007 sections 7 and 9's candidate pairing `ConnectCode::Unavailable` with a non-`retryable` `ErrorClass` such as `fatal` or `internal` remains permitted and tested across RFC 0008's 80-cell `faults_peer` table).

**Wire `code` validation and foreign-prefix separation (amends RFC 0007 section 3, for `#1853`):**
When an untrusted or cross-version peer supplies `ErrorDetail.code` over the wire, consumers MUST NOT use prefix-only checks (`starts_with("GRDR-")`) or Unicode character predicates:
1. **Whole-string ASCII grammar (`&[u8]`):** The full byte slice MUST match `^[A-Z]{2,8}-[A-Z]{2,8}-[0-9]{4}$` using strict ASCII byte checks (`b.is_ascii_uppercase()` and `b.is_ascii_digit()`), matching the whole string with zero leading/trailing whitespace, zero line breaks (`\n`), zero bidi/control characters, zero non-ASCII digits, and zero path segments (`..`, `/`, `\`).
2. **Pinned namespace match:** The leading 2-to-8-byte prefix before the first `-` MUST equal `[identity] namespace` upper-cased from `brand/brand.toml` (`"GRDR"` for upstream Guardrails).
3. **Three-way rendering rule (`#1853` coordination):**
   - *Known active code* (passes 1 & 2 and exists in `codes::ALL`): render normal registered message token, fix token, and `/codes/<code>` link.
   - *Valid newer-peer code* (passes 1 & 2, absent from `codes::ALL`): render the validated code string and `{docs_base_url}/<locale>/codes/<code>` link alongside `#1853`'s unrecognised-newer-peer fallback token.
   - *Malformed grammar or foreign prefix* (fails 1 or fails 2): emit ONLY `#1853`'s unrecognised-code placeholder token, emitting NO echoed code string and NO `/codes/` link.

### 6. `docs_anchor` derivation (Question 3, R6)

**Question 3 decision:** `ErrorDetail.docs_anchor` is `CodeEntry::anchor()` verbatim (`"codes/<PREFIX>-<AREA>-<NNNN>"`, such as `"codes/GRDR-CFG-0007"`).
- No URL scheme, host, port, or locale enters `ErrorDetail` (`design/34` section 6, `design/28`).
- Callers combine local configuration (`docs.base_url`) and active UI locale (`{docs_base_url}/<locale>/<docs_anchor>`) so air-gapped deployments and white-labelled forks (`brand/brand.toml`, `D-66`) resolve local documentation cleanly.
- No extra registry key is added; `CodeEntry::anchor()` remains the single source of truth (`P17`). Degraded and critical health runbooks (`RFC 0016` / `docs/runbooks/`) remain separate from `ErrorDetail.docs_anchor`.

### 7. Reconciliation with RFC 0007 Decision Constraint 2c (R7)

During RFC 0007 acceptance (`ADR-0038`), Seat 1 raised Decision Constraint 2c asking whether `ErrorDetail` should carry structural contextual fields (`component`, `rule_id`, `bound_name`).

**Decision:** `ErrorDetail` keeps **strictly the six code-derived fields** (`1..=6`) and adds **no** `component`, `rule_id`, `bound_name`, or caller-supplied argument fields (`#1851` AC-2, AC-3; `#280` Non-goals; `design/04` section 1).

Rationale and where structured context belongs (`P8`, `P17`, `D-69`):
1. `RFC 0007` section 3 forbids error codes from naming policy rules or enforcement verdicts; keeping `Code::detail(&self)` zero-argument makes it impossible to smuggle unvalidated dynamic strings into structural code metadata.
2. Policy enforcement context (`component`, `rule_id`, `pack`, `person_route`, `agent_next`) belongs in `grdr.decide.v1alpha1.BlockNotice` (`#1384`, `#1537`, `design/28`). `#1384` MUST read `component` and `rule_id` from `BlockNotice` rather than `ErrorDetail`.
3. Typed template arguments (including `limits.toml` bound names tagged with `DataClass::Structural` or `DataClass::Identifier`) travel in `grdr.common.v1alpha1.MessageRef` (defined in its own proto RFC following [RFC 0017](./0017-grdr-strings-language-token-runtime.md)) or in `google.rpc.ErrorInfo.metadata` paired with `ErrorDetail` inside RPC `Status.details` (`design/23` section 3).

### 8. Explicit RFC 0007 amendments and RFC 0006 / RFC 0016 coordination (R8)

Accepting this RFC records the following explicit amendments to [RFC 0007](./0007-grdr-model-and-grdr-schema-slice-0-surface.md) ([ADR-0038](../docs/decisions/ADR-0038-the-grdr-model-and-grdr-schema-slice-0-surface-adopted-by-rfc-0007.md)) and layout alignments with [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md) and [RFC 0016](./0016-health-condition-registry.md):

1. **RFC 0007 section 2 R1 (Dependencies):** Amend from zero dependencies to allow `grdr-schema` to exercise its listed same-layer dependency edge in `architecture.toml` on `grdr-proto` (`grdr-proto = { version = "0.1.0", path = "../grdr-proto" }`) as its sole normal workspace dependency. Normal third-party direct dependencies on `grdr-schema` remain zero.
2. **RFC 0007 section 2 R3 (No allocation):** Amend so `Code::detail(&self)` (and its `From` impls in `codes::detail`) is the single documented heap-allocating entry point in `grdr-schema` (allocating the `String` fields of protobuf `ErrorDetail`). All registry, limit, health, capture, and field-registry queries (`codes`, `limits`, `health`, `capture`, `registry`) remain zero-allocation `Copy` types. `grdr-schema` retains zero Cargo features, zero I/O, zero clocks/randomness, `#![forbid(unsafe_code)]`, `#![deny(clippy::arithmetic_side_effects)]`, and `wasm32-unknown-unknown` builds.
3. **RFC 0007 section 2 R10 (`layout`) coordinated with RFC 0016 & RFC 0006:** Admit `crates/grdr-schema/src/codes/detail.rs` as a sibling submodule declared via `mod detail;` inside `crates/grdr-schema/src/codes.rs`. `crates/grdr-schema/tests/construction.rs` `layout` test's exhaustive source set becomes: `lib.rs`, `{codes, limits, health}.rs` with `{types, table, tests}.rs` plus `codes/detail.rs`, and RFC 0006's `capture.rs`, `registry.rs`, `registry/**`. `crates/grdr-schema/src/lib.rs` continues declaring plain `pub mod` lines only (`RFC 0006` `manifests` / `lib.rs` rule).
4. **RFC 0007 section 3 & section 12 (Unknown class & wire-code rule):** Amend unknown/unspecified `ErrorClass` handling from `fatal` to `internal`, and amend wire-code parsing to require whole-string ASCII `^[A-Z]{2,8}-[A-Z]{2,8}-[0-9]{4}$` plus exact prefix equality with `[identity] namespace` from `brand/brand.toml`.
5. **RFC 0007 section 8 (`security/trust-core.paths`):** Add `crates/grdr-schema/src/codes/detail.rs` to `security/trust-core.paths` alongside `crates/grdr-schema/src/codes.rs` and `crates/grdr-schema/Cargo.toml` so changes to enum mapping, allocation surface, or field projection require full trust-core review.
6. **RFC 0007 sections 7 & 9 (`ConnectCode::Unavailable` pairing):** Clarify that `ConnectCode` and `ErrorClass` stay orthogonal; `Unavailable` paired with `fatal` or `internal` remains legal in `codes::ALL` and covered by RFC 0008's 80-cell `faults_peer` matrix.
7. **RFC 0016 (`ADR-0050`, `#2056`, `#2057`) coordination:** Health conditions in `schema/health.toml` and `health.<name>.*` tokens stay disjoint from `ErrorDetail` and `Code::detail()`. Language token keys emitted by `Code::detail()` (`code.<area>_<nnnn>.message`, `code.<area>_<nnnn>.fix`) coordinate cleanly with `#2057`'s token registration under [RFC 0010](./0010-code-tokens-before-the-token-check.md).
8. **Stability (`surfaces.toml`, `#1851` AC-6):** No new `surfaces.toml` row is needed. `grdr.common.v1alpha1` is already filed as `experimental` by [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md) (`#2094`), and `grdr-schema` is already filed as `experimental` by [RFC 0007](./0007-grdr-model-and-grdr-schema-slice-0-surface.md) (`#1942`). Both `ErrorClass` and `ErrorDetail` inherit `experimental` (`D-60`, [ADR-0020](../docs/decisions/ADR-0020-stability-classes-live-in-surfaces-toml.md)).

### 9. `ARCH-004` privileged-closure and `wasm32` accounting (R9)

- `grdr-fastpath` is `#![no_std]` and links neither `grdr-schema` nor `grdr-proto`.
- Privileged binaries linking `grdr-schema` (`grdr-daemon`, `grdr-updater`, `grdr-approve`; `grdr-daemon` already links `grdr-proto` for IPC) add `grdr-proto` to their normal closure:
  - **Under `sp1-buffa`:** `13` normal-edge packages (`buffa` / `buffa-types` `0.9.2` transitive closure per [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md)).
  - **Under `sp1-prost`:** `11` normal-edge packages (`prost` / `prost-types` `0.14.6` transitive closure per [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md)).
- `grdr-proto` is an admitted `ARCH-004` protobuf decoder (`admits = []`) with zero `content_parsers` and zero `serde_json` normal edges (`RFC 0006` R28).
- `cargo check --locked --target wasm32-unknown-unknown -p grdr-schema` must exit `0` when `#280` adds the `grdr-proto` dependency.

### 10. Invariants and failure modes (R10)

| Invariant | Enforcement mechanism |
|---|---|
| `Code::detail()` is total and zero-arg | Sealed `Code` (`Seal`), exhaustive `match self.class()` in `codes/detail.rs`, no `Result` or panic paths |
| All 6 fields are `DATA_CLASS_STRUCTURAL` | `proto/grdr/common/v1alpha1/error.proto` + `SL01` / `SL02` + `SL12` (`grdr-schema-lint`) |
| `ErrorClass` has a single 1:1 definition | Compile-time match in `codes/detail.rs` + `enums.toml` (`SL05`) + `tests/error_detail.rs` bijection check |
| Unknown / `0` `ErrorClass` maps to `internal` | Codec preserves raw `i32`; consumer dispatchers route `0` and unknown `i32` to `internal`, never retry |
| Wire codes prevent spoofing and injection | Whole-string ASCII `^[A-Z]{2,8}-[A-Z]{2,8}-[0-9]{4}$` + `[identity] namespace` equality in `#1853` |
| No JSON parser in `grdr-schema` / `grdr-proto` | `ARCH-004` + `RFC 0006` R28; `serde_json` confined to `[dev-dependencies]` in `#280` |

| Failure | Outcome | Visible as |
|---|---|---|
| Variant added to `codes::ErrorClass` without updating proto/match | `grdr-schema` fails to compile (`codes/detail.rs`); descriptor bijection test fails | Compiler error and CI `rust` gate |
| Value added to `ErrorClass` in `.proto` without updating `enums.toml` or tests | `grdr-schema-lint` `SL05` / `SL12` exits 1; descriptor test fails | CI `schema-gate` and `tests/error_detail.rs` |
| Field added to `ErrorDetail` without `DATA_CLASS_STRUCTURAL` or via caller args | `SL01` / `SL12` rejects proto change; review blocks extra fields (Constraint 2c) | CI `schema-gate` and evaluator review |
| Unrecognised wire `ErrorClass` (`0` or `99`) received from newer/faulty peer | Raw integer preserved in wire struct; behavioural consumer treats as `internal` without retrying | `tests/error_detail.rs` and retry unit tests |
| Untrusted peer sends `"OTHER-CFG-0001"` or `"GRDR-CFG-0007\n"` | Fails ASCII grammar or namespace check; renders `#1853` placeholder only with no echoed string or `/codes/` link | `#1853` negative test suite |
| `serde_json` added to normal `[dependencies]` of `grdr-schema` or `grdr-proto` | `ARCH-004` check fails privileged-closure / decoder policy | CI `archlint` gate |

### 11. Follow-up work items and write-backs (R11)

On acceptance (`ADR-*` issued on `#1851`):
- **Update `#280` (`grdr-schema` `ErrorDetail`, `ErrorClass`, `Code::detail()`):**
  - Keep `#280` held until `#368` closes (`AC-9`) alongside its `#353`, `#386`, and `#278` prerequisites.
  - Fix AC-1 token casing example from `"code.GRDR-CFG-0007.message"` to `"code.cfg_0007.message"` matching RFC 0007 section 3 and `CodeEntry::message_token()`.
  - Require `proto/grdr/common/v1alpha1/error.proto`, `crates/grdr-schema/enums.toml`, regenerated `proto.binpb` / `capture.rs` / `registry.rs`, `crates/grdr-schema/src/codes/detail.rs` (`mod detail;` in `codes.rs`), updated `tests/construction.rs` `layout`, `tests/error_detail.rs` (dev-only `serde_json`), `crates/grdr-schema/Cargo.toml` (`grdr-proto` path dependency), `wasm32-unknown-unknown` build verification, and `RFC: 0022` in the PR body.
  - Add `crates/grdr-schema/src/codes/detail.rs` to `security/trust-core.paths` (via `#280`'s trust-core lane or a dedicated protected gate item).
- **Update `#1384` (`BlockNotice`):** Record Constraint 2c's disposition that `BlockNotice` carries `component`, `rule_id`, `pack`, `person_route`, and `agent_next` in `grdr.decide.v1alpha1` and does not read them from `ErrorDetail`.
- **Update `#1853` (CLI / UI code display):** Record the exact whole-string ASCII `^[A-Z]{2,8}-[A-Z]{2,8}-[0-9]{4}$` and `[identity] namespace` validation rule for wire codes, plus the three-way rendering split.
- **File RFC 0007 / design-doc alignment item:** Update `docs/design/03` (same-layer `grdr-schema -> grdr-proto` note if helpful, `ARCH-004` privileged-closure reference), `docs/design/04` (`ErrorDetail` / `ErrorClass` section 1 and 15 cross-links), `docs/design/23` (`ErrorInfo` + `ErrorDetail` parity), and `docs/design/34` (`docs_anchor` / `code.<area>_<nnnn>.*` parity), reflecting the six RFC 0007 amendments and `#2095` descriptor-test handoff.

## Surfaces changed

| Surface | Class | At v1 freeze |
|---|---|---|
| `proto/grdr/common/v1alpha1/error.proto` (`ErrorClass`, `ErrorDetail`) | `experimental` (`#2094`) | Renamed `v1`; field numbers `1..=6` and enum values `0..=5` preserved |
| `ErrorClass` `(grdr.common.v1alpha1.wire_name)` values (`input`, `policy`, `retryable`, `fatal`, `internal`) | `experimental` | Kept; changes require RFC + `reclassifications.toml` entry |
| `crates/grdr-schema/src/codes/detail.rs` (`Code::detail()`, `From<&Code>`, `From<Code>`) | `experimental` (`#1942`) | Signatures preserved across codecs and v1 promotion |
| `crates/grdr-schema/enums.toml` (`ErrorClass` closed entry) | gate data, trust core | Kept closed; new values require RFC + `SL12` |
| `security/trust-core.paths` (`crates/grdr-schema/src/codes/detail.rs`) | gate data, trust core | Retained as trust-core path |

- **Data classes (`P8`):** All six fields on `ErrorDetail` carry explicit `DATA_CLASS_STRUCTURAL` and zero `content_kind`. No event content, user prompt, path, or secret enters `ErrorDetail`.
- **Assurance effect (`P1`):** None. Unknown wire `ErrorClass` handling fails closed to `internal` with zero automatic retries (`P9`), and malformed/foreign wire codes emit no echoed string or link.
- **`surfaces.toml` and spine:** Zero new `surfaces.toml` rows (`#2094` and `#1942` cover both surfaces) and zero spine text changes.
- **Dependencies:** Uses the SP-1 (`#368`) winning codec inside `grdr-proto` and dev-only `serde_json` already in `supply-chain/admissions.toml`; adds zero new third-party crates.

## Alternatives

- **Place `Code::detail()` or `impl From<Code> for ErrorDetail` in `grdr-proto`.** Rejected. `grdr-proto` has `depends_on = []` (no workspace dependencies) and holds generated protobuf modules only (`architecture.toml`, `design/04`). Placing conversions in `grdr-proto` reverses the edge, breaks generated-only guarantees, and prevents an inherent `Code::detail()` method due to Rust's orphan rule.
- **Place `detail.rs` inside `crates/grdr-schema/src/codes/registry/`.** Rejected. `Code` and `CodeEntry` use module-private struct sealing (`codes::generated::Seal` in `RFC 0007`). Adding a sibling `mod detail;` directly in `codes.rs` keeps `Seal` encapsulation untouched.
- **Generate `codes::ErrorClass` from `.proto` (or `.proto` from `grdr-schema`) via `build.rs`.** Rejected. [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md) forbids `build.rs` on `grdr-schema`, and cross-crate codegen introduces cyclic build dependencies. Compile-time exhaustive matching plus `enums.toml` and descriptor-registry CI assertions enforce the 1:1 invariant without build scripts.
- **Include `component`, `rule_id`, or `bound_name` fields on `ErrorDetail` (Constraint 2c option).** Rejected. Breaks `#1851` AC-2/AC-3, `RFC 0007` section 3, and `P17` by blurring static error identity with policy verdicts and parameterised message rendering; those belong in `BlockNotice`, `MessageRef`, and `ErrorInfo.metadata`.
- **Make `ErrorDetail.class` an open enum (`ERROR_CLASS_OTHER = 99`) or string, or default unknown values to `fatal`.** Rejected. `SL05` requires closed enums for action categories, `design/04` specifies typed enum + `(wire_name)`, and mapping unknown wire values (`0` or out-of-range `i32`) to `internal` accurately models protocol/peer mismatch without triggering retries or claiming semantic finality.
- **Add feature-gated `serde_json` serialisation to `grdr-proto` or `grdr-schema`.** Rejected under `ARCH-004` and `RFC 0006` R28 so privileged binaries linking `grdr-schema` or `grdr-proto` never risk Cargo feature unification dragging `serde_json` into normal dependency closures.
- **Bake host URL or locale prefix into `ErrorDetail.docs_anchor`.** Rejected under `D-66` and `design/34` section 6 because anchors must resolve offline against configurable `docs.base_url` and local viewer locale.

## Drawbacks

- **Closure footprint on privileged `grdr-schema` consumers:** Privileged programs that depend on `grdr-schema` (`grdr-daemon`, `grdr-updater`, `grdr-approve`) pull `grdr-proto` (`13` normal packages under `sp1-buffa`, or `11` under `sp1-prost`), though `grdr-daemon` already links `grdr-proto` and `#![no_std]` `grdr-fastpath` does not link `grdr-schema`.
- **Single allocating path in `grdr-schema`:** `Code::detail()` introduces one heap-allocating API into a crate otherwise built solely of `Copy` static references (`RFC 0007` R3), mitigated by keeping all registry/limits/health lookups allocation-free.
- **Cross-crate enum coupling:** Keeping `codes::ErrorClass` and protobuf `ErrorClass` synchronised requires maintaining both definitions plus tests rather than single-file generation.
- **`#368` dependency hold:** Exact field construction syntax inside `codes/detail.rs` waits on `#368`'s codec decision before `#280` can be merged cleanly.

## Unresolved questions

1. **SP-1 (`#368`) codec outcome (`#1851` AC-9):** `Code::detail(&self) -> grdr_proto::grdr::common::v1alpha1::ErrorDetail` keeps the same public Rust signature regardless of SP-1's outcome, while private construction syntax inside `codes/detail.rs` (`buffa::EnumValue<WireErrorClass>` + `..Default::default()` vs `prost` `i32` enum field) binds when `#368` closes.
2. **Merge order between `#280` and `#2095`:** If `#280` lands before `#2095` introduces `grdr_schema::registry`, `#280` proves `ErrorClass` parity using exhaustive Rust matches, `enums.toml`, and wire tags `1..=5`, and `#2095` adds the `grdr_schema::registry` descriptor check in `crates/grdr-schema/tests/error_detail.rs`.
3. **`MessageRef` proto binding:** Wire carriage for typed template parameters (such as `limits.toml` bound names following Constraint 2c) remains scoped to the standalone `grdr.common.v1alpha1.MessageRef` RFC (`RFC 0017` Unresolved Question 2).

## Review

Review on `#1851` runs on this blob under `D-61`, `D-63`, [`.claude/risk-tiers.toml`](../.claude/risk-tiers.toml) (`[kinds] rfc` plus `public_api_change` and `wire_or_pack_format_change`), and [ADR-0043](../docs/decisions/ADR-0043-lean-token-optimised-agent-team.md) (`eval-review` and `eval-security` on two distinct models). Every reviewing comment on `#1851` opens with the role lines defined in [RFC 0001](./0001-adopt-the-spine.md):
- `RFC file: <blob of rfcs/0022-error-detail-and-error-class.md at the commit reviewed>`
- `Proposed text: none`
- `Base: a80859235e7a2a4444648d6fa8d389d78dde6be9`
- `read=<path>@<blob>` for every other file relied on

This RFC modifies no pinned path in [`rfcs/pins.toml`](./pins.toml), so its decision writes no RFC 0001 decision line ([ADR-0036](../docs/decisions/ADR-0036-the-amended-spine-is-the-baseline-adopted-by-rfc-0001.md)).

This text was written against these git blobs at commit `806359a` on `main`:
- `docs/design/00-decisions.md`: `a80859235e7a2a4444648d6fa8d389d78dde6be9`
- `docs/design/03-system-architecture-and-modularity.md`: `315027b541b6d9b4f278d58faed9e3ff8eaaf32e`
- `docs/design/04-event-model-and-schemas.md`: `e77880a12d2f42e715836a6da9598b86f33b20b0`
- `docs/design/23-api-policy-as-code-and-mcp-server.md`: `a32dbca792471addc7615c8546b4134428a8c1e9`
- `docs/design/28-desktop-and-developer-experience.md`: `428385fc76372e0ee0b1bcc1e3b8aa2a76bd0b21`
- `docs/design/30-open-source-governance-and-community.md`: `91f909de5f9ed9aaf6db0bbeb4641db16976adda`
- `docs/design/34-documentation-support-and-lifecycle.md`: `6565a02207601fbc59b83568cfd48e9d026432eb`
- `rfcs/0000-template.md`: `dde5fb92fe861182e00c93a0b70d2eac73df0bb3`
- `rfcs/0001-adopt-the-spine.md`: `353436cd2f9cff08037783ca66678c52cd7d6be4`
- `rfcs/0006-grdr-common-v1alpha1-options-and-sp1-crates.md`: `be45e4321a38f753ebd61a208bb0227f866d8be1`
- `rfcs/0007-grdr-model-and-grdr-schema-slice-0-surface.md`: `0c0a6745f04888bec8ef2e718352549f47181201`
- `rfcs/0008-clock-entropy-and-the-retry-executor.md`: `b4af2b007041e3abdf6f7439824662ea6f08c52d`
- `rfcs/0010-code-tokens-before-the-token-check.md`: `43cbdb3c08933783ce089f4e768f55771f1e9607`
- `rfcs/0016-health-condition-registry.md`: `a05ed5df0e912fa258cb12cbf6b1e606ce38f6f5`
- `rfcs/0017-grdr-strings-language-token-runtime.md`: `3eca0104bcd3ce536aaa780ac77dfa28e4f74d1b`
- `rfcs/pins.toml`: `993f808476d52888e4a3673da9ad685e1ce55989`
- `docs/decisions/ADR-0038-the-grdr-model-and-grdr-schema-slice-0-surface-adopted-by-rfc-0007.md`: `3ab6d9e63b2f8dc3a5d42322153141ebaa160bfc`
- `docs/decisions/ADR-0050-health-condition-registry-adopted-by-rfc-0016.md`: `a47ca323d697bff05f7003c25b4209de95380b6b`
- `docs/decisions/ADR-0052-grdr-common-v1alpha1-options-and-sp1-crates-adopted-by-rfc-0006.md`: `5789709f68887ac37462669239b6a4b573ef2c3b`
- `architecture.toml`: `60743ee6b3f532190237a499b236784bf3587e04`
- `surfaces.toml`: `2c000f6b76e08117a3551251c28f3081f8991b1e`
- `brand/brand.toml`: `a32c7cfbf0c9197a8464581483546e74f08c545b`
- `security/trust-core.paths`: `54b7a0fcacd7276252c510f5525aa6f3d3cd37eb`
- `supply-chain/admissions.toml`: `1b25c164ade9d313e80bd6286444e289062d7f1f`
- `crates/grdr-schema/Cargo.toml`: `5923d213a1bd8b5c64543eb024597fd7eb77d106`
- `crates/grdr-proto/Cargo.toml`: `9f752e645517203c695c5d87e5c4041481524f0`
- `.claude/risk-tiers.toml`: `bdeae4e47033768f9ddb2166b5e75635f642cbf6`

## Decision

Pending review on `#1851` and SP-1 (`#368`) codec decision; decision record not yet written.
