RFC: 0008
Title: Clock, Entropy, Monotonic and the retry executor: the first surface of grdr-ports and grdr-ports-testkit
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #1924
Spine: D-05, D-15, D-60, D-61, P1, P5, P6, P8, P9, P14, P15, P17 (no spine text changes)
Surfaces: the public crates `grdr-ports` (modules `clock`, `entropy` and `retry`) and `grdr-ports-testkit` (`ManualClock`, `ClockError`, `SeededEntropy`, `block_on`, `Stalled`, the conformance runner and the Clock suite), and the `grdr-model` type `Monotonic`. As proposals: two rows of `surfaces.toml`; two third-party allow-lists and three ARCH-017 exemption entries in `architecture.toml`; the jitter sentence of design/03 section 10 and design/22 section 2.7; three security requirements of design/02. No third-party dependency, same-layer edge, wire format or Cedar schema changes
Decision record: none yet

To comment, write on issue #1924 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This RFC takes sections 3 and 4 of RFC 0002 (#1688) at blob `5227384311da574174149f1a23958502ff213877`, with the parts of that RFC they rest on. Section 1 lists where it decides otherwise than that text. This is revision 2. The disposition of every round 1 finding is a comment on #1924.

## Summary
Slice 0 adds the first public items to `grdr-ports` and `grdr-ports-testkit`: the `Clock` and `Entropy` ports, the `grdr-model` instant type `Monotonic`, the one retry executor `grdr_ports::retry::run` and the `RetryState` it works on, their deterministic reference adapters (`ManualClock`, `SeededEntropy` and `block_on`), and the conformance runner that every later port suite extends. Layers 0 and 1 take `now` and `entropy` as arguments and do no I/O, and only the programs' OS adapters read a system clock or the system generator. `run` reads every bound from a `limits.toml` retry table through RFC 0007's `RetryLimits`. One `RetryState` serves every call of one port instance. It owns its policy, holds the budget, the breaker and the attempt counter of design/22 section 2.7, and lets health read the breaker, so a dead peer sees about one call per backoff from the whole instance. Nothing here names a tenant context, a tenant witness, the seal, the mint authority, a fence or a storage port; those stay in RFC 0002, which amends this RFC's runner for its storage suites. Both crates enter `surfaces.toml` as `experimental`.

## Motivation
#281 (Clock, Entropy, the reference adapters and the runner) and #283 (`retry::run`) are the first code in both crates, and the first runnable path needs them (#645, comment 7074036495): the daemon links `grdr-ports` for `Clock`, `Entropy` and `retry::run`. RFC 0002 sections 3 and 4 stated this surface. They share no mechanism with that RFC's tenant contexts, seal, mint authority or fences, which are what RFC 0002's review is about. A public crate changes only by RFC (D-61; design/30 section 3), and `experimental` sets the break rules, not the route (the ruling on #1535). If nothing changes, #281 and #283 wait on a tenant boundary they do not use.

Round 1 showed that the source's retry state, borrowed by one run at a time and holding no attempt counter, left the per-instance state of design/22 section 2.7 and design/20 with nowhere to live (#1924, comment 7076101630). Revision 2 states that state here, before #283 builds `run`.

## Design

### 1. Scope and the split from RFC 0002
This RFC states RFC 0002 sections 3 and 4, and the parts of RFC 0002's Rules 1, 2, 7, 8 and 12 and sections 5, 12 and 14 that bear on them. RFC 0002 keeps everything else. Its next revision removes sections 3 and 4 and points here (section 8).

The rules of section 2 and the failure modes of section 6 gather what RFC 0002, #281 and #283 already say. Otherwise the text follows the source, except in six places:
1. The runner (section 5) is generic over its subject. The source bound it to a storage `Fixture`, so the Clock suite, which is generic over `A: Clock`, could not run on it. Its types are `#[non_exhaustive]`, so RFC 0002 adds case kinds, fixtures, stop points, induced faults and the `NotApplicable` outcome by amendment, with the storage suites that need them.
2. "The RFC of #1710" becomes #1850 for the `grdr-model` retry types and RFC 0007 for `RetryLimits`, as RFC 0007 section 7 asks.
3. `Monotonic` gains `from_nanos` and its derives. Without a constructor, neither an OS clock nor a test can make the instant `ManualClock::new` takes, and `monotonic() >= d` needs the order.
4. Before each call, `run` checks the breaker, then the budget, then takes the permit, in one step under the state's lock. A refused call spends nothing, and every permit, a probe included, is followed by a call. In the source order a probe that the budget then refused was never made, and the breaker stayed half-open with every later permit refused (#282 R9).
5. One `RetryState` serves every call of one port instance (R9). It owns its policy, holds the budget, the breaker and design/22's attempt counter, and gives health a read of the breaker. The source let one run at a time borrow a state with no counter, so concurrent calls needed a state each, and even one kept state restarted its backoff at every run: a dead peer saw about one call per base delay.
6. A half-open breaker holds a probe deadline, the permit's instant plus the call timeout. Under #282 R9 a probe whose run was dropped held the breaker half-open for good.

The split needs items 1 and 2. Items 3 to 6 each fix a defect of the source that would stop #281 or #283, or leave a peer unprotected. Where the source is silent this RFC states that `start` is the call's own start; that a deadline past the maximum instant is the maximum instant, as #282 has it for the breaker; that the runner passes one seeded entropy to its cases in turn; that `RetryError` is exhaustive; that each call and each failed attempt reads the clock once; that a peer's refusal of one request is `Done`, not `Fail`; the derives of every public type; how `to_toml` writes a string; and the values of the Clock suite's case parameters.

### 2. Rules
- R1. **Dependencies.** `grdr-ports` depends on `grdr-model` and `grdr-schema` and on no other crate, third-party crates included. The privileged daemon links it, so whatever it links is in the daemon's closure. `grdr-ports-testkit` depends on `grdr-ports`, through the listed same-layer edge, on layer 0 and 1 crates of the workspace, and on no third-party crate; RFC 0002 adds the Arrow crates for its Events reference adapter. It is never in the normal-dependency closure of a layer 4 program, resolved with all of that program's features. A program's `Clock` is `grdr-os-clock`'s and its `Entropy` is `grdr-crypto`'s `OsRandom`, the system generator (#1927 R11; design/03 ARCH-003). So neither `ManualClock`, which whoever holds it can move, nor `SeededEntropy`, whose every later output one output reveals, reaches product code.
- R2. **Async shape.** `Clock` has `Send + Sync` as supertraits. `sleep_until` is declared as returning `impl Future<Output = ()> + Send`, which an implementation may write as an `async fn`. There is no `async-trait`, no boxed future and no `futures` crate, so `Clock` is not dyn-compatible and a caller is generic over `C: Clock`. `Entropy` is synchronous and stays dyn-compatible, because `Engine::step` takes `&mut dyn Entropy` (design/03 section 3). `RetryState` is `Send + Sync`, so the future of `run` is `Send` while it borrows a shared state. A WebAssembly host passes `now` and an `Entropy` to the engine as values and implements no `Clock`.
- R3. **Open traits.** `Clock` and `Entropy` are not sealed. The programs implement them over the operating system (#1927), and the kit implements them for tests. RFC 0002's seal covers its storage ports only.
- R4. **Layers 0 and 1.** Layers 0 and 1 hold no `Clock`, read no clock or randomness source and do no I/O (spine section 5; D-05). A layer 1 function that needs time takes `now: Timestamp` or a `Monotonic` as an argument, and one that needs randomness takes an `Entropy`, as `Engine::step` does. `Monotonic` and `Entropy` live in `grdr-model`, and `Monotonic` is a value that reads no clock. `Clock` lives in layer 2, so no layer 0 or 1 crate can name it (ARCH-001). Above layer 1, design/03's ARCH-003 makes `grdr-os-clock` the only crate that calls a system clock and the `random` module of `grdr-crypto` the only reader of the system generator, so nothing in `grdr-ports` or `grdr-ports-testkit` reads either (design/03 section 10, Time and Randomness).
- R5. **Bounds are parameters.** Every bound `run` applies (attempts, elapsed time, delays, call timeout, budget, breaker and probe deadline) comes from the `RetryPolicy` its state owns. Product code builds a policy only with `RetryPolicy::from_limits`, from a `[retry.<name>]` table of `limits.toml` or a narrowing of one (RFC 0007 sections 5 and 6; #1850). `block_on`'s poll bound is an argument. No type here holds a tunable bound (ARCH-019). The Clock suite's case parameters (section 3) are part of each case's definition, not bounds the product applies: they are named constants of the kit's case module, at the values section 3 states, and a change to one is a change to the case, so a new kit version and an amendment (section 8).
- R6. **Errors.** `RetryError<E>` has no code. Its caller maps every variant to a code of the subsystem that failed, and the caller's rule class decides what the failure means (D-15). It is exhaustive, so a variant added by amendment fails every caller's build until the caller maps it. The kit's errors, `ClockError` and `Stalled`, have no code and hold no free text. All three are entries of the ARCH-017 exemption list in `architecture.toml`, each with its reason, so the lint reads data and special-cases no name (section 8). Each implements `LogSafe` (#1850): `RetryError<E>` where `E` does, with the `Monotonic` and the give-up reason it carries. No type here holds a person-facing string.
- R7. **Data classes and assurance.** `Monotonic`, `Timestamp`, attempt counts, the attempt counter, delays, deadlines, the breaker's state, seeds, reports and the kit's errors are `structural` (P8). Entropy output is never logged or stored. `run` never logs `E`, which keeps the class its own type declares. Assurance effect: none; no action class changes `visibility`, `control`, `on_failure` or `tamper` (P1).
- R8. **Scale.** `run` adds no request of its own (P15). One call makes at most `free_retries_ceiling + 1` retries in a budget window, as RFC 0007 section 5 bounds it. Every call of one port instance shares one state (R9), so once its breaker has opened, the instance as a whole reaches a peer that fails every call once per open period: at `until`, which the attempt counter's backoff set, or at a probe deadline. The counter keeps growing across runs up to the table's cap. With design/22 section 2.7's control-plane backoff (attempt n waits `U(0, min(120 s, 1 s × 2^n))`) and a breaker that opens after 5 failures, one device against a dead origin makes about 69 calls an hour, where counting attempts per run makes about 1,460. At ten million devices that is about 190,000 requests a second instead of about 4 million (the revision 2 bench, posted on #1924).
- R9. **One state per port instance.** A `RetryState` belongs to one port instance and one policy, and every call of that instance, from any task, uses it: the adapter instance of a server port (design/20, "Stability"), or one origin and operation class of the uplink (design/22 section 2.7). It is built with the instance and lives as long as it. It is never per call, and never per principal (P8; RFC 0007 section 7).
- R10. **Derives.** Every public type here implements `Debug`, and each derives what sections 3 to 5 write beside it, so a test can unwrap a kit result and compare an error. `RetryState` and `ManualClock` are not `Clone`, because a copy would split one instance's state, or one test's time, in two. `Outcome` is not `Copy`, so RFC 0002's `NotApplicable(Fault)` can join it.

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
#[derive(Debug)]
pub struct ManualClock { /* private; Sync */ }
impl ManualClock {
    pub fn new(now: Timestamp, monotonic: Monotonic) -> ManualClock;
    pub fn advance(&self, by: Duration) -> Result<(), ClockError>;
    pub fn jump_wall(&self, by_ms: i64) -> Result<(), ClockError>;
    pub fn sleeps(&self) -> Vec<Monotonic>;
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ClockError { Overflow }
pub fn suite<A: Clock>() -> Suite<A>;
// grdr_ports_testkit::entropy
#[derive(Clone, Debug)]
pub struct SeededEntropy { /* private */ }
impl SeededEntropy { pub fn from_seed(seed: u64) -> SeededEntropy; }

// grdr_ports_testkit, the crate root
pub use clock::{ClockError, ManualClock};
pub use entropy::SeededEntropy;
pub fn block_on<F: Future>(future: F, max_polls: u32) -> Result<F::Output, Stalled>;
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Stalled { pub polls: u32 }
```

`Timestamp` and `Entropy` are `grdr-model` types that #383 builds and #1850 states. Semantics:
- `Monotonic` orders instants within one process; its arithmetic never wraps or panics. `from_nanos` takes a count of nanoseconds from an origin the clock fixes for the process, and instants of two processes are never compared. Nothing here sends one, and the one value section 4 lets a program persist, the attempt counter, holds none.
- `now` is wall time and may jump. `monotonic` never decreases within a process and counts time the host spent suspended, so a lease holder that wakes after a sleep sees its deadlines as passed and renews or reacquires at once. The OS adapter meets this with the boot-time count: `CLOCK_BOOTTIME` on Linux, `mach_continuous_time` on macOS, and `QueryInterruptTimePrecise` on Windows, the same interrupt-time count as `QueryInterruptTime` read from the timer hardware instead of at the last clock tick (#1927 R2).
- `sleep_until` completes once `monotonic()` is at or past `deadline`; a past deadline completes on the first poll.
- `ManualClock::advance` moves both clocks; `jump_wall` moves only `now`. `sleep_until(d)` completes on its first poll and, if `d` is later than the current monotonic value, advances both clocks to `d`. A sleep records its deadline when first polled; `sleeps` returns the recorded deadlines in order. Overflow returns `ClockError::Overflow`.
- `SeededEntropy` is SplitMix64, so one seed gives the same bytes on every target; its output for seed 0 equals the reference `splitmix64.c`. Its state is no secret, since a report records the seed, so it derives `Clone` and `Debug`.
- `block_on` drives a future with a no-op waker and returns `Stalled` once `max_polls` polls have returned `Pending`.

Suite `clock::suite()`, for any `A: Clock`, has three cases, in this order:
- `monotonic_never_decreases`: 1,000 reads of `monotonic()`, each at or after the one before.
- `sleep_reaches_deadline`: `d` is `monotonic()` plus 10 ms; `block_on(sleep_until(d), 1_000)` completes, and `monotonic() >= d` after it.
- `past_deadline_first_poll`: `d` is `monotonic()`; `block_on(sleep_until(d), 1)` completes.

Each case drives its future with `block_on`, so a clock runs the suite when its sleep completes by being polled. `ManualClock`'s does. An OS clock whose sleep waits on its runtime's timer runs the suite with a test timer that blocks the thread and is ready on its first poll: #1927's `OsClock<T: Timer>` takes its timer as a parameter for this, so the suite runs it as written (lead-core, #1924 comment 7075943320). The 10 ms offset keeps that run short. Callers of `Clock`: every target, the daemon, `retry::run`.

### 4. Retry executor (#283)
```rust
// grdr_ports::retry
pub async fn run<T, E, C, R, F, Fut>(
    state: &RetryState, clock: &C, entropy: &mut R, op: F,
) -> Result<T, RetryError<E>>
where
    C: Clock, R: Entropy + Send + ?Sized,
    F: FnMut() -> Fut + Send, Fut: Future<Output = Attempt<T, E>> + Send,
    T: Send, E: Send;

#[derive(Debug)]
pub struct RetryState { /* private: the RetryPolicy; behind one lock, the RetryBudget, the Breaker and the attempt counter */ }
impl RetryState {
    pub fn new(policy: RetryPolicy) -> RetryState;
    pub fn resume(policy: RetryPolicy, attempt_counter: u32) -> RetryState;
    pub fn policy(&self) -> &RetryPolicy;
    pub fn breaker(&self) -> Breaker;
    pub fn attempt_counter(&self) -> u32;
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Attempt<T, E> { Done(T), Retry { error: E, hint: Option<Duration> }, Fail(E) }
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RetryError<E> {
    BreakerOpen { until: Monotonic, last: Option<E> },
    BudgetExhausted { attempts: u32, last: Option<E> },
    Timeout { attempts: u32, last: Option<E> },
    GaveUp { reason: GiveUp, attempts: u32, last: Option<E> },
    Failed(E),
}
```

`RetryPolicy`, `RetryBudget`, `Breaker` and the give-up reason `GiveUp` are `grdr-model` types that #282 builds and #1850 states (RFC 0007 section 1); section 8 lists what this section needs of them. `RetryPolicy::from_limits` reads RFC 0007's `RetryLimits`.

The state:
- `RetryState::new(policy)` builds the state of one port instance (R9) under `policy`, which it owns, so a state never runs under a policy it was not built from. `run` borrows it shared, so any number of concurrent calls use one state. It is `Send + Sync` and not `Clone`.
- The budget, the breaker and the attempt counter sit behind one `std::sync::Mutex`. `run` holds the lock only while it reads or updates them: never across an `.await`, and never while the operation or the entropy runs. A poisoned lock is taken back with `PoisonError::into_inner`, because no step that holds it runs caller code or a panic path, and each step leaves the state whole. The state reads no clock: every instant it records is one that `run` read from the `Clock`.
- The attempt counter is design/22 section 2.7's: the failed attempts on the instance since its last success, across every run and every caller. A `Retry`, a `Fail` and a timed-out call each add one, saturating at `u32::MAX`; only `Done` sets it to 0. `run` passes its value before the failure being recorded to `RetryPolicy::next`, as the attempt whose ceiling the delay is drawn under, and passes the run's own retries so far for the give-up checks. So a new run continues the backoff the instance reached, and a table's `max_attempts` and `max_elapsed` still bound one call.
- `attempt_counter()` reads the counter, and `resume(policy, n)` builds a state that continues from `n`. design/22 section 2.7 keeps the uplink's counter in the daemon's state directory, so an uplink restart continues it; #1238 (22-5, `uplink-reconnect`) writes it there and reads it back, and needs no port from this RFC. Only the counter persists. A new process starts with an empty budget and a closed breaker, because both hold `Monotonic` instants. design/20 asks nothing more of its policies, so theirs live in memory.
- `breaker()` returns a copy of the breaker's state, from which a target shows an open breaker in its health and on the operator plane (design/20, "Stability" and the operator plane's health list). The copy changes nothing.

A call:
- Before each call `run` reads `clock.monotonic()` once. Under one hold of the lock it asks the breaker, without a transition, whether a permit at that instant would be refused. If so, the run ends with `BreakerOpen { until, last }` and nothing is recorded. Otherwise it records a request in the budget for the first call, or spends from the budget for a later one, and a budget refusal ends the run with `BudgetExhausted` with the breaker untouched. Only then does it take the breaker's permit, which the first check has granted. So a refused call spends nothing, and every permit, a probe included, is followed by a call.
- That instant is the call's `start`. The call races the operation against `clock.sleep_until(start + timeout)`, where `timeout` is the policy's call timeout. Each poll polls the operation first, so an operation ready on the same poll wins. If the sleep wins, the operation is dropped and the attempt counts as retryable with no hint; with no retry after it the run returns `Timeout`.
- On `Done(t)` the breaker records a success, the counter goes to 0 and `run` returns `Ok(t)`. The operation returns `Done` only for an answer it accepts as the peer's own; for the uplink that is a verified response (design/22 section 2.7).
- On `Retry`, `Fail` or a timeout, `run` reads `clock.monotonic()` once. That instant is the breaker's record, the start of the sleep and the end of `elapsed`, which runs from the first call's instant. `run` asks the policy once for the next step, with no hint for `Fail` or a timeout. Then, under the lock, the breaker records a failure with that step's delay and the counter adds one, so an opened breaker's `until` is the instant this run's next attempt is due. `Fail(e)` returns `Failed(e)`. Otherwise the run sleeps until `now + delay` and calls again, or returns `GaveUp`, or `Timeout` if the last attempt timed out.
- `Fail` is a failure of the peer that no retry fixes, such as a certificate the operation refuses, and it counts against the instance as `Retry` does. A peer's answer that refuses one request, such as an invalid argument or a missing row, is `Done` with the operation's own error in `T`. The peer answered, so one caller's refused requests never open the breaker that every caller of the instance shares, and never grow its counter.
- A half-open breaker holds its probe deadline: the permit's instant plus the policy's call timeout, which is the `timeout_ms` of its `[retry.<name>]` table, at most the `retry-bounds.timeout-ceiling` row (RFC 0007 section 6). Before the deadline every permit is refused with `until` at it; at or after it the next permit takes a new probe. A live probe reports by that instant, because its race ends there. A probe that never reports, because its run was dropped, forgotten or is no longer polled, holds the instance for at most the call timeout.
- A deadline that would pass the maximum instant is the maximum instant, as the breaker's `until` is (#282).
- The race is written over `core::future::poll_fn`, with no dependency and no runtime. Every variant keeps the attempt count and the last error.
- The future of `run` is `Send` under these bounds. A compile-time test shows it, and so also shows that no lock is held across an `.await`.

Callers: every port call site in the targets and the daemon (ARCH-018 forbids any other retry loop), each through the state of its port instance (R9).

### 5. Conformance runner (#281)
```rust
// grdr_ports_testkit::conformance
#[non_exhaustive]
pub struct Case<S> { pub name: &'static str, pub run: fn(&S, &mut SeededEntropy) -> Result<(), Failure> }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Failure { pub check: &'static str }
pub struct Suite<S> { /* private: ordered cases */ }
impl<S> Suite<S> { pub fn run(&self, subject: &S, adapter: &str, seed: u64) -> Report; }
#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Outcome { Pass, Fail(Failure) }
#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CaseResult { pub name: &'static str, pub outcome: Outcome }
#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Report { pub kit_version: String, pub adapter: String, pub seed: u64, pub results: Vec<CaseResult> }
impl Report { pub fn passed(&self) -> bool; pub fn to_toml(&self) -> String; }
// Case<S> is Clone, Copy and Debug, and Suite<S> is Debug, for every S.
```

Rules of the runner:
- This RFC holds the one definition of `Case`, `Suite`, `Outcome`, `CaseResult`, `Report` and the runner. RFC 0002 (#1688) amends them for the storage suites: `kind` on `Case` and `CaseResult`, `Outcome::NotApplicable(Fault)`, the `Fixture` bound on each storage suite's constructor, and the arming state `run` holds. #281 builds the runner as this RFC states it.
- Only the kit builds a `Suite`, since it has no public constructor, so the cases a subject passes are the kit's own. The report's kit version is the `grdr-ports-testkit` crate version, and a change to any case is a new version. An adapter states the kit version it passed (design/03, extension points).
- `Case`, `CaseResult`, `Outcome` and `Report` are `#[non_exhaustive]`. Code outside the kit reads them and cannot build one, so no report is made outside the kit, and a field or variant added by amendment breaks no caller: a match on `Outcome` outside the kit already needs a wildcard arm.
- `Suite::run` has no bound on `S`. A suite's constructor carries the bound its cases need, as `clock::suite<A: Clock>()` does, and `run` may hold state the kit keeps per process for the whole run. So neither RFC 0002's `Fixture` bound nor its arming changes `run`.
- `run` runs every case once, in order, on the calling thread. It builds one `SeededEntropy::from_seed(seed)` and passes it to each case in turn, so the same kit version, subject and seed replay the same run, and the report records the seed. A failing case does not stop the run.
- A `Failure` names the kit's own check and holds no text from the subject, so nothing an adapter returns, such as a driver error that echoes a connection string, reaches a report or a CI log.
- `passed()` is true when no case failed. `to_toml` renders the report as a TOML document and writes each string as a TOML basic string, with the quotation mark, the backslash and every control character escaped, so no adapter name adds a key or a line.

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
| The peer fails every call and callers keep starting runs | Once the breaker has opened, the instance reaches the peer once per open period; every other call ends with `BreakerOpen` and makes no call, and the counter's backoff grows across runs up to the table's cap (R8) | `BreakerOpen` to each refused caller; the open breaker in the target's health, through `breaker()` |
| The breaker is open | `BreakerOpen { until, last }`; no call is made and the budget is not touched | The returned error |
| The budget is spent | `BudgetExhausted { attempts, last }`; the breaker is not touched | The returned error |
| The operation returns `Fail` | `Failed(e)` after that call; the breaker records a failure and the counter adds one | The returned error |
| The peer refuses one caller's request | The operation returns it as `Done` with its own error, so the breaker and the counter count the peer as up | The caller's error |
| The policy gives up after a `Retry` | `GaveUp { reason, attempts, last }` | The returned error |
| A probe never reports: its run is dropped, forgotten or no longer polled | The breaker stays half-open until the probe deadline, the permit's instant plus the call timeout; the next permit at or after it takes a new probe | `BreakerOpen { until }`, with `until` at the deadline, to calls in between |
| The future of `run` is dropped during an ordinary call | The call is dropped with it. The budget keeps the request or the retry it recorded before the call began; the breaker and the counter record no outcome for it | Nothing |
| A resumed attempt counter is stale or altered | Any value is a valid counter. The delay stays within the table's cap, so a counter set too high makes each retry wait at most the cap, and one set too low costs at most the retries the budget allows before the breaker opens | The delays of the next run; `ManualClock::sleeps()` under test |
| The state's lock is poisoned | Taken back with `into_inner`; no step that holds the lock runs caller code or a panic path, so the state is whole | Nothing |
| The wall clock jumps during a run | No effect: elapsed time and deadlines use `monotonic()` only | #283's case with `jump_wall` between attempts |
| The host suspends during a run | A deadline that passed while the host was suspended has passed on waking, so the next attempt or the timeout comes within `clock.recheck` of waking (#1927 R8) | #1927's sleep model; #1936 on real cells |
| The system generator fails | The programs' `Entropy` never returns bytes it did not draw from the generator: zeroed or repeated bytes would make every full-jitter delay 0, and every key and nonce predictable. How the failure reaches `run` is #1850's; question 2 gives what each option does to `RetryError` | #1850's error, or the give-up reason `run` returns |
| A caller meets a `RetryError` | It maps the variant to its own subsystem's code, and its rule class decides the outcome (D-15) | The caller's error and code |

Nothing here fails open: no `RetryError` variant reads as success, a variant a caller does not map fails its build, and none of #1850's options for a failed draw returns bytes that were not drawn.

### 7. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| R1 | A third-party allow-list per crate in `architecture.toml`, empty for both crates, read by the archlint graph rules. A check that `grdr-ports-testkit` is in no layer 4 program's normal closure, resolved with all of that program's features, with negative fixtures: a program with the kit as a normal dependency, one that reaches it through a layer 3 crate, and one that reaches it only under one of its features each fail | #1580 reads the data and adds the fixtures, a constraint posted there on acceptance; the entries are the protected change filed on acceptance |
| R1 and R4, the readers above layer 1 | design/03 ARCH-003: outside `grdr-os-clock` and the `random` module of `grdr-crypto`, the architecture lint refuses a system clock or generator call, a `clippy::disallowed_methods` allow over one, and a direct `getrandom` or `rand` dependency, reading the two readers and the refused calls from `architecture.toml` | #1582, its ARCH-003 part (#1582 comment 7076081436) |
| R2 | The `+ Send` bounds, checked by the compiler; compile-time tests that `run`'s future is `Send` with a sized entropy and with `dyn Entropy + Send`, and that two runs on one `&RetryState` build and run | #283 |
| R4, layers 0 and 1 | ARCH-001 (no layer 0 or 1 crate depends on `grdr-ports`); ARCH-003's disallowed methods and banned crates; `cargo build -p grdr-model --target wasm32-unknown-unknown` | #1580; #1582; #281 AC-6 |
| R5 | ARCH-019; policies built only through `RetryPolicy::from_limits`; the Clock suite's parameters as named constants at section 3's values | #1582; #279; #282; #281 |
| R6 | ARCH-017, reading the three exemption entries; for the exhaustive `RetryError`, the compiler on each caller's match, which fails until a new variant is mapped | #1582; the protected change filed on acceptance; #283 |
| R9 | `run` borrows a `Sync` state, and `RetryState` is not `Clone`, so sharing is the one form that compiles without a state per call. `eval-architecture` checks, on every pull request that adds a call to `retry::run` or `RetryState::new`, that the state is built with its port instance and stored in it. No scan holds this: a constructor that builds its state and retries its first connection through `run` is correct, and a rule on the call sites would refuse it | The compiler; review, on that event |
| R10 | The compiler on #281's and #283's tests, which unwrap the kit's results, return `Result<(), ClockError>` and format each public type with `{:?}`; `cargo public-api` lists the impls | #281; #283 |
| One retry loop | ARCH-018 | #1582 |
| One randomness trait (P17) | `pub use grdr_model::Entropy`; `eval-architecture` refuses a second clock or randomness trait in layers 0 to 2 on every pull request that names this RFC | #281; review |
| Section 3 and the runner | `clock::suite()` on `ManualClock` with the `jump_wall` case; a fixture clock whose monotonic value decreases, which fails exactly that case; the reference `splitmix64.c` output for seed 0; a future `Pending` by construction under `block_on`; `Monotonic` at 0 and at the largest instant. Compile-fail doctests: outside the kit, a struct expression of `Report`, `CaseResult` or `Case`, and a match on `Outcome` with no wildcard arm, each fail. `to_toml` of a report whose adapter name holds a quotation mark, a backslash and a line break has one `adapter` line and no other key | #281 AC-1 to AC-5, and its doctests |
| `run`'s semantics | Under `ManualClock` and `SeededEntropy`: each recorded deadline against `RetryPolicy::next` called directly with the same seed and counts; the breaker's `until` equal to the next sleep's deadline; the timeout drop; the breaker and budget transitions, counted by a fixture operation; a run whose budget refuses a later call while the breaker would grant a probe, after which the next run still gets its probe; and a retry the open breaker refuses, which spends nothing, so the retry due at `until` makes the probe | #283 AC-1 to AC-3 |
| The shared state and the counter (R8, R9) | Against a reference model of section 4 over #282's types, written in the test from this text: one caller that starts a new run after each error against a peer that fails every call, whose peer calls and gaps equal the model's; many runs on one state under a test clock whose sleep waits until the test moves it, whose peer calls equal the model's; `resume` continuing the backoff; and a success resetting the counter | #283 |
| The probe deadline | `HalfOpen` refuses before its deadline with `until` at it, and probes at it. A run that takes the probe and is dropped after one poll, under the test clock above; a run one nanosecond before the deadline is then refused with no call, and a run at the deadline makes the probe | #282; #283 |
| Health | `RetryState::breaker()`; each target shows an open breaker in its health | #283 (the read); #1584 and each target's health item (the display) |
| Suspended time counts | #1927 proves the sleep against scripted boot-time readings and checks each system's boot-time read on the hosted runners; real suspend and wake on each system's matrix cell | #1927; #1936 on real cells |
| Stability | The `surfaces.toml` rows, `rfc-required`, `cargo public-api`, `cargo semver-checks` | The protected change filed on acceptance; #1741 |

### 8. Stability, and what each item changes
Stability:
- Both crates enter `surfaces.toml` as `experimental` (D-60; ADR-0020; design/03 section 7: every surface starts there), through the protected-change item filed on acceptance. Each gets one row of the kind `surfaces.toml` has when the item lands; in RFC 0005 R6.1's `[[crate]]` kind that is `name`, `class = "experimental"` and `rfc = "0008"`. RFC 0002 amends this RFC for both crates and keeps the rows. `Monotonic` takes the class of the `grdr-model` row (#1850), because a class belongs to a crate (RFC 0007 section 11).
- `experimental` allows a break in any release, and every change still goes by RFC. A signature, a semantic, a variant or a suite case is an amendment: a new RFC that names RFC 0008, because an accepted RFC never returns to `Review` (RFC 0001, "RFC states"). Its pull requests name that RFC for `rfc-required`. `cargo public-api` and `cargo semver-checks` run against the class once the rows exist, and the release notes list every amendment, as `breaking` when it breaks.

Proposed for `architecture.toml`, in the protected change filed on acceptance: an empty third-party allow-list for each crate, with the rule that `grdr-ports-testkit` is in no layer 4 program's normal closure under any of that program's features; and ARCH-017 exemption entries for `grdr_ports::retry::RetryError` (generic over the caller's error, and each caller maps every variant to its own code) and for `grdr_ports_testkit::clock::ClockError` and `grdr_ports_testkit::Stalled` (test kit errors, never returned by product code). The entries take the form of the exemption list in force when the item lands (RFC 0002 section 14; RFC 0005 R4.1).

Proposed for the design documents, each filed on acceptance as the chief architect's design item:
- **design/03 section 10 (Retries) and design/22 section 2.7.** The full jitter is drawn from the program's system generator (R1), not "seeded by device id, boot id and attempt". Independent draws from each device's generator keep devices out of step, which is what the seed was for, while a seed built from those three values would let anyone who knows them predict a device's retries.
- **design/02 section 3.8.** Three security requirements, as eval-security worded them in round 1 (#1924 comment 7076101630). One `RetryState` per port instance and policy holds the attempt counter, the budget and the breaker for every call to that peer; a new run continues the counter, only a success resets it, and a program can persist and resume it. A probe that never reports stops holding the breaker by its permit's instant plus the call timeout. Product code draws randomness only from the system generator, and no deterministic `Entropy` is in a program's normal closure.

What each item changes:
- **#281**: its route and its scope are this RFC: sections 3 and 5 as decided, with any amendment decided before it is worked. R1 gains `from_nanos` and the derives. R2: `Clock: Send + Sync`, and `monotonic` counts suspended time. R4: `ManualClock` is `Sync`. R8 becomes the runner of section 5: a `Suite<S>` only the kit builds, an unbounded `run(&subject, adapter, seed)`, cases that take `&mut SeededEntropy`, a `Failure` that names the kit's check in place of failure text, the seed in the report, the `#[non_exhaustive]` types with their compile-fail doctests, and `to_toml`'s escaping. R9 takes the three cases and parameters of section 3. Every public type takes the derives of R10. The `Fixture` traits, case kinds, `NotApplicable`, stop points, `arm`, `reach`, `authority()`, `tenancy()` and the storage how-to page, which RFC 0002 section 15 gave #281, come with RFC 0002's amendment and its items.
- **#283**: its route is this RFC. R1 becomes `run(state: &RetryState, clock, entropy: &mut R, op)` with the bounds of section 4, where `RetryState` owns its policy and holds the budget, the breaker and the attempt counter behind one lock, with `new`, `resume`, `policy`, `breaker` and `attempt_counter`. R3 and R4 take section 4's one-step check. R7 passes the counter and the run's retries to `next`, and the entropy as `&mut R`. The non-goal "Sharing `RetryState` across tasks" goes, because sharing is the point (R9). Its tests take section 7's cases for R2, `run`'s semantics, the shared state and the probe deadline. AC-4 cites ARCH-018, a scan rule of #1582, not #1580. It needs #1850 decided for the retry types and RFC 0007 for `RetryLimits`.
- **#1850**, with #282, which builds its types. `Monotonic` is this RFC's, and section 4 needs these:
  1. `RetryPolicy::next` takes its entropy as `&mut R` for any `R: Entropy + ?Sized`, because `&mut dyn Entropy` cannot be formed from `run`'s `R` (rustc E0277).
  2. `next` takes two counts: the instance's attempt counter, which sets the ceiling (#282 R3 and R4), and the run's retries so far, which the `MaxAttempts` check reads (#282 R7). For one run on a new state the two are equal, so #282's vectors hold.
  3. `Breaker`'s half-open state holds its probe deadline, the permit's instant plus the policy's call timeout. Before the deadline a permit is refused with `until` at it; at or after it the permit takes a new probe and moves the deadline. This replaces #282 R9's `Refuse { until: now }`, with a case for each.
  4. `Breaker` answers, without a transition, whether a permit at `now` would be refused and until when, so `run` checks it before it spends.
  5. `RetryPolicy`, `RetryBudget` and `Breaker` are `Send + Sync`, so the future of `run` is `Send`. `RetryPolicy` is `Clone` and `Debug`, since a state owns one. `Breaker` derives `Clone`, `Copy`, `Debug`, `PartialEq` and `Eq`, since `breaker()` returns a copy. The give-up reason derives the same and implements `LogSafe`, so `RetryError<E>` is `LogSafe` where `E` is.
  6. AC-3's use `RetryState::new(&RetryPolicy)` becomes `RetryState::new(RetryPolicy)`, by value.
  7. How a failed draw from the system generator reaches `run` (question 2).

  #282's non-goal "Sharing one budget or breaker across threads: the caller owns the instance" stays true: `RetryState` in `grdr-ports` shares them.
- **#1580**: the negative fixtures of R1's closure check, posted there as a constraint on acceptance.
- **#1582**: ARCH-003 for layers 2 to 4 as design/03 has it (R1, R4).
- **#1238** (22-5, `uplink-reconnect`): one `RetryState` per origin and operation class, with the counter written to the daemon's state directory from `attempt_counter()` and read back through `resume` when the uplink starts (design/22 section 2.7).
- **RFC 0002, next revision**: removes sections 3 and 4 and the parts of Rules 1, 2, 8 and 12 and sections 5, 12, 13, 14 and 15 that this RFC states, and points here. It states its runner additions as an amendment of this RFC (section 5): `kind` on `Case` and `CaseResult`, `Outcome::NotApplicable(Fault)`, the `Fixture` bound on each storage suite's constructor in place of `impl<F: Fixture> Suite<F>`, and the arming state the kit holds inside `run` for every suite. Its adapters build one `RetryState` per port instance and policy (R9). Its Rule 12 barrier, under which no crate that depends on `grdr-ports` takes a registry dependency or a proc macro until #1475 lands, applies to crates that name a capability type of `grdr-ports` (its `tenant`, `storage` and `adapter` modules). The daemon, which links `grdr-ports` only for this RFC's `clock`, `entropy` and `retry`, is outside it.
- **RFC 0007, next revision or decision**: section 1's row for `Monotonic`, and its notes on `Entropy` and on `RetryError` with its ARCH-017 exemption, name this RFC in place of RFC 0002. Section 5's "the caller decides whether a new episode starts" still holds: a new run continues the attempt counter, and only a success resets it (design/22 section 2.7).
- **#1927**: builds the programs' OS `Clock`, `OsClock`, with the suspend rows of sections 6 and 7 and the Windows reader of section 3, and pairs it with `OsRandom` as the programs' `Entropy` (#1927 R11).

## Surfaces changed
- `grdr-ports` (layer 2, public): modules `clock`, `entropy` (a re-export) and `retry`. Class `experimental`.
- `grdr-ports-testkit` (layer 2, public): `ManualClock`, `ClockError`, `SeededEntropy`, `block_on` and `Stalled` at the root, the conformance runner in `conformance`, and `clock::suite`. Class `experimental`.
- `grdr-model` (layer 1, public): `Monotonic`. Class `experimental`, the crate's.
- As proposals: two `surfaces.toml` rows, and the allow-lists and ARCH-017 exemption entries of `architecture.toml`; the jitter sentence of design/03 section 10 and design/22 section 2.7, and three security requirements of design/02 (section 8).
- No spine text, protobuf package, Cedar schema, third-party dependency or same-layer edge changes.

## Alternatives
- **Keep sections 3 and 4 in RFC 0002.** #281 and #283 would wait on a tenant boundary they do not use. Rejected.
- **A runner bound to a storage `Fixture`, as RFC 0002 section 5 has it.** The Clock suite has no store, so it could not run, and #281 would wait on the tenant types the `Fixture` names. Rejected for a runner generic over its subject.
- **Case kinds and `NotApplicable` here.** A crash case needs stop points and `NotApplicable` names a store fault. Declared here, neither would have a case. Rejected; RFC 0002 adds them by amendment.
- **Exhaustive runner types.** A field or variant RFC 0002 adds would break every caller that builds or matches one, and code outside the kit could build a report that passes. Rejected for `#[non_exhaustive]`.
- **A `Clock` over `std::time::Instant` in `grdr-ports`.** The standard library does not specify whether `Instant` counts time the host spent suspended, and says the behaviour varies by platform and release (https://doc.rust-lang.org/std/time/struct.Instant.html, read 2026-11-22). A deadline could stay in the future after a sleep, and layer 2 would read a clock. Rejected for OS adapters in the programs.
- **`async-trait` or a boxed future, for a dyn-compatible `Clock`.** A new dependency and an allocation per sleep, while each program names its clock type at compile time anyway. Rejected.
- **The breaker before the budget on every call, as the source had it.** A probe that the budget then refused was never made. Rejected.
- **The budget before the breaker on later calls, as revision 1 had it.** A retry the open breaker then refused had already spent its allowance, which matters once every call of an instance shares one budget. Rejected for one step that asks the breaker without a transition first.
- **A state borrowed by one run at a time, with no counter, as revision 1 had it.** Against a dead peer, 1,000 callers in one minute with a state each make 7,000 calls. Even one state kept across runs restarts the backoff at every run, so one caller that restarts after each error makes about 1,460 calls an hour, and the 1,000 callers make 712. Revision 2's shared state with its counter gives 69 and 24 (the revision 2 bench). Rejected.
- **A lock the caller holds over `run`.** It serialises every call of the instance through each backoff sleep, and a `std` guard held across an `.await` makes the future not `Send`. Rejected for the lock inside the state, held only in synchronous steps.
- **One count for the backoff and the give-up checks.** Under a shared counter, concurrent calls during a short outage would each start past `max_attempts` and get no retry at all, and `max_attempts` would no longer mean what #282 R7 says. Rejected for two counts.
- **Persisting the budget and the breaker with the counter.** Both hold `Monotonic` instants, which two processes never compare. Rejected; a restarted process starts with an empty budget and a closed breaker, and the counter keeps its backoff.
- **A drop guard in `run` that records an abandoned probe as a failure.** `Drop` would have to take the lock and read the clock, and it never runs for a future that is forgotten or no longer polled. Rejected for the probe deadline, which covers all three.
- **`Fail` that leaves the breaker and the counter alone.** The breaker would never see a failure no retry fixes, and a half-open breaker whose probe ended in `Fail` would need another exit. Rejected for `Fail` counting, with a peer's refusal of one request returned as `Done`.
- **`RetryError` as `#[non_exhaustive]`.** Each caller maps every variant to its own code, so a wildcard arm would map a variant added later with no decision. Rejected.

## Drawbacks
- The runner changes shape when RFC 0002 adds case kinds and `NotApplicable`. `#[non_exhaustive]` keeps that from breaking callers outside the kit, but it is still a change inside it.
- `Clock` is not dyn-compatible, so every caller is generic over its clock.
- The Clock suite drives futures with `block_on`, so an OS clock runs it with a test timer that blocks, not with its runtime's timer.
- Every call of an instance takes the state's lock two or three times. Each hold is short and never spans an `.await`, but a busy instance contends for it.
- The counter spans runs, so after an outage an instance notices recovery only at its next probe, up to the table's cap after the last failure. design/22 section 2.7 asks for this.
- A probe that never reports holds every other call of its instance for up to the call timeout.
- An operation has to sort a peer's refusals into `Done` and its failures into `Fail`. A wrong sort lets one caller's refused requests open the breaker every caller shares.
- Readers find the slice-0 surface of `grdr-ports` in two RFCs.

## Unresolved questions
1. **#1850's signatures.** The give-up reason's name (`GiveUp` here; #1850 question 5) and the seven uses section 8 lists for #1850 are #1850's to state. This RFC can be decided first: #1850's AC-3 holds its types to the uses here, and a difference is settled by an amendment of this RFC, or by #1850's RFC while it is in review, naming both.
2. **A failed draw from the system generator.** `run` follows #1850's decision on `Entropy::fill` (lead-core, #1850 comment 7075943583). What each option does here:
   - Option 1, a fallible `fill`, with `RetryPolicy::next` turning a failed draw into a give-up with a reason of its own and the step's ceiling, with no jitter, as its `backoff`: `run` times the breaker by that ceiling and returns `GaveUp { reason, .. }`. `RetryError` does not change.
   - Option 1, with `next` returning the entropy error instead: `run` needs a new `RetryError` variant, by amendment of this RFC, and each caller maps it (R6).
   - Option 2, an infallible `fill` over a generator whose failure the adapter latches: `next` and `RetryError` do not change, and #1850 states how the adapter keeps section 6's rule that it never returns bytes it did not draw.

   This RFC prefers the first form of option 1. Its decision waits on #1850 only if #1850 chooses the second.

## Review
Review happens on #1924. It calls for:
- the nine persona council seats, once;
- `eval-architecture`, the `[kinds] rfc` row of `.claude/risk-tiers.toml`;
- `eval-api`, the `public_api_change` row, because this RFC states the public API of three public crates;
- `eval-security` and, from round 2, `eval-adversarial`, because #1924 is `tier:high` (the session's ruling, comment 7076117194).

At least one evaluator runs on the other model from the one in the metadata block (D-63, owner instruction 7). The RFC changes no trust-core path. It is decided after the first round in which no evaluator reports a blocker or a major (#1828, comment 7074036273).

Every seat comment and every evaluator verdict names the blobs it read, as full 40-character ids, on fixed lines (RFC 0001, "Review binds the decision"; #1798):
- `RFC file:` `git rev-parse <commit>:rfcs/0008-clock-entropy-and-the-retry-executor.md`, with the commit it read.
- `Proposed text: none`. This RFC decides no pinned path of `rfcs/pins.toml`, so it adds no decision line and commits no evidence.
- `Base:` the spine pin in force, `a80859235e7a2a4444648d6fa8d389d78dde6be9`, SHA-256 `8f6ea876777c0121ecec068c0bc4cef45932be45c1c2aff4140712db1e06628d`.

The decision rests on an `eval-architecture` pass that names the RFC file blob it decides, with no fail by an evaluator of this review on that blob. The file the decision commits may differ from that blob only in `State:`, `Decision record:`, link lines under this section and the `Decision` section (RFC 0001). Verdicts and seat comments are linked below, one per line.

Round 1, on blob `4c59ecba87713e0ff06b3a8b89351fe0f7fc433f`:
- eval-architecture, pass: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7075820992
- eval-api, pass: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7075849304
- eval-security, fail: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7076101630
- the session's rulings for revision 2: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7076117194

## Decision
None yet.
