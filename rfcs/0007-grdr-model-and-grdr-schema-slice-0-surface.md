RFC: 0007
Title: The slice-0 public surface of grdr-schema (error codes, the Coded binding and limits), and where each slice-0 type of grdr-model and grdr-schema lives
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #1710
Spine: D-05, D-23, D-31, D-48, D-51, D-60, D-61, D-63, D-66, D-69, P1, P8, P9, P10, P14, P15, P17 (no spine text changes)
Surfaces: the public crate `grdr-schema` (layer 0): modules `codes` and `limits`, their sealed registry types and their generated constants and tables; the formats they are generated from, `schema/codes/areas.toml`, `schema/codes/<area>.toml` and `limits.toml`; the rendered code form `GRDR-<AREA>-<NNNN>` with its language-token ids and docs anchor; the published registry `codes.json`; the error-code area `LIMITS` with one code. As proposals: design/03 sections 2 and 10, one `[[crate]]` row of `surfaces.toml` for `grdr-schema`, and ten `security/trust-core.paths` lines. No dependency, same-layer edge, wire format or Cedar schema changes
Decision record: none yet

To comment, write on issue #1710 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This is revision 3. It answers round 2's verdicts of `eval-architecture`, `eval-security` and `eval-adversarial` and the nine persona council seats, under the orchestrating session's rulings 1 to 11 on #1710 (comment 7073495899) and its ruling 10 on #1848 (comment 7073435306). The comment "RFC 0007 revision 3" on #1710 gives every finding its disposition. The text below is normative on its own. Where it differs from the items it covers, this RFC wins, and section 9 tells each lead what to write back.

## Summary
#1710 asked for one RFC over the slice-0 surface of `grdr-model` and `grdr-schema`. This RFC decides that scope in parts. It states in full the `grdr-schema` surface that #278 and #279 build, and fixes where every other slice-0 type of the two crates lives and which RFC states it: the `grdr-model` surface (#1850), the `ErrorDetail` message and its binding (#1851), and the lake column manifest type (#1852).

Only each module's generated file can build a code, a registry entry, a checked retry policy or a limits row: their constructors take a seal token that only that file can write, and a generated assertion makes any hand-written item that shadows a generated name fail to build. A retired code is metadata with no value a caller can return. A code's area, number, reason, class and Connect code never change once on `main`, and a check that runs from the base build holds that. The prefix comes from the pinned wire namespace of the brand manifest, and the token ids carry no prefix. Every retry field has a ceiling. Every bound has a range, says whether a setting may change it and up to which ceiling, and says whether raising it collects or keeps more. Both modules enter `surfaces.toml` as `experimental`, while the codes themselves are stable wire identifiers from the first release.

## Motivation
#278 has 202 dependants by the #645 count, and #279 builds `limits.toml` and the module that is the only place ARCH-019 lets a bound live. Both cite RFC 0001 as their route, but RFC 0001 adopts the spine text and no crate surface, and the ruling on #1535 holds that `experimental` does not exempt a public crate (D-61, design/30 section 3). RFC 0002 (#1688), RFC 0003 (#1757) and RFC 0005 (#405) already depend on this surface:
- RFC 0002 binds every port error to a code through `Coded` and assigns seven areas, but states no signature for `Code` or `Coded`.
- RFC 0003 proposes `limits.toml` keys such as `ipc.call-max-ms`, which repeat their unit in the name.
- RFC 0005 needs a unit for its fast-path expiry rows. #1768 asked for nanoseconds, with 18,446,744,073,709,551,615 meaning "until the scope ends", which TOML cannot write.
- #1768's keys (`fastpath.eval_cap_steps`) and RFC 0005's ceiling rows failed #279 R3's name grammar.

If nothing changes, #278 and #279 wait on a review of the whole two-crate surface, and three RFCs keep pointing at types nobody has stated.

## Design

### 1. Scope
**Decision.** This RFC states the `codes` and `limits` modules of `grdr-schema` and the formats behind them. The rest of #1710's scope goes to three RFC issues filed from this decision, each with the prerequisites it actually has:

| Part | Prerequisites | Issue | Blocks |
|---|---|---|---|
| `grdr-model`: time, `Entropy`, ids, lanes, `LogSafe`, the retry state types, `InstallProfile`, `Tamper` | Drafting needs nothing; deciding needs this RFC decided | #1850 | #18, #383, #282, #284 |
| `ErrorDetail` and `ErrorClass` in `grdr.common.v1alpha1`, the `codes.json` message type, and `Code::detail()` | RFC 0006 (#1848) and this RFC decided; the SP-1 codec (#368) before the decision | #1851 | #280, #1636's `codes.json` |
| The lake column manifest type in `grdr-schema` | #386 merged, #510 specified, this RFC decided | #1852 | #510 |

Reasons:
1. **Dependency direction.** `grdr-schema` is layer 0 and depends on nothing in this RFC. `grdr-model` is layer 1 and reads `RetryLimits` and `Coded` from it. Deciding the lower layer alone lets #278 and #279 proceed, and the `grdr-model` RFC cites a decided text.
2. **Readiness.** #510 is a stub until #386's field registry format merges, so its type cannot be stated now. `ErrorDetail` is a protobuf package change that imports RFC 0006's options, and `Code::detail()` returns a type whose shape depends on SP-1. Holding `Code` behind either would hold #278 behind SP-1.
3. **Open questions in `grdr-model`.** Drafting this RFC found eight questions in the `grdr-model` half, listed on #1850. A finding on any of them would hold the code registry in the same review.
4. **Review size.** Every round re-reads the whole text, so a text with one concern costs less per round.

**Where each type lives.** No type below gets a second definition in another crate (P17).

| Type | Crate and module | Stated by | Built by |
|---|---|---|---|
| `Code`, `CodeEntry`, `CodeStatus`, `ErrorClass`, `ConnectCode`, `Coded`, the code constants, `codes::ALL` | `grdr_schema::codes` | Section 3 | #278 |
| `Bytes`, `Count`, `Millis`, `Permille`, `Backoff`, `BudgetLimits`, `RetrySpec`, `RetryLimits`, `BoundEntry`, `BoundUnit`, `BoundScope`, `BoundEffect`, `LimitsError`, `RetryRule`, `BUDGET_SLOTS_MAX`, the limit constants, `limits::rows`, `limits::ALL` | `grdr_schema::limits` | Section 5 | #279 |
| `Code::detail()`, `ErrorDetail`, the protobuf `ErrorClass`, the message type of `codes.json` | `grdr_schema::codes` or `grdr-proto`, and `grdr.common.v1alpha1` | #1851 | #280; #1636 |
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
- R2. **Layer 0.** `codes` and `limits` do no I/O, read no clock or randomness and call no host, so a build that links them, an embedded one included, makes no network call (D-60). No async runtime or Cargo feature. The crate builds for `wasm32-unknown-unknown` (ARCH-003). Arithmetic is checked or saturating (`#![deny(clippy::arithmetic_side_effects)]`), no non-test code has a panic path, and `unsafe` is forbidden.
- R3. **No allocation.** Every type here is `Copy` and holds integers, `bool`, closed enums and `&'static` data.
- R4. **No rendering.** The crate is `renders = "none"`. No type implements `Display`. A code is read with `as_str`, and it reaches a person only through its `message` and `fix` language tokens (D-69, UX6):
  - an argument of either token is a `LogSafe` value of class `structural`, never a path, argument vector, host or principal (P8);
  - the code itself, where a message shows it, is an identifier-class argument: formatted by `grdr-strings` and `@grdr/i18n` in a left-to-right isolate, with ASCII digits whatever the locale's numbering system, never through `:number`, and copied as the plain `GRDR-CFG-0007` with no isolate marks;
  - the `as_str` words of `CodeStatus`, `ErrorClass`, `ConnectCode`, `RetryRule` and the three bound enums are identifiers for the registry and the wire, never display words: a person sees their `present()` labels from the presentation registry (UX5).
- R5. **Generated files.** `src/codes/generated.rs` and `src/limits/generated.rs` are generated by test code under `crates/grdr-schema/tests/gen/` and committed.
  - The ignored `regenerate` test of each target is their only writer, and a `drift` test in `cargo test --workspace --locked` fails when a committed file differs from a fresh generation, printing the first differing line and the exact regenerate command (a fixture shows it).
  - Each generated file starts with a header that names its source files and that command and says it is not to be edited.
  - Output is byte-identical on Linux, macOS and Windows: input line endings normalised, LF out, sorted, no timestamp or path (#278 R4, R5, R8; #279 R4, R6, R10).
  - `schema/codes/areas.toml`, each area file and `limits.toml` start with a header comment that states the never-change rule of their entries and how to retire one, and names the step list of R11.
- R6. **One home for each derived string and each word list.** The generator renders every code string once. `grdr-archlint` (ARCH-017), the docs generator (`/codes/<code>` pages and `codes.json`) and `grdr-interface-gen` (the token check) are `tool` crates (ARCH-001). They link `grdr-schema` and read `codes::ALL` and `limits::ALL` through their accessors, and none renders a code from the TOML itself. Each closed enum is declared by one macro list that gives its variants, their `as_str` words and `VARIANTS` together, so the three cannot disagree, and the generator takes every word from `VARIANTS` and `as_str`, never from a list of its own.
- R7. **Format constants.** The numbers that define the formats are not tunables, as RFC 0002 Rule 7 treats its 255-byte identifier ceiling. Changing one changes a format, which is an amendment (section 11), so none is a `limits.toml` row.
  - The registry grammar's numbers (an area of 2 to 8 letters, a reason of at most 63 bytes, a number from 1 to 9999) are the generator's own and read by nothing else, so they are not public items. Fixtures pin each boundary (#278 AC-1).
  - In `limits`, `Permille::ONE` (1000 permille) and `BUDGET_SLOTS_MAX` (1000) are public, because `grdr-model`'s `RetryPolicy` and `RetryBudget` read them (#1850). The retry ceilings of section 5 are read only by `RetryLimits::new`, so they are private constants of `limits::registry`, each pinned by a fixture at the ceiling and one above it (#279 AC-1).
- R8. **Data classes and assurance.** Every type, registry field and limit is `structural` (P8). No action class changes `visibility`, `control`, `on_failure` or `tamper` (P1).
- R9. **Scale.** Codes and limits are compile-time constants. They add no request, byte, connection or store call at any fleet size (P15). What an error costs on the wire is #1851's.
- R10. **Construction.** Each module has a defining submodule, `registry`, and a generated submodule, `generated`, both private and re-exported by the module.
  - `registry` holds the sealed types (`CodeEntry` and `Code`; `RetryLimits` and `BoundEntry`) with private fields, their accessors, their constructors, the retry rules and the parity comparisons, and nothing else. It has no child module, so a struct expression of a sealed type compiles nowhere else (E0451).
  - Every constructor of a sealed type takes a `generated::Seal`, except `RetryLimits::new`, which is public and checks every rule. The seal is a tuple struct declared in `generated` whose one field is private to `generated`. No other module can write `Seal(())`, so a call from the parent module or any sibling fails to compile (E0603). Outside the crate the constructors are private (E0624).
  - The module re-exports `generated` by glob, and a hand-written item of the same name would win over the glob without a warning. So for every generated constant, for `ALL` and for every row of `limits::rows`, `generated` holds a `const` assertion that the item the module's public path names has the generated type and equals the generated value field by field. A shadow of another value fails to compile (E0080), and one of another type fails too (E0308).
  - `registry`, `generated`, the generators and the crate manifest are trust core (section 8), so the one file where a sealed value can be written by hand changes only with the full lane.
- R11. **The contributor's path.** `crates/grdr-schema/AGENTS.md` carries two step lists, "Add an error code" (#278) and "Add a limit" (#279): the files in order, the key grammar, the regenerate command, what the pull request names for `rfc-required`, and for a code a default pairing of class and Connect code for a first entry (`input` with `invalid_argument`). The lint messages (section 8), the generated-file headers and the doc comment on `Code` point to them.

### 3. The `codes` module
```rust
// grdr_schema::codes
// One macro list per enum gives its variants, their words and VARIANTS.
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
//   pub const VARIANTS: &'static [Self];        every variant, in declaration order
//   pub const fn as_str(self) -> &'static str;  "active", "input", "invalid_argument", ...

pub trait Coded { fn code(&self) -> &'static Code; }

// codes::registry, re-exported by codes
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct CodeEntry { /* private: the registry keys and the five rendered strings */ }
impl CodeEntry {
    pub const fn area(&self) -> &'static str;                // "CFG"
    pub const fn number(&self) -> u16;                       // 7
    pub const fn reason(&self) -> &'static str;              // "ADAPTER_NOT_IN_PROFILE"
    pub const fn status(&self) -> CodeStatus;
    pub const fn class(&self) -> ErrorClass;
    pub const fn connect(&self) -> ConnectCode;
    pub const fn retired_in(&self) -> Option<&'static str>;  // "0.3.0", retired entries only
    pub const fn replaced_by(&self) -> Option<&'static str>; // "CFG-0012", retired entries only
    pub const fn as_str(&self) -> &'static str;              // "GRDR-CFG-0007"
    pub const fn const_name(&self) -> &'static str;          // "CFG_ADAPTER_NOT_IN_PROFILE"
    pub const fn message_token(&self) -> &'static str;       // "code.cfg_0007.message"
    pub const fn fix_token(&self) -> &'static str;           // "code.cfg_0007.fix"
    pub const fn anchor(&self) -> &'static str;              // "codes/GRDR-CFG-0007"
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Code { /* private: the &'static CodeEntry of one active entry */ }
impl Code {
    pub const fn entry(&self) -> &'static CodeEntry;
    pub const fn as_str(&self) -> &'static str;
    pub const fn class(&self) -> ErrorClass;
    pub const fn connect(&self) -> ConnectCode;
}

// codes::generated, re-exported by codes
pub const CFG_ADAPTER_NOT_IN_PROFILE: Code = /* built with the seal, active entries only */;
pub const ALL: &[CodeEntry] = &[/* every entry, active and retired, in area then number order */];
// plus one parity assertion per constant and one for ALL (R10)
```

`CodeEntry` is one row of the registry. `Code` is the value an error returns, and one exists only for an active entry.
- Neither implements `Default`, `Deserialize` or any parse from a string. Both are built only in `generated` (R10). A crate that needs a code names a generated constant, so a code the registry does not hold cannot exist.
- `as_str` renders `<PREFIX>-<AREA>-<NNNN>`, with the number zero-padded to four digits. `const_name` is `<AREA>_<REASON>`, the constant's identifier.
- The token ids are `code.<area>_<nnnn>.message` and `code.<area>_<nnnn>.fix`, with the area in lower case: `code.cfg_0007.message`. They fit the token id grammar, `<namespace>.<area>.<name>` in lower snake case, and carry no prefix, so a translation never depends on the namespace (D-69). An area holds no underscore, so the id is unambiguous.
- The anchor is `codes/<as_str>`, the code's page below the docs site root, with no locale in it (design/34 sections 5 and 6). A link is `{docs_base_url}/<locale>/codes/<code>`, and `docs.base_url` may be `local`, the installed version's pages, so a code link never needs a host an offline machine cannot reach (design/34 section 6).
- The generator computes these five strings once, and every other tool reads them from `ALL` (R6), so none can disagree with the code (P17).
- Equality and hashing cover every field.

**The prefix.** `<PREFIX>` is `[identity] namespace` of `brand/brand.toml`, upper-cased by ASCII rules: `GRDR` today. Ruling 10 on #1848 makes that value the wire namespace:
- its grammar is `[a-z]{2,8}`, ASCII lower-case letters only, so upper-casing has one result and the rendered code holds exactly two hyphens;
- it is pinned: a white-label or partner manifest keeps the upstream value, and the brand manifest loader (#1856, LBC-3) refuses any other, so a rebuilt distribution keeps the codes its support pages quote (design/26 section 9: reason codes are unchanged in a rebuild);
- the generator reads it through #1856's loader once that lands. Until then it reads the one key with its `toml` dev-dependency and applies the grammar. A missing or malformed namespace stops generation, with no default;
- the committed generated file holds every rendered string, so a swapped manifest also fails the drift test, and regenerating changes a trust-core file (section 8);
- design/36 section 2 makes `GRDR-` a Class A identifier: an RFC may move it for everyone before the first release, and nothing changes it after. Constant names and token ids carry no prefix, so such a move regenerates only the rendered strings and anchors. Until the D-66 search is recorded, the namespace is provisional (ADR-0003, proposed).

`CodeStatus` is an entry's lifecycle. `Active` entries have a `Code` constant. `Retired` entries are `CodeEntry` values in `ALL` only, with no `Code` and no constant, so no `Coded` impl can return one. They stay in `ALL` so their pages, tokens and support quotes keep working, and they never return to `Active`. A third state, such as a deprecated constant kept for one deprecation release, arrives as a new variant by amendment (section 11).

`ErrorClass` tells the caller of our code what to do next. It is the registry's `class` word:
- `input`: the caller's request or data is wrong, and the same input fails the same way;
- `policy`: the request is well formed and a rule, a policy, a verification or a quota refused it; this is a decision, not a fault. A bound reached by correct use, such as an organisation at its quota, is `policy` with Connect `resource_exhausted`. A `policy` code's `fix` names the exception route, or says there is none (design/34 section 7);
- `retryable`: a transient fault, and the same call may succeed later under its retry policy. A lock or contention that the other process releases is retryable. A refusal by software outside the product, such as an incumbent EDR denying a file open or ending our process, is not: it is `fatal`, its `fix` names the coexistence step (the coexistence pack, D-23), and it is never retried unchanged;
- `fatal`: the operation cannot complete, and repeating it unchanged does not help; the next step is the one its `fix` token names, such as a configuration change, a coexistence exclusion or a new acquisition;
- `internal`: a defect in the product, reported and never retried. A bound that only a defect can cross is `internal`. An `internal` code's `fix` names the support-bundle command through the CLI registry (ARCH-023), never as a literal, and the support contact from the brand manifest's `links.support_contact_default` (design/36), so a partner's build names its own.

`ConnectCode` is the status a remote client of the API sees, one of the sixteen error codes of the Connect protocol, in its snake-case spelling (P10). Class and Connect code answer different questions, and neither is derived from the other. RFC 0002 and RFC 0003 pair them freely: `GRDR-WIRE-0002 BODY_TOO_LARGE` is `internal` with `invalid_argument`, because only a defect in our own sender reaches it. One pairing is refused: `unavailable` with any class but `retryable`, because a remote client retries `unavailable` while a local caller would treat the code as final. No code in RFC 0002 or RFC 0003 pairs them otherwise.

An error code identifies a failure of the product's own code. It never names a finding, a rule or a Verdict reason, and it is never a suppression key for a finding. Findings take the ids of #1850, and rules take `RuleId` from the policy module (#212). A stored record or an export that carries a code carries its `as_str`, never a token id or a message.

`CodeStatus`, `ErrorClass` and `ConnectCode` are exhaustive enums. A new value is an amendment, and it fails every exhaustive match until handled.

`Coded`:
- Every error type implements it with one exhaustive `match`, no wildcard arm, one generated constant per variant.
- A variant that only wraps another coded error returns that error's code (RFC 0005 R4.6).
- Callers act on `code().class()`, never on the variant (RFC 0002 Rule 8).
- `code` returns a reference to a generated constant, which Rust promotes to `'static`. The trait is object safe.
- The exceptions are the ARCH-017 exemption list of `architecture.toml`, which is not on `main`. RFC 0002 section 14 proposes it as a protected change, and RFC 0005 R4.1 adds per-variant entries to it. Until it lands, the exceptions are the types an RFC in `Accepted` state exempts by name, and review applies the rule, because ARCH-017 is not built yet (#1582).

`ALL` lists every entry, active and retired, ordered by area bytes and then number. Nothing in this module looks a code up by its string. A consumer that holds a rendered code from the wire compares strings or walks `ALL`. A newer peer's code that `ALL` does not hold is shown as its string with its `/codes/<code>` link and no message, and never as success (P9).

**`codes.json`.** The docs generator (#1636) writes every entry of `ALL`, with every key of section 4 and the five derived strings, to `codes.json` beside the `/codes/` pages. It is a release artefact of every version: it ships wherever that version's docs ship, the site, the `grdr-docs` package and the air-gap bundle (design/34 section 6). Its message type is #1851's, so it is a protobuf message in proto3 JSON (ARCH-022). A SIEM or SOAR rule that cannot link `grdr-schema` reads it.

### 4. The code registry format
`schema/codes/areas.toml` holds one table per area:
```toml
[area.CFG]
subsystem = "configuration"
owner = "design/03"
```
- `AREA` is two to eight upper-case ASCII letters: `[A-Z]{2,8}`.
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

[[code]]
number = 8
reason = "PROFILE_NAME_LEGACY"
status = "retired"
class = "input"
connect = "invalid_argument"
retired_in = "0.3.0"
replaced_by = "CFG-0007"
```
Keys:
- `number`: 1 to 9999; required;
- `reason`: UPPER_SNAKE per AIP-193, `[A-Z][A-Z0-9_]*[A-Z0-9]`, at most 63 bytes; required;
- `status`, `class`, `connect`: a word of `CodeStatus::VARIANTS`, `ErrorClass::VARIANTS` and `ConnectCode::VARIANTS`; required;
- `retired_in`: required on a retired entry and refused on an active one. It is the `version` of `crates/grdr-schema/Cargo.toml` on the base of the pull request that retires the entry, so the entry has a constant in that release and none in any later one. The release notes map it to the product release (design/34 section 14);
- `replaced_by`: optional on a retired entry and refused on an active one. It names the entry that replaces this one as `<AREA>-<NNNN>`, with no prefix.

There is no `anchor` key, because the anchor is derived (section 3), and no `retired` flag, because `status` holds the lifecycle. Both change #278 R2.

The generator refuses each of these, names the file, the entry and the rule, and writes nothing:
- #278 R7's list: a file with no area row, a number repeated within its area (retired entries included), a reason repeated within its area, an area or a reason outside its grammar, a word outside its enum's `VARIANTS`, a number outside 1 to 9999, an unknown key;
- a missing key, or a value of the wrong TOML type;
- an area row with no file, or whose file holds no entry;
- an `owner` that resolves to no document or to more than one;
- `connect = "unavailable"` with a class other than `retryable`;
- `retired_in` or `replaced_by` on an active entry, a retired entry with no `retired_in`, a `retired_in` that is not a SemVer version, and a `replaced_by` that names no entry or names its own;
- a missing or malformed `[identity] namespace` in `brand/brand.toml`.

Two constant names cannot collide: an area holds no underscore, and a reason is unique within its area. `codes` declares no other public constant, so no generated name can meet a hand-written one, and the parity assertions of R10 fail the build if one is ever added.

**The registry check.** The generator sees one snapshot, so it cannot see an entry change between two of them. #278 builds a second check with the registry, the ignored test `history` in `crates/grdr-schema/tests/codes_gen.rs`. It runs from the base build: CI checks out the pull request's base, builds that, and points the base's `history` test at a copy of the head's `schema/codes/` as data, never running the head's code, as `rfc-required` does (#1741). It refuses:
- deleting an entry, an area file or an area row;
- reusing a number;
- setting a retired entry back to `active`;
- any change to `area`, `number`, `reason`, `class` or `connect` on an existing entry;
- a change to `retired_in` once set, a change to `replaced_by` once set, a retirement whose `retired_in` is not the base's `grdr-schema` version, and a new `replaced_by` that names a retired entry, so the chain of replacements always ends at an active entry.

When it cannot read the base's registry or the head's files, it fails with "could not look" and never passes. The gate item filed on acceptance wires the job (section 8). That item comes after #278 and blocks every later item that changes `schema/codes/`, so every base the job reads holds a registry.

**Content, not surface.** The registry is content of the mechanism this RFC fixes (P14).
- Adding an entry, or an area with its first entry, needs no RFC of its own. The item that first constructs the code adds it and regenerates, and its pull request names RFC 0007 for `rfc-required`. Because the generated file is trust core, that pull request takes the full lane (section 8).
- The item that registers a code may write the code's two source-locale tokens in the same pull request, in `interface/strings/src/code.mf2.toml`, which its write set then names; `eval-ux` judges them there. An item that does not write them is blocked by the interfaces item that does, so the token check never fails on `main`. Translations follow through `impl-l10n` (D-69).
- An RFC that assigns codes fixes what it states, and the item copies it. RFC 0002 section 11 and RFC 0003 section 9 fix numbers, reasons, classes and Connect codes. RFC 0005 R4.3 and R4.4 name the areas `FASTPATH` and `COMPILE` and the three `COMPILE` reasons, and leave the rest to the items that register them: #427 for `FASTPATH`, and #71 or #414 for `COMPILE`. Every area these RFCs name, `TENANT`, `STORE`, `BLOBS`, `JOBS`, `BUS`, `REL`, `EVENTS`, `WIRE`, `PEER`, `FASTPATH` and `COMPILE`, fits the grammar.
- Otherwise an item takes the next number in its area: one above the highest present, retired entries included. Two items that add to one area at once both append to one file, so the second conflicts and rebases.
- An entry on `main` never changes its area, number, reason, class or Connect code, and is never deleted. Its status moves only from `active` to `retired`. Callers act on class, so a new class or Connect code is a new meaning: the item retires the entry, with `replaced_by` naming a new entry under the next number, and the release notes list both (design/34 sections 10 and 14).

### 5. The `limits` module
```rust
// grdr_schema::limits
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Hash)]
pub struct Bytes(/* private */ u64);
impl Bytes { pub const fn new(value: u64) -> Bytes; pub const fn get(self) -> u64; }
// Count (u64), Millis (u64) and Permille (u32) have the same derives, `new` and `get`.
impl Millis { pub const fn as_duration(self) -> core::time::Duration; }
impl Permille { pub const ONE: Permille; } // 1000 permille

pub const BUDGET_SLOTS_MAX: u16 = 1000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Backoff {
    Exponential { base: Millis, factor: Permille, cap: Millis },
    Schedule { delays: &'static [Millis], jitter: Permille },
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

// One macro list each, as in codes: variants, words and VARIANTS.
pub enum BoundUnit { Bytes, Count, Ms, Permille }          // "bytes", "count", "ms", "permille"
pub enum BoundScope { Fixed, Setting, Ceiling }            // "fixed", "setting", "ceiling"
pub enum BoundEffect { None, Collection, Retention }       // "none", "collection", "retention"

// limits::registry, re-exported by limits
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RetryLimits { /* private: a RetrySpec that passed every rule */ }
impl RetryLimits {
    pub fn new(spec: RetrySpec) -> Result<RetryLimits, LimitsError>;
    pub const fn spec(&self) -> &RetrySpec;
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct BoundEntry { /* private: one [bound.<name>] row */ }
impl BoundEntry {
    pub const fn name(&self) -> &'static str;          // "ipc.frame-max"
    pub const fn unit(&self) -> BoundUnit;
    pub const fn value(&self) -> u64;
    pub const fn min(&self) -> u64;
    pub const fn max(&self) -> u64;
    pub const fn scope(&self) -> BoundScope;
    pub const fn effect(&self) -> BoundEffect;
    pub const fn key(&self) -> Option<&'static str>;     // a setting's grdr.config key
    pub const fn ceiling(&self) -> Option<&'static str>; // a setting's ceiling row
    pub const fn clamp(&self, value: u64) -> u64;        // into [min, max]; total
}

#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LimitsError { RetryTable { rule: RetryRule } }
impl Coded for LimitsError { /* RetryTable { .. } => &LIMITS_RETRY_TABLE_INVALID */ }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum RetryRule {
    MaxAttemptsZero, MaxAttemptsAboveCeiling, MaxElapsedZero, MaxElapsedAboveCeiling,
    BaseZero, FactorBelowOne, FactorAboveCeiling, CapBelowBase, CapAboveElapsed,
    ScheduleEmpty, ScheduleTooLong, ScheduleDecreasing { index: u16 }, ScheduleLastZero,
    ScheduleAboveElapsed, JitterAboveOne,
    BudgetRatioAboveOne, BudgetWindowZero, BudgetWindowAboveCeiling, BudgetSlotsOutOfRange,
    BudgetWindowNotDivisible, BudgetIntervalZero, BudgetIntervalAboveWindow,
    TimeoutZero, TimeoutAboveElapsed, BreakerFailuresZero, BreakerFailuresAboveCeiling,
}
impl RetryRule { pub const fn as_str(self) -> &'static str; } // "schedule_decreasing", ...

// limits::generated, re-exported by limits
pub const IPC_FRAME_MAX: Bytes = Bytes::new(2_097_152);
pub mod rows { pub const IPC_FRAME_MAX: BoundEntry = /* built with the seal */; }
pub const ALL: &[BoundEntry] = &[/* every row, in name order */];
// one per [retry.<name>] table, once its owning document adds it (#279 R8); for example:
pub const FASTPATH_RELOAD: RetryLimits = /* built with the seal, checked at generation */;
// plus one parity assertion per constant, per row and for ALL (R10)
```

Unit types:
- A unit type is a plain amount in its unit. `new` is public and infallible, because tests and values derived at run time need it. ARCH-019 forbids an integer literal in its operand outside `src/limits/generated.rs` and test code (section 8), so every bound in product code is a generated constant or read from configuration, a peer or an argument. A bound derived from another is a row of its own (P14).
- The unit types derive `PartialOrd` but not `Ord`, so the panicking `Ord::clamp` is not available on them. The one clamp is `BoundEntry::clamp`, which never panics, because the generator checks `min <= max` (section 6).
- `Millis::as_duration` is total.
- `Permille` is a ratio in thousandths and may exceed `Permille::ONE`, as a backoff factor does.

How a person reads each unit, for the interfaces squad, which owns the formatting and the scale rule (#1853); the crate itself formats nothing (R4):

| Type | Formatted by | Rule |
|---|---|---|
| `Bytes` | `:unit` with a byte unit | One scale for every surface, decided once by #1853, so 2,097,152 bytes never shows as "2 MB" on one surface and "2 MiB" on another |
| `Millis` | `:grdr:duration` | The locale's own duration units and digits |
| `Count` | `:integer` | With plural rules |
| `Permille` | `:number` as a percent or as a multiplier, chosen by the field | A backoff factor of 1500 shows as a multiplier, a budget ratio of 100 as a percent |

`RetryLimits`:
- `new` checks the rules in `RetryRule` order and returns the first that fails:
  - `max_attempts` of 0, or above 10,000;
  - `max_elapsed` of 0, which would give up before any retry, or above 604,800,000 ms. A policy that never retries says so with `max_attempts = 1`, its one spelling;
  - an exponential `base` of 0, which would make every delay 0 and leave no backoff; a `factor` below `Permille::ONE` or above 10,000 permille; a `cap` below its `base` or above `max_elapsed`;
  - an empty schedule, one longer than 64 entries, one that decreases at `index`, one whose last delay is 0, one whose last delay is above `max_elapsed`, or a `jitter` above `Permille::ONE`;
  - a budget `ratio` above `Permille::ONE`, a `window` of 0 or above 86,400,000 ms, `slots` of 0 or above `BUDGET_SLOTS_MAX`, a `window` that is not a multiple of `slots`, or a `min_interval` of 0 or above `window`;
  - a `timeout` of 0, which would fail every attempt at once, or above `max_elapsed`, so one attempt cannot outlast the policy;
  - `breaker_failures` of 0, or above 100, so the breaker always opens.
- Every field therefore has an upper ceiling from a format constant, directly or through `max_elapsed` and `window` (R7). The hint a server sends is bounded too, because `next` never returns a delay longer than the remaining elapsed allowance (#282 R7).
- A schedule's last delay repeats past its end, until `max_attempts` or `max_elapsed` ends the policy (#282 R4), and it times the breaker (#282 R9). So the last delay may not be 0. A leading 0 stays possible, so one immediate retry is still expressible.
- `jitter` makes a schedule's delay a uniform draw from `[d - d * jitter / 1000, d]` for a scheduled delay `d`: 1000 is full jitter and 0 is none, so no jitter is a choice the table writes. An exponential policy always draws in `[0, ceiling]`, full jitter (P15 mechanism 2, design/22 section 2.7), and has no `jitter` key.
- `new` is the one copy of the rules, in `limits::registry`. The generator calls it on every `[retry.<name>]` table before it writes the constant, so a committed constant has passed it, and the drift test runs it again on every test run.
- The generated constants use a constructor that takes the seal and skips the checks (R10), so they cannot fail at run time.
- Product code reads a named policy only through `RetryPolicy::from_limits` (#1850). A retry table that is run-time content, such as a provider-scoped table for one integration target, is built through `new` from configuration values, which hold no literal, and a refusal is `GRDR-LIMITS-0001`. That changes no format (seat 4).
- A policy that must keep trying, such as the uplink's, gives up at its `max_elapsed` and reports the give-up (P9); the caller decides whether a new episode starts (design/22 section 2.7).

`LimitsError` is the crate's one error enum, `#[non_exhaustive]`. `RetryTable` binds to a new area, `LIMITS` (subsystem: bounds and retry policies; owner: `design/03`):

| Code | Reason | Class | Connect | Bound by | Next step (`code.<code>.fix`) |
|---|---|---|---|---|---|
| `GRDR-LIMITS-0001` | `RETRY_TABLE_INVALID` | internal | `internal` | `LimitsError::RetryTable` | A defect: a retry policy was built from values `limits.toml` would refuse. Run the support-bundle command and send it to the support contact, with the rule the error names |

#279 registers the area and the entry, since it constructs the code (ARCH-017), and may write its two source-locale tokens from the text above (section 4). The rule reaches the token as its `as_str` word, an identifier-class argument, with `index` as an integer argument.

### 6. The `limits.toml` format
Two table families, `[bound.<name>]` and `[retry.<name>]`.

Names:
- A name is dot-separated segments, each `[a-z][a-z0-9]*(-[a-z0-9]+)*`. This tightens #279 R3, so no segment ends in a hyphen or holds two in a row.
- No hyphen-separated word of any segment is a unit word: `b`, `byte`, `bytes`, `kb`, `kib`, `mb`, `mib`, `gb`, `gib`, `count`, `ns`, `us`, `ms`, `millis`, `s`, `sec`, `secs`, `second`, `seconds`, `minute`, `minutes`, `h`, `hour`, `hours`, `day`, `days`, `permille`, `percent` or `pct`. The unit is written once, as the key, so a name does not repeat it. `min` stays allowed, because it also means "minimum".
- No segment equals a key of the format: `bytes`, `count`, `ms`, `permille`, `min`, `max`, `scope`, `effect`, `key`, `ceiling`, `owner`, `note`.
- A row is the table its full dotted name reaches. A table that holds a unit key holds no sub-table, and every other table under `bound` or `retry` holds only sub-tables, so `[bound.ipc]` cannot be both a row and the parent of `[bound.ipc.frame-max]`.
- The generated identifier upper-cases the name and replaces `.` and `-` with `_`. Two names that map to one identifier are refused, across both families.

`[bound.<name>]` keys:

| Key | Required | Meaning |
|---|---|---|
| `bytes`, `count`, `ms` or `permille` | exactly one | The row's amount in that unit: the bound itself, or a `setting`'s default |
| `min`, `max` | yes | The range, in the same unit. `min <= value <= max`. There is no default for `min`, so a value of 0 needs `min = 0` written |
| `scope` | yes | A word of `BoundScope::VARIANTS` |
| `effect` | yes | A word of `BoundEffect::VARIANTS` |
| `key` | a `setting` only | The `grdr.config` key whose default this row is |
| `ceiling` | a `setting` only | The name of the `ceiling` row that caps it |
| `owner` | yes | `design/NN`, resolving as an area's owner does |
| `note` | yes | One line of English, at most 200 bytes and with no control character, that says what the bound limits |

`scope`:
- `fixed`: a release is the only change. No configuration key sets it. A value a peer sends in its place or against it, such as a field of the server's `Schedule` (design/22 section 2.7) or a blob header's cap (RFC 0005 R5.3), is clamped or refused by its consumer against the row.
- `setting`: the default of the `grdr.config` key `key` (design/03 section 9). At run time the key's value is clamped into `[min, max]`, and the generator requires `max` to be at most the value of the row `ceiling` names, so the ceiling bounds the whole range. The configuration resolver (#1591) clamps through the row, and `grdr config explain` and `grdr doctor` (#1289) show the effective value and where it came from.
- `ceiling`: the cap of one or more `setting` rows. A `ceiling` row that no `setting` names is refused, since it is then `fixed`.

`effect` says what raising the value does, and an author writes the bound in that direction:
- `none`: it changes no collection or retention, such as a frame cap or a memory target;
- `collection`: the product captures, keeps on the device or uploads more of what a developer does, such as an argument capture size;
- `retention`: records are kept longer.

A row whose `effect` is not `none` is a `setting` or a `ceiling`, and a `setting` has its ceiling's effect, so an organisation can raise it only through its own setting. Raising one is widening under D-31:
- a release that raises its value, `max` or ceiling leaves every deployed device on the effective value it had; the higher value takes effect only as the organisation's own signed setting, through D-31's step-up, and never above the ceiling (#1591);
- operator-signed deployment configuration may only lower it (design/03 section 9, layer 1);
- a pull request that adds such a row or changes its value, range, ceiling or effect gets a `persona-privacy-officer` comment on its issue before it lands, which the orchestrating session asks for and `eval-security` checks in the diff, and its `[release_note]` names the bound with its old and new values, category `security`;
- the disclosure surface (D-51) and `grdr status` (#1639) show its effective value through the same resolver, which reads its row from `limits::ALL`, and hold no copy of it (P17).

Values:
- Every amount, `min` and `max` included, is a non-negative TOML integer, which TOML caps at 2^63 - 1. A `permille` amount fits `u32`.
- A bound is the finite amount it names. The format has no value meaning "unbounded" or "until an event", and `max` gives every row a stated ceiling. Such a choice is behaviour, carried by the consumer's own type and set from a data source that holds a choice (P14), never by a reserved number. A state hidden in a number is what structure rule S4 forbids.
- There is no unit below a millisecond, because no bound needs one: section 7 settles the one candidate in `ms`. A unit such as `ns` arrives by amendment with the first bound that needs it.

`note` is reference prose, as a proto comment is. The generator writes it into no Rust file, so no product surface can read it. The `limits.toml` reference page (DOC-2, #1065) shows each row's name, unit, value, range, scope, effect, key, ceiling, owner and note, so a reader learns what a bound is and whether a setting may change it without reading source. It takes the values from `limits::ALL`, and `owner` and `note` from `limits.toml`, matched by name, and fails on a name found in only one of them. It shows `note` inside `lang="en" dir="ltr"` and renders it as text, never as MDX. `note` is not a language token (D-69). A screen that describes a limit uses a language token with its own `desc`.

`[retry.<name>]` holds #279 R2's keys, mapped onto `RetrySpec`, plus `jitter_permille` for a schedule, `owner` and `note`, all required:

| Keys | Field |
|---|---|
| `kind = "exponential"` with `base_ms`, `factor_permille`, `cap_ms`, or `kind = "schedule"` with `delays_ms` and `jitter_permille` | `backoff` |
| `max_attempts`, `max_elapsed_ms`, `honour_hint`, `timeout_ms`, `breaker_failures` | the field of the same name |
| `budget_ratio_permille`, `budget_window_ms`, `budget_slots`, `budget_min_interval_ms` | `budget` |
| `owner`, `note` | not generated; as for a bound |

The generator refuses, naming the file, the table, the key and the rule:
- every `RetryRule`, through `RetryLimits::new`, and #279 R5's other refusals;
- a name outside the grammar above;
- a missing key, an unknown key, or a value of the wrong TOML type, such as `bytes = 2097152.0`;
- a value that is negative or does not fit its field's type in section 5 (`u32` for `permille`, `max_attempts` and `breaker_failures`, `u16` for `budget_slots`);
- a `min` above the value or a value above `max`, so a value of 0 needs `min = 0`;
- a `key` or `ceiling` on a row that is not a `setting`, a `setting` without both, a `ceiling` that names no row or names one whose scope is not `ceiling` or whose unit differs, a `setting` whose `max` is above its ceiling's value, and a `ceiling` row no `setting` names;
- an `effect` other than `none` on a `fixed` row, and a `setting` whose effect differs from its ceiling's;
- a `note` that is empty, longer than 200 bytes or holds a control character, and an `owner` that resolves to nothing;
- a backoff key of the other kind, such as `delays_ms` under `kind = "exponential"`, or `jitter_permille` under it.

The seed is #279 R7's rows, each now with `min`, `max`, `scope` and `effect`. No retry table is seeded (#279 R8). Adding or changing a row is content in an item whose write set names `limits.toml`, which is trust core (D-63), and its pull request names RFC 0007. Anyone may open that pull request; it lands only through the full lane. Removing a row removes its constant, which fails the build of every crate that names it.

### 7. What this settles for other RFCs and items
- **RFC 0005 (#405).** Its rows fit section 6 as its R5.1, R5.3, R2.18 and R2.19 now state them:
  - `fastpath.eval-cap` and `fastpath.path-max` in `count`, and `fastpath.expiry-bundle` and `fastpath.expiry-session` in `ms`, which `from_limits` converts to the header's nanoseconds with checked arithmetic (R5.1);
  - the ceiling rows `fastpath.host-eval-cap-ceiling` and `fastpath.host-path-max-ceiling` in `count`, and `fastpath.reload-settle` in `ms`, each `scope = "fixed"` and `effect = "none"`, because no setting names them (R5.3, R2.19);
  - `[retry.fastpath-reload]`, `kind = "exponential"` with `honour_hint = false` (R2.18), owned by design/26.
- **"Until the scope ends".** RFC 0005 owns it, in R5.2 and R5.2a, as `Expiry::ScopeEnd`, never as a reserved number in a `limits.toml` row (section 6). Under ruling 9 on #1710, only the signed bundle may choose `ScopeEnd`, through a field of its manifest that needs its own RFC (RFC 0005 section 13). Choosing it lengthens verdict reuse, which SR-26 counts as widening, so an artefact signed by an operator alone cannot make the choice (D-31). A `grdr.config` key may only shorten an expiry, through `FastpathLimits::narrow`. Until that manifest field exists, `from_limits` yields `After` from the `ms` rows, and no blob our compiler writes carries `ScopeEnd`. If such a key is added, it is a `setting` whose `ceiling` is its expiry row, and that row's scope becomes `ceiling` in the same item.
- **#1768.** Its four rows take the names above, with `min`, `max`, `fixed` and `none` (RFC 0005 R5.3).
- **#245 (`tables.md` section 2).** Its source table names the rows as above. RFC 0005 section 12 lists the same change, with the expiry rule of R5.2a.
- **RFC 0003, section 11.** Its proposed keys drop their unit suffixes: `ipc.call-max`, `ipc.first-frame`, `ipc.link-suite-wait` and `ipc.link-suite-margin` in `ms`, and `ipc.read-chunk` in `bytes`, each with `min`, `max`, `scope` and `effect`. `ipc.frame-max` and `endpoint.connections-max` already fit. Whether `ipc.call-max` and `ipc.first-frame` are settings with a ceiling, for slow hosts, is RFC 0003's to decide.
- **Pointers in RFC 0002 and RFC 0003, for their author.**
  - `Coded` is built by #278, not #280: RFC 0002 Rule 8 and the Rule 8 row of its mechanisms table; RFC 0003 Rule 7, the `Coded` line of its section 11 and the Rule 7 row of its mechanisms table.
  - "The RFC of #1710" now means #1850 for the `grdr-model` types: RFC 0002 sections 2, 4 and 10, and RFC 0003 section 11, its list of item changes, its Surfaces changed and its question 3. It means #1852 for the column manifest in RFC 0002 section 10 and its Unresolved question 4.
  - RFC 0002 section 11: `GRDR-STORE-0006 STORE_PERMISSION_DENIED` can be an incumbent's refusal as well as a file mode, so its `fix` also names the coexistence step (section 3). `GRDR-STORE-0002 STORE_BUSY` is a lock the other process releases, so it stays `retryable`.
- **RFC 0002 and RFC 0003 codes.** Every code they assign fits section 4, `unavailable` appears only with `retryable` in both, and section 1's "Agreement with RFC 0002" holds.
- **#1851.** The protobuf `ErrorClass` is either generated from `codes::ErrorClass::VARIANTS` or held equal to it by a test, so the five words have one home (P17). `ErrorDetail` carries no free text, only `LogSafe` values of class `structural`, and names a bound by its `limits::ALL` row name. It also states the message type of `codes.json`.
- **#1850.** `RetryBudget` and `Breaker` are per endpoint or port instance, never per principal, so no per-person retry count exists (P8). `RetryPolicy` reads a schedule's `jitter` (section 5).

### 8. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| A sealed value exists only where `generated` built it | The seal and the defining `registry` module (R10); the compiler on every build. The test `construction` copies the crate to a temporary directory, adds one item per case, runs `cargo check --offline` and expects the case's error: a mint from the parent or a sibling (E0603), a struct expression outside `registry` (E0451), a shadow of a constant, of `ALL` or of a `rows` entry (E0080), a shadow of another type (E0308). Compile-fail doctests show that no crate outside `grdr-schema` can build a `Code` or a `CodeEntry` | #278, #279 |
| A hand-written name never shadows a generated one | The parity assertions of R10 | #278, #279 |
| No retired code can be returned | A retired entry is a `CodeEntry` only, with no `Code` | #278 |
| Every error variant has one code | `Coded` with an exhaustive match, and a compile-fail doctest whose impl leaves a variant unmatched (#280 AC-3, moved); ARCH-017 over the error enums, reading the `const_name` of each active entry from `ALL` | #278; #1582 |
| The constants equal the registry and `limits.toml` | The `drift` tests, the `regenerate` test as the one writer, the line-ending tests | #278, #279 |
| The drift tests always run | A required CI step that runs `cargo test --locked -p grdr-schema --test codes_gen --test limits_gen -- --exact drift` and fails unless each target reports exactly one passed test, so a missing target, `required-features`, `test = false`, `#[ignore]` or a renamed test fails it | The gate item filed on acceptance |
| The generators, the sealed types and the drift tests change only with the full lane | Ten `security/trust-core.paths` lines: `crates/grdr-schema/Cargo.toml`, `crates/grdr-schema/src/codes/registry.rs`, `crates/grdr-schema/src/codes/generated.rs`, `crates/grdr-schema/src/limits/registry.rs`, `crates/grdr-schema/src/limits/generated.rs`, `crates/grdr-schema/tests/gen/**`, `crates/grdr-schema/tests/codes_gen.rs`, `crates/grdr-schema/tests/limits_gen.rs`, `crates/grdr-schema/tests/fixtures/codes/**` and `crates/grdr-schema/tests/fixtures/limits/**`, beside `limits.toml` | The gate item filed on acceptance |
| An entry never changes its area, number, reason, class or Connect code, never leaves, and moves only from `active` to `retired` | The registry check `history` (section 4), run from the base build by a `pull_request_target` job that reads the head as data | #278 builds it; the gate item wires the job and adds it to the ruleset's required checks through #1719 |
| The grammars and refusals of sections 4 and 6 | One fixture per refusal, each format number pinned at its boundary | #278, #279 |
| The prefix is the pinned namespace | The namespace grammar and #1856's refusal of a changed value; the generator's refusal of a malformed one; the drift test against the committed strings; a refusal fixture for a malformed namespace and a drift fixture for a changed one | #1856; #278 |
| Derived strings have one home | The constants test checks the five strings of every entry against its area, number and the namespace; the docs generator, ARCH-017 and the token check read `ALL` | #278; #1636, #1582, #1853 |
| Each enum's words are one list | One macro list per enum; the generator reads `VARIANTS` and `as_str` | #278, #279 |
| Every entry has its two tokens in every shipped locale | A check in `grdr-interface-gen` that walks every entry of `ALL`, retired ones included, and fails on a missing `message_token()` or `fix_token()` | #1853 |
| No literal bound in product code | ARCH-019, outside `src/limits/generated.rs` and test code: no integer literal, and no `MAX` or `MIN` of an integer type, anywhere in the operand of a unit constructor (`Bytes::new(..)` or `Bytes(..)` and the other three) or in any field of a `RetrySpec`, `BudgetLimits` or `Backoff` expression, including inside macro arguments; and no renaming `use` of these types. Its message has the four parts of design/03 section 2 and names `limits.toml`, the key grammar, the regenerate command and the step list (R11) | #1582 |
| One copy of the retry rules | The generator validates through `RetryLimits::new`; one fixture per `RetryRule` | #279 |
| A bound's range, scope and effect hold | The generator's refusals; `BoundEntry::clamp` in the resolver; the D-31 rule for raised effect rows | #279; #1591 |
| A change to a row whose effect is not `none` is reviewed for privacy | Review: `persona-privacy-officer` comments on the item's issue, asked by the orchestrating session on every pull request whose `limits.toml` diff touches such a row; `eval-security` checks the row in the diff; `eval-docs` checks the release note | `grdr-work-issue`, on each such pull request |
| `note` reaches no product surface | It is generated into no Rust file | #279 |
| No parser in a normal closure | `cargo tree --locked -p grdr-schema -e normal` names no `toml`, `toml_edit`, `serde` or `serde_json` (#278 AC-6) | #278 |
| Layer 0 rules | `cargo check --locked --target wasm32-unknown-unknown -p grdr-schema`; the workspace lints | #278, #279 |
| One definition per type (section 1) | `eval-architecture` on every pull request that adds a public type to a layer 0 to 2 crate; ARCH-007 | Review; #1582 |
| Stability | The `[[crate]]` row of section 11, `rfc-required`, `cargo public-api`, `cargo semver-checks`; the registry check for the codes themselves | The protected-change item filed on acceptance (#1710 R3); #1741; #278 |

### 9. What each item changes
Under #1710 R4, each lead writes these changes into its item before readying it.
- **#278**:
  - R1's `owner` is `design/NN`.
  - R2's keys are those of section 4: `status` replaces `retired`, `anchor` goes, `retired_in` and `replaced_by` join for retired entries, and every other key is required.
  - R3's prefix is the pinned namespace, read as section 3 says; the token ids are `code.<area>_<nnnn>.message` and `.fix`.
  - R4's output is `codes::ALL` of `CodeEntry`, retired entries included, a `Code` constant per active entry, and the parity assertions.
  - R6 becomes `CodeEntry` and `Code` in `codes::registry`, built only with the seal (R10).
  - R7 gains the refusals of section 4.
  - The item also builds `CodeStatus`, `ErrorClass` and `ConnectCode` from one macro list each, and `Coded` with its compile-fail doctest from #280.
  - It builds the registry check `history`, the `construction` test, the "Add an error code" step list in `crates/grdr-schema/AGENTS.md`, the generated-file header and the registry headers (R5, R11). Its write set gains `crates/grdr-schema/AGENTS.md`.
  - AC-1 gains a fixture per new refusal and at each grammar boundary (an area of one and of nine letters, a reason of 64 bytes, numbers 0 and 10000). AC-4 checks the five derived strings.
- **#279**:
  - R1 gives a bound the keys of section 6, with `owner` as `design/NN` only.
  - R2 adds `jitter_permille` for a schedule and `owner` and `note` for every table.
  - R3 tightens the grammar as section 6 states.
  - R4's types become those of section 5: `RetryLimits` and `BoundEntry` in `limits::registry` with the seal, `limits::rows`, `limits::ALL` and the parity assertions.
  - R5 gains the refusals of section 6 and the ceilings, and validates retry tables through `RetryLimits::new`.
  - R7's seed rows gain `min`, `max`, `scope` and `effect`, which #279's lead sets from each row's owning document.
  - R9's "constants only" becomes "no parser": the module holds types, constants, tables and one checked constructor.
  - It registers area `LIMITS` and `GRDR-LIMITS-0001`, so its write set gains `schema/codes/areas.toml` and `schema/codes/limits.toml`, and it is blocked by the gate item.
  - It builds the `construction` test and the "Add a limit" step list (R11).
  - AC-1 gains a fixture per new refusal, each retry ceiling at and one above its value, and `budget_slots = 1001`.
- **#280**: keeps `ErrorDetail` and `Code::detail()`, which #1851 now states. `Coded` moves to #278.
- **#18, #383, #282, #284**: the route is #1850, not RFC 0001. #282's tests build `RetryLimits` through `RetryLimits::new`, and its R4 takes a schedule's `jitter`.
- **#510**: the route is #1852.
- **#1768**: the row names, units and keys of section 7.
- **#1580 and #1278**: register `grdr-archlint` and `grdr-docgen` as `layer = "tool"` rows of `architecture.toml`, a protected change, before #1582 and #1636 link `grdr-schema`.
- **#1582**: ARCH-017 reads `ALL`, and ARCH-019 gains the patterns and the message of section 8.
- **#1636**: the `/codes/<code>` pages walk `ALL`, retired entries included, show `retired_in` and the chain of `replaced_by`, render registry text as text and never as MDX, render no code string themselves, and write `codes.json`.
- **#1853**: the token ids of section 3; its check covers retired entries in every shipped locale; a `policy` code's `fix` names the exception route and an `internal` code's `fix` names the support-bundle command and the brand's support contact; token arguments are `LogSafe` and `structural`, and the code is an identifier-class argument (R4); it owns the formatting scale rule of section 5 and its open question of role-specific `fix` tokens; and an item that registers a code may write its source-locale tokens (section 4).
- **#1856**: the namespace grammar and pin of section 3, and the loader the generator reads.
- **#1591 and #1289**: the resolution and clamp of `setting` rows, the D-31 rule for rows whose effect is not `none`, a refusal of a `key` that names no configuration key, and the effective value with its source in `grdr config explain` and `grdr doctor`.
- **#1639**: `grdr status` shows effective values through #1591's resolver.
- **RFC 0002, RFC 0003 and RFC 0005**: the pointers and row names of section 7, by their author in their next revision.
- **`CONTRIBUTING.md`**: a one-line link to the step lists of R11, for lead-security, which owns the file.

### 10. Proposed changes to design/03
Each lands after acceptance through an issue whose write set names design/03, filed on acceptance.
- **Section 10, Errors.** "the `code.<code>.message` and `code.<code>.fix` language tokens and a docs anchor" becomes "the `code.<area>_<nnnn>.message` and `code.<area>_<nnnn>.fix` language tokens and the docs anchor `codes/<code>`, all derived from the code and never written in the registry; an entry's lifecycle is its `status`, and its area, number, reason, class and Connect code never change". The five class meanings of section 3 follow the class list.
- **Section 10, Resource budgets.** A bound's unit is one of `bytes`, `count`, `ms` and `permille`, written as its key and never in its name; every bound has a range, a scope and an effect; and no bound value is reserved to mean unbounded.
- **Section 10, Retries, timeouts and backoff.** `kind = "schedule"` gains `jitter_permille`, and every retry field has a ceiling (RFC 0007 section 5).
- **Section 2, ARCH-019.** The rule gains the patterns of section 8, and the general patterns gain `channel(<literal>)`, `sync_channel(<literal>)` and `vec![<value>; <literal>]`. An array length and `take(<literal>)` stay with structure rule S7 in review, because a fixed-size array or a take of a protocol constant is not always a bound.

### 11. Stability
| Part | Rule | Held by |
|---|---|---|
| An entry's rendered code, area, number, reason, class and Connect code | Stable wire identifiers from the first release, whatever the crate's class: never changed or reused; a new meaning is a new number | The registry check (section 4) |
| Token ids and the anchor | Derived from area and number, and from the code; as stable as the code | The generator and the drift test |
| The prefix `GRDR-` | Class A (design/36 section 2): an RFC before the first release, nothing after | #1856 |
| `codes.json` | Its message type's class (#1851) | #1851 |
| The Rust API of `codes` and `limits` | `experimental` | The `[[crate]]` row, `cargo public-api`, `cargo semver-checks` |
| The formats and their refusals | Amendment by a new RFC that names RFC 0007 | `rfc-required` |
| Adding or retiring an entry; adding, changing or removing a row | Content | Sections 4 and 6 |

- `grdr-schema` enters `surfaces.toml` as `experimental` (D-60; ADR-0020; design/03 section 7: every surface starts there) in one row of the `[[crate]]` kind RFC 0005 R6.1 proposes: `name = "grdr-schema"`, `class = "experimental"`, `rfc = "0007"`. The class is the crate's, so no module key is needed. #1851 and #1852 amend this RFC and keep the row. The protected-change item #1710 R3 files after acceptance adds it, once the row kind exists; if RFC 0005 is not accepted, that item adds the row kind with the same three keys.
- `experimental` allows a break of the Rust API in any release, and every change still goes by RFC. A change to a type, a rendered form, a format constant, a registry or `limits.toml` rule, or a generator refusal is an amendment: a new RFC that names RFC 0007, since an accepted RFC never returns to `Review` (RFC 0001, "RFC states").
- Retiring a code removes its constant, which breaks a crate that names it. That is allowed while the crate is experimental. The release notes list the retirement with its replacement code (design/34 sections 10 and 14). The RFC that moves `grdr-schema` to beta decides whether a retired code keeps a deprecated constant for its deprecation release, as a new `CodeStatus` variant.
- The release notes list every change to these modules (design/34 section 10).

### 12. Failure modes
| Failure | Declared outcome | Visible as |
|---|---|---|
| A registry or `limits.toml` entry breaks a rule | Generation stops and writes nothing | One line naming the file, the entry or table, the key, the rule and the fix, in the tests gate on every system |
| The brand namespace is missing or malformed | Generation stops; there is no default prefix | The refusal line |
| A manifest sets another namespace | #1856's loader refuses it; a regenerate would also fail the drift test and change a trust-core file | The loader's error; the drift line |
| A committed generated file is stale | The `drift` test fails | The first differing line and the regenerate command |
| The drift tests did not run | The required CI step fails | The step names the target with no passed test |
| A hand-written item shadows a generated name | The crate does not compile | rustc's E0080 at the parity assertion, or E0308 |
| A module other than `generated` builds a sealed value | The crate does not compile | rustc's E0603 or E0451 |
| An entry on `main` is changed, deleted or reactivated | The registry check refuses the pull request | The check names the entry and the rule |
| The registry check cannot read the base or the head | It fails with "could not look"; never a pass | The job's output |
| A crate names a code or bound that is not registered | The crate does not compile | rustc names the missing constant |
| An error variant has no code | The `Coded` impl does not compile | rustc's exhaustiveness error at the impl |
| An entry has no `message` or `fix` token in a shipped locale | The token check fails (#1853) | The check names the code and the locale |
| A `RetryLimits` built at run time breaks a rule | `LimitsError::RetryTable { rule }`, `GRDR-LIMITS-0001` | The caller's error, with its code and the rule's word |
| A setting's value is outside its row's range | Clamped into `[min, max]` (#1591) | `grdr config explain` and `grdr doctor` show the effective value and its source |
| A consumer reaches a bound | It returns its own coded error, or a gap record, that names the row; never an empty result (P9) | The error or gap, naming the bound |
| A newer peer sends a code `ALL` lacks | Shown as its string and link, never as success | The `/codes/<code>` link |
| An owner names no design document | Generation stops | The refusal line |

Nothing in either module fails at run time except `RetryLimits::new`, and nothing fails open.

## Surfaces changed
- `grdr-schema` (layer 0, public): module `codes` (`Code`, `CodeEntry`, `CodeStatus`, `ErrorClass`, `ConnectCode`, `Coded`, the generated constants and `ALL`) and module `limits` (`Bytes`, `Count`, `Millis`, `Permille`, `Backoff`, `BudgetLimits`, `RetrySpec`, `RetryLimits`, `BoundEntry`, `BoundUnit`, `BoundScope`, `BoundEffect`, `LimitsError`, `RetryRule`, `BUDGET_SLOTS_MAX`, the generated constants, `rows` and `ALL`). Class `experimental`.
- The formats `schema/codes/areas.toml`, `schema/codes/<area>.toml` and `limits.toml`, read by the generators.
- The rendered code `GRDR-<AREA>-<NNNN>`, with its prefix from the pinned namespace, its token ids `code.<area>_<nnnn>.message` and `.fix`, and its anchor `codes/<code>`: stable wire identifiers from the first release.
- `codes.json`, written by #1636 in #1851's message type.
- Content: area `LIMITS` and `GRDR-LIMITS-0001`.
- As proposals: design/03 sections 2 and 10 (section 10), the `[[crate]]` row of `surfaces.toml` (section 11), and the ten `security/trust-core.paths` lines of section 8.
- No spine text, protobuf package, Cedar schema, dependency or same-layer edge changes.

## Alternatives
- **One RFC for the whole scope of #1710.** Rejected for section 1's reasons: #510 cannot be stated yet, `ErrorDetail` waits on RFC 0006 and SP-1, and the open `grdr-model` questions would hold #278 in the same review.
- **Two parts: codes and limits here, and the rest of #1710's scope in one more RFC.** That RFC would wait on SP-1 and #386 through `ErrorDetail` and the manifest, and hold the `grdr-model` types that #383 and #18 need sooner. Rejected for one issue per prerequisite chain.
- **`anchor` as a registry key** (#278 R2). Every anchor would be a function of the code written out by hand, and one could drift from it. Rejected for a derived anchor.
- **Each tool rendering codes from the TOML** (revision 1). The docs generator, ARCH-017 and the token check would each re-implement the padding and the prefix. Rejected for one rendering in the generator, read through `ALL`.
- **`retired = true`** (#278 R2, revision 1). A lifecycle in a flag, which a third state would have to break. Rejected for `status` (S4).
- **A `GRDR` literal in the generator** (revision 1), or the prefix as a format constant. A second home for a Class A identifier that `brand/brand.toml` already holds, and one a partner could still change by hand. Rejected for the pinned namespace that #1856 holds.
- **A constructor private to `codes`** (revision 2). Every child module of `codes`, and `codes.rs` itself, could still call it, and a hand-written constant could shadow a generated one with a changed class and pass every test (round 2, adversarial M1). Rejected for the seal, the defining module and the parity assertions (R10).
- **Public fields or a public constructor on `Code`.** Any crate could make a code the registry lacks, and only ARCH-017's scan would notice. Rejected.
- **Retired entries as `Code` values in `ALL`** (revision 2). A `Coded` impl could return one by searching `ALL`. Rejected for `CodeEntry`, which is not a `Code`.
- **Token ids that embed the rendered code** (revision 2). Upper case and hyphens break the token id grammar, and a namespace move would orphan every translation. Rejected for ids from area and number.
- **A class or Connect code changed in place** (revision 2). A stored record or a playbook keyed on the code would change meaning with no trace. Rejected: a new meaning is a new number.
- **The registry comparison filed after acceptance, with `eval-diff` until then** (revision 2). Review alone would hold the rule while the first codes land. Rejected for a check built with the registry and run from the base build.
- **A parse from string, or `Display`, on `Code`.** Parsing invites building codes from data, and `Display` invites concatenation into person-facing text (UX6). Rejected, as #278 R6 already does for parsing.
- **Constants in one module per area,** such as `codes::cfg::ADAPTER_NOT_IN_PROFILE`. It works. Rejected for the flat names #278 R4 specified and RFC 0005 cites, which are unique by construction.
- **A table pairing each class with the Connect codes it allows.** RFC 0002 and RFC 0003 pair them freely for good reasons, and the two answer different questions. Rejected, except the one refusal of `unavailable` outside `retryable`, which no assigned code meets.
- **A position `match` for `VARIANTS`** (revision 2). A new variant could take a position while `VARIANTS` still left it out. Rejected for one macro list per enum.
- **Public format constants in `codes`** (revision 2). Nothing outside the generator reads them, and each public item is surface. Rejected for the generator's own grammar, pinned by fixtures (seat 8, cut 5).
- **An `owner` that names a crate or program** (revision 2). Its path rules were unstated, so `grdr-core/../grdr-wire` resolved. Rejected for `design/NN` only (seat 8, cut 5).
- **Cutting the retry half, `ConnectCode`, `CodeStatus` or the derived strings for slice 0** (seat 8). The retry half has a slice-0 user, RFC 0005's `fastpath-reload`; slice 0 includes the server API, and back-filling `connect` later costs more; seats 1, 2 and 3 rely on retirement; and the derived strings are the one home the architecture review found sound. Rejected under ruling 10.
- **Public fields on `RetryLimits`.** `RetryPolicy::from_limits` would have to be fallible, or trust input nothing checked. Rejected for a checked wrapper.
- **No public constructor for `RetryLimits`.** #282's tests, RFC 0002's executor tests and run-time tables need policies that `limits.toml` does not hold, and `#[cfg(test)]` items do not reach integration tests. Rejected.
- **The retry rules in the generator only.** A run-time constructor would need a second copy. Rejected for one copy in `RetryLimits::new`, which the generator calls.
- **Retry fields with no ceiling** (revision 2). `u32::MAX` breaker failures switched the breaker off, and 2^63 - 1 ms never gave up (round 2, adversarial M5). Rejected for a ceiling on every field.
- **Floors on retry delays** (adversarial M5). A floor would refuse legitimate local policies, such as a relational call's short base. Rejected: the ceilings, the budget and the full lane on `limits.toml` hold the rest.
- **A `jitter` key on exponential tables.** P15 fixes full jitter for them, so the key would have one allowed value, a reserved value in all but name. Rejected.
- **`max_elapsed = 0` meaning "no elapsed limit".** A reserved value, which section 6 forbids. Rejected: 0 is refused, and every policy has a finite elapsed limit below its ceiling.
- **All ones meaning "until the scope ends"** (#1768). TOML cannot write the value, and a reserved number hides a state. Rejected for `Expiry::ScopeEnd` in RFC 0005's own type.
- **An `ns` unit now** (revision 1). No bound needs it: both expiry rows are cache-reuse lifetimes in whole milliseconds, which `from_limits` converts. Rejected; a unit below a millisecond arrives by amendment with the first bound that needs it.
- **The unit in the name,** as RFC 0003 and #1768 wrote it. The unit would be written twice. Rejected.
- **Bounds with no range** (revision 2). Any value up to 2^63 - 1 passed, a clamp pair could be inverted, and a 0 could switch off a timeout (round 2, security 2 and adversarial m3). Rejected for required `min` and `max`.
- **`Ord` on the unit types.** Its `clamp` panics when a consumer passes two rows in the wrong order. Rejected for `BoundEntry::clamp`, total by construction.
- **An SR key on a bound row** (security 2). The owning document cites the SR, and `max` holds its figure; a key would be a second home for the same reference. Rejected.
- **`effect` as a review marker only.** A release could still raise a collection bound on every device with no person approving it. Rejected for the D-31 rule of section 6.

## Drawbacks
- The slice-0 surface of the two crates is decided in four RFCs instead of one, and readers follow the table of section 1 to find a type.
- #278 grows by the registry types, the three enums, `Coded`, the registry check and the construction test, and #279 by the `LIMITS` area, the bound keys, the ceilings and their refusals.
- Every pull request that registers a code changes `src/codes/generated.rs`, which is trust core, so it takes the full lane: `eval-security`, `eval-adversarial` and two passing evaluators on different models.
- The `construction` test runs `cargo check` on scratch copies, which slows the tests gate.
- `RetryLimits::new` is public, so a crate can build a retry policy that `limits.toml` does not hold. Only ARCH-019 and review stop literals in it.
- Retiring a code removes its constant, which breaks a downstream crate that names it.
- `retired_in` names a `grdr-schema` version, not a product version, so a reader maps it through the release notes.
- The registry check can only refuse. A wrong entry is repaired by retiring it and registering a new one.
- The generator reads `brand/brand.toml`, so a malformed manifest stops code generation as well as the build steps that already read it.
- Twenty-six retry rules each need a fixture.

## Unresolved questions
None for this RFC. Open elsewhere:
- Partner error codes and limits rows without a fork (seat 5): #1858, which names design/26 and waits on an embedding partner's stated need.
- Role-specific `fix` tokens, such as one for an end user and one for a technician (seat 4): #1853.
- The bundle manifest field that may choose `Expiry::ScopeEnd`: its own RFC, which RFC 0005 section 13 files.
- The `grdr-model` surface (#1850), `ErrorDetail`, `Code::detail()` and the `codes.json` message type (#1851), and the lake column manifest type (#1852).
- The code tokens and their check (#1853), and the brand manifest loader that pins the namespace (#1856).

Filed on acceptance:
- the `surfaces.toml` row (#1710 R3);
- the gate item, for lead-agent-kit, trust core, blocked by #278 and blocking every later item that changes `schema/codes/`, #279 first: the ten `security/trust-core.paths` lines of section 8, the required drift step, and the `pull_request_target` job that runs the registry check from the base build;
- the design/03 change (section 10).

## Review
How review binds the decision (RFC 0001, "Review binds the decision"; ADR-0036):
- RFC 0007 decides no pinned path, so its decision adds no decision line and no file under `rfcs/evidence/`.
- The review set is the `[kinds] rfc` row of `.claude/risk-tiers.toml` on the base, which names `eval-architecture`. `eval-security` and `eval-adversarial` join it because #1710 is `tier:high` (the session's correction on #1710): the RFC fixes the `GRDR-` wire identifier and the format of `limits.toml`, a trust-core path (`security/trust-core.paths`). The passing evaluators run on two models (D-63, owner instruction 7). The RFC changes no trust-core file itself; #278 and #279 take the full trust-core lane. The nine persona council seats comment on #1710.
- Each verdict by an evaluator of the set, and each seat comment, carries the three role lines of RFC 0001 (#1798):
  - `RFC file:` the blob of this file it read (`git rev-parse <commit>:rfcs/0007-grdr-model-and-grdr-schema-slice-0-surface.md`);
  - `Proposed text: none`, because no pinned path changes;
  - `Base:` the spine pin in force in `rfcs/pins.toml` on the base, `a80859235e7a2a4444648d6fa8d389d78dde6be9`, SHA-256 `8f6ea876777c0121ecec068c0bc4cef45932be45c1c2aff4140712db1e06628d`.
- The decision rests on an `eval-architecture` pass on the blob it decides, with no fail by an evaluator of the set on that blob. Before deciding, the chief architect checks that the seats the session names commented on that blob.
- The file the decision commits differs from that blob only in `State:`, `Decision record:`, lines under `Review` that each hold one comment link, and the `Decision` section.
- The file reaches `main` in `Review` before the commit that decides it, because a file is added only as `Draft` or `Review` (RFC 0001, "RFC states").

Round 1, on revision 1 (RFC file blob `04b07a7`):
- `eval-architecture`, fail, one major and eleven minors: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073130936

Round 2, on revision 2 (RFC file blob `3961680`):
- `eval-architecture`, pass, eight minors: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073295898
- `eval-security`, pass, six minors: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073439148
- `eval-adversarial`, fail, six majors and five minors: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073483800
- Seat 1, solo developer: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073316100
- Seat 2, IT admin: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073319446
- Seat 3, SOC analyst: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073314441
- Seat 4, MSP operator: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073315786
- Seat 5, OEM partner: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073319243
- Seat 6, privacy officer: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073320955
- Seat 7, contributor: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073334929
- Seat 8, simplicity: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073335631
- Seat 9, international operator: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073341917
- The session's rulings for revision 3: https://github.com/416rehman/Guardrails/issues/1710#issuecomment-7073495899

Round 3, on revision 3. The verdicts and seat comments on its blob are linked below, one per line.

## Decision
Pending.
