RFC: 0007
Title: The slice-0 public surface of grdr-schema (error codes, the Coded binding and limits), and where each slice-0 type of grdr-model and grdr-schema lives
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #1710
Spine: D-05, D-48, D-60, D-61, D-63, D-66, D-69, P1, P8, P9, P10, P14, P15, P17 (no spine text changes)
Surfaces: the public crate `grdr-schema` (layer 0): modules `codes` and `limits` with their generated constants; the formats they are generated from, `schema/codes/areas.toml`, `schema/codes/<area>.toml` and `limits.toml`; the rendered code form `GRDR-<AREA>-<NNNN>` with its language-token ids and docs anchor; the error-code area `LIMITS` with one code. As proposals: design/03 sections 2 and 10, and one `[[crate]]` row of `surfaces.toml` for `grdr-schema`. No dependency, same-layer edge, wire format or Cedar schema changes
Decision record: none yet

To comment, write on issue #1710 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This is revision 2. It answers round 1's `eval-architecture` verdict (Review). The comment "RFC 0007 revision 2" on #1710 lists every finding and where it went. The text below is normative on its own. Where it differs from the items it covers, this RFC wins, and section 9 tells each lead what to write back.

## Summary
#1710 asked for one RFC over the slice-0 surface of `grdr-model` and `grdr-schema`. This RFC decides that scope in parts. It states in full the `grdr-schema` surface that #278 and #279 build: the `Code` type and its generated constants, the `Coded` trait, the registry format they come from, the limit unit types, `RetryLimits`, and the `limits.toml` format. It also fixes where every other slice-0 type of the two crates lives and which RFC states it: the `grdr-model` surface (#1850), the `ErrorDetail` message and its binding (#1851), and the lake column manifest type (#1852). `Code` can be built only inside its own module, so holding one means the registry has that entry. The code prefix comes from the brand manifest, and the docs anchor and token ids are derived from the code, each in one place that every other tool reads. A registry entry's lifecycle is a status value, not a flag. `limits.toml` refuses a unit written into a name and has no reserved value. Both modules enter `surfaces.toml` as `experimental`, in one `[[crate]]` row.

## Motivation
#278 has 202 dependants by the #645 count, and #279 builds `limits.toml` and the module that is the only place ARCH-019 lets a bound live. Both cite RFC 0001 as their route, but RFC 0001 adopts the spine text and no crate surface, and the ruling on #1535 holds that `experimental` does not exempt a public crate (D-61, design/30 section 3). RFC 0002 (#1688), RFC 0003 (#1757) and RFC 0005 (#405) already depend on this surface:
- RFC 0002 binds every port error to a code through `Coded` and assigns seven areas, but states no signature for `Code` or `Coded`.
- RFC 0003 proposes `limits.toml` keys such as `ipc.call-max-ms`, which repeat their unit in the name.
- RFC 0005's Unresolved question 3 leaves the unit of the fast-path expiry rows open between #1768 and #279. #1768 asks for nanoseconds, with 18,446,744,073,709,551,615 meaning "until the scope ends". TOML cannot write that number.
- #1768's keys (`fastpath.eval_cap_steps`) and RFC 0005 R5.3's ceiling rows fail #279 R3's name grammar.

If nothing changes, #278 and #279 wait on a review of the whole two-crate surface, and three RFCs keep pointing at types nobody has stated.

## Design

### 1. Scope
**Decision.** This RFC states the `codes` and `limits` modules of `grdr-schema` and the formats behind them. The rest of #1710's scope goes to three RFC issues filed from this decision, each with the prerequisites it actually has:

| Part | Prerequisites | Issue | Blocks |
|---|---|---|---|
| `grdr-model`: time, `Entropy`, ids, lanes, `LogSafe`, the retry state types, `InstallProfile`, `Tamper` | Drafting needs nothing; deciding needs this RFC decided | #1850 | #18, #383, #282, #284 |
| `ErrorDetail` and `ErrorClass` in `grdr.common.v1alpha1`, and `Code::detail()` | RFC 0006 (#1848) and this RFC decided; the SP-1 codec (#368) before the decision | #1851 | #280 |
| The lake column manifest type in `grdr-schema` | #386 merged, #510 specified, this RFC decided | #1852 | #510 |

Reasons:
1. **Dependency direction.** `grdr-schema` is layer 0 and depends on nothing in this RFC. `grdr-model` is layer 1 and reads `RetryLimits` and `Coded` from it. Deciding the lower layer alone lets #278 and #279 proceed, and the `grdr-model` RFC cites a decided text.
2. **Readiness.** #510 is a stub until #386's field registry format merges, so its type cannot be stated now. `ErrorDetail` is a protobuf package change that imports RFC 0006's options, and `Code::detail()` returns a type whose shape depends on SP-1. Holding `Code` behind either would hold #278 behind SP-1.
3. **Open questions in `grdr-model`.** Drafting this RFC found eight questions in the `grdr-model` half, listed on #1850: among them a `DelegationSnapshotId` with no id row, five lanes in design/04 against four in RFC 0002, and two names for the give-up reason. A finding on any of them would hold the code registry in the same review.
4. **Review size.** RFC 0001 took six revisions, and RFC 0002 is in its fourth round. Every round re-reads the whole text, so a text with one concern costs less per round.

**Where each type lives.** No type below gets a second definition in another crate (P17).

| Type | Crate and module | Stated by | Built by |
|---|---|---|---|
| `Code`, `CodeStatus`, `ErrorClass`, `ConnectCode`, `Coded`, the code constants, `ALL`, the format constants | `grdr_schema::codes` | Section 3 | #278 |
| `Bytes`, `Count`, `Millis`, `Permille`, `Backoff`, `BudgetLimits`, `RetrySpec`, `RetryLimits`, `LimitsError`, `RetryRule`, `BUDGET_SLOTS_MAX`, the limit constants | `grdr_schema::limits` | Section 5 | #279 |
| `Code::detail()`, `ErrorDetail`, the protobuf `ErrorClass` | `grdr_schema::codes` or `grdr-proto`, and `grdr.common.v1alpha1` | #1851 | #280 |
| The lake column manifest type | `grdr-schema` | #1852, amending this RFC | #510 |
| `Timestamp`, `TimeError`, `Entropy`, `IdKind`, `MintRoute`, `IdError`, the typed ids (`OrgId`, `SessionId`, `DeviceId`, `DelegationSnapshotId` and the rest) | `grdr-model` | #1850 | #383 |
| `Lane`, `Epoch`, `Seq` | `grdr-model` | #1850 | #18 |
| `RetryPolicy`, `RetryStep`, the give-up reason, `RetryBudget`, `Breaker` | `grdr-model` | #1850 | #282 |
| `LogSafe`, `LogValue`, `LogRecord`, the log macros, and `LogSafe` for `Code` and the limit units | `grdr-model` | #1850 | #284 |
| `InstallProfile { Protected, User }` (D-48), `Tamper { User, Admin, Platform }` (spine section 3) | `grdr-model` | #1850 | the item #1850 names; `grdr-wire` imports them (RFC 0003) |
| `Monotonic` | `grdr-model` | RFC 0002 section 3 | #281 |

Notes:
- `Entropy` is re-exported by `grdr-ports` (RFC 0002 section 3), never redefined.
- The module paths of `InstallProfile` and `Tamper` are #1850's to fix, and RFC 0003 follows them.
- RFC 0005's `grdr_fastpath::layout::Nanos` is that crate's own type, and no type here shares its name.
- For #1851: a `detail()` method on `Code` would bring `grdr-proto` into the closure of every crate that reads a limit, and would allocate inside `codes` (section 2, R3). #1851 weighs that against a conversion in `grdr-proto` (its question 4).

**Agreement with RFC 0002.** Of the types both RFCs name, this RFC states `Code` and `Coded`. RFC 0002 names them without a signature, so this is their one definition. RFC 0002's `RetryError<E>` and its proposed ARCH-017 exemption list are unchanged. The other shared types are #1850's and #1852's, and `Monotonic` stays RFC 0002's.

### 2. Rules for both modules
- R1. **Dependencies.** `grdr-schema` has no normal dependency, third-party or workspace. Its listed same-layer edge to `grdr-proto` is first used, if at all, by #1851. `toml` is a dev-dependency only, for the generators (#1575), so no parser enters any normal closure (ARCH-004). A privileged program may therefore link `grdr-schema`, as RFC 0005 R5.3 relies on.
- R2. **Layer 0.** No I/O, clock, randomness, async runtime or Cargo feature. It builds for `wasm32-unknown-unknown` (ARCH-003). Arithmetic is checked or saturating (`#![deny(clippy::arithmetic_side_effects)]`), no non-test code has a panic path, and `unsafe` is forbidden.
- R3. **No allocation.** Every type here is `Copy` and holds integers, `bool`, closed enums and `&'static` data.
- R4. **No rendering.** The crate is `renders = "none"`. No type implements `Display`. A code is read with `as_str`, and it reaches a person only through its `code.<code>.message` and `code.<code>.fix` language tokens, with any argument passed as a typed value (D-69, UX6).
- R5. **Generated files.** `src/codes/generated.rs` and `src/limits/generated.rs` are generated by test code under `crates/grdr-schema/tests/gen/` and committed. The ignored `regenerate` test is their only writer, and a `drift` test in `cargo test --workspace --locked` fails when a committed file differs from a fresh generation. Output is byte-identical on Linux, macOS and Windows: input line endings normalised, LF out, sorted, no timestamp or path (#278 R4, R5, R8; #279 R4, R6, R10).
- R6. **One home for each derived string and each word list.** The generator renders every code string once. `grdr-archlint` (ARCH-017), the docs generator (`/codes/<code>` pages) and `grdr-interface-gen` (the token check) are tool crates, which may depend on any layer (ARCH-001). They link `grdr-schema` and read `codes::ALL` through its accessors, and none renders a code from the TOML itself. The generator, in turn, takes the class, Connect and status words from the enums' `VARIANTS` and `as_str`, never from a list of its own.
- R7. **Format constants.** The numbers that define the formats are not tunables, as RFC 0002 Rule 7 treats its 255-byte identifier ceiling. Each is one named `pub const` in its module: `NUMBER_MAX`, `REASON_MAX_BYTES`, `AREA_MIN_BYTES` and `AREA_MAX_BYTES` in `codes`, and `BUDGET_SLOTS_MAX` and `Permille::ONE` in `limits`. They are not `limits.toml` rows, because changing one changes a format, which is an amendment (section 11).
- R8. **Data classes and assurance.** Every type, registry field and limit is `structural` (P8). No action class changes `visibility`, `control`, `on_failure` or `tamper` (P1).
- R9. **Scale.** Codes and limits are compile-time constants. They add no request, byte, connection or store call at any fleet size (P15). What an error costs on the wire is #1851's.

### 3. The `codes` module
```rust
// grdr_schema::codes
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Code { /* private: area, number, reason, status, class, connect and the five rendered strings */ }
impl Code {
    pub const fn area(&self) -> &'static str;          // "CFG"
    pub const fn number(&self) -> u16;                 // 7
    pub const fn reason(&self) -> &'static str;        // "ADAPTER_NOT_IN_PROFILE"
    pub const fn status(&self) -> CodeStatus;
    pub const fn class(&self) -> ErrorClass;
    pub const fn connect(&self) -> ConnectCode;
    pub const fn as_str(&self) -> &'static str;        // "GRDR-CFG-0007"
    pub const fn const_name(&self) -> &'static str;    // "CFG_ADAPTER_NOT_IN_PROFILE"
    pub const fn message_token(&self) -> &'static str; // "code.GRDR-CFG-0007.message"
    pub const fn fix_token(&self) -> &'static str;     // "code.GRDR-CFG-0007.fix"
    pub const fn anchor(&self) -> &'static str;        // "codes/GRDR-CFG-0007"
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum CodeStatus { Active, Retired }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum ErrorClass { Input, Policy, Retryable, Fatal, Internal }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum ConnectCode {
    Canceled, Unknown, InvalidArgument, DeadlineExceeded, NotFound, AlreadyExists,
    PermissionDenied, ResourceExhausted, FailedPrecondition, Aborted, OutOfRange,
    Unimplemented, Internal, Unavailable, DataLoss, Unauthenticated,
}
// CodeStatus, ErrorClass and ConnectCode each have:
//   pub const VARIANTS: [Self; N];            every variant, in declaration order
//   pub const fn as_str(self) -> &'static str; "active", "input", "invalid_argument", ...

pub trait Coded { fn code(&self) -> &'static Code; }

pub const NUMBER_MAX: u16 = 9999;
pub const REASON_MAX_BYTES: usize = 63;
pub const AREA_MIN_BYTES: usize = 2;
pub const AREA_MAX_BYTES: usize = 8;

// generated: src/codes/generated.rs, the child module codes::generated, re-exported by codes
pub const CFG_ADAPTER_NOT_IN_PROFILE: Code = /* the constructor private to codes */;
pub const ALL: &[Code] = &[/* every entry, active and retired, in area then number order */];
```

`Code`:
- It implements neither `Default`, `Deserialize` nor any parse from a string. Its `const` constructor is private to `codes`. Rust lets a child module use its parent's private items, so `codes::generated` calls it and no other module of the crate can, `limits` included. `codes` itself holds no other caller; review holds that (section 8). A crate that needs a code names a generated constant, so a code the registry does not hold cannot exist.
- `as_str` renders `<PREFIX>-<AREA>-<NNNN>`, with the number zero-padded to four digits. `const_name` is `<AREA>_<REASON>`, the constant's identifier. The token ids are `code.<as_str>.message` and `code.<as_str>.fix`. The anchor is `codes/<as_str>`, the code's page below the docs site root (design/34 sections 5 and 6). The generator computes these five strings once, and every other tool reads them from `ALL` (section 2, R6), so none can disagree with the code (P17).
- `<PREFIX>` is `[identity] namespace` of `brand/brand.toml`, upper-cased: `GRDR` today. The generator reads it there and holds no literal, and a missing or malformed namespace stops generation, with no default. Design/36 section 2 makes `GRDR-` a Class A wire identifier: an RFC may change it before the first release, and nothing changes it after. A white-label manifest changes Class B and C names only, so a partner's build keeps the codes an embedder's support pages quote. A namespace change regenerates every rendered string and no constant name, because constant names carry no prefix. Until the D-66 search is recorded, the namespace is provisional (ADR-0003, proposed).
- Equality and hashing cover every field. Two constants of one entry are equal.

`CodeStatus` is an entry's lifecycle. `Active` entries have a constant. `Retired` entries have none, stay in `ALL` so their pages and support quotes keep working, and never return to `Active`. A third state, such as a deprecated constant kept for one deprecation release, arrives as a new variant by amendment (section 11).

`ErrorClass` tells the caller of our code what to do next. It is the registry's `class` word:
- `input`: the caller's request or data is wrong, and the same input fails the same way;
- `policy`: the request is well formed and a rule, a policy or a verification refused it; this is a decision, not a fault;
- `retryable`: a transient fault, and the same call may succeed later under its retry policy;
- `fatal`: the operation cannot complete, and repeating it unchanged does not help; the next step is the one its `fix` token names, such as a configuration change or a new acquisition;
- `internal`: a defect in the product, reported and never retried.

`ConnectCode` is the status a remote client of the API sees, one of the sixteen error codes of the Connect protocol, in its snake-case spelling (P10). Class and Connect code answer different questions, and neither is derived from the other. RFC 0002 and RFC 0003 already pair them freely: for example, `GRDR-WIRE-0002 BODY_TOO_LARGE` is `internal` with `invalid_argument`, because only a defect in our own sender reaches it.

`CodeStatus`, `ErrorClass` and `ConnectCode` are exhaustive enums. A new value is an amendment, and it fails every exhaustive match until handled. `VARIANTS` lists every variant: a `match` with no wildcard arm, in the same module, gives each variant its position in `VARIANTS`, so a new variant does not compile until it is listed.

`Coded`:
- Every error type implements it with one exhaustive `match`, no wildcard arm, one generated constant per variant. It never returns an element of `ALL`, so it cannot return a retired code.
- A variant that only wraps another coded error returns that error's code (RFC 0005 R4.6).
- Callers act on `code().class()`, never on the variant (RFC 0002 Rule 8).
- `code` returns a reference to a constant, which Rust promotes to `'static`. The trait is object safe.
- The exceptions are the ARCH-017 exemption list of `architecture.toml`, which is not on `main`. RFC 0002 section 14 proposes it as a protected change, and RFC 0005 R4.1 adds per-variant entries to it. Until it lands, the exceptions are the types an RFC in `Accepted` state exempts by name, and review applies the rule, because ARCH-017 is not built yet (#1582).

`ALL` lists every entry, active and retired, ordered by area bytes and then number. Nothing in this module looks a code up by its string. A consumer that holds a rendered code from the wire compares strings or walks `ALL`.

### 4. The code registry format
`schema/codes/areas.toml` holds one table per area:
```toml
[area.CFG]
subsystem = "configuration"
owner = "design/03"
```
- `AREA` is upper-case ASCII letters, `AREA_MIN_BYTES` to `AREA_MAX_BYTES` long: `[A-Z]{2,8}`.
- `subsystem` names the subsystem that fails, never the surface that prints the code (design/03 section 10).
- `owner` is `design/NN` and resolves to exactly one file `docs/design/NN-*.md`.

`schema/codes/<area>.toml`, named after its area in lower case, holds the entries:
```toml
[[code]]
number = 7
reason = "ADAPTER_NOT_IN_PROFILE"
status = "active"
class = "input"
connect = "failed_precondition"
```
Every key is required:
- `number`: 1 to `NUMBER_MAX`;
- `reason`: UPPER_SNAKE per AIP-193, `[A-Z][A-Z0-9_]*[A-Z0-9]`, at most `REASON_MAX_BYTES`;
- `status`: a word of `CodeStatus::VARIANTS`;
- `class`: a word of `ErrorClass::VARIANTS`;
- `connect`: a word of `ConnectCode::VARIANTS`.

There is no `anchor` key, because the anchor is derived (section 3), and no `retired` flag, because `status` holds the lifecycle. Both change #278 R2.

The generator refuses each of these, names the file, the entry and the rule, and writes nothing:
- #278 R7's list: a file with no area row, a number repeated within its area (retired entries included), a reason repeated within its area, an area or a reason outside its grammar, a word outside its enum's `VARIANTS`, a number outside 1 to `NUMBER_MAX`, an unknown key;
- a missing key;
- an area row with no file, or whose file holds no entry;
- an `owner` that resolves to no document or to more than one;
- a missing or malformed `[identity] namespace` in `brand/brand.toml`.

Two constant names cannot collide: an area holds no underscore, and a reason is unique within its area. A retired entry keeps its number, which is never reused.

**Content, not surface.** The registry is content of the mechanism this RFC fixes (P14).
- Adding an entry, or an area with its first entry, needs no RFC of its own. The item that first constructs the code adds it and regenerates, and its pull request names RFC 0007 for `rfc-required`.
- The code's two language tokens are written by an interfaces item, because `interface/**` belongs to that squad. #1853 writes them for the codes registered before its check exists. From that check on, an item that registers a code is blocked by the interfaces item that writes its tokens, so the check never fails on `main`.
- An RFC that assigns codes fixes their numbers, reasons, classes and Connect codes, and the item copies them. RFC 0002 section 11, RFC 0003 section 9 and RFC 0005 R4.3 and R4.4 do this. Their areas, `TENANT`, `STORE`, `BLOBS`, `JOBS`, `BUS`, `REL`, `EVENTS`, `WIRE`, `PEER`, `FASTPATH` and `COMPILE`, all fit the grammar.
- Otherwise an item takes the next number in its area: one above the highest present, retired entries included. Two items that add to one area at once both append to one file, so the second conflicts and rebases.
- An entry on `main` never changes its area, number or reason, and is never deleted. Its status moves only from `active` to `retired`. A changed class or Connect code changes what callers do, so the item that changes the behaviour makes it, and the release notes list it (design/34 section 10).

### 5. The `limits` module
```rust
// grdr_schema::limits
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Bytes(/* private */ u64);
impl Bytes { pub const fn new(value: u64) -> Bytes; pub const fn get(self) -> u64; }
// Count (u64), Millis (u64) and Permille (u32) have the same derives, `new` and `get`.
impl Millis { pub const fn as_duration(self) -> core::time::Duration; }
impl Permille { pub const ONE: Permille; } // 1000 permille

pub const BUDGET_SLOTS_MAX: u16 = 1000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Backoff {
    Exponential { base: Millis, factor: Permille, cap: Millis },
    Schedule { delays: &'static [Millis] },
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BudgetLimits { pub ratio: Permille, pub window: Millis, pub slots: u16, pub min_interval: Millis }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RetrySpec {
    pub backoff: Backoff,
    pub max_attempts: u32,
    pub max_elapsed: Millis,
    pub honour_hint: bool,
    pub budget: BudgetLimits,
    pub timeout: Millis,
    pub breaker_failures: u32,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RetryLimits { /* private: a RetrySpec that passed every rule */ }
impl RetryLimits {
    pub fn new(spec: RetrySpec) -> Result<RetryLimits, LimitsError>;
    pub const fn spec(&self) -> &RetrySpec;
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LimitsError { RetryTable { rule: RetryRule } }
impl Coded for LimitsError { /* RetryTable { .. } => &LIMITS_RETRY_TABLE_INVALID */ }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RetryRule {
    MaxAttemptsZero, MaxElapsedZero, BaseZero, FactorBelowOne, CapBelowBase, ScheduleEmpty,
    ScheduleDecreasing { index: usize }, BudgetRatioAboveOne, BudgetWindowZero,
    BudgetSlotsOutOfRange, BudgetWindowNotDivisible, BudgetIntervalZero, TimeoutZero,
    BreakerFailuresZero,
}

// generated: src/limits/generated.rs, the child module limits::generated, re-exported by limits
pub const IPC_FRAME_MAX: Bytes = Bytes::new(2_097_152);
// one per [retry.<name>] table, once its owning document adds it (#279 R8); for example:
pub const UPLINK_RECONNECT: RetryLimits = /* the constructor private to limits, checked at generation */;
```

Unit types:
- A unit type is a plain amount in its unit. `new` is public and infallible, because tests and values derived at run time need it. ARCH-019 forbids it with a literal outside `limits`, the generated files and tests (section 8), so every bound in product code is a generated constant or derived from one (P14).
- `Millis::as_duration` is total.
- `Permille` is a ratio in thousandths and may exceed `Permille::ONE`, as a backoff factor does.

`RetryLimits`:
- `new` checks the rules in `RetryRule` order and returns the first that fails:
  - `max_attempts` of 0;
  - `max_elapsed` of 0, which would give up before any retry; a policy that never retries says so with `max_attempts = 1`, its one spelling;
  - an exponential `base` of 0, which would make every delay 0 and leave no backoff; a `factor` below `Permille::ONE`; a `cap` below its `base`;
  - an empty schedule, or one that decreases at `index`;
  - a budget `ratio` above `Permille::ONE`, a `window` of 0, `slots` of 0 or above `BUDGET_SLOTS_MAX`, a `window` that is not a multiple of `slots`, or a `min_interval` of 0;
  - a `timeout` of 0, which would fail every attempt at once;
  - `breaker_failures` of 0.
- These are #279 R5's rules plus `max_elapsed`, `base` and `timeout`, which #279 R5 lacks.
- `new` is the one copy of the rules. The generator calls it on every `[retry.<name>]` table before it writes the constant, so a committed constant has passed it, and the drift test runs it again on every test run.
- The generated constants use a `const` constructor private to `limits`, which only `limits::generated` calls, so they cannot fail at run time.
- Product code reads a policy only through `RetryPolicy::from_limits` (#1850). A crate may still build a `RetryLimits` at run time through `new`; ARCH-019 and review hold that to tests and to values derived from other limits (section 8).

`LimitsError` is the crate's one error enum, `#[non_exhaustive]`. `RetryTable` binds to a new area, `LIMITS` (subsystem: bounds and retry policies; owner: `design/03`):

| Code | Reason | Class | Connect | Bound by | Next step (`code.<code>.fix`) |
|---|---|---|---|---|---|
| `GRDR-LIMITS-0001` | `RETRY_TABLE_INVALID` | internal | `internal` | `LimitsError::RetryTable` | A defect: a retry policy was built from values `limits.toml` would refuse; report it with the rule the error names |

#279 registers the area and the entry, since it constructs the code (ARCH-017). #1853 writes the code's two tokens, from the next-step text above.

### 6. The `limits.toml` format
Two table families, `[bound.<name>]` and `[retry.<name>]`.

Names:
- A name is dot-separated segments, each `[a-z][a-z0-9]*(-[a-z0-9]+)*`. This tightens #279 R3, so no segment ends in a hyphen or holds two in a row.
- The last segment does not end in `-bytes`, `-count`, `-ms` or `-permille`. The unit is written once, as the key, so a name cannot disagree with its value.
- The generated identifier upper-cases the name and replaces `.` and `-` with `_`. Two names that map to one identifier are refused, across both families.

`[bound.<name>]` holds three keys, all required:
- exactly one unit key: `bytes`, `count`, `ms` or `permille`;
- `owner`: `design/NN`, resolving as an area's owner does, or the name of a crate or program, resolving to exactly one of `crates/<name>` and `programs/<name>`;
- `note`: one line of English that says what the bound limits. It is reference prose, as a proto comment is, shown on the generated reference page, which stays English (design/34). It is not a language token (D-69) and reaches no product surface.

Values:
- A value is a non-negative TOML integer, which TOML caps at 2^63 - 1. A `permille` value fits `u32`.
- A bound is the finite amount it names. The format has no value meaning "unbounded" or "until an event". Such a choice is behaviour, carried by the consumer's own type and set from a data source that holds a choice (P14), never by a reserved number. A state hidden in a number is what structure rule S4 forbids.
- There is no unit below a millisecond, because no bound needs one: section 7 settles the one candidate in `ms`. A unit such as `ns` arrives by amendment with the first bound that needs resolution below a millisecond.

`[retry.<name>]` holds #279 R2's keys, mapped onto `RetrySpec`, plus `owner` and `note`, both required as for a bound:

| Keys | Field |
|---|---|
| `kind` with `base_ms`, `factor_permille`, `cap_ms`, or `kind` with `delays_ms` | `backoff` |
| `max_attempts`, `max_elapsed_ms`, `honour_hint`, `timeout_ms`, `breaker_failures` | the field of the same name |
| `budget_ratio_permille`, `budget_window_ms`, `budget_slots`, `budget_min_interval_ms` | `budget` |
| `owner`, `note` | not generated |

The generator refuses, naming the file, the table, the key and the rule:
- #279 R5's list, through `RetryLimits::new` for the retry rules;
- a name outside the tightened grammar, or one ending in a unit;
- a missing `owner` or `note`, or an `owner` that resolves to nothing;
- a negative value, or one that does not fit its field's type in section 5 (`u32` for `permille`, `max_attempts` and `breaker_failures`, `u16` for `budget_slots`);
- a backoff key of the other kind, such as `delays_ms` under `kind = "exponential"`.

The seed is #279 R7 unchanged, and no retry table is seeded (#279 R8). Adding or changing a bound or a retry table is content in an item whose write set names `limits.toml`, which is a protected change on a trust-core path (D-63), and its pull request names RFC 0007. Removing one removes its constant, which fails the build of every crate that names it.

### 7. What this settles for other RFCs and items
- **RFC 0005, Unresolved question 3** (`issue/405` at `8c3fed7`). The two expiry rows are bounds in `ms`. A cache-reuse lifetime (`tables.md` section 2) is a whole number of milliseconds, and `FastpathLimits::from_limits` converts it to the header's nanoseconds with checked arithmetic, as RFC 0005 R5.5 already allows.
- **"Until the scope ends".** RFC 0005 owns this choice, because it states `FastpathLimits` and `layout::Expiry`, and #1768's lead sets its default with it. It is expressed as `Expiry::ScopeEnd`, the variant RFC 0005 revision 3 defines beside `Expiry::After(Nanos)`, never as a reserved number in a `limits.toml` row (section 6). The default between `ScopeEnd` and `After` comes from a data source that holds a choice rather than an amount, such as a `grdr.config` key with an enum value (design/03 section 9) or a field of the compiled bundle. When the choice is `After`, its amount is the `ms` row. Which source is open on #405 (Unresolved questions).
- **#1768.** Its keys follow section 6, for example `fastpath.eval-cap` and `fastpath.path-max` in `count`, and `fastpath.expiry-bundle` and `fastpath.expiry-session` in `ms`.
- **RFC 0005 R5.3.** Its two ceiling rows become, for example, `fastpath.host-eval-cap-ceiling` and `fastpath.host-path-max-ceiling`, both in `count`. `[retry.fastpath-reload]` already fits.
- **RFC 0003, section 11.** Its proposed keys drop their unit suffixes: `ipc.call-max`, `ipc.first-frame`, `ipc.link-suite-wait` and `ipc.link-suite-margin` in `ms`, and `ipc.read-chunk` in `bytes`. `ipc.frame-max` and `endpoint.connections-max` already fit.
- **Pointers in RFC 0002 and RFC 0003, for their author.**
  - `Coded` is built by #278, not #280: RFC 0002 Rule 8 and the Rule 8 row of its mechanisms table; RFC 0003 Rule 7, the `Coded` line of its section 11 and the Rule 7 row of its mechanisms table.
  - "The RFC of #1710" now means #1850 for the `grdr-model` types: RFC 0002 sections 2, 4 and 10, and RFC 0003 section 11, its list of item changes, its Surfaces changed and its question 3. It means #1852 for the column manifest in RFC 0002's Unresolved question 4.
- **RFC 0002.** Section 1's "Agreement with RFC 0002" holds, and its codes fit section 4 as written.

### 8. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| A `Code` exists only for a registry entry | The constructor private to `codes`; a compile-fail doctest that builds a `Code` outside `grdr-schema`; review that `codes` holds no caller but `codes::generated` | #278; `eval-architecture` on every pull request that touches `crates/grdr-schema/src/codes*` |
| Every error variant has one code | `Coded` with an exhaustive match, and a compile-fail doctest whose impl leaves a variant unmatched (#280 AC-3, moved); ARCH-017 over the error enums, reading `const_name` from `ALL` | #278; #1582 |
| The constants equal the registry and `limits.toml` | The `drift` tests, the `regenerate` test as the one writer, the line-ending tests | #278, #279 |
| The grammars and refusals of sections 4 and 6 | One fixture per refusal | #278, #279 |
| Derived strings have one home | The constants test checks the five strings of every entry against its area, number and the brand namespace; the docs generator, ARCH-017 and the token check read `ALL` | #278; #1636, #1582, #1853 |
| The generator's words are the enums' | It reads `VARIANTS` and `as_str`; the position `match` makes a new variant fail to compile until listed | #278 |
| Every active code has its two tokens | A check in `grdr-interface-gen` that walks `ALL` and fails on a missing `message_token()` or `fix_token()` in the source locale | #1853 |
| An entry never changes its area, number or reason, never leaves, and moves only from `active` to `retired` | A CI check comparing `schema/codes/` at a pull request's base and head, filed on acceptance for lead-agent-kit; until it lands, `eval-diff` on every pull request that touches `schema/codes/` | The item filed on acceptance; review |
| No literal bound in product code | ARCH-019's patterns, outside `limits`, the generated files and tests: `Bytes::new`, `Count::new`, `Millis::new` and `Permille::new` with an integer literal; a `RetrySpec`, `BudgetLimits` or `Backoff` written with an integer literal in any field, and `RetryLimits::new` on one; and a `const` or `static` item of any of these types or `RetryLimits`. The patterns match integer literal tokens, so a value is derived when its expression reads a generated constant, a configuration value or an argument. A literal moved behind a named integer constant passes them, and structure rule S7 in review catches it | #1582; review |
| One copy of the retry rules | The generator validates through `RetryLimits::new`; one fixture per `RetryRule` | #279 |
| No parser in a normal closure | `cargo tree --locked -p grdr-schema -e normal` names no `toml`, `toml_edit`, `serde` or `serde_json` (#278 AC-6) | #278 |
| Layer 0 rules | `cargo check --locked --target wasm32-unknown-unknown -p grdr-schema`; the workspace lints | #278, #279 |
| One definition per type (section 1) | `eval-architecture` on every pull request that adds a public type to a layer 0 to 2 crate; ARCH-007 | Review; #1582 |
| Stability | The `[[crate]]` row of section 11, `rfc-required`, `cargo public-api`, `cargo semver-checks` | The protected-change item filed on acceptance (#1710 R3); #1741 |

### 9. What each item changes
Under #1710 R4, each lead writes these changes into its item before readying it.
- **#278**:
  - R1's `owner` is `design/NN`.
  - R2's keys are those of section 4: `status` replaces `retired`, `anchor` goes, and every key is required.
  - R3's prefix comes from `brand/brand.toml`.
  - R4's `ALL` holds retired entries too, with their status.
  - R6's `Code` gains `status` and `const_name`, and its constructor is private to `codes`.
  - R7 gains the refusals of section 4.
  - The item also builds `CodeStatus`, `ErrorClass`, `ConnectCode` with their `VARIANTS`, the four format constants and `Coded`, taking `Coded` and its compile-fail doctest from #280.
  - AC-4 checks the five derived strings.
- **#279**:
  - R1 is unchanged in its units.
  - R2 adds `owner` and `note` to retry tables, and R1 makes `note` required for bounds.
  - R3 tightens the grammar and refuses a unit suffix.
  - R4's types become those of section 5, with the constructor private to `limits`.
  - R5 gains the refusals of section 6 and the `max_elapsed`, `base` and `timeout` rules, and validates retry tables through `RetryLimits::new`.
  - R9's "constants only" becomes "no parser": the module holds types, constants and one checked constructor.
  - It registers area `LIMITS` and `GRDR-LIMITS-0001`, so its write set gains `schema/codes/areas.toml` and `schema/codes/limits.toml`.
  - AC-1 gains a fixture per new refusal.
- **#280**: keeps `ErrorDetail` and `Code::detail()`, which #1851 now states. `Coded` moves to #278.
- **#18, #383, #282, #284**: the route is #1850, not RFC 0001. #282's tests build `RetryLimits` through `RetryLimits::new`.
- **#510**: the route is #1852.
- **#1768**: the key names and units of section 7.
- **#1582**: ARCH-017 reads `ALL`, and ARCH-019 gains the patterns of section 8.
- **#1636**: the `/codes/<code>` pages walk `ALL`, retired entries included, and render no code string themselves.
- **RFC 0002, RFC 0003 and RFC 0005**: the pointers and row names of section 7, by their author in their next revision.

### 10. Proposed changes to design/03
Each lands after acceptance through an issue whose write set names design/03, filed on acceptance.
- **Section 10, Errors.** "the `code.<code>.message` and `code.<code>.fix` language tokens and a docs anchor" becomes "the `code.<code>.message` and `code.<code>.fix` language tokens and the docs anchor `codes/<code>`, all derived from the code and never written in the registry; an entry's lifecycle is its `status`". The five class meanings of section 3 follow the class list.
- **Section 10, Resource budgets.** A bound's unit is one of `bytes`, `count`, `ms` and `permille`, written as its key and never in its name, and no bound value is reserved to mean unbounded.
- **Section 2, ARCH-019.** The rule gains the patterns of section 8.

### 11. Stability
- `grdr-schema` enters `surfaces.toml` as `experimental` (D-60; ADR-0020; design/03 section 7: every surface starts there) in one row of the `[[crate]]` kind RFC 0005 R6.1 proposes: `name = "grdr-schema"`, `class = "experimental"`, `rfc = "0007"`. The class is the crate's, so no module key is needed. #1851 and #1852 amend this RFC and keep the row. The protected-change item #1710 R3 files after acceptance adds it, once the row kind exists; if RFC 0005 is not accepted, that item adds the row kind with the same three keys.
- `experimental` allows a break in any release, and every change still goes by RFC. A change to a type, a rendered form, a format constant, a registry or `limits.toml` rule, or a generator refusal is an amendment: a new RFC that names RFC 0007, since an accepted RFC never returns to `Review` (RFC 0001, "RFC states").
- Adding or retiring a code, and adding, changing or removing a bound or retry table, is content (sections 4 and 6), not an amendment.
- Retiring a code removes its constant, which breaks a crate that names it. That is allowed while the crate is experimental. The RFC that moves `grdr-schema` to beta decides whether a retired code keeps a deprecated constant for its deprecation release, as a new `CodeStatus` variant.
- The release notes list every change to these modules (design/34 section 10).

### 12. Failure modes
| Failure | Declared outcome | Visible as |
|---|---|---|
| A registry or `limits.toml` entry breaks a rule | Generation stops and writes nothing | One line naming the file, the entry or table, the key, the rule and the fix, in the tests gate on every system |
| The brand namespace is missing or malformed | Generation stops; there is no default prefix | The refusal line |
| A committed generated file is stale | The `drift` test fails | The first differing line and the regenerate command |
| A crate names a code or bound that is not registered | The crate does not compile | rustc names the missing constant |
| An error variant has no code | The `Coded` impl does not compile | rustc's exhaustiveness error at the impl |
| An active code has no `message` or `fix` token | The token check fails (#1853) | The check names the code |
| A `RetryLimits` built at run time breaks a rule | `LimitsError::RetryTable { rule }`, `GRDR-LIMITS-0001` | The caller's error, with its code |
| An owner names no design document, crate or program | Generation stops | The refusal line |

Nothing in either module fails at run time except `RetryLimits::new`, and nothing fails open.

## Surfaces changed
- `grdr-schema` (layer 0, public): module `codes` (`Code`, `CodeStatus`, `ErrorClass`, `ConnectCode`, `Coded`, the format constants, the generated constants and `ALL`) and module `limits` (`Bytes`, `Count`, `Millis`, `Permille`, `Backoff`, `BudgetLimits`, `RetrySpec`, `RetryLimits`, `LimitsError`, `RetryRule`, `BUDGET_SLOTS_MAX` and the generated constants). Class `experimental`.
- The formats `schema/codes/areas.toml`, `schema/codes/<area>.toml` and `limits.toml`, read by the generators.
- The rendered code `GRDR-<AREA>-<NNNN>`, with its prefix from `brand/brand.toml`, its token ids and its anchor `codes/<code>`.
- Content: area `LIMITS` and `GRDR-LIMITS-0001`.
- As proposals: design/03 sections 2 and 10 (section 10) and the `[[crate]]` row of `surfaces.toml` (section 11).
- No spine text, protobuf package, Cedar schema, dependency or same-layer edge changes.

## Alternatives
- **One RFC for the whole scope of #1710.** Rejected for section 1's reasons: #510 cannot be stated yet, `ErrorDetail` waits on RFC 0006 and SP-1, and the open `grdr-model` questions would hold #278 in the same review.
- **Two parts: codes and limits here, and the rest of #1710's scope in one more RFC.** That RFC would wait on SP-1 and #386 through `ErrorDetail` and the manifest, and hold the `grdr-model` types that #383 and #18 need sooner. Rejected for one issue per prerequisite chain.
- **`anchor` as a registry key** (#278 R2). Every anchor would be a function of the code written out by hand, and one could drift from it. Rejected for a derived anchor.
- **Each tool rendering codes from the TOML** (revision 1). The docs generator, ARCH-017 and the token check would each re-implement the padding and the prefix. Rejected for one rendering in the generator, read through `ALL`.
- **`retired = true`** (#278 R2, revision 1). A lifecycle in a flag, which a third state would have to break. Rejected for `status` (S4).
- **A `GRDR` literal in the generator** (revision 1). A second home for a Class A identifier that `brand/brand.toml` already holds. Rejected.
- **A `pub(crate)` constructor on `Code`** (revision 1). Any module of the crate could mint a code. Rejected for a constructor private to `codes`.
- **Public fields or a public constructor on `Code`.** Any crate could make a code the registry lacks, and only ARCH-017's scan would notice. Rejected.
- **A parse from string, or `Display`, on `Code`.** Parsing invites building codes from data, and `Display` invites concatenation into person-facing text (UX6). Rejected, as #278 R6 already does for parsing.
- **Constants in one module per area,** such as `codes::cfg::ADAPTER_NOT_IN_PROFILE`. It works. Rejected for the flat names #278 R4 specified and RFC 0005 cites, which are unique by construction.
- **A table pairing each class with the Connect codes it allows.** RFC 0002 and RFC 0003 pair them freely for good reasons, and the two answer different questions. Rejected.
- **Public fields on `RetryLimits`.** `RetryPolicy::from_limits` would have to be fallible, or trust input nothing checked. Rejected for a checked wrapper.
- **No public constructor for `RetryLimits`.** #282's tests and RFC 0002's executor tests need policies that `limits.toml` does not hold, and `#[cfg(test)]` items do not reach integration tests. Rejected.
- **The retry rules in the generator only.** A run-time constructor would need a second copy. Rejected for one copy in `RetryLimits::new`, which the generator calls.
- **`max_elapsed = 0` meaning "no elapsed limit".** A reserved value, which section 6 forbids. Rejected: 0 is refused, and every policy has a finite elapsed limit.
- **All ones meaning "until the scope ends"** (#1768). TOML cannot write the value, and a reserved number hides a state. Rejected for `Expiry::ScopeEnd` in RFC 0005's own type.
- **An `ns` unit now** (revision 1). No bound needs it: both expiry rows are cache-reuse lifetimes in whole milliseconds, and RFC 0005 R5.5 already converts a millisecond row to the header's nanoseconds. Revision 1 justified it with the fast path's p99 evaluation target, which is a latency target and bounds no row. Rejected; a unit below a millisecond arrives by amendment with the first bound that needs it.
- **The unit in the name,** as RFC 0003 and #1768 wrote it. The unit would be written twice. Rejected.

## Drawbacks
- The slice-0 surface of the two crates is decided in four RFCs instead of one, and readers follow the table of section 1 to find a type.
- #278 grows by `CodeStatus`, `ErrorClass`, `ConnectCode`, `Coded` and the format constants, and #279 by the `LIMITS` area and its new refusals.
- `RetryLimits::new` is public, so a crate can build a retry policy that `limits.toml` does not hold. Only ARCH-019 and review stop it.
- Every item that registers a code waits for an interfaces item that writes its tokens.
- The generator reads `brand/brand.toml`, so a malformed manifest stops code generation as well as the build steps that already read it.
- Retiring a code removes its constant, which breaks a downstream crate that names it.
- Until the CI comparison lands, review alone holds the rule that a registry entry never changes or leaves.

## Unresolved questions
None for this RFC. Open elsewhere:
- Which data source picks `Expiry::ScopeEnd` or `Expiry::After` for the fast path's bundle and session scopes by default (section 7): RFC 0005 (#405), with #1768.
- The `grdr-model` surface (#1850), `ErrorDetail` and `Code::detail()` (#1851), and the lake column manifest type (#1852).
- The code tokens and their check (#1853).

Filed on acceptance: the `surfaces.toml` row (#1710 R3), the CI comparison of `schema/codes/` (section 8) and the design/03 change (section 10).

## Review
How review binds the decision (RFC 0001, "Review binds the decision"; ADR-0036):
- RFC 0007 decides no pinned path, so its decision adds no decision line and no file under `rfcs/evidence/`.
- The review set is the `[kinds] rfc` row of `.claude/risk-tiers.toml` on the base, which names `eval-architecture`. `eval-security` joins it because sections 5 and 6 fix the format of `limits.toml`, a trust-core path (`security/trust-core.paths`). The passing evaluators run on two models (D-63, owner instruction 7). The RFC changes no trust-core file itself; #279, which writes `limits.toml`, takes the full trust-core lane. The nine persona council seats comment on #1710.
- Each verdict by an evaluator of the set, and each seat comment, carries the three role lines of RFC 0001 (#1798):
  - `RFC file:` the blob of this file it read (`git rev-parse <commit>:rfcs/0007-grdr-model-and-grdr-schema-slice-0-surface.md`);
  - `Proposed text: none`, because no pinned path changes;
  - `Base:` the spine pin in force in `rfcs/pins.toml` on the base, `a80859235e7a2a4444648d6fa8d389d78dde6be9`, SHA-256 `8f6ea876777c0121ecec068c0bc4cef45932be45c1c2aff4140712db1e06628d`.
- The decision rests on an `eval-architecture` pass on the blob it decides, with no fail by an evaluator of the set on that blob. Before deciding, the chief architect checks that the seats commented on that blob.
- The file the decision commits differs from that blob only in `State:`, `Decision record:`, lines under `Review` that each hold one comment link, and the `Decision` section.
- The file reaches `main` in `Review` before the commit that decides it, because a file is added only as `Draft` or `Review` (RFC 0001, "RFC states").

Round 1, on revision 1 (RFC file blob `04b07a7`):
- `eval-architecture`, fail, one major and eleven minors: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073130936

Round 2, on revision 2. The verdicts and seat comments on its blob are linked below, one per line.

## Decision
Pending.
