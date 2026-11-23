RFC: 0018
Title: Policy engine slice-0 public types in grdr-model, grdr-core and grdr-schema
Author: chief-architect
Harness: Antigravity
Model: Gemini 4 Neon
State: Review
Design issue: #739
Spine: D-05, D-07, D-08, D-09, D-10, D-11, D-13, D-15, D-16, D-25, D-31, D-44, D-53, D-60, D-61, D-63, D-69, P1, P2, P5, P7, P8, P9, P14, P17 (no spine text changes)
Surfaces: public crate `grdr-model` (layer 1: `Mode`, `RuleClass`, `ApproverKind`, `OnLoss`, `RuleStatus`, `ApprovalRoute`, `Liftability`, `PolicyLayer`, `PackId`, `PackVersion`, `InertText`, `TokenKey`, `PolicyMessageRef`, `AnnotationParseError`, `RuleMeta`, `RuleMetaLimits`, `RuleMetaLimitsError`, `RuleMetaError`, `RuleClassDefaults`, `RuleClassTable`, `RuleClassTableError`, `ModeRuleInput`, `ModeContext`, `CompiledSet`, `CompiledRuleMeta`, `ModeDiagnostic`, `ModeCompileError`, plus `Obligation::is_must` on RFC 0013's `Obligation`, amending RFC 0009); public crate `grdr-core` (layer 1, `experimental`: `analyze::{vocab, path_class, host_class, command_class}`, `policy::mode` exposing `cedar_policy::{Policy, PolicySet}` under `ARCH-007`, and `engine::{Input::ActionRequest, ActionRequest, ActionControlContext, ActionPayload, ExecActionRequest, EnvDeltaValue, TranslationOutcome, Decision, DeterminingRule, CacheScope, StepOutput.decision, LoadError::Policy}`, amending RFC 0013, RFC 0014 and RFC 0015); public crate `grdr-schema` (layer 0: `grdr_schema::cedar::EXEC_OPAQUE`, error code registrations in `MODEL`, `POLICY`, `ANALYZE` and `CORE`, and `[bound.policy.*]` limits rows, amending RFC 0007 and RFC 0013); tool crate `grdr-policy-ref` (`layer = "tool"`, reference `mode` transform sharing `grdr-model` metadata types). As proposals: `limits.toml` (`#741`), `schema/codes/{model,policy,analyze,core}.toml` (`#278`, `#1853`), `architecture.toml` (`ARCH-007` `Policy`/`PolicySet` tracking), `security/trust-core.paths` (`#2075`, `PC-1`), `surfaces.toml`, `docs/design/{03,12,13,34}`, and issue write-backs on `#739`, `#212`, `#213`, `#217`, `#218`, `#221`, `#222`, `#223`, `#1861`, `#741`, `#435`, `#1600`, `#1900`, `#1885`, `#1537` and `#1582`
Decision record: none yet

To comment, write on issue #739 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

## Summary

This RFC defines the slice-0 policy engine public types in [`grdr-model`](../crates/grdr-model/Cargo.toml), [`grdr-core`](../crates/grdr-core/Cargo.toml) and [`grdr-schema`](../crates/grdr-schema/Cargo.toml) under escalation `#739-E1` Option A, unblocking the first runnable path (`#645`) across `#212`, `#213`, `#217`, `#218`, `#221`, `#222`, `#223`, `#1861` and `#741`. It reuses the shared policy contract types and Cedar surface established by [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md) ([ADR-0053](../docs/decisions/ADR-0053-cedar-schema-grdr-policy-surface-adopted-by-rfc-0013.md)), extends the slice-0 `Engine` boundary of [RFC 0014](./0014-engine-boundary-c-abi.md) ([ADR-0054](../docs/decisions/ADR-0054-engine-boundary-c-abi-adopted-by-rfc-0014.md)) and the `analyze` surface of [RFC 0015](./0015-analyze-shell-surface.md) ([ADR-0049](../docs/decisions/ADR-0049-analyze-shell-surface-adopted-by-rfc-0015.md)), preserves strict layer boundaries (`ARCH-001`, `ARCH-013`, `ARCH-024`) with [RFC 0017](./0017-grdr-strings-language-token-runtime.md) ([ADR-0055](../docs/decisions/ADR-0055-grdr-strings-language-token-runtime-adopted-by-rfc-0017.md)), and leaves slice-1 grant and retry types (`#214`, `#215`, `#219`) out of scope for a subsequent RFC.

## Motivation

Work item `RFC-1` (`#739`) moved from slice 1 to slice 0 to unblock the first runnable end-to-end decision path in `#645` (`#212`, `#213`, `#217`, `#218`, `#221`, `#222`, `#223` and `#1861`). [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md) fixed the Cedar schema, request inputs, `derive` and `degrade` contract (`#431`), and [RFC 0014](./0014-engine-boundary-c-abi.md) fixed the minimal `Engine` skeleton (`#378`), leaving six concrete specification gaps that block implementation unless decided once:

1. **Shared `grdr-model` enums and Cedar annotation spelling differences ([RFC 0013](./0013-cedar-schema-grdr-policy-surface.md), `#212`, `#218`):** RFC 0013 placed `ApprovalGrade`, `Obligation`, `Transform`, `EnforcedMode` and `PolicyRuleId` in `grdr-model` using [RFC 0009](./0009-grdr-model-slice-0-surface.md) `wire_enum!`, whose `WireName` grammar requires lower-case words (`"g0".."g3"`, `"ask"`, `"block"`). Meanwhile, `docs/design/12` sections 3 and 5, `#212` R1/R14 and `#218` R4/R9 spell Cedar annotations in TitleCase (`@max_mode("Ask")`, `@mode("Block")`, `@min_grade("G1")`) and use Rust keywords (`@approver("self")`, `@final("true")`). Defining explicit `as_annotation` / `from_annotation` contracts alongside `wire_enum!` words keeps one canonical definition per enum (`P17`) without failing `WireName` validation or `AC-3` round-trips.
2. **Reference-model crate isolation (`D-63`, `#217` R10):** `grdr-policy-ref` (`#217`) cannot depend on `grdr-core` or `cedar-policy`, yet `#218` AC-2 compares every compiled rule metadata field and error against `grdr-policy-ref`. Hosting pure compiled metadata types (`ModeRuleInput`, `ModeContext`, `CompiledSet`, `CompiledRuleMeta`, `ModeDiagnostic`, `ModeCompileError`) in `grdr-model` allows differential equality with zero shared evaluator code.
3. **Layer-1 purity against `grdr-agents` and `grdr-strings` (`ARCH-001`, `ARCH-024`, `#1861` R2/R5):** `#1861` R2 references `#376` in Layer-3 `grdr-agents` (`TranslationOutcome`), and `#1861` R5 asks for `@steer` and `@message` as `MessageRef` values while referencing Layer-2 `grdr-strings` (`ADR-0055`). Layer-1 `grdr-core` cannot depend on Layer 2 or Layer 3 (`ARCH-001`) and formats no text (`renders = "none"`, `ARCH-024`). Defining Layer-1 `TranslationOutcome` and `PolicyMessageRef` preserves all layer edges while letting Layer-4 `grdr-engine` (`#1537`) convert cleanly at the boundary.
4. **Intracrate `ARCH-013` boundary and RFC 0015 / `#223` composition (`#213`, `#223`):** Under `ARCH-013`, `analyze` and `policy` inside `grdr-core` cannot import each other. [RFC 0015](./0015-analyze-shell-surface.md) returns `Resolution<CommandTree>` (without partial leaves on `Unresolved`), whereas `#223` accepts partial resolved leaves alongside `UnresolvedReason` values and imports `exec.opaque` from `grdr-schema`. Explicitly defining `EXEC_OPAQUE` in `grdr_schema::cedar`, keeping `ClassName` in `analyze::vocab` with a documented `ClassName` to `ClassTag` invariant, and adding `CommandInput` + `flatten_tree` resolves the seam cleanly.
5. **Non-UTF-8 entry testing across `#213` R4 and `#221` R2:** `#213` R4 describes `VocabularyList` entries as strings, yet `#221` R2 explicitly requires a non-UTF-8 path pattern to be a build error (`PatternNotUtf8`), and `#223` R1 operates on canonical byte-string `argv` tokens. Typed byte entries (`Vec<Vec<u8>>` with string convenience constructors) let `#213` check count and byte length generically while each engine enforces its own encoding rules.
6. **`limits.toml` naming compliance and `LoadError: Copy` preservation (`#741`, [RFC 0007](./0007-grdr-model-and-grdr-schema-slice-0-surface.md), [RFC 0014](./0014-engine-boundary-c-abi.md)):** `#741` stub keys (`*_bytes`, `*_ms`, `list_max_entries`) violate RFC 0007 section 6's ban on unit words in key names, and adding a non-`Copy` `PolicyError` directly into `LoadError::Policy` would break RFC 0014's `Copy` guarantee on `LoadError`. Replacing the key names with compliant `[bound.policy.*]` rows and typing `LoadError::Policy(&'static Code)` preserves compatibility across `#384`, `#388`, `#19` and `#1861`.

## Design

### 1. Scope, slice boundary and architectural invariants

#### 1.1 Slice-0 vs slice-1+ scope (`#739-E1` Option A)

| Component | In scope (RFC 0018, slice 0) | Out of scope (deferred to follow-up RFCs) |
|---|---|---|
| Rule metadata (`#212`) | `Mode`, `RuleClass`, `ApproverKind`, `OnLoss`, `RuleStatus`, `ApprovalRoute`, `Liftability`, `PolicyLayer`, `PackId`, `PackVersion`, `InertText`, `TokenKey`, `PolicyMessageRef`, `AnnotationParseError`, `RuleMeta`, `RuleMetaLimits`, `RuleMetaError`, `RuleClassDefaults`, `RuleClassTable`, `Obligation::is_must` | Grants and retry types: `CanonicalAction`, `ActionDigest`, `EncodeError` (`#214`), `RetryBinding`, `PendingApproval`, `TokenCheck` (`#215`), `Grant`, grant index and matching (`#219`) |
| Analyser vocabularies (`#213`) | `ListType`, `Polarity`, `ManagedBy`, `ClassName`, `VocabularyList`, `VocabularyLimits`, `VocabularyTable`, `VocabularyError` | Pack directory parsing (`#1885`, RFC 0019), layer list containment (`#71`), non-exec consumer list types (`env-protect`, `psl-suffix`, etc.) |
| Analyser engines (`#221` to `#223`) | `PathTemplate`, `PathContext`, `CanonicalPath`, `WorkspaceMembership`, `PathClasses`, `PathClassifier`, `CanonicalHost`, `HostClasses`, `HostClassifier`, `CommandLeaf`, `CommandInput`, `flatten_tree`, `CommandClasses`, `UnresolvedCommandClasses`, `CommandOutcome`, `CommandClassifier`, `grdr_schema::cedar::EXEC_OPAQUE` | Shell canonicaliser internals (`#423`), URL parser and UTS 46 (`URL-1`), PowerShell and `cmd` canonicalisers (`#894`), `grdr-fastpath` compiler (`#414`), MCP and cloud analysers |
| Mode transform (`#217`, `#218`) | `ModeRuleInput`, `ModeContext`, `CompiledSet`, `CompiledRuleMeta`, `ModeDiagnostic`, `ModeCompileError`, `ModeSourceRule`, `CompiledRule`, `CompiledSets`, `ModeError`, `compile_rule`, `compile_sets` | Rule read sets and floor eligibility (`#216`, `#71`), fail-safe tables (`#71`), `policy::decide` (`#1900`), `compile_down` native fragments |
| Engine decide inputs/outputs (`#1861`) | `Input::ActionRequest(&ActionRequest)`, `ActionRequest`, `ActionControlContext`, `ActionPayload::Exec(ExecActionRequest)`, `EnvDeltaValue`, `TranslationOutcome`, `Decision`, `DeterminingRule`, `CacheScope`, `StepOutput.decision`, `LoadError::Policy(&'static Code)` | Other 14 action payloads (`#1602`), verdict caching (E1.5), `grdr.embed.v1alpha1` protobuf messages (`#381`), detection findings (`#171`) |
| Schema, codes and limits (`#741`, `#278`) | Slice-0 `[bound.policy.*]` key names and bounds, `MODEL` / `POLICY` / `ANALYZE` / `CORE` error reasons, `EXEC_OPAQUE` | Slice-1 `[bound.policy.*]` runtime activation (`retry-token-ttl`, `route-timer-default`, `approval-streak-max`, `grants-index-max`) if split in `#741` |

#### 1.2 Alignment with [ADR-0053](../docs/decisions/ADR-0053-cedar-schema-grdr-policy-surface-adopted-by-rfc-0013.md) section 12.1

In accordance with [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md) (`ADR-0053`), every shared domain enum and rule identifier defined there is reused verbatim rather than duplicated (`P17`):
- `grdr_model::{ActionClass, ControlPoint, Verdict, ExecutedVerb, DerivationRow, ModifyBudget, EnforcedMode, ApprovalGrade, Obligation, Transform, NormaliserOutcome, ControlPointCoverage, DecisionReason, PendingWindow, PolicyRuleId, PolicyRuleIdError, ControlPointCaps}` remain single-sourced from RFC 0013.
- Future slice-1 work covering `#214`, `#215` and `#219` (`CanonicalAction`, retry bindings, grants) must likewise consume `ActionClass`, `ApprovalGrade`, `ApproverKind`, `Obligation`, `EnforcedMode` and `PolicyRuleId` from `grdr-model` in its own amending RFC (`#739-E1` Option A).

#### 1.3 Layer and safety invariants

1. **`ARCH-001` and `wasm32-unknown-unknown`:** `grdr-model` and `grdr-core` stay Layer 1 (`privilege = "none"`, `renders = "none"`), perform zero I/O, read no ambient clock or entropy (`ARCH-003`), prohibit `unsafe` (`#![forbid(unsafe_code)]`), prohibit panics or unchecked arithmetic (`#![deny(clippy::arithmetic_side_effects)]`), and compile cleanly for `wasm32-unknown-unknown`. Neither crate depends on Layer-2 `grdr-strings` or Layer-3 `grdr-agents`.
2. **`ARCH-013` intracrate isolation:** Inside `grdr-core`, modules `analyze` and `policy` import only `grdr-schema` and `grdr-model` (plus `cedar-policy` inside `policy`, and `cedar::EXEC_OPAQUE` inside `analyze::command_class`), and never import each other. `engine` and `compile` import `analyze` and `policy` per `architecture.toml`.
3. **`ARCH-007` Cedar exposure (`experimental`):** While `grdr-core` stays `class = "experimental"` in [`surfaces.toml`](../surfaces.toml), `grdr_core::policy::mode` joins `policy::{schema, request}` in exposing `cedar-policy` types (`cedar_policy::{Policy, PolicySet}`). Before `grdr-core` promotes to `beta` or `stable` (`D-60`), `Policy` and `PolicySet` must be wrapped behind opaque Guardrails types.
4. **`P8` and `LogSafe`:** Only structural identifiers, error codes (`LogValue::Code`) and `WireName` variants (`LogValue::Enum`) implement `LogSafe`. `CanonicalPath`, `PathContext`, `CanonicalHost`, `CommandLeaf`, `ActionRequest`, `ExecActionRequest`, `RuleMeta`, `PolicyMessageRef` and `InertText` never implement `LogSafe` (`RFC 0009` section 7), and types holding `identifier` or `content` data implement manual redacting `fmt::Debug` printing byte lengths, boolean flags or field summaries only.

---

### 2. Typed rule metadata and `RuleClassTable` in `grdr-model` (`#212`, amending [RFC 0009](./0009-grdr-model-slice-0-surface.md))

Under RFC 0009 section 13 (`ADR-0041`), all types below live in private submodules (`crates/grdr-model/src/policy/*.rs` per `#212`) and are publicly re-exported once at `grdr-model`'s crate root (RFC 0009 R3), and re-exported publicly by `grdr_core::policy` (RFC 0013 R4). Because RFC 0009 requires `renders = "none"` on `grdr-model`, none of these types implements `fmt::Display`; enum printing and parsing occur through `as_str()`, `as_annotation()` and `from_annotation()`.

#### 2.1 Closed metadata enums and annotation spelling contract

Every enum below except `RuleStatus` (`NotDraft` has no annotation spelling) and compound enum `Liftability` is declared via `wire_enum!` (providing `VARIANTS`, `as_str`, `wire_name` and `LogSafe` via `LogValue::Enum`). Types reused from RFC 0013 (`ApprovalGrade`, `Obligation`, `Transform`, `EnforcedMode`) keep their lower-case `WireName` words and gain explicit annotation helpers matching `#212` R1/R2/R14.

```rust
// Reused verbatim from RFC 0013 in `grdr-model`:
//   ApprovalGrade { G0 => "g0", G1 => "g1", G2 => "g2", G3 => "g3" }  (PartialOrd, Ord)
//   Obligation    { Receipt, Expect, Snapshot, PinRecorder, NotifyUser, NotifySponsor }
//   Transform     { RedactSecrets, WrapLauncher, SwapCredential }
//   EnforcedMode  { Ask => "ask", Block => "block" }

impl Obligation {
    pub const fn is_must(self) -> bool; // true for Obligation::Snapshot only (#212 R2)
    pub const fn as_annotation(self) -> &'static str; // identical to as_str(self)
    pub fn from_annotation(text: &str) -> Result<Self, AnnotationParseError>;
}

impl Transform {
    pub const fn as_annotation(self) -> &'static str; // identical to as_str(self)
    pub fn from_annotation(text: &str) -> Result<Self, AnnotationParseError>;
}

impl ApprovalGrade {
    pub const fn as_annotation(self) -> &'static str; // "G0" | "G1" | "G2" | "G3"
    pub fn from_annotation(text: &str) -> Result<Self, AnnotationParseError>; // exact TitleCase/upper-G only
}

wire_enum! {
    #[derive(PartialOrd, Ord)]
    pub enum Mode {
        Off => "off",
        Watch => "watch",
        Ask => "ask",
        Block => "block",
    }
}

impl Mode {
    pub const fn as_annotation(self) -> &'static str; // "Off" | "Watch" | "Ask" | "Block"
    pub fn from_annotation(text: &str) -> Result<Self, AnnotationParseError>; // exact TitleCase only
    pub const fn enforced(self) -> Option<EnforcedMode>; // Ask | Block -> Some(..), else None
}

impl From<EnforcedMode> for Mode { /* Ask -> Ask, Block -> Block */ }

wire_enum! {
    pub enum RuleClass {
        Routine => "routine",
        OutOfBoundary => "out-of-boundary",
        Secret => "secret",
        Elevate => "elevate",
        Irreversible => "irreversible",
        ConfigTamper => "config-tamper",
    }
}

impl RuleClass {
    pub const fn as_annotation(self) -> &'static str; // identical to as_str(self)
    pub fn from_annotation(text: &str) -> Result<Self, AnnotationParseError>;
}

wire_enum! {
    #[derive(PartialOrd, Ord)]
    pub enum ApproverKind {
        SelfApprover => "self",
        Sponsor => "sponsor",
        Admin => "admin",
        Quorum => "quorum",
    }
}

impl ApproverKind {
    pub const fn as_annotation(self) -> &'static str; // identical to as_str(self)
    pub fn from_annotation(text: &str) -> Result<Self, AnnotationParseError>;
}

wire_enum! {
    #[derive(PartialOrd, Ord)]
    pub enum OnLoss {
        Allow => "allow",
        Block => "block",
    }
}

impl OnLoss {
    pub const fn as_annotation(self) -> &'static str; // identical to as_str(self)
    pub fn from_annotation(text: &str) -> Result<Self, AnnotationParseError>;
}

wire_enum! {
    pub enum RuleStatus {
        Draft => "draft",
        NotDraft => "not-draft",
    }
}

impl RuleStatus {
    pub const fn as_annotation(self) -> Option<&'static str>; // Some("draft") | None
    pub fn from_annotation(text: &str) -> Result<Self, AnnotationParseError>; // "draft" -> Ok(Draft), else Err
}

wire_enum! {
    #[derive(PartialOrd, Ord)]
    pub enum ApprovalRoute {
        TimeLock => "time-lock",
        Authenticator => "authenticator",
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Liftability {
    None,
    Exception,
    Approval(ApprovalRoute),
}

wire_enum! {
    #[derive(PartialOrd, Ord)]
    pub enum PolicyLayer {
        Provider => "provider",
        Operator => "operator",
        Org => "org",
        Group => "group",
        Local => "local",
        User => "user",
    }
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum AnnotationParseError {
    UnknownSpelling,
}
// Implements Coded (GRDR-MODEL-0013) and LogSafe (LogValue::Code); no Display or Error (RFC 0009 R6).
```

Rules for section 2.1:
1. **Enum ordering:** Rust derives `PartialOrd, Ord` matching variant order: `Mode::Off < Watch < Ask < Block`; `ApproverKind::SelfApprover < Sponsor < Admin < Quorum`; `ApprovalGrade::G0 < G1 < G2 < G3`; `OnLoss::Allow < Block`; `PolicyLayer::Provider < Operator < Org < Group < Local < User`; `Liftability::None < Liftability::Exception < Liftability::Approval(ApprovalRoute::TimeLock) < Liftability::Approval(ApprovalRoute::Authenticator)` (`#212` R1, `#217` AC-4).
2. **`SelfApprover` spelling:** Because `self` is a Rust keyword, the enum variant is `ApproverKind::SelfApprover` while `as_str()`, `as_annotation()` and `from_annotation()` accept and emit `"self"`.
3. **`RuleStatus` asymmetry:** `@status("draft")` parses to `RuleStatus::Draft`; omitting `@status` yields `RuleStatus::NotDraft`. Passing `"not-draft"` in `@status` fails parsing (`#212` R1, AC-2).
4. **No `std::str::FromStr` confusion with `WireName`:** `from_annotation` parses only exact Cedar annotation spellings (`"Ask"`, `"G1"`), rejecting `"ask"` or `"g1"` (`#212` R11).

#### 2.2 Validated identifiers, inert text, `PolicyMessageRef`, `RuleMeta` and `RuleClassTable`

```rust
/// Validated pack identifier (`[a-z][a-z0-9.-]*`, rejecting `..`, leading/trailing `.` or `-`,
/// no `/` or `@`, up to `POLICY_RULE_ID_MAX` bytes).
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PackId(/* private String */);
impl PackId {
    pub fn parse(text: &str) -> Result<Self, PolicyRuleIdError>;
    pub fn as_str(&self) -> &str;
}

/// Validated semantic version (`<major>.<minor>.<patch>` plus optional safe pre-release `[a-z0-9.-]+`,
/// no whitespace, `/`, `@`, or `..`, up to `POLICY_RULE_ID_MAX` bytes).
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PackVersion(/* private String */);
impl PackVersion {
    pub fn parse(text: &str) -> Result<Self, PolicyRuleIdError>;
    pub fn as_str(&self) -> &str;
}

/// Validated inert annotation text (`@message`, `@steer`, `@intent`): byte length <= limits.annotation_max,
/// zero `char::is_control`, zero bidi overrides (`U+202A..=202E`, `U+2066..=2069`, `U+200E..=200F`, `U+061C`),
/// and neither `://` nor `www.` (ASCII case-insensitive). Never implements `LogSafe`.
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct InertText(/* private String */);
impl InertText {
    pub fn as_str(&self) -> &str;
}
// Manual fmt::Debug: prints byte length summary (`InertText(<len> bytes)`), never leaking text.

/// Validated Layer-1 message token key (`[a-z][a-z0-9_.-]*`, no `..`, up to `POLICY_RULE_ID_MAX` bytes).
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct TokenKey(/* private String */);
impl TokenKey {
    pub fn parse(text: &str) -> Result<Self, PolicyRuleIdError>;
    pub fn as_str(&self) -> &str;
}

/// Layer-1 unrendered policy notice reference carried on `Decision` (`ARCH-001`, `ARCH-024`, P7, P8).
/// Layer-4 callers (`grdr-engine`) resolve `token_id` and `source` into `grdr_strings::MessageRef`
/// or `CompiledPackMessage` without adding a Layer-1 -> Layer-2 dependency.
#[derive(Clone, PartialEq, Eq)]
pub struct PolicyMessageRef {
    pub token_id: TokenKey,
    pub source: Option<InertText>,
    pub source_hash: Option<[u8; 32]>,
}
// Manual fmt::Debug: prints `token_id`, `has_source` and `has_hash` only.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct RuleMetaLimits {
    /* private: rule_id_max: Bytes, annotation_max: Bytes */
}

impl RuleMetaLimits {
    pub const fn from_schema() -> Self;
    pub fn new(rule_id_max: Bytes, annotation_max: Bytes) -> Result<Self, RuleMetaLimitsError>;
    pub const fn rule_id_max(self) -> Bytes;
    pub const fn annotation_max(self) -> Bytes;
}
// Does NOT implement `Default` (#212 Failure modes: zero optional bounds).

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum RuleMetaLimitsError {
    ZeroLimit { field: &'static str },
    ExceedsSchemaMax { field: &'static str },
}
// Implements Coded + LogSafe (LogValue::Code); no Display or Error (RFC 0009 R6).

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RuleMeta {
    pub id: PolicyRuleId,
    pub class: RuleClass,
    pub max_mode: Mode,
    pub approver: ApproverKind,
    pub min_grade: Option<ApprovalGrade>,
    pub on_loss: Option<OnLoss>,
    pub is_final: bool,
    pub message: Option<InertText>,
    pub steer: Option<InertText>,
    pub remedy: Option<Transform>,
    pub obligations: BTreeSet<Obligation>,
    pub intent: Option<InertText>,
    pub status: RuleStatus,
}

impl RuleMeta {
    pub fn from_annotations(
        prefixes: &[&str],
        annotations: &[(&str, &str)],
        limits: RuleMetaLimits,
    ) -> Result<Self, RuleMetaError>;
}

#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RuleMetaError {
    MissingRequired { key: &'static str, rule_id: Option<String> },
    UnknownKey { key: String, rule_id: Option<String> },
    DuplicateKey { key: &'static str, rule_id: Option<String> },
    InvalidClass { rule_id: Option<String> },
    InvalidMaxMode { rule_id: Option<String> },
    InvalidApprover { rule_id: Option<String> },
    InvalidMinGrade { rule_id: Option<String> },
    InvalidOnLoss { rule_id: Option<String> },
    InvalidFinal { rule_id: Option<String> },
    InvalidRemedy { rule_id: Option<String> },
    InvalidObligation { rule_id: Option<String> },
    DuplicateObligation { rule_id: Option<String> },
    InvalidStatus { rule_id: Option<String> },
    RuleIdInvalid { rule_id: Option<String> },
    RuleIdPrefixMismatch { rule_id: String },
    RuleIdOverLimit { rule_id: Option<String> },
    AnnotationOverLimit { key: &'static str, rule_id: Option<String> },
    AnnotationControlChar { key: &'static str, rule_id: Option<String> },
    AnnotationDisallowedUrl { key: &'static str, rule_id: Option<String> },
}

impl RuleMetaError {
    pub fn rule_id(&self) -> Option<&str>;
    pub fn key(&self) -> Option<&str>;
}
// Implements Coded (1:1 to schema/codes/policy.toml) + LogSafe (LogValue::Code); no Display or Error.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct RuleClassDefaults {
    pub min_grade: ApprovalGrade,
    pub on_loss: OnLoss,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RuleClassTable {
    /* private: one RuleClassDefaults field per RuleClass variant (zero fallback in non-test code) */
}

impl RuleClassTable {
    pub const fn new(
        routine: RuleClassDefaults,
        out_of_boundary: RuleClassDefaults,
        secret: RuleClassDefaults,
        elevate: RuleClassDefaults,
        irreversible: RuleClassDefaults,
        config_tamper: RuleClassDefaults,
    ) -> Self;
    pub fn try_from_entries(
        entries: &[(RuleClass, RuleClassDefaults)],
    ) -> Result<Self, RuleClassTableError>;
    pub const fn get(self, class: RuleClass) -> RuleClassDefaults;
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum RuleClassTableError {
    MissingClass { class: RuleClass },
    DuplicateClass { class: RuleClass },
}
// Implements Coded + LogSafe (LogValue::Code); no Display or Error.
```

Rules for section 2.2:
1. **`RuleMeta::from_annotations` grammar (`#212` R4 to R12):**
   - Accepted keys: `"id"`, `"class"`, `"max_mode"`, `"approver"`, `"min_grade"`, `"on_loss"`, `"final"`, `"message"`, `"steer"`, `"remedy"`, `"obligation"`, `"intent"`, `"status"`. Unknown keys (including `"mode"`, which only the compiler emits) return `RuleMetaError::UnknownKey`, and duplicate keys return `RuleMetaError::DuplicateKey`.
   - Required keys: `"id"` and `"class"`. Missing either returns `RuleMetaError::MissingRequired`. Note `rule_id` on every error is populated whenever `"id"` is present in `annotations` and valid ASCII length-bounded text, or `None` when `"id"` is missing or over limit.
   - `id`: must start with `<prefix>.` for at least one valid prefix in `prefixes` (and reject empty `prefixes` or prefixes outside `[a-z][a-z0-9.-]*`), contain only `[a-z0-9.-]`, contain no `..`, not end in `.`, and satisfy `id.len() <= min(limits.rule_id_max.get(), POLICY_RULE_ID_MAX.get())`.
   - Defaults when omitted: `max_mode = Mode::Block`, `approver = ApproverKind::SelfApprover`, `min_grade = None`, `on_loss = None`, `is_final = false`, `obligations` empty `BTreeSet`, `status = RuleStatus::NotDraft`.
   - `final`: accepts `"true"` only (`#212` R8); `"false"` or `"yes"` returns `InvalidFinal`.
   - `remedy`: accepts `"modify:<transform>"` with `<transform>` parsed by `Transform::from_annotation` only; anything else returns `InvalidRemedy`.
   - `obligation`: comma-separated non-empty items trimmed of zero implicit whitespace (`#212` R10: exact spellings separated by `,`), rejecting empty segments (`InvalidObligation`) or repeated variants (`DuplicateObligation`).
   - `RuleMetaLimits::new` checks `1 <= rule_id_max <= grdr_schema::limits::rows::POLICY_RULE_ID_MAX.max()` (`512`, with constructed `PolicyRuleId`s additionally bounded by `POLICY_RULE_ID_MAX`) and `1 <= annotation_max <= grdr_schema::limits::rows::POLICY_ANNOTATION_MAX.max()` (`4096`), returning `ZeroLimit` on `0` or `ExceedsSchemaMax` above the schema ceiling while permitting tests to inject smaller limits.
2. **`RuleClassTable` (`#212` R13):** Contains no default table constants in non-test code (`P14`). `docs/design/12` section 3's table lives solely in test fixtures and signed pack/configuration bundles.
3. **Granular coded errors (`#212` AC-2):** Each rejection in `#212` AC-2 maps to its own variant and dedicated `GRDR-POLICY-*` code in section 7.

---

### 3. Analyser vocabulary tables in `grdr_core::analyze` (`#213`)

Public types sit in `crates/grdr-core/src/analyze/vocab.rs` and are publicly re-exported at `grdr_core::analyze` (`pub mod vocab; pub use vocab::{...};`).

```rust
wire_enum! {
    #[derive(PartialOrd, Ord)]
    pub enum ListType {
        Path => "path",
        Host => "host",
        Command => "command",
        ArgvToken => "argv-token",
        McpArgument => "mcp-argument",
        CloudAccount => "cloud-account",
        Tenant => "tenant",
        PackageKey => "package-key",
        ArtefactKey => "artefact-key",
    }
}

wire_enum! {
    #[derive(PartialOrd, Ord)]
    pub enum Polarity {
        Protect => "protect",
        Allow => "allow",
    }
}

wire_enum! {
    #[derive(PartialOrd, Ord)]
    pub enum ManagedBy {
        Pack => "pack",
        Feed => "feed",
    }
}

/// Validated class or literal-fact name: `[a-z][a-z0-9.-]*`, no `..`, byte length <= `POLICY_CLASS_NAME_MAX`
/// (and <= `limits.class_name_max` when built via `VocabularyLimits`).
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ClassName(/* private String */);

impl ClassName {
    pub fn parse(text: &str, limits: VocabularyLimits) -> Result<Self, VocabularyError>;
    pub fn parse_schema(text: &str) -> Result<Self, VocabularyError>; // uses POLICY_CLASS_NAME_MAX
    pub fn as_str(&self) -> &str;
}

#[derive(Clone, PartialEq, Eq)]
pub struct VocabularyList {
    pub list_type: ListType,
    pub class: ClassName,
    pub polarity: Polarity,
    pub managed_by: ManagedBy,
    pub entries: Vec<Vec<u8>>,
}

impl VocabularyList {
    pub fn from_strs(
        list_type: ListType,
        class: ClassName,
        polarity: Polarity,
        managed_by: ManagedBy,
        entries: &[&str],
    ) -> Self;
}
// Manual fmt::Debug: prints `list_type`, `class`, `polarity`, `managed_by` and `entry_count` only.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct VocabularyLimits {
    /* private: class_name_max: Bytes, list_entries_max: Count,
       list_entry_max: Bytes, vocabulary_entries_max: Count */
}

impl VocabularyLimits {
    pub const fn from_schema() -> Self;
    pub fn new(
        class_name_max: Bytes,
        list_entries_max: Count,
        list_entry_max: Bytes,
        vocabulary_entries_max: Count,
    ) -> Result<Self, VocabularyError>;
    pub const fn class_name_max(self) -> Bytes;
    pub const fn list_entries_max(self) -> Count;
    pub const fn list_entry_max(self) -> Bytes;
    pub const fn vocabulary_entries_max(self) -> Count;
}

#[derive(Clone, PartialEq, Eq)]
pub struct VocabularyTable {
    /* private: sorted BTreeMap<(ListType, ClassName), VocabularyList> + limits */
}

impl VocabularyTable {
    pub fn build(lists: Vec<VocabularyList>, limits: VocabularyLimits) -> Result<Self, VocabularyError>;
    pub fn polarity_of(&self, class: &ClassName) -> Option<Polarity>;
    pub fn lists_of(&self, list_type: ListType) -> impl Iterator<Item = &VocabularyList>;
    pub fn iter(&self) -> impl Iterator<Item = &VocabularyList>;
    pub fn literal_token_facts(&self) -> BTreeSet<ClassName>;
    pub fn with_feed_entries(
        &self,
        list_type: ListType,
        class: &ClassName,
        entries: Vec<Vec<u8>>,
    ) -> Result<Self, VocabularyError>;
}
// Manual fmt::Debug: prints list count and limits only (`P8`).

#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum VocabularyError {
    ZeroLimit { field: &'static str },
    InvalidClassName,
    ClassNameOverLimit { limit: u64, actual: usize },
    DuplicateList { list_type: ListType, class: ClassName },
    PolarityConflict { class: ClassName },
    FeedListNotProtect { list_type: ListType, class: ClassName },
    FeedListType { list_type: ListType, class: ClassName },
    ListEntriesOverLimit { list_type: ListType, class: ClassName, limit: u64, actual: usize },
    ListEntryOverLimit { list_type: ListType, class: ClassName, limit: u64, actual: usize },
    VocabularyEntriesOverLimit { limit: u64, actual: usize },
    NotFeedManaged { list_type: ListType, class: ClassName },
    UnknownList { list_type: ListType, class: ClassName },
}
// Implements Display, Error, Coded (1:1 to schema/codes/analyze.toml) and LogSafe (LogValue::Code).
```

Rules for section 3:
1. **`ClassName` to `ClassTag` invariant (`ARCH-013`):** `limits.toml` enforces `POLICY_CLASS_NAME_MAX.get() <= POLICY_CLASS_TAG_MAX.get()` (both `128` bytes in section 7). Every `ClassName` (`[a-z][a-z0-9.-]*`) is therefore a strict subset of [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md)'s `ClassTag` grammar, allowing `grdr_core::engine` and `grdr_core::compile` to map `ClassName::as_str()` into `ClassTag::parse` infallibly at runtime without `analyze` importing `policy`.
2. **Feed-managed invariant (`#213` R7, R11):** A `ManagedBy::Feed` list requires `Polarity::Protect` and `ListType::{Host, PackageKey, ArtefactKey}`. `with_feed_entries` returns a new validated `VocabularyTable` checked against the stored `VocabularyLimits` (list entry count, entry byte length and total vocabulary entries) and leaves `&self` untouched on any error.
3. **Deterministic order (`#213` R10):** Lists are stored sorted by `(ListType, ClassName)` (`BTreeMap`), and `literal_token_facts()` returns the sorted `BTreeSet<ClassName>` of every `ListType::ArgvToken` list. Entries inside a single `VocabularyList` preserve deterministic comparison/canonical order when built.

---

### 4. Path, host and command classifiers and `grdr_schema::cedar::EXEC_OPAQUE` (`#221`, `#222`, `#223`)

#### 4.1 `grdr_schema::cedar::EXEC_OPAQUE` (`#223` R12, amending [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md) section 3)

In `crates/grdr-schema/src/cedar.rs`, add one exported constant beside `SCHEMA_VERSION` and `V1ALPHA1`:

```rust
pub const EXEC_OPAQUE: &str = "exec.opaque";
```

`command_class` (`crates/grdr-core/src/analyze/command_class*`) imports `grdr_schema::cedar::EXEC_OPAQUE` and never spells `"exec.opaque"` as a string literal (`#223` R12, AC-6). `ClassName::parse_schema(EXEC_OPAQUE)` is asserted in tests (`11` bytes, valid `ClassName`). Because `crates/grdr-schema/src/cedar.rs` tracks `security/trust-core.paths` via `#2075`, this addition lands through `#435` (or a small follow-up ahead of `#223`).

#### 4.2 `grdr_core::analyze::path_class` (`#221`)

```rust
wire_enum! {
    #[derive(PartialOrd, Ord)]
    pub enum PathTemplate {
        Home => "home",
        Workspace => "workspace",
        Tmp => "tmp",
        SessionTmp => "session-tmp",
        AppData => "app-data",
        LocalAppData => "local-app-data",
    }
}

impl PathTemplate {
    pub const fn token(self) -> &'static str; // "$HOME", "$WORKSPACE", "$TMP", "$SESSION_TMP", "$APPDATA", "$LOCALAPPDATA"
    pub fn from_token(token: &str) -> Option<Self>;
}

#[derive(Clone, PartialEq, Eq)]
pub struct PathContext {
    pub home: Option<CanonicalPath>,
    pub workspace: Option<CanonicalPath>,
    pub tmp: Option<CanonicalPath>,
    pub session_tmp: Option<CanonicalPath>,
    pub app_data: Option<CanonicalPath>,
    pub local_app_data: Option<CanonicalPath>,
}

impl PathContext {
    pub const fn empty() -> Self;
    pub fn get(&self, template: PathTemplate) -> Option<&CanonicalPath>;
}
// Manual fmt::Debug: prints per-template presence booleans only, never path bytes (`P8`).

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct CanonicalPath { /* private path: String, case_folded: bool */ }

impl CanonicalPath {
    pub fn new(raw: &[u8], case_folded: bool) -> Result<Self, PathInputError>; // uses PathClassLimits::from_schema()
    pub fn new_with_limits(
        raw: &[u8],
        case_folded: bool,
        limits: PathClassLimits,
    ) -> Result<Self, PathInputError>;
    pub fn as_str(&self) -> &str;
    pub const fn is_case_folded(&self) -> bool;
}
// Manual fmt::Debug: prints byte length and `case_folded` only (`P8`).

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum WorkspaceMembership {
    Inside,
    Outside,
    Undecided,
}

impl WorkspaceMembership {
    pub const fn is_inside(self) -> bool;    // true only for Inside
    pub const fn is_undecided(self) -> bool; // true only for Undecided
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PathClasses {
    pub classes: BTreeSet<ClassName>,
    pub in_workspace: WorkspaceMembership,
    pub undecided: BTreeSet<ClassName>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct PathClassLimits {
    /* private: pattern_max: Bytes, path_max: Bytes */
}

impl PathClassLimits {
    pub const fn from_schema() -> Self;
    pub fn new(pattern_max: Bytes, path_max: Bytes) -> Result<Self, PathClassError>;
    pub const fn pattern_max(self) -> Bytes;
    pub const fn path_max(self) -> Bytes;
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct PathClassifyStats {
    pub max_entry_steps: u64,
    pub total_steps: u64,
}

#[derive(Clone, PartialEq, Eq)]
pub struct PathClassifier { /* private compiled patterns + optional workspace root */ }
// Manual fmt::Debug: prints compiled class/pattern count and workspace-root presence only (`P8`).

impl PathClassifier {
    pub fn build(table: &VocabularyTable, context: &PathContext) -> Result<Self, PathClassError>;
    pub fn build_with_limits(
        table: &VocabularyTable,
        context: &PathContext,
        limits: PathClassLimits,
    ) -> Result<Self, PathClassError>;
    pub fn classify(&self, path: &CanonicalPath) -> PathClasses;
    pub fn classify_with_stats(&self, path: &CanonicalPath) -> (PathClasses, PathClassifyStats);
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum PathInputError {
    NotCanonical,
}
// Implements Display, Error, Coded (GRDR-ANALYZE-*) and LogSafe (LogValue::Code).

#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PathClassError {
    ZeroLimit { field: &'static str },
    PatternNotUtf8 { class: ClassName },
    PatternOverLimit { class: ClassName, limit: u64, actual: usize },
    PatternInvalidStart { class: ClassName },
    DoubleStarWithBytes { class: ClassName },
    UnknownTemplate { class: ClassName },
    TemplateNotFirstSegment { class: ClassName },
    EmptySegment { class: ClassName },
    DotSegment { class: ClassName },
    DanglingEscape { class: ClassName },
}
// Implements Display, Error, Coded (1:1 to schema/codes/analyze.toml) and LogSafe (LogValue::Code).
```

Rules for section 4.2:
1. **Root `/` vs trailing `/`:** `CanonicalPath` accepts `/` (root, zero non-root segments). Any path longer than 1 byte must start with `/`, must not end with `/`, must contain zero empty (`//`), `.` or `..` segments, must be valid UTF-8, and must be at most `limits.path_max` bytes.
2. **Unicode scalar value character unit (`spec/host-contract/tables.md`):** Wildcards `*` and `?` and matcher step bounds `(path_chars + 1) * (pattern_chars + 1)` count Rust `char` (Unicode scalar values), using checked/saturating DP matching with zero exponential backtracking.

#### 4.3 `grdr_core::analyze::host_class` (`#222`)

```rust
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct CanonicalHost { /* private repr: CanonicalHostKind */ }

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum HostKind<'a> {
    Name(&'a str),
    Ipv4(core::net::Ipv4Addr),
    Ipv6(core::net::Ipv6Addr),
}
// Manual fmt::Debug: prints variant tag and `name_len` or IP family only (`P8`).

impl CanonicalHost {
    pub fn parse(bytes: &[u8]) -> Result<Self, HostInputError>;
    pub fn kind(&self) -> HostKind<'_>;
    pub fn name(&self) -> Option<&str>;
    pub fn ipv4(&self) -> Option<core::net::Ipv4Addr>;
    pub fn ipv6(&self) -> Option<core::net::Ipv6Addr>;
}
// Manual fmt::Debug: prints variant tag + name_len or address-family only, never host text/IP (`P8`).

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HostClasses {
    pub classes: BTreeSet<ClassName>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct HostClassLimits {
    /* private: entry_max: Bytes */
}

impl HostClassLimits {
    pub const fn from_schema() -> Self;
    pub fn new(entry_max: Bytes) -> Result<Self, HostClassError>;
    pub const fn entry_max(self) -> Bytes;
}

#[derive(Clone, PartialEq, Eq)]
pub struct HostClassifier { /* private canonical exact/wildcard/CIDR rules */ }
// Manual fmt::Debug: prints compiled class/entry count only (`P8`).

impl HostClassifier {
    pub fn build(table: &VocabularyTable) -> Result<Self, HostClassError>;
    pub fn build_with_limits(
        table: &VocabularyTable,
        limits: HostClassLimits,
    ) -> Result<Self, HostClassError>;
    pub fn classify(&self, host: &CanonicalHost) -> HostClasses;
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum HostInputError {
    NonAscii,
    InvalidHost,
}
// Implements Display, Error, Coded and LogSafe (LogValue::Code).

#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum HostClassError {
    ZeroLimit { field: &'static str },
    EntryOverLimit { class: ClassName, limit: u64, actual: usize },
    EmptyEntry { class: ClassName },
    InvalidEntrySyntax { class: ClassName },
    InvalidCidrPrefix { class: ClassName },
    NonZeroHostBits { class: ClassName },
}
// Implements Display, Error, Coded (1:1 to schema/codes/analyze.toml) and LogSafe (LogValue::Code).
```

Rules for section 4.3: `CanonicalHost::parse` strips brackets (`[...]`), resolves WHATWG decimal/octal/hex IPv4 forms (`2130706433`, `0x7f.1`, `127.1`), converts IPv4-mapped `::ffff:0:0/96` and NAT64 `64:ff9b::/96` (RFC 6052) addresses directly to `HostKind::Ipv4`, lower-cases ASCII DNS labels and strips at most one trailing `.`, rejecting zone indexes, ports, empty labels and non-ASCII bytes (`NonAscii`).

#### 4.4 `grdr_core::analyze::command_class` (`#223`, bridging [RFC 0015](./0015-analyze-shell-surface.md))

```rust
#[derive(Clone, PartialEq, Eq)]
pub struct CommandLeaf {
    pub argv: Vec<Vec<u8>>,
}
// Manual fmt::Debug: prints `argc` and per-argument byte lengths only, never raw argv bytes (`P8`).

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CommandInput {
    Resolved { leaves: Vec<CommandLeaf> },
    Unresolved { leaves: Vec<CommandLeaf>, reasons: Vec<UnresolvedReason> },
    Malformed(MalformedReason),
}

pub fn flatten_tree(tree: &CommandTree) -> Vec<CommandLeaf>;

impl From<Resolution<CommandTree>> for CommandInput {
    // Resolved(t) -> Resolved { leaves: flatten_tree(&t) }
    // Unresolved(reasons) -> Unresolved { leaves: Vec::new(), reasons }
    // Malformed(r) -> Malformed(r)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CommandClasses {
    pub classes: BTreeSet<ClassName>,
    pub facts: BTreeSet<ClassName>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct UnresolvedCommandClasses {
    // No `classes` field: unresolved commands report `command.classes` absent, never empty (D-10).
    pub facts: BTreeSet<ClassName>, // always includes EXEC_OPAQUE plus R8 facts from resolved leaves
    pub reasons: Vec<UnresolvedReason>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CommandOutcome {
    Resolved(CommandClasses),
    Unresolved(UnresolvedCommandClasses),
    Malformed(MalformedReason),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct CommandClassLimits {
    /* private: entry_tokens_max: Count */
}

impl CommandClassLimits {
    pub const fn from_schema() -> Self;
    pub fn new(entry_tokens_max: Count) -> Result<Self, CommandClassError>;
    pub const fn entry_tokens_max(self) -> Count;
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct CommandClassifyStats {
    pub max_entry_steps: u64,
    pub total_steps: u64,
}

#[derive(Clone, PartialEq, Eq)]
pub struct CommandClassifier { /* private compiled command + argv-token entries */ }
// Manual fmt::Debug: prints compiled command/fact entry counts only (`P8`).

impl CommandClassifier {
    pub fn build(table: &VocabularyTable) -> Result<Self, CommandClassError>;
    pub fn build_with_limits(
        table: &VocabularyTable,
        limits: CommandClassLimits,
    ) -> Result<Self, CommandClassError>;
    pub fn classify(&self, input: &CommandInput) -> CommandOutcome;
    pub fn classify_with_stats(&self, input: &CommandInput) -> (CommandOutcome, CommandClassifyStats);
}

#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CommandClassError {
    ZeroLimit { field: &'static str },
    EmptyEntry { class: ClassName },
    DoubleSpace { class: ClassName },
    DoubleDashToken { class: ClassName },
    SlashInProgram { class: ClassName },
    EntryTokensOverLimit { class: ClassName, limit: u64, actual: usize },
}
// Implements Display, Error, Coded (1:1 to schema/codes/analyze.toml) and LogSafe (LogValue::Code).
```

Rules for section 4.4: `flatten_tree` traverses `CommandTree` in left-to-right source order, emitting one `CommandLeaf` per `Command::Simple` with non-empty `argv` and recursing into `Command::Subshell`. Wrapper recursion (`sudo`, `env`, `bash -c`) runs upstream before constructing `CommandInput` (`#22` follow-up). `CommandOutcome::Unresolved` always includes `ClassName::parse_schema(grdr_schema::cedar::EXEC_OPAQUE)` in `facts` (alongside any literal-token facts from resolved leaves), even when both `leaves` and `reasons` are empty (for example non-POSIX shells or upstream `TranslationOutcome::Unresolved`).

---

### 5. Mode transform and compiled policy sets (`#217`, `#218`)

#### 5.1 Shared pure compile metadata in `grdr-model` (`#217`, `#218`)

```rust
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModeRuleInput {
    pub meta: RuleMeta,
    pub layer: PolicyLayer,
    pub pack_id: PackId,
    pub pack_version: PackVersion,
    pub requested: Mode,
    pub pack_on_loss: OnLoss,
    pub effective_approver: ApproverKind,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModeContext {
    pub class_table: RuleClassTable,
    pub offered_grades: BTreeSet<ApprovalGrade>,
    pub install_profile: InstallProfile,
}

wire_enum! {
    pub enum CompiledSet {
        Dropped => "dropped",
        Shadow => "shadow",
        Enforced => "enforced",
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CompiledRuleMeta {
    pub rule_id: PolicyRuleId,
    pub instance_id: PolicyRuleId,
    pub layer: PolicyLayer,
    pub pack_id: PackId,
    pub pack_version: PackVersion,
    pub effective_mode: Mode,
    pub set: CompiledSet,
    pub mode_tag: Option<EnforcedMode>,
    pub grant_clause: bool,
    pub min_grade: ApprovalGrade,
    pub exception_grade_floor: ApprovalGrade, // max(min_grade, G1) (#217 R9)
    pub on_loss: OnLoss,
    pub fail_closed: bool,
    pub liftability: Option<Liftability>,     // Some(..) when Enforced, None when Shadow/Dropped
    pub is_final: bool,
    pub approver: ApproverKind,
    pub remedy: Option<Transform>,
    pub obligations: BTreeSet<Obligation>,
    pub user_local_time_lock: bool,
    pub message: Option<InertText>,
    pub steer: Option<InertText>,
}

#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ModeDiagnostic {
    Clamped {
        rule_id: PolicyRuleId,
        requested: Mode,
        effective: Mode,
    },
}

#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ModeCompileError {
    MinGradeBelowClass {
        rule_id: PolicyRuleId,
        class_min: ApprovalGrade,
        rule_min: ApprovalGrade,
    },
    OnLossBelowClass {
        rule_id: PolicyRuleId,
        class_on_loss: OnLoss,
        rule_on_loss: OnLoss,
    },
    ApproverBelowRule {
        rule_id: PolicyRuleId,
        rule_approver: ApproverKind,
        effective_approver: ApproverKind,
    },
    InvalidSourceRuleId {
        rule_id: PolicyRuleId,
    },
    InstanceIdOverLimit {
        rule_id: PolicyRuleId,
    },
    MessageTokenKeyOverLimit {
        rule_id: PolicyRuleId,
    },
    Unspecified {
        rule_id: Option<PolicyRuleId>,
    },
}
// Implements Coded + LogSafe (LogValue::Code); no Display or Error (RFC 0009 R6).
```

Notes for section 5.1:
- `grdr-policy-ref` (`#217`) links `grdr-model` and `std` only (`cargo tree -p grdr-policy-ref -e normal` contains neither `grdr-core` nor `cedar-policy`), type-aliasing or wrapping `ModeRuleInput` (`RefRule`) and `CompiledRuleMeta` (`RefCompiledRule`) and implementing `compile_rule` directly from R1 to R9 with zero shared code (`D-63`).
- **No downgrade or time-lock spoofing by construction (`D-31`, `docs/design/18` section 4):** `ModeRuleInput` omits any raw `user_local_time_lock: bool` field; `compile_rule` computes `user_local_time_lock = (rule.layer == PolicyLayer::User && ctx.install_profile == InstallProfile::User && rule.effective_approver == ApproverKind::SelfApprover && set == CompiledSet::Enforced && effective_mode == Mode::Ask && min_grade == ApprovalGrade::G1)` directly (making cross-layer or protected-profile time-lock forging unrepresentable). Both `#217` and `#218` reject `rule.effective_approver < rule.meta.approver` with `ModeCompileError::ApproverBelowRule`.
- **Source id grammar and `@message` token budget checks (`#217`, `#218`):** `compile_rule` validates `rule.meta.id` against the source rule-id grammar (`[a-z][a-z0-9.-]*`, zero `/`, zero `@`, zero `..`, no empty `.`-separated segment, rejecting non-conforming directly constructed `RuleMeta` values with `InvalidSourceRuleId`), validates the rendered `<layer>/<pack_id>@<pack_version>/<rule_id>` length (`<= POLICY_RULE_ID_MAX`, returning `InstanceIdOverLimit`), and whenever `rule.meta.message.is_some()` enforces checked length `5 + rule.pack_id.as_str().len() + 1 + rule.meta.id.as_str().len() + 8 <= POLICY_RULE_ID_MAX` (`MessageTokenKeyOverLimit`), guaranteeing `TokenKey::parse` for `pack.<pack_id>.<rule_id>.message` can never overflow in `Engine::step`.
- `CompiledRuleMeta::liftability` is `Option<Liftability>` so `Shadow` and `Dropped` rules carry `None` rather than colliding with `Some(Liftability::None)` (final rule at `Block`, `#217` R8).

#### 5.2 Cedar mode transform in `grdr_core::policy::mode` (`#218`)

Module `crates/grdr-core/src/policy/mode.rs` (re-exported via `pub mod mode;` and key types at `grdr_core::policy`) implements the transform through Cedar JSON AST manipulation (`cedar_policy::Policy::to_json` and `Policy::from_json`), never raw string splicing:

```rust
pub use grdr_model::{
    CompiledRuleMeta, CompiledSet, ModeCompileError, ModeContext, ModeDiagnostic, ModeRuleInput,
};

#[derive(Clone, Debug)]
pub struct ModeSourceRule {
    pub policy: cedar_policy::Policy,
    pub input: ModeRuleInput,
}

#[derive(Clone, Debug)]
pub struct CompiledRule {
    pub meta: CompiledRuleMeta,
    pub policy: Option<cedar_policy::Policy>,
    pub diagnostic: Option<ModeDiagnostic>,
}

#[derive(Clone, Debug)]
pub struct CompiledSets {
    pub enforced: cedar_policy::PolicySet,
    pub shadow: cedar_policy::PolicySet,
    pub rules: BTreeMap<PolicyRuleId, CompiledRuleMeta>,
    pub diagnostics: Vec<ModeDiagnostic>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct ModeCompileLimits {
    /* private: bundle_policies_max: Count, rule_id_max: Bytes */
}

impl ModeCompileLimits {
    pub const fn from_schema() -> Self;
    pub fn new(bundle_policies_max: Count, rule_id_max: Bytes) -> Result<Self, ModeError>;
}

#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ModeError {
    MetaCompile(ModeCompileError), // delegates Coded::code() verbatim
    NotForbid { rule_id: Option<PolicyRuleId> },
    ModeAnnotationInSource { rule_id: PolicyRuleId },
    PolicyMetadataMismatch { rule_id: PolicyRuleId },
    DuplicateInstance { instance_id: PolicyRuleId },
    BundlePoliciesOverLimit { limit: u64, actual: usize },
    TransformFailed { rule_id: PolicyRuleId },
    RuleMeta(RuleMetaError),       // delegates Coded::code() verbatim
    ZeroLimit { field: &'static str },
}
// Implements Display, Error, Coded (1:1 to schema/codes/policy.toml) and LogSafe (LogValue::Code).

pub fn compile_rule(
    rule: &ModeSourceRule,
    ctx: &ModeContext,
) -> Result<CompiledRule, ModeError>;

pub fn compile_sets(
    rules: &[ModeSourceRule],
    ctx: &ModeContext,
) -> Result<CompiledSets, ModeError>;

pub fn compile_sets_with_limits(
    rules: &[ModeSourceRule],
    ctx: &ModeContext,
    limits: ModeCompileLimits,
) -> Result<CompiledSets, ModeError>;
```

Rules for section 5.2:
1. **Instance id formatting and source verification:** `compile_rule` enforces every `ModeCompileError` invariant of section 5.1 (`InvalidSourceRuleId`, `ApproverBelowRule`, `MinGradeBelowClass`, `OnLossBelowClass`, `InstanceIdOverLimit`, `MessageTokenKeyOverLimit`), verifies `rule.policy` is a Cedar `forbid` (`NotForbid`), rejects any `@mode` annotation in `rule.policy` (`ModeAnnotationInSource`), and verifies `rule.policy`'s parsed Cedar annotations match every field of `rule.input.meta` (`ModeError::RuleMeta` on invalid annotations, `ModeError::PolicyMetadataMismatch` if any field disagrees). Constructed instance ids follow `<layer>/<pack_id>@<pack_version>/<rule_id>`, assigned as both the Cedar `Policy` id (`PolicyId`) and `@id` annotation value. Because `PackId`, `PackVersion` and validated `rule.meta.id` exclude `/`, `@` and `..`, instance ids are strictly injective.
2. **Deterministic compilation (`#218` R7, R8):** `compile_sets` sorts inputs by `instance_id` before inserting into `enforced` (`PolicySet`) and `shadow` (`PolicySet`), rejects duplicates with `ModeError::DuplicateInstance`, enforces `bundle_policies_max` (`5,000` from `limits.toml`, `docs/design/12` section 16), and validates `RuleMeta` and `ModeCompileError` before emitting policies.
3. **Transform semantics (`#218` R2 to R6):** Rejects `permit` policies (`NotForbid`) and any source already carrying `@mode` (`ModeAnnotationInSource`). `Shadow` rewrites `@id` to `instance_id` only; `Enforced` adds `@mode("Ask")` or `@mode("Block")` (from `Mode::enforced().as_annotation()`), carries all remaining annotations verbatim, preserves every `when`/`unless` clause in order, and appends `unless { context.grants.contains("<rule_id>") }` whenever `meta.grant_clause` is true (`Ask`, or `Block` with `!is_final`).
4. **Consumer alignment:** `policy::decide` (`#1900`) evaluates `CompiledSets::enforced` and `CompiledSets::shadow` directly and looks up satisfied or errored `PolicyRuleId`s inside `CompiledSets::rules` to populate `ForbidMatch`, `NotEvaluableRule` and `DeterminingRule`.

---

### 6. Exec `ActionRequest`, `TranslationOutcome`, Layer-1 `Decision` and `Engine` extensions (`#1861`, amending [RFC 0014](./0014-engine-boundary-c-abi.md))

#### 6.1 Additions to `grdr_core::engine`

Extending RFC 0014 (`grdr_core::engine` `#[non_exhaustive]` contract in `crates/grdr-core/src/engine.rs` and `engine/decide.rs`):

```rust
wire_enum! {
    pub enum TranslationOutcome {
        Resolved => "resolved",
        Unresolved => "unresolved",
        Malformed => "malformed",
    }
}

#[derive(Clone, PartialEq, Eq)]
pub enum EnvDeltaValue {
    Set(Vec<u8>),
    Unset,
}
// Manual fmt::Debug: prints `Set(<len> bytes)` or `Unset`, never raw values (`P8`).

#[derive(Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct ExecActionRequest {
    pub shell: ShellDialect,
    pub translation: TranslationOutcome,
    pub command: Vec<u8>,
    pub env_delta: BTreeMap<Vec<u8>, EnvDeltaValue>,
    pub executable: OpaqueId,
    pub executable_classes: Vec<ClassTag>,
}

impl ExecActionRequest {
    pub fn new(
        shell: ShellDialect,
        translation: TranslationOutcome,
        command: Vec<u8>,
        env_delta: BTreeMap<Vec<u8>, EnvDeltaValue>,
        executable: OpaqueId,
        executable_classes: Vec<ClassTag>,
    ) -> Self;
}
// Manual fmt::Debug: prints `shell`, `translation`, `command_len`, `env_delta_count` and redacted `executable` only.

#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum ActionPayload {
    Exec(ExecActionRequest),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ActionControlContext {
    pub control_coverage: ControlPointCoverage,
    pub os_control_point_attached: bool,
    pub caps: ControlPointCaps,
    pub offered_grades: BTreeSet<ApprovalGrade>,
    pub pending_window: PendingWindow,
    pub modify_budget: ModifyBudget,
}

impl ActionControlContext {
    pub fn new(
        control_coverage: ControlPointCoverage,
        os_control_point_attached: bool,
        caps: ControlPointCaps,
        offered_grades: BTreeSet<ApprovalGrade>,
        pending_window: PendingWindow,
        modify_budget: ModifyBudget,
    ) -> Self;
}

#[derive(Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct ActionRequest {
    pub tool_use_id: OpaqueId,
    pub principal: PrincipalInput,
    pub common: CommonInput,
    pub control: ActionControlContext,
    pub payload: ActionPayload,
}

impl ActionRequest {
    pub fn new(
        tool_use_id: OpaqueId,
        principal: PrincipalInput,
        common: CommonInput,
        control: ActionControlContext,
        payload: ActionPayload,
    ) -> Self;
    pub fn action_class(&self) -> ActionClass; // derived from payload; Exec(_) => ActionClass::Exec
}
// Manual fmt::Debug: prints `action_class`, `control_point`, `control_coverage`, `os_control_point_attached`
// and redacted `tool_use_id` only; zero command bytes, env values or opaque session ids (`P8`).

// Extension to RFC 0014 `Input<'a>`:
#[non_exhaustive]
#[derive(Clone, Debug)]
pub enum Input<'a> {
    Event(&'a Event),
    Tick,
    ActionRequest(&'a ActionRequest),
}

wire_enum! {
    #[non_exhaustive]
    pub enum CacheScope {
        None => "none",
    }
}

#[derive(Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct DeterminingRule {
    pub rule_id: PolicyRuleId,
    pub instance_id: PolicyRuleId,
    pub pack_id: PackId,
    pub pack_version: PackVersion,
    pub layer: PolicyLayer,
    pub mode: EnforcedMode,
    pub approver: ApproverKind,
    pub liftability: Liftability, // Enforced determining rules always hold a Liftability variant
    pub is_final: bool,
    pub min_grade: ApprovalGrade,
    pub message: Option<PolicyMessageRef>,
    pub steer: Option<PolicyMessageRef>,
}
// Manual fmt::Debug: structural metadata + redacted PolicyMessageRef summaries.

#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub struct Decision {
    pub action_class: ActionClass,
    pub control_point: ControlPoint,
    pub control: ControlPointCoverage,
    pub coverage_gap: bool,
    pub verdict: Verdict,
    pub executed_as: ExecutedVerb,
    pub would_be: Option<Verdict>,
    pub row: DerivationRow,
    pub reason: DecisionReason,
    pub determining: Vec<DeterminingRule>, // sorted deterministically by (instance_id, rule_id)
    pub obligations: BTreeSet<Obligation>,
    pub not_evaluable: BTreeSet<PolicyRuleId>,
    pub min_grade: Option<ApprovalGrade>,
    pub transform: Option<Transform>,
    pub retry_after_ms: Option<u64>,
    pub hold_ms: Option<u64>,
    pub cache_scope: CacheScope,
}

// Extension to RFC 0014 `StepOutput`:
#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StepOutput {
    pub step_seq: u64,
    pub step_id: StepId,
    pub events: Vec<Event>,
    pub effects: Vec<Effect>,
    pub diagnostics: Vec<Diagnostic>,
    pub decision: Option<Decision>, // None for Event and Tick; Some(Decision) for ActionRequest
}

// Extension to RFC 0014 `LoadError` (preserves `Copy`):
#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LoadError {
    Profile,
    SnapshotBundle,
    SnapshotFormat,
    Policy(&'static Code), // wraps coded error from pack reader, layer merge, compile, read-set, or mode transform
}
```

Rules for section 6.1:
1. **`Input::Event` and `Input::Tick` untouched:** Existing RFC 0014 paths emit `decision: None`, preserving `#384`, `#388` and `#19` binary parity vectors without modification. `grdr.embed.v1alpha1` (`Input` tags 3..5, `Output.decision` tag 6) stays reserved until a wire RFC unreserves it (`#1861` Non-goals).
2. **`LoadError: Copy` preserved (`RFC 0014` section 3.2):** Adding `LoadError::Policy(&'static Code)` satisfies `#1861` R1 (`"LoadError::Policy with that error's code"`) and `Coded::code()` (`ARCH-017`) while preserving `Copy` across `grdr-ffi` and `grdr-wasm`.
3. **External construction and read-only outputs:** Callers in `grdr-engine` (`#1537`) and integration tests construct inputs via `ExecActionRequest::new`, `ActionControlContext::new` (or struct literal) and `ActionRequest::new`, avoiding E0639 on `#[non_exhaustive]` request structs while staying within Clippy's argument-count threshold. `Decision` and `DeterminingRule` are `#[non_exhaustive]` outputs constructed solely within `grdr-core`; `#[derive(Debug)]` on `Decision` is `P8`-clean because `DeterminingRule` redacts `PolicyMessageRef` and all other fields are `structural`.
4. **Control effect computation on `Decision`:** `Decision.control` equals `ControlPointCoverage::None` when `executed_as == ExecutedVerb::ObserveOnly` (`coverage_gap == true`), otherwise `request.control.control_coverage`.
5. **In-process pipeline (`#1861` R3 to R6):**
   - When `translation == TranslationOutcome::Malformed`, `Engine::step` skips `analyze::shell::canonicalise` and evaluates `NormaliserOutcome::Malformed` in `policy::decide` (row 1, `Verdict::Deny`).
   - When `translation == TranslationOutcome::Resolved` and `shell == ShellDialect::Posix`, `Engine::step` builds `ShellInput` from `command` and `EnvDeltaValue::Set` entries, calls `analyze::shell::canonicalise` under bundle `ShellLimits`, maps `Resolution<CommandTree>` to `CommandInput` (`From<Resolution<CommandTree>>`), classifies via `CommandClassifier` (`#223`), and builds `ExecInput` via `build_exec` (`#1600`, mapping `ClassName::as_str()` to `ClassTag` and `CommandOutcome::Unresolved` to neutral `[]` + `ContextField::CommandClasses` in `absent` + `exec.opaque` in `facts`).
   - Any non-POSIX `ShellDialect` or `translation == TranslationOutcome::Unresolved` enters `CommandClassifier` as `CommandInput::Unresolved { leaves: vec![], reasons: vec![] }` (`#1861` R3, `#223` R9: sets `exec.opaque`, marks `context.command.classes` absent).
   - If `build_exec` fails Cedar schema validation (`#1600` R4), `Engine::step` returns a `Decision` with `Verdict::Deny`, `DerivationRow::PolicyError`, `DecisionReason::PolicyError`, and emits the builder's `PolicyError` code in `StepOutput.diagnostics` (`#1861` R4).
   - `Output.diagnostics` sorts all `ShadowMatch`, `ShadowError`, `PolicyError` and coverage-gap `Diagnostic` entries deterministically by `(code.as_str(), rule_id)`.
6. **`PolicyMessageRef` and Layer-4 rendering (`#1537`):** For a determining rule carrying `@message`, `token_id` is deterministically derived as `pack.<pack_id>.<rule_id>.message` (guaranteed `<= POLICY_RULE_ID_MAX` by section 5.1's `MessageTokenKeyOverLimit` check at compile time, with `@message` in `source`), and for `@steer` as `agent.steer` (with `@steer` in `source`). Layer-4 `grdr-engine` (`#1537`) maps these Layer-1 structural values to `grdr_strings::MessageRef` (`#1384`, RFC 0017 `pack-text`), keeping Layer 1 free of `grdr-strings` (`ARCH-001`, `ARCH-024`).
7. **`Engine::load` policy state and `LoadReport.not_evaluable` (`#1861` R1):** `Engine::load` keeps RFC 0014's exact signature (`(&VerifiedBundle, &HostProfile) -> Result<(Engine, LoadReport), LoadError>`), compiling bundle policy state during load, reporting unsupported-field rules in RFC 0014's `LoadReport.not_evaluable`, and surfacing any reader, layer-merge, compile or validation error as `LoadError::Policy(err.code())`.

---

### 7. Registered error codes (`schema/codes/`), `limits.toml` (`#741`) and follow-up gates

#### 7.1 `schema/codes/` entries under RFC 0007 and RFC 0010 (`ADR-0038`, `ADR-0044`)

Under RFC 0007 section 4 ("Content, not surface"), each implementing item registers the error codes it constructs (`schema/codes/{model,policy,analyze,core}.toml` and `interface/strings/src/code.mf2.toml` under RFC 0010, with lowercase `code.<area>_<nnnn>.message` and `.fix` tokens). Because sibling items (`#435`, `#436`, `#1595`, `#1900`, `#384`) may allocate earlier numbers in parallel, exact numeric codes follow RFC 0007 section 4 ("one above the highest present in `schema/codes/<area>.toml`"), while this RFC freezes the canonical `Reason`, `ErrorClass`, `ConnectCode` and error-variant bindings below (showing first free slots after RFC 0013's `MODEL-0012` and `POLICY-0012`, RFC 0015's `ANALYZE-0006` and RFC 0014's `CORE-0009`):

| Area & suggested slot | Reason (`UPPER_SNAKE`) | Class | Connect | Bound error variant(s) |
|---|---|---|---|---|
| `MODEL` `0013` | `ANNOTATION_SPELLING_INVALID` | `input` | `invalid_argument` | `AnnotationParseError::UnknownSpelling` |
| `POLICY` `0013` | `LIMITS_ZERO_OR_OUT_OF_RANGE` | `input` | `invalid_argument` | `RuleMetaLimitsError::{ZeroLimit, ExceedsSchemaMax}`, `ModeError::ZeroLimit` |
| `POLICY` `0014` | `ANNOTATION_MISSING_REQUIRED` | `input` | `invalid_argument` | `RuleMetaError::MissingRequired` |
| `POLICY` `0015` | `ANNOTATION_UNKNOWN_KEY` | `input` | `invalid_argument` | `RuleMetaError::UnknownKey` |
| `POLICY` `0016` | `ANNOTATION_DUPLICATE_KEY` | `input` | `invalid_argument` | `RuleMetaError::DuplicateKey` |
| `POLICY` `0017` | `ANNOTATION_INVALID_CLASS` | `input` | `invalid_argument` | `RuleMetaError::InvalidClass` |
| `POLICY` `0018` | `ANNOTATION_INVALID_MAX_MODE` | `input` | `invalid_argument` | `RuleMetaError::InvalidMaxMode` |
| `POLICY` `0019` | `ANNOTATION_INVALID_APPROVER` | `input` | `invalid_argument` | `RuleMetaError::InvalidApprover` |
| `POLICY` `0020` | `ANNOTATION_INVALID_MIN_GRADE` | `input` | `invalid_argument` | `RuleMetaError::InvalidMinGrade` |
| `POLICY` `0021` | `ANNOTATION_INVALID_ON_LOSS` | `input` | `invalid_argument` | `RuleMetaError::InvalidOnLoss` |
| `POLICY` `0022` | `ANNOTATION_INVALID_FINAL` | `input` | `invalid_argument` | `RuleMetaError::InvalidFinal` |
| `POLICY` `0023` | `ANNOTATION_INVALID_REMEDY` | `input` | `invalid_argument` | `RuleMetaError::InvalidRemedy` |
| `POLICY` `0024` | `ANNOTATION_INVALID_OBLIGATION` | `input` | `invalid_argument` | `RuleMetaError::InvalidObligation` |
| `POLICY` `0025` | `ANNOTATION_DUPLICATE_OBLIGATION` | `input` | `invalid_argument` | `RuleMetaError::DuplicateObligation` |
| `POLICY` `0026` | `ANNOTATION_INVALID_STATUS` | `input` | `invalid_argument` | `RuleMetaError::InvalidStatus` |
| `POLICY` `0027` | `RULE_ID_INVALID_SYNTAX` | `input` | `invalid_argument` | `RuleMetaError::RuleIdInvalid`, `ModeCompileError::InvalidSourceRuleId` |
| `POLICY` `0028` | `RULE_ID_PREFIX_MISMATCH` | `input` | `invalid_argument` | `RuleMetaError::RuleIdPrefixMismatch` |
| `POLICY` `0029` | `RULE_ID_OVER_LIMIT` | `input` | `invalid_argument` | `RuleMetaError::RuleIdOverLimit`, `ModeCompileError::InstanceIdOverLimit` |
| `POLICY` `0030` | `MESSAGE_TOKEN_KEY_OVER_LIMIT` | `input` | `invalid_argument` | `ModeCompileError::MessageTokenKeyOverLimit` |
| `POLICY` `0031` | `ANNOTATION_TEXT_OVER_LIMIT` | `input` | `invalid_argument` | `RuleMetaError::AnnotationOverLimit` |
| `POLICY` `0032` | `ANNOTATION_TEXT_CONTROL_CHAR` | `input` | `invalid_argument` | `RuleMetaError::AnnotationControlChar` |
| `POLICY` `0033` | `ANNOTATION_TEXT_URL_FORBIDDEN` | `input` | `invalid_argument` | `RuleMetaError::AnnotationDisallowedUrl` |
| `POLICY` `0034` | `RULE_CLASS_TABLE_INVALID` | `input` | `invalid_argument` | `RuleClassTableError::{MissingClass, DuplicateClass}` |
| `POLICY` `0035` | `MIN_GRADE_BELOW_CLASS` | `input` | `invalid_argument` | `ModeCompileError::MinGradeBelowClass` |
| `POLICY` `0036` | `ON_LOSS_BELOW_CLASS` | `input` | `invalid_argument` | `ModeCompileError::OnLossBelowClass` |
| `POLICY` `0037` | `APPROVER_BELOW_RULE` | `input` | `invalid_argument` | `ModeCompileError::ApproverBelowRule` |
| `POLICY` `0038` | `MODE_COMPILE_UNSPECIFIED` | `internal` | `internal` | `ModeCompileError::Unspecified` |
| `POLICY` `0039` | `SOURCE_RULE_NOT_FORBID` | `input` | `invalid_argument` | `ModeError::NotForbid` |
| `POLICY` `0040` | `MODE_ANNOTATION_IN_SOURCE` | `input` | `invalid_argument` | `ModeError::ModeAnnotationInSource` |
| `POLICY` `0041` | `POLICY_METADATA_MISMATCH` | `input` | `invalid_argument` | `ModeError::PolicyMetadataMismatch` |
| `POLICY` `0042` | `DUPLICATE_RULE_INSTANCE` | `input` | `invalid_argument` | `ModeError::DuplicateInstance` |
| `POLICY` `0043` | `BUNDLE_POLICIES_OVER_LIMIT` | `input` | `invalid_argument` | `ModeError::BundlePoliciesOverLimit` |
| `POLICY` `0044` | `MODE_TRANSFORM_FAILED` | `internal` | `internal` | `ModeError::TransformFailed` |
| `ANALYZE` `0007` | `ANALYZE_LIMIT_ZERO` | `input` | `invalid_argument` | `ZeroLimit` across `VocabularyError`, `PathClassError`, `HostClassError`, `CommandClassError` |
| `ANALYZE` `0008` | `VOCAB_CLASS_NAME_INVALID` | `input` | `invalid_argument` | `VocabularyError::InvalidClassName` |
| `ANALYZE` `0009` | `VOCAB_CLASS_NAME_OVER_LIMIT` | `input` | `invalid_argument` | `VocabularyError::ClassNameOverLimit` |
| `ANALYZE` `0010` | `VOCAB_DUPLICATE_LIST` | `input` | `invalid_argument` | `VocabularyError::DuplicateList` |
| `ANALYZE` `0011` | `VOCAB_POLARITY_CONFLICT` | `input` | `invalid_argument` | `VocabularyError::PolarityConflict` |
| `ANALYZE` `0012` | `VOCAB_FEED_LIST_NOT_PROTECT` | `input` | `invalid_argument` | `VocabularyError::FeedListNotProtect` |
| `ANALYZE` `0013` | `VOCAB_FEED_LIST_TYPE` | `input` | `invalid_argument` | `VocabularyError::FeedListType` |
| `ANALYZE` `0014` | `VOCAB_LIST_ENTRIES_OVER_LIMIT` | `input` | `invalid_argument` | `VocabularyError::ListEntriesOverLimit` |
| `ANALYZE` `0015` | `VOCAB_LIST_ENTRY_OVER_LIMIT` | `input` | `invalid_argument` | `VocabularyError::ListEntryOverLimit` |
| `ANALYZE` `0016` | `VOCAB_TOTAL_ENTRIES_OVER_LIMIT` | `input` | `invalid_argument` | `VocabularyError::VocabularyEntriesOverLimit` |
| `ANALYZE` `0017` | `VOCAB_NOT_FEED_MANAGED` | `input` | `invalid_argument` | `VocabularyError::NotFeedManaged` |
| `ANALYZE` `0018` | `VOCAB_UNKNOWN_LIST` | `input` | `invalid_argument` | `VocabularyError::UnknownList` |
| `ANALYZE` `0019` | `PATH_NOT_CANONICAL` | `input` | `invalid_argument` | `PathInputError::NotCanonical` |
| `ANALYZE` `0020` | `PATH_PATTERN_NOT_UTF8` | `input` | `invalid_argument` | `PathClassError::PatternNotUtf8` |
| `ANALYZE` `0021` | `PATH_PATTERN_OVER_LIMIT` | `input` | `invalid_argument` | `PathClassError::PatternOverLimit` |
| `ANALYZE` `0022` | `PATH_PATTERN_INVALID_START` | `input` | `invalid_argument` | `PathClassError::PatternInvalidStart` |
| `ANALYZE` `0023` | `PATH_PATTERN_DOUBLE_STAR` | `input` | `invalid_argument` | `PathClassError::DoubleStarWithBytes` |
| `ANALYZE` `0024` | `PATH_PATTERN_UNKNOWN_TEMPLATE` | `input` | `invalid_argument` | `PathClassError::UnknownTemplate` |
| `ANALYZE` `0025` | `PATH_PATTERN_TEMPLATE_POSITION` | `input` | `invalid_argument` | `PathClassError::TemplateNotFirstSegment` |
| `ANALYZE` `0026` | `PATH_PATTERN_EMPTY_SEGMENT` | `input` | `invalid_argument` | `PathClassError::EmptySegment` |
| `ANALYZE` `0027` | `PATH_PATTERN_DOT_SEGMENT` | `input` | `invalid_argument` | `PathClassError::DotSegment` |
| `ANALYZE` `0028` | `PATH_PATTERN_DANGLING_ESCAPE` | `input` | `invalid_argument` | `PathClassError::DanglingEscape` |
| `ANALYZE` `0029` | `HOST_NON_ASCII` | `input` | `invalid_argument` | `HostInputError::NonAscii` |
| `ANALYZE` `0030` | `HOST_INVALID` | `input` | `invalid_argument` | `HostInputError::InvalidHost` |
| `ANALYZE` `0031` | `HOST_ENTRY_OVER_LIMIT` | `input` | `invalid_argument` | `HostClassError::EntryOverLimit` |
| `ANALYZE` `0032` | `HOST_ENTRY_EMPTY` | `input` | `invalid_argument` | `HostClassError::EmptyEntry` |
| `ANALYZE` `0033` | `HOST_ENTRY_INVALID_SYNTAX` | `input` | `invalid_argument` | `HostClassError::InvalidEntrySyntax` |
| `ANALYZE` `0034` | `HOST_ENTRY_INVALID_CIDR` | `input` | `invalid_argument` | `HostClassError::InvalidCidrPrefix` |
| `ANALYZE` `0035` | `HOST_ENTRY_NON_ZERO_HOST_BITS` | `input` | `invalid_argument` | `HostClassError::NonZeroHostBits` |
| `ANALYZE` `0036` | `COMMAND_ENTRY_EMPTY` | `input` | `invalid_argument` | `CommandClassError::EmptyEntry` |
| `ANALYZE` `0037` | `COMMAND_ENTRY_DOUBLE_SPACE` | `input` | `invalid_argument` | `CommandClassError::DoubleSpace` |
| `ANALYZE` `0038` | `COMMAND_ENTRY_DOUBLE_DASH` | `input` | `invalid_argument` | `CommandClassError::DoubleDashToken` |
| `ANALYZE` `0039` | `COMMAND_ENTRY_SLASH_PROGRAM` | `input` | `invalid_argument` | `CommandClassError::SlashInProgram` |
| `ANALYZE` `0040` | `COMMAND_ENTRY_TOKENS_OVER_LIMIT` | `input` | `invalid_argument` | `CommandClassError::EntryTokensOverLimit` |
| `CORE` `0010` | `ENGINE_SHADOW_RULE_MATCHED` | `policy` | `permission_denied` | `Output.diagnostics` for `ShadowMatch` (`Severity::Warning`, `#1861` R6/R9) |
| `CORE` `0011` | `ENGINE_SHADOW_RULE_ERRORED` | `policy` | `internal` | `Output.diagnostics` for `ShadowError` (`Severity::Warning`, `#1861` R6/R9) |
| `CORE` `0012` | `ENGINE_COVERAGE_GAP` | `policy` | `failed_precondition` | `Output.diagnostics` for `coverage_gap` (`Severity::Warning`, `#1861` R6/R9) |

Note on `RuleMetaLimitsError::ZeroLimit` / `RuleMetaLimitsError::ExceedsSchemaMax` and `RuleClassTableError::MissingClass` / `DuplicateClass`: if AC checks separate codes per sub-variant, split `LIMITS_ZERO` / `LIMITS_OUT_OF_RANGE` and `RULE_CLASS_MISSING` / `RULE_CLASS_DUPLICATE` under RFC 0007 section 4 without changing this RFC.

#### 7.2 `[bound.policy.*]` limits rows in `limits.toml` (`#741` PC-2)

All names below satisfy RFC 0007 section 6's strict naming rules (no hyphenated segment matches a unit word such as `bytes`, `count`, `ms` or `permille`, and no dot-separated segment matches a format keyword such as `min` or `max`):

| `#741` stub key | Canonical `limits.toml` key | Unit = value | `min`..=`max` | Scope / Effect | Generated constant (`grdr_schema::limits`) | Consumer |
|---|---|---|---|---|---|---|
| `annotation_max_bytes` | `policy.annotation-max` | `bytes = 1024` | `64..=4096` | `fixed` / `none` | `POLICY_ANNOTATION_MAX` | `#212` |
| `rule_id_max_bytes` | `policy.rule-id-max` | `bytes = 256` | `32..=512` | `fixed` / `none` | `POLICY_RULE_ID_MAX` | Reused from RFC 0013 (`#212`, `#218`) |
| `class_name_max_bytes` | `policy.class-name-max` | `bytes = 128` | `32..=256` | `fixed` / `none` | `POLICY_CLASS_NAME_MAX` | `#213` (must satisfy `<= POLICY_CLASS_TAG_MAX`) |
| `list_max_entries` | `policy.list-entries-max` | `count = 4096` | `1..=65536` | `fixed` / `none` | `POLICY_LIST_ENTRIES_MAX` | `#213` |
| `list_entry_max_bytes` | `policy.list-entry-max` | `bytes = 1024` | `64..=4096` | `fixed` / `none` | `POLICY_LIST_ENTRY_MAX` | `#213` |
| `vocabulary_max_entries` | `policy.vocabulary-entries-max` | `count = 32768` | `1..=262144` | `fixed` / `none` | `POLICY_VOCABULARY_ENTRIES_MAX` | `#213` |
| `path_pattern_max_bytes` | `policy.path-pattern-max` | `bytes = 512` | `64..=4096` | `fixed` / `none` | `POLICY_PATH_PATTERN_MAX` | `#221` |
| `path_max_bytes` | `policy.path-max` | `bytes = 4096` | `256..=32768` | `fixed` / `none` | `POLICY_PATH_MAX` | `#221` |
| `host_entry_max_bytes` | `policy.host-entry-max` | `bytes = 256` | `64..=1024` | `fixed` / `none` | `POLICY_HOST_ENTRY_MAX` | `#222` |
| `command_entry_max_tokens` | `policy.command-entry-tokens-max` | `count = 16` | `1..=64` | `fixed` / `none` | `POLICY_COMMAND_ENTRY_TOKENS_MAX` | `#223` |
| `5,000` policy count (`§16`) | `policy.bundle-policies-max` | `count = 5000` | `1..=50000` | `fixed` / `none` | `POLICY_BUNDLE_POLICIES_MAX` | `#218`, `#71` |
| `retry_token_ttl_ms` (slice 1) | `policy.retry-token-ttl` | `ms = 600000` | `60000..=3600000` | `fixed` / `none` | `POLICY_RETRY_TOKEN_TTL` | Slice 1 (`#215`) |
| `route_timer_default_ms` (slice 1) | `policy.route-timer-default` | `ms = 14400000` | `60000..=86400000` | `fixed` / `none` | `POLICY_ROUTE_TIMER_DEFAULT` | Slice 1 (`#215`) |
| `approval_streak` (slice 1) | `policy.approval-streak-max` | `count = 3` | `1..=10` | `fixed` / `none` | `POLICY_APPROVAL_STREAK_MAX` | Slice 1 (`#215`) |
| `grants_index_max` (slice 1) | `policy.grants-index-max` | `count = 4096` | `1..=65536` | `fixed` / `none` | `POLICY_GRANTS_INDEX_MAX` | Slice 1 (`#219`) |

---

### 8. Mechanisms (`P14`), Data classes (`P8`), Assurance (`P1`), Failure modes (`P9`), Scale (`P15`) and downstream write-backs

- **Mechanism (`P14`):** All rule classes, default grades, loss outcomes, vocabulary lists, path/host/command patterns, mode settings, bounds (`limits.toml`) and error text (`schema/codes/`) live in pack artefacts or schema tables. Rust types encode only fixed vocabulary domains (`Mode`, `RuleClass`, `ApproverKind`, `OnLoss`, `Obligation`, `Transform`, `ListType`, `PathTemplate`) and deterministic evaluation rules.
- **Data classes (`P8`):** Rule metadata (`RuleMeta`, `RuleClassTable`, `CompiledRuleMeta`, `PolicyMessageRef`), vocabulary class names and `PolicyLayer`/`PackId` are `structural`; raw command bytes, environment values, canonical paths, template roots, canonical hosts and `OpaqueId` fields are `content` or `identifier`, implement manual redacting `fmt::Debug` and never implement `LogSafe`.
- **Assurance (`P1`):** Mode transformation decides `Enforced` vs `Shadow` sets and propagates `fail_closed`; `PathClassifier` treats absent templates or unsafe case-folded non-ASCII protect comparisons as explicit `undecided` (never silent non-match); `CommandClassifier` sets `exec.opaque` and omits `classes` on `Unresolved`; `Decision.control` records `ControlPointCoverage::None` when observe-only.
- **Failure modes (`P9`):** Every invalid annotation, malformed pack list, duplicate instance id, out-of-range limit or schema error fails closed with a coded error, keeping the device's last-known-good bundle intact; malformed inputs on `ActionRequest` or `CanonicalPath`/`CanonicalHost` decide `Verdict::Deny` upstream; zero `unwrap`/`expect`/`panic!` paths exist in non-test code.
- **Scale (`P15`):** Bounded entry matching (`(path_chars + 1) * (pattern_chars + 1)` in `PathClassifier`, `(leaf_elems + 1) * (entry_tokens + 1)` in `CommandClassifier`) and deterministic `BTreeMap`/`BTreeSet` containers keep evaluation quadratic-safe and bounded by `limits.toml`.

#### Protected follow-up items and downstream write-backs after acceptance

1. **Protected changes (for `lead-agent-kit` / `chief-architect`):**
   - `#741` (`PC-2`, `limits.toml`): adopt section 7.2's RFC-0007-compliant `[bound.policy.*]` keys (unblocking `#212`, `#213`, `#218`, `#221`, `#222`, `#223`).
   - `#2075` / `#1582` (`architecture.toml` + `security/trust-core.paths`): extend RFC 0013's `ARCH-007` experimental Cedar exposure tracking to `cedar_policy::{Policy, PolicySet}` in `grdr_core::policy::mode`; confirm `ARCH-013` permits `analyze::command_class -> grdr_schema::cedar::EXEC_OPAQUE`; track `PC-1` (`crates/grdr-policy-ref/**`) in `security/trust-core.paths`.
   - `#435` / `#223`: export `pub const EXEC_OPAQUE: &str = "exec.opaque";` in `crates/grdr-schema/src/cedar.rs`.
   - `#278` / `#1853`: register section 7.1 `MODEL`, `POLICY`, `ANALYZE` and `CORE` codes and RFC 0010 tokens as each implementing item lands.
   - Design doc follow-up (`chief-architect`): sync `docs/design/12`, `13`, `03` and `34` with `EXEC_OPAQUE`, `CommandInput`/`flatten_tree`, `PolicyMessageRef` Layer-1/Layer-4 split, and slice-0 `limits.toml` keys.
2. **Downstream issue write-backs:**
   - **`#739`:** record RFC 0018 acceptance (`ADR-0056` or next ADR), noting slice-1 grant/retry types (`#214`, `#215`, `#219`) remain deferred per `#739-E1`.
   - **`#212`:** reuse RFC 0013's `ApprovalGrade`, `Obligation`, `Transform`, `EnforcedMode`, `PolicyRuleId` in `grdr-model` crate root; add `Obligation::is_must`, `as_annotation`/`from_annotation`, `AnnotationParseError` (`GRDR-MODEL-0013`), `ApproverKind::SelfApprover`, `RuleMeta.is_final`, `RuleMetaLimits`, `PackId`, `PackVersion`, `PolicyLayer`, `InertText`, `TokenKey`, `PolicyMessageRef`, `RuleClassTable::{new, try_from_entries}` and granular `RuleMetaError` codes.
   - **`#213`:** type `VocabularyList.entries` as `Vec<Vec<u8>>` (with `from_strs` helper), adopt `VocabularyLimits` (`policy.class-name-max`, `policy.list-entries-max`, `policy.list-entry-max`, `policy.vocabulary-entries-max`), add `UnknownList` and `ClassNameOverLimit`, and note `POLICY_CLASS_NAME_MAX <= POLICY_CLASS_TAG_MAX`.
   - **`#217`:** share `ModeRuleInput` (`RefRule`), `ModeContext` (carrying `InstallProfile`, deriving `user_local_time_lock` cleanly without an unconstrained input boolean), `CompiledSet`, `CompiledRuleMeta` (`RefCompiledRule` with `liftability: Option<Liftability>`), `ModeDiagnostic` and `ModeCompileError` (`ApproverBelowRule`, `InvalidSourceRuleId`, `InstanceIdOverLimit`, `MessageTokenKeyOverLimit`) from `grdr-model` while keeping zero dependency on `grdr-core` or `cedar-policy`.
   - **`#218`:** expose `CompiledRule`, `CompiledSets`, `ModeSourceRule`, `ModeCompileLimits`, `ModeError` (including `PolicyMetadataMismatch` verifying source `Policy` annotations against `ModeRuleInput.meta`), `compile_rule`, `compile_sets` in `grdr_core::policy::mode` (`ARCH-007` `Policy`/`PolicySet` tracked while `experimental`), bind `policy.bundle-policies-max`, and compare `CompiledRule.meta == RefCompiledRule` in `#218` AC-2.
   - **`#221`:** adopt `PathTemplate`, `PathContext` (`Option<CanonicalPath>`), `CanonicalPath` (root `/` permitted; manual redacting `Debug`), `WorkspaceMembership`, `PathClasses`, `PathClassLimits` (`policy.path-pattern-max`, `policy.path-max`), `build`/`build_with_limits` and `classify_with_stats`.
   - **`#222`:** adopt `CanonicalHost` (redacting `Debug`, bracket removal + IPv4-mapped/NAT64 IPv4 conversion at parse), `HostClassLimits` (`policy.host-entry-max`), `build`/`build_with_limits`, `HostInputError` and `HostClassError`.
   - **`#223`:** import `grdr_schema::cedar::EXEC_OPAQUE`, expose `CommandLeaf`, `CommandInput`, `flatten_tree`, `From<Resolution<CommandTree>>`, `CommandClasses`, `UnresolvedCommandClasses` (without `classes` field), `CommandOutcome`, `CommandClassLimits` (`policy.command-entry-tokens-max`) and `classify_with_stats`.
   - **`#1861`:** adopt Layer-1 `TranslationOutcome`, `EnvDeltaValue`, `ExecActionRequest::new`, `ActionPayload`, `ActionControlContext::new`, `ActionRequest::new`, `DeterminingRule`, `PolicyMessageRef`, `CacheScope`, `Decision`, `StepOutput.decision` and `LoadError::Policy(&'static Code)`, with `#1537` translating `PolicyMessageRef` into `grdr_strings::MessageRef`.
   - **`#1600`, `#1900`, `#1885`:** `#1600` consumes `ClassTag::parse(class_name.as_str())` and `CommandOutcome::Unresolved`; `#1900` consumes `CompiledSets::{enforced, shadow, rules}` (`CompiledRuleMeta`) and `ModeError`; `#1885` shares `RuleMeta`, `PolicyLayer`, `PackId`, `PackVersion` and `VocabularyList` without redefining them.

## Surfaces changed

This RFC authors specification only (`rfcs/0018-policy-engine-slice-0-public-types.md`). No crate source, schema, `limits.toml`, `surfaces.toml`, `architecture.toml`, `security/trust-core.paths`, `rfcs/pins.toml` or `docs/design/` file is modified in this pull request. Upon acceptance and follow-up issue execution, the surfaces below change under `class = "experimental"` (`D-60`):

| Surface | Change summary | Implementing item(s) |
|---|---|---|
| `grdr-model` (layer 1, amending RFC 0009) | Root-exported rule metadata types, `AnnotationParseError`, `RuleClassTable`, `ModeRuleInput`, `ModeContext`, `CompiledRuleMeta`, `PolicyMessageRef`, `Obligation::is_must`, `ModeCompileError` | `#212`, `#217` |
| `grdr-core` (layer 1, amending RFC 0013, RFC 0014, RFC 0015) | `analyze::{vocab, path_class, host_class, command_class}`, `policy::mode` (`cedar_policy::{Policy, PolicySet}` under `ARCH-007`), `engine::{Input::ActionRequest, ActionRequest, ActionControlContext, ActionPayload, ExecActionRequest, Decision, StepOutput.decision, LoadError::Policy}` | `#213`, `#221`, `#222`, `#223`, `#218`, `#1861` |
| `grdr-schema` (layer 0, amending RFC 0007, RFC 0013) | `cedar::EXEC_OPAQUE`, `MODEL` / `POLICY` / `ANALYZE` / `CORE` error codes, 10 slice-0 `[bound.policy.*]` limits rows (reusing `policy.rule-id-max`) | `#435`, `#278`, `#741` |
| `grdr-policy-ref` (`tool`) | Pure `mode` reference evaluator over `grdr-model` (`PC-1` trust core) | `#217` |
| Gate and design files | `limits.toml`, `architecture.toml`, `security/trust-core.paths`, `schema/codes/`, `docs/design/{03,12,13,34}` | `#741`, `#2075`, `#1582`, `#278`, `#1853`, design follow-up |

## Alternatives

1. **Depend on Layer-2 `grdr-strings::MessageRef` directly from `grdr-core` (`#1861` R5 literally):**
   - *Rejected:* Violates `ARCH-001` ("five layers, one direction") and `ARCH-024` by dragging ICU4X/locale crates into Layer 1 and `grdr-ffi`/`grdr-wasm`. Using Layer-1 `PolicyMessageRef` lets Layer-4 `grdr-engine` (`#1537`) resolve `MessageRef` and `CompiledPackMessage` cleanly.
2. **Duplicate `ApprovalGrade`, `Obligation`, `Transform` and `EnforcedMode` in `grdr-model::policy` or drop `wire_enum!` for TitleCase wire strings:**
   - *Rejected:* Violates `P17` and [RFC 0009](./0009-grdr-model-slice-0-surface.md) R5 (`WireName` grammar requires lower-case words). Explicit `as_annotation`/`from_annotation` methods preserve shared types and round-trip annotation parsing simultaneously.
3. **Wrap `LoadError::Policy(PolicyError)` in `grdr_core::engine` instead of `&'static Code`:**
   - *Rejected:* `PolicyError` holds a `BTreeSet<PolicyRuleId>`, stripping `Copy` from RFC 0014's `LoadError` and breaking `grdr-ffi` / `grdr-wasm` error handling contracts (`ADR-0054`).
4. **Keep `VocabularyList.entries` as `Vec<String>` instead of `Vec<Vec<u8>>`:**
   - *Rejected:* Prevents `#221` R2's non-UTF-8 entry check (`PatternNotUtf8`) from running through `VocabularyTable` and prevents non-UTF-8 POSIX command entries from matching `argv` byte strings (`#223` R1).
5. **Include `#214`, `#215` and `#219` (grants, `CanonicalAction`, retry tokens) in RFC 0018:**
   - *Rejected:* Overturns `#739-E1` Option A, delaying slice-0 unblocking of `#645` behind unrelated E2.2 grant-index design details.
6. **Require `#1861` to run `PathClassifier` (`#221`) inside slice-0 exec:**
   - *Rejected:* Adds an unrequested dependency edge from `#1861` onto `#221` (`#1861` only depends on `#223` and `#1600`); keeping `executable_classes: Vec<ClassTag>` on `ExecActionRequest` supports slice-0 `grdr-core` tests now and `#221` population later without changing `ActionRequest`.

## Drawbacks

- Requires write-back edits to `#212`, `#213`, `#217`, `#218`, `#221`, `#222`, `#223`, `#1861`, `#741`, `#435`, `#1600`, `#1900` and `#1537` so issue specs match the exact unified signatures (`RuleMetaLimits`, `ApproverKind::SelfApprover`, `is_final`, `Vec<Vec<u8>>` entries, `CommandInput`, `PolicyMessageRef`, `LoadError::Policy(&'static Code)` and compliant `limits.toml` names).
- Extends [RFC 0009](./0009-grdr-model-slice-0-surface.md) (`grdr-model` crate root), [RFC 0013](./0013-cedar-schema-grdr-policy-surface.md) (`EXEC_OPAQUE`, `ARCH-007` `Policy`/`PolicySet`), and [RFC 0014](./0014-engine-boundary-c-abi.md) (`Input::ActionRequest`, `StepOutput.decision`, `LoadError::Policy`) before slice 1, reserving future tightening of `cedar_policy` behind opaque wrappers prior to `beta` promotion (`D-60`).

## Unresolved questions

None for slice-0 scope. Three follow-up items remain for slice-1+ RFCs without blocking `#212`, `#213`, `#217`, `#218`, `#221`, `#222`, `#223` or `#1861`:
1. Slice-1 RFC (`RFC-1b` / E2.2) specifying `CanonicalAction`, `ActionDigest`, `RetryBinding`, `PendingApproval`, `TokenCheck` and `Grant` (`#214`, `#215`, `#219`) together with remaining `ActionPayload` variants (`#1602`).
2. Future wire-protocol RFC unreserving `grdr.embed.v1alpha1.Input` tags 3..5, `Output.decision` tag 6 and `Effect` tags 1..4 (`#381`) once out-of-process hosts need decision payloads over C ABI / Wasm.
3. Integration of `#22`'s shell wrapper recursion (`sudo`, `env`, `bash -c`) into `CommandInput` extraction cleanly for E2.1 / slice 1.

## Review

Revision 2 resolves Round 1 findings from `eval-review` and `eval-security` on PR `#2108` (`9b574ce16b6a0fda6748ae253e6cb0442b47e3ec`): adding `install_profile: InstallProfile` to `ModeContext`, removing unconstrained `user_local_time_lock` from `ModeRuleInput` and adding `ModeCompileError::ApproverBelowRule`, `InvalidSourceRuleId`, `InstanceIdOverLimit` and `MessageTokenKeyOverLimit`; adding `ExecActionRequest::new`, `ActionControlContext::new` and `ActionRequest::new` constructors; adding `Debug` across `Decision`, `ActionPayload`, `ActionControlContext`, `HostKind`, `PathClassifier`, `HostClassifier` and `CommandClassifier`; making `AnnotationParseError` a `#[non_exhaustive]` `Coded` + `LogSafe` enum (`GRDR-MODEL-0013`); verifying `ModeSourceRule.policy` annotations against `ModeRuleInput.meta` (`PolicyMetadataMismatch`); and clarifying unconditional `EXEC_OPAQUE` emission in `CommandOutcome::Unresolved`.

Drafted in `State: Review` against spine pin [`docs/design/00-decisions.md`](../docs/design/00-decisions.md) blob `a80859235e7a2a4444648d6fa8d389d78dde6be9` (`sha256` `8f6ea876777c0121ecec068c0bc4cef45932be45c1c2aff4140712db1e06628d`). Per [`.claude/risk-tiers.toml`](../.claude/risk-tiers.toml) (`[checklist_addons].rfc` and [ADR-0043](../docs/decisions/ADR-0043-lean-token-optimised-agent-team.md)), review proceeds on `#739` with `eval-review` and `eval-security` across two distinct models or providers, naming the reviewed RFC blob, proposed text/base pin, provider and model:
- `eval-review`: Pending Round 2 on `#739`.
- `eval-security`: Pending Round 2 on `#739`.

## Decision

Pending chief architect decision on `#739` following two-model evaluation under [RFC 0001](./0001-adopt-the-spine.md) and [ADR-0043](../docs/decisions/ADR-0043-lean-token-optimised-agent-team.md).
