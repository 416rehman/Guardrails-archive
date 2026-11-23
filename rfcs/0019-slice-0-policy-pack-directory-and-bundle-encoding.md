RFC: 0019
Title: Policy pack directory layout, formats and VerifiedBundle member encoding for slice 0
Author: chief-architect
Harness: antigravity
Model: Gemini 4 Neon
State: Review
Design issue: #1885
Spine: D-07, D-08, D-10, D-11, D-14, D-15, D-25, D-37, D-53, D-60, D-61, D-63, D-69, D-71, P2, P7, P8, P9, P14, P17 (no spine text changes)
Surfaces: public crate `grdr-model` (layer 1: `MemberPath`, `ArchiveEntryInput`, `BundleLimits`, `ArchiveEntryView`, `DecodedBundleArchive`, `encode_bundle_archive`, `decode_bundle_archive`, `BundleArchiveError` alongside `VerifiedBundle` in `crates/grdr-model/src/bundle.rs`); public crate `grdr-core` (layer 1, `experimental`: module `compile::pack` shared pack directory reader and types `PackId`, `SemVer`, `PackKind`, `PackChannel`, `DeclaredRead`, `PackManifest`, `ParsedRule`, `TestPolarity`, `PrincipalType`, `PackTestResolution`, `StructuredTestRequest`, `CommandTestInput`, `CommandAnalysisExpectation`, `ModeExpectation`, `PackTestKind`, `PackTestCase`, `PackTestSuite`, `PackRuleMessages`, `PackLocaleMessages`, `PackLimits`, `PolicyPack`, `PolicyBundle`, `PackError`, `PackReadContext`, `read_bundle_members`, with `pub(crate) read_archive`, plus `engine::bundle` `pack_verified_members` and `load_verified_policy_bundle`); error-code areas `BUNDLE` (`GRDR-BUNDLE-0001`..`0011`) and `PACK` (`GRDR-PACK-0001`..`0016`); eighteen `bundle.*` and `pack.*` resource bounds in `limits.toml`; `toml` and `serde` dependencies on `grdr-core` via existing `#1575` supply-chain admission. As amendments: RFC 0009 (ADR-0041, adding bundle archive framing and error types to `grdr-model`); RFC 0014 (ADR-0054, extending `crates/grdr-model/src/bundle.rs` and adding `engine::bundle` helpers). As proposals: `Cargo.toml`, `Cargo.lock`, `crates/grdr-core/Cargo.toml`, `supply-chain/admissions.toml`, `architecture.toml`, `security/trust-core.paths`, `schema/codes/areas.toml`, `schema/codes/bundle.toml`, `schema/codes/pack.toml`, `limits.toml`, `docs/design/11`, `docs/design/12`, `docs/design/13`, and downstream write-backs on `#1885`, `#41`, `#1889`, `#1538`, `#71`, `#1861`, `#1862`, `#739` and `#1582`
Decision record: none yet

To comment, write on issue #1885 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This is revision 2. It resolves round 1 findings from `eval-security` and `eval-review` on PR #2107 (`358ae2c`): restricts `ModeExpectation.verdict` to the five `grdr_model::Verdict` variants, nominates `security/trust-core.paths` entries and `Trust core: yes` on `#1885`, makes `compile::pack::read_archive` `pub(crate)` so `engine::load_verified_policy_bundle` is the sole public `GRDB` decoder verifying `GRDR-BUNDLE-0001`, drops `Display`/`Error` from `BundleArchiveError` (`renders = "none"`) and clarifies `PackError::Display` code-only rendering, adds RFC 0009/RFC 0014 amendments and complete `Surfaces` items, aligns `ParsedRule` and `MemberPath` `source_path` across sections 5 and 9.2, fixes `ARCH-017` code coverage (`PackError::Policy`, `BundleArchiveError` enum, `GRDR-BUNDLE-0011`, removing dead `BundleLimits.rules_max`), binds `BundleLimits.pack_id_max` cleanly across `GRDB` layout checks, restricts Layer-1 message inertness to `#212` lexical checks, and updates `## Review` blobs to `origin/main` (`5a21f62`).

## Summary
This RFC settles escalation `#1885-E3` (Option A) by specifying the complete slice-0 policy pack directory contract (`packs/<pack-id>/`) and the deterministic canonical binary framing inside `grdr_model::VerifiedBundle`:

1. **Canonical `VerifiedBundle` member framing (`GRDB` v1, Section 2).** Defines a deterministic, bijective, length-checked binary archive format (`\x89GRDBUN\n`, format version 1) carried inside `VerifiedBundle::bytes()`. Each member carries its strictly ascending UTF-8 relative path, exact byte slice and per-member SHA-256 digest with zero gaps or timestamps, bounded by `limits.toml` (`bundle.*`). The framing codec sits in `grdr-model` (layer 1, no content parsers, no `unsafe`), allowing privileged `grdr-daemon` (`#1538`) to package `<bundle-dir>/packs/<pack-id>/...` without violating `ARCH-004` while `grdr-core` (`#1861`, `#1889`) verifies SHA-256 digests and decodes member slices byte-for-byte identically.
2. **Closed pack directory layout and file schemas (Sections 3 to 8).** Fixes the exact schemas, allowed relative paths and closed validation rules under P7 for:
   - `pack.toml` (`format_version = 1`, `id`, `kind = "policy"`, semver `version`, `min_engine`, `channel`, shipped `mode` in `Off | Watch | Ask | Block`, optional `rule_prefixes`, `on_loss`, `requires_capabilities` and `[[reads]]` `(field, data_class)` declarations, plus `grdr.base` invariants);
   - `rules/*.cedar` (Cedar 4.14.1 strict parsing against `v1alpha1.cedarschema`, template rejection, `@mode` forbidden in source, `permit` restricted exclusively to `grdr.base` under [docs/design/12-policy-engine.md](../docs/design/12-policy-engine.md) section 7 step 6 with `@id` required and forbid-only annotations disallowed on `permit`, and `forbid` annotations checked through `#212`'s `RuleMeta`);
   - `lists/*.toml` (one TOML file per `VocabularyList` of `#213` carrying `type`, `class`, `polarity`, `managed_by` and bounded `entries`, including empty `argv-token` lists for `#41`);
   - `tests/*.yaml` (both `structured` requests and `command` raw command + `cwd` tests, per-Mode `verdict`, `determining_rules`/`determining_forbids` and shadow `findings` expectations, `selftest` flagging, `forbid`-rule positive/negative coverage scope exempting unconditional `grdr.base` permits, and a bounded pure-Rust YAML 1.2 fail-safe subset parser);
   - `messages/<locale>.mf2.toml` and `session-rules.yaml` (layer-1 TOML framing and fail-closed validation aligning cleanly with [RFC 0017](./0017-grdr-strings-language-token-runtime.md) / `ARCH-024`, keeping pack message directories optional in slice 0 `#41` and refusing non-empty slice-1 `session-rules.yaml` cleanly under P9).
3. **Shared layer-1 reader and `#739` (`RFC 0018`) coordination (Sections 1, 9, 10 and 11).** Places the directory-to-typed-pack parser at `grdr_core::compile::pack` (`read_bundle_members` over an in-memory `BTreeMap<MemberPath, &[u8]>`, plus `pub(crate) read_archive`), paired with digest verification in `grdr_core::engine::load_verified_policy_bundle` (`crates/grdr-core/src/engine/bundle.rs`) as the sole public `GRDB` -> `PolicyBundle` entry point. Reuses `toml` and `serde` from `#1575` (`supply-chain/admissions.toml`) without introducing unvetted YAML crates or `ARCH-001`/`ARCH-004`/`ARCH-013`/`ARCH-024` violations, and registers subsystem areas `BUNDLE` (`GRDR-BUNDLE-0001`..`0011`), `PACK` (`GRDR-PACK-0001`..`0016`) and eighteen `limits.toml` `[bound.*]` rows under [RFC 0007](./0007-grdr-model-and-grdr-schema-slice-0-surface.md).

## Motivation
- **Blocked first runnable path (`#645`):** `#41` (`packs/grdr.base`, `packs/grdr.essentials`), `#1885` (shared layer-1 reader), `#1889` (`grdr-content` CI check), `#1691` (content repo CI), `#1538` (device compile instance), `#1862` (user archive installer) and `#1861` (`Engine::load` and `Engine::step`) all depend on one shared pack directory schema and bundle encoding.
- **Unresolved opaque bytes in `VerifiedBundle`:** [RFC 0014](./0014-engine-boundary-c-abi.md) defines `VerifiedBundle` over opaque `(bytes: Vec<u8>, digest: [u8; 32])`, while `#1885` specifies a reader taking relative path to bytes. Without fixing the canonical binary archive framing inside `VerifiedBundle::bytes()`, `grdr-daemon` (`#1538`), `grdr-engine` (`#1861`, `#1538`) and `grdr-content` CI (`#1889`) cannot consume identical bytes across Linux, macOS, Windows and `wasm32-unknown-unknown`.
- **`ARCH-004` privileged closure separation:** `grdr-daemon` is `privileged` and must not link `grdr-core`, `toml` or `cedar-policy` ([docs/design/03-system-architecture-and-modularity.md](../docs/design/03-system-architecture-and-modularity.md) `ARCH-004`). Putting the pure binary `GRDB` v1 framing codec inside `grdr-model` keeps all TOML, YAML and Cedar parsing strictly inside sandboxed `grdr-core` and CI tools while preserving `bundle_sha256` identity from disk to engine.
- **`grdr.base` `permit` and test-coverage mismatch risk:** `#41` R1 writes `grdr.base/rules/base.cedar` with fifteen `permit` rules carrying `@id("base.<class>")` and no `@class` or `tests/*.yaml`, whereas `forbid` rules (`#212`) require `@class` and one positive and one negative test (`docs/design/12` section 11). Fixing the exact `permit` rule schema and coverage rule now prevents `#1885`, `#1889` and `#41` from deadlocking at integration.

## Design

### 1. Scope, layer placement and `#739` (`RFC 0018`) coordination
This RFC governs slice 0 (`format_version = 1`) for `kind = "policy"` packs and `VerifiedBundle` member framing:

| Responsibility | Crate / module | Layer | Stability | Rationale |
|---|---|---|---|---|
| `VerifiedBundle`, `MemberPath`, `GRDB` v1 archive encoder/decoder (`ArchiveEntryInput`, `BundleLimits`, `ArchiveEntryView`, `DecodedBundleArchive`, `BundleArchiveError`) | `grdr-model` (`crates/grdr-model/src/bundle.rs`, re-exported at root per RFC 0009 R3; trust core nominated) | `1` | `experimental` (RFC 0005 / RFC 0009 / RFC 0014) | Callable by both privileged `grdr-daemon` (`#1538`, zero `content_parsers`) and `grdr-core` (`ARCH-004`) |
| Shared pack parser & validator (`pack.toml`, `rules/*.cedar`, `lists/*.toml`, `tests/*.yaml`, `messages/*.mf2.toml`, `session-rules.yaml`) | `grdr-core` (`crates/grdr-core/src/compile/pack.rs`, `grdr_core::compile::pack`; trust core nominated) | `1` | `experimental` (`surfaces.toml`) | Under `ARCH-013`, `compile` is permitted to import both `policy` and `analyze` plus `grdr-schema` and `grdr-model` |
| SHA-256 verification wrapper over `VerifiedBundle` (`engine::load_verified_policy_bundle`, `pack_verified_members`) | `grdr-core` (`crates/grdr-core/src/engine/bundle.rs`, re-exported under `engine`; trust core nominated) | `1` | `experimental` | Reuses RFC 0014 `bundle_sha256` (`crates/grdr-core/src/engine/bundle_sha256.rs`) without adding reverse `compile -> engine` imports (`ARCH-013`) |
| Domain policy enums (`Mode`, `RuleClass`, `ApproverKind`, `ApprovalGrade`, `OnLoss`, `Obligation`, `Transform`, `RuleStatus`, `RuleMeta`) and vocab types (`ListType`, `Polarity`, `ManagedBy`, `ClassName`, `VocabularyList`, `VocabularyTable`) | Defined by `#739` (`RFC 0018`, `RFC-1`) across `grdr-model` and `grdr-core::analyze` | `1` | `experimental` | RFC 0019 references these types by role and spelling (`#212`, `#213`, `#739`); RFC 0018 owns their struct/enum definitions |

- **Coordination with `#739` (`RFC 0018`):** RFC 0019 neither redefines `#739`'s types (`RuleMeta`, `Mode`, `RuleClass`, `ListType`, `VocabularyList`, `VocabularyTable`, `ActionRequest`, `CompiledRule`, `CompiledSets`) nor alters `#739`'s write paths. `grdr_core::compile::pack` constructs `RuleMeta` (`#212`) for `forbid` rules and `VocabularyList` (`#213`) for `lists/*.toml`, and supplies `ReadDecl` pairs compatible with `#216`'s `ReadSet` / `check_declared`.
- **`DataClass` alignment:** `DeclaredRead.data_class` uses the four spine/event data classes (`"identifier"`, `"structural"`, `"derived"`, `"content"`, matching [docs/design/04-event-model-and-schemas.md](../docs/design/04-event-model-and-schemas.md) section 1 and [RFC 0017](./0017-grdr-strings-language-token-runtime.md) section 2.1). `grdr_core::compile::pack` maps `"identifier" | "structural" | "derived" | "content"` directly to the shared layer-0/layer-1 `DataClass` enum delivered under RFC 0006 (`#353`) / `#17` (referenced by `#216`).
- **Deferrals to later slices:** Multi-format detection packs (`sigma`, `yara`, `catalogue`), DSSE/Cosign signature envelopes inside the bundle (`#1251`), delta reconstruction (`#1251`), `layers/*.settings` bundle delivery (`#71`, `#754`), and active `session-rules.yaml` evaluation (`#1894`) remain out of scope for `format_version = 1`.

### 2. Canonical `VerifiedBundle` member encoding (`GRDB` v1)
To allow `#1538`, `#1861` and `#1889` to pack and decode an identical bundle byte buffer inside `VerifiedBundle`, `VerifiedBundle::bytes()` carries a **Guardrails Bundle Archive (`GRDB` v1)** with the following normative binary grammar.

#### 2.1 Conventions
- Every multi-byte integer is unsigned and little-endian (`u32`, `u64`), matching [spec/host-contract/tables.md](../spec/host-contract/tables.md) and `GRDI` v1 ([RFC 0014](./0014-engine-boundary-c-abi.md)).
- All size, offset and capacity arithmetic executes in checked `u64` (`checked_add`, `checked_mul`, `usize::try_from`) so 32-bit `wasm32-unknown-unknown` and 64-bit native hosts behave identically with zero overflow or panic paths.
- Every reserved or unused byte is `0` on encode and rejected if non-zero on decode.
- Every digest is a 32-byte raw SHA-256 (`[u8; 32]`).

#### 2.2 Frame layout
1. **Header (32 bytes, offset `0..32`):**

| Offset | Size | Field | Type | Normative value / invariant |
|---|---|---|---|---|
| `0` | `8` | `magic` | `[u8; 8]` | `89 47 52 44 42 55 4E 0A` (`\x89GRDBUN\n`; high bit catches 7-bit corruption, trailing `\n` catches CRLF mangling) |
| `8` | `4` | `format_version` | `u32` | `1` for slice 0 |
| `12` | `4` | `flags` | `u32` | `0` (reserved; any non-zero bit rejected with `GRDR-BUNDLE-0003`) |
| `16` | `4` | `member_count` | `u32` | `N`, with `1 <= N <= limits.members_max` |
| `20` | `4` | `reserved` | `u32` | `0` (rejected if non-zero) |
| `24` | `8` | `total_len` | `u64` | Exact byte length of the complete frame (`total_len == bytes.len()` and `total_len <= limits.archive_max`) |

2. **Sorted Member Index (`N * 56` bytes, offset `32..index_end`):**
   Entry `i` (`0 <= i < N`) sits at byte offset `32 + 56 * i`:

| Relative offset | Size | Field | Type | Normative value / invariant |
|---|---|---|---|---|
| `0` | `4` | `path_offset` | `u32` | Byte offset from start of frame to relative path UTF-8 bytes |
| `4` | `4` | `path_len` | `u32` | Byte length of path (`1 <= path_len <= limits.path_max`) |
| `8` | `8` | `payload_offset` | `u64` | Byte offset from start of frame to member payload bytes |
| `16` | `8` | `payload_len` | `u64` | Byte length of member payload (`0 <= payload_len <= limits.member_max`) |
| `24` | `32` | `payload_sha256` | `[u8; 32]` | SHA-256 of the member's `payload_len` bytes |

3. **Contiguous String Path Table (`index_end..path_end`):**
   Paths are packed contiguously with zero gaps or delimiters:
   - `path_offset[0] == index_end` (`32 + 56 * N`).
   - For all `i > 0`: `path_offset[i] == path_offset[i - 1] + path_len[i - 1]`.
   - `path[0] < path[1] < ... < path[N - 1]` in strict lexicographical UTF-8 byte order (preventing duplicate paths and non-canonical ordering).

4. **Contiguous Member Payload Table (`path_end..total_len`):**
   Payloads are packed contiguously immediately after the last path byte:
   - `payload_offset[0] == path_end`.
   - For all `i > 0`: `payload_offset[i] == payload_offset[i - 1] + payload_len[i - 1]`.
   - `payload_offset[N - 1] + payload_len[N - 1] == total_len == bytes.len()`.

**Bijective security invariant (`P7`, `P9`):** Because paths and payloads are tightly contiguous with zero padding or alignment gaps and paths are strictly sorted, two member sets produce byte-for-byte identical `GRDB` v1 bytes (and thus identical `VerifiedBundle::digest()`) if and only if they contain identical `(path, payload_bytes)` pairs. Any unreferenced gap byte, trailing byte, out-of-order path, duplicate path, arithmetic wrap, or digest mismatch fails closed.

#### 2.3 Producer and consumer flow (`#1538`, `#1861`, `#1889`)
- **On device (`#1538` `grdr-daemon`):** `BundleSource` reads files from the installed bundle directory `<bundle-dir>/packs/<pack-id>/...` (skipping nothing silently, refusing symlinks/non-regular files and paths outside Section 3), hashes each member payload with `grdr-crypto` (`ARCH-006`), builds canonical `GRDB` v1 bytes via `grdr_model::encode_bundle_archive`, hashes the complete `GRDB` v1 buffer via `grdr-crypto` to obtain `VerifiedBundle` (`ARCH-012`), seals a read-only descriptor (`memfd` on Linux, read-only handle elsewhere), and passes `BundleLoad` to the compile instance and serving `grdr-engine`. `grdr-daemon` performs zero TOML, YAML or Cedar parsing (`ARCH-004`).
- **At `grdr-ffi` and `grdr-wasm` ingress (`#388`, `#19`):** Host callers pass `GRDB` v1 bytes directly to `grdr_engine_load`, where FFI/Wasm ingress computes `bundle_sha256` and constructs `VerifiedBundle::assume_verified` ([RFC 0014](./0014-engine-boundary-c-abi.md)).
- **Inside `grdr-core` (`#1861`, `#1538`, `#1889`):**
  1. When loading from `&VerifiedBundle`, `grdr_core::engine::load_verified_policy_bundle` (`crates/grdr-core/src/engine/bundle.rs`) is the **sole public `GRDB` -> `PolicyBundle` entry point**: it verifies `bundle_sha256(bundle.bytes()) == *bundle.digest()` (`GRDR-BUNDLE-0001`), calls `grdr_model::decode_bundle_archive(bundle.bytes(), &limits.bundle)`, verifies `bundle_sha256(entry.payload) == entry.payload_sha256` for every entry (`GRDR-BUNDLE-0001`), and invokes `pub(crate) crate::compile::pack::read_archive`. No public function accepts an unverified `DecodedBundleArchive` directly to build a `PolicyBundle`.
  2. When running content repository CI (`#1889`) over a directory checkout without a daemon, the check walks `packs/<pack-id>/...` into `BTreeMap<MemberPath, &[u8]>` and calls `grdr_core::compile::pack::read_bundle_members`, and also verifies canonical `GRDB` v1 framing round-trips via `pack_verified_members` -> `VerifiedBundle` (constructed via `grdr-crypto` in the CI binary or in tests under `ARCH-012`) -> `load_verified_policy_bundle` so CI and device compile paths execute the exact same framing, digest checks and parser (`P7`).

### 3. Bundle directory layout and closed `MemberPath` grammar
Every `MemberPath` in a slice-0 bundle (`GRDB` v1 or filesystem checkout relative root) must satisfy ALL of the following rules:

1. **Lexical path hygiene (`GRDR-BUNDLE-0006`, enforced by `MemberPath::parse`):**
   - Byte length `1 <= len <= limits.path_max` (`bundle.path-max = 256`).
   - Printable ASCII only (`0x21..=0x7E`; no whitespace, no control bytes, no NUL).
   - `/` separator only; no `\\`, no leading `/`, no trailing `/`, no `//` empty segment, no `.` or `..` segment.
2. **Closed slice-0 directory layout (`GRDR-BUNDLE-0008`, enforced by `encode_bundle_archive`, `decode_bundle_archive` and `read_bundle_members` using `limits.pack_id_max`):**
   Every member path must match `packs/<pack-id>/<member-subpath>`, where `<pack-id>` matches `^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*$` (`len <= limits.pack_id_max`, `pack.id-max = 128`) and `<member-subpath>` is exclusively one of:
   - `pack.toml` (required per pack)
   - `rules/<stem>.cedar` (`<stem>` matches `^[a-z][a-z0-9._-]*$`; at least one `.cedar` file required per pack)
   - `lists/<stem>.toml` (`<stem>` matches `^[a-z][a-z0-9._-]*$`; zero or more per pack)
   - `tests/<stem>.yaml` (`<stem>` matches `^[a-z][a-z0-9._-]*$`; zero or more at reader level)
   - `messages/<locale>.mf2.toml` (`<locale>` matches `^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$`, max 32 bytes; zero or more per pack)
   - `session-rules.yaml` (zero or one per pack; see Section 8)
3. **Cross-platform case-collision ban (`GRDR-BUNDLE-0007`):**
   No two member paths in a bundle may collide under ASCII case folding (protecting case-insensitive macOS/Windows checkouts in `#1691` and `#1862`, especially for `messages/<locale>.mf2.toml`). No uppercase ASCII characters are admitted outside `<locale>` in `messages/<locale>.mf2.toml`.
4. **Aggregate bundle caps (`GRDR-BUNDLE-0009`, `0010`, `0011`):**
   - At least 1 pack (`packs/` cannot be empty, `GRDR-BUNDLE-0009`), at most `bundle.packs-max` (`64`, `GRDR-BUNDLE-0010`) distinct packs.
   - Total rules (`permit` + `forbid`) across all packs in the bundle `<= bundle.rules-max` (`5000`, `GRDR-BUNDLE-0011`, [docs/design/12-policy-engine.md](../docs/design/12-policy-engine.md) section 16), checked inside `grdr_core::compile::pack`.
   - No two rules in the same pack or across different packs in one bundle may share an `@id` (`GRDR-PACK-0008`).

### 4. `pack.toml` exact schema (`PackManifest`)
Each `packs/<pack-id>/pack.toml` is valid UTF-8, at most `policy.parser-input-max` bytes, parsed strictly with unknown fields forbidden (`#[serde(deny_unknown_fields)]`, `P7`):

```toml
format_version = 1
id = "grdr.essentials"
kind = "policy"
version = "0.1.0"
min_engine = "0.1.0"
channel = "policy"
mode = "Watch"

# Optional in slice 0:
# rule_prefixes = ["essentials"]
# on_loss = "block"
# requires_capabilities = []

[[reads]]
field = "action"
data_class = "structural"

[[reads]]
field = "context.facts"
data_class = "structural"

[[reads]]
field = "principal.type"
data_class = "structural"
```

Field contract:

| Key | Type | Required | Validation / constraint |
|---|---|---|---|
| `format_version` | `u32` (integer) | Yes | Must equal `1` in slice 0 (`GRDR-PACK-0004` otherwise) |
| `id` | `String` (`PackId`) | Yes | Matches `^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*$`, `len <= pack.id-max` (`128`), and must equal directory name `<pack-id>` under `packs/<pack-id>/` (`GRDR-PACK-0003`) |
| `kind` | `String` (`PackKind`) | Yes | Closed enum `{ "policy", "sigma", "yara", "catalogue" }` ([docs/design/13-detection-engine-and-content.md](../docs/design/13-detection-engine-and-content.md) section 11). Slice-0 policy reader requires `"policy"` (`GRDR-PACK-0003` otherwise) |
| `version` | `String` (`SemVer`) | Yes | Strict SemVer 2.0.0 (`MAJOR.MINOR.PATCH[-pre][+build]`), `len <= pack.version-max` (`64`), ASCII `[0-9A-Za-z.+-]` (`GRDR-PACK-0003`) |
| `min_engine` | `String` (`SemVer`) | Yes | Strict SemVer 2.0.0, `len <= pack.version-max`; engine checks `ctx.engine_version >= min_engine` using SemVer precedence (`GRDR-PACK-0004`) |
| `channel` | `String` (`PackChannel`) | Yes | Closed enum `{ "policy", "detection-content", "schema", "agent-config" }`. When `kind == "policy"`, `channel` must equal `"policy"` (`GRDR-PACK-0003`) |
| `mode` | `String` (`grdr_model::Mode`) | Yes | Exact spelling in `{ "Off", "Watch", "Ask", "Block" }` (`#212` R1). When `id == "grdr.base"`, `mode` must equal `"Block"` ([docs/design/12-policy-engine.md](../docs/design/12-policy-engine.md) section 14 built-in pack; `GRDR-PACK-0003`) |
| `rule_prefixes` | `Vec<String>` | No | When present: `1..=pack.rule-prefixes-max` distinct prefixes, each matching `^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*$`, `len <= policy.rule-id-max`. When omitted: defaults to `[<suffix>]` if `id == "grdr.<suffix>"`, else `[id]`. Only `grdr.base` may hold `"base"` |
| `on_loss` | `String` (`grdr_model::OnLoss`) | No | Optional pack-level loss-of-sensor floor `{ "allow", "block" }` (`#217` R7) |
| `requires_capabilities` | `Vec<String>` | No | Defaults to `[]`; at most `pack.capabilities-max` (`32`) unique ASCII identifiers `^[a-z][a-z0-9._-]*$`. Unknown or unoffered capabilities fail cleanly with `GRDR-PACK-0004` (`P9`) |
| `reads` (`[[reads]]`) | `Vec<DeclaredRead>` | No (defaults `[]`) | At most `pack.reads-max` (`128`) entries `{ field, data_class }`. Every `field` matches `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$`, `len <= pack.read-field-max` (`128`), unique within pack; `data_class` is `{ "identifier", "structural", "derived", "content" }` (`GRDR-PACK-0003`) |

Example `packs/grdr.base/pack.toml` (`#41` R1, R4, R5):
```toml
format_version = 1
id = "grdr.base"
kind = "policy"
version = "0.1.0"
min_engine = "0.1.0"
channel = "policy"
mode = "Block"

[[reads]]
field = "action"
data_class = "structural"
```
Notes:
- Pack-to-pack effective `rule_prefixes` in one bundle must not overlap on equal prefix strings (`GRDR-PACK-0008`), preventing one pack from forging another pack's `@id` namespace. Note that `grdr.supply-chain` (`docs/design/12` section 5 policy 6 `supply.publish`) and `grdr.agents` (`#212` R6 `["agents", "identity", "cred"]`) specify explicit `rule_prefixes` in `pack.toml`.
- Declared `reads` verification against computed rule read sets (`#216` `check_declared`) rejects missing fields or mismatched `DataClass` (`GRDR-PACK-0014` in `#1889` CI and device compile).

### 5. `rules/*.cedar` parsing, annotations and `grdr.base` `permit` rule
Every `rules/<stem>.cedar` file is decoded as follows using `cedar-policy = "=4.14.1"` (`default-features = false`):

1. **Size and non-emptiness (`GRDR-POLICY-0012`, `GRDR-PACK-0005`):**
   - Raw bytes must be valid UTF-8 and at most `policy.parser-input-max` (`262144` bytes per `.cedar` file, returning `PackError::Policy { source: PolicyError::ParserInputOverLimit { .. }, .. }` -> `GRDR-POLICY-0012`, mitigating the Cedar parser memory advisory noted in [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md)).
   - At least one `rules/*.cedar` file must exist per pack, and every `.cedar` file must parse to at least one policy statement (zero-statement comment-only files are refused with `GRDR-PACK-0005`).
   - Pack rule count `<= pack.rules-max` (`1024`).
2. **Cedar syntax, template ban and strict validation (`GRDR-PACK-0006`):**
   - Parse source with `cedar_policy::PolicySet::from_str`. Reject any parse error (`GRDR-PACK-0006`).
   - Reject linked templates or policy templates (`policy_set.templates().next().is_some()` -> `GRDR-PACK-0006`).
   - Validate `policy_set` against `grdr_schema::cedar::schema()` (`v1alpha1`) using `cedar_policy::Validator` under `ValidationMode::Strict`. Any validation error or warning rejects the pack (`GRDR-PACK-0006`).
3. **Rule ordering and source annotation bans:**
   - Files iterate in canonical ascending relative path order (`rules/a.cedar`, `rules/b.cedar`), and policies within one file preserve source order.
   - Any policy carrying `@mode` in source is rejected (`GRDR-PACK-0008`, `docs/design/12` section 3, `#212`, `#218`: `@mode` is compiler-emitted only).
   - Duplicate annotation keys on one Cedar statement are rejected cleanly by Cedar's parser; any annotation missing a string literal value (`@flag` without `"..."`) is rejected (`GRDR-PACK-0008`).
4. **Effect split (`permit` vs `forbid`):**
   - **`Effect::Permit` (`grdr.base` only, [docs/design/12-policy-engine.md](../docs/design/12-policy-engine.md) section 7 step 6):**
     - If `manifest.id != "grdr.base"`, reject immediately with `GRDR-PACK-0007` (`PERMIT_OUTSIDE_BASE`).
     - Annotation contract for `Permit`: `@id` is required, must match `manifest.rule_prefixes` (specifically `base.<action-class>` in `#41` R1), valid `PolicyRuleId`, len `<= policy.rule-id-max`. Optional `@intent` and `@status` (validated as `#212` inert text) are accepted if present. Any forbid-only control annotation (`@class`, `@mode`, `@max_mode`, `@approver`, `@min_grade`, `@on_loss`, `@final`, `@message`, `@steer`, `@remedy`, `@obligation`) on a `Permit` is rejected with `GRDR-PACK-0008` (`INVALID_PERMIT_ANNOTATION`), matching `#41` R1 cleanly.
     - Produces `ParsedRule::Permit { id: PolicyRuleId, policy: cedar_policy::Policy, source_path: MemberPath }` with the Cedar `PolicyId` rebound cleanly to `@id`.
   - **`Effect::Forbid` (all policy packs including future base freezes in `grdr.base`):**
     - Annotation map is passed verbatim to `#212`'s `RuleMeta::from_annotations(&manifest.rule_prefixes, annotations, meta_limits)`: `@id` and `@class` are required; optional `@max_mode` (default `Block`), `@approver` (default `self`), `@min_grade`, `@on_loss`, `@final` (`"true"` only), `@message`, `@steer`, `@remedy` (`modify:<transform>`), `@obligation` (comma-separated without duplicates), `@intent`, and `@status` (`"draft"`) follow `#212` R1 to R15 (`@message`, `@steer`, `@intent` inert: bounded by `policy.annotation-max`, no C0/C1/bidi controls, no `://`, no case-insensitive `www.`).
     - Note for `#41` R2 (`packs/grdr.essentials/rules/bypass-flags.cedar`): `essentials.bypass-flags` sets `@id`, `@class`, `@final`, `@message`, `@steer`, leaving `@max_mode` at its default (`Block`).
     - Produces `ParsedRule::Forbid { meta: RuleMeta, policy: cedar_policy::Policy, source_path: MemberPath }` with Cedar `PolicyId` rebound to `meta.id` before `#218` mode transformation.
5. **Cross-bundle uniqueness (`GRDR-PACK-0008`):**
   - Every `@id` across all `Permit` and `Forbid` rules in a pack and across all packs in the bundle must be globally unique.

### 6. `lists/*.toml` exact schema
Each `packs/<pack-id>/lists/<stem>.toml` is valid UTF-8, at most `policy.parser-input-max` bytes, parsed strictly (`#[serde(deny_unknown_fields)]`) into one `VocabularyList` (`#213`):

```toml
type = "argv-token"
class = "flag.bypass-permissions"
polarity = "protect"
managed_by = "pack"
entries = [
  "--dangerously-skip-permissions",
]
```

Empty list example (`#41` R3):
```toml
type = "argv-token"
class = "flag.hooks-disabled"
polarity = "protect"
managed_by = "pack"
entries = []
```

Field contract and validation (`GRDR-PACK-0009`, `0010`):

| Key | Type | Required | Validation / constraint |
|---|---|---|---|
| `type` | `String` (`#213` `ListType`) | Yes | Closed enum: `"path"`, `"host"`, `"command"`, `"argv-token"`, `"mcp-argument"`, `"cloud-account"`, `"tenant"`, `"package-key"`, `"artefact-key"` |
| `class` | `String` (`#213` `ClassName`) | Yes | Matches `^[a-z][a-z0-9.-]*$`, `len <= policy.class-name-max` |
| `polarity` | `String` (`#213` `Polarity`) | Yes | Closed enum `{ "protect", "allow" }` |
| `managed_by` | `String` (`#213` `ManagedBy`) | No (defaults `"pack"`) | Closed enum `{ "pack", "feed" }`. `"feed"` requires `polarity == "protect"` and `type` in `{ "host", "package-key", "artefact-key" }` (`#213` R7; `GRDR-PACK-0010`) |
| `entries` | `Vec<String>` | Yes | May be empty (`[]`, matching `#41` R3 and `#213` Failure modes). Count `<= policy.list-max-entries`; each entry `1 <= len <= policy.list-entry-max`; no NUL, C0/C1 control char or Unicode bidi isolate/override; no duplicate entries inside one list (`GRDR-PACK-0009`) |

- Recommended `<stem>.toml` filenames use `<class>.toml` (for example `flag.bypass-permissions.toml`) or `<type>.<class>.toml` when one pack defines two `ListType` files for the same `ClassName`. The reader enforces `(ListType, ClassName)` uniqueness and `Polarity` consistency per `ClassName` across each pack and across the entire bundle (`#213` R5, R6; `GRDR-PACK-0010`), plus aggregate `policy.vocabulary-max-entries` (`#213` R8).
- Entry-level engine grammar (for example `#223` R2 single-space command tokens or R8 non-whitespace argv tokens) runs in the analyser engine or `command_class` builder; `pack` guarantees UTF-8, length bounds, non-emptiness and control-character cleanliness.

### 7. `tests/*.yaml` exact schema and YAML 1.2 subset parser

#### 7.1 Bounded YAML 1.2 fail-safe subset (`grdr_core::compile::pack::yaml_subset`)
To eliminate third-party YAML dependency churn, CVE history (`yaml-rust`/`serde_yaml`), billion-laughs anchor expansion and YAML 1.1 implicit type bugs (`yes`/`no`/`on`/`off`/`0123`) in layer 1 (`wasm32-unknown-unknown`, `#![forbid(unsafe_code)]`), slice 0 uses a pure-Rust deterministic parser implementing a strict subset of standard YAML 1.2:
- **Accepted constructs:** valid UTF-8 without BOM; LF (`\n`) or CRLF (`\r\n`) line breaks; optional single `---` header and `...` footer; consistent space-indented mappings (tabs banned for indentation); unique literal string keys per mapping; block sequences (`- ...`) and inline flow sequences (`[...]`); inline empty mapping `{}` (for `env: {}`); single-quoted `'...'` strings (`''` escape); double-quoted `"..."` strings (JSON escapes `\"`, `\\`, `\n`, `\t`, `\r`, `\uXXXX` rejecting `\u0000` and control chars); explicit `true` and `false` booleans; decimal non-negative integers `0 | [1-9][0-9]*`; plain unquoted strings not starting with YAML reserved indicators (`&`, `*`, `!`, `|`, `>`, `{`, `[`, `?`, `,`, `@`, `` ` ``, `%`) and never parsed as YAML 1.1 sexagesimals, octal or implicit `yes`/`no`/`on`/`off`. Comments begin with `#` outside quotes.
- **Rejected constructs (`GRDR-PACK-0011`):** anchors (`&`), aliases (`*`), merge keys (`<<`), tags (`!`), block scalars (`|` / `>`), multi-document streams, duplicate mapping keys, tabs in indentation, forbidden C0/C1/bidi controls, raw bytes `> pack.yaml-input-max` (`262144`), nesting depth `> pack.yaml-depth-max` (`8`), or total parsed nodes `> pack.yaml-items-max` (`16384`).
- Every file valid under this subset is 100% valid standard YAML 1.2, preserving full tooling interoperability while isolating parser internals cleanly inside `compile::pack::yaml_subset`.

#### 7.2 Schema (`PackTestSuite`)
Each `packs/<pack-id>/tests/<stem>.yaml` deserialises into `PackTestSuite` (unknown fields rejected):

```yaml
schema_version: 1
tests:
  - id: T1
    rule: essentials.bypass-flags
    polarity: positive
    selftest: true
    kind: structured
    request:
      principal_type: Session
      action: exec
      resource_classes: []
      facts:
        - flag.bypass-permissions
    expectations:
      - mode: Watch
        verdict: ALLOW
        determining_rules:
          - base.exec
        findings:
          - essentials.bypass-flags
      - mode: Block
        verdict: DENY
        determining_rules:
          - essentials.bypass-flags
        findings: []

  - id: T2
    rule: essentials.bypass-flags
    polarity: negative
    selftest: true
    kind: structured
    request:
      principal_type: Session
      action: exec
      resource_classes: []
      facts: []
    expectations:
      - mode: Block
        verdict: ALLOW
        determining_forbids: []
        findings: []

  - id: T4
    rule: essentials.bypass-flags
    polarity: positive
    kind: command
    command:
      raw: 'claude --dangerously-skip-permissions -p "fix the build"'
      cwd: /workspace/repo
      dialect: posix
      env: {}
    expect_analysis:
      resolution: resolved
      facts:
        - flag.bypass-permissions
      command_classes: []

  - id: T7
    rule: essentials.bypass-flags
    polarity: negative
    kind: command
    command:
      raw: "claude --permission-mode plan -p hi"
      cwd: /workspace/repo
    expect_analysis:
      resolution: resolved
      facts: []
      absent_facts:
        - "flag.*"
      command_classes: []
```

Field and validation rules:
1. **Top level (`PackTestSuite`):** `schema_version` (`1` only, required) and `tests` (non-empty list; sum across pack `<= pack.tests-max`). Test `id` (`^[A-Za-z][A-Za-z0-9._-]*$`, len `<= 64`) must be unique across all `tests/*.yaml` files in the pack.
2. **Case metadata (`PackTestCase`):**
   - `id`: required unique identifier.
   - `rule`: optional `PolicyRuleId` belonging to a rule in this pack; **required** if `polarity` is set.
   - `polarity`: `"positive" | "negative"`, optional only on standalone analysis-only `command` tests with no `rule`, required whenever `rule` is named.
   - `selftest`: optional `bool` (default `false`; marks device activation self-tests per [docs/design/12-policy-engine.md](../docs/design/12-policy-engine.md) section 11 and `#1538` R2).
   - `kind`: `"structured" | "command"` (required discriminator).
3. **Structured form (`kind: structured`):**
   - Requires `request` (forbids `command` and `expect_analysis`):
     - `principal_type`: `"Session" | "Process"` (required).
     - `action`: one of the 15 spine action class wire strings (`"exec"`, `"file.read"`, ..., `"data.flow"`, required).
     - `control_point`: optional `ControlPoint` string (default `"hook"`).
     - `resource_classes`: optional list of `ClassName` strings (default `[]`).
     - `facts`: optional list of fact strings (default `[]`).
     - `session_labels`: optional list of label strings (default `[]`).
     - `grants`: optional list of rule `@id` strings (default `[]`).
   - Requires non-empty `expectations` (`ModeExpectation` list with unique `mode` values).
4. **Raw command form (`kind: command`):**
   - Requires `command` (forbids `request`): `raw` (non-empty UTF-8 string, `len <= analyze.shell.input-max`), `cwd` (non-empty string), optional `dialect` (`"posix" | "powershell" | "cmd"`, default `"posix"`), optional `env` (`BTreeMap<String, String>`, default `{}`).
   - Requires at least one of `expect_analysis` or non-empty `expectations` (vacuous tests with neither expectation are refused with `GRDR-PACK-0011`, `P9`).
   - When `expectations` is present on a `command` case, optional `command_request` (`principal_type` default `"Session"`, `action` default `"exec"`, `control_point` default `"hook"`, `resource_classes` default `[]`, `session_labels` default `[]`, `grants` default `[]`) supplies the Cedar request envelope.
   - `expect_analysis`: `resolution` (`"resolved" | "unresolved" | "malformed"`, default `"resolved"`), `facts` (optional exact sorted set, default `[]`), `absent_facts` (optional list of exact fact names or trailing-`*` prefixes such as `"flag.*"` that must not appear), `command_classes` (optional exact sorted set, default `[]`).
5. **Mode expectation (`ModeExpectation`):**
   - `mode`: `"Off" | "Watch" | "Ask" | "Block"` (required; unique per test case).
   - `verdict`: `"ALLOW" | "DENY" | "MODIFY" | "STEP_UP" | "DEFER"` (required; matched strictly against the five variants of `grdr_model::Verdict` per [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md) / `ADR-0053` / D-07).
   - `determining_rules`: optional exact set of determining `@id` rule identifiers returned in `Decision` (for `ALLOW`, includes the matching `base.<action>` permit when `grdr.base` is in scope).
   - `determining_forbids`: optional exact set of determining `forbid` rule `@id`s (allowing T2/T3 to assert `determining_forbids: []` cleanly). At least one of `determining_rules` or `determining_forbids` should be specified when asserting verdicts unless only `verdict` + `findings` matters; when `verdict == "DENY"` and `determining_rules` is provided, the engine/CI checks exact `@id` equality.
   - `findings`: optional list of shadow/watch `@id` rule identifiers (default `[]`).
   - `obligations`: optional list of `#212` `Obligation` spellings (default `[]`).
6. **`forbid`-rule coverage rule (`design/12` section 11, `#1889` check 4, `#41` R1 & AC-1):**
   - Every `forbid` rule in a pack must be covered by at least one `polarity: positive` and one `polarity: negative` test case naming `rule: <its @id>` (measured by `#1889` CI and policy validator; `GRDR-PACK-0015`).
   - `Permit` statements inside `grdr.base` (such as `#41` R1's fifteen unconditional `base.<class>` action permits) are exempt from per-rule positive/negative coverage because an unconditional action permit carries no blocking condition inside that action class; once `#1894` adds `forbid` rules to `grdr.base`, each such `forbid` rule requires positive and negative tests as normal.

### 8. Integration of `messages/<locale>.mf2.toml` and `session-rules.yaml`

1. **`messages/<locale>.mf2.toml` ([RFC 0017](./0017-grdr-strings-language-token-runtime.md) / `ADR-0055` alignment):**
   - **Optional in slice 0:** Packs without localised overrides (including `#41`'s `grdr.base` and `grdr.essentials`) omit `messages/` cleanly.
   - **Strict `ARCH-001` and `ARCH-024` boundary:** `grdr-strings` sits at layer 2 and `grdr-strings/pack-text` is forbidden outside `{ grdr-engine, grdr-server, grdr }` (RFC 0017 section 4). Layer-1 `grdr-core` therefore does not link `grdr-strings` or `icu*`. Instead, `grdr_core::compile::pack` uses the already-admitted `toml` crate to validate every `packs/<pack-id>/messages/<locale>.mf2.toml` (max `pack.message-file-max = 65536` bytes, matching `strings.pack-blob-max` of RFC 0017):
     ```toml
     schema_version = 1
     locale = "fr"

     [rules."essentials.bypass-flags"]
     message = "..."
     ```
   - Layer 1 verifies: `schema_version == 1`, `locale` matches filename `<locale>` (exact string), `#[serde(deny_unknown_fields)]`, every key under `[rules]` matches an `@id` defined in that pack, and every `message` string passes `#212` R12 lexical inert-text checks (`len <= policy.annotation-max`, valid UTF-8, no `://`, no case-insensitive `www.`, and no C0/C1/bidi control characters `U+0000..=U+001F`, `U+007F..=U+009F`, `U+061C`, `U+200E..=U+200F`, `U+202A..=U+202E`, `U+2066..=U+2069`). Full Unicode NFC normalisation verification and MF2 AST compilation stay in Layer-2/Layer-4 `grdr-strings::CompiledPackMessage` / `grdr-interface-gen` (`GRDR-IFG-0009`, RFC 0017), keeping `icu*` out of `grdr-core` (`ARCH-024`). Note `@steer` is never translated (`agent`-domain English text in `docs/design/12` section 3), so `[rules."<id>"]` carries `message` only (`#[serde(deny_unknown_fields)]` forbids `steer` in `messages/`).
   - At layer 4 (`grdr-engine`, `grdr-server`, `grdr`), programs holding `grdr-strings/pack-text` parse and compile `PackLocaleMessages` entries via `grdr_strings::MessageTemplate::parse(..., MessageDomain::PackRule, ...)` for viewer rendering; when absent, rendering falls back cleanly to the English `@message` on the compiled rule metadata (`#1861` R5, `design/34` section 7).
2. **`session-rules.yaml` reservation (`P9`, `#1894`):**
   - `MemberPath` allows optional `packs/<pack-id>/session-rules.yaml` in the path grammar. In slice 0 (`format_version = 1`), any `session-rules.yaml` with non-whitespace content returns `PackError::SessionRulesUnsupported` (`GRDR-PACK-0013`) so a slice-1 file is never silently accepted while unimplemented (`P9`).

### 9. Public Rust surface (`grdr-model` and `grdr-core::compile::pack`)

#### 9.1 `grdr-model` (`crates/grdr-model/src/bundle.rs`, crate root exports)
```rust
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct MemberPath(/* validated bundle-relative ASCII UTF-8 path (Rule 1 hygiene) */);
impl MemberPath {
    pub fn parse(raw: &str, max_bytes: usize) -> Result<Self, BundleArchiveError>;
    pub fn as_str(&self) -> &str;
}

#[derive(Clone, Copy, Debug)]
pub struct ArchiveEntryInput<'a> {
    pub path: &'a MemberPath,
    pub bytes: &'a [u8],
    pub sha256: [u8; 32],
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BundleLimits {
    pub archive_max: usize,
    pub members_max: usize,
    pub member_max: usize,
    pub path_max: usize,
    pub packs_max: usize,
    pub pack_id_max: usize,
}
impl BundleLimits {
    pub fn from_schema() -> Self; // reads grdr_schema::limits::{BUNDLE_*, PACK_ID_MAX}
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ArchiveEntryView<'a> {
    pub path: &'a str,
    pub payload: &'a [u8],
    pub sha256: [u8; 32],
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DecodedBundleArchive<'a> { /* sorted Vec<ArchiveEntryView<'a>> */ }
impl<'a> DecodedBundleArchive<'a> {
    pub fn entries(&self) -> &[ArchiveEntryView<'a>];
    pub fn get(&self, path: &str) -> Option<&'a [u8]>;
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq)] // manual redacting Debug; no Display or Error (RFC 0009 R4)
pub enum BundleArchiveError {
    MagicOrVersion { magic_ok: bool, version: u32 },
    HeaderInvalid { actual_len: usize, flags: u32, reserved: u32, declared_total_len: u64 },
    OverLimit { bound: &'static str, actual: u64, limit: u64 },
    IndexMalformed { entry_index: usize },
    MemberPathInvalid { byte_len: usize },
    MemberPathOrderOrDuplicate { entry_index: usize },
    UnsupportedMemberPath { byte_len: usize },
    EmptyArchive,
    TooManyPacks { count: usize, max: usize },
}
// BundleArchiveError implements grdr_schema::codes::Coded (GRDR-BUNDLE-0002..0010, exhaustive)
// and grdr_model::LogSafe (LogValue::Code(self.code())).

pub fn encode_bundle_archive(
    entries: &[ArchiveEntryInput<'_>],
    limits: &BundleLimits,
) -> Result<Vec<u8>, BundleArchiveError>;

pub fn decode_bundle_archive<'a>(
    bytes: &'a [u8],
    limits: &BundleLimits,
) -> Result<DecodedBundleArchive<'a>, BundleArchiveError>;
```
Notes:
- `MemberPath::parse(raw, max_bytes)` validates Section 3 Rule 1 (`GRDR-BUNDLE-0006`, bounded by `limits.path_max`), while `encode_bundle_archive`, `decode_bundle_archive` and `grdr_core::compile::pack::read_bundle_members` share one `grdr-model` slice-0 path-layout validator enforcing Section 3 Rules 2 and 3 (`GRDR-BUNDLE-0008` using `limits.pack_id_max`, case-collision check `GRDR-BUNDLE-0007`) and pack cap `limits.packs_max` (`GRDR-BUNDLE-0010`), using checked `u64` arithmetic.
- Because `grdr-model` declares `renders = "none"` ([RFC 0009](./0009-grdr-model-slice-0-surface.md) R4, [ADR-0053](../docs/decisions/ADR-0053-cedar-schema-grdr-policy-surface-adopted-by-rfc-0013.md) `PolicyRuleIdError`), `BundleArchiveError` does not implement `std::fmt::Display` or `std::error::Error`; callers inspect `Coded::code()` and `LogSafe` (`P8`), and `Debug` prints structural indices/lengths/bounds only, never payload bytes.

#### 9.2 `grdr-core` (`crates/grdr-core/src/compile/pack.rs` and `crates/grdr-core/src/engine/bundle.rs`)
```rust
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PackId(/* validated pack identifier e.g. "grdr.essentials" */);

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct SemVer { /* major, minor, patch: u64, pre: Option<String>, build: Option<String> */ }
impl SemVer {
    pub fn parse(raw: &str, max_bytes: usize) -> Result<Self, PackError>;
    pub fn cmp_precedence(&self, other: &Self) -> core::cmp::Ordering;
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum PackKind { Policy, Sigma, Yara, Catalogue }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum PackChannel { Policy, DetectionContent, Schema, AgentConfig }

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DeclaredRead {
    pub field: String,
    pub data_class: DataClass,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PackManifest {
    pub format_version: u32,
    pub id: PackId,
    pub kind: PackKind,
    pub version: SemVer,
    pub min_engine: SemVer,
    pub channel: PackChannel,
    pub mode: grdr_model::Mode,
    pub rule_prefixes: Vec<String>,
    pub on_loss: Option<grdr_model::OnLoss>,
    pub requires_capabilities: Vec<String>,
    pub reads: Vec<DeclaredRead>,
}

#[derive(Clone, Debug)]
pub enum ParsedRule {
    Permit {
        id: grdr_model::PolicyRuleId,
        policy: cedar_policy::Policy,
        source_path: grdr_model::MemberPath,
    },
    Forbid {
        meta: grdr_model::RuleMeta,
        policy: cedar_policy::Policy,
        source_path: grdr_model::MemberPath,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum TestPolarity { Positive, Negative }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum PrincipalType { Session, Process }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum PackTestResolution { Resolved, Unresolved, Malformed }

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StructuredTestRequest {
    pub principal_type: PrincipalType,
    pub action: grdr_model::ActionClass,
    pub control_point: grdr_model::ControlPoint,
    pub resource_classes: Vec<String>,
    pub facts: Vec<String>,
    pub session_labels: Vec<String>,
    pub grants: Vec<grdr_model::PolicyRuleId>,
}

#[derive(Clone, PartialEq, Eq)] // manual redacting Debug: omits raw/env command text
pub struct CommandTestInput {
    pub raw: String,
    pub cwd: String,
    pub dialect: crate::analyze::ShellDialect,
    pub env: std::collections::BTreeMap<String, String>,
    pub request_defaults: StructuredTestRequest,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CommandAnalysisExpectation {
    pub resolution: PackTestResolution,
    pub facts: Vec<String>,
    pub absent_facts: Vec<String>,
    pub command_classes: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModeExpectation {
    pub mode: grdr_model::Mode,
    pub verdict: grdr_model::Verdict,
    pub determining_rules: Option<Vec<grdr_model::PolicyRuleId>>,
    pub determining_forbids: Option<Vec<grdr_model::PolicyRuleId>>,
    pub findings: Vec<grdr_model::PolicyRuleId>,
    pub obligations: Vec<grdr_model::Obligation>,
}

#[derive(Clone, PartialEq, Eq)] // manual redacting Debug
pub enum PackTestKind {
    Structured {
        request: StructuredTestRequest,
        expectations: Vec<ModeExpectation>,
    },
    Command {
        command: CommandTestInput,
        expect_analysis: Option<CommandAnalysisExpectation>,
        expectations: Vec<ModeExpectation>,
    },
}

#[derive(Clone, PartialEq, Eq)] // manual redacting Debug
pub struct PackTestCase {
    pub id: String,
    pub rule: Option<grdr_model::PolicyRuleId>,
    pub polarity: Option<TestPolarity>,
    pub selftest: bool,
    pub kind: PackTestKind,
}

#[derive(Clone, PartialEq, Eq)] // manual redacting Debug
pub struct PackTestSuite {
    pub schema_version: u32,
    pub source_path: grdr_model::MemberPath,
    pub tests: Vec<PackTestCase>,
}

#[derive(Clone, PartialEq, Eq)] // manual redacting Debug: omits rule text strings
pub struct PackRuleMessages {
    pub message: String,
}

#[derive(Clone, PartialEq, Eq)] // manual redacting Debug
pub struct PackLocaleMessages {
    pub schema_version: u32,
    pub locale: String,
    pub source_path: grdr_model::MemberPath,
    pub rules: std::collections::BTreeMap<grdr_model::PolicyRuleId, PackRuleMessages>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PackLimits {
    pub bundle: grdr_model::BundleLimits,
    pub bundle_rules_max: usize,
    pub version_max: usize,
    pub rule_prefixes_max: usize,
    pub capabilities_max: usize,
    pub reads_max: usize,
    pub read_field_max: usize,
    pub pack_rules_max: usize,
    pub tests_max: usize,
    pub yaml_input_max: usize,
    pub yaml_depth_max: usize,
    pub yaml_items_max: usize,
    pub message_file_max: usize,
    pub parser_input_max: usize,
    pub rule_id_max: usize,
    pub annotation_max: usize,
    pub class_name_max: usize,
    pub list_max_entries: usize,
    pub list_entry_max: usize,
    pub vocabulary_max_entries: usize,
    pub shell_input_max: usize,
}
impl PackLimits {
    pub fn from_schema() -> Self; // reads grdr_schema::limits::*
}

#[derive(Clone, Debug)]
pub struct PolicyPack {
    pub manifest: PackManifest,
    pub rules: Vec<ParsedRule>,
    pub lists: Vec<crate::analyze::VocabularyList>,
    pub tests: Vec<PackTestSuite>,
    pub messages: Vec<PackLocaleMessages>,
}

#[derive(Clone, Debug)]
pub struct PolicyBundle {
    pub packs: Vec<PolicyPack>, // sorted lexicographically by PackId
}

#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PackError {
    BundleDigestMismatch,
    BundleArchive(grdr_model::BundleArchiveError),
    TooManyBundleRules { count: usize, max: usize },
    ManifestMissing { pack_id: String },
    ManifestSyntax { path: String },
    ManifestField { path: String, field: &'static str },
    ManifestUnsupportedVersion { path: String },
    RulesMissingOrEmpty { path: String },
    RuleSyntaxOrSchema { path: String },
    PermitOutsideBase { path: String, pack_id: String },
    RuleAnnotation { path: String, rule_id: Option<String> },
    RuleMeta { path: String, source: grdr_model::RuleMetaError },
    Policy { path: String, source: crate::policy::PolicyError },
    ListSyntax { path: String },
    ListConflict { path: String, class: String },
    Vocab(crate::analyze::VocabError),
    TestSuiteInvalid { path: String, test_id: Option<String> },
    MessageCatalogueInvalid { path: String, locale: Option<String> },
    SessionRulesUnsupported { path: String },
}
// PackError implements grdr_schema::codes::Coded (delegating BundleArchive, RuleMeta,
// Policy and Vocab to source.code()), grdr_model::LogSafe (LogValue::Code(self.code())),
// manual redacting Debug, and core::fmt::Display / core::error::Error rendering strictly
// self.code().as_str() (never prose or pack text, preserving grdr-core renders = "none").

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PackReadContext<'a> {
    pub engine_version: &'a SemVer,
    pub supported_capabilities: &'a [&'a str],
}

pub fn read_bundle_members<'a>(
    members: &std::collections::BTreeMap<grdr_model::MemberPath, &'a [u8]>,
    ctx: &PackReadContext<'_>,
    limits: &PackLimits,
) -> Result<PolicyBundle, PackError>;

pub(crate) fn read_archive<'a>(
    archive: &grdr_model::DecodedBundleArchive<'a>,
    ctx: &PackReadContext<'_>,
    limits: &PackLimits,
) -> Result<PolicyBundle, PackError>;
```
And inside `crates/grdr-core/src/engine/bundle.rs` (re-exported under `grdr_core::engine`, reusing `engine::boundary::bundle_sha256` per RFC 0014):
```rust
pub fn pack_verified_members<'a>(
    members: &std::collections::BTreeMap<grdr_model::MemberPath, &'a [u8]>,
    limits: &grdr_model::BundleLimits,
) -> Result<(Vec<u8>, [u8; 32]), grdr_model::BundleArchiveError>;

pub fn load_verified_policy_bundle(
    bundle: &grdr_model::VerifiedBundle,
    ctx: &crate::compile::pack::PackReadContext<'_>,
    limits: &crate::compile::pack::PackLimits,
) -> Result<crate::compile::pack::PolicyBundle, crate::compile::pack::PackError>;
```
Notes:
- `PackLimits` embeds `grdr_model::BundleLimits` (whose `pack_id_max` and `packs_max` govern pack-id length and pack count across both `encode_bundle_archive`/`decode_bundle_archive` and `read_bundle_members`) plus `bundle_rules_max` (`BUNDLE_RULES_MAX`) and `#212`/`#213`/`pack.*` bounds, with `PackLimits::from_schema()` reading `grdr_schema::limits::*` (`ARCH-019`).
- `cedar_policy::Policy` sits inside `ParsedRule` behind `grdr-core`'s existing `experimental` exposure rule tracked by [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md) (`ARCH-007`), to be wrapped before `grdr-core` leaves `experimental`.
- `ParsedRule`, `PackTestSuite`, `PackTestCase`, `PackLocaleMessages` and `PackError` implement manual redacting `Debug` (`P8`): command raw text, env maps and `@message`/`@steer` text never enter error values or `LogSafe` output (`PackError` carries code, pack id, relative path, line/column and rule/test id only). `PackError::Display` prints `self.code().as_str()` only, matching `PolicyError` ([RFC 0013](./0013-cedar-schema-grdr-policy-surface.md)) and `LoadError` ([RFC 0014](./0014-engine-boundary-c-abi.md)) while keeping `crates/grdr-core/Cargo.toml` `renders = "none"` (`D-69`, UX6).

### 10. Dependencies, purity and architecture compliance
- **TOML parsing (`toml` + `serde`):** Reuses `toml = "=1.2.2+spec-1.1.0"` (default features disabled, `parse` and `serde` features enabled, zero `preserve_order`, `#![forbid(unsafe_code)]`, `MIT OR Apache-2.0`) and `serde = { version = "=1.0.229", features = ["derive"] }` already admitted in [supply-chain/admissions.toml](../supply-chain/admissions.toml) by `#1575`. Cooldown `not_before = "2026-11-24T04:25:29Z"` is respected before `#1885` updates `Cargo.lock`. `#1885` adds `{ crate = "grdr-core", kind = "normal", issue = 1885 }` to `#1575`'s `consumers` list in `supply-chain/admissions.toml`. No new third-party crate is admitted.
- **`ARCH-001`, `ARCH-003` and `wasm32`:** `grdr-model` (`grdr-schema` only) and `grdr-core` (`grdr-schema`, `grdr-model`, `grdr-proto`, `grdr-fastpath` layout, `cedar-policy` no-default, `brush-parser` no-default, `toml`, `serde`) perform zero I/O, zero clock reads, zero randomness reads, zero `unsafe` (`[workspace.lints] unsafe_code = "forbid"`, `#![deny(clippy::arithmetic_side_effects)]`), and build cleanly for `wasm32-unknown-unknown`.
- **`ARCH-004` (`content_parsers`):** `grdr-core` is already in `[arch004] content_parsers` ([architecture.toml](../architecture.toml)). Adding `"toml"` to `content_parsers` (or confirming neither `toml` nor `grdr-core` ever enters `grdr-daemon`, `grdr-updater`, `grdr-approve`, or `grdr-hook` normal dependencies; `grdr-schema` keeps `toml` solely under `[dev-dependencies]`) prevents accidental parser drift into privileged closures.
- **`ARCH-012`:** `VerifiedBundle::assume_verified` is never called in `grdr-core` or `grdr-model::bundle`. `grdr-daemon` constructs `VerifiedBundle` via `grdr-crypto`; `grdr-ffi` and `grdr-wasm` call `assume_verified` solely at their documented FFI/Wasm ingress points (`RFC 0014`).
- **`ARCH-013`:** `compile::pack` lives inside `crates/grdr-core/src/compile/`, importing `grdr_model`, `grdr_schema`, `crate::analyze`, `crate::policy` and `cedar_policy`, with zero sibling edge into `analyze` or `policy` and zero reverse edge from `compile` to `engine`.
- **`ARCH-024`:** `grdr-core` takes no dependency on `grdr-strings` or `icu*`.

### 11. `BUNDLE` and `PACK` error codes and `limits.toml` bounds

#### 11.1 `schema/codes/areas.toml`, `bundle.toml` and `pack.toml` ([RFC 0007](./0007-grdr-model-and-grdr-schema-slice-0-surface.md))
```toml
[area.BUNDLE]
subsystem = "bundle archive"
owner = "design/12"

[area.PACK]
subsystem = "policy pack"
owner = "design/12"
```

| Code | Reason (`UPPER_SNAKE`) | Class | Connect code | Registered by | When raised |
|---|---|---|---|---|---|
| `GRDR-BUNDLE-0001` | `BUNDLE_DIGEST_MISMATCH` | `input` | `invalid_argument` | `#1885` | `VerifiedBundle::digest()` or member `payload_sha256` fails SHA-256 check |
| `GRDR-BUNDLE-0002` | `ARCHIVE_MAGIC_OR_VERSION` | `input` | `invalid_argument` | `#1885` | `GRDB` magic or `format_version != 1` mismatch |
| `GRDR-BUNDLE-0003` | `ARCHIVE_HEADER_INVALID` | `input` | `invalid_argument` | `#1885` | Short header, non-zero `flags`/`reserved`, or `total_len != bytes.len()` |
| `GRDR-BUNDLE-0004` | `ARCHIVE_OVER_LIMIT` | `input` | `invalid_argument` | `#1885` | Frame bytes, `member_count`, path len or payload len over `bundle.*` limits |
| `GRDR-BUNDLE-0005` | `ARCHIVE_INDEX_MALFORMED` | `input` | `invalid_argument` | `#1885` | Offset/length arithmetic overflow or non-contiguous path/payload offsets |
| `GRDR-BUNDLE-0006` | `MEMBER_PATH_INVALID` | `input` | `invalid_argument` | `#1885` | Empty, non-ASCII, traversal (`.`, `..`), `\\`, `//`, leading/trailing `/` |
| `GRDR-BUNDLE-0007` | `MEMBER_PATH_ORDER_OR_DUP` | `input` | `invalid_argument` | `#1885` | Unsorted paths, duplicate paths or ASCII case collision |
| `GRDR-BUNDLE-0008` | `UNSUPPORTED_MEMBER_PATH` | `input` | `invalid_argument` | `#1885` | Path outside `packs/<pack-id>/{pack.toml,rules/*.cedar,lists/*.toml,tests/*.yaml,messages/*.mf2.toml,session-rules.yaml}` |
| `GRDR-BUNDLE-0009` | `EMPTY_ARCHIVE` | `input` | `invalid_argument` | `#1885` | `member_count == 0` or zero packs in archive/map |
| `GRDR-BUNDLE-0010` | `BUNDLE_PACKS_OVER_LIMIT` | `input` | `invalid_argument` | `#1885` | Distinct packs exceed `BUNDLE_PACKS_MAX` |
| `GRDR-BUNDLE-0011` | `BUNDLE_RULES_OVER_LIMIT` | `input` | `invalid_argument` | `#1885` | Aggregate rules across bundle exceed `BUNDLE_RULES_MAX` (`TooManyBundleRules`) |
| `GRDR-PACK-0001` | `MANIFEST_MISSING` | `input` | `invalid_argument` | `#1885` | Pack directory lacks `pack.toml` |
| `GRDR-PACK-0002` | `MANIFEST_SYNTAX_INVALID` | `input` | `invalid_argument` | `#1885` | `pack.toml` invalid UTF-8, invalid TOML, missing/unknown key (`P7`) or oversized |
| `GRDR-PACK-0003` | `MANIFEST_FIELD_INVALID` | `input` | `invalid_argument` | `#1885` | Invalid `id`, dir/`id` mismatch, non-policy `kind`/`channel`, invalid SemVer, bad `mode`, bad `grdr.base` mode, invalid/duplicate `reads`, or bad prefix |
| `GRDR-PACK-0004` | `MANIFEST_VERSION_UNSUPPORTED` | `input` | `failed_precondition` | `#1885` | Unsupported `format_version`, `min_engine > current_engine`, or unsupported capability |
| `GRDR-PACK-0005` | `RULES_MISSING_OR_EMPTY` | `input` | `invalid_argument` | `#1885` | Pack lacks `rules/*.cedar`, a rule file has zero policies, or pack exceeds `pack.rules-max` |
| `GRDR-PACK-0006` | `RULE_SYNTAX_OR_SCHEMA` | `input` | `invalid_argument` | `#1885` | Cedar parse error, Cedar template present, or `ValidationMode::Strict` error/warning |
| `GRDR-PACK-0007` | `PERMIT_OUTSIDE_BASE` | `policy` | `invalid_argument` | `#1885` | `permit` statement appears outside `grdr.base` |
| `GRDR-PACK-0008` | `RULE_ANNOTATION_INVALID` | `input` | `invalid_argument` | `#1885` | Source `@mode`, missing/bad `permit` `@id`/annotation, duplicate `@id`, or cross-pack overlapping prefix |
| `GRDR-PACK-0009` | `LIST_SYNTAX_INVALID` | `input` | `invalid_argument` | `#1885` | `lists/*.toml` invalid UTF-8/TOML/unknown key, empty/duplicate/control-char entry or size/count overflow |
| `GRDR-PACK-0010` | `LIST_CONFLICT` | `input` | `invalid_argument` | `#1885` | Invalid `ListType`/`Polarity`/`ManagedBy`/`ClassName`, invalid feed list, duplicate `(type, class)` or polarity conflict |
| `GRDR-PACK-0011` | `TEST_SUITE_INVALID` | `input` | `invalid_argument` | `#1885` | `tests/*.yaml` invalid UTF-8, invalid YAML subset, duplicate key, forbidden construct, depth/item/size overflow, bad test schema or duplicate test id |
| `GRDR-PACK-0012` | `MESSAGE_CATALOGUE_INVALID` | `input` | `invalid_argument` | `#1885` | `messages/<locale>.mf2.toml` invalid UTF-8/TOML, locale mismatch, unknown rule id, forbidden control/URL or over `pack.message-file-max` |
| `GRDR-PACK-0013` | `SESSION_RULES_UNSUPPORTED` | `input` | `failed_precondition` | `#1885` | Non-empty `session-rules.yaml` present in slice 0 |
| `GRDR-PACK-0014` | `READS_CHECK_FAILED` | `input` | `invalid_argument` | `#1889` / `#1538` | Pack `[[reads]]` fails `#216` `check_declared` (constructed by validator/CI) |
| `GRDR-PACK-0015` | `TEST_COVERAGE_MISSING` | `input` | `invalid_argument` | `#1889` | A `forbid` rule lacks positive or negative test coverage |
| `GRDR-PACK-0016` | `TEST_ASSERTION_FAILED` | `input` | `failed_precondition` | `#1889` / `#1538` | Pack test case fails expected verdict, rule ids, findings or analysis facts/classes |

`ARCH-017` rule-adherence note: `#1885` registers only `GRDR-BUNDLE-0001`..`0011` and `GRDR-PACK-0001`..`0013` (all constructed by `BundleArchiveError` / `PackError` in `#1885`, while `PackError` delegates `RuleMeta`, `Policy`, `Vocab` and `BundleArchive` via `source.code()`, including `PolicyError::ParserInputOverLimit` `GRDR-POLICY-0012`); `#1889` and `#1538` register and construct `GRDR-PACK-0014`..`0016` additively when validator/test-runner checks land so zero unused registered codes exist on `main` in between.

#### 11.2 `[bound.bundle.*]` and `[bound.pack.*]` rows in `limits.toml`
All bound names adhere strictly to RFC 0007 section 6 naming rules (`[a-z][a-z0-9]*(-[a-z0-9]+)*`, zero unit words or reserved keywords inside any segment), all `scope = "fixed"`, `effect = "none"`, `owner = "design/12"`:

| Bound name | Unit = value | `min..=max` | Generated constant | Caps |
|---|---|---|---|---|
| `bundle.archive-max` | `bytes = 4194304` | `4096..=16777216` | `BUNDLE_ARCHIVE_MAX` | Maximum total `GRDB` v1 archive size (4 MiB; comfortably inside RFC 0014 64 MiB Wasm cap) |
| `bundle.members-max` | `count = 256` | `1..=4096` | `BUNDLE_MEMBERS_MAX` | Maximum member files per archive |
| `bundle.member-max` | `bytes = 1048576` | `1024..=4194304` | `BUNDLE_MEMBER_MAX` | Maximum raw byte length of one archive member |
| `bundle.path-max` | `bytes = 256` | `64..=512` | `BUNDLE_PATH_MAX` | Maximum UTF-8 byte length of one `MemberPath` |
| `bundle.packs-max` | `count = 64` | `1..=256` | `BUNDLE_PACKS_MAX` | Maximum distinct packs per bundle |
| `bundle.rules-max` | `count = 5000` | `1..=10000` | `BUNDLE_RULES_MAX` | Maximum total rules across one bundle (`design/12` section 16) |
| `pack.id-max` | `bytes = 128` | `16..=256` | `PACK_ID_MAX` | Maximum `PackId` byte length |
| `pack.version-max` | `bytes = 64` | `16..=128` | `PACK_VERSION_MAX` | Maximum `SemVer` string length in `pack.toml` |
| `pack.rule-prefixes-max` | `count = 16` | `1..=64` | `PACK_RULE_PREFIXES_MAX` | Maximum `rule_prefixes` entries per pack |
| `pack.capabilities-max` | `count = 32` | `1..=128` | `PACK_CAPABILITIES_MAX` | Maximum `requires_capabilities` entries per pack |
| `pack.reads-max` | `count = 128` | `1..=512` | `PACK_READS_MAX` | Maximum `[[reads]]` entries per pack |
| `pack.read-field-max` | `bytes = 128` | `16..=256` | `PACK_READ_FIELD_MAX` | Maximum schema field path length in `[[reads]]` |
| `pack.rules-max` | `count = 1024` | `1..=5000` | `PACK_RULES_MAX` | Maximum Cedar rules per pack |
| `pack.tests-max` | `count = 2048` | `1..=10000` | `PACK_TESTS_MAX` | Maximum test cases across a pack |
| `pack.yaml-input-max` | `bytes = 262144` | `4096..=1048576` | `PACK_YAML_INPUT_MAX` | Maximum raw byte length of one `tests/*.yaml` file |
| `pack.yaml-depth-max` | `count = 8` | `4..=16` | `PACK_YAML_DEPTH_MAX` | Maximum YAML container nesting depth |
| `pack.yaml-items-max` | `count = 16384` | `64..=65536` | `PACK_YAML_ITEMS_MAX` | Maximum total YAML AST nodes per file |
| `pack.message-file-max` | `bytes = 65536` | `1024..=262144` | `PACK_MESSAGE_FILE_MAX` | Maximum byte length of one `messages/<locale>.mf2.toml` |

Existing bounds in [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md) (`policy.parser-input-max`, `policy.rule-id-max`) and `#741` (`PC-2`: `policy.annotation-max`, `policy.class-name-max`, `policy.list-max-entries`, `policy.list-entry-max`, `policy.vocabulary-max-entries`, aligned with RFC 0007 section 6 unit-word-free naming) supply the remaining rule and list limits.

### 12. Mechanisms (`P14`), Data classes (`P8`), Assurance (`P1`), Failure modes (`P9`)
- **Mechanism (`P14`):** Policy behaviour, rule classes, bypass flag tokens, declared read sets and test vectors stay wholly inside signed pack directories (`packs/<pack-id>/`), compiled/parsed by one shared codec (`grdr-model` + `grdr_core::compile::pack`) and bounded by `limits.toml`.
- **Data classes (`P8`):** Pack manifests, Cedar schemas/annotations, rule `@id`s, list entries and schema read paths are `structural`. Raw command test inputs in `tests/*.yaml` are `structural` pack fixtures evaluated solely during offline CI (`#1889`) or device self-tests (`#1538`); neither test raw command text nor pack `@message`/`@steer` strings ever appear in `LogSafe` records or error structs (`PackError` / `BundleArchiveError`).
- **Assurance effect (`P1`):** Strict pack validation and closed `GRDB` v1 decoding never admit degraded fallbacks: `grdr.base` must run in `Mode::Block`, `permit` is disallowed outside `grdr.base`, and any malformed archive or pack rejects bundle load/compile so the device preserves last-known-good tables (`#1538`) or container-scoped floor-missing fail-closed protection (`D-15`, RFC 0005 / RFC 0011).
- **Failure modes (`P9`):** Every unknown key, version mismatch, unsupported capability, non-empty `session-rules.yaml`, gap byte, unsorted path or SHA-256 mismatch exits with its distinct `GRDR-BUNDLE-*` or `GRDR-PACK-*` code and never substitutes a silent default.

### 13. Follow-up changes and issue write-backs
Upon decision of RFC 0019:
- **Protected gate/schema/trust-core items (extending existing `#278`, `#279`, `#1575` / `lead-agent-kit`):**
  1. Register areas `BUNDLE` (`0001..0011`) and `PACK` (`0001..0013`) in `schema/codes/{areas,bundle,pack}.toml` (via `#278` or `#1885`'s protected sub-step, plus `0014..0016` additively when `#1889`/`#1538` construct them).
  2. Add the 18 `[bound.bundle.*]` and `[bound.pack.*]` rows (Section 11.2) to `limits.toml` (blocked by `#279`), and align `#741`'s pending `policy.*` bound names (`policy.annotation-max`, `policy.class-name-max`, `policy.list-max-entries`, `policy.list-entry-max`, `policy.vocabulary-max-entries`, `policy.command-entry-max-tokens`) with RFC 0007 section 6 unit-word-free naming.
  3. Update `supply-chain/admissions.toml` (`consumers` row for `grdr-core` on `#1575`'s `toml`/`serde` admission after `not_before = "2026-11-24T04:25:29Z"`) and `architecture.toml` (`[arch004]` note confirming `toml` exclusion from privileged programs).
  4. **Protected `security/trust-core.paths` nominations (`lead-agent-kit` / `chief-architect`, prerequisite before `#1885` lands, `D-63`):** add `crates/grdr-model/src/bundle.rs`, `crates/grdr-model/src/bundle/**`, `crates/grdr-core/src/compile/pack.rs`, `crates/grdr-core/src/compile/pack/**`, `crates/grdr-core/src/engine/bundle.rs` and `crates/grdr-core/src/engine/bundle/**` to `security/trust-core.paths` (matching `crates/grdr-core/src/policy` and `compile/fastpath` trust-core gating over `VerifiedBundle` decoding and policy pack parsing).
- **Required specification write-backs on open issues:**
  - **`#1885`:** Set **`Trust core: yes`** (`D-63` / `.claude/risk-tiers.toml`: `eval-review` and `eval-security` on two distinct models or providers, plus `eval-architecture` and `eval-adversarial`). Specify `grdr-model::bundle` (`GRDB` v1 archive encoder/decoder, `MemberPath`, `BundleLimits` including `pack_id_max`, `BundleArchiveError` without `Display`/`Error` per RFC 0009 R4), `grdr_core::compile::pack` (`read_bundle_members`, `pub(crate) read_archive`, `PolicyBundle`, `PolicyPack`, `PackManifest`, `ParsedRule::{Permit, Forbid}` using `MemberPath`, `lists/*.toml`, `tests/*.yaml` with pure-Rust YAML 1.2 subset parser and five `grdr_model::Verdict` values, `messages/<locale>.mf2.toml` lexical inert checks, non-empty `session-rules.yaml` refusal), `grdr_core::engine::bundle::{pack_verified_members, load_verified_policy_bundle}`, `GRDR-BUNDLE-0001..0011` and `GRDR-PACK-0001..0013` codes, and round-trip + fuzz/hostile tests (`grdr_core` `wasm32` check included). Blocked by `#278`, `#279`, `#435`, `#739`, `#212`, `#213`, the `security/trust-core.paths` item, and `#1575` `toml` admission (`grdr-core` Cargo dependency item).
  - **`#41`:** Adopt Section 4 `pack.toml` keys (`format_version = 1`, `id`, `kind = "policy"`, `version`, `min_engine`, `channel`, `mode = "Block"` for `grdr.base` / `"Watch"` for `grdr.essentials`, `[[reads]]`), Section 5 `grdr.base` `Permit` `@id`-only rules, Section 6 `lists/<stem>.toml` TOML format (`flag.bypass-permissions.toml`, `flag.hooks-disabled.toml`, `grdr.disable.toml` with `managed_by = "pack"`), and Section 7 `tests/bypass-flags.yaml` (`schema_version: 1`, `T1..T3` `kind: structured` with `positive`/`negative` + `selftest: true`, `T4..T9` `kind: command` with `cwd` and `expect_analysis` / `absent_facts: ["flag.*"]`).
  - **`#1889`:** Call `grdr_core::compile::pack::read_bundle_members` plus a deterministic `pack_verified_members` -> `VerifiedBundle` (via `grdr-crypto`) -> `load_verified_policy_bundle` round-trip check; apply Section 7.2 rule 6 so `forbid` rules enforce `>= 1` positive and `>= 1` negative tests while `grdr.base`'s unconditional `permit` statements pass check 4; register/construct `GRDR-PACK-0014..0016` for reads, coverage and test failures.
  - **`#1538`:** `grdr-daemon` `BundleSource` walks installed `<bundle-dir>/packs/<pack-id>/...` files (rejecting symlinks/non-regular files and paths failing `MemberPath`), computes per-member SHA-256 via `grdr-crypto`, encodes canonical `GRDB` v1 bytes via `grdr_model::encode_bundle_archive`, builds `VerifiedBundle` via `grdr-crypto`, seals descriptor (`memfd`/handle), and runs `tests/*.yaml` cases with `selftest: true` in the compile instance before adopting tables.
  - **`#1861`:** `Engine::load(&VerifiedBundle, &HostProfile)` loads policy bundles exclusively via `load_verified_policy_bundle` (checking whole-archive and per-entry `GRDB` v1 digests and parsing through `compile::pack`), checks `min_engine` and `requires_capabilities`, compiles layers/sets (`#71`, `#218`, `#216`) into `PolicyState`, and surfaces `GRDR-BUNDLE-*` / `GRDR-PACK-*` through `LoadError::Policy`.
  - **`#1862`:** Confirms `<bundle-dir>/packs/<pack-id>/...` installed directory layout matches `#1538` `BundleSource` verbatim.
  - **`#71` & `#739` (`RFC 0018`):** Confirms `grdr-model` (`RuleMeta`, `Mode`, `OnLoss`) and `grdr-core::analyze` (`VocabularyList`, `ListType`, `Polarity`, `ManagedBy`, `ClassName`) sit in `#739` / `#212` / `#213` without duplication, and `#71` reads `PackManifest.mode` (manifest Mode when no layer override exists) and `PackManifest.on_loss` directly from `PolicyPack`.
  - **Design doc sync (post-acceptance):** Note `lists/*.toml`, `GRDB` v1 inside `VerifiedBundle`, `grdr.base` `Mode::Block` + `permit`-exemption for per-rule tests, and slice-0 `tests/*.yaml` schema cleanly in `docs/design/11`, `docs/design/12` (§3, §10, §11, §14) and `docs/design/13` (§11).

## Surfaces changed
This RFC authors specification only (`rfcs/0019-slice-0-policy-pack-directory-and-bundle-encoding.md`). Acceptance authorises the following changes in follow-up items (amending [RFC 0009](./0009-grdr-model-slice-0-surface.md) `ADR-0041` for `grdr-model::bundle` additions and [RFC 0014](./0014-engine-boundary-c-abi.md) `ADR-0054` for `crates/grdr-model/src/bundle.rs` expansion and `engine::bundle`):

| Surface | Proposed change | Implementing item(s) |
|---|---|---|
| `grdr-model` (layer 1, public crate; amending RFC 0009 / RFC 0014; proposed trust core) | Expand `crates/grdr-model/src/bundle.rs` (`MemberPath`, `ArchiveEntryInput`, `BundleLimits`, `ArchiveEntryView`, `DecodedBundleArchive`, `encode_bundle_archive`, `decode_bundle_archive`, `BundleArchiveError` implementing `Coded` + `LogSafe` only, no `Display`/`Error`) | `#1885` (within `#739` / `#384` `bundle.rs` contract) |
| `grdr-core` (layer 1, `experimental`; amending RFC 0014 `engine`; proposed trust core) | Add `pub mod compile` -> `pub mod pack` (`PackId`, `SemVer`, `PackKind`, `PackChannel`, `DeclaredRead`, `PackManifest`, `ParsedRule`, `TestPolarity`, `PrincipalType`, `PackTestResolution`, `StructuredTestRequest`, `CommandTestInput`, `CommandAnalysisExpectation`, `ModeExpectation`, `PackTestKind`, `PackTestCase`, `PackTestSuite`, `PackRuleMessages`, `PackLocaleMessages`, `PackLimits`, `PolicyPack`, `PolicyBundle`, `PackError`, `PackReadContext`, `read_bundle_members`, with `pub(crate) read_archive` and private `yaml_subset`) and `crates/grdr-core/src/engine/bundle.rs` (`pack_verified_members`, `load_verified_policy_bundle`) | `#1885`, `#1889`, `#1861`, `#1538`, `#71` |
| `Cargo.toml`, `crates/grdr-core/Cargo.toml`, `supply-chain/admissions.toml` | Add `toml` (`parse`, `serde`) and `serde` (`derive`) to `grdr-core` under `#1575`'s existing admission | Protected dependency item (`#1575` / `#1885`) |
| `schema/codes/{areas,bundle,pack}.toml`, `limits.toml`, `architecture.toml`, `security/trust-core.paths` | Register `BUNDLE` (`0001..0011`), `PACK` (`0001..0013`, plus `0014..0016` on `#1889`/`#1538`), 18 `[bound.bundle.*]`/`[bound.pack.*]` limits, `ARCH-004` `toml` note, and trust-core path globs for `grdr-model/src/bundle*`, `grdr-core/src/compile/pack*` and `grdr-core/src/engine/bundle*` | `#278`, `#279`, `#1885`, `#1889`, `#1582`, trust-core gate item |
| Content pack format (`grdr-content`) | Adopt exact `pack.toml`, `rules/*.cedar`, `lists/*.toml`, `tests/*.yaml`, `messages/<locale>.mf2.toml` layouts | `#41`, `#1691`, `#1889`, `#1894`, `#1862` |
| `docs/design/11`, `docs/design/12`, `docs/design/13` | Document `GRDB` v1 member framing, `.toml` list extension, `grdr.base` `Mode = "Block"` and `permit` test exemption, and `tests/*.yaml` schema | Design follow-up upon acceptance |

## Alternatives
1. **Place the pack reader or `GRDB` archive encoder in `grdr-core` only and let `grdr-daemon` call it (rejected).** Violates `ARCH-004`: `grdr-daemon` is `privileged` and must never link `grdr-core`, `cedar-policy` or `toml`. Separating raw binary `GRDB` v1 framing (`grdr-model::bundle`) from TOML/YAML/Cedar parsing (`grdr_core::compile::pack`) preserves `ARCH-004` with zero parsing in privileged code and zero code duplication (`P17`).
2. **Use `tar` + `zstd` inside `VerifiedBundle` in slice 0 (rejected).** `docs/design/22` uses tar+zstd for `.grdrpack` network transfer (`#1251`, slice 4), whereas `VerifiedBundle` holds already-staged verified bytes passed in memory / `memfd` between `grdr-daemon` and `grdr-engine` (`#1538`, `#384`). Avoiding `tar`/`zstd` inside layer-1 `grdr-core` keeps `grdr-model` dependency-free, avoids `wasm32` compression overhead, eliminates archive header non-determinism (`mtime`, `uid`, pax headers) and guarantees zero unreferenced gap bytes.
3. **Pass multiple file descriptors across IPC instead of framing members inside `VerifiedBundle::bytes()` (rejected).** Violates [RFC 0014](./0014-engine-boundary-c-abi.md) (`Engine::load(&VerifiedBundle, &HostProfile)`), [spec/host-contract/c-abi.md](../spec/host-contract/c-abi.md) (`grdr_engine_load` takes one byte buffer), and `grdr-wasm` linear-memory transfer, and would create divergent code paths between daemon, C ABI, `wasm32` and content CI.
4. **Admit a crates.io YAML crate (`saphyr` / `serde_yml` / `yaml-rust2`) immediately in slice 0 (rejected).** Adds unreviewed external supply-chain surface, transitive crates and publish-cooldown delay on `priority:p0` `#1885` (`#645` critical path) and invites YAML 1.1 / anchor-alias complexity. A small pure-Rust YAML 1.2 fail-safe subset parser behind a private module accepts clean standard YAML 1.2 subset syntax for `tests/*.yaml`, rejects anchors/aliases/tags fail-closed, and can swap cleanly later without modifying any pack file.
5. **Require `@class` and one-positive-one-negative tests on `grdr.base`'s `permit` statements, or invent a non-spine `"built-in"` `Mode` for `grdr.base` (rejected).** Contradicts `#41` R1 ("`base.cedar` has one `permit ...` with `@id("base.<class>")`, and nothing else"), `#1885` req 1 (shipped Modes are `Off`, `Watch`, `Ask`, `Block`), and `#212` R1 (`Mode` closed 4-variant enum). Fixing `grdr.base` at `mode = "Block"`, permitting `@id`-only annotations on `Permit` inside `grdr.base`, and scoping the positive/negative test requirement to `forbid` rules satisfies all three without inventing new enum variants.
6. **Put `grdr_core::compile::pack` inside `grdr_core::policy` or depend directly on `grdr-strings/pack-text` (rejected).** Violates `ARCH-013` (`policy` cannot import `analyze`, whereas `lists/*` belongs to `analyze::vocab`) and violates `ARCH-001` / `ARCH-024` (layer-1 `grdr-core` cannot depend on layer-2 `grdr-strings`).

## Drawbacks
- **Strict YAML 1.2 subset limitations for `tests/*.yaml`:** Pack authors cannot use YAML anchors (`&`/`*`), aliases, multi-line block scalars (`|`/`>`) or YAML 1.1 bare `yes`/`no` booleans in `tests/*.yaml`. Quoted strings handle all command vectors cleanly, and standard YAML 1.2 tooling (`yq`, `PyYAML`) still reads every accepted file natively.
- **Per-member SHA-256 hashing on encode and decode:** `GRDB` v1 stores and verifies a SHA-256 digest per member plus the whole archive `VerifiedBundle::digest()`. On slice-0 KiB-to-low-MiB bundles (`<= 4 MiB`), verifying both catches partial member or frame corruption at load in negligible time, at the cost of a small constant linear pass.
- **Cross-issue dependency chain before `#1885` code compiles:** `#1885` code in `crates/grdr-model` and `crates/grdr-core` relies on `#278` (`BUNDLE`/`PACK` error registry), `#279` (`limits.toml` `bundle.*`/`pack.*` rows), `#435` (`v1alpha1` Cedar schema), `#739` / `#212` / `#213` shared domain types, and `#1575`'s `toml`/`serde` admission (`not_before = "2026-11-24T04:25:29Z"`).

## Unresolved questions
1. **Slice-1 `layers/*.settings` and bundle `manifest.toml` addition:** When slice-1 layer distribution (`#754`, `#71`) lands, should `layers/<layer>.settings` and top-level `manifest.toml` extend `GRDB` v1 behind `flags` bit `0x0001` or move to `GRDB` `format_version = 2` (`D-71` compat range)? Left to `#754` so slice-0 `GRDB` v1 stays minimal and closed.
2. **`session-rules.yaml` schema and YAML subset vs admitted YAML 1.2 parser:** When `#1894` activates `session-rules.yaml`, confirm whether `session-rules.yaml` uses the same bounded YAML 1.2 subset or admits a full YAML 1.2 crate once cooldown and supply-chain audits complete.
3. **`PackLocaleMessages` runtime MF2 compilation cache in `grdr-engine` (`#1537` / `#1894`):** Confirm on `#1894` whether `grdr-engine` parses `PackLocaleMessages` into `CompiledPackMessage` eagerly at `BundleLoad` or lazily per active `ui.locale` within `grdr-engine`'s 140 MB resident memory budget (`docs/design/11` section 3).

## Review
Review on `#1885` runs on this blob under `D-61`, `D-63`, `.claude/risk-tiers.toml` (`[kinds] rfc` plus `wire_or_pack_format_change` and `public_api_change`), and `ADR-0043`. Every reviewing comment on `#1885` opens with the three role lines required by [RFC 0001](./0001-adopt-the-spine.md):
- `RFC file: <blob of rfcs/0019-slice-0-policy-pack-directory-and-bundle-encoding.md at the commit reviewed>`
- `Proposed text: none`
- `Base: a80859235e7a2a4444648d6fa8d389d78dde6be9`
- `read=<path>@<blob>` for every other file it relied on

The decided file may differ from the reviewed blob only where [RFC 0001](./0001-adopt-the-spine.md) ("Review binds the decision") permits (`State:`, `Decision record:`, review link lines and `## Decision`).

This text rests on these git blobs at `origin/main` (`5a21f62`):
- `docs/design/00-decisions.md`: `a80859235e7a2a4444648d6fa8d389d78dde6be9` (SHA-256 `8f6ea876777c0121ecec068c0bc4cef45932be45c1c2aff4140712db1e06628d`)
- `docs/design/03-system-architecture-and-modularity.md`: `315027b541b6d9b4f278d58faed9e3ff8eaaf32e`
- `docs/design/04-event-model-and-schemas.md`: `e77880a12d2f42e715836a6da9598b86f33b20b0`
- `docs/design/11-endpoint-engineering.md`: `e1f14a5f0b7c4e3c3ded753865bf74a2c4a04b7b`
- `docs/design/12-policy-engine.md`: `b432904799251eca1d931378a6094ca6ea8b08db`
- `docs/design/13-detection-engine-and-content.md`: `3e10c55ef3e957396dd942c61ccdd62935e3aa07`
- `docs/design/22-transport-fleet-and-updates.md`: `ccf77d0280ae78cd1efa9491a20b48c7ebdecd27`
- `docs/design/28-desktop-and-developer-experience.md`: `428385fc76372e0ee0b1bcc1e3b8aa2a76bd0b21`
- `docs/design/30-open-source-governance-and-community.md`: `91f909de5f9ed9aaf6db0bbeb4641db16976adda`
- `docs/design/34-documentation-support-and-lifecycle.md`: `6565a02207601fbc59b83568cfd48e9d026432eb`
- `rfcs/0000-template.md`: `dde5fb92fe861182e00c93a0b70d2eac73df0bb3`
- `rfcs/0001-adopt-the-spine.md`: `353436cd2f9cff08037783ca66678c52cd7d6be4`
- `rfcs/0005-fastpath-rust-surface.md`: `4ad52380450ff611f274b4813a19a7f8e412eb7f`
- `rfcs/0007-grdr-model-and-grdr-schema-slice-0-surface.md`: `0c0a6745f04888bec8ef2e718352549f47181201`
- `rfcs/0009-grdr-model-slice-0-surface.md`: `4f36df6f0b2ce122d3b09d8109e83fb4720b1c68`
- `rfcs/0013-cedar-schema-grdr-policy-surface.md`: `cba59d501d07f7a6b366826fe20d26d71872ac08`
- `rfcs/0014-engine-boundary-c-abi.md`: `2519dae95887355b050965098d9c7c5fcac84ab1`
- `rfcs/0015-analyze-shell-surface.md`: `15bb343b63f6efb5fbea92fc864b64613a506702`
- `rfcs/0017-grdr-strings-language-token-runtime.md`: `3eca0104bcd3ce536aaa780ac77dfa28e4f74d1b`
- `rfcs/pins.toml`: `993f808476d52888e4a3673da9ad685e1ce55989`
- `Cargo.toml`: `3523225e39637bfe71665ec01e3398cc3379f448`
- `architecture.toml`: `2fae65054a0cd8dd3bc3906beeab658e2382e68f`
- `surfaces.toml`: `423a26a1c925708038b900e2fc4473d561c8def1`
- `security/trust-core.paths`: `54b7a0fcacd7276252c510f5525aa6f3d3cd37eb`
- `.claude/risk-tiers.toml`: `bdeae4e47033768f9ddb2166b5e75635f642cbf6`
- `deny.toml`: `91a4c447d101243d37b64f610f2dbe74d24bdd27`
- `supply-chain/licences.toml`: `65338a382a81c1ac500c533e22fa6ee22397928d`
- `supply-chain/admissions.toml`: `1b25c164ade9d313e80bd6286444e289062d7f1f`
- `spec/host-contract/tables.md`: `aff9a845fc212046311d9aa4581a5053809c9601`
- `crates/grdr-core/Cargo.toml`: `c7e158fbaabfecad2c2f111696a189ac381e75c5`
- `crates/grdr-core/src/lib.rs`: `694e63cb9ba79a61981fbf28ea6edd4e385ff74c`
- `crates/grdr-model/Cargo.toml`: `5675ea11d6ab6e61ba9da6807dc7ccb38c1b76b3`
- `crates/grdr-model/src/lib.rs`: `0757c655ac2114fc28145a86c59cb51979db7139`

## Decision
Not decided. Awaits review on `#1885` under `D-61` and [RFC 0001](./0001-adopt-the-spine.md).
