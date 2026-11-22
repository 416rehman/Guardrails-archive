RFC: 0005
Title: The fast-path Rust surface: grdr-fastpath types, load and eval, compile_fastpath, its errors and the per-call cap
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #405
Spine: D-05, D-15, D-20, D-41, D-60, D-61, D-71, P5, P9, P14, P17 (no spine text changes)
Surfaces: the public crates `grdr-fastpath` (its first surface) and `grdr-core` (module `compile::fastpath`), each entering `surfaces.toml` as `experimental`; proposals for `architecture.toml` and design/03. No wire format, C ABI, host-contract text, Cedar schema or same-layer edge changes
Decision record: none yet

To comment, write on issue #405 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

## Summary
This RFC fixes the Rust surface of the fast path: the types and functions of `grdr-fastpath`, the table layout module that `grdr-core` writes through, and `compile_fastpath` in `grdr-core`. It answers R1 to R7 of #405. The library takes a safe, borrowed input and returns a verdict enum whose variants carry their own data. The `#[repr(C)]` mirrors of `grdr_fastpath.h` live in `grdr-fastpath-ffi`, because only that crate may hold raw pointers. The tables handle is generic over who owns the blob and the arena, so the daemon can own them in safe Rust and the C library can borrow them. The four error variants map one to one onto the four fast-path status codes and are bound to the status registry through the FFI crate, not to `schema/codes/`. The per-call cap and the other three bounds travel in the blob header, written by the compiler from `limits.toml`, as #245 already rules. Both new surfaces are `experimental`, and no dependency or edge is added.

## Motivation
WI-0017 (#20) and its sub-issues #409, #410, #412 and #414, and EM-2 (#418), all build against a Rust surface no document states. #245 fixes the blob bytes and #246 the C functions. Design/26 section 2 says "Our daemon links `grdr-fastpath` directly from Rust", and #378 leaves `compile_fastpath` out of scope. `grdr-fastpath` and `grdr-core` are public crates in layer 1, so their surfaces change only by RFC (D-61; design/30 section 3).

Read together, the items already disagree. #405 R3 has `compile_fastpath` return a blob; #414 R1 returns a blob and a floor report. #412 R2 makes an action class outside the table's vocabulary an argument error; `tables.md` section 6 answers `pass` with scope `none` for a class within the ABI. #409 R2 asks for "the layout types of the RFC", which do not exist. Nothing says where the `#[repr(C)]` structs live, how the daemon holds tables it loaded, how an error variant gets a code when the crate has no dependency, or where the cap comes from. Each item would otherwise answer on its own.

## Design

### 0. What this RFC fixes, and what it reads
It fixes the Rust items, their placement, their signatures and which error or value each case gives. The bytes of the blob, the numbered TV rules, the evaluation semantics, the cost model and the cache-scope rules are `spec/host-contract/tables.md` (#245). The C functions and structs are `spec/host-contract/c-abi.md` (#246), and the header's generated form is RFC 0004. This RFC refers to those texts and does not restate them.

It was written against:
- `tables.md` blob `8339bea85bb2ee563dd0dfe38befee871a5b7d12`, on `issue/245` at `115ec8b`;
- `c-abi.md` blob `b147c9dbd81068cd0d95cad4813bfee5e702fe30` and `status-codes.toml` blob `abcaa9704974359cdf7fac76712263b7b6f6f74b`, on `issue/246` at `ca039ed`;
- the spine pin in force, blob `a80859235e7a2a4444648d6fa8d389d78dde6be9`, on `main` at `4e46c2c`.

Where `c-abi.md` at `ca039ed` and `tables.md` at `115ec8b` disagree, this RFC follows `tables.md` (Unresolved question 2).

Out of scope, as #405 says: the blob layout (#245), the C functions (#246), the shim's fail-safe table (#71) and the bounded hook-field scanner of design/07. The last two join `grdr-fastpath` later, each by an amendment of this RFC.

### 1. The `grdr-fastpath` surface (R1, R2)

```rust
// grdr_fastpath: #![no_std], #![forbid(unsafe_code)], no dependency, no alloc.
pub mod layout;                                    // section 2

pub struct Tables<B, A> { /* private: blob B, arena A, the validated layout::Header */ }

pub fn header(blob: &[u8]) -> Result<layout::Header, Error>;
pub fn arena_size(blob: &[u8]) -> Result<usize, Error>;
pub fn load<B, A>(blob: B, arena: A) -> Result<Tables<B, A>, Error>
where B: AsRef<[u8]>, A: AsRef<[u8]> + AsMut<[u8]>;
pub fn eval<B, A>(tables: &Tables<B, A>, input: &Input<'_>) -> Result<Outcome, Error>
where B: AsRef<[u8]>, A: AsRef<[u8]>;
pub fn classify<B, A>(tables: &Tables<B, A>, input: &Input<'_>) -> Result<ClassBits, Error>
where B: AsRef<[u8]>, A: AsRef<[u8]>;
pub fn interest<B, A>(tables: &Tables<B, A>) -> Result<Interest<'_>, Error>
where B: AsRef<[u8]>, A: AsRef<[u8]>;

impl<B, A> Tables<B, A> {
    pub fn header(&self) -> &layout::Header;
    pub fn reason(&self, index: u32) -> Option<Reason<'_>> where B: AsRef<[u8]>;
    pub fn into_parts(self) -> (B, A);
}

pub struct Input<'a> {
    pub action_class: u16,           // tables.md section 1 numbers
    pub principal_kind: u16,         // Session 1, Process 2
    pub exe_digest: [u8; 32],        // all zero: unknown
    pub path: Option<Path<'a>>,      // already resolved by the host; empty is no path
    pub dest: Option<Dest<'a>>,
    pub labels: Labels,
    pub grant_digest: [u8; 32],      // all zero: no grant
}
pub enum Path<'a> { Utf8(&'a [u8]), Utf16Le(&'a [u8]) }    // bytes at any alignment
pub struct Dest<'a> { pub host: Host<'a>, pub port: u16 }
pub enum Host<'a> { Name(&'a [u8]), Ipv4([u8; 4]), Ipv6([u8; 16]) }
pub struct Labels { pub bits: u64, pub bundle_tag: u64 }

pub struct Outcome { pub verdict: Verdict, pub scope: CacheScope }
pub enum Verdict { Pass, Deny(Hit), StepUp(Hit) }
pub struct Hit { pub rule_index: u32, pub reason: u32 }
pub enum CacheScope { None, Call, Session(layout::Expiry), Bundle(layout::Expiry) }
pub struct ClassBits(/* private: u64 */);
impl ClassBits { pub fn bits(self) -> u64; }
pub struct Reason<'a> { pub code: &'a str, pub rule_id: &'a str }

pub struct Interest<'a> {
    pub process_scope: Records<'a, layout::ProcessScopeEntry>,
    pub paths: Records<'a, layout::PathEntry>,
    pub hosts: Records<'a, layout::HostEntry>,
    pub ports: Records<'a, layout::PortRange>,
    pub strings: &'a [u8],
}
pub struct Records<'a, R> { /* private: the section's bytes and count */ }
impl<'a, R: layout::Record> Records<'a, R> {
    pub fn as_bytes(&self) -> &'a [u8];
    pub fn count(&self) -> u32;
    pub fn iter(&self) -> impl Iterator<Item = R> + 'a;
}

pub enum Error { Arg(ArgFault), Abi, Bundle(BundleFault), State }
pub enum ArgFault { Arena, ActionClass, PrincipalKind, Path, Destination }
pub enum BundleFault { Rule(TvRule), EvalCap, Changed }
pub struct TvRule(/* private: a rule number of tables.md section 5 */);
impl TvRule { pub fn number(self) -> u8; }
impl Error { pub fn rule(&self) -> Option<TvRule>; }      // TV-3 for Abi
```

Types (R1):
- R1.1. The crate is `#![no_std]` with no `alloc`, no dependency and `#![forbid(unsafe_code)]`, and builds for `wasm32-unknown-unknown` and every host triple (design/26 section 2, ARCH-003).
- R1.2. `Input` is the safe form of `grdr_fp_input`. Its fields keep the names, numbers and meanings of `c-abi.md` section 2.1, except four. `struct_size` is a C concern. `process_key` is read by no row. Each pointer and length pair is a slice. `path_encoding` and `dest_kind` become the variants of `Path` and `Host`. A `Path::Utf16Le` slice holds the little-endian code units as bytes, so the FFI never builds an aligned `u16` slice from a host pointer. An empty path is no path, as `path_len` 0 is in C.
- R1.3. `Verdict` is one enum whose variants carry their own data (#412 R8): `Pass` names no row, and `Deny` and `StepUp` carry the winning row's index and its reason index. `Pass` is not `ALLOW` (design/26 section 2).
- R1.4. `CacheScope` carries the expiry inside the two scopes that have one, so the two meanings of `tables.md` section 6 never meet. `Call` and `None` are never reused, and `Session` and `Bundle` carry `layout::Expiry`. The C numbers of scopes are the FFI's (section 4).
- R1.5. `Error` has the four variants of the four fast-path status codes of `c-abi.md` section 6: `Arg` is `GRDR_E_ARG`, `Abi` is `GRDR_E_ABI`, `Bundle` is `GRDR_E_BUNDLE` and `State` is `GRDR_E_STATE`. `TvRule` names the failing rule, so a test can tell which rule failed (#409 R5). `BundleFault::EvalCap` is an evaluation that would exceed `eval_cap`. `BundleFault::Changed` covers a read that finds the blob or arena no longer holding what `load` validated (R2.7).
- R1.6. Every public enum is exhaustive. A new `Error` variant must fail the FFI crate's build until it maps to a status (section 4), and `#[non_exhaustive]` would force a wildcard arm there.
- R1.7. No type implements `Display`, and none formats text (`renders = "none"`). Errors derive `Debug`, `Clone`, `Copy`, `PartialEq` and `Eq`, and carry structural values only, never input bytes. A host that reports a fast-path failure to a person does so under its own registered code and language tokens (section 5; D-69).
- R1.8. The `#[repr(C)]` structs of `grdr_fastpath.h` live in `grdr-fastpath-ffi`, not here (section 4). A struct holding raw pointers can be read only through `unsafe`, which this crate forbids. Keeping the structs in the FFI crate also keeps the C ABI's minor-version rule (trailing fields behind `struct_size`) apart from this crate's SemVer line (D-71). That answers RFC 0004's unresolved question 2 and its D10.
- R1.9. `Tables<B, A>` is generic over who owns the blob and the arena. The FFI crate uses borrowed slices. The daemon, the first consumer, can own both, for example as `Box<[u8]>`, and keep the handle in safe Rust with no self-referential helper. Whatever the owner, the handle holds both for as long as it lives, and while it lives its arena cannot be passed to another `load` (#409 R7; `tables.md` section 10).

Functions (R2):
- R2.1. `header` applies TV-1 to TV-14 of `tables.md` section 5 in number order to `blob`, whose length is the length TV-6 compares, and returns the header. `arena_size` does the same and returns the arena size, computed from the header alone (`tables.md` section 7). A host makes the binding and cap checks of `tables.md` section 11 on `header`'s result before it loads (#1769).
- R2.2. `load` applies TV-1 to TV-14 and then checks the arena. An arena shorter than `arena_size` is `Arg(Arena)`. It then applies TV-15 to TV-33, builds its indices in the arena and returns the handle. It is never lazy. It writes only the arena, never copies the blob and allocates nothing. On any error the caller keeps the tables it had. `load` takes the blob and the arena by value, so an owning caller's new buffers are dropped on an error; `into_parts` returns them from a live handle.
- R2.3. `eval` checks in the order of `c-abi.md` section 2 after the C-only argument checks:
  1. a `labels.bundle_tag` that differs from the first eight bytes of `bundle_digest` is `State`;
  2. an input field outside its range is `Arg`, naming the field;
  3. a cost above `eval_cap` is `Bundle(EvalCap)`, before any matching;
  4. evaluation by `tables.md` section 6.

  Which field values are out of range, and the class within the ABI but above `action_class_count` that gives `Pass` with scope `None`, are `tables.md` section 6's. `eval` reads only the tables and the input, writes nothing but its return value, and never returns `Pass` on a failure.
- R2.4. `classify` returns the class bits of `tables.md` section 6 for one input, with the same checks and the same cap, and never partial bits. #20 AC-2 holds it against `grdr-core`'s classifiers, so it is public.
- R2.5. `interest` returns the four interest tables and the string pool as views into the blob (`tables.md` section 3.5). It fails only with `Bundle(Changed)`.
- R2.6. `eval`, `classify`, `interest` and `reason` take `&Tables`. `Tables<B, A>` is `Send` and `Sync` whenever `B` and `A` are, and the crate holds no interior mutability, global or thread-local state. So any number of threads may evaluate the same tables at once (design/26 section 2).
- R2.7. `B` and `A` must return the same bytes on every call, as slices, arrays, `Box<[u8]>` and `Vec<u8>` do. Storage that changes under the handle breaks the custody obligation of `tables.md` section 11. Every read stays checked whatever the storage. A read that finds the blob or arena no longer as validated returns `Bundle(Changed)` from `eval`, `classify` and `interest`, and `None` from `reason`, never a verdict.
- R2.8. `reason` returns the reason code and the instantiated rule id of one entry of the reason-code table, which TV-19 holds to visible ASCII, or `None` for an index that names no entry. A Rust host takes the rule id it records from here, so it never reads the blob's layout itself (P17).

### 2. The table layout (R1, R3)
`grdr_fastpath::layout` is the one definition of the blob's layout that the writer and the reader share. It holds:
- the numbers `tables.md` fixes, as `pub const`: the magic, `table_format` 1, the 224-byte header and 20-byte stable prefix, the ten sections, each record size, the kind values, the row outcomes and verdict numbers, and the fast-path ABI version (`ABI_MAJOR`, `ABI_MINOR`, `abi_version()`) with the highest action class it carries (15 at 0.1). These are the format, like a protobuf field number, not tunable bounds, so they are not `limits.toml` entries (ARCH-019 targets bounds);
- `Header`, with one public field per field of `tables.md` section 2, of the same name and width, and `SectionEntry`;
- `Section`, the ten sections in directory order with their record sizes;
- one record type per record of `tables.md` section 3: `FloorRow`, `PathEntry`, `HostEntry`, `ExeEntry`, `ProcessScopeEntry`, `PortRange` and `ReasonEntry`, each with public fields of the document's names and widths and an impl of `Record`, a `Copy + 'static` trait that gives the record size and decodes one record;
- `encode` and `decode` for the header and every record, over byte arrays of the exact size, with no validation, which is `load`'s;
- `Expiry`, which is `ScopeEnd` or `After(Nanos)`, where `Nanos` refuses 0 and the all-ones value, with the header mapping of `tables.md` sections 2 and 6;
- the cost function of `tables.md` section 7, which `eval` applies to the input and the compiler to its worst case, so the formula exists once.

Rules:
- R3.1. `compile::fastpath` in `grdr-core` is the only non-test code outside `grdr-fastpath` that imports it, and it imports only `layout`. That is what "table layout only" on the same-layer edge means (design/03 section 2). Tests of `grdr-core` (#20, #414) may also call `load`, `eval` and `classify`, the blob's real consumer.
- R3.2. Sharing `layout` makes a layout fault symmetric, so it is not its own oracle. The oracles are independent of it: #409's reference validator under `tests/`, which shares no code with `src/`; #414's golden rows, written by hand from the Cedar text; and #20's differential against `cedar-policy`.

### 3. `compile_fastpath` (R3)

```rust
// grdr_core::compile::fastpath
use grdr_fastpath::layout::Expiry;

pub fn compile_fastpath(
    bundle: &VerifiedBundle,
    facts: &Facts<'_>,
    limits: &FastpathLimits,
) -> Result<FastpathOutput, CompileError>;

pub struct FastpathOutput { pub blob: Blob, pub report: FloorReport }
pub struct Blob { /* private: Vec<u8> */ }
impl Blob { pub fn as_bytes(&self) -> &[u8]; pub fn into_vec(self) -> Vec<u8>; }

pub enum Facts<'a> { Device(DeviceFacts<'a>), Relay }
pub struct DeviceFacts<'a> { pub templates: &'a PathContext, pub volumes: &'a [Volume<'a>] }
pub struct Volume<'a> { pub mount: &'a [u8], pub case: CaseRule }
pub enum CaseRule { Sensitive, Insensitive }

pub struct FastpathLimits { /* private: the four header values */ }
impl FastpathLimits {
    pub fn from_limits() -> Result<FastpathLimits, CompileError>;
    pub fn new(eval_cap_steps: u32, path_max_units: u32, expiry_bundle: Expiry,
               expiry_session: Expiry) -> Result<FastpathLimits, CompileError>;
}

pub struct FloorReport { /* private: entries in rule-id order */ }
impl FloorReport { pub fn entries(&self) -> &[FloorEntry]; }
pub struct FloorEntry { pub rule: RuleId, pub outcome: FloorOutcome }
pub enum FloorOutcome {
    InFloor { rows: u32 },
    ModeWithoutRow,          // enforced Mode is Watch or Off
    Ineligible(Ineligible),  // #216's first failing atom
    TooManyClasses,
    TooManyLabels,
    NoDeviceValue,           // a template with no device-wide value, or any template under Relay
    Unmappable,              // a path or host entry the format cannot hold
    CannotMatch,             // contradictory labels, or a class no entry sets (TV-31, TV-32)
    FoldNonAscii,            // a fold-class entry with a non-ASCII literal
}

pub enum CompileError {
    Policy(PolicyCompileError),   // steps 1 to 7 of design/12 section 7, with their own codes
    CostAboveCap { action_class: u16, cost: u64, cap: u32 },
    TooLarge,                     // the blob or a section would pass 4,294,967,295 bytes
    Limit(LimitRow),
}
pub enum LimitRow { EvalCapSteps, PathMaxUnits, ExpiryBundle, ExpirySession }
```

- R3.3. `compile_fastpath` runs steps 1 to 7 of design/12 section 7 on the verified bundle and writes step 8's fast-path blob in the canonical form of `tables.md` section 4, through `grdr_fastpath::layout` only. It is pure and deterministic: one bundle, one set of facts and one set of limits give the same bytes on every target (D-05). The effective-policy compiler of #71 writes its step 8 blob by calling this function, so the blob has one writer.
- R3.4. It returns the floor report beside the blob. The report has one entry per rule of a fail-closed class, in rule-id order, so nothing is dropped silently (#414 R6). Its outcomes are #414's and those `tables.md` section 13 adds. `RuleId` is the instantiated rule id of design/12 section 7 step 4, the policy module's type, and `Ineligible` and `PolicyCompileError` are the types #216 and #71 define.
- R3.5. `Facts::Device` carries the device-wide template values (#221's `PathContext`, whose `$WORKSPACE` and `$SESSION_TMP` the fast path never reads) and each volume's mount point and case rule, which decide `path_fold_classes` (`tables.md` section 13). `Facts::Relay` is a partner relay compile with no per-device facts: it sets every bit of `path_fold_classes` and compiles no rule whose pattern holds a template (`tables.md` section 9). `DeviceFacts` is the device-facts input of design/12's `compile(layers, packs, device_facts)`, so #71 takes the same type (P17).
- R3.6. `FastpathLimits` carries the four header values the compiler writes. `from_limits` reads the four `limits.toml` rows of #1768 through `grdr-schema`'s generated limits module (#279). `new` lets a caller compile to a lower cap, which is how a host compiles to its own ceiling (`tables.md` section 11) and how a test meets the cap. Both refuse a value `tables.md` TV-8 would refuse, as `Limit`, naming the row.
- R3.7. It refuses with `CostAboveCap` a bundle whose worst-case cost for any action class exceeds the cap, taking the path length as `path_max_units`. So a blob it wrote never reaches the cap at run time (`tables.md` section 13).
- R3.8. `compiler_version` is the writing crate's own package version, and `bundle_digest` and `effective_hash` come from the bundle. The `Blob` makes no alignment promise. A host copies it into private memory before it loads (`tables.md` section 11, custody), and a C host aligns that copy to 8.

### 4. What `grdr-fastpath-ffi` holds (R1)
- R1.10. It defines `grdr_fp_input`, `grdr_fp_verdict`, `grdr_fp_span` and `grdr_fp_interest_view` as `#[repr(C)]` structs and `grdr_fp_tables` as an opaque type, under the names `c-abi.md` section 2 gives. RFC 0004's descriptor describes them there, so its D10 re-export case does not arise.
- R1.11. It converts `grdr_fp_input` to `Input` after the checks only C has: null pointers, `struct_size`, an 8-aligned blob and arena, and the `path_encoding` and `dest_kind` values. Each gives `GRDR_E_ARG` and never reaches `grdr-fastpath`. The Rust surface reads bytes at any alignment and has no such check.
- R1.12. Its arena holds the handle first, then the arena `grdr-fastpath` uses. `grdr_fp_arena_size` is the handle's size rounded up to 8 plus `arena_size(blob)`, in checked arithmetic. `grdr_fp_load` splits the arena, calls `load` with the blob and the second part as slices, and writes the handle into the first part. That is an `unsafe` block with a `// SAFETY:` comment: the host keeps the blob and the arena alive and unchanged while the handle is in use (`c-abi.md` section 2).
- R1.13. It maps `Outcome` to `grdr_fp_verdict`. The verdict numbers come from `layout`. `rule_index` and `reason_code` are `UINT32_MAX` for `Pass`. The scope number is `c-abi.md`'s. `expiry_ns` follows `tables.md` section 6: the header value for `Session` and `Bundle`, all ones meaning until the scope ends, and 0 for `Call` and `None`.
- R1.14. It maps `Error` to `grdr_status` in one exhaustive `match` with no wildcard arm (#418 R3). The constants `GRDR_FP_ABI_MAJOR`, `GRDR_FP_ABI_MINOR` and `GRDR_FP_ABI_VERSION` (RFC 0004 section 9) and `grdr_fp_abi_version()` come from `layout`. The cache-scope, path-encoding, destination-kind and status values, which only `c-abi.md` fixes, are its own constants, held to the contract and the registry by RFC 0004's `HDR-3` and `HDR-4`.

### 5. Error codes (R4)
ARCH-017 binds every error variant to an entry in `schema/codes/<area>.toml`. `grdr-fastpath` has no dependency, so it cannot name `grdr-schema`'s generated codes. #405 offers two answers.

**(a) Entries in `schema/codes/fastpath.toml`, checked by a drift test in `grdr-core`.** The orphan rule keeps `grdr-core` from implementing a `grdr-model` trait for a `grdr-fastpath` type, so the binding would be a mapping function in `grdr-core`. The fast path's one Rust consumer is the daemon, a privileged program, and ARCH-004 keeps `grdr-core` out of its closure. The mapping would never reach the code that meets the errors. The registered codes would be constructed only by a test and shown on no surface.

**(b) An ARCH-017 exemption, with the variants bound to the status registry.** The fast-path errors are already registered, as the four rows of `spec/host-contract/status-codes.toml`, each with a `meaning` and a `handle_after`. The FFI crate's exhaustive match binds every variant to one row at compile time, and `HDR-4` holds its constants to the registry.

**Decision: (b).**
- R4.1. `grdr_fastpath::Error`, `ArgFault` and `BundleFault` are listed in the ARCH-017 exemption list of `architecture.toml`. Their reason is "bound one to one to `spec/host-contract/status-codes.toml` through `grdr-fastpath-ffi`'s exhaustive match (RFC 0005)", in the form RFC 0002 section 14 proposes for that list, so the lint reads data and special-cases no name.
- R4.2. A test in `grdr-fastpath-ffi` shows that each of `GRDR_E_ARG`, `GRDR_E_ABI`, `GRDR_E_BUNDLE` and `GRDR_E_STATE` is produced by at least one variant, which is ARCH-017's "every registered code is constructed somewhere" for these rows.
- R4.3. A person never meets a fast-path error as such. The host applies the class's `on_failure` (D-15) and reports under its own registered code, which names the status and the TV rule number as structural fields. The daemon's item registers those codes, with their `/codes` pages and runbooks.
- R4.4. `CompileError` is in `grdr-core`, which has `grdr-schema`, so ordinary ARCH-017 applies. `CostAboveCap`, `TooLarge` and `Limit` bind to three entries of area `COMPILE` (subsystem: the effective-policy compiler; owner: docs/design/12), with the reasons `FASTPATH_COST_ABOVE_CAP`, `FASTPATH_TOO_LARGE` and `FASTPATH_LIMIT_OUT_OF_RANGE`. `Policy` carries the code of the error it wraps. #414 registers the entries through #278's registry, and the area itself if #71 has not.

### 6. The per-call cap and the other header bounds (R5)
The cap could be a header field written by the compiler from a `limits.toml` row, or a row generated into `grdr-fastpath` as a constant. A constant would put our default inside every partner's library, needing a rebuild to change. A blob from a partner's relay could not state its own cap. A host would have nothing in the blob to compare with its ceiling.

**Decision: the header, as #245 rules** (`tables.md` sections 2, 7, 11 and 13; the chief architect's comment on #405 recording it):
- R5.1. `eval_cap`, `path_max_units`, `expiry_bundle_ns` and `expiry_session_ns` are header fields. The compiler writes them from `fastpath.eval_cap_steps`, `fastpath.path_max_units`, `fastpath.expiry_bundle_ns` and `fastpath.expiry_session_ns` through `FastpathLimits` (R3.6). `grdr-fastpath` holds none of them.
- R5.2. An expiry of all ones means until the scope ends, and TV-8 refuses 0, so 0 only ever means "never reused" (`tables.md` section 6).
- R5.3. The compiler refuses a bundle whose worst case exceeds the cap (R3.7). `eval` refuses an input whose cost exceeds it (R2.3). A host refuses a blob whose cap exceeds its own ceiling, from its configuration, so a blob cannot raise the latency the host accepts (`tables.md` section 11; #1769).
- R5.4. The rows land through #1768, a protected change for lead-agent-kit. How a row writes nanoseconds and "until the scope ends" is open between #1768 and #279's units (Unresolved question 3). Whatever the form, `from_limits` maps it to these values and the library never sees it.

### 7. Stability (R6)
- R6.1. `grdr-fastpath`, and the `compile::fastpath` items of `grdr-core`, enter `surfaces.toml` as `experimental` (D-60; design/03 section 7: every surface starts there; ADR-0020). A protected-change item adds the two entries once this RFC is accepted and #1817 has created the file.
- R6.2. The blob format, `table_format` 1, is experimental by `tables.md` section 12, and the C header's class is its `[[c_header]]` row (#1817). This RFC adds neither.
- R6.3. While experimental, either crate may break in any release (D-60). A break is an amendment that names this RFC, and `cargo semver-checks` shows it once its gate exists (ADR-0020).

### 8. Dependencies (R7)
- R7.1. `grdr-fastpath`: no normal or build dependency (design/26 section 2; #409 AC-5). Its tests may take `proptest` as a dev-dependency once #432 admits it to the workspace. That adds no package to `Cargo.lock` and never enters the normal or build graph.
- R7.2. `grdr-fastpath-ffi`: `grdr-fastpath` only, plus `grdr-cabi-testkit` as a dev-dependency (RFC 0004).
- R7.3. `grdr-core`: `grdr-model` and `grdr-fastpath`, its listed same-layer edges, and `grdr-schema` in layer 0 for codes and limits. `cedar-policy` and `proptest` reach it through #431's ruling and #432's admission. #414 is blocked by #432, and #20 by #21 and #414. This RFC adds no third-party dependency and no edge. A ruling here would make two RFCs answer for one dependency set.

### 9. Failure modes, data classes and assurance effect
| Failure | Outcome | Visible as |
|---|---|---|
| A TV rule fails at `header`, `arena_size` or `load` | `Abi` for TV-3, `Bundle(Rule(n))` otherwise; no handle; the host keeps its previous tables | The returned error; the host applies the class's `on_failure` and reports under its own code |
| The arena is too short | `Arg(Arena)`; no handle | As above |
| Label bits from another bundle | `State` on every call until labels and tables agree | As above |
| An input field out of range | `Arg`, naming the field | As above |
| An input whose cost exceeds `eval_cap` | `Bundle(EvalCap)`, never `Pass` | As above |
| The blob or arena changed under the handle | `Bundle(Changed)`, never a verdict | As above; a custody failure of `tables.md` section 11 |
| No floor row objects | `Pass`, which is not `ALLOW` | The verdict; the host goes on to the engine or to `on_failure` |
| A bundle whose worst case exceeds the cap, or a blob too large | `CostAboveCap` or `TooLarge`; no blob | The error code; the caller keeps its last-known-good tables (design/12 section 10) |
| A limit row out of range | `Limit(row)` | The error code, naming the row |
| A fail-closed rule the floor cannot hold | Its `FloorReport` outcome; the rule keeps its class's loss-of-sensor outcome | The floor report, which #71 and #41 read |

Data classes (P8): `action_class`, `principal_kind`, `dest.port`, the verdict, rule and reason indices, scope and expiry are `structural`. `exe_digest`, `grant_digest`, `bundle_tag`, a destination name and address are `identifier`. `labels.bits` and `ClassBits` are `derived`. The target path is `content` (`content_kind` argument). Header and records take the classes of `tables.md` section 14, and so does the `Blob`, which is `content` when it holds a resolved template and then never leaves the device. Errors and the floor report are `structural`. `grdr-fastpath` logs nothing.

Assurance effect (P1): none of its own. The surface carries the floor rows that answer fail-closed classes while the engine is gone (D-15, D-20), and its items' tests are the evidence for `control` of those classes.

### 10. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| No raw pointer, `unsafe`, `alloc` or dependency in `grdr-fastpath` | `#![forbid(unsafe_code)]`, `#![no_std]`; `cargo tree -e normal,build` shows the crate alone; ARCH-001 | #409 (AC-5); #1580 |
| Builds for `wasm32-unknown-unknown` | `cargo build --target wasm32-unknown-unknown -p grdr-fastpath` | #409 (AC-6) |
| `compile::fastpath` is the only importer, and only of `layout` | ARCH-013's import table reads the edge's importers and paths in `architecture.toml` (section 11); until #1582 lands, `eval-architecture` on every change to `crates/grdr-core/src/compile/**` | #1582; the `architecture.toml` item filed on acceptance |
| One layout definition, independent oracles | `layout` shared; #409's reference validator with no shared code; #414's golden rows; #20's differential | #409, #414, #20 |
| Rust and C give the same answers | #418's behaviour: on any blob, `grdr_fp_load` then `grdr_fp_eval` equal `load` then `eval` | #418 |
| Every `Error` variant maps to one status, every fast-path status is produced | The exhaustive match (R1.14); `HDR-4` against `status-codes.toml`; the coverage test of R4.2 | #418; #1778 |
| The ARCH-017 exemption is data | The exemption list entry of R4.1, read by ARCH-017 | The `architecture.toml` item; #1582 |
| `CompileError` codes | Area `COMPILE` entries; ARCH-017; #278's drift test | #414; #278; #1582 |
| No bound in `grdr-fastpath` | The four header fields; TV-8; `FastpathLimits` from the generated module; ARCH-019 | #1768; #414; #409; #1582 |
| A blob from our compiler never reaches the cap | `CostAboveCap` with a seeded bundle above a small cap through `FastpathLimits::new` | #414 |
| A host's ceiling bounds the cap | The host obligation of `tables.md` section 11 | #1769; the daemon's item |
| Concurrent evaluation is safe | A type-level test that `Tables<&'static [u8], &'static mut [u8]>` and `Tables<Box<[u8]>, Box<[u8]>>` are `Send + Sync`; #412's determinism property | #412 |
| The ABI's highest action class equals the spine's | A test in `grdr-core` that `layout`'s ceiling equals the highest `grdr.common.v1alpha1.ActionClass` number, so a new class fails until a new minor raises it | #414 |
| The fast path is a deliberate second implementation (P17) | An `architecture.toml` record of the pair `grdr-fastpath` and `grdr-core`, held equal by the B2 differential | The `architecture.toml` item; #20 |
| Both surfaces are `experimental` | The `surfaces.toml` entries; `cargo public-api` and `cargo semver-checks` once their gate exists | The `surfaces.toml` item filed on acceptance; ADR-0020's gate item |

### 11. Proposed changes to design documents and gate files
Each lands through an issue whose write set names its file, after acceptance.
- **design/03 section 2, crate table.** `grdr-fastpath`: "`no_std` table evaluator over fixed-layout inputs, the table layout `grdr-core` writes through, and the bounded field scanner; no dependencies". `grdr-fastpath-ffi`: "`extern "C"` entry points and the `#[repr(C)]` structs of `grdr_fastpath.h`, so `libgrdr_fastpath` carries no engine code (26); core squad".
- **design/03 section 2, same-layer edges.** "`grdr-core` to `grdr-fastpath` (table layout only: module `compile::fastpath` imports `grdr_fastpath::layout`)".
- **`architecture.toml`.** On the `grdr-core` to `grdr-fastpath` edge, `importers = ["compile::fastpath"]` and `paths = ["grdr_fastpath::layout"]` beside the existing `scope`. In the ARCH-017 exemption list, the three types of R4.1 with their reason. One record of the independent pair `grdr-fastpath` and `grdr-core`, whose reason names the no_std fast path of P17 and the B2 differential (#20) that holds them equal.
- **`surfaces.toml`.** The two `experimental` entries of R6.1, in the row form #1817 uses: one double-quoted string per key.
- **`schema/codes/`.** Area `COMPILE` and its three entries (R4.4), through #414.
- **`limits.toml`.** The four rows of #1768, unchanged by this RFC.
- **`spec/host-contract/`, design/12, design/26, `supply-chain/`.** No change from this RFC. `c-abi.md`'s alignment with `tables.md` is #246's (Unresolved question 2).

### 12. What each item changes
This RFC is normative. Each lead writes these changes back into its item before readying it.
- **#409.** R2's layout types are `grdr_fastpath::layout` (section 2). R3 and R4 are `header`, `arena_size` and `load` as R2.1 and R2.2 state, over `Tables<B, A>`. R5's errors are `Abi`, `Bundle(Rule(n))` and `Arg(Arena)`, with the rule number from `Error::rule`. Its write set gains `crates/grdr-fastpath/src/layout.rs`, `crates/grdr-fastpath/src/layout/**` and `crates/grdr-fastpath/AGENTS.md`, whose purpose line no longer says the inputs are `#[repr(C)]`. `proptest` may be its dev-dependency (R7.1).
- **#410.** `classify` is public, as R2.4 states, and fails with `Bundle(EvalCap)` or `Bundle(Changed)`, never partial bits. The cost is the shared function of `layout`.
- **#412.** `eval` returns `Outcome` with the `CacheScope` of R1.4. R2's vocabulary case follows `tables.md` section 6: a class within the ABI but above `action_class_count` is `Pass` with scope `None`, not `Arg`. Its tests add R2.6's type-level test. R7's `interest` is R2.5's.
- **#414.** R1 is `compile_fastpath` as section 3 states, with `Facts` and `FastpathLimits`. R6's report gains the outcomes of `tables.md` section 13. R8 reads its bounds through `FastpathLimits`. R9 binds to area `COMPILE` (R4.4). It adds the cost-refusal and action-class-ceiling tests of section 10.
- **#418.** It defines the C structs (R1.10), converts and checks as R1.11 says, lays out its arena as R1.12 says, maps verdicts and errors as R1.13 and R1.14 say, and adds the test of R4.2.
- **#20.** No change beyond the names: R2 calls `compile_fastpath`, `load` and `eval`, and R5 calls `classify`.
- **#71.** Its step 8 writes the fast-path blob by calling `compile_fastpath` (R3.3), and its `compile` takes `DeviceFacts` (R3.5).
- **#1768.** Its rows are what `FastpathLimits::from_limits` reads, and it settles their units with #279 (Unresolved question 3).
- **#1582.** ARCH-013 reads the edge's `importers` and `paths`, and ARCH-017 reads the exemption list.
- **#246.** It aligns `c-abi.md` section 2 with `tables.md` as merged (Unresolved question 2).

Filed on acceptance, each linked as it blocks:
- the `architecture.toml` change of section 11, a protected change for lead-agent-kit, blocking #418 and #414;
- the `surfaces.toml` entries of R6.1, a protected trust-core change, blocked by #1817;
- the design/03 amendments of section 11, for the chief architect.

## Surfaces changed
- `grdr-fastpath` (public crate, layer 1, `experimental`): its first surface, the items of section 1 and the module `layout` of section 2.
- `grdr-core` (public crate, layer 1, `experimental`): module `compile::fastpath`, with the items of section 3.
- `grdr-fastpath-ffi`: no Rust surface of its own beyond the `extern "C"` items of `c-abi.md`; this RFC places the `#[repr(C)]` structs there.
- As proposals: two `surfaces.toml` entries; the `architecture.toml` edge keys, ARCH-017 exemption entries and independent-pair record; the design/03 text of section 11; area `COMPILE` in `schema/codes/`.
- No change to `tables.md`, `c-abi.md`, `status-codes.toml`, a protobuf package, the Cedar schema, a same-layer edge, the spine or the licence policy.

## Alternatives
- **The `#[repr(C)]` input and verdict in `grdr-fastpath`, re-exported by the FFI crate** (#405 R1 as written; RFC 0004 D10). The Rust API would carry raw pointers and `struct_size` that safe Rust cannot read, a second input type beside the safe one, and the C ABI's minor rule inside the crate's SemVer line. Rejected for R1.8.
- **A borrowed handle only, `Tables<'a>`.** It matches C, but the daemon owns its buffers, and safe Rust cannot store a handle beside the buffers it borrows. The daemon would need `unsafe`, a leaked buffer per swap, or a self-referential dependency. Rejected for R1.9.
- **The handle inside the arena in Rust too.** Writing a typed value into caller bytes needs `unsafe`. Rejected; the FFI crate does it (R1.12).
- **`#[non_exhaustive]` error enums.** The FFI match would need a wildcard, and a new variant would map silently. Rejected for R1.6.
- **One error variant per TV rule.** It is 33 variants that #245 can still renumber. `TvRule` carries the number. Rejected.
- **Codes in `schema/codes/fastpath.toml`** (option (a)). Rejected for section 5.
- **The cap as a generated constant in `grdr-fastpath`.** Rejected for section 6.
- **`compile_fastpath(bundle) -> Blob`** (#405 R3 as written). It drops the floor report #414 and #71 read, and the device facts and limits `tables.md` sections 2 and 13 need. Rejected.
- **`compile_fastpath` over an effective bundle.** That type does not exist yet (#71), and the verified bundle is the only input a host can vouch for (design/03 section 3). Rejected for now. When #71 lands, both call one emitter (R3.3).
- **A separate layout crate.** It adds a crate and two edges, and gives `grdr-fastpath` a dependency against design/26 section 2. Rejected.
- **The layout defined in `grdr-core` and read again by `grdr-fastpath`.** Two definitions of one format (P17), and the edge runs from `grdr-core` to `grdr-fastpath`, not back. Rejected.
- **`classify` behind a `test-util` feature.** ARCH-008 allows the feature, but a build-dependent public surface is harder to reason about than a small public function. Rejected.
- **`Display` on errors.** The crate renders nothing, and person-facing text is language tokens (D-69). Rejected for R1.7.

## Drawbacks
- Two input types, `Input` and `grdr_fp_input`, with a conversion that #418's differential has to hold.
- Every function carries the storage parameters `B` and `A`.
- Exhaustive enums make every new variant a breaking change, which `experimental` allows and a later class will price.
- The FFI crate needs one more `unsafe` block, to place the handle in the arena.
- That storage returns the same bytes on every call is a host obligation the library cannot check; it can only refuse to answer from bytes it did not validate (R2.7).
- The fast-path errors take an ARCH-017 exemption, so the lint carries one more data entry.

## Unresolved questions
1. **#245 is not merged.** Round 4 is pending on `issue/245`. This RFC reads `tables.md` at `115ec8b`. Its items name rule numbers and argument faults, not rule content, so a change to a TV rule's content, an input check or the cost model changes no item here. A change that adds an error class, a function, or a header field the compiler writes from `limits.toml` is an amendment of this RFC. Accepting this RFC does not wait on #245, and #409, #410, #412 and #414 each already require it.
2. **`c-abi.md` at `ca039ed` differs from `tables.md` at `115ec8b`.** Section 2's `grdr_fp_load` row applies "TV-15 to TV-31", where `tables.md` has 33 rules. Its `grdr_fp_eval` check 3 makes an action class above `action_class_count` an argument error, where `tables.md` section 6 gives `pass` with scope `none` within the ABI. Its `expiry_ns` comment says "0: no bound beyond the scope", where `tables.md` section 6 makes 0 "never reused" and all ones "until the scope ends". Check 3 also points the name form at TV-20, the path grammar, rather than section 3.3. #246 aligns these with `tables.md` as merged. This RFC follows `tables.md`, and #418 is blocked by #246.
3. **The units of #1768's rows.** #279 R1 gives a bound one of `bytes`, `count`, `ms` or `permille`, while #1768 asks for nanoseconds with all ones meaning until the scope ends. #1768's lead settles the form with #279: a nanosecond unit, or a millisecond row the compiler converts with checked arithmetic, plus a way to write "until the scope ends". Either way R5.4 holds.
4. **The ARCH-017 exemption list.** RFC 0002 (#1688, in review) proposes its form. If neither RFC is accepted with it, the `architecture.toml` item of section 11 creates the list with these entries.
5. **Types other items define.** `PathContext` (#221), `Ineligible` (#216), `PolicyCompileError` (#71) and `RuleId` (the policy module, #212) are named here and defined by their items. If one of them lands with another name, the item that lands it renames the use here, which changes no rule of this RFC.

## Review
Review happens on #405. The review calls for the nine persona council seats and `eval-architecture`, the `[kinds] rfc` row of `.claude/risk-tiers.toml` on `main` at `4e46c2c`. This RFC states the public API of two trust-core paths (`crates/grdr-fastpath/**` and `crates/grdr-core/src/compile/fastpath*`), and #405 is high tier with `public_api_change`. So the review also calls for `eval-security` and `eval-adversarial`, the row #1821 makes data, and `eval-api`, that trigger's row. At least one evaluator runs on the other model from the one in the metadata block (owner instruction 7).

Every seat comment and every evaluator verdict on this RFC names the blobs it read, as full 40-character ids, on fixed lines (RFC 0001, "Review binds the decision"; #1798):
- **RFC file:** `git rev-parse <commit>:rfcs/0005-fastpath-rust-surface.md`, with the commit it read.
- **Proposed text:** none. This RFC decides no pinned path of `rfcs/pins.toml`, so it adds no decision line and commits no evidence.
- **Base:** the spine pin in force, `a80859235e7a2a4444648d6fa8d389d78dde6be9`.
- **Contracts read:** the blobs of `tables.md`, `c-abi.md` and `status-codes.toml` it read, with their commits, from section 0 or newer ones.

A comment that cannot compute an id says so on that line and is not a pass. The decision rests on an `eval-architecture` pass that names the RFC file blob it decides. No verdict by an evaluator of this review may fail that blob. The file the decision commits may differ from that blob only in `State:`, `Decision record:`, link lines under this section and the `Decision` section, as RFC 0001 allows.

## Decision
None yet.
