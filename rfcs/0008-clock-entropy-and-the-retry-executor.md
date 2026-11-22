RFC: 0008
Title: Clock, Entropy, Monotonic and the retry executor: the first surface of grdr-ports and grdr-ports-testkit
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #1924
Spine: D-05, D-15, D-60, D-61, P1, P5, P6, P8, P9, P14, P15, P17 (no spine text changes)
Surfaces: the public crates `grdr-ports` (modules `clock`, `entropy` and `retry`) and `grdr-ports-testkit` (`ManualClock`, `ClockError`, `SeededEntropy`, `block_on`, `Stalled`, the conformance runner and the Clock suite), and the `grdr-model` type `Monotonic`. As proposals: two rows of `surfaces.toml`, and two third-party allow-lists and three ARCH-017 exemption entries in `architecture.toml`. No third-party dependency, same-layer edge, wire format or Cedar schema changes
Decision record: none yet

To comment, write on issue #1924 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This RFC takes sections 3 and 4 of RFC 0002 (#1688) at blob `5227384311da574174149f1a23958502ff213877`, with the parts of that RFC they rest on. Section 1 lists where it decides otherwise than that text.

## Summary
Slice 0 adds the first public items to `grdr-ports` and `grdr-ports-testkit`: the `Clock` and `Entropy` ports, the `grdr-model` instant type `Monotonic`, the one retry executor `grdr_ports::retry::run`, their deterministic reference adapters (`ManualClock`, `SeededEntropy` and `block_on`), and the conformance runner that every later port suite extends. Layers 0 and 1 take `now` and `entropy` as arguments and do no I/O, and only the programs implement `Clock` and `Entropy` over the operating system. `run` reads every bound from a `limits.toml` retry table through RFC 0007's `RetryLimits`. Nothing here names a tenant context, a tenant witness, the seal, the mint authority, a fence or a storage port; those stay in RFC 0002. Both crates enter `surfaces.toml` as `experimental`.

## Motivation
#281 (Clock, Entropy, the reference adapters and the runner) and #283 (`retry::run`) are the first code in both crates, and the first runnable path needs them (#645, comment 7074036495): the daemon links `grdr-ports` for `Clock`, `Entropy` and `retry::run`. RFC 0002 sections 3 and 4 stated this surface. They share no mechanism with that RFC's tenant contexts, seal, mint authority or fences, which are what RFC 0002's review is about. A public crate changes only by RFC (D-61; design/30 section 3), and `experimental` sets the break rules, not the route (the ruling on #1535). If nothing changes, #281 and #283 wait on a tenant boundary they do not use.

## Design

### 1. Scope and the split from RFC 0002
This RFC states RFC 0002 sections 3 and 4, and the parts of RFC 0002's Rules 1, 2, 7, 8 and 12 and sections 5, 12 and 14 that bear on them. RFC 0002 keeps everything else. Its next revision removes sections 3 and 4 and points here (section 8).

The rules of section 2 and the failure modes of section 6 gather what RFC 0002, #281 and #283 already say. Otherwise the text follows the source, except in four places:
1. The runner (section 5) is generic over its subject. The source bound it to a storage `Fixture`, so the Clock suite, which is generic over `A: Clock`, could not run on it. Case kinds, fixtures, stop points, induced faults and the `NotApplicable` outcome need storage types, so they enter with the storage suites.
2. "The RFC of #1710" becomes #1850 for the `grdr-model` retry types and RFC 0007 for `RetryLimits`, as RFC 0007 section 7 asks.
3. `Monotonic` gains `from_nanos` and its derives. Without a constructor, neither an OS clock nor a test can make the instant `ManualClock::new` takes, and `monotonic() >= d` needs the order.
4. Before each later call, `run` spends from the budget before it asks the breaker, so every permit, a probe included, is followed by a call. In the source order a probe that the budget then refused was never made, and the breaker stayed half-open with every later permit refused (#282 R9).

The split needs items 1 and 2. Items 3 and 4 each fix a defect of the source that would stop #281 or #283. Four statements fill places where the source is silent: `start` is the call's own start, a deadline past the maximum instant is the maximum instant (as #282 has it for the breaker), the runner passes one seeded entropy to its cases in turn, and `RetryError` is exhaustive.

### 2. Rules
- R1. **Dependencies.** `grdr-ports` depends on `grdr-model` and `grdr-schema` and on no other crate, third-party crates included. The privileged daemon links it, so whatever it links is in the daemon's closure. `grdr-ports-testkit` depends on `grdr-ports`, through the listed same-layer edge, on layer 0 and 1 crates of the workspace, and on no third-party crate; RFC 0002 adds the Arrow crates for its Events reference adapter. It is never in the normal-dependency closure of a layer 4 program.
- R2. **Async shape.** `Clock` has `Send + Sync` as supertraits. `sleep_until` is declared as returning `impl Future<Output = ()> + Send`, which an implementation may write as an `async fn`. There is no `async-trait`, no boxed future and no `futures` crate, so `Clock` is not dyn-compatible and a caller is generic over `C: Clock`. `Entropy` is synchronous and stays dyn-compatible, because `Engine::step` takes `&mut dyn Entropy` (design/03 section 3). A WebAssembly host passes `now` and an `Entropy` to the engine as values and implements no `Clock`.
- R3. **Open traits.** `Clock` and `Entropy` are not sealed. The programs implement them over the operating system (#1927), and the kit implements them for tests. RFC 0002's seal covers its storage ports only.
- R4. **Layers 0 and 1.** Layers 0 and 1 hold no `Clock`, read no clock or randomness source and do no I/O (spine section 5; D-05). A layer 1 function that needs time takes `now: Timestamp` or a `Monotonic` as an argument, and one that needs randomness takes an `Entropy`, as `Engine::step` does. `Monotonic` and `Entropy` live in `grdr-model`, and `Monotonic` is a value that reads no clock. `Clock` lives in layer 2, so no layer 0 or 1 crate can name it (ARCH-001). Nothing in `grdr-ports` or `grdr-ports-testkit` reads a system clock or the operating system's randomness either: the programs' OS adapters are the only readers (design/03 section 10, Time and Randomness).
- R5. **Bounds are parameters.** Every bound `run` applies (attempts, elapsed time, delays, call timeout, budget and breaker) comes from the `RetryPolicy` it is given. Product code builds a policy only with `RetryPolicy::from_limits`, from a `[retry.<name>]` table of `limits.toml` or a narrowing of one (RFC 0007 sections 5 and 6; #1850). `block_on`'s poll bound is an argument. No type here holds a tunable bound (ARCH-019).
- R6. **Errors.** `RetryError<E>` has no code. Its caller maps every variant to a code of the subsystem that failed, and the caller's rule class decides what the failure means (D-15). It is exhaustive, so a variant added by amendment fails every caller's build until the caller maps it. The kit's errors, `ClockError` and `Stalled`, have no code and hold no free text. All three are entries of the ARCH-017 exemption list in `architecture.toml`, each with its reason, so the lint reads data and special-cases no name (section 8). Each implements `LogSafe` (#1850), `RetryError<E>` where `E` does, and so does the `Monotonic` it carries. No type here holds a person-facing string.
- R7. **Data classes and assurance.** `Monotonic`, `Timestamp`, attempt counts, delays, deadlines, seeds, reports and the kit's errors are `structural` (P8). Entropy output is never logged or stored. `run` never logs `E`, which keeps the class its own type declares. Assurance effect: none; no action class changes `visibility`, `control`, `on_failure` or `tamper` (P1).
- R8. **Scale.** `run` adds no request of its own (P15). How many retries one call makes, and how fast, is the policy's, bounded by RFC 0007 section 5: against a peer that never answers, with no other traffic, one call makes at most `free_retries_ceiling + 1` retries in a budget window.

### 3. Clock, Entropy and Monotonic (#281)
```rust
// grdr_model
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Monotonic { /* private: nanoseconds */ }
impl Monotonic {
    pub fn from_nanos(nanos: u64) -> Monotonic;
    pub fn checked_add(self, by: Duration) -> Option<Monotonic>;
    pub fn saturating_duration_since(self, earlier: Monotonic) -> Duration;
}

// grdr_ports::clock
pub trait Clock: Send + Sync {
    fn now(&self) -> Timestamp;
    fn monotonic(&self) -> Monotonic;
    fn sleep_until(&self, deadline: Monotonic) -> impl Future<Output = ()> + Send;
}
// grdr_ports::entropy
pub use grdr_model::Entropy;

// grdr_ports_testkit::clock
pub struct ManualClock { /* private; Sync */ }
impl ManualClock {
    pub fn new(now: Timestamp, monotonic: Monotonic) -> ManualClock;
    pub fn advance(&self, by: Duration) -> Result<(), ClockError>;
    pub fn jump_wall(&self, by_ms: i64) -> Result<(), ClockError>;
    pub fn sleeps(&self) -> Vec<Monotonic>;
}
pub enum ClockError { Overflow }
pub fn suite<A: Clock>() -> Suite<A>;
// grdr_ports_testkit::entropy
pub struct SeededEntropy { /* private */ }
impl SeededEntropy { pub fn from_seed(seed: u64) -> SeededEntropy; }

// grdr_ports_testkit, the crate root
pub use clock::{ClockError, ManualClock};
pub use entropy::SeededEntropy;
pub fn block_on<F: Future>(future: F, max_polls: u32) -> Result<F::Output, Stalled>;
pub struct Stalled { pub polls: u32 }
```

`Timestamp` and `Entropy` are `grdr-model` types that #383 builds and #1850 states. Semantics:
- `Monotonic` orders instants within one process; its arithmetic never wraps or panics. `from_nanos` takes a count of nanoseconds from an origin the clock fixes for the process, and instants of two processes are never compared.
- `now` is wall time and may jump. `monotonic` never decreases within a process and counts time the host spent suspended, so a lease holder that wakes after a sleep sees its deadlines as passed and renews or reacquires at once. The OS adapters in the programs meet this (`CLOCK_BOOTTIME` on Linux, `mach_continuous_time` on macOS, `QueryInterruptTime` on Windows; #1927).
- `sleep_until` completes once `monotonic()` is at or past `deadline`; a past deadline completes on the first poll.
- `ManualClock::advance` moves both clocks; `jump_wall` moves only `now`. `sleep_until(d)` completes on its first poll and, if `d` is later than the current monotonic value, advances both clocks to `d`. A sleep records its deadline when first polled; `sleeps` returns the recorded deadlines in order. Overflow returns `ClockError::Overflow`.
- `SeededEntropy` is SplitMix64, so one seed gives the same bytes on every target; its output for seed 0 equals the reference `splitmix64.c`.
- `block_on` drives a future with a no-op waker and returns `Stalled` once `max_polls` polls have returned `Pending`.

Suite `clock::suite()`, for any `A: Clock`: monotonic never decreases over 1,000 reads; after `sleep_until(d)` completes, `monotonic() >= d`; a past deadline completes on the first poll. Its cases drive each future with `block_on` (question 1). Callers of `Clock`: every target, the daemon, `retry::run`.

### 4. Retry executor (#283)
```rust
// grdr_ports::retry
pub async fn run<T, E, C, R, F, Fut>(
    policy: &RetryPolicy, state: &mut RetryState, clock: &C, entropy: &mut R, op: F,
) -> Result<T, RetryError<E>>
where
    C: Clock, R: Entropy + Send + ?Sized,
    F: FnMut() -> Fut + Send, Fut: Future<Output = Attempt<T, E>> + Send,
    T: Send, E: Send;

pub struct RetryState { /* private: RetryBudget, Breaker */ }
impl RetryState { pub fn new(policy: &RetryPolicy) -> RetryState; }
pub enum Attempt<T, E> { Done(T), Retry { error: E, hint: Option<Duration> }, Fail(E) }
pub enum RetryError<E> {
    BreakerOpen { until: Monotonic, last: Option<E> },
    BudgetExhausted { attempts: u32, last: Option<E> },
    Timeout { attempts: u32, last: Option<E> },
    GaveUp { reason: GiveUp, attempts: u32, last: Option<E> },
    Failed(E),
}
```

`RetryPolicy`, `RetryBudget`, `Breaker` and the give-up reason `GiveUp` are `grdr-model` types that #282 builds and #1850 states (RFC 0007 section 1). `RetryPolicy::from_limits` reads RFC 0007's `RetryLimits`. `run` passes its entropy to `RetryPolicy::next` as `&mut R` (question 2). Semantics:
- The operation says whether a failure may be retried; `run` never inspects `E`.
- Before the first call, `run` asks the breaker for a permit at `clock.monotonic()`, then records a request in the budget. Before each later call, it spends from the budget first, then asks the breaker. A breaker refusal ends the run with `BreakerOpen` and makes no call; a budget refusal ends it with `BudgetExhausted`. So every permit, a probe included, is followed by a call.
- Each call races the operation against `clock.sleep_until(start + timeout)`, where `start` is `clock.monotonic()` when the call begins and `timeout` is the policy's call timeout. Each poll polls the operation first, so an operation ready on the same poll wins. If the sleep wins, the operation is dropped and the attempt counts as retryable with no hint; with no retry after it the run returns `Timeout`.
- On `Done(t)` the breaker records a success and `run` returns `Ok(t)`.
- On `Retry` or `Fail`, `run` asks the policy once for the next step (with no hint for `Fail`), and the breaker records a failure with that step's delay, so an opened breaker's `until` is the time of the next attempt. `Fail(e)` returns `Failed(e)`. `Retry` either sleeps until `now + delay` and calls again, or returns `GaveUp`. Elapsed time is measured on `clock.monotonic()` from the first call.
- A deadline that would pass the maximum instant is the maximum instant, as the breaker's `until` is (#282).
- The race is written over `core::future::poll_fn`, with no dependency and no runtime. Every variant keeps the attempt count and the last error.
- The future of `run` is `Send` under these bounds; a compile-time test shows it.

Callers: every port call site in the targets and the daemon (ARCH-018 forbids any other retry loop).

### 5. Conformance runner (#281)
```rust
// grdr_ports_testkit::conformance
pub struct Case<S> { pub name: &'static str, pub run: fn(&S, &mut SeededEntropy) -> Result<(), Failure> }
pub struct Failure { pub check: &'static str }
pub struct Suite<S> { /* private: ordered cases */ }
impl<S> Suite<S> { pub fn run(&self, subject: &S, adapter: &str, seed: u64) -> Report; }
pub enum Outcome { Pass, Fail(Failure) }
pub struct CaseResult { pub name: &'static str, pub outcome: Outcome }
pub struct Report { pub kit_version: String, pub adapter: String, pub seed: u64, pub results: Vec<CaseResult> }
impl Report { pub fn passed(&self) -> bool; pub fn to_toml(&self) -> String; }
```

Rules of the runner:
- Only the kit builds a `Suite`, since it has no public constructor, so the cases a subject passes are the kit's own. The report's kit version is the `grdr-ports-testkit` crate version, and a change to any case is a new version. An adapter states the kit version it passed (design/03, extension points).
- `run` runs every case once, in order, on the calling thread. It builds one `SeededEntropy::from_seed(seed)` and passes it to each case in turn, so the same kit version, subject and seed replay the same run, and the report records the seed. A failing case does not stop the run.
- A `Failure` names the kit's own check and holds no text from the subject, so nothing an adapter returns, such as a driver error that echoes a connection string, reaches a report or a CI log.
- `passed()` is true when no case failed. `to_toml` renders the report as a TOML document.
- RFC 0002 section 5 extends this runner for the storage ports, with case kinds, fixtures, stop points, induced faults and a `NotApplicable` outcome. That is an amendment of this RFC.

### 6. Failure modes
| Failure | Declared outcome | Visible as |
|---|---|---|
| A future does not complete under `block_on` | `Err(Stalled { polls })` once `max_polls` polls have returned `Pending`; it never spins without a bound | The caller's error |
| A subject fails a case | That case's outcome is `Fail` with the kit's check; the run goes on to the next case, and `passed()` is false | The report: case, adapter, seed and kit version |
| A subject panics inside a case | The test fails on the panic and no report is produced, so the run never passes | The test harness's output |
| `ManualClock` arithmetic would overflow | `advance` and `jump_wall` return `ClockError::Overflow` and leave both clocks unchanged | The returned error |
| `Monotonic` arithmetic would overflow | `checked_add` returns `None`; `saturating_duration_since` given a later instant returns zero | The returned value |
| A deadline of `run` would pass the maximum instant | It is the maximum instant | The deadline in `ManualClock::sleeps()` |
| The peer never answers | Each attempt is dropped at its deadline. The run ends with `Timeout` when the policy gives up after a timed-out attempt, or earlier with `BudgetExhausted` or `BreakerOpen` | The returned error, with the attempt count and the last error |
| The breaker is open | `BreakerOpen { until, last }`, and no call is made | The returned error |
| The budget is spent | `BudgetExhausted { attempts, last }` | The returned error |
| The operation returns `Fail` | `Failed(e)` after that call; the breaker records a failure | The returned error |
| The policy gives up after a `Retry` | `GaveUp { reason, attempts, last }` | The returned error |
| The wall clock jumps during a run | No effect: elapsed time and deadlines use `monotonic()` only | #283's case with `jump_wall` between attempts |
| The host suspends during a run | A deadline that passed while the host was suspended has passed on waking, so the next attempt or the timeout comes at once | #1927's suspend case |
| The future of `run` is dropped during a call | The call is dropped with it, and neither the budget nor the breaker records it. A probe in flight leaves the breaker half-open until #1850's exit for a probe that never reports (question 2) | Nothing for an ordinary call; for a probe, the next run's `BreakerOpen` until that exit |
| A caller meets a `RetryError` | It maps the variant to its own subsystem's code, and its rule class decides the outcome (D-15) | The caller's error and code |

Nothing here fails open: no `RetryError` variant reads as success, and a variant a caller does not map fails its build.

### 7. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| R1 | A third-party allow-list per crate in `architecture.toml`, empty for both crates, read by the archlint graph rules, and a check that `grdr-ports-testkit` is in no layer 4 program's normal closure | #1580 reads the data; the entries are the protected change filed on acceptance |
| R2 | The `+ Send` bounds, checked by the compiler; a compile-time test that `run`'s future is `Send` with a sized entropy and with `dyn Entropy + Send` | #283 |
| R4, layers 0 and 1 | ARCH-001 (no layer 0 or 1 crate depends on `grdr-ports`); ARCH-003's disallowed methods and banned crates; `cargo build -p grdr-model --target wasm32-unknown-unknown` | #1580; #1582; #281 AC-6 |
| R4, layer 2 | R1's empty allow-lists, and design/03 section 10's ban on direct clock and randomness calls outside the OS adapters as disallowed methods (`std::time::Instant::now`, `std::time::SystemTime::now`, `std::thread::sleep`) in both crates | #1580; #1582 |
| R5 | ARCH-019; policies built only through `RetryPolicy::from_limits` | #1582; #279; #282 |
| R6 | ARCH-017, reading the three exemption entries; for the exhaustive `RetryError`, the compiler on each caller's match, which fails until a new variant is mapped | #1582; the protected change filed on acceptance; #283 |
| One retry loop | ARCH-018 | #1582 |
| One randomness trait (P17) | `pub use grdr_model::Entropy`; `eval-architecture` refuses a second clock or randomness trait in layers 0 to 2 on every pull request that names this RFC | #281; review |
| Section 3 and the runner | `clock::suite()` on `ManualClock` with the `jump_wall` case; a fixture clock whose monotonic value decreases, which fails exactly that case; the reference `splitmix64.c` output for seed 0; a future `Pending` by construction under `block_on`; `Monotonic` at 0 and at the largest instant | #281 AC-1 to AC-5 |
| `run`'s semantics | Under `ManualClock` and `SeededEntropy`: each recorded deadline against `RetryPolicy::next` called directly with the same seed; the timeout drop; the breaker and budget transitions, counted by a fixture operation; and a run whose budget refuses a later call while the breaker would grant a probe, after which the next run still gets its probe | #283 AC-1 to AC-3 |
| Suspended time counts | A deadline that passes while the host is suspended completes the clock's sleep on waking, on each operating system's matrix cell | #1927 |
| Stability | The `surfaces.toml` rows, `rfc-required`, `cargo public-api`, `cargo semver-checks` | The protected change filed on acceptance; #1741 |

### 8. Stability, and what each item changes
Stability:
- Both crates enter `surfaces.toml` as `experimental` (D-60; ADR-0020; design/03 section 7: every surface starts there), through the protected-change item filed on acceptance. Each gets one row of the kind `surfaces.toml` has when the item lands; in RFC 0005 R6.1's `[[crate]]` kind that is `name`, `class = "experimental"` and `rfc = "0008"`. RFC 0002 amends this RFC for both crates and keeps the rows. `Monotonic` takes the class of the `grdr-model` row (#1850), because a class belongs to a crate (RFC 0007 section 11).
- `experimental` allows a break in any release, and every change still goes by RFC. A signature, a semantic, a variant or a suite case is an amendment: a new RFC that names RFC 0008, because an accepted RFC never returns to `Review` (RFC 0001, "RFC states"). Its pull requests name that RFC for `rfc-required`. `cargo public-api` and `cargo semver-checks` run against the class once the rows exist, and the release notes list every amendment, as `breaking` when it breaks.

Proposed for `architecture.toml`, in the protected change filed on acceptance: an empty third-party allow-list for each crate, with the rule that `grdr-ports-testkit` is in no layer 4 program's normal closure; and ARCH-017 exemption entries for `grdr_ports::retry::RetryError` (generic over the caller's error, and each caller maps every variant to its own code) and for `grdr_ports_testkit::clock::ClockError` and `grdr_ports_testkit::Stalled` (test kit errors, never returned by product code). The entries take the form of the exemption list in force when the item lands (RFC 0002 section 14; RFC 0005 R4.1).

What each item changes:
- **#281**: its route is this RFC. R1 gains `from_nanos` and the derives. R2: `Clock: Send + Sync`, and `monotonic` counts suspended time. R4: `ManualClock` is `Sync`. R8 becomes the runner of section 5: a `Suite<S>` only the kit builds, cases that take `&mut SeededEntropy`, `run(&subject, adapter, seed)`, a `Failure` that names the kit's check in place of failure text, and the seed in the report. The `Fixture` traits, stop points, `arm`, `reach`, `authority()`, `tenancy()` and the storage how-to page, which RFC 0002 section 15 gave #281, are not part of it.
- **#283**: its route is this RFC. R1 takes the bounds of section 4, with a compile-time `Send` test. R3 and R4 take the order of section 4, with the budget-refusal case of section 7. R7 passes the entropy as `&mut R`. AC-4 cites ARCH-018, a scan rule of #1582, not #1580. It needs #1850 decided for the retry types and RFC 0007 for `RetryLimits`.
- **#1850**: `Monotonic` is this RFC's. `RetryPolicy::next` takes its entropy as `&mut R` for any `R: Entropy + ?Sized`, because `&mut dyn Entropy` cannot be formed from `run`'s `R` (rustc E0277). The breaker's half-open state gets an exit for a probe that never reports. Its AC-3 checks these uses against this RFC.
- **RFC 0002, next revision**: removes sections 3 and 4 and the parts of Rules 1, 2, 8 and 12 and sections 5, 12, 13, 14 and 15 that this RFC states, and points here. Its section 5 extends the runner of section 5 here, as an amendment of this RFC. Its Rule 12 barrier, under which no crate that depends on `grdr-ports` takes a registry dependency or a proc macro until #1475 lands, meets crates that already depend on `grdr-ports` for these types, the daemon first, and says how.
- **RFC 0007, next revision or decision**: section 1's row for `Monotonic`, and its notes on `Entropy` and on `RetryError` with its ARCH-017 exemption, name this RFC in place of RFC 0002.
- **#1927**: builds the OS adapters of `Clock` and `Entropy`, with the suspend case of section 7.

## Surfaces changed
- `grdr-ports` (layer 2, public): modules `clock`, `entropy` (a re-export) and `retry`. Class `experimental`.
- `grdr-ports-testkit` (layer 2, public): `ManualClock`, `ClockError`, `SeededEntropy`, `block_on` and `Stalled` at the root, the conformance runner in `conformance`, and `clock::suite`. Class `experimental`.
- `grdr-model` (layer 1, public): `Monotonic`. Class `experimental`, the crate's.
- As proposals: two `surfaces.toml` rows, and the allow-lists and ARCH-017 exemption entries of `architecture.toml` (section 8).
- No spine text, protobuf package, Cedar schema, third-party dependency or same-layer edge changes.

## Alternatives
- **Keep sections 3 and 4 in RFC 0002.** #281 and #283 would wait on a tenant boundary they do not use. Rejected.
- **A runner bound to a storage `Fixture`, as RFC 0002 section 5 has it.** The Clock suite has no store, so it could not run, and #281 would wait on the tenant types the `Fixture` names. Rejected for a runner generic over its subject.
- **Case kinds and `NotApplicable` here.** A crash case needs stop points and `NotApplicable` names a store fault. Declared here, neither would have a case. Rejected; they enter with the storage suites.
- **A `Clock` over `std::time::Instant` in `grdr-ports`.** The standard library does not specify whether `Instant` counts time the host spent suspended, and says the behaviour varies by platform and release (https://doc.rust-lang.org/std/time/struct.Instant.html, read 2026-11-22). A deadline could stay in the future after a sleep, and layer 2 would read a clock. Rejected for OS adapters in the programs.
- **`async-trait` or a boxed future, for a dyn-compatible `Clock`.** A new dependency and an allocation per sleep, while each program names its clock type at compile time anyway. Rejected.
- **The breaker before the budget on every call, as the source had it.** A probe that the budget then refused was never made. Rejected.
- **The budget before the breaker on every call.** The first call would record a request that an open breaker then never sends, so the ratio term would grow while the breaker is open. Rejected for permit, then request, on the first call.
- **`RetryError` as `#[non_exhaustive]`.** Each caller maps every variant to its own code, so a wildcard arm would map a variant added later with no decision. Rejected.

## Drawbacks
- The runner changes shape when RFC 0002 adds case kinds and `NotApplicable`: a break inside the kit, which `experimental` allows.
- `Clock` is not dyn-compatible, so every caller is generic over its clock.
- The Clock suite runs only clocks whose sleep completes by being polled (question 1).
- A later call spends a retry from the budget before an open breaker refuses it, so a breaker that stays open uses up allowance the window would otherwise keep.
- Readers find the slice-0 surface of `grdr-ports` in two RFCs.

## Unresolved questions
1. **Clocks that need a runtime.** The suite drives each future with `block_on`, which polls with a no-op waker, so it runs `ManualClock` and any clock whose sleep completes by being polled. An OS clock whose sleep needs its runtime's timer cannot pass it as written. #1927 settles how its clock runs the suite, by an amendment of this RFC, once the async runtime design/03 section 13 lists as not yet verified is chosen. This holds neither #281 nor #283, whose subjects are `ManualClock` and fixtures.
2. **#1850's signatures.** The give-up reason's name (`GiveUp` here; #1850 question 5), the entropy parameter of `RetryPolicy::next`, and the breaker's exit for a probe that never reports are #1850's. This RFC can be decided first: #1850's AC-3 holds its types to the uses here, and a difference is settled by an amendment of this RFC, or by #1850's RFC while it is in review, naming both.

## Review
Review happens on #1924. It calls for:
- the nine persona council seats, once;
- `eval-architecture`, the `[kinds] rfc` row of `.claude/risk-tiers.toml`;
- `eval-api`, the `public_api_change` row, because this RFC states the public API of three public crates;
- `eval-security`, because #1924 is `tier:high`.

At least one evaluator runs on the other model from the one in the metadata block (D-63, owner instruction 7). The RFC changes no trust-core path. It is decided after the first round in which no evaluator reports a blocker or a major (#1828, comment 7074036273).

Every seat comment and every evaluator verdict names the blobs it read, as full 40-character ids, on fixed lines (RFC 0001, "Review binds the decision"; #1798):
- `RFC file:` `git rev-parse <commit>:rfcs/0008-clock-entropy-and-the-retry-executor.md`, with the commit it read.
- `Proposed text: none`. This RFC decides no pinned path of `rfcs/pins.toml`, so it adds no decision line and commits no evidence.
- `Base:` the spine pin in force, `a80859235e7a2a4444648d6fa8d389d78dde6be9`, SHA-256 `8f6ea876777c0121ecec068c0bc4cef45932be45c1c2aff4140712db1e06628d`.

The decision rests on an `eval-architecture` pass that names the RFC file blob it decides, with no fail by an evaluator of this review on that blob. The file the decision commits may differ from that blob only in `State:`, `Decision record:`, link lines under this section and the `Decision` section (RFC 0001). Verdicts and seat comments are linked below, one per line.

## Decision
None yet.
