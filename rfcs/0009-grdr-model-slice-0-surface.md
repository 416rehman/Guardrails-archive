RFC: 0009
Title: The slice-0 public surface of grdr-model: time, Entropy, ids, lanes, logging, the retry state types, InstallProfile and Tamper
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #1850
Spine: D-05, D-06, D-15, D-36, D-48, D-60, D-61, P1, P5, P8, P9, P14, P15, P17 (no spine text changes)
Surfaces: the public crate `grdr-model` (layer 1): `Timestamp`, `TimeError`, `Entropy`, `EntropyError`, `IdKind`, `MintRoute`, `IdError`, the typed ids, `Lane`, `UploadedLane`, `Epoch`, `Seq`, `OrderError`, `RetryPolicy`, `RetryPolicyError`, `RetryStep`, `GiveUp`, `AttemptCounter`, `RetryBudget`, `AttemptOutcome`, `Breaker`, `ProbeKind`, `Permit`, `CheckOutcome`, `LogSafe`, `LogValue`, `IdRef`, `WireName`, `EventName`, `FieldName`, `LogLevel`, `LogRecord`, the macros `wire_enum!`, `wire_name!`, `event_name!`, `field_name!` and `log_record!`, `InstallProfile` and `Tamper`; the error-code area `MODEL` with eleven codes. As proposals: one `[[crate]]` row of `surfaces.toml`, the `grdr-model` edges in `Cargo.toml` and `Cargo.lock`, sentences of design/03 section 10, design/04 sections 2 and 3, design/20 section 6 and design/21 sections 2 and 5. No wire format, Cedar schema or third-party dependency changes
Decision record: none yet

To comment, write on issue #1850 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

The text below is normative on its own. Where it differs from the items it covers (#383, #18, #282, #284), this RFC wins, and section 14 tells each lead what to write back (#1850 R4).

## Summary
Slice 0 adds the first public items to `grdr-model`: the wall-clock instant `Timestamp`, the `Entropy` trait, the typed ids and their one registry `IdKind`, the envelope's lane, epoch and sequence types, the retry state types that RFC 0008's executor drives, the `LogSafe` gate with its record and macros, and the install profile and tamper grade that `grdr-wire` reads. This RFC states every signature, error, code and stability class, answers the eight questions of #1850 and the three its comments add, and lists what each item and document changes.

The decisions that matter most:
- `Entropy::fill` returns a `Result`. A failed source is an error with a code, never bytes nobody drew. Minting returns the error, and `RetryPolicy::next` gives up with its own reason, so RFC 0008's `RetryError` does not change.
- A lane is `Lane::Uploaded(UploadedLane)` or `Lane::Local`. The server takes only `UploadedLane`, so no server type can hold `local`. A test with exhaustive matches both ways holds `Lane` and the protobuf enum to one definition.
- `RetryPolicy::from_limits(table, call)` is the one constructor and refuses a table whose peer kind differs from the call's.
- Only the organisation id and the delegation snapshot id can reach a log.
- Every public item has one path, at the crate root. The crate enters `surfaces.toml` as `experimental`.

## Motivation
#383, #18, #282 and #284 add these types, and RFC 0002 (#1688), RFC 0003 (#1757), RFC 0007 and RFC 0008 already use them. No RFC states their signatures. `grdr-model` is a public crate, so its surface changes only by RFC (D-61; the ruling on #1535), and RFC 0001 adopts the spine text and no crate surface. RFC 0007 section 1 gave this half of #1710's scope to #1850.

The texts disagree where a builder would turn the gap into a defect:
- RFC 0002 gives `Lane` four variants and design/04 section 2 five, with `local` among them.
- RFC 0002 mints `HolderId` "through grdr-model's id constructor" while the type lives in `grdr-ports`, and uses `DelegationSnapshotId`, `DelegationId` and `ProviderId`, which #383's table lacks.
- #282 calls the give-up reason `GiveUpReason` and RFC 0008 calls it `GiveUp`.
- #383's `Entropy::fill` cannot report a failure, and #334 must report one (lead-core, https://github.com/416rehman/Guardrails/issues/1850#issuecomment-7075943583).
- #284 makes every minted id loggable, and design/21 section 2 lets server logs carry the organisation id and the request id only.
- RFC 0007 lets a remote call read a `local` retry table and skip the remote floors (https://github.com/416rehman/Guardrails/issues/1850#issuecomment-7075275383).
- RFC 0008 section 8 lists nine changes it needs of these types (https://github.com/416rehman/Guardrails/issues/1850#issuecomment-7082237522).

#1850 blocks #18, and #18 blocks the Clock port (#281) on the path to the first runnable target (#645). If nothing changes, four implementers build against conflicting signatures and three RFCs keep pointing at types nobody has stated.

## Design

### 1. Scope and rules for every item
| Section | Items | Built by |
|---|---|---|
| 2 | `Timestamp`, `TimeError` | #383 |
| 3 | `Entropy`, `EntropyError` | #383 |
| 4 | `IdKind`, `MintRoute`, `IdError`, the typed ids | #383 |
| 5 | `Lane`, `UploadedLane`, `Epoch`, `Seq`, `OrderError` | the order item: a #18 sub-issue filed on acceptance (section 15) |
| 6 | `RetryPolicy`, `RetryPolicyError`, `RetryStep`, `GiveUp`, `AttemptCounter`, `RetryBudget`, `AttemptOutcome`, `Breaker`, `ProbeKind`, `Permit`, `CheckOutcome` | #282 |
| 7 | `LogSafe`, `LogValue`, `IdRef`, `WireName`, `EventName`, `FieldName`, `LogLevel`, `LogRecord`, the macros, and `LogSafe` for RFC 0007's `Code` and unit types | #284 |
| 8 | `InstallProfile`, `Tamper` | the install profile item, filed on acceptance (section 15) |

`Monotonic` is RFC 0008's (section 3 there) and is not restated. It takes this crate's stability class.

- R1. **Dependencies.** `grdr-model` depends on `grdr-schema` and on nothing else, for `Code`, `Coded`, `ErrorClass`, `ConnectCode`, `RetryLimits`, `RetryPeer`, `BudgetLimits`, the unit types and `RETRY_BOUNDS` (RFC 0007 sections 3 and 5). `grdr-proto` is a dev-dependency only, for the parity tests of section 5. No third-party dependency and no Cargo feature. Both edges go to layer 0 (design/03 section 2), and each changes `Cargo.lock`, a protected path, so they land as one protected change before #383 (section 15).
- R2. **Layer 1.** No I/O, async runtime, clock or randomness source: every instant and every draw is an argument (D-05, ARCH-003). The crate builds for `wasm32-unknown-unknown`. Arithmetic is checked or saturating (`#![deny(clippy::arithmetic_side_effects)]`), no non-test code has a panic path, and `unsafe` is forbidden.
- R3. **One path per item.** Every public type, trait and function is at the crate root, such as `grdr_model::Timestamp`, and the module that holds its source is private. The macros are `#[macro_export]`, so they are at the root too. RFC 0002, RFC 0003 and RFC 0008 already name root paths (`grdr_model::Monotonic`, `pub use grdr_model::Entropy`, `pub use grdr_model::{DelegationId, DelegationSnapshotId, OrgId, ProviderId}`), and a module path beside each would be a second way to name it (P17).
- R4. **No rendering.** The crate is `renders = "none"`. No type implements `Display`. Ids, lanes and enum words are read with `as_str`, and a person sees them only through a label of the presentation registry or as an argument of a language token (D-69, UX5, UX6), as RFC 0007 R4 has it for codes.
- R5. **One word list per enum.** Every closed enum whose values have wire words is declared with `wire_enum!` (section 7), which gives its variants, their words, `VARIANTS` and its `LogSafe` impl from one list. The words are wire identifiers, never display words.
- R6. **Errors.** Each error enum is `#[non_exhaustive]`, because callers act on the code's class and never on the variant (RFC 0002 Rule 8). Each implements RFC 0007's `Coded` with one exhaustive `match` and no wildcard arm, and a variant that wraps another coded error returns that error's code (RFC 0007 section 3). Each implements `LogSafe` as `LogValue::Code` of its code. The codes are section 9's.
- R7. **Format constants.** The numbers that define a format are not tunables (RFC 0007 R7): the range of `google.protobuf.Timestamp`, the 26-character id form and its prefix grammar, the 64-byte bound on names and words, and the first epoch and sequence number, 1. Every retry bound comes from the policy, which comes from a `limits.toml` table through `RetryLimits` (P14). No type here holds a tunable bound (ARCH-019).
- R8. **Data classes and assurance.** The ids are `identifier` (design/04 section 11). Every other type here is `structural`. Entropy output is never stored or logged except as the bits it gives an id. Assurance effect: none. No action class changes `visibility`, `control`, `on_failure` or `tamper` (P1); `Tamper` declares the grade's type and sets no grade.
- R9. **Scale.** No type makes a call or holds a queue (P15). An id holds its text, at most 30 bytes, allocated once when it is built. A `RetryBudget` holds `budget_slots` counters and `2 * breaker_failures` outcomes, fixed at construction and bounded by the `retry-bounds.slots-ceiling` and `retry-bounds.breaker-failures-ceiling` rows. A log record borrows the fields its call site writes.
- R10. **Derives.** Every public type implements `Debug` and derives what its block below writes. None has interior mutability, so every type is `Send + Sync`, as RFC 0008 change 7 needs.

### 2. Time (#383)
```rust
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Timestamp { /* private: seconds from 1970-01-01T00:00:00Z and nanoseconds, UTC */ }
impl Timestamp {
    pub const MIN: Timestamp; // 0001-01-01T00:00:00Z
    pub const MAX: Timestamp; // 9999-12-31T23:59:59.999999999Z
    pub const fn new(secs: i64, nanos: u32) -> Result<Timestamp, TimeError>;
    pub const fn secs(self) -> i64;
    pub const fn nanos(self) -> u32;
    pub fn checked_add(self, by: Duration) -> Option<Timestamp>;
    pub fn checked_sub(self, by: Duration) -> Option<Timestamp>;
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum TimeError { Seconds, Nanos }
```
- `Timestamp` is a UTC instant with the range of `google.protobuf.Timestamp` (#383 R1). `new` refuses `nanos` of 1,000,000,000 or more with `Nanos` and seconds outside the range with `Seconds`. Arithmetic that would leave the range returns `None`.
- It orders and compares, so an expiry check reads `now >= expires_at`, but nothing orders events by it: the order is epoch, lane and sequence (design/03 section 10, Time).
- Its uses fit: RFC 0002's `Date::from_timestamp` reads `secs`; a lease's `expires_at` and a token's expiry are `checked_add`; #1927 R5 clamps a system clock outside the range to `MIN` or `MAX`; `ManualClock::jump_wall` (RFC 0008 section 3) is `checked_add` or `checked_sub`; RFC 0008 constraint 2h reads `Clock::now()` as UTC.
- Errors: `TimeError`, `GRDR-MODEL-0001` and `GRDR-MODEL-0002`.

### 3. Entropy (#383; answer 9)
```rust
pub trait Entropy {
    fn fill(&mut self, out: &mut [u8]) -> Result<(), EntropyError>;
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum EntropyError { Unavailable }
```
- `fill` writes `out.len()` bytes drawn from its source and returns `Ok`, or returns `Err`. After `Err` the contents of `out` are unspecified and no caller reads them, so a partial fill is an `Err`, never a success. No implementation returns bytes its source did not produce, zeroed or repeated bytes included (RFC 0008 section 6).
- The trait has one required method, no provided method and no supertrait, and stays dyn-compatible: `Engine::step` takes `&mut dyn Entropy` (design/03 section 3), and RFC 0002 Rule 2 relies on it.
- Every function in this crate that draws takes `entropy: &mut R` with `R: Entropy + ?Sized`, so a caller may pass `&mut dyn Entropy`, `&mut (dyn Entropy + Send)` or a concrete type. RFC 0008's `run` holds `&mut R` with `R: Entropy + Send + ?Sized`, from which rustc cannot form a `&mut dyn Entropy` (E0277), so the generic form is what lets it reach `RetryPolicy::next` (RFC 0008 change 1). The bench of the Review section shows both.
- `grdr-model` implements `Entropy` for no type. Outside test code the implementations are those ARCH-003's list names: `grdr-crypto`'s `random` module and `grdr-ports-testkit` (RFC 0008 R3).
- `EntropyError` holds no data: a failed generator gives nothing structured, and a source's own message is not ours to carry. An implementation returns `EntropyError::Unavailable`.
- Errors: `EntropyError`, `GRDR-MODEL-0003`.

**Answer 9: `fill` is fallible.** lead-core offered three options:
1. `fill` returns a `Result`, and minting and `RetryPolicy::next` carry the failure. **Chosen.**
2. `fill` stays infallible over a source that latches its failure. After a failure the source must still write bytes into `out`, and it has none to give. Zeroed bytes make every full-jitter delay 0 and every key or nonce drawn from them all zeros (eval-security on #1924, https://github.com/416rehman/Guardrails/issues/1850#issuecomment-7076106123); repeated bytes are predictable. Rejected.
3. `fill` stays infallible behind a constructor that probes the source once. A failure after the probe leaves the same gap as option 2. Rejected.

What option 1 costs:
- Minting returns `IdError::Entropy` (section 4).
- `RetryPolicy::next` returns `GiveUp { reason: GiveUp::EntropyUnavailable, .. }` with the counter's ceiling as its backoff and `open_for` (section 6). That is RFC 0008's preferred form (its question 2), so `RetryError` does not change.
- `Engine::step` (#1537) and the daemon's decision ids (#1536) each state the outcome of a failed draw (section 14).

In the programs the source is `grdr_crypto::OsRandom` over aws-lc-rs (#334 R7, #1927 R11). AWS-LC documents that `RAND_bytes` calls `abort` when it cannot get enough random data (https://github.com/aws/aws-lc/blob/main/include/openssl/rand.h, read 2026-11-22), and aws-lc-rs's `fill` returns an error only when `RAND_bytes` does not return 1 (https://github.com/aws/aws-lc-rs/blob/main/aws-lc-rs/src/rand.rs, read 2026-11-22). So on the programs' path a generator failure ends the process inside the library before `fill` returns, and `OsRandom`'s `Err` branch maps the library's result type. The trait still carries the failure, because another source, such as a host's generator behind `grdr-ffi` or `grdr-wasm`, can fail and return. Section 14 lists what #334 states about the abort.

### 4. Ids (#383; answers 1 and 2)
```rust
#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum IdKind {
    Event, Session, ToolCall, Action, Decision, Incident, OperatorAccount, Grant, DelegationSnapshot,
    Org, RetryToken, Provider, Delegation, Holder,
    Device, HumanPrincipal, ServicePrincipal, AgentIdentity, AgentInstance, McpServer, McpTool,
    Skill, Plugin, ModelEndpoint, CredentialRef, Process, Flow, Finding,
}
impl IdKind {
    pub const VARIANTS: &'static [IdKind];
    pub const fn prefix(self) -> &'static str; // "evt"
    pub const fn route(self) -> MintRoute;
    pub const fn loggable(self) -> bool;
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum MintRoute { Uuid7, Random128, Derived128 }

// Every typed id but PrincipalId has this shape. EventId stands for each.
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct EventId { /* private: its text */ }
impl EventId {
    pub const KIND: IdKind = IdKind::Event;
    pub fn from_wire(text: &str) -> Result<EventId, IdError>;
    pub fn as_str(&self) -> &str;
    // One constructor, by the kind's route:
    pub fn mint<R: Entropy + ?Sized>(now: Timestamp, entropy: &mut R) -> Result<EventId, IdError>; // Uuid7
}
// Random128:  pub fn mint<R: Entropy + ?Sized>(entropy: &mut R) -> Result<OrgId, IdError>;
// Derived128: pub fn derive(digest: [u8; 16]) -> DeviceId;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PrincipalId { /* private: its text */ }
impl PrincipalId {
    pub fn human(digest: [u8; 16]) -> PrincipalId;          // prn_
    pub fn service(digest: [u8; 16]) -> PrincipalId;        // svc_
    pub fn agent_identity(digest: [u8; 16]) -> PrincipalId; // aid_
    pub fn from_wire(text: &str) -> Result<PrincipalId, IdError>;
    pub fn kind(&self) -> IdKind;
    pub fn as_str(&self) -> &str;
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum IdError { Form, TimeOutOfRange, Entropy(EntropyError) }
```

| `IdKind` | Prefix | Route | Type | Defined by | Loggable |
|---|---|---|---|---|---|
| `Event` | `evt` | `Uuid7` | `EventId` | design/04 section 2 | no |
| `Session` | `ses` | `Uuid7` | `SessionId` | design/04 section 3 | no |
| `ToolCall` | `tc` | `Uuid7` | `ToolCallId` | design/04 section 3 | no |
| `Action` | `act` | `Uuid7` | `ActionId` | design/04 section 3 | no |
| `Decision` | `dec` | `Uuid7` | `DecisionId` | design/04 section 3 | no |
| `Incident` | `inc` | `Uuid7` | `IncidentId` | design/04 section 3 | no |
| `OperatorAccount` | `opa` | `Uuid7` | `OperatorAccountId` | design/04 section 3 | no |
| `Grant` | `grt` | `Uuid7` | `GrantId` | design/12 section 6 | no |
| `DelegationSnapshot` | `dls` | `Uuid7` | `DelegationSnapshotId` | design/21 section 5 (answer 1) | yes |
| `Org` | `org` | `Random128` | `OrgId` | design/04 section 3 | yes |
| `RetryToken` | `rty` | `Random128` | `RetryTokenId` | design/12 section 6 | no |
| `Provider` | `prv` | `Random128` | `ProviderId` | design/21 section 1 | no |
| `Delegation` | `dlg` | `Random128` | `DelegationId` | design/21 section 5 | no |
| `Holder` | `hld` | `Random128` | `HolderId` | RFC 0002 section 7 (answer 2) | no |
| `Device` | `dev` | `Derived128` | `DeviceId` | design/04 section 3 | no |
| `HumanPrincipal`, `ServicePrincipal`, `AgentIdentity` | `prn`, `svc`, `aid` | `Derived128` | `PrincipalId` | design/04 section 3 | no |
| `AgentInstance` | `agi` | `Derived128` | `AgentInstanceId` | design/04 section 3 | no |
| `McpServer`, `McpTool` | `mcp`, `mct` | `Derived128` | `McpServerId`, `McpToolId` | design/04 section 3 | no |
| `Skill`, `Plugin` | `skl`, `plg` | `Derived128` | `SkillId`, `PluginId` | design/04 section 3 | no |
| `ModelEndpoint` | `mdl` | `Derived128` | `ModelEndpointId` | design/04 section 3 | no |
| `CredentialRef` | `crd` | `Derived128` | `CredentialRefId` | design/04 section 3 | no |
| `Process`, `Flow`, `Finding` | `prc`, `flw`, `fnd` | `Derived128` | `ProcessId`, `FlowId`, `FindingId` | design/04 section 3 | no |

Form and minting, as #383 R5 to R10 state them, with these changes:
- The text is `<prefix>_` and 26 lower-case Crockford base32 characters, two zero bits in front of the 128 bits, so the first character is `0` to `7` and the order of two ids of one kind is the order of their bytes (#383 R8). The alphabet has no `/`, `=` or `.`, so `org=<id>/` keeps listings apart (RFC 0002 section 15).
- `from_wire` accepts exactly that form for its kind and refuses anything else with `Form`; it checks form and decodes nothing (#383 R9). `PrincipalId::from_wire` accepts any of its three prefixes, and `kind` reads the prefix.
- `Uuid7` minting draws 10 bytes in one `fill` and builds RFC 9562 section 5.7's layout from `now`'s Unix milliseconds (#383 R5). A `now` before 1970 is `TimeOutOfRange`; `Timestamp::MAX` is below 2^48 milliseconds, so no later `now` can be. `Random128` draws 16 bytes in one `fill` and uses them as they are. `Derived128` takes the caller's 16 bytes, a digest that `grdr-crypto` computed and truncated (ARCH-006), and draws nothing. A failed draw returns `IdError::Entropy` and builds no id.
- No method returns an id's bits, its time or its random part. No id implements `Display` (R4). Ids are `Clone`, not `Copy`, because each holds its text so `as_str` is total: an inline ASCII buffer would need a fallible conversion to `&str`, and `core::ascii::Char` is unstable on the pinned 1.99.1 (the bench).
- Errors: `IdError`, `GRDR-MODEL-0004` and `GRDR-MODEL-0005`; `Entropy` returns `GRDR-MODEL-0003`.

The id table is one macro list in `grdr-model`: one entry per kind with its variant, prefix, route, newtype and whether it is loggable, from which `IdKind`, `VARIANTS`, `prefix`, `route`, `loggable` and each newtype with exactly the shape above are generated. A new row is content of this mechanism, as a code is content of RFC 0007's registry: the item that defines the id adds one entry and its pull request names RFC 0009 for `rfc-required`. A new prefix fits `[a-z]{2,3}`, is unique, and is not `agt`, which agent type ids hold (design/04 section 3). A new row is not loggable: making a kind loggable widens what logs carry (P8), so it is an amendment. `IdKind` is `#[non_exhaustive]`, so a new row breaks no match outside the crate.

**Answer 1: `DelegationSnapshotId` is `dls_`, minted as UUIDv7.** The token exchange writes a delegation snapshot at every workbench exchange (design/21 section 5), and a time-ordered key keeps that table's index append-mostly. `DelegationId` (`dlg_`) and `ProviderId` (`prv_`, which design/21 section 1 already names) are `Random128`, like `OrgId`: long-lived tenancy objects whose ids need no time. All three are minted by the server's tenancy code from its clock and entropy (ARCH-020).

**Answer 2: the id moves; the capability stays.** `HolderId` becomes a `grdr-model` id, `hld_`, `Random128`: it names one process start, needs no time and needs 128 random bits so two processes never share one. RFC 0002's capability stays in `grdr-ports` under the name `Holder`, holding a `HolderId`, and only `Setup` and the kit's handle build one, so holding an id builds nothing (RFC 0002 section 7). Leases take `&Holder`, and an adapter stores the holder's `id().as_str()`. Minting through grdr-model's constructor keeps ARCH-020; keeping the capability in `grdr-ports` keeps RFC 0002's rule that only the composition root makes one. The rename keeps one name per type: two crates each stating a `HolderId` would be the clash #1710 AC-3 refuses.

### 5. Lanes, epochs and sequence numbers (#18; answers 3 and 4)
```rust
wire_enum! {
    pub enum UploadedLane { Decision => "decision", Spine => "spine", Bulk => "bulk", Evidence => "evidence" }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Lane { Uploaded(UploadedLane), Local }
impl Lane {
    pub const VARIANTS: &'static [Lane]; // the four uploaded lanes in order, then Local
    pub const fn as_str(self) -> &'static str; // "decision", "spine", "bulk", "evidence", "local"
    pub const fn wire_name(self) -> WireName;
    pub const fn number(self) -> i32; // 1 to 5, the protobuf enum's numbers
    pub const fn from_number(number: i32) -> Result<Lane, OrderError>;
    pub const fn uploaded(self) -> Result<UploadedLane, OrderError>;
}
impl From<UploadedLane> for Lane;
// Lane implements LogSafe as its word.

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Epoch { /* private: a non-zero u32 */ }
impl Epoch {
    pub const FIRST: Epoch; // 1
    pub const fn new(value: u32) -> Result<Epoch, OrderError>;
    pub const fn get(self) -> u32;
    pub const fn next(self) -> Option<Epoch>;
}
// Seq has the same shape over a non-zero u64. Both implement LogSafe as their number.

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum OrderError { LaneUnspecified, LaneUnknown { number: i32 }, LaneNotUploaded, EpochZero, SeqZero }
```

**Answer 3: one `Lane` type of five lanes, with the four that leave the device as a type of their own.** design/04 section 2 has five lanes and the envelope's `lane` is a protobuf enum of five values (#394 R3). The daemon stamps `local` records with their own sequence and hash chain, so it needs all five. `local` is never uploaded, so the server never holds one: RFC 0002's `OrgWork::Ingest`, `StorageClass::Archive`, `ArchiveBatch` and `RowPosition` take `UploadedLane`, and none of them can name `local`. Ingest refuses a `local` record once, where it decodes the lane (`Lane::from_number(n)?.uploaded()?`), instead of in every server match. Each lane and its word is declared once: the four in `UploadedLane`'s list and `local` in `Lane`. RFC 0002's "there is no second lane enum" holds in that sense, and its four uses change (section 14).

The protobuf enum and `Lane` stay one definition through a test, `crates/grdr-model/tests/lane_wire.rs`, with `grdr-proto` as a dev-dependency (R1):
- two functions match exhaustively, with no wildcard arm, from `Lane` to the generated enum and from the generated enum to `Option<Lane>`, so a value added on either side fails to compile until the other side has it. In the bench, adding a sixth value to a generated enum of prost's shape fails the test's build with E0004;
- for every `Lane`, the generated value's number equals `number()`, `from_number` returns the lane, both conversions round-trip, and the value's `wire_name` option, read from the descriptor set #17 generates, equals `as_str()`;
- `LANE_UNSPECIFIED` is `LaneUnspecified`, a number no value has is `LaneUnknown { number }`, and `Lane::Local.uploaded()` is `LaneNotUploaded`.

Generation was the other mechanism AC-4 allows. It would need a `.proto` reader in a test or `grdr-model` depending on `grdr-proto` in its normal closure, which ties this crate's API to the codec SP-1 has not chosen yet (Alternatives). The numbers are wire format, which `buf breaking` already keeps from changing, so holding them in a test costs little.

**Answer 4: `Epoch` is a non-zero `u32`, `Seq` a non-zero `u64`, `DeviceId` a `Derived128` id.** The envelope carries `uint32 epoch` and `uint64 seq` (design/04 section 1). In proto3 a zero scalar is indistinguishable from an absent field, so 0 is refused: `seq` starts at 1 per epoch and lane (design/04 section 2), and the epoch counter starts at 1 too (section 14). `next` returns `None` at the type's maximum, and its caller maps that to its own code: the daemon cannot start a new epoch, and a lane cannot take another record in this epoch. `DeviceId` is `dev_` over the 16-byte digest of the device's public key (design/04 section 3). RFC 0002's `RowPosition { observed_time: Timestamp, device_id: DeviceId, epoch: Epoch, monotonic_ns: u64, lane: UploadedLane, seq: Seq }` fits these types. `monotonic_ns` stays a `u64`: it is the device's reading in another process, and RFC 0008 section 3 never compares instants of two processes.

Errors: `OrderError`, `GRDR-MODEL-0007` to `GRDR-MODEL-0011`.

### 6. The retry state types (#282; answers 5, 6, 10 and 11)
```rust
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RetryPolicy { /* private: the RetrySpec of one RetryLimits */ }
impl RetryPolicy {
    pub fn from_limits(limits: &RetryLimits, call: RetryPeer) -> Result<RetryPolicy, RetryPolicyError>;
    pub fn next<R: Entropy + ?Sized>(
        &self, counter: AttemptCounter, retries: u32, elapsed: Duration, hint: Option<Duration>, entropy: &mut R,
    ) -> RetryStep;
    pub fn at_cap(&self, counter: AttemptCounter) -> bool;
    pub fn peer(&self) -> RetryPeer;
    pub fn timeout(&self) -> Duration;
    pub fn cap(&self) -> Duration;
    pub fn budget(&self) -> BudgetLimits;
    pub fn breaker_failures(&self) -> u32;
}
#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RetryPolicyError { PeerMismatch { table: RetryPeer, call: RetryPeer } }

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct AttemptCounter { /* private: u32 */ }
impl AttemptCounter {
    pub const fn new(value: u32) -> AttemptCounter;
    pub const fn get(self) -> u32;
    pub const fn next(self) -> AttemptCounter; // saturating
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RetryStep {
    Delay { delay: Duration, open_for: Duration },
    GiveUp { reason: GiveUp, backoff: Duration, open_for: Duration },
}
wire_enum! {
    pub enum GiveUp { MaxAttempts => "max_attempts", MaxElapsed => "max_elapsed", EntropyUnavailable => "entropy_unavailable" }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RetryBudget { /* private: the slot counters and the recent outcomes */ }
impl RetryBudget {
    pub fn new(policy: &RetryPolicy, registered: &RetryLimits) -> RetryBudget;
    pub fn record_request(&mut self, now: Monotonic);
    pub fn try_spend(&mut self, now: Monotonic) -> bool;
    pub fn record_attempt(&mut self, outcome: AttemptOutcome);
    pub fn failure_share(&self) -> Permille;
}
wire_enum! { pub enum AttemptOutcome { Succeeded => "succeeded", Failed => "failed" } }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Breaker {
    Closed { consecutive_failures: u32, quiet_until: Option<Monotonic> },
    Checking { check_until: Monotonic },
    Open { until: Monotonic, unhealthy_probes: u32, turn_until: Option<Monotonic> },
    HalfOpen { probe_until: Monotonic, probe: ProbeKind, unhealthy_probes: u32, turn_until: Option<Monotonic> },
}
impl Breaker {
    pub const CLOSED: Breaker; // Closed { consecutive_failures: 0, quiet_until: None }
    pub fn peek(&self, now: Monotonic, policy: &RetryPolicy) -> Permit;
    pub fn permit(self, now: Monotonic, policy: &RetryPolicy) -> (Breaker, Permit);
    pub fn unanswered(self, now: Monotonic, open_for: Duration) -> Breaker;
    pub fn record_success(self, now: Monotonic, policy: &RetryPolicy) -> Breaker;
    pub fn record_failure(self, now: Monotonic, policy: &RetryPolicy) -> (Breaker, Option<Monotonic>);
    pub fn record_check(self, started: Breaker, outcome: CheckOutcome, now: Monotonic, open_for: Duration, policy: &RetryPolicy) -> Breaker;
    pub fn release(self, started: Breaker, now: Monotonic, policy: &RetryPolicy) -> Breaker;
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Permit { Call, Probe(ProbeKind), Refuse { until: Monotonic }, Unanswered }
wire_enum! { pub enum ProbeKind { Health => "health", Call => "call" } }
wire_enum! { pub enum CheckOutcome { Healthy => "healthy", Unhealthy => "unhealthy", Inconclusive => "inconclusive" } }
```
`RetryLimits`, `RetryPeer`, `BudgetLimits`, `Permille` and `RETRY_BOUNDS` are RFC 0007's (`grdr_schema::limits`). `Monotonic` is RFC 0008's.

**`RetryPolicy`.**
- `from_limits` copies one checked table and is the only constructor; the fields are private, so a struct expression outside the crate fails (E0451). There is no `#[cfg(test)]` constructor. Product code reads a registered table, or a table RFC 0007's `narrow` built from one, and tests build tables with `RetryLimits::new`, which ARCH-019 keeps to test code (RFC 0007 sections 5 and 8). **Answer 6.**
- **Answer 10, the peer kind.** The caller passes `call`, the peer kind of the call it builds the policy for, and `from_limits` refuses a table whose `peer` differs, either way, with `PeerMismatch { table, call }`. The call's peer kind comes from the port that makes the call, at construction: `grdr-uplink`'s classes pass `RetryPeer::Remote`; an adapter's set-up passes the kind of the back end it resolved from its configuration, `Local` for one on this machine and `Remote` for any other, and reads the registered table of that kind. A compile-time check cannot hold this, because RFC 0007's generated tables are one type whatever their peer, and an adapter's back end is configuration. The error is class `internal`, because the code that picked the table is wrong, and the caller's rule class decides the outcome (D-15): at set-up the construction fails with the code (RFC 0008 section 6). #282's tests include a remote call given a `local` table and a local call given a `remote` table.
- `next` is #282 R2 to R7 with these changes:
  - It takes two counts (RFC 0008 change 2): `counter`, the class's attempt counter before this failure is counted, sets the delay ceiling (#282 R3 and R4, with `counter.get()` in place of `attempt`), and `retries`, the run's own retries so far, is what the `MaxAttempts` check reads (`retries + 2 > max_attempts`).
  - A schedule's delay `d` is a draw in `[d - d * jitter / 1000, d]` (RFC 0007 section 5).
  - A hint `h` is first raised to `RETRY_BOUNDS.hint_floor`, and the delay is the larger of the backoff draw and `h + U(0, h)` (RFC 0007 section 5; #282 R5 as #282's first comment asks).
  - A uniform draw in `[0, m]` reads one `u64` as `u64::from_le_bytes` of 8 bytes from one `fill`, and returns `(r * (m + 1)) >> 64` in `u128` (#282 R6), so a seed gives the same delays on every target.
  - Each step carries `open_for`, the smaller of its delay, or a give-up's `backoff`, and the counter's ceiling (RFC 0008 change 3). With no hint `open_for` equals the delay, so #282's vectors hold.
  - A failed draw returns `GiveUp { reason: EntropyUnavailable, backoff: c, open_for: c }`, where `c` is the counter's ceiling, whatever else applies, so a failed source always shows as its own reason (answer 9).
  - Every sum saturates, so a counter of `u32::MAX` or a hint of `u64::MAX` milliseconds gives a ceiling at the cap and never panics.
- `at_cap(counter)` says the counter's ceiling has reached the cap. `timeout`, `cap` (the exponential cap or a schedule's last delay), `budget` and `breaker_failures` are what the executor, `for_class` and `set_policy` read (RFC 0008 change 4).
- Errors: `RetryPolicyError`, `GRDR-MODEL-0006`.

**Answer 5: the give-up reason is `GiveUp`.** RFC 0008, decided, writes `RetryError::GaveUp { reason: GiveUp, .. }`, and `GiveUpReason` would amend it for a name. `RetryStep::GiveUp { reason: GiveUp }` names the variant and the type alike, as RFC 0008 already reads. It derives what `wire_enum!` gives, `Clone`, `Copy`, `Debug`, `PartialEq`, `Eq` and `Hash`, and is `LogSafe` (RFC 0008 change 7).

**`RetryBudget`.** One budget serves one class (RFC 0008 R9).
- `new` takes the allowance's fields from `policy.budget()`, which RFC 0007's rules have checked, so no caller can build a budget from unchecked fields. `record_request` and `try_spend` are #282 R8.
- `record_attempt` records the outcome of each attempt of the class, first or retry, in order, and keeps the last `2 * breaker_failures` of them. `failure_share` is the failed share of those as a `Permille`, and 0 until that many are recorded. `breaker_failures` is that of `registered`, the class's registered table, so a narrowed table, whose `breaker_failures` may only fall, cannot shorten the window. This is constraint 1d (`Permille`) and constraint 1f of RFC 0008's decision, which has this RFC follow #1966 R2 (the share over the last `2 * breaker_failures` attempts, not over the budget's time window). If #1966 is decided otherwise, this RFC follows it (Unresolved questions).
- Errors: none. `try_spend` returning `false` is the refusal, which the executor reports as `BudgetExhausted` (RFC 0008 section 4).

**`Breaker`.** One class's breaker, with the four states of RFC 0008 change 5. `quiet_until` and `turn_until` are `None` outside a quiet period or a call-probe turn, so no instant stands for "none". Every instant `now + d` that would pass the largest `Monotonic` is the largest (RFC 0008 section 4). The methods consume the state and return the next one (design/03 section 10, State machines):

| Method | Transition | RFC 0008 change 5 row |
|---|---|---|
| `peek` | What `permit` would return at `now`, with no transition | change 6 |
| `permit` | `Closed` and `Checking`: unchanged, `Call`. `Open` before `until`: `Refuse { until }`. `Open` at or after `until`: `HalfOpen` with `probe_until` at `now` plus the call timeout, and `Probe(kind)`, where `kind` is `Call` once `unhealthy_probes` has reached `breaker_failures` and `Health` otherwise; the first call probe of a turn sets `turn_until` to `now` plus the cap, and a permit at or after `turn_until` is a `Health` probe with `unhealthy_probes` at 0 and no turn. `HalfOpen` before `probe_until`: `Refuse { until: probe_until }`. `HalfOpen` at or after `probe_until`: unchanged, `Unanswered`, and the caller draws a step and calls `unanswered` | `Open` at `until` and a permit |
| `unanswered` | `HalfOpen { probe: Health }` becomes `Open` until `now + open_for` with one more unhealthy probe; `HalfOpen { probe: Call }` becomes `Open` until `now + open_for` with no unhealthy probes and no turn; any other state is unchanged. The permit is refused | `HalfOpen` at or after `probe_until` and a permit |
| `record_success` | `Closed`: count to 0. `Checking` and `HalfOpen`: `Closed` with the count at 0 and `quiet_until` at `now` plus the call timeout. `Open`: `until` at the earlier of `until` and `now` | `Checking` and a success; `Open` and a late success; `HalfOpen` and a late success |
| `record_failure` | `Closed`: count one more, saturating, and at `breaker_failures` outside the quiet period move to `Checking` with `check_until` at `now` plus the call timeout. `Checking` before `check_until`: unchanged; at or after it, a new `Checking`. `Open`, `HalfOpen`: unchanged. The second value is the new `check_until` when a check starts, so the run that recorded the failure makes the health call | `Closed` and a recorded failure; `Checking` and a recorded failure; `Open` and a late failure; `HalfOpen` and a recorded failure |
| `record_check` | Applies only if the breaker still equals `started`, the state the check or probe began from; otherwise unchanged. `Checking`: `Healthy` closes with the count at 0 and a quiet period, `Unhealthy` opens until `now + open_for` with no unhealthy probes. `HalfOpen { probe: Health }`: `Healthy` closes the same way, `Unhealthy` opens until `now + open_for` with one more unhealthy probe. `HalfOpen { probe: Call }`: `Healthy`, a `Done`, closes; `Unhealthy`, a peer failure or the cutoff, opens until `now + open_for` with no unhealthy probes and no turn; `Inconclusive`, an error the peer did not cause, is `Open { until: now }` with the unhealthy probes and the turn as they were. `Inconclusive` leaves every other state unchanged; a health call is never inconclusive, because only `Ok` is healthy (RFC 0008 R13) | `Checking` and a verdict; `HalfOpen` and a verdict, of either kind; `HalfOpen { probe: Call }` and no verdict |
| `release` | Applies only if the breaker still equals `started`. `HalfOpen`: `Open` until `now` plus the call timeout, with the unhealthy probes and the turn as they were. `Checking`: `Closed` with the count one below `breaker_failures` and `quiet_until` at `now` plus the call timeout | `release` of an abandoned probe or check |

`Open` is left only through `HalfOpen` (#282 AC-4). `CheckOutcome` names the result of a check or a probe; the spine's *Verdict* is a decision's (spine section 3), so the type does not borrow the word. Errors: none.

**Answer 11: what RFC 0008 section 8 needs.**
| RFC 0008 change | Where it is met |
|---|---|
| 1. `next` takes `&mut R` for any `R: Entropy + ?Sized` | `RetryPolicy::next` |
| 2. Two counts; `AttemptCounter` with `new`, `get`, saturating `next`, its derives and `LogSafe` | `next`'s `counter` and `retries`; `AttemptCounter`, `LogSafe` in section 7 |
| 3. `open_for` on each step | `RetryStep` |
| 4. The policy's timeout, cap, budget fields, `breaker_failures` and `at_cap`; the budget's failure count and share | `RetryPolicy`; `RetryBudget::record_attempt` and `failure_share`, as `Permille` (constraint 1d) and per attempt (constraint 1f) |
| 5. Four states with the probe's state in them, every row | `Breaker` and its methods |
| 6. A permit's answer without a transition | `Breaker::peek` |
| 7. `Send + Sync`; `Clone` and `Debug`; the derives of `Breaker`, `ProbeKind` and the give-up reason | R10; the blocks above |
| 8. `RetryState::new(policy, clock, entropy, health)` with the policy by value | `RetryPolicy` is `Copy` |
| 9. A failed draw | Answer 9: `GiveUp::EntropyUnavailable`; `RetryError` unchanged |

### 7. Logging (#284; answer 7)
```rust
pub trait LogSafe { fn log_value(&self) -> LogValue<'_>; }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LogValue<'a> {
    Bool(bool),
    U64(u64),
    I64(i64),
    Bytes(Bytes),       // grdr_schema::limits::Bytes
    Permille(Permille), // grdr_schema::limits::Permille
    Duration(Duration),
    Timestamp(Timestamp),
    Monotonic(Monotonic),
    Enum(WireName),
    Code(Code),         // grdr_schema::codes::Code
    Id(IdRef<'a>),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct IdRef<'a> { /* private: the kind and the id's text */ }
impl<'a> IdRef<'a> {
    pub const fn kind(&self) -> IdKind;
    pub const fn as_str(&self) -> &'a str;
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct WireName { /* private: &'static str */ }
impl WireName {
    pub const fn new(text: &'static str) -> Option<WireName>; // [a-z][a-z0-9_.-]*, at most 64 bytes
    pub const fn as_str(self) -> &'static str;
}
// EventName and FieldName have the same shape, with the grammar [a-z][a-z0-9_.]*, at most 64 bytes.

wire_enum! { #[derive(PartialOrd, Ord)] pub enum LogLevel { Debug => "debug", Info => "info", Warn => "warn", Error => "error" } }

#[derive(Clone, Copy, Debug)]
pub struct LogRecord<'a> { /* private: the level, the event and the fields */ }
impl<'a> LogRecord<'a> {
    pub const fn new(level: LogLevel, event: EventName, fields: &'a [(FieldName, LogValue<'a>)]) -> LogRecord<'a>;
    pub const fn level(&self) -> LogLevel;
    pub const fn event(&self) -> EventName;
    pub const fn fields(&self) -> &'a [(FieldName, LogValue<'a>)];
}

// The macros, at the crate root:
//   wire_enum! { $(#[$meta])* $vis enum Name { Variant => "word", ... } }
//   wire_name!("word"), event_name!("session.start"), field_name!("retry.attempts")
//   log_record!(level, EVENT, "field.name" => value, ...)
```

The gate. A value reaches a log only as a `LogValue`, and no variant carries free text or raw bytes: numbers, durations, instants, a `WireName`, a `Code` or an `IdRef`.
- `WireName` is the only text, and its grammar refuses a path, a URL, a command line, a host name, an address, an upper-case word and anything longer than 64 bytes. A single lower-case word still passes, so the grammar is a tripwire, and review holds the rest: a `LogSafe` impl outside this crate builds its value from the `LogSafe` values of its own fields, as RFC 0002's contexts return their organisation id's, and `eval-security` reads every new impl.
- `IdRef` has no public constructor. It is built only by the `LogSafe` impls of the ids whose kind is loggable, so a struct expression of it fails (E0451) and no other id reaches a log.
- `LogValue` is exhaustive, so a variant added by amendment fails every sink's build until the sink formats it.

`LogSafe` is implemented for:
- `bool`; `u8`, `u16`, `u32`, `u64` and `usize` as `U64`, and `i8` to `i64` and `isize` as `I64`, saturating (no supported target has a `usize` wider than 64 bits, so the saturation never applies there);
- `Duration`, `Timestamp`, `Monotonic`, `AttemptCounter`, `Epoch` and `Seq`;
- every `wire_enum!` type, and `Lane`, as `Enum` of the word;
- `OrgId` and `DelegationSnapshotId`, as `Id`;
- every error enum of this crate, as `Code` (R6);
- RFC 0007's `Code` as `Code`, `Bytes` as `Bytes`, `Count` as `U64`, `Millis` as `Duration` and `Permille` as `Permille`;
- `&T` where `T: LogSafe + ?Sized`.

It is implemented for no text type (`str`, `String`, `char`), no byte type (`[u8]`, `[u8; N]`, `Vec<u8>`), no path or OS string, no generic container (`Option`, `Result`, `Vec`), no id of a kind that is not loggable, and nothing that holds entropy output (#284 R2 and R8). A program that needs to correlate a raw identifier or a content value logs its keyed digest once that type exists, never the value or a bare hash of it.

**Answer 7, which ids are `LogSafe` and how a `Code` logs.**
- Two kinds are loggable: `Org` and `DelegationSnapshot`. design/21 section 2 lets server logs carry the organisation id and the request id only, and RFC 0002's contexts log only their organisation id or snapshot id. Every other kind names a person, a device, or something one person did, and a log line that carried one would be a per-person record outside the event stream's data classes and retention (P8). A diagnostic that needs to point at a record points at its `(epoch, lane, seq)`, which is structural. The request id joins when its id row is added, by amendment, as any loggable kind does.
- `LogValue::Id(IdRef)` carries the kind and the text, so a sink can label the field; the data class stays `identifier`.
- A `Code` logs as `LogValue::Code(code)`, and a sink writes its `as_str()`, never a token id or a message (RFC 0007 section 3).

The macros:
- `wire_enum!` declares a fieldless enum from one list of variants and words, deriving `Clone`, `Copy`, `Debug`, `PartialEq`, `Eq` and `Hash`, with any further derives the caller writes, and gives `VARIANTS`, `as_str`, `wire_name` and the `LogSafe` impl. A variant with a field does not match the macro's grammar and fails to compile, and a word outside `WireName`'s grammar fails in a `const` item (E0080). It replaces #284's `log_enum!`, whose separate list of words would be a second home for them (R5).
- `wire_name!`, `event_name!` and `field_name!` check their literal in a `const` item, so a name outside the grammar fails compilation (E0080) and no check runs at run time. Clippy with the workspace deny list passes over the expansion, the `panic!` in the `const` item included (the bench).
- `log_record!(level, EVENT, "name" => value, ...)` builds the field array, calls `log_value()` on each value and returns a `LogRecord`. A field name is a string literal, because a name may hold dots. A value whose type is not `LogSafe` fails at the call site (E0277). The record borrows an array of temporaries, so it lives for the statement that writes it: `sink.write(&log_record!(..))`. Keeping it in a `let` fails (E0716).
- Formatting a record and writing it to the operating-system log or a file are the programs' (#284 R7).

`LogValue::Digest([u8; 32])` (#284 R1) is not in slice 0. No type yields it yet (#284 R2), and a public variant holding 32 bytes would let any impl log a bare hash. Design/04 work item 04-16 adds the keyed digest type, and the variant with it, by amendment. `Level` is named `LogLevel`, because R3 puts every item at the crate root and `grdr_model::Level` would not say which level.

Errors: none. Every check here is at compile time.

### 8. InstallProfile and Tamper (answer 8)
```rust
wire_enum! { pub enum InstallProfile { Protected => "protected", User => "user" } }
wire_enum! { #[derive(PartialOrd, Ord)] pub enum Tamper { User => "user", Admin => "admin", Platform => "platform" } }
```
**Answer 8: the paths are `grdr_model::InstallProfile` and `grdr_model::Tamper`** (R3).
- `InstallProfile` is D-48's choice at install, read from install state and never from configuration (RFC 0003 section 6).
- `Tamper` is the assurance record's tamper grade (spine section 3). It is ordered by grade, `User < Admin < Platform`, so a rule that asks for at least `admin` reads `>=`.
- RFC 0003's uses fit: `peer_auth::resolve(spec, profile: InstallProfile, user)` gives `Tamper::Admin` for `Protected` and `Tamper::User` for `User`, and `EndpointIdentity::tamper() -> Tamper`.
- A protobuf or Cedar twin, when the assurance package or the configuration schema declares one, is held to the Rust type by a test of section 5's form, which the item that declares the twin adds.
- Errors: none. Both are `structural`.

### 9. Error codes
The area `MODEL` is `grdr-model`'s: subsystem "the domain types of grdr-model", owner `design/03`. This RFC assigns the codes (RFC 0007 section 4), and each item registers the codes it first constructs in `schema/codes/model.toml` and writes their source-locale tokens. Numbers may land out of order; the registry refuses a repeated number, not a gap.

| Code | Reason | Class | Connect | Bound by | Registered by | Next step (`code.<code>.fix`) |
|---|---|---|---|---|---|---|
| `GRDR-MODEL-0001` | `TIMESTAMP_SECONDS_OUT_OF_RANGE` | input | `invalid_argument` | `TimeError::Seconds` | #383 | A time falls outside 0001-01-01 to 9999-12-31 UTC. Check the clock or the record that gave it |
| `GRDR-MODEL-0002` | `TIMESTAMP_NANOS_OUT_OF_RANGE` | input | `invalid_argument` | `TimeError::Nanos` | #383 | A time's nanoseconds are a whole second or more. Check the record that gave it |
| `GRDR-MODEL-0003` | `ENTROPY_UNAVAILABLE` | fatal | `internal` | `EntropyError::Unavailable`; `IdError::Entropy` | #383 | The random source failed, so nothing that needs randomness ran. Check the host's random source, then collect a support bundle |
| `GRDR-MODEL-0004` | `ID_FORM` | input | `invalid_argument` | `IdError::Form` | #383 | An id is not a known prefix, `_` and 26 base32 characters. Check the record or request that carried it |
| `GRDR-MODEL-0005` | `ID_TIME_OUT_OF_RANGE` | fatal | `failed_precondition` | `IdError::TimeOutOfRange` | #383 | The clock reads a time before 1970, so no time-ordered id can be made. Set the system clock |
| `GRDR-MODEL-0006` | `RETRY_PEER_MISMATCH` | internal | `internal` | `RetryPolicyError::PeerMismatch` | #282 | A retry table was read for a call to the other kind of peer. This is a defect; collect a support bundle |
| `GRDR-MODEL-0007` | `LANE_UNSPECIFIED` | input | `invalid_argument` | `OrderError::LaneUnspecified` | the order item | A record names no lane. Check the version of the component that sent it |
| `GRDR-MODEL-0008` | `LANE_UNKNOWN` | input | `invalid_argument` | `OrderError::LaneUnknown` | the order item | A record names a lane this version does not know. Update this component, or check the sender |
| `GRDR-MODEL-0009` | `LANE_NOT_UPLOADED` | input | `invalid_argument` | `OrderError::LaneNotUploaded` | the order item | A record of the local lane arrived, and local records never leave the device. Check the version of the component that sent it |
| `GRDR-MODEL-0010` | `EPOCH_ZERO` | input | `invalid_argument` | `OrderError::EpochZero` | the order item | A record has epoch 0, which no device writes. Check the component that sent it |
| `GRDR-MODEL-0011` | `SEQ_ZERO` | input | `invalid_argument` | `OrderError::SeqZero` | the order item | A record has sequence number 0, which no device writes. Check the component that sent it |

Each fits RFC 0007 section 4's grammar. `ENTROPY_UNAVAILABLE` is `fatal`: repeating the call unchanged does not help, and a retry of it would need the randomness that failed. It is never `retryable`, so no policy retries it. `faults_peer` (RFC 0008 R12) is true for it, so a remote peer that returns it counts as not serving the call. `ID_TIME_OUT_OF_RANGE` is `fatal` with `failed_precondition`, because the host's clock is in a state no id can be made from. `RETRY_PEER_MISMATCH` is `internal`, a defect in the code that chose the table, and its `fix` names the support-bundle command through the CLI registry (RFC 0007 section 3). Token arguments are `structural` `LogSafe` values.

### 10. Answers to the questions of #1850
| # | Question | Answer |
|---|---|---|
| 1 | `DelegationSnapshotId`'s prefix and route | `dls_`, `Uuid7`; `DelegationId` `dlg_` and `ProviderId` `prv_`, both `Random128` (section 4) |
| 2 | `HolderId`'s route, and whether the type moves | `hld_`, `Random128`, in `grdr-model`; RFC 0002's capability stays in `grdr-ports` as `Holder` (section 4) |
| 3 | One `Lane` type, its variants, one definition with the protobuf enum | `Lane { Uploaded(UploadedLane), Local }`, with `UploadedLane`'s four lanes; the `lane_wire` test with exhaustive matches both ways (section 5) |
| 4 | The shapes of `Epoch`, `Seq` and `DeviceId` | Non-zero `u32`, non-zero `u64`, a `Derived128` id (section 5) |
| 5 | The give-up reason's name | `GiveUp` (section 6) |
| 6 | #282's `#[cfg(test)]` constructor | None; tests use `RetryLimits::new` and `from_limits` (section 6) |
| 7 | Which ids are `LogSafe`, through `IdRef`, and a `Code`'s form | `OrgId` and `DelegationSnapshotId`; `LogValue::Code` (section 7) |
| 8 | The paths of `InstallProfile` and `Tamper` | `grdr_model::InstallProfile`, `grdr_model::Tamper` (section 8) |
| 9 | `Entropy::fill` and a failing source (lead-core's comment) | `fill` returns `Result<(), EntropyError>` (section 3) |
| 10 | How the call's peer kind reaches `from_limits` (RFC 0007 round 4) | An argument from the port, checked at construction (section 6) |
| 11 | RFC 0008 section 8's changes 1 to 9 and constraints 1d and 1f | The table in section 6 |

### 11. Failure modes
| Failure | Declared outcome | Visible as |
|---|---|---|
| A time's seconds or nanoseconds are out of range | `TimeError::Seconds` or `Nanos` | The caller's error, `GRDR-MODEL-0001` or `0002` |
| `Timestamp` arithmetic would leave the range | `None` | The returned value |
| The random source fails | `EntropyError::Unavailable`; minting returns `IdError::Entropy` and builds no id; `next` returns `GiveUp::EntropyUnavailable` with the ceiling as backoff and `open_for`; no bytes the source did not produce are ever used | The caller's error, `GRDR-MODEL-0003`; RFC 0008's `GaveUp` with its reason |
| A source fills part of the buffer | `Err`, never `Ok` | As above |
| AWS-LC cannot get random data in a program | The library aborts the process before `fill` returns | The process ends; #334's row says what the daemon shows |
| An id is minted with a `now` before 1970 | `IdError::TimeOutOfRange` | The caller's error, `GRDR-MODEL-0005` |
| A wire id is malformed or of another kind | `IdError::Form`; nothing is decoded | The decoder's error, `GRDR-MODEL-0004` |
| A wire lane is 0, unknown, or `local` where an uploaded lane is required | `OrderError::LaneUnspecified`, `LaneUnknown { number }` or `LaneNotUploaded` | The decoder's error, `GRDR-MODEL-0007` to `0009` |
| A wire epoch or sequence number is 0 | `OrderError::EpochZero` or `SeqZero` | The decoder's error, `GRDR-MODEL-0010` or `0011` |
| An epoch or a sequence number is at its maximum | `next` returns `None`; the caller maps it to its own code | The caller's error |
| A table's peer kind differs from the call's | `RetryPolicyError::PeerMismatch`; the caller's rule class decides (D-15) | The caller's error, `GRDR-MODEL-0006` |
| A counter or a hint is huge | The ceiling stays at the cap; sums saturate | #282's cases at `u32::MAX` and a hint of `u64::MAX` ms |
| A probe never reports | `HalfOpen` ends at `probe_until`: the next permit is `Unanswered` | The breaker's state |
| A check never reports | `Checking` ends at `check_until`: the next recorded failure starts a new check | The breaker's state |
| A check or probe reports after the breaker moved on | `record_check` and `release` leave the breaker unchanged | The breaker's state |
| A caller logs a type that is not `LogSafe`, or an id of a kind that is not loggable | Compile error at the call site | rustc's E0277 |
| A name or word is outside its grammar | Compile error in the `const` item | rustc's E0080 |
| A record is kept past its statement | Compile error | rustc's E0716 |
| The protobuf lane enum gains a value, or `Lane` a variant | `lane_wire` fails to compile | rustc's E0004 |

Nothing here fails open: no error reads as success, a failed draw never yields bytes, and a refused permit is never a call.

### 12. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| One path per item (R3) | The source modules are private; a compile-fail doctest that `grdr_model::log::LogSafe` does not resolve (E0603); `cargo public-api` lists exactly sections 2 to 8 at the root | #383 and #284; #1741 |
| Layer 1 (R2) | `cargo check --locked --target wasm32-unknown-unknown -p grdr-model`; the workspace lints; ARCH-003 | Each item; #1582 |
| The edges (R1) | The protected change of section 15; ARCH-001's graph | Section 15; #1580 |
| A failed source is an error, never bytes | A fixture source that writes a marker into `out` and returns `Err`: every minting route returns `IdError::Entropy` and no id holds the marker; `next` returns `GiveUp::EntropyUnavailable` with backoff and `open_for` at the ceiling | #383; #282 |
| `Entropy` stays dyn-compatible and reaches RFC 0008's `run` | Compile tests: `&mut dyn Entropy` passed to each minting route; a function generic over `R: Entropy + Send + ?Sized` that calls `mint` and `next`, whose future is `Send` when given `&mut (dyn Entropy + Send)` | #383; #282 |
| The id form and minting | #383 AC-1 to AC-7, with AC-5 gaining an id holding `/`, `=`, `.` and `..`, each refused (RFC 0002 section 15) | #383 |
| One id table | One macro list generates `IdKind`, `VARIANTS`, `prefix`, `route`, `loggable` and the newtypes; a test checks that every prefix fits `[a-z]{2,3}`, is unique and is not `agt`, and that each kind's `from_wire` refuses every other kind's text | #383 |
| Only two kinds log | `loggable()` is true for exactly `Org` and `DelegationSnapshot`, by a test; compile-fail doctests that log a `DeviceId`, a `SessionId` and a `PrincipalId` (E0277) and build an `IdRef` (E0451) | #284 |
| The `LogSafe` gate | #284 AC-1's compile-fail doctests with a `String`, a `&str`, a `Vec<u8>`, a `[u8; 32]`, a `PathBuf`, a `char` and an `Option<u64>` (E0277), and `wire_enum!` given a variant with a field | #284 |
| Names and words in their grammar | Compile-fail doctests with `"Bad"`, `"9lives"`, a 65-byte name, and words holding a space or `/` (E0080); #284 AC-2's grammar table at 64 and 65 bytes | #284 |
| A record lives for its statement | A compile-fail doctest that keeps one in a `let` (E0716) | #284 |
| One word list per enum (R5) | `wire_enum!`; a test that each enum's words are unique | #284 |
| `Lane` is one definition with the protobuf enum | `crates/grdr-model/tests/lane_wire.rs` (section 5) | The order item (section 15), after #394 |
| Epoch and sequence numbers start at 1 | Tests at 0, 1 and the maximum, where `next` is `None` | The order item |
| One `RetryPolicy` constructor | Private fields (a compile-fail doctest, E0451); ARCH-019 refuses `RetryLimits::new` outside test code (RFC 0007 section 8) | #282; #1582 |
| The peer kind is checked | #282's tests: a remote call given a `local` table and a local call given a `remote` table, each `PeerMismatch` | #282 |
| `next`'s arithmetic | #282 AC-1 to AC-3, with the counter and the run's retries drawn independently (RFC 0008 change 2), the hint floor, schedule jitter, a failed draw, and a hint of `u64::MAX` ms whose `open_for` is the ceiling | #282 |
| The breaker's transitions | #282 AC-4 as a table test with one case per row of section 6, the late `record_check` and `release` cases, and seeded random sequences in which nothing leaves `Open` except through `HalfOpen` | #282 |
| The budget and the share | #282 AC-3, and share cases: 0 until the window is full, and the window set by `registered`, not by a narrowed table | #282 |
| Every error variant has one code | `Coded` with an exhaustive match; RFC 0007's registry and ARCH-017 | Each item; #1582 |
| `Tamper` is ordered by grade | A test of `User < Admin < Platform` | The install profile item (section 15) |
| Stability (section 13) | The `[[crate]]` row of `surfaces.toml`, `rfc-required`, `cargo public-api`, `cargo semver-checks` | Section 15; #1741 |

### 13. Stability
- `grdr-model` enters `surfaces.toml` as `experimental` (D-60; ADR-0020; design/03 section 7), in one row of the `[[crate]]` kind RFC 0007 section 11 uses: `name = "grdr-model"`, `class = "experimental"`, `rfc = "0009"`. The class is the crate's, so `Monotonic` (RFC 0008) takes it too, and no item needs a key of its own.
- `experimental` allows a break in any release, and every change still goes by RFC: a change to a signature, a semantic, a variant, a grammar, a code's class, the loggable kinds or the lane mapping is an amendment, a new RFC that names RFC 0009, because an accepted RFC never returns to `Review` (RFC 0001, "RFC states").
- A new row of the id table (section 4) and a new code in the `MODEL` area are content under this RFC and RFC 0007; their pull requests name RFC 0009 or RFC 0007 for `rfc-required`.
- The codes' area, numbers, reasons, classes and Connect codes are stable wire identifiers from the first release, whatever the crate's class (RFC 0007 section 11). An id's text form and a lane's word and number are wire format and change only with the protobuf package's own rules (D-06).
- The release notes list every change to this surface (design/34 section 10).

### 14. What each item and document changes
Under #1850 R4 and R5, each lead or author writes these into its item or document; the chief architect's documents change through the design item of section 15.
- **#383**: its route is RFC 0009, not RFC 0001.
  - R2: `fill` returns `Result<(), EntropyError>` (section 3).
  - R3: the table of section 4, with `DelegationSnapshot`, `Provider`, `Delegation` and `Holder`; `prv_` leaves the non-goals.
  - R4: no `Display`; ids are `Clone` and not `Copy`; `PrincipalId` has its three constructors and `kind`.
  - R5 and R6: `mint` takes `&mut R` with `R: Entropy + ?Sized`, draws once, and returns `IdError::Entropy` on a failed draw; `Random128` minting returns a `Result`.
  - R11: the codes `GRDR-MODEL-0001` to `0005` of section 9, with the area row; its write set already names `schema/codes/model.toml`, and gains `schema/codes/areas.toml`, `crates/grdr-schema/src/codes/generated.rs` and `interface/strings/src/code.mf2.toml` (RFC 0007 section 4).
  - The id table is one macro list (section 12). Its acceptance gains the cases of section 12. It is blocked by the edges item of section 15.
- **#18**: `Lane`, `UploadedLane`, `Epoch`, `Seq` and `OrderError` are built by a new sub-issue (section 15), not by #383.
- **#394**: number the `Lane` values 1 to 5 in the order `decision`, `spine`, `bulk`, `evidence`, `local`, which `Lane::number` follows.
- **#282**: its route is RFC 0009.
  - R1: `from_limits(limits, call: RetryPeer) -> Result<RetryPolicy, RetryPolicyError>`, the only constructor; its tests build tables with `RetryLimits::new`, and the `#[cfg(test)]` constructor goes.
  - R2: `next(counter, retries, elapsed, hint, entropy: &mut R)`, `RetryStep` with `open_for`, and `GiveUp` with `EntropyUnavailable`.
  - R4: a schedule's jitter. R5: the hint floor and the larger of the two delays. R6: the little-endian `u64` read.
  - R8: `RetryBudget::new(policy, registered)`, `record_attempt` and `failure_share` as `Permille`.
  - R9: the four-state `Breaker` with the methods of section 6, `Permit`, `ProbeKind` and `CheckOutcome`, in place of the three-state breaker.
  - `AttemptCounter`; the code `GRDR-MODEL-0006`, so its write set gains `schema/codes/model.toml`, `crates/grdr-schema/src/codes/generated.rs` and the token file.
  - The non-goal "Sharing one budget or breaker across threads" stays true (RFC 0008 section 8). Its acceptance gains section 12's cases. It is blocked by the edges item, by #383 for `Entropy`, and by #281 for `Monotonic`, as its Requires already says. The item grows past size M, so its lead should split it, for example into the policy, the budget and the breaker.
- **#284**: its route is RFC 0009.
  - R1: `LogValue<'a>` has the variants of section 7, with no `Digest`; `LogSafe::log_value(&self) -> LogValue<'_>`.
  - R2: `LogSafe` for the list of section 7, ids only for `OrgId` and `DelegationSnapshotId`, through `IdRef`, and for RFC 0007's `Code` and unit types.
  - R3: `wire_enum!` replaces `log_enum!`, and `WireName` and `wire_name!` join.
  - R4 and R5: `LogLevel` with four levels in place of `Level`; every item at the crate root.
  - R6: `log_record!` takes `"name" => value`.
  - Its write set gains the `LogSafe` impls for the ids and the units, which live in its `log` module. It is blocked by #383 and the edges item.
- **#334**: `OsRandom::fill` returns `EntropyError::Unavailable` when aws-lc-rs returns an error, and `CryptoError` carries a failed draw as a variant that wraps `EntropyError` and returns its code, so `RandomUnavailable` goes and one failure has one code (P17). Its failure table says that AWS-LC aborts the process when it cannot get random data, and what the daemon's supervisor then shows (section 3).
- **#1536**: R4 states what the daemon does when minting the `decision_id` fails: the request is answered as R8 answers a request it cannot take, and the failure shows with `GRDR-MODEL-0003`.
- **#1537**: R2 states what `Engine::step` does when a draw fails. It cannot return a decision whose id was not drawn; the rule class's failure mode decides the answer (D-15), and a diagnostic carries `GRDR-MODEL-0003`.
- **#1927**: its open question on `Entropy::fill` is answered by section 3. `OsRandom` passed as `&mut dyn Entropy` fits.
- **RFC 0002, for its author in its next revision**:
  - `Lane` becomes `UploadedLane` in `OrgWork::Ingest`, `StorageClass::Archive`, `ArchiveBatch` and `RowPosition`, and section 2's "`Lane` is `Decision`, `Spine`, `Bulk` or `Evidence`; there is no second lane enum" becomes "the server takes `UploadedLane`, the lanes that leave the device; each lane is declared once (RFC 0009 section 5)".
  - Section 7's `HolderId` becomes the capability `Holder`, holding RFC 0009's `HolderId`; `Setup::holder_id` and the kit's `holder_id` become `holder(&mut self, entropy: &mut dyn Entropy) -> Result<Holder, IdError>`; `Leases::acquire`, `Lease::holder` and `Claim::holder` take or return `&Holder`; the compile-fail doctests name `Holder`.
  - Section 2's contexts log their id as `LogValue::Id`, of data class `identifier`, not `structural`.
  - Section 15's request for `OrgId`, `DelegationId` and `DelegationSnapshotId` is met by section 4, with `ProviderId`.
  - The `grdr-model` types are RFC 0009's, not "#1850" or "#18, settled by #1850".
- **RFC 0003, for its author in its next revision**: `InstallProfile` and `Tamper` are `grdr_model::InstallProfile` and `grdr_model::Tamper`, stated by RFC 0009; `Monotonic`, `Timestamp` and `Clock` are RFC 0008's, not RFC 0002 section 3's; `LogSafe` is RFC 0009's and `Coded` RFC 0007's (#278), not #284 and #280.
- **RFC 0008**: no change. Its section 8 changes 1 to 9 are met (section 6). The failure share's form is #1966's amendment, which this RFC follows.
- **design/03 section 10**, proposed:
  - Randomness: "a failed draw is an error with its code, never bytes the source did not produce";
  - Logging: "an id is `LogSafe` only for the organisation and delegation snapshot kinds; a record lives for the statement that writes it";
  - Retries: "`RetryPolicy` (pure: the attempt counter, the run's retries, injected entropy and the server's hint in, the next delay or a give-up out)", in place of "attempt number".
- **design/04**, proposed: section 2's `epoch` row adds "starting at 1"; section 3's sentence "Ids defined elsewhere follow the same form" adds providers (`prv_`), delegations (`dlg_`) and delegation snapshots (`dls_`) in 21 and lease holders (`hld_`) in 20.
- **design/21 sections 2 and 5 and design/20 section 6**, proposed: the logs row of design/21 section 2 adds the delegation snapshot id beside the organisation id. The `delegation_snapshot` key that design/21 section 5 writes holds the snapshot id's text form, and the row-level security policy of design/21 section 2 and design/20 section 6 compares `current_setting('grdr.orgset', true)` as text, with no `::uuid` cast, because no `grdr-model` id gives out its bits (#383 R4) and RFC 0002 binds `as_str`.

### 15. Filed on acceptance
Each cites RFC 0009 and is blocked by the decision record's issue:
- the protected change that adds `grdr-schema` as a dependency and `grdr-proto` as a dev-dependency of `grdr-model`, in `crates/grdr-model/Cargo.toml` and `Cargo.lock`, for lead-agent-kit, trust core; it blocks #383, #282, #284 and the order item;
- the `surfaces.toml` row of section 13, titled with `surfaces.toml` and `grdr-model`, for lead-agent-kit, trust core, blocked by #1817 and #1915 as #1942 is (#1850 AC-6);
- the #18 sub-issue for `Lane`, `UploadedLane`, `Epoch`, `Seq`, `OrderError`, `lane_wire` and codes `0007` to `0011`, for lead-core, blocked by #394, #284 and the edges item;
- the item for `InstallProfile` and `Tamper`, for lead-core, blocked by #284, blocking the `grdr-wire` items that call `resolve` (#377, #516);
- the design item for the design/03, design/04, design/20 and design/21 sentences of section 14, for the chief architect;
- constraint comments on #1688 and #1757 carrying section 14's changes to RFC 0002 and RFC 0003, and on #383, #282, #284, #334, #394, #1536, #1537 and #1927 carrying theirs.

## Surfaces changed
- `grdr-model` (layer 1, public): the items of sections 2 to 8, every one at the crate root. Class `experimental`.
- The error registry: the area `MODEL` and its eleven codes (section 9).
- As proposals: the `[[crate]]` row of `surfaces.toml`; the `grdr-model` edges in `Cargo.toml` and `Cargo.lock`; sentences of design/03 section 10, design/04 sections 2 and 3, design/20 section 6 and design/21 sections 2 and 5 (section 14).
- No spine text, protobuf package, Cedar schema, third-party dependency or same-layer edge changes. The new edges go to layer 0.

## Alternatives
- **`Lane` with RFC 0002's four variants.** The daemon could not stamp `local` records, which design/04 section 2 gives their own sequence and chain. Rejected.
- **One flat `Lane` of five variants.** Every server type that takes a lane could hold `local`, so ingest, the archive path and the lifecycle table would each need a refusal for a value that never arrives. Rejected for `UploadedLane` inside `Lane`.
- **A flat `Lane` beside a four-variant `UploadedLane`.** Each word would be declared twice. Rejected for the nested form.
- **`Lane` generated from the `.proto` file, or `grdr-model` depending on `grdr-proto` for a `TryFrom` of the generated enum.** The first needs a `.proto` reader in the tests. The second puts the codec's runtime in the normal closure of every crate that links `grdr-model` and ties this crate's API to the generated type before SP-1 has chosen the codec. Rejected for the wire numbers and a parity test.
- **An infallible `fill` with a latched failure, or with a probing constructor.** Neither has bytes to give after a failure (section 3). Rejected.
- **`GiveUpReason`.** A new name that would amend RFC 0008. Rejected.
- **A `#[cfg(test)]` or public second constructor of `RetryPolicy`.** The first does not reach integration tests and the second lets any crate build an unchecked policy. Rejected for `RetryLimits::new` in tests and `from_limits`.
- **The peer kind as a type parameter.** RFC 0007's tables are one type whatever their peer, and an adapter's back end is configuration, so the type would only restate an argument. Rejected for an argument checked at construction.
- **The peer kind on RFC 0008's `Health` trait.** It would amend RFC 0008 and still need this check. Rejected.
- **Refusing only a remote call given a local table.** A one-way check leaves the other mismatch silent, and equality is simpler to state and test. Rejected.
- **`HolderId` as the capability in `grdr-model`.** Any crate could mint one, which RFC 0002's lease rules forbid. **`HolderId` minted by `grdr-ports`' own code.** ARCH-020 forbids it. Both rejected for an id in `grdr-model` and the capability `Holder` in `grdr-ports`.
- **Every minted id `LogSafe`, as #284 R2 had it.** A log would carry session, device and principal ids, per-person records outside the event stream's classes and retention, against design/21's logs row (P8). Rejected for two kinds.
- **`Display` on ids.** It invites building person-facing text by concatenation (UX6) in a crate that renders nothing. Rejected, as RFC 0007 rejects it for codes.
- **`Copy` ids with inline text.** `as_str` would need a fallible conversion, since `core::ascii::Char` is unstable on the pinned toolchain. Rejected for ids that hold their text.
- **`log_enum!` with its own list of words.** A second home for the words `as_str` returns. Rejected for `wire_enum!`.
- **`LogValue::Enum(&'static str)`.** Any static or leaked string, a path included, would pass. Rejected for `WireName`'s grammar.
- **`LogValue::Digest` now.** No type yields it, and a public variant of raw bytes would let any impl log a bare hash. Rejected until the keyed digest exists.
- **Public modules, such as `grdr_model::log::LogSafe`, beside or instead of root paths.** RFC 0002, 0003 and 0008 name root paths, and two paths per item are two ways to name it. Rejected for one root path.
- **Bare `u32` and `u64` for the epoch and sequence number.** A proto3 zero is an absent field, and a bare integer would accept it as a position. Rejected for non-zero types.
- **The failure share over the budget's time window, as RFC 0008 has it.** Under a steady failure rate it flickers (eval-adversarial m1, RFC 0008's constraint 1f). Rejected for #1966 R2's form.
- **`Verdict` or `Health` for the breaker's check result.** The first is the spine's word for a decision, and the second is RFC 0008's trait. Rejected for `CheckOutcome`.
- **`Level` at the crate root.** It does not say which level. Rejected for `LogLevel`.

## Drawbacks
- Every function that draws can fail, so minting, `Engine::step`, the daemon's decision ids and `Setup::holder` each carry a failure that, with AWS-LC, the programs never see returned.
- Readers meet two lane types, and the daemon writes `Lane::Uploaded(UploadedLane::Decision)` where a flat enum would be shorter.
- Each id allocates its text once.
- Only two kinds of id can be logged, so a diagnostic points at a record by `(epoch, lane, seq)`.
- The lane numbers are written in Rust and in the `.proto` file, held equal by a test rather than generated.
- `WireName`'s grammar is a tripwire: a single lower-case word passes it, so review holds what it cannot.
- `RetryBudget::new` takes the registered table beside the policy, and the executor must pass the right one.
- The breaker has seven methods, and the executor keeps the state each check or probe started from.
- #282 grows past size M and needs splitting.
- The surface lands across four items and two more filed on acceptance, so a reader follows section 1's table.

## Unresolved questions
None for this RFC's own decision. Open elsewhere:
1. **The failure share (#1966).** This RFC states #1966 R2's form, as RFC 0008's constraint 1f asks. If #1966 is decided with another form, it amends this RFC too and names both.
2. **Server-authored records.** design/04 section 2 puts an emitter id (`srv_`) in the envelope's `device_id`, which `DeviceId` refuses. The item that adds the `srv_` row decides the emitter type, and RFC 0002's `RowPosition` follows by amendment. No slice-0 path writes a server-authored record to the lake.
3. **The keyed digest.** Design/04 work item 04-16 adds its type and `LogValue::Digest` by amendment.
4. **Twins of `InstallProfile` and `Tamper`.** The item that declares either in protobuf or Cedar adds its parity test (section 8).

## Review
How review binds the decision (RFC 0001, "Review binds the decision"; ADR-0036):
- RFC 0009 decides no pinned path, so its decision adds no decision line and no file under `rfcs/evidence/`, and `rfcs/pins.toml` does not change.
- The review set: the nine persona council seats, once, on #1850; `eval-architecture`, the `[kinds] rfc` row of `.claude/risk-tiers.toml`; `eval-api`, the `public_api_change` row, because this RFC states a public crate's API; and `eval-security`, from the `medium` tier's set, because the RFC fixes what a failed random source yields and what may reach a log. At least one evaluator runs on the other model from the one in the metadata block.
- Each verdict and each seat comment gives the three role lines of RFC 0001 (#1798), as full 40-character ids:
  - `RFC file:` the blob of this file it read (`git rev-parse <commit>:rfcs/0009-grdr-model-slice-0-surface.md`), with the commit;
  - `Proposed text: none`, because no pinned path changes;
  - `Base:` the spine pin in force in `rfcs/pins.toml`, `a80859235e7a2a4444648d6fa8d389d78dde6be9`, SHA-256 `8f6ea876777c0121ecec068c0bc4cef45932be45c1c2aff4140712db1e06628d`.
- RFC 0009 is decided only while RFC 0007 reads `Accepted` on `main` (#1850 R5 and AC-9); it does at `91e1cec`. RFC 0008 is accepted too, and this RFC meets its section 8 list.
- The decision rests on an `eval-architecture` pass on the blob it decides, with no fail by an evaluator of the set on that blob, and the chief architect checks that the seats commented on that blob. The file the decision commits differs from that blob only in `State:`, `Decision record:`, link lines under this section and the `Decision` section. It reaches `main` in `Review` before the commit that decides it (RFC 0001, "RFC states").

The bench behind sections 2 to 8 is a set of sketches of the signatures, compiled with rustc 1.99.1, the pinned toolchain, outside the repository: the sketch, clippy over it with the workspace deny list, the sketch for `wasm32-unknown-unknown`, the uses that RFC 0002, RFC 0003 and RFC 0008 make of these types, the lane parity test and its failure against a widened generated enum (E0004), and 25 compile-fail cases, each failing with the error section 12 names. The revision 1 comment on #1850 gives its commands and exit codes.

Verdicts and seat comments on this revision are linked below, one per line.

## Decision
Pending.
