RFC: 0005
Title: The fast-path Rust surface: grdr-fastpath types, load and eval, compile_fastpath, its errors and the per-call cap
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #405
Spine: D-05, D-15, D-20, D-41, D-60, D-61, D-71, P5, P8, P9, P14, P17 (no spine text changes)
Surfaces: the public crates `grdr-fastpath` (its first surface), `grdr-fastpath-ffi` (where its `#[repr(C)]` structs live) and `grdr-core` (module `compile::fastpath`); a new `[[crate]]` row kind in `surfaces.toml`, with three rows, all `experimental`; proposed changes to the host contract (`c-abi.md` and `status-codes.toml`, including a new status and arena custody, and `tables.md` sections 6, 10, 11 and 13), carried by #246 and #245; proposals for `architecture.toml`, `limits.toml`, design/03, design/12 and design/26. No wire format, Cedar schema or same-layer edge changes
Decision record: none yet

To comment, write on issue #405 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This is revision 3. It answers the round 2 verdicts of `eval-security` and `eval-architecture`, after revision 2 answered round 1 (Review). The comments "RFC 0005 revision 2" and "RFC 0005 revision 3" on #405 list every finding and where it went. The text below is normative on its own.

## Summary
This RFC fixes the Rust surface of the fast path: the types and functions of `grdr-fastpath`, the table layout module that `grdr-core` writes through, and `compile_fastpath` in `grdr-core`. It answers R1 to R7 of #405.
- The library takes a safe, borrowed input and returns a verdict enum whose variants carry their own data, scope included.
- The `#[repr(C)]` mirrors of `grdr_fastpath.h` live in `grdr-fastpath-ffi`, because only that crate may read raw pointers.
- The tables handle is generic over who owns the blob and the arena, so the daemon can own them in safe Rust and the C library can borrow them. Custody of both, the arena included, is a host obligation. What a call re-checks of that storage is a closed list, applied at the first read of what each check guards, and a change that keeps the list true is not detected.
- A blob or arena that fails a re-check gets a new status, `GRDR_E_CHANGED`. The host then counts the floor as missing and reloads within a bound, with stated exits.
- Error variants are exempt from ARCH-017 one variant at a time. Each is bound to a status row through the FFI crate, and to a registered code through the daemon's floor module (#427).
- The per-call cap and three other bounds travel in the blob header, written by the compiler from `limits.toml`, as #245 rules. A host checks them against its own ceilings.
- All three crates enter `surfaces.toml` as `experimental`, through a new `[[crate]]` row kind. No dependency or edge is added.

## Motivation
WI-0017 (#20) and its sub-issues #409, #410, #412 and #414, and EM-2 (#418), all build against a Rust surface no document states. #245 fixes the blob bytes and #246 the C functions. Design/26 section 2 says "Our daemon links `grdr-fastpath` directly from Rust", and #378 leaves `compile_fastpath` out of scope. `grdr-fastpath` and `grdr-core` are public crates in layer 1, so their surfaces change only by RFC (D-61; design/30 section 3).

Read together, the items already disagree:
- #405 R3 has `compile_fastpath` return a blob, while #414 R1 returns a blob and a floor report.
- #412 R2 makes an action class outside the table's vocabulary an argument error, while `tables.md` section 6 answers `pass` with scope `none` for a class within the ABI.
- #409 R2 asks for "the layout types of the RFC", which do not exist.

Nothing says where the `#[repr(C)]` structs live, how the daemon holds tables it loaded, how an error variant gets a code when the crate has no dependency, or where the cap comes from. Each item would otherwise answer on its own.

## Design

### 0. What this RFC fixes, and what it reads
It fixes the Rust items, their placement, their signatures, and which error or value each case gives. The bytes of the blob, the numbered TV rules, the evaluation semantics, the cost model and the cache-scope rules are `spec/host-contract/tables.md` (#245). The C functions and structs are `spec/host-contract/c-abi.md` (#246), and the header's generated form is RFC 0004. This RFC refers to those texts. Where it needs them changed, it lists the change for the item that owns the text (section 12).

It was written against, and its decision rests on, exactly these blobs:
- `tables.md` blob `8339bea85bb2ee563dd0dfe38befee871a5b7d12`, on `issue/245` at `115ec8b`;
- `c-abi.md` blob `b147c9dbd81068cd0d95cad4813bfee5e702fe30` and `status-codes.toml` blob `abcaa9704974359cdf7fac76712263b7b6f6f74b`, on `issue/246` at `ca039ed`;
- the spine pin in force, blob `a80859235e7a2a4444648d6fa8d389d78dde6be9`, on `main` at `4e46c2c`.

Where `c-abi.md` at `ca039ed` and `tables.md` at `115ec8b` disagree, this RFC follows `tables.md` (Unresolved question 2). Round 3 of #245 failed on `115ec8b` (Unresolved question 1), so this text may need an amendment when #245 lands.

Out of scope, as #405 says: the blob layout (#245), the C functions (#246), the shim's fail-safe table (#71) and the bounded hook-field scanner of design/07. The last two join `grdr-fastpath` later, each by an amendment of this RFC, with their own error enums (R4.6).

### 1. The `grdr-fastpath` surface (R1, R2)

```rust
// grdr_fastpath: #![no_std], #![forbid(unsafe_code)], #![deny(clippy::arithmetic_side_effects,
// clippy::as_conversions)], no dependency, no alloc.
pub mod layout;                                    // section 3

pub struct Tables<B, A> { /* private: blob B, arena A, their validated lengths, a copy of the header */ }

pub fn arena_size(blob: &[u8]) -> Result<usize, Error>;
pub fn load<B, A>(blob: B, arena: A) -> Result<Tables<B, A>, Error>
where B: AsRef<[u8]>, A: AsRef<[u8]> + AsMut<[u8]>;
pub fn eval<B, A>(tables: &Tables<B, A>, input: &Input<'_>) -> Result<Verdict, Error>
where B: AsRef<[u8]>, A: AsRef<[u8]>;
pub fn classify<B, A>(tables: &Tables<B, A>, input: &Input<'_>) -> Result<Option<ClassBits>, Error>
where B: AsRef<[u8]>, A: AsRef<[u8]>;
pub fn interest<B, A>(tables: &Tables<B, A>) -> Result<Interest<'_>, Error>
where B: AsRef<[u8]>, A: AsRef<[u8]>;

impl<B, A> Tables<B, A> {
    pub fn header(&self) -> &layout::Header;                  // the copy every call reads
    pub fn check_pairing(&self, labels: &Labels) -> Result<(), Error>   // R2.3 step 1
    where B: AsRef<[u8]>, A: AsRef<[u8]>;
    pub fn reason(&self, index: u32) -> Result<Reason<'_>, Error> where B: AsRef<[u8]>, A: AsRef<[u8]>;
    pub fn into_parts(self) -> (B, A);
}

pub struct Input<'a> {
    pub action_class: u16,            // tables.md section 1 numbers
    pub principal_kind: u16,          // Session 1, Process 2
    pub exe_digest: Option<Digest>,
    pub path: Option<Path<'a>>,       // already resolved by the host
    pub dest: Option<Dest<'a>>,
    pub labels: Labels,
    pub grant_digest: Option<Digest>,
}
pub struct Digest(/* private: [u8; 32], never all zero */);
impl Digest { pub fn new(bytes: [u8; 32]) -> Option<Digest>; pub fn as_bytes(&self) -> &[u8; 32]; }
pub enum Path<'a> { Utf8(&'a [u8]), Utf16Le(&'a [u8]) }    // bytes at any alignment
pub struct Dest<'a> { pub host: Host<'a>, pub port: u16 }
pub enum Host<'a> { Name(&'a [u8]), Ipv4([u8; 4]), Ipv6([u8; 16]) }
pub struct Labels { pub bits: u64, pub bundle_tag: u64 }

pub enum Verdict {
    Pass { scope: CacheScope },
    Deny { hit: Hit, scope: CacheScope },
    StepUp { hit: Hit },              // always scope none (tables.md section 6, rule 1)
}
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

pub enum Error { Arg(ArgFault), Abi, Bundle(BundleFault), State, Changed }
pub enum ArgFault { Arena, ActionClass, PrincipalKind, Path, Destination, Reason }
pub enum BundleFault { Rule(TvRule), EvalCap, TooLarge }
pub struct TvRule(/* private: a rule number of tables.md section 5 */);
impl TvRule { pub fn number(self) -> u8; }
impl Error { pub fn rule(&self) -> Option<TvRule>; }      // TV-3 for Abi
impl core::fmt::Display for Error;
impl core::error::Error for Error;
```

Types (R1):
- R1.1. The crate is `#![no_std]` with no `alloc`, no dependency and `#![forbid(unsafe_code)]`. It denies `clippy::arithmetic_side_effects` and `clippy::as_conversions` at its root, so no cast can truncate silently. It builds for `wasm32-unknown-unknown` and every host triple (design/26 section 2, ARCH-003).
- R1.2. `Input` is the safe form of `grdr_fp_input`. Its fields keep the names, numbers and meanings of `c-abi.md` section 2.1, with these differences:
  - `struct_size` is a C concern, and `process_key` is read by no row, so neither is here;
  - each pointer and length pair is a slice, and `path_encoding` and `dest_kind` become the variants of `Path` and `Host`;
  - absence has one form, `None`: an all-zero C digest is `exe_digest: None` or `grant_digest: None`, and `path_len` 0 is `path: None`;
  - a `Some` path with an empty slice is `Arg(Path)`, and so is a `Path::Utf16Le` slice of odd length. That slice holds the little-endian code units as bytes, so the FFI never builds an aligned `u16` slice from a host pointer.
- R1.3. `Verdict` holds each pairing `tables.md` section 6 allows, and no other. `Pass` names no row. `Deny` and `StepUp` carry the winning row's index and its reason index (#412 R8). `StepUp` carries no scope, because its scope is always `none`. `Pass` is not `ALLOW` (design/26 section 2).
- R1.4. `CacheScope` carries the expiry inside the two scopes that have one, so the two meanings of `tables.md` section 6 never meet. `Call` and `None` are never reused. `Session` and `Bundle` carry `layout::Expiry`. The C numbers of scopes are the FFI's (section 5).
- R1.5. `Error` has one variant per fast-path status: `Arg` is `GRDR_E_ARG`, `Abi` is `GRDR_E_ABI`, `Bundle` is `GRDR_E_BUNDLE`, `State` is `GRDR_E_STATE` and `Changed` is the new `GRDR_E_CHANGED` (section 12).
  - `TvRule` names the failing rule, so a test can tell which rule failed (#409 R5).
  - `BundleFault::EvalCap` is an input whose cost exceeds `eval_cap`. `BundleFault::TooLarge` is a blob whose arena size is above `isize::MAX` on this target.
  - `ArgFault::Reason` is a reason index that names no entry.
  - `Changed` is a failed re-check of section 2.
- R1.6. Every public enum is exhaustive, so a new variant fails the FFI crate's build until it maps to a status (section 5). `#[non_exhaustive]` would force a wildcard arm there.
- R1.7. Formatting:
  - `Error` and its fault types derive `Debug`, `Clone`, `Copy`, `PartialEq` and `Eq`, and carry structural values only, never input bytes.
  - `Display` writes the same text as `Debug`: the variant path and its numbers, which are identifiers, not prose. With `Display`, `Error` implements `core::error::Error`. No other type implements `Display`, and the crate formats no text a person reads (`renders = "none"`; D-69). A host that reports a fast-path failure to a person does so under its own registered code (R4.3).
  - A type that holds a `content` or `identifier` field implements no derived `Debug`. In `grdr-fastpath` those are `Input`, `Path`, `Dest`, `Host`, `Digest`, `Labels`, `Header` and the `layout` records that hold a digest, an address or a pool string. In `grdr-core` they are `Blob`, `FastpathOutput`, `Facts`, `DeviceFacts` and `Volume`. Each has a redacting `Debug` that prints field names and lengths only, so an assertion or a wrapped error cannot carry the value into a log. `Tables` and `Interest` print counts only. The types other items define for the floor report (R3.4) follow the same rule in those items.
- R1.8. The `#[repr(C)]` structs of `grdr_fastpath.h` live in `grdr-fastpath-ffi`, not here (section 5). A struct holding raw pointers can be read only through `unsafe`, which this crate forbids. Keeping the structs in the FFI crate also keeps the C ABI's minor-version rule (trailing fields behind `struct_size`) apart from this crate's SemVer line (D-71). That answers RFC 0004's unresolved question 2 and its D10.
- R1.9. `Tables<B, A>` is generic over who owns the blob and the arena.
  - The FFI crate uses borrowed slices. The daemon, the first consumer, can own both, for example as `Box<[u8]>`, and keep the handle in safe Rust with no self-referential helper.
  - Whatever the owner, the handle holds both for as long as it lives. While it lives, its arena cannot be passed to another `load` (#409 R7; `tables.md` section 10).
  - The host keeps both in custody, the arena as much as the blob (R2.14). What a call re-checks of that storage is section 2's.

Functions (R2):
- R2.1. `arena_size` applies TV-1 to TV-14 of `tables.md` section 5 in number order, then returns the arena size, computed from the header alone (`tables.md` section 7). The length TV-6 compares is `blob.len()`, compared in 64-bit arithmetic, so a blob longer than `u32::MAX` bytes fails TV-6 on every target. A size above `isize::MAX`, the largest slice any owner can hold, is `Bundle(TooLarge)`, on 32-bit targets as on 64-bit ones.
- R2.2. `load` checks in this order:
  1. it applies TV-1 to TV-14;
  2. it checks the arena, and an arena shorter than `arena_size` is `Arg(Arena)`;
  3. it applies TV-15 to TV-33;
  4. it builds its indices in the arena and returns the handle, with the two storage lengths and a copy of the header.

  It is never lazy. It writes only the arena, never copies the blob and allocates nothing. On any error the caller keeps the tables it had. `load` takes the blob and the arena by value, so an owning caller's new buffers are dropped on an error; `into_parts` returns them from a live handle.
- R2.3. `eval` checks in this order and stops at the first failure:
  1. `check_pairing`: RC1 of section 2, which is `Changed`, then a `labels.bundle_tag` that differs from the first eight bytes of the handle's `bundle_digest`, which is `State`;
  2. the argument checks `tables.md` section 6 gives the library, each before any read of the blob or the arena:
     - an action class of 0 or above the ABI's highest is `Arg(ActionClass)`;
     - a principal kind of 0 or above `principal_kind_count` is `Arg(PrincipalKind)`;
     - a path whose code units exceed `path_max_units` is `Arg(Path)`, checked before the path is decoded; so is a path not well formed or not in the form section 6 checks;
     - a destination name that is empty, longer than `layout::NAME_MAX_BYTES` or not in the canonical form of section 3.3 is `Arg(Destination)`;
  3. an action class within the ABI but above `action_class_count`, which returns `Pass { scope: None }` with no cost check, no class bits and no read of the blob or the arena;
  4. the cost, which reads the class's run from the arena and each path pattern's length from the pool; a cost above `eval_cap` is `Bundle(EvalCap)`, before any matching;
  5. evaluation by `tables.md` section 6.

  Steps 4 and 5 read storage. Each re-check of section 2 applies at the first read of what it guards, in whichever step that read happens (R2.12). So a run index or a pattern that fails its re-check gives `Changed` at step 4, never `Bundle(EvalCap)`. `check_pairing` is step 1 on its own: `eval` and `classify` call it first, and the FFI calls it before its own field and length checks (R1.11), so C and Rust give one answer for one input. An input gets the same `Arg` answer whatever the vocabulary of the tables. `eval` reads only the tables and the input, writes nothing but its return value, and never returns a verdict on a failure.
- R2.4. `classify` makes steps 1 to 4 of R2.3, then returns the class bits of `tables.md` section 6. For the class of step 3 it returns `Ok(None)`, since no class bits are computed for it. Its step 4 reads the run as `eval`'s does, so it makes RC2. It never returns partial bits. #20 AC-2 holds it against `grdr-core`'s classifiers, so it is public.
- R2.5. `interest` returns the four interest tables and the string pool as views into the blob (`tables.md` section 3.5). Their places come from the handle's header copy, so only RC1 can fail it, as `Changed`.
- R2.6. `eval`, `classify`, `interest`, `reason` and `check_pairing` take `&Tables`. `Tables<B, A>`, `Interest` and `Records` are `Send` and `Sync` whenever `B` and `A` are. The crate holds no interior mutability and no global or thread-local state. So any number of threads may evaluate the same tables at once (design/26 section 2).
- R2.7. `reason` returns the reason code and the instantiated rule id of one entry of the reason-code table. An index at or above the table's count is `Arg(Reason)`, and a failed RC1, RC5 or RC6 is `Changed`. A Rust host takes the rule id it records from here, so it never reads the blob's layout itself (P17).
- R2.8. Every value a call reads from the header (counts, offsets, `eval_cap`, the vocabulary sizes, the expiries and `bundle_digest`) comes from the copy `load` kept, never from the blob again.

### 2. What a call re-checks (R2)
The storage the handle holds can change after `load`. In safe Rust a type with interior mutability can return other bytes from `as_ref()`. Through the FFI, host memory is behind raw pointers. Re-running the TV rules per call is not open: each rule is linear in the blob's length (`tables.md` section 5), and a call is bounded by the rows it touches (`tables.md` section 7). So the property is this:
- R2.9. For any bytes the storage returns, at any time, every function is free of panics, reads only inside the views of R2.10, and does no more work than the cost bound of `tables.md` section 7 plus one scan of the input path.
- R2.10. Each function takes one view of each storage per call, one `as_ref()` of the blob and one of the arena, and reads only those views. RC1 holds for exactly those views. A read that would fall outside a view is `Changed`, never a default value such as an empty run.
- R2.11. The arena holds the per-action-class run index and nothing else, besides the FFI's handle (R1.12). An index added to the arena later is an amendment that adds its re-check here.
- R2.12. A function returns `Changed` when one of these re-checks fails. Each re-check applies at the first read of what it guards, in every step of every entry point, and never after a result computed from what it guards:
  - **RC1, storage lengths.** The blob view's length equals the length `load` validated, and the arena view's length is at least the size `load` used. Every function makes this check first, inside `check_pairing` for `eval` and `classify`.
  - **RC2, run index.** At the first read of an action class's run, in the cost step and in evaluation, the run lies inside the floor-row section. Where they exist, the row just before the run has a lower action class, and the row just after it a higher one. The run's first and last rows have the run's class. `load` writes a class with no rows as an empty run at the position its rows would sit. TV-27 sorts rows by class, so with an unchanged blob any change to a run entry, an emptied run included, fails this check. It costs at most four row reads per call. `eval` and `classify` make this check.
  - **RC3, rows touched.** Each row of the run has the run's action class, an outcome of 2 or 3, a principal kind at most `principal_kind_count`, and a reason below the reason table's count (TV-26 and TV-28 to TV-30, on those rows). `eval` makes this check.
  - **RC4, entries touched.** Each host entry read has a kind of 1 to 5 (TV-16), and a `prefix_len` of at most 32 for kind 3 and at most 128 for kind 4 (TV-22's bound), before the prefix indexes the address. Each path entry read has a class bit of at most 63 (TV-24). `eval` and `classify` make this check.
  - **RC5, pool references.** Each pool reference a call follows, including each pattern whose length the cost step counts, lies inside the pool. `eval`, `classify` and `reason` make this check.
  - **RC6, strings.** Each string a call decodes, including each pattern whose characters the cost step counts, is what TV-19 allows for it: valid UTF-8, UTF-16LE that decodes, or visible ASCII for a reason code or rule id. `eval`, `classify` and `reason` make this check.
- R2.13. A change that keeps every re-check true is not detected, and the call answers from the changed bytes. With RC2 as stated, such changes are blob changes: a row's outcome moved from 2 to 3, a label or class bit, a grant digest, an entry moved inside its section, and an order that TV-25 or TV-33 held. In C they are also changes to the handle, whose stored lengths, header copy and slice addresses are the references the re-checks compare against. Custody is the only defence against both, and the re-checks catch accident, not intent.
- R2.14. Custody covers the blob and the whole arena. The host keeps both, the handle included, in memory no less privileged process can write. They stay unchanged from `load` until the host's quiescence point after it retires the tables. Today `tables.md` section 11 states custody for the blob only, and `c-abi.md` says only that the blob and arena "must outlive the tables". Section 12 gives #245 and #246 the text that widens both. In the FFI the slices rest on that promise, which is the safety invariant of R1.12. A host that breaks it gets no claim beyond accident.

A sealed storage trait cannot make this a type:
- a trait can promise unchanged bytes to the compiler only as an `unsafe trait`, which `forbid(unsafe_code)` refuses;
- a safe sealed trait can be implemented only for types this crate can name, and with no `alloc` that excludes `Box<[u8]>` and `Vec<u8>`, the daemon's owners. A `std` feature that names them would make a public trait's implementations depend on a build feature;
- no trait reaches the host memory behind the FFI's raw pointers.

So the property stays with custody, and the re-checks are a closed list that tests hold (R2.15).
- R2.15. The tests, each over a test storage type whose bytes change after `load`:
  - one per re-check, `fastpath_changed_rc1` to `fastpath_changed_rc6`, each breaking exactly that re-check and expecting `Changed` from every function that makes it;
  - for RC2, `fastpath_changed_rc2_cost`, where the altered run would also exceed `eval_cap` and the answer is `Changed`, not `Bundle(EvalCap)`, from `eval` and `classify`; and `fastpath_changed_rc2_empty`, which empties a run that has rows;
  - for RC4, an entry whose `prefix_len` is above its kind's bound;
  - `fastpath_one_view`, with a storage that counts its `as_ref()` calls and returns a shorter slice on the second, expecting one call per storage per function call;
  - `fastpath_changed_undetected`, which moves a row's outcome from 2 to 3 and expects the new verdict and no error, so R2.13 is a tested fact.

### 2a. The host after `Changed` (R2)
`Changed` means the tables the handle reads are no longer the ones `load` validated. The status's `handle_after`, `reload-required`, names a host state with these exits. A host's floor state is an explicit state type (design/03 section 10). Our daemon's is #427's, and a partner host's follows the same rules through the contract text of section 12.
- R2.16. On `Changed` the host stops using that handle at once: no further call takes it. It keeps the old interest filters installed, so selection never shrinks (`tables.md` section 10). It frees the old blob and arena only after its quiescence point, when no call on them can still be running.
- R2.17. Until a load succeeds the floor counts as missing, as it does at start with no tables, and the device is Degraded. The host contract's minimum is that fail-closed classes deny and the others take their class's `on_failure`. Our daemon answers as #427 R8 does, every class denying with `degraded_reason` `floor-missing`. No answer comes from the dropped handle, so the device is never left unprotected (design/12 E3.3).
- R2.18. The host reloads from a fresh copy that it verifies again from its source. That is the signed envelope it accepted, or for our daemon a fresh compile instance (#1538), and never the private copy that changed. Reloading follows a named retry policy, `[retry.fastpath-reload]` in `limits.toml`, so the number of attempts and the time they take are bounded (design/03 section 10).
- R2.19. The exits from the floor-missing state:
  - a load that succeeds and passes the host's ceilings and binding checks returns the host to serving with the new handle, and Degraded clears unless another cause holds it;
  - a load that fails, with `GRDR_E_BUNDLE`, `GRDR_E_ABI` or a host refusal, stays floor-missing and tries again under the policy. A failed reload never returns to the dropped handle, so `last-known-good` here means no tables, because the dropped tables are not good;
  - `Changed` again on a fresh copy of the same envelope ends reloading. The cause is then a defect in `load` or the library, not custody, so the host stays floor-missing and reports it under its own code;
  - an exhausted retry policy ends reloading in the same way, with its own code;
  - a new bundle activation (#1538), or a restart of the host, is the exit from a state where reloading has ended.
- R2.20. `fastpath_reload` (#427) tests each transition of R2.16 to R2.19 with an injected clock and a storage that changes: a successful reload, a reload that fails a TV rule, `Changed` on a fresh copy of the same envelope, an exhausted policy, and a new activation. For each it asserts the floor-missing answers, the Degraded state, the codes reported, and that the old handle is never called again.

### 3. The table layout (R1, R3)
`grdr_fastpath::layout` is the one definition of the blob's layout that the writer and the reader share. It holds:
- the numbers `tables.md` fixes, as `pub const`: the magic, `table_format` 1, the 224-byte header and the 20-byte stable prefix, the ten sections, each record size, the kind values, the row outcomes and verdict numbers, the 253-byte name maximum of section 3.3 (`NAME_MAX_BYTES`), and the fast-path ABI version (`ABI_MAJOR`, `ABI_MINOR`, `abi_version()`) with the highest action class it carries (15 at 0.1). These are the format, like a protobuf field number, not tunable bounds, so they are not `limits.toml` entries (ARCH-019 targets bounds);
- `Header`, with one public field per field of `tables.md` section 2, of the same name and width, and `SectionEntry`;
- `Section`, the ten sections in directory order with their record sizes;
- one record type per record of `tables.md` section 3: `FloorRow`, `PathEntry`, `HostEntry`, `ExeEntry`, `ProcessScopeEntry`, `PortRange` and `ReasonEntry`, each with public fields of the document's names and widths;
- `Record`, a sealed `Copy + 'static` trait implemented by each record type, which gives the record size and decodes one record. It is sealed by a private supertrait, so no other crate can claim a type is a table record;
- `encode` and `decode` for the header and every record, over byte arrays of the exact size, with no validation, which is `load`'s;
- `Expiry`, which is `ScopeEnd` or `After(Nanos)`, where `Nanos` refuses 0 and the all-ones value, with the header mapping of `tables.md` sections 2 and 6;
- the cost function of `tables.md` section 7, which `eval` applies to the input and the compiler to its worst case, so the formula exists once.

Rules:
- R3.1. Of `grdr-core`, only module `compile::fastpath` imports `grdr-fastpath`, and only `layout`: its types, its constants, `encode` and `decode`, and the cost function. That is what "table layout only" on the `grdr-core` to `grdr-fastpath` edge means (design/03 section 2), and the edge text names the cost function (section 12). Tests of `grdr-core` (#20, #414) may also call `load`, `eval` and `classify`, the blob's real consumer. The other edges into `grdr-fastpath` are unchanged:
  - `grdr-fastpath-ffi` uses the whole surface;
  - `grdr-ffi` and `grdr-wasm` keep their listed edges, and this RFC adds no use through them, since `grdr_engine_compile_fastpath` reaches the blob through `grdr-core`;
  - the daemon, a layer 4 program, uses the evaluator surface.
- R3.2. Sharing `layout` makes a layout fault symmetric, so it is not its own oracle. The oracles are independent of it:
  - #409's reference validator under `tests/`, which shares no code with `src/`;
  - #412's hand-encoded fixture blobs;
  - #414's golden rows, written by hand from the Cedar text;
  - #20's differential against `cedar-policy`.

  The shared cost function's independent oracle is the comparison-count vectors of `tables.md` section 7.

### 4. `compile_fastpath` (R3)

```rust
// grdr_core::compile::fastpath
use grdr_fastpath::layout::Expiry;

pub fn compile_fastpath(
    bundle: &VerifiedBundle,
    facts: &Facts<'_>,
    limits: &FastpathLimits,
) -> Result<FastpathOutput, FastpathCompileError>;

pub struct FastpathOutput { pub blob: Blob, pub report: FloorReport }
pub struct Blob { /* private: Vec<u8> */ }
impl Blob { pub fn as_bytes(&self) -> &[u8]; pub fn into_vec(self) -> Vec<u8>; }

pub enum Facts<'a> { Device(DeviceFacts<'a>), Relay }
pub struct DeviceFacts<'a> { pub templates: &'a PathContext, pub volumes: &'a [Volume<'a>] }
pub struct Volume<'a> { pub mount: &'a [u8], pub case: CaseRule }
pub enum CaseRule { Sensitive, Insensitive, Unknown }

pub struct FastpathLimits { /* private: the four header values */ }
impl FastpathLimits {
    pub fn from_limits() -> Result<FastpathLimits, FastpathCompileError>;
    pub fn new(eval_cap_steps: u32, path_max_units: u32, expiry_bundle: Expiry,
               expiry_session: Expiry) -> Result<FastpathLimits, FastpathCompileError>;
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

pub enum FastpathCompileError {
    Effective(EffectiveCompileError),  // steps 1 to 7 of design/12 section 7, with their own codes
    CostAboveCap { action_class: u16, cost: u64, cap: u32 },
    TooLarge,                          // the blob or a section would pass 4,294,967,295 bytes
    Limit(LimitRow),
}
pub enum LimitRow { EvalCapSteps, PathMaxUnits, ExpiryBundle, ExpirySession }
```

- R3.3. `compile_fastpath` runs steps 1 to 7 of design/12 section 7 on the verified bundle. It then writes step 8's fast-path blob in the canonical form of `tables.md` section 4, through `grdr_fastpath::layout` only. It is pure and deterministic: one bundle, one set of facts and one set of limits give the same bytes on every target for one compiler version (D-05; R6.6). The effective-policy compiler of #71 writes its step 8 blob by calling this function, so the blob has one writer.
- R3.4. It returns the floor report beside the blob. The report has one entry per rule of a fail-closed class, in rule-id order, so nothing is dropped silently (#414 R6). Its outcomes are #414's and those `tables.md` section 13 adds.
  - `RuleId` is the instantiated rule id of design/12 section 7 step 4, the policy module's type.
  - `Ineligible` and `EffectiveCompileError` are the types #216 and #71 define.
- R3.5. `Facts::Device` carries the device-wide template values and each volume's mount point and case rule:
  - the templates are #221's `PathContext`, whose `$WORKSPACE` and `$SESSION_TMP` the fast path never reads;
  - the case rules decide `path_fold_classes` (`tables.md` section 13);
  - `CaseRule::Unknown` folds, and so does any volume a pattern can reach that `volumes` does not list, because folding errs toward `deny` (`tables.md` section 13);
  - a change of the device's volumes is a change of its facts, and the host compiles again (#1538).

  `Facts::Relay` is a partner relay compile with no per-device facts. It sets every bit of `path_fold_classes` and compiles no rule whose pattern holds a template (`tables.md` section 9). `DeviceFacts` is the device-facts input of design/12's `compile(layers, packs, device_facts)`, so #71 takes the same type (P17).
- R3.6. `FastpathLimits` carries the four header values the compiler writes.
  - `from_limits` reads the four `limits.toml` rows of #1768 through `grdr-schema`'s generated limits module (#279).
  - `new` lets a caller compile to a lower cap, which is how a host compiles to its own ceiling (R5.3) and how a test meets the cap.
  - Both refuse a value `tables.md` TV-8 would refuse, as `Limit`, naming the row. A test holds `from_limits` to `Ok` on the committed `limits.toml`.
- R3.7. It refuses with `CostAboveCap` a bundle whose worst-case cost for any action class exceeds the cap, taking the path length as `path_max_units`. So a blob it wrote never reaches the cap at run time (`tables.md` section 13).
- R3.8. It writes an interest set that selects every action a floor row can match (`tables.md` section 13). `load` cannot check that property, since no TV rule reads interest coverage, so a compiler test holds it (R3.9). An interest set that selects too little is silent: the floor is never asked about the actions it misses.
- R3.9. `fastpath_compile_interest` (#414) compiles the bundles of #414 AC-4, and AC-5's generated bundles in its soak run. Its inputs are actions in the form a sensor sees them, not only fixed-layout inputs: each carries the fixed-layout fields, plus the acting process's executable path, signing identity, package identity and its lineage to a selected ancestor, which a process-scope entry reads (`tables.md` section 3.5). A catalogue fixture lists the sessions the bundle's catalogue opens, so rows naming `Session` can be judged (`tables.md` section 13).
  - For every action that an unindexed reference matcher in the test finds a floor row of the blob to match, a reference interest selector, written from `tables.md` section 3.5, must select that action.
  - Every floor row of every compiled blob must have at least one matching action in the generated set, so no row passes for lack of a witness. That covers rows naming `Session`, rows covered only through process scope, and rows of classes whose actions carry no target path or destination, such as `elevate`.
  - The class vocabularies are enumerated exhaustively up to 20 class bits and sampled above.
- R3.10. `compiler_version` is the crate's own package version, and no caller can set it. `bundle_digest` and `effective_hash` come from the bundle. The `Blob` makes no alignment promise. A host copies it into private memory before it loads (`tables.md` section 11, custody), and a C host aligns that copy to 8.

### 5. What `grdr-fastpath-ffi` holds (R1)
- R1.10. It defines `grdr_fp_input`, `grdr_fp_verdict`, `grdr_fp_span` and `grdr_fp_interest_view` as `#[repr(C)]` structs and `grdr_fp_tables` as an opaque type, under the names `c-abi.md` section 2 gives. RFC 0004's descriptor describes them there, so its D10 re-export case does not arise. The crate root denies `clippy::as_conversions` as `grdr-fastpath` does, and uses `<*const T>::addr` for addresses.
- R1.11. Each entry point checks its arguments in this order, so that C and Rust give one answer for one input:
  1. address checks, made before anything is read through a pointer, each `GRDR_E_ARG`:
     - a null pointer where the contract needs one;
     - an output range that meets the blob or the arena: the `out` of `grdr_fp_arena_size`, `grdr_fp_load`, `grdr_fp_eval` and `grdr_fp_interest`. Writing through one would change validated bytes while the handle reads them;
     - an input struct whose base-size range meets the arena, since reading it would alias the arena the handle holds mutably;
  2. a `struct_size` below the base size, or a struct whose `struct_size` range meets the arena, `GRDR_E_ARG`;
  3. for `grdr_fp_eval`, `check_pairing` on the handle with the input's labels, so RC1 is `GRDR_E_CHANGED` and a label mismatch `GRDR_E_STATE`, as in Rust;
  4. the checks only C has, each `GRDR_E_ARG`, with every length checked before any slice is built:
     - a blob or arena not 8-aligned; a `path_encoding` or `dest_kind` value outside its set;
     - `path_len` above the handle's `path_max_units`, compared as code units, before the slice exists;
     - a UTF-16LE byte length, `path_len` times 2, computed with `checked_mul`;
     - any byte length above `isize::MAX`, the precondition of `core::slice::from_raw_parts`, for the path, the destination name, the blob or the arena;
     - `dest_name_len` above `layout::NAME_MAX_BYTES`;
     - a blob and arena whose address ranges overlap, which would let `load` write its index into the blob it validated;
     - a path or destination name whose range meets the arena.

  Steps 1 and 2, and the alignment, value-set, overlap and range checks of step 4, have no Rust counterpart, because a Rust caller cannot pass a null, a short struct, an unknown encoding or aliasing slices. The length checks of step 4 come after step 3, as Rust's `Arg(Path)` and `Arg(Destination)` come after its `check_pairing`. For every input both can express, the answers are equal, which #418's differential checks. An all-zero digest becomes `None`, and `path_len` 0 becomes `path: None`. The Rust surface reads bytes at any alignment.
- R1.12. Its arena holds the handle first, then the arena `grdr-fastpath` uses.
  - `grdr_fp_arena_size` is the handle's size rounded up to 8 plus `arena_size(blob)`, in checked arithmetic. A sum above `isize::MAX` is `GRDR_E_BUNDLE`, as `Bundle(TooLarge)` is.
  - `grdr_fp_load` splits the arena, calls `load` with the blob and the second part as slices, and writes the handle into the first part. That is an `unsafe` block with a `// SAFETY:` comment citing the custody text of section 12: the host keeps the blob and the whole arena, handle included, alive, unchanged and out of reach of any less privileged process, from `grdr_fp_load` until its quiescence point after it retires the tables (R2.14).
- R1.13. It maps a `Verdict` to `grdr_fp_verdict`:
  - the verdict numbers come from `layout`;
  - `rule_index` and `reason_code` are `UINT32_MAX` for `Pass`;
  - `StepUp` has scope `NONE`;
  - the scope number is `c-abi.md`'s;
  - `expiry_ns` follows `tables.md` section 6: the header value for `Session` and `Bundle`, where all ones means until the scope ends, and 0 for `Call` and `None`.
- R1.14. It maps `Error` to `grdr_status` in one nested `match` that names every leaf variant, with no wildcard at any depth (R4.2). The constants `GRDR_FP_ABI_MAJOR`, `GRDR_FP_ABI_MINOR` and `GRDR_FP_ABI_VERSION` (RFC 0004 section 9), and the value `grdr_fp_abi_version()` returns, come from `layout`. The cache-scope, path-encoding, destination-kind and status values, which only `c-abi.md` fixes, are its own constants. RFC 0004's `HDR-3` and `HDR-4` hold them to the contract and the registry.

### 6. Error codes (R4)
ARCH-017 binds every error variant to an entry in `schema/codes/<area>.toml`. `grdr-fastpath` has no dependency, so it cannot name `grdr-schema`'s generated codes. Three bindings were weighed:
- **(a) Entries in `schema/codes/fastpath.toml`, with the mapping in `grdr-core`.** The orphan rule keeps `grdr-core` from implementing a `grdr-model` trait for a `grdr-fastpath` type, so the binding would be a function in `grdr-core`. The daemon is the fast path's one Rust consumer, and ARCH-004 keeps `grdr-core` out of its closure, so the mapping would never reach the code that meets the errors.
- **(c) A test-only binding through a `grdr-schema` dev-dependency of `grdr-fastpath`.** A test could hold every variant to a code, but non-test code that constructs those codes would need its own copy of the mapping, which the test cannot see (P17). The test would bind codes nobody raises, or check a copy.
- **(b) Bound in two places, each whole.** Each leaf variant maps to one row of `spec/host-contract/status-codes.toml` through the FFI crate's match, which `HDR-4` holds to the registry. Each leaf also maps to one registered code through the daemon's floor module, where ARCH-017 applies in full.

**Decision: (b), exempted one variant at a time.** The leaves are the twelve variants that carry no fault type: the six of `ArgFault`, `Abi`, the three of `BundleFault`, `State` and `Changed`.
- R4.1. Each leaf has its own entry in the ARCH-017 exemption list of `architecture.toml`, in the list form RFC 0002 section 14 proposes, with typed fields, not prose:
  - `type` and `variant`, such as `grdr_fastpath::ArgFault` and `Arena`;
  - `registry`, `spec/host-contract/status-codes.toml`, and `status`, the row's name;
  - `bound_in`, `grdr-fastpath-ffi`;
  - `coded_by`, `grdr-daemon`, and `code`, the reason of the code R4.3 registers.

  The entries are the one copy of both mappings, leaf to status and leaf to code. The two `match` expressions that implement them are checked against the entries, so neither is a second source:
  - ARCH-017 checks that the registry exists and holds a row named `status`, that `code` is a reason registered in area `FASTPATH` (R4.3), that `bound_in` and `coded_by` depend on the type's crate, and that every variant of a listed type has its own entry, unless it is a wrapper. So a variant added later fails the lint until it has an entry of its own.
  - A wrapper is a tuple variant whose only field is an enum that has entries of its own, here `Error::Arg(ArgFault)` and `Error::Bundle(BundleFault)`. ARCH-017 resolves a wrapper to the entries of its field's type and gives it no entry. Any other variant, a tuple variant over a type with no entries included, needs its own entry. In `grdr-core`, `FastpathCompileError::Effective` is a wrapper over a type bound in the ordinary way (R4.4).
- R4.2. The FFI crate's mapping is one nested `match` naming every leaf, with no wildcard at any depth.
  - A test, `status_per_variant`, reads the entries from `architecture.toml` with `grdr-cabi-testkit`'s row reader (RFC 0004), the FFI crate's existing dev-dependency, and checks the crate's mapping against each entry's `status`.
  - The test's own nested `match`, again with no wildcard, lists the leaves by name only, so a new leaf fails the test's build. A leaf the mapping sends to a status other than its entry's fails the test's run.
  - The same test shows that each fast-path status row is produced by at least one leaf, which is ARCH-017's "every registered code is constructed somewhere" for those rows.
- R4.3. The daemon's floor module (#427, `programs/grdr-daemon/src/floor`) maps every leaf, by a nested `match` with no wildcard, to its own variant of the daemon's error, bound by ARCH-017 to one code each.
  - The codes are in area `FASTPATH` (subsystem: the fast-path evaluator; owner: docs/design/26), with their `/codes` pages and runbooks.
  - `Bundle(Rule(n))` is one code, with the TV number as a structural field.
  - Section 2a's state adds three codes of the daemon's own: entering floor-missing on `Changed`, `Changed` again on a fresh copy of the same envelope, and an exhausted reload policy.
  - #427 registers the codes, and its acceptance gains "every `grdr_fastpath` leaf variant has one registered code". Its test `code_per_variant` reads the entries as `status_per_variant` does and checks the daemon's mapping against each entry's `code`.
  - #1538's `Refused { code }` uses the load-side codes.
  - A person never meets a fast-path error as such. The host applies the class's `on_failure` (D-15) and reports under these codes.
- R4.4. `FastpathCompileError` is in `grdr-core`, which has `grdr-schema`, so ordinary ARCH-017 applies.
  - `CostAboveCap`, `TooLarge` and `Limit` bind to three entries of area `COMPILE` (subsystem: the effective-policy compiler; owner: docs/design/12), with the reasons `FASTPATH_COST_ABOVE_CAP`, `FASTPATH_TOO_LARGE` and `FASTPATH_LIMIT_OUT_OF_RANGE`.
  - `Effective` carries the code of the error it wraps and has no entry of its own (R4.6).
  - Whichever of #71 and #414 lands first creates area `COMPILE` through #278's registry, and #414 adds its three entries.
- R4.5. `grdr_engine_compile_fastpath`, which #388 and #378 R3 leave to a later C ABI minor, calls `compile_fastpath` with `Facts::Relay` and `FastpathLimits::from_limits()`. It maps the top-level variants of `FastpathCompileError` in one `match` with no wildcard:
  - `Effective`, `CostAboveCap` and `TooLarge` are `GRDR_E_BUNDLE`, and the loaded bundle stays;
  - `Limit` is `GRDR_E_INTERNAL`, a defect in the shipped `limits.toml`, which R3.6's test keeps unreachable.

  A host whose ceiling is below our cap needs a limits input on that function, which the item that adds it decides (section 13).
- R4.6. Design/03 section 10 says "One enum per crate". This RFC settles it as follows, and proposes the wording to design/03 (section 12):
  - In `grdr-fastpath`, `Error` is the floor tables' enum, and it mirrors the statuses of `grdr_fastpath.h`. The fail-safe table and the field scanner get their own enums in their own modules when they arrive, because their failures never cross that header, and putting them in `Error` would force C statuses for errors that never reach C.
  - In `grdr-core`, `FastpathCompileError` sits beside #71's error. `grdr-core`'s modules are its future crates (design/03 section 2), and RFC 0002, in review, gives each port module of `grdr-ports` one enum in the same way.
  - A variant that only wraps another bound error takes that error's code, as `Effective` does, and ARCH-017 recognises it by R4.1's wrapper rule.

### 7. The per-call cap and the other header bounds (R5)
The cap could be a header field written by the compiler from a `limits.toml` row, or a row generated into `grdr-fastpath` as a constant. A constant would put our default inside every partner's library, needing a rebuild to change. A blob from a partner's relay could not state its own cap. A host would have nothing in the blob to compare with its ceiling.

**Decision: the header, as #245 rules** (`tables.md` sections 2, 7, 11 and 13; the chief architect's comment on #405 recording it):
- R5.1. `eval_cap`, `path_max_units`, `expiry_bundle_ns` and `expiry_session_ns` are header fields. The compiler writes them from `fastpath.eval_cap_steps`, `fastpath.path_max_units`, `fastpath.expiry_bundle_ns` and `fastpath.expiry_session_ns` through `FastpathLimits` (R3.6). `grdr-fastpath` holds none of them.
- R5.2. An expiry of all ones means until the scope ends, and TV-8 refuses 0, so 0 only ever means "never reused" (`tables.md` section 6).
- R5.3. Three parties hold the bounds:
  - the compiler refuses a bundle whose worst case exceeds the cap (R3.7);
  - `eval` refuses an input whose cost exceeds it (R2.3);
  - a host refuses a blob whose `eval_cap` or `path_max_units` exceeds its own ceilings, taken from its configuration, so a blob cannot raise the work a host accepts per call.

  A Rust host reads both values from `Tables::header()` after `load` and before it publishes the handle. That copy is what every call reads (R2.8), so the check and the use read one value. A C host reads them from its private copy before `grdr_fp_load` (`tables.md` section 11). Today `tables.md` section 11's cap obligation covers `eval_cap` only. Adding `path_max_units` is a change for #245 (section 12), and the daemon's tests of both are #1769's.

  Our daemon's ceilings are two `limits.toml` rows, `fastpath.host_eval_cap_ceiling_steps` and `fastpath.host_path_max_units_ceiling` (`count` each), read through `grdr-schema`'s generated module, which is constants only and so admitted in a privileged closure. They are bounds, not operator settings, so they are not `grdr.config` keys (`grdr-structure`'s values table); an operator setting would need a stated use first. A test in #1538 holds `fastpath.eval_cap_steps` and `fastpath.path_max_units` at or below them, so our own compiler's blobs always load on our daemon. The rows land with `[retry.fastpath-reload]` (R2.18) through one protected `limits.toml` item, filed on acceptance (section 13).
- R5.4. The argument checks of R2.3 step 2 scan the input path once, linearly in its length, before the cost check. `eval_cap` does not count that scan; `tables.md` section 7's cost model counts steps per row and per entry. So `path_max_units` bounds the scan, and for a blob from elsewhere only the host's ceiling bounds `path_max_units`.
- R5.5. The rows land through #1768, a protected change for lead-agent-kit. How a row writes nanoseconds and "until the scope ends" is open between #1768 and #279's units (Unresolved question 3). Whatever the form, `from_limits` maps it to these values and the library never sees it.

### 8. Stability (R6)
- R6.1. `surfaces.toml` gains a row kind for a public crate: `[[crate]]`, with the keys `name`, `class` and `rfc`. Each value is one double-quoted string on its own `key = "value"` line, the subset #1817's rows use.
  - Three rows, all `experimental`: `grdr-fastpath`, `grdr-fastpath-ffi`, and `grdr-core` unless another accepted RFC has added it.
  - A protected-change item adds the row kind and the rows once this RFC is accepted and #1817 has created the file.
  - ADR-0020's gate reads these rows for `cargo public-api` and `cargo semver-checks`.
- R6.2. A class is per crate. `compile::fastpath` has `grdr-core`'s class, and no row classes a module. A crate's class is at most the class of every crate whose public types its own public API exposes. `grdr-core` exposes `grdr_fastpath::layout::Expiry`, so it cannot move above `grdr-fastpath`. `cargo public-api` lists the exposed types, and the stability gate checks the rule.
- R6.3. The blob format, `table_format` 1, is experimental by `tables.md` section 12, and the C header's class is its `[[c_header]]` row (#1817). This RFC sets neither.
- R6.4. An experimental crate may break, but a break bumps its major, with no overlap (ADR-0020, D-71). Under SemVer 0.y, `cargo semver-checks` treats the next 0.y as that major. A break is an amendment that names this RFC.
- R6.5. Moving any of the three crates to `beta` needs:
  - an RFC that changes its `surfaces.toml` row (design/30 section 3);
  - the external embed pilot of D-60, since `grdr-fastpath` mirrors `table_format` 1 and the C ABI, which stay experimental until it completes;
  - `#[non_exhaustive]` or constructors on `Input` and every `layout` record, so that a field a C ABI minor adds is not a break;
  - a decision on which enums stay exhaustive (`Error` does, for R4.2);
  - `layout` versioned with `table_format`;
  - design/03 F3's freeze, and #1771's header compatibility gate.
- R6.6. Determinism holds within one compiler version, since `compiler_version` changes with each release (R3.10). Golden blob tests compare blobs with the six `compiler_version` bytes masked by one test helper, so a release bump changes no golden vector. A caller-set version was rejected (Alternatives).

### 9. Dependencies (R7)
- R7.1. `grdr-fastpath`: no normal or build dependency (design/26 section 2; #409 AC-5). Its tests may take `proptest` as a dev-dependency once #432 admits it to the workspace. That adds no package to `Cargo.lock` and never enters the normal or build graph.
- R7.2. `grdr-fastpath-ffi`: `grdr-fastpath` only, plus `grdr-cabi-testkit` as a dev-dependency (RFC 0004).
- R7.3. `grdr-core`: `grdr-model` and `grdr-fastpath`, its listed same-layer edges, and `grdr-schema` in layer 0 for codes and limits. `cedar-policy` and `proptest` reach it through #431's ruling and #432's admission. #414 is blocked by #432, and #20 by #21 and #414.
- R7.4. The fuzz target of SD-04 (section 11) uses the libFuzzer harness #415 admits, in the item that builds it. This RFC adds no third-party dependency and no edge. A ruling here would make two RFCs answer for one dependency set.

### 10. Failure modes, data classes and assurance effect
| Failure | Outcome | Visible as |
|---|---|---|
| A TV rule fails at `arena_size` or `load` | `Abi` for TV-3, `Bundle(Rule(n))` otherwise; no handle; the host keeps its previous tables | The returned error; the host reports under its `FASTPATH` code (R4.3) |
| The arena is too short, or its size is above `isize::MAX` | `Arg(Arena)` or `Bundle(TooLarge)`; no handle | As above |
| A C argument or length is invalid; blob and arena overlap; an output meets the blob or arena, or an input lies in the arena | `GRDR_E_ARG`; nothing written | The status; the host applies the class's `on_failure` |
| Label bits from another bundle | `State` on every call until labels and tables agree | The returned error; the host applies `on_failure` and reports |
| An input field out of range | `Arg`, naming the field | As above |
| An input whose cost exceeds `eval_cap` | `Bundle(EvalCap)`, never a verdict | As above |
| A re-check of section 2 fails, in any step, the cost step included | `Changed`, never a verdict and never `EvalCap`; the host stops using the handle at once (R2.16) | The returned error or `GRDR_E_CHANGED`; the host reports a custody fault and is Degraded |
| A run entry in the arena is rewritten, an emptied run included | `Changed` from RC2's boundary rows | As above |
| Between dropping the handle and a successful reload | The floor counts as missing: fail-closed classes deny, the others take `on_failure`; our daemon denies every class (#427 R8); the old interest filters stay (R2.17) | `degraded_reason` `floor-missing`; the device is Degraded |
| A reload fails a TV rule, the ABI or a host check | Floor-missing stays, never the dropped tables; the next attempt follows `[retry.fastpath-reload]` (R2.19) | The daemon's code for the failure |
| `Changed` again on a fresh copy of the same envelope, or the reload policy exhausted | Reloading ends; floor-missing stays until a new bundle activation or a restart (R2.19) | The daemon's code for each case |
| Storage changes in a way no re-check sees: valid blob bytes, or in C the handle | A verdict from the changed bytes (R2.13) | Not visible to the library; custody (R2.14) prevents it |
| A host's ceiling is below the blob's `eval_cap` or `path_max_units` | The host refuses the blob and keeps its previous tables | The host's report (#1769) |
| No floor row objects | `Pass`, which is not `ALLOW` | The verdict; the host goes on to the engine or to `on_failure` |
| A bundle whose worst case exceeds the cap, or a blob too large | `CostAboveCap` or `TooLarge`; no blob | The `COMPILE` code; the caller keeps its last-known-good tables (design/12 section 10) |
| A limit row out of range | `Limit(row)` | The `COMPILE` code, naming the row |
| A fail-closed rule the floor cannot hold | Its `FloorReport` outcome; the rule keeps its class's loss-of-sensor outcome | The floor report, which #71 and #41 read |
| An interest set that selects too little | Not detectable at `load`; held at compile time by R3.9 | `fastpath_compile_interest` fails |
| A volume of unknown case | Its classes fold, which errs toward `deny` | The compiled `path_fold_classes` |

Data classes (P8):
- `action_class`, `principal_kind`, `dest.port`, the verdict, the rule and reason indices, the scope and the expiry are `structural`;
- `Digest` values, `bundle_tag`, and a destination name and address are `identifier`;
- `labels.bits` and `ClassBits` are `derived`;
- the target path is `content` (`content_kind` argument);
- header and records take the classes of `tables.md` section 14, and so does the `Blob`, which is `content` when it holds a resolved template and then never leaves the device;
- a volume mount point is `identifier`;
- errors and the floor report are `structural`.

`grdr-fastpath` logs nothing, and R1.7 keeps content and identifiers out of `Debug`.

Assurance effect (P1): none of its own. The surface carries the floor rows that answer fail-closed classes while the engine is gone (D-15, D-20), and its items' tests are the evidence for `control` of those classes.

### 11. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| No raw pointer, `unsafe`, `alloc` or dependency in `grdr-fastpath` | `#![forbid(unsafe_code)]`, `#![no_std]`; `cargo tree -e normal,build` shows the crate alone; ARCH-001 | #409 (AC-5); #1580 |
| No truncating cast in either crate | `#![deny(clippy::as_conversions)]` at both crate roots, beside `arithmetic_side_effects` | #409; #418 |
| Builds for `wasm32-unknown-unknown` | `cargo build --target wasm32-unknown-unknown -p grdr-fastpath` | #409 (AC-6) |
| 32-bit arithmetic is executed, not only compiled; the FFI's `unsafe` runs under Miri (SD-01) | The nightly Miri job runs `grdr-fastpath`'s tests for `i686-unknown-linux-gnu`, which Miri interprets without a 32-bit libc, and `grdr-fastpath-ffi`'s tests on the host target | #1475 |
| `load`, the path decoder and the name check are fuzzed (SD-04) | A fuzz target over `load`, `eval` and `classify`, differential against #409's reference validator and #412's unindexed evaluator | The fuzz item filed on acceptance, blocked by #415 and #409 |
| Of `grdr-core`, only `compile::fastpath` imports `grdr-fastpath`, and only `layout` | ARCH-013's import table reads the edge's `importers` and `paths` in `architecture.toml` (section 12). Until #1582 lands, `eval-architecture` checks every change to `crates/grdr-core/src/**` | #1582; the `architecture.toml` item filed on acceptance |
| One layout definition, independent oracles | `layout` shared; #409's reference validator; #412's fixtures; #414's golden rows; #20's differential; the comparison-count vectors | #409, #412, #414, #20 |
| Rust and C give the same answers | #418's behaviour: on any blob, `grdr_fp_load` then `grdr_fp_eval` equal `load` then `eval` | #418 |
| The FFI's argument, length, overlap and range rules, in R1.11's order | One seeded test per R1.11 rule, each expecting `GRDR_E_ARG` with nothing written; one with a mismatched label tag and an over-long path, expecting `GRDR_E_STATE` from C as `State` from Rust | #418 |
| Each re-check gives `Changed` at its first read, and an undetected change is recorded | The tests of R2.15, `fastpath_changed_rc2_cost`, `fastpath_changed_rc2_empty` and `fastpath_one_view` among them | #412, with #410 for RC2 and RC4 to RC6 in `classify` |
| `reload-required` is a state with bounded exits | `fastpath_reload` (R2.20) | #427 |
| The host keeps blob and arena in custody | The contract text of section 12; for our daemon, #1769's custody race test extended to the arena, where a write to the arena after `load` must give `Changed` through RC2 | #246; #245; #1769 |
| Every leaf variant maps to its status, and every fast-path status is produced | The nested no-wildcard mapping (R1.14), checked against the entries' `status` by `status_per_variant` (R4.2); `HDR-4` against `status-codes.toml` | #418; #1778 |
| The ARCH-017 exemption is per variant, typed, and the one copy of both mappings | The entries of R4.1, whose `status`, `code`, `bound_in` and `coded_by` ARCH-017 checks; the wrapper rule | The `architecture.toml` item; #1582 |
| Every leaf variant has a registered code where the errors are met | The daemon's nested no-wildcard mapping, checked against the entries' `code` by `code_per_variant`; ARCH-017 on the daemon's enum; area `FASTPATH` | #427; #278 |
| Our daemon's ceilings and reload policy are data | The `limits.toml` rows of R5.3 and R2.18; a test that the compiler's defaults sit at or below the ceilings | The `limits.toml` item filed on acceptance; #1538 |
| `FastpathCompileError` codes and C statuses | Area `COMPILE`; ARCH-017; #278's drift test; the no-wildcard status match of R4.5 | #414; #71; #278; #1582; the `grdr_engine_compile_fastpath` item |
| No bound in `grdr-fastpath` | The four header fields; TV-8; `FastpathLimits` from the generated module; ARCH-019 | #1768; #414; #409; #1582 |
| A blob from our compiler never reaches the cap, and the built-in limits are valid | `CostAboveCap` with a seeded bundle above a small cap through `FastpathLimits::new`; `from_limits` is `Ok` on the committed file | #414 |
| A host's ceilings bound `eval_cap` and `path_max_units` | The host obligation of `tables.md` section 11, widened to `path_max_units`; the daemon's negative tests | #245; #1769 |
| The interest set covers every floor row | `fastpath_compile_interest` (R3.9) | #414 |
| Unknown or missing volume facts fold | A test with `CaseRule::Unknown`, an empty `volumes` and a partial one, each expecting the class's fold bit set | #414 |
| Concurrent evaluation is safe | A type-level test that `Tables`, `Interest` and `Records` are `Send + Sync`, for borrowed and boxed storage; #412's determinism property | #412 |
| No content or identifier in `Debug` | A test per R1.7 type that its `Debug` output holds no byte of the value it was built from | #409, #410, #412, #414 for their types |
| The ABI's highest action class equals the spine's | A test in `grdr-core` that `layout`'s ceiling equals the highest `grdr.common.v1alpha1.ActionClass` number, so a new class fails until a new minor raises it | #414 |
| The fast path is a deliberate second implementation (P17) | An `architecture.toml` record of the pair `grdr-fastpath` and `grdr-core`, held equal by the B2 differential | The `architecture.toml` item; #20 |
| Each crate has a class, and no crate outranks what it exposes | `[[crate]]` rows; `cargo public-api` and `cargo semver-checks` | The `surfaces.toml` item filed on acceptance; ADR-0020's gate item |
| Golden blobs survive a release | The masking helper of R6.6 | #414 |

### 12. Proposed changes to contracts, design documents and gate files
Each lands through the item named, or an issue whose write set names its file, after acceptance.

**`c-abi.md` and `status-codes.toml`** (#246, while it is open; otherwise a protected-change item):
1. A new status, `GRDR_E_CHANGED`, value 11, the next free one. Its `meaning` is "Fast path only: the tables' blob or arena no longer reads as `grdr_fp_load` validated it." Its `handle_after` is `reload-required`, a new value whose text, in the registry's header comment and in `c-abi.md` section 7, is section 2a's state:
   - stop using the handle at once;
   - until a load from a freshly verified copy succeeds, count the floor as missing, so fail-closed classes deny and the others take `on_failure`, keep the interest filters, and report Degraded;
   - free the old blob and arena only after the quiescence point;
   - never return to the old handle;
   - bound the reloads, and stop when a fresh copy of the same envelope gives `GRDR_E_CHANGED` again.

   Section 6 says the fast path uses five statuses, not four.
2. The `grdr_fp_eval` and `grdr_fp_interest` rows list `GRDR_E_CHANGED`.
3. The `grdr_fp_eval` check order of R1.11 and R2.3:
   1. the address checks and `struct_size`, `GRDR_E_ARG`;
   2. a failed RC1, `GRDR_E_CHANGED`; then a label mismatch, `GRDR_E_STATE`;
   3. the remaining argument and length checks, `GRDR_E_ARG`;
   4. the class above `action_class_count`, which gives `pass` with scope `none`;
   5. the cost, where a failed re-check of what the cost reads is `GRDR_E_CHANGED` and a cost that exceeds `eval_cap` is `GRDR_E_BUNDLE`;
   6. evaluation, where a failed re-check is `GRDR_E_CHANGED`.

   So `GRDR_E_CHANGED` can come before the cost result.
4. The argument rules of R1.11 in the rows of all four fast-path functions: address checks before any read, lengths checked before any slice, `PTRDIFF_MAX` as the largest byte length, the name maximum, blob and arena overlap, outputs that meet the blob or arena, and inputs inside the arena.
5. The `grdr_fp_arena_size` row: `GRDR_E_BUNDLE` also when the arena size exceeds `PTRDIFF_MAX`.
6. The `grdr_fp_verdict` text: a `step_up` verdict always has `cache_scope` `NONE`.
7. The `grdr_engine_compile_fastpath` row: `GRDR_E_BUNDLE` also when the worst-case cost exceeds the cap, and `GRDR_E_INTERNAL` for invalid built-in limits (R4.5).
8. Arena custody, in section 2 and the `grdr_fp_load` row, replacing "The blob and arena must outlive the tables": "The host keeps the blob and the whole arena, the tables handle included, in memory no less privileged process can write, unchanged from `grdr_fp_load` until its quiescence point after it retires the tables" (R2.14).
9. The alignments of Unresolved question 2.

**`tables.md`** (#245):
1. Section 11, Cap: the host's ceiling also bounds `path_max_units` (R5.3).
2. Section 13: a class folds when a volume it can reach has an unknown case or is missing from the facts, and a change of the device's volumes is a recompile (R3.5).
3. Section 13: the compiler test that proves interest coverage is #414's `fastpath_compile_interest`.
4. Section 6: the order of the vocabulary case against the argument checks and the cost (R2.3).
5. Section 11, Custody: the arena joins the blob, with the text of item 8 above (R2.14).
6. Sections 10 and 11: the host's state after `GRDR_E_CHANGED`, as section 2a states it.

**Design documents** (the chief architect, through one issue):
- **design/26 section 2.** The sentence that fast-path functions return `GRDR_E_ARG`, `GRDR_E_ABI`, `GRDR_E_BUNDLE` and `GRDR_E_STATE` gains `GRDR_E_CHANGED` for a blob or arena that no longer reads as loaded.
- **design/26 section 3, error model.** The status table gains the row `GRDR_E_CHANGED` (11), "Reload from a freshly verified copy; until then the floor counts as missing".
- **design/03 section 2, crate table.** `grdr-fastpath`: "`no_std` table evaluator over fixed-layout inputs, the table layout `grdr-core` writes through, and the bounded field scanner; no dependencies". `grdr-fastpath-ffi`: "`extern "C"` entry points and the `#[repr(C)]` structs of `grdr_fastpath.h`, so `libgrdr_fastpath` carries no engine code (26); core squad".
- **design/03 section 2, same-layer edges.** "`grdr-core` to `grdr-fastpath` (table layout only: module `compile::fastpath` imports `grdr_fastpath::layout`, its types, constants, codecs and the cost function of the table format)".
- **design/03 section 10, Errors.** "One error enum per crate, or per module where the module is a future crate or serves its own interface. A variant that only wraps another bound error takes that error's code" (R4.6).
- **design/12 section 16.** A property row: "Interest set covers the floor rows | the compiled interest set | exhaustive up to 20 class bits, random above" (R3.9).

**Gate and registry files** (protected changes):
- **`architecture.toml`.** On the `grdr-core` to `grdr-fastpath` edge, `importers = ["compile::fastpath"]` and `paths = ["grdr_fastpath::layout"]` beside the existing `scope`, whose text gains "and the cost function". The twelve per-variant ARCH-017 entries of R4.1. One record of the independent pair `grdr-fastpath` and `grdr-core`, whose reason names the no_std fast path of P17 and the B2 differential (#20) that holds them equal.
- **`surfaces.toml`.** The `[[crate]]` row kind and its three rows (R6.1).
- **`schema/codes/`.** Area `COMPILE` and its three entries (R4.4); area `FASTPATH` with one entry per leaf variant and the three state codes (R4.3).
- **`security/requirements.yaml`.** The requirements eval-security's threat-model deltas propose, filed for the security squad:
  - from round 1, SR-new-A to SR-new-E: re-checked storage with a distinct status, the FFI's length and overlap rules, unknown case folds, interest coverage, and host ceilings;
  - from round 2, SR-new-F and SR-new-G: blob and whole arena in custody until quiescence, and `reload-required` as a floor-missing state with a bounded reload. SR-new-A gains "a re-check applies at first read, over one view per call".
- **`limits.toml`.** The four rows of #1768, unchanged by this RFC. A new protected item adds `fastpath.host_eval_cap_ceiling_steps`, `fastpath.host_path_max_units_ceiling` and `[retry.fastpath-reload]` (R5.3, R2.18).

### 13. What each item changes
This RFC is normative. Each lead writes these changes back into its item before readying it.
- **#409.**
  - R2's layout types are `grdr_fastpath::layout` (section 3), with `Record` sealed.
  - R3 and R4 are `arena_size` and `load` as R2.1 and R2.2 state, over `Tables<B, A>`, keeping the storage lengths and the header copy.
  - R5's errors are `Abi`, `Bundle(Rule(n))`, `Bundle(TooLarge)` and `Arg(Arena)`, with the rule number from `Error::rule`.
  - It adds `clippy::as_conversions` to the crate root, and the redacting `Debug` of its types.
  - Its write set gains `crates/grdr-fastpath/src/layout.rs`, `crates/grdr-fastpath/src/layout/**` and `crates/grdr-fastpath/AGENTS.md`, whose purpose line no longer says the inputs are `#[repr(C)]`.
  - `proptest` may be its dev-dependency (R7.1).
- **#410.** `classify` is public and returns `Option<ClassBits>` as R2.4 states. It fails with `Bundle(EvalCap)` or `Changed`, never partial bits. It makes RC2 in its cost step and RC4 to RC6, `prefix_len` included, at the first read of what each guards, and adds their tests. The cost is the shared function of `layout`.
- **#412.**
  - `eval` returns `Verdict` with the scopes of R1.3 and R1.4, in the order of R2.3.
  - R2's vocabulary case follows `tables.md` section 6: a class within the ABI but above `action_class_count` is `Pass { scope: None }`, not `Arg`.
  - It makes RC1 to RC3, RC5 and RC6 at the first read of what each guards, the cost step included, over one view of each storage per call (R2.10). RC2 checks the boundary rows. It adds the tests of R2.15 and the type-level test of R2.6.
  - `check_pairing` is public (R2.3), and `reason` returns `Result` (R2.7). R7's `interest` is R2.5's.
  - Its arena holds the run index and nothing else (R2.11).
- **#414.**
  - R1 is `compile_fastpath` as section 4 states, with `Facts`, `CaseRule::Unknown` and `FastpathLimits`. R6's report gains the outcomes of `tables.md` section 13.
  - R8 reads its bounds through `FastpathLimits`. R9 binds to area `COMPILE` (R4.4), which it creates if #71 has not.
  - It adds `fastpath_compile_interest` with its process-scope inputs, catalogue fixture and one witness per row (R3.9), the fold test, the cost-refusal, `from_limits` and action-class-ceiling tests, and the masking helper (R6.6).
  - Its `grdr-core` types follow R1.7's `Debug` rule.
- **#418.**
  - It defines the C structs (R1.10), and converts and checks in R1.11's order, calling `check_pairing` before its own field and length checks, with one test per rule. It lays out its arena as R1.12 says, with the custody text in its `SAFETY` comment.
  - It maps verdicts and errors as R1.13 and R1.14 say, adds `status_per_variant` reading the `architecture.toml` entries (R4.2), and adds `clippy::as_conversions` to its root.
- **#388.** `grdr.h` takes the shared status block, so `grdr-ffi` defines `GRDR_E_CHANGED` with `c_status!` to pass `HDR-4`, though no engine function returns it. Its `grdr_status_str` returns the new row's name, and its handle-state tests list the `reload-required` value.
- **#1778.** `content::grdr_status` renders row 11 in both C ABI headers. Its row reader also reads the ARCH-017 entries of `architecture.toml`, which use the same one-string-per-line subset, for `status_per_variant` and `code_per_variant`.
- **#20.** No change beyond the names: R2 calls `compile_fastpath`, `load` and `eval`, and R5 calls `classify`, whose `None` case it skips.
- **#71.** Its step 8 writes the fast-path blob by calling `compile_fastpath` (R3.3), and its `compile` takes `DeviceFacts` (R3.5). Its error is the one `Effective` wraps, and it may create area `COMPILE` for it (R4.4).
- **#427.**
  - Its floor module maps every `grdr_fastpath` leaf variant to its own coded error, registers area `FASTPATH` with the three state codes, and adds `code_per_variant` (R4.3).
  - Its floor state is an explicit type with section 2a's states and exits: serving, and floor-missing with its reload pending or ended. `fastpath_reload` tests them (R2.20).
  - On `Changed` it answers as R8's floor-missing until a reload succeeds.
- **#1538.**
  - Its `Refused { code }` uses the load-side `FASTPATH` codes.
  - After `load` and before it adopts the handle, it checks `Tables::header()` against the ceiling rows of R5.3, and tests that the compiler's defaults sit at or below them.
  - It recompiles when the device's volumes change (R3.5), and its fresh compile instance is the reload source of R2.18.
- **#1769.** It gains the daemon's negative tests for both ceilings (R5.3), and its custody race test covers the arena (R2.14).
- **#1768.** Its rows are what `FastpathLimits::from_limits` reads, and it settles their units with #279 (Unresolved question 3).
- **#1582.** ARCH-013 reads the edge's `importers` and `paths`. ARCH-017 reads the per-variant entries, checks their `status`, `code`, `bound_in` and `coded_by`, applies the wrapper rule, and fails a variant without an entry (R4.1).
- **#1475.** Its Miri job covers the two fast-path crates as section 11 states.
- **#246 and #245.** The deltas of section 12, and the alignments of Unresolved question 2.

Filed on acceptance, each linked as it blocks:
- the `architecture.toml` change of section 12, a protected change for lead-agent-kit, blocking #414, #418 and #427;
- the `surfaces.toml` row kind and rows of R6.1, a protected trust-core change, blocked by #1817;
- the design/03, design/12 and design/26 amendments of section 12, for the chief architect;
- the `limits.toml` item for the two ceiling rows and `[retry.fastpath-reload]` (R5.3, R2.18), a protected change for lead-agent-kit, blocking #1538 and #427;
- the `grdr-ffi` item that adds `grdr_engine_compile_fastpath` in a later C ABI minor (R4.5), which decides whether it takes a limits input;
- the fuzz item of section 11, blocked by #415 and #409;
- the `security/requirements.yaml` item of section 12, for the security squad.

## Surfaces changed
- `grdr-fastpath` (public crate, layer 1, `experimental`): its first surface, the items of section 1 and the module `layout` of section 3.
- `grdr-fastpath-ffi` (public crate, layer 1, `experimental`): the `#[repr(C)]` structs of section 5 beside the `extern "C"` items of `c-abi.md`.
- `grdr-core` (public crate, layer 1, `experimental`): module `compile::fastpath`, with the items of section 4.
- The host contract, as changes for #246 and #245: a new status `GRDR_E_CHANGED` and its `handle_after` value with the host state it names, new statuses on two fast-path rows, the `grdr_fp_eval` order, the argument, length and range rules, arena custody, and the `tables.md` obligations of section 12.
- As proposals: the `[[crate]]` row kind and three rows of `surfaces.toml`; the `architecture.toml` edge keys, per-variant ARCH-017 entries and independent-pair record; the design/03, design/12 and design/26 text of section 12; areas `COMPILE` and `FASTPATH` in `schema/codes/`; two ceiling rows and a retry policy in `limits.toml`.
- No change to a protobuf package, the Cedar schema, a same-layer edge, the spine or the licence policy.

## Alternatives
- **The `#[repr(C)]` input and verdict in `grdr-fastpath`, re-exported by the FFI crate** (#405 R1 as written; RFC 0004 D10). The Rust API would carry raw pointers and `struct_size` that safe Rust cannot read, a second input type beside the safe one, and the C ABI's minor rule inside the crate's SemVer line. Rejected for R1.8.
- **A borrowed handle only, `Tables<'a>`.** It matches C, but the daemon owns its buffers, and safe Rust cannot store a handle beside the buffers it borrows. The daemon would need `unsafe`, a leaked buffer per swap, or a self-referential dependency. Rejected for R1.9.
- **A sealed storage trait.** Not viable, for the reasons of section 2. Rejected.
- **Re-running every TV rule on each call.** Each rule is linear in the blob, against a per-call bound of rows touched. Rejected for the closed re-check list.
- **Re-checks after the cost step** (revision 2). The cost reads the run index and the pattern lengths, so a changed index came back as `EvalCap`, whose `handle_after` keeps the tables. Rejected for re-checks at first read (R2.12).
- **RC2 as a bounds check alone** (revision 2). An emptied run passes it, and the call returns a cacheable `Pass`. Rejected for the boundary rows, which TV-27's order makes exact.
- **Keeping the dropped tables until a reload succeeds.** Every answer in between would come from bytes known not to be the ones validated. Rejected for floor-missing (R2.17).
- **Unbounded reloading.** A defect in `load` gives `Changed` on every fresh copy, so the host would loop. Rejected for the retry policy and the same-envelope stop (R2.18, R2.19).
- **Host ceilings as `grdr.config` keys.** They are bounds with no stated operator use, so they are `limits.toml` rows (R5.3). An operator setting can be added when a use is stated.
- **The leaf-to-status mapping in the test as well as the entries and the FFI** (revision 2). Three copies, two of them unchecked against each other. Rejected for entries as the one copy, with both `match` expressions checked against them (R4.1, R4.2).
- **The handle inside the arena in Rust too.** Writing a typed value into caller bytes needs `unsafe`. Rejected; the FFI crate does it (R1.12).
- **`Changed` as `GRDR_E_BUNDLE` with a wider meaning** (revision 1). Its `handle_after`, `last-known-good`, tells the host to keep the tables it has, which are the altered ones. Rejected for `GRDR_E_CHANGED`.
- **`Changed` as `GRDR_E_INTERNAL`.** Its meaning is a bug in the library and its `handle_after` is `poisoned`, which the library, holding no state, cannot enforce. A custody fault is not a library bug. Rejected.
- **`#[non_exhaustive]` error enums.** The FFI match would need a wildcard, and a new variant would map silently. Rejected for R1.6.
- **An ARCH-017 exemption by type** (revision 1). A variant added later would be exempt with no decision, and a match on `Arg(_)` would let a new `ArgFault` inherit a status. Rejected for R4.1 and R4.2.
- **Codes bound in `grdr-core`, or through a test-only `grdr-schema` dev-dependency** (options (a) and (c)). Rejected for section 6.
- **One error variant per TV rule.** It is 33 variants that #245 can still renumber. `TvRule` carries the number. Rejected.
- **The cap as a generated constant in `grdr-fastpath`.** Rejected for section 7.
- **Host ceilings as parameters of the Rust `load`.** The Rust and C entry points would differ, and `Tables::header()` already gives the host the one copy every call reads. Rejected for R5.3.
- **`compile_fastpath(bundle) -> Blob`** (#405 R3 as written). It drops the floor report #414 and #71 read, and the device facts and limits `tables.md` sections 2 and 13 need. Rejected.
- **`compile_fastpath` over an effective bundle.** That type does not exist yet (#71), and the verified bundle is the only input a host can vouch for (design/03 section 3). Rejected for now. When #71 lands, both call one emitter (R3.3).
- **A caller-set `compiler_version`.** It would let a caller write a false version into the field that says which compiler wrote the blob. Rejected for the masking helper of R6.6.
- **A load-time TV rule for interest coverage.** Rows naming `Session` are covered through catalogue data the blob does not hold, and an inclusion check over sorted sections is not linear in the blob. Rejected for the compiler test of R3.9; a new rule would be #245's.
- **A per-module class in `surfaces.toml`.** `cargo public-api` and `cargo semver-checks` work per crate. Rejected for R6.2.
- **A separate layout crate.** It adds a crate and two edges, and gives `grdr-fastpath` a dependency against design/26 section 2. Rejected.
- **The layout defined in `grdr-core` and read again by `grdr-fastpath`.** Two definitions of one format (P17), and the edge runs from `grdr-core` to `grdr-fastpath`, not back. Rejected.
- **`classify` behind a `test-util` feature.** ARCH-008 allows the feature, but a build-dependent public surface is harder to reason about than a small public function. Rejected.
- **No `Display` on `Error`** (revision 1). The daemon could not use `?` into a boxed error. A `Display` that writes identifiers is not person-facing text. Rejected.

## Drawbacks
- Two input types, `Input` and `grdr_fp_input`, with a conversion that #418's differential has to hold.
- Every function carries the storage parameters `B` and `A`.
- The re-checks detect only changes that break one of six invariants. An in-place change to valid blob bytes, or in C to the handle, is answered, and only custody prevents it (R2.13).
- RC2's boundary rows add up to four row reads to every call.
- Every host carries a floor-missing state with a bounded reload and its exits (section 2a), and our daemon carries three more codes for it.
- A new status, `GRDR_E_CHANGED`, and a new `handle_after` value for every C host to handle.
- Twelve exemption entries in `architecture.toml`, one per leaf, and a daemon wrapper that repeats the leaves to bind their codes.
- Exhaustive enums make every new variant a breaking change, which `experimental` allows and a later class will price.
- The FFI crate needs one more `unsafe` block, to place the handle in the arena.
- Golden blob tests need a masking helper for `compiler_version`.

## Unresolved questions
1. **#245 is not merged, and round 3 failed on the commit this RFC reads.** At `115ec8b`, eval-security failed round 3 on the section 8 heading, on the library's own path and destination input checks, which became undefined when canonicalisation moved to the host, and on host obligations no item carried (#1769) or could meet (#1770). The orchestrating session allowed a round 4. If #245 lands with different text, this RFC needs an amendment when any of these change:
   - an error class, a status, or which rule gives `GRDR_E_ABI`;
   - the numbering or grouping of the TV rules, which R1.5, R2.1 and R2.2 bind (TV-3, TV-1 to TV-14, TV-15 to TV-33) and section 2 cites (TV-16, TV-19, TV-24, TV-26, TV-28 to TV-30);
   - an input field, such as `grant_digest` if #1770 changes how grants reach the host;
   - the section list or a record's fields, which `layout` mirrors;
   - a function, or a header field the compiler writes from `limits.toml`;
   - which argument checks belong to the library, which R2.3 step 2 defers to `tables.md` section 6.

   A change to a rule's content inside one of these, or to the cost model, changes no item here. Accepting this RFC does not wait on #245, and #409, #410, #412 and #414 each already require it.
2. **`c-abi.md` at `ca039ed` differs from `tables.md` at `115ec8b`.** This RFC follows `tables.md`, #246 aligns these with `tables.md` as merged, and #418 is blocked by #246. The differences:
   - the `grdr_fp_load` row applies "TV-15 to TV-31", where `tables.md` has 33 rules;
   - `grdr_fp_eval` check 3 makes an action class above `action_class_count` an argument error, where `tables.md` section 6 gives `pass` with scope `none` within the ABI;
   - the `grdr_fp_eval` row, check 4 and the `GRDR_E_BUNDLE` meaning in `status-codes.toml` say an evaluation "reaches" `eval_cap`, where `tables.md` section 7 says a cost that "exceeds" it, so a cost equal to the cap gets a verdict from one and an error from the other;
   - the `expiry_ns` comment says "0: no bound beyond the scope", where `tables.md` section 6 makes 0 "never reused" and all ones "until the scope ends";
   - check 3 points the name form at TV-20, the path grammar, rather than section 3.3 and TV-21, and the path form at #221 R4 rather than `tables.md` sections 6 and 11;
   - the `grdr_fp_eval` row and the `grdr_fp_verdict` text cite `tables.md` section 5 for evaluation, scope and expiry, which are section 6, and section 5 cites `tables.md` section 9 for the arena rule, which is section 10;
   - the `grdr_fp_verdict` text has a host clear its cache on a swap, where `tables.md` section 10 keys entries by a generation and needs no clearing.
3. **The units of #1768's rows.** #279 R1 gives a bound one of `bytes`, `count`, `ms` or `permille`, while #1768 asks for nanoseconds with all ones meaning until the scope ends. #1768's lead settles the form with #279: a nanosecond unit, or a millisecond row the compiler converts with checked arithmetic, plus a way to write "until the scope ends". Either way R5.5 holds.
4. **The ARCH-017 exemption list.** RFC 0002 (#1688, in review) proposes its form. If neither RFC is accepted with it, the `architecture.toml` item of section 12 creates the list with the typed fields of R4.1.
5. **Types other items define.** `PathContext` (#221), `Ineligible` (#216), `EffectiveCompileError` (#71) and `RuleId` (the policy module, #212) are named here and defined by their items. If one of them lands with another name, the item that lands it renames the use here, which changes no rule of this RFC.

## Review
Review happens on #405. The review calls for:
- the nine persona council seats;
- `eval-architecture`, the `[kinds] rfc` row of `.claude/risk-tiers.toml` on `main` at `4e46c2c`;
- `eval-security` and `eval-adversarial`, the row #1821 makes data, and `eval-api`, the `public_api_change` trigger's row. This RFC states the public API of two trust-core paths (`crates/grdr-fastpath/**` and `crates/grdr-core/src/compile/fastpath*`), and #405 is high tier with `public_api_change`.

At least one evaluator runs on the other model from the one in the metadata block (owner instruction 7).

Every seat comment and every evaluator verdict on this RFC names the blobs it read, as full 40-character ids, on fixed lines (RFC 0001, "Review binds the decision"; #1798):
- **RFC file:** `git rev-parse <commit>:rfcs/0005-fastpath-rust-surface.md`, with the commit it read.
- **Proposed text:** none. This RFC decides no pinned path of `rfcs/pins.toml`, so it adds no decision line and commits no evidence.
- **Base:** the spine pin in force, `a80859235e7a2a4444648d6fa8d389d78dde6be9`.
- **Contracts read:** the three contract blobs of section 0. A verdict that read other contract blobs names them, and the decision then waits for a revision that names the blobs it rests on.

A comment that cannot compute an id says so on that line and is not a pass. The decision rests on an `eval-architecture` pass that names the RFC file blob it decides. No verdict by an evaluator of this review may fail that blob. The file the decision commits may differ from that blob only in `State:`, `Decision record:`, link lines under this section and the `Decision` section, as RFC 0001 allows.

Round 1, on RFC file blob `f751240ac8974ef53f0f1769fdb5ac1676a241f9`:
- `eval-api`, fail: https://github.com/416rehman/Guardrails/issues/405#issuecomment-7072105713
- `eval-architecture`, fail: https://github.com/416rehman/Guardrails/issues/405#issuecomment-7072152013
- `eval-security`, fail: https://github.com/416rehman/Guardrails/issues/405#issuecomment-7072328947

Round 2, on RFC file blob `c90f24fe5cf9d87dab1934bcf928d965762bf9ba`:
- `eval-architecture`, pass with seven minors: https://github.com/416rehman/Guardrails/issues/405#issuecomment-7072611466
- `eval-security`, fail: https://github.com/416rehman/Guardrails/issues/405#issuecomment-7072851867

The round 2 pass names blob `c90f24f`, not this revision, so the decision needs a pass on this revision's blob.

Round 3, on this revision: `eval-architecture` (a delta review), `eval-security`, `eval-api` and `eval-adversarial`, then the nine seats, all on the same blob.

## Decision
None yet.
