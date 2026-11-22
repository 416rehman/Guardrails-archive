RFC: 0008
Title: Clock, Entropy, Monotonic and the retry executor: the first surface of grdr-ports and grdr-ports-testkit
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #1924
Spine: D-05, D-15, D-60, D-61, P1, P5, P6, P8, P9, P14, P15, P17 (no spine text changes)
Surfaces: the public crates `grdr-ports` (modules `clock`, `entropy` and `retry`) and `grdr-ports-testkit` (`ManualClock`, `ClockError`, `SeededEntropy`, `block_on`, `Stalled`, the conformance runner and the Clock suite), and the `grdr-model` type `Monotonic`. As proposals: two rows of `surfaces.toml`; in `architecture.toml`, two third-party allow-lists, a per-target closure rule, the implementors of `Clock` and `Entropy` in ARCH-003's reader entries, four ARCH-017 exemption entries and one ARCH-019 exemption; two sentences of design/03 section 10 and design/22 section 2.7; five security requirements of design/02. No third-party dependency, same-layer edge, wire format or Cedar schema changes
Decision record: none yet

To comment, write on issue #1924 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This RFC takes sections 3 and 4 of RFC 0002 (#1688) at blob `5227384311da574174149f1a23958502ff213877`, with the parts of that RFC they rest on. Section 1 lists where it decides otherwise than that text. This is revision 3. The disposition of every finding of rounds 1 and 2 is a comment on #1924.

## Summary
Slice 0 adds the first public items to `grdr-ports` and `grdr-ports-testkit`: the `Clock` and `Entropy` ports, the `grdr-model` instant type `Monotonic`, the one retry executor `grdr_ports::retry::run` and the `RetryState` it works on, their deterministic reference adapters (`ManualClock`, `SeededEntropy` and `block_on`), and the conformance runner that every later port suite extends. Layers 0 and 1 take `now` and `entropy` as arguments and do no I/O, and only the programs' OS adapters read a system clock or the system generator. `run` reads every bound from a `limits.toml` retry table through RFC 0007's `RetryLimits`.

One `RetryState` serves every call of one port instance. It owns its policy, its clock and its entropy, and holds the budget, the breaker and the attempt counter of design/22 section 2.7. Operation classes of one origin share its breaker and budget and keep their own counters. A failure counts against the peer only when the peer served no one else meanwhile, so one principal's failing requests do not open the breaker for the others. A caller passes its deadline, every abandoned run is counted, and an abandoned probe frees its slot at once. Against a dead peer the instance makes about one call per backoff.

Nothing here names a tenant context, a tenant witness, the seal, the mint authority, a fence or a storage port; those stay in RFC 0002, which amends this RFC's runner for its storage suites. Both crates enter `surfaces.toml` as `experimental`.

## Motivation
#281 (Clock, Entropy, the reference adapters and the runner) and #283 (`retry::run`) are the first code in both crates, and the first runnable path needs them (#645, comment 7074036495): the daemon links `grdr-ports` for `Clock`, `Entropy` and `retry::run`. RFC 0002 sections 3 and 4 stated this surface. They share no mechanism with that RFC's tenant contexts, seal, mint authority or fences, which are what RFC 0002's review is about. A public crate changes only by RFC (D-61; design/30 section 3), and `experimental` sets the break rules, not the route (the ruling on #1535). If nothing changes, #281 and #283 wait on a tenant boundary they do not use.

Round 1 showed that the source's retry state left the per-instance state of design/22 section 2.7 and design/20 with nowhere to live. Round 2 showed that a shared state needs rules for the callers that share it: those that cancel, those whose requests fail for their own reasons, those that pass a hint, and those that bring their own clock (#1924, comments 7076704404 and 7076812230). Revision 3 states them here, before #283 builds `run`.

## Design

### 1. Scope and the split from RFC 0002
This RFC states RFC 0002 sections 3 and 4, and the parts of RFC 0002's Rules 1, 2, 7, 8 and 12 and sections 5, 12 and 14 that bear on them. RFC 0002 keeps everything else. Its revision 10 removes sections 3 and 4, points here, and amends section 5's runner (section 8).

The rules of section 2 and the failure modes of section 6 gather what RFC 0002, #281 and #283 already say. Otherwise the text follows the source, except in nine places:
1. The runner (section 5) is generic over its subject. The source bound it to a storage `Fixture`, so the Clock suite, which is generic over `A: Clock`, could not run on it. Its types are `#[non_exhaustive]` or have private fields, so RFC 0002 adds case kinds, fixtures, stop points, induced faults and the `NotApplicable` outcome by amendment.
2. "The RFC of #1710" becomes #1850 for the `grdr-model` retry types and RFC 0007 for `RetryLimits`, as RFC 0007 section 7 asks.
3. `Monotonic` gains `from_nanos` and its derives. Without a constructor, neither an OS clock nor a test can make the instant `ManualClock::new` takes, and `monotonic() >= d` needs the order.
4. Before each call, `run` checks the breaker, then the budget, then takes the permit, in one step under the state's lock. A refused call spends nothing, and every permit, a probe included, is followed by a call.
5. One `RetryState` serves every call of one port instance (R9). It owns its policy, clock and entropy, holds the budget, the breaker and design/22's attempt counter, and lets classes of one origin share its breaker and budget. The source let one run at a time borrow a state with no counter, so a dead peer saw about one call per base delay.
6. A failure counts against the peer only if the peer served no call on the breaker while it was in flight, and no other recent caller was last served (section 4). The source counted every failure, so one principal's slow requests opened the breaker for every principal.
7. `run` takes the caller's deadline, and an attempt it cuts short counts as a timeout. The source took none, so callers that cancel before the call timeout kept the breaker closed against a peer that hangs.
8. A probe has a deadline, an abandoned probe frees its slot at once, and the key whose probe ended without success waits one call timeout before it may take the next. Under #282 R9 a dropped probe held the breaker half-open for good.
9. The breaker opens for the smaller of the step's delay and the counter's ceiling, and a breaker shared by classes for at most the shortest cap among them. The source timed it by the delay alone, so a peer's hint set how long every caller was refused.

The split needs items 1 and 2. Items 3 to 9 each fix a defect of the source that would stop #281 or #283, or leave a peer or its callers unprotected. Where the source is silent this RFC states that `start` is the call's own start; that a deadline past the maximum instant is the maximum instant, as #282 has it for the breaker; that the runner passes one seeded entropy to its cases in turn; that `RetryError` is exhaustive; that each call and each failed attempt reads the clock once; that a peer's refusal of one request is `Done`, not `Fail`; the late reports on an open breaker; the derives of every public type; how `to_toml` writes a string; and the values of the Clock suite's case parameters.

### 2. Rules
- R1. **Dependencies.** `grdr-ports` depends on `grdr-model` and `grdr-schema` and on no other crate, third-party crates included. The privileged daemon links it, so whatever it links is in the daemon's closure. `grdr-ports-testkit` depends on `grdr-ports`, through the listed same-layer edge, on layer 0 and 1 crates of the workspace, and on no third-party crate; RFC 0002 adds the Arrow crates for its Events reference adapter. It is never in the normal-dependency closure of a layer 4 program, resolved with all of that program's features for each target triple the release ships. A program's `Clock` is `grdr-os-clock`'s and its `Entropy` is `grdr-crypto`'s `OsRandom`, the system generator (#1927 R11; design/03 ARCH-003). So neither `ManualClock`, which whoever holds it can move, nor `SeededEntropy`, whose every later output one output reveals, reaches product code.
- R2. **Async shape.** `Clock` has `Send + Sync` as supertraits. `sleep_until` is declared as returning `impl Future<Output = ()> + Send`, which an implementation may write as an `async fn`. There is no `async-trait`, no boxed future and no `futures` crate, so `Clock` is not dyn-compatible and a caller is generic over `C: Clock`. `Entropy` is synchronous and stays dyn-compatible, because `Engine::step` takes `&mut dyn Entropy` (design/03 section 3). `RetryState<C, R, K>` is `Send + Sync` when `R: Send` and `K: Send`, so the future of `run` is `Send` while it borrows a shared state. A WebAssembly host passes `now` and an `Entropy` to the engine as values and implements no `Clock`.
- R3. **Open traits, confined implementations.** `Clock` and `Entropy` are not sealed, so a program can implement them over its operating system and a test over a script. Outside test code they are implemented only in the crates ARCH-003's reader entries name: `grdr-os-clock`, the `random` module of `grdr-crypto`, and `grdr-ports-testkit`, which R1 keeps out of every program (section 7). RFC 0002's seal covers its storage ports only.
- R4. **Layers 0 and 1.** Layers 0 and 1 hold no `Clock`, read no clock or randomness source and do no I/O (spine section 5; D-05). A layer 1 function that needs time takes `now: Timestamp` or a `Monotonic` as an argument, and one that needs randomness takes an `Entropy`, as `Engine::step` does. `Monotonic` and `Entropy` live in `grdr-model`, and `Monotonic` is a value that reads no clock. `Clock` lives in layer 2, so no layer 0 or 1 crate can name it (ARCH-001). Above layer 1, design/03's ARCH-003 makes `grdr-os-clock` the only crate that calls a system clock and the `random` module of `grdr-crypto` the only reader of the system generator, so nothing in `grdr-ports` or `grdr-ports-testkit` reads either (design/03 section 10, Time and Randomness).
- R5. **Bounds are parameters.** Every bound `run` applies comes from the `RetryPolicy` of the state's class: attempts, elapsed time, delays, call timeout, budget, breaker, probe deadline and the one call timeout a barred key waits. The window in which a caller counts as recent is the policy's budget window. Product code builds a policy only with `RetryPolicy::from_limits`, from a `[retry.<name>]` table of `limits.toml` or a narrowing of one (RFC 0007 sections 5 and 6; #1850). `block_on`'s poll bound is an argument. No type here holds a tunable bound (ARCH-019). The Clock suite's case parameters (section 3) are part of each case's definition, not bounds the product applies. They are named constants in one file, `crates/grdr-ports-testkit/src/clock/params.rs`, which ARCH-019 exempts by its full path, and a change to one is a new kit version and an amendment (section 8).
- R6. **Errors.** `RetryError<E>` has no code. Its caller maps every variant to a code of the subsystem that failed, and the caller's rule class decides what the failure means (D-15). It is exhaustive, so a variant added by amendment fails every caller's build until the caller maps it. `ShareError` has no code either: the composition root that calls `for_class` maps it. The kit's errors, `ClockError` and `Stalled`, have no code and hold no free text. All four are entries of the ARCH-017 exemption list in `architecture.toml`, each with its reason, so the lint reads data and special-cases no name (section 8). Each implements `LogSafe` (#1850): `RetryError<E>` where `E` does, with the `Monotonic` and the give-up reason it carries. No type here holds a person-facing string.
- R7. **Data classes and assurance.** `Monotonic`, `Timestamp`, attempt counts, the attempt counter, delays, deadlines, the breaker's state, the abandoned count, seeds, reports and the kit's errors are `structural` (P8). A caller key (R9) is held in memory only, for at most three callers, and is never logged, persisted or returned. Entropy output is never logged or stored. `run` never logs `E`, which keeps the class its own type declares. Assurance effect: none; no action class changes `visibility`, `control`, `on_failure` or `tamper` (P1).
- R8. **Scale.** `run` adds no request of its own (P15). One call makes at most `free_retries_ceiling + 1` retries in a budget window, as RFC 0007 section 5 bounds it. Every call of one port instance shares one state (R9), so once its breaker has opened, the instance as a whole reaches a peer that fails every call once per open period. The attempt counter keeps growing across runs up to the table's cap. With design/22 section 2.7's two uplink classes on one state (control at a 120 s cap, data at 15 minutes) and a breaker that opens after 5 failures, one device against a dead origin makes about 66 to 70 calls an hour. Counting attempts per run instead made about 1,460, and two separate states make about 85. At ten million devices that is about 190,000 requests a second instead of about 4 million (the revision 3 bench, posted on #1924). Callers that pass their deadline get the same bound against a peer that hangs (E2 in section 7).
- R9. **One state per port instance.** A `RetryState` belongs to one port instance and one policy, and every call of that instance, from any task, uses it: the adapter instance of a server port (design/20, "Stability"), or one origin of the uplink (design/22 section 2.7). Another operation class of the same origin is a state built by `for_class`. It shares the clock, entropy, budget and breaker, and keeps its own policy and attempt counter, so design/22's scopes hold: a breaker per origin, a budget per uplink, and a counter and caps per class. A state is built with its instance and lives as long as it, never per call. It keeps no count or history per principal (P8; RFC 0007 section 7). The only per-caller data it holds is the caller key of the two most recent distinct callers and of one barred caller (section 4). `K` is the call's caller key: the organisation for a port that serves many, and `()` for one that serves one principal, never a person's id.
- R10. **Derives.** Every public type here implements `Debug`, and each derives what sections 3 to 5 write beside it, so a test can unwrap a kit result and compare an error. `RetryState` and `ManualClock` are not `Clone`, because a copy would split one instance's state, or one test's time, in two. `RetryState`'s `Debug` prints no entropy, clock or key. `Outcome` is not `Copy`, so RFC 0002's `NotApplicable(Fault)` can join it.
- R11. **The caller's deadline.** A caller whose request has a deadline passes it to `run`, which never calls past it. An attempt the deadline cuts short counts as a timed-out attempt (section 4), so a caller cannot keep the breaker closed by giving up early. A caller that drops its run instead is counted in `abandoned()`.

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

Suite `clock::suite()`, for any `A: Clock`, has three cases, in this order, with the parameters of `params.rs` (R5):
- `monotonic_never_decreases`: 1,000 reads of `monotonic()`, each at or after the one before.
- `sleep_reaches_deadline`: `d` is `monotonic()` plus 10 ms; `block_on(sleep_until(d), 1_000)` completes, and `monotonic() >= d` after it.
- `past_deadline_first_poll`: `d` is `monotonic()`; `block_on(sleep_until(d), 1)` completes.

Each case drives its future with `block_on`, so a clock runs the suite when its sleep completes by being polled. `ManualClock`'s does. An OS clock whose sleep waits on its runtime's timer runs the suite with a test timer that blocks the thread and is ready on its first poll: #1927's `OsClock<T: Timer>` takes its timer as a parameter for this, so the suite runs it as written (lead-core, #1924 comment 7075943320). The 10 ms offset keeps that run short. Callers of `Clock`: every target, the daemon, `retry::run`.

### 4. Retry executor (#283)
```rust
// grdr_ports::retry
pub async fn run<T, E, C, R, K, F, Fut>(
    state: &RetryState<C, R, K>, key: K, deadline: Option<Monotonic>, op: F,
) -> Result<T, RetryError<E>>
where
    C: Clock, R: Entropy + Send, K: PartialEq + Clone + Send,
    F: FnMut() -> Fut + Send, Fut: Future<Output = Attempt<T, E>> + Send,
    T: Send, E: Send;

pub struct RetryState<C, R, K = ()> {
    /* private: the class's RetryPolicy; shared by the classes of one state: the clock, the
       entropy and, behind one lock, the RetryBudget, the Breaker, each class's AttemptCounter,
       the abandoned count and the caller record */
}
impl<C, R, K> RetryState<C, R, K> {
    pub fn new(policy: RetryPolicy, clock: Arc<C>, entropy: R) -> RetryState<C, R, K>;
    pub fn for_class(&self, policy: RetryPolicy) -> Result<RetryState<C, R, K>, ShareError>;
    pub fn resume(self, counter: AttemptCounter) -> RetryState<C, R, K>;
    pub fn policy(&self) -> &RetryPolicy;
    pub fn breaker(&self) -> Breaker;
    pub fn attempt_counter(&self) -> AttemptCounter;
    pub fn abandoned(&self) -> u64;
}
// RetryState<C, R, K> implements Debug for every C, R and K.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ShareError { pub field: RetryField }
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

`RetryPolicy`, `RetryStep`, `RetryBudget`, `Breaker`, `AttemptCounter` and the give-up reason `GiveUp` are `grdr-model` types that #282 builds and #1850 states (RFC 0007 section 1). `RetryField` is RFC 0007's. Section 8 lists what this section needs of #1850. `RetryPolicy::from_limits` reads RFC 0007's `RetryLimits`.

The state:
- `RetryState::new(policy, clock, entropy)` builds the state of one port instance (R9). It owns its policy, so a state never runs under a policy it was not built from. It also owns its clock and its entropy, so no caller can bring a skewed clock or an entropy that returns zeros into a state other callers share. `run` borrows it shared, so any number of concurrent calls use one state. It is `Send + Sync` and not `Clone`.
- `for_class(policy)` builds another operation class of the same instance. It shares the clock, entropy, budget and breaker, and keeps its own policy and attempt counter. It returns `ShareError { field }` if the policy's budget fields or `breaker_failures` differ from the state's, since one budget and one breaker cannot follow two tables. The uplink retries one origin (design/22 section 2.1), so its control and data classes are classes of one state.
- The budget, the breaker, the counters, the abandoned count and the caller record sit behind one `std::sync::Mutex`. `run` holds the lock only while it reads or updates them, never across an `.await` and never while the operation runs. The draw from the state's entropy happens under it. A poisoned lock is taken back with `PoisonError::into_inner`, because no step that holds it runs caller code or a panic path, and each step leaves the state whole. The state reads no clock except its own, and every instant it records is one `run` read from that clock.
- The attempt counter is design/22 section 2.7's: the failed attempts of the class since its last success, across every run and every caller. Each failed attempt that counts against the peer adds one, saturating. Only the class's `Done` sets it to 0. `run` passes its value before the failure being recorded to `RetryPolicy::next` as the `AttemptCounter` whose ceiling the delay is drawn under, and passes the run's own retries so far, a `u32`, for the give-up checks. So a new run continues the backoff the class reached, and a table's `max_attempts` and `max_elapsed` still bound one call. The two counts have different types, so they cannot be swapped.
- `attempt_counter()` reads the counter, and `resume(counter)` sets it on a state just built, so a restarted program continues from it. design/22 section 2.7 keeps the uplink's counter in the daemon's state directory; #1238 (22-5, `uplink-reconnect`) writes it there and reads it back, and needs no port from this RFC. Only the counter persists. A new process starts with an empty budget and a closed breaker, because both hold `Monotonic` instants. design/20 asks nothing more of its policies, so theirs live in memory.
- `breaker()` returns a copy of the breaker's state, and `abandoned()` the number of runs dropped before they returned. A target shows an open breaker and the abandoned count in its health and on the operator plane (design/20, "Stability" and the operator plane's health list). Neither read changes anything.
- The caller record holds, for the two most recent distinct caller keys, when each was last seen and whether its latest outcome was a success, and at most one barred key with the instant its bar ends.

A call:
- If the caller's deadline has passed, the run returns `Timeout` and makes no call.
- Before each call `run` reads its clock once. Under one hold of the lock it records the caller as seen, then asks the breaker, without a transition, whether a permit at that instant would be refused. If so, the run ends with `BreakerOpen { until, last }` and nothing else is recorded. If the permit would be a probe, the caller's key is barred, and another key has called within the budget window, the run ends with `BreakerOpen` with `until` at the bar's end. Otherwise it records a request in the budget for the first call, or spends from the budget for a later one. A budget refusal ends the run with `BudgetExhausted` with the breaker untouched. Only then does it take the breaker's permit, which the checks have granted. So a refused call spends nothing, and every permit, a probe included, is followed by a call.
- That instant is the call's `start`. The call races the operation against `clock.sleep_until(min(start + timeout, deadline))`, where `timeout` is the class's call timeout. Each poll polls the operation first, so an operation ready on the same poll wins. If the sleep wins, the operation is dropped and the attempt counts as timed out, retryable with no hint. When the caller's deadline ended it, or when no retry follows, the run returns `Timeout`.
- On `Done(t)` the breaker records a success at the instant of the report, the class's counter goes to 0, the caller is recorded as served, and `run` returns `Ok(t)`. The operation returns `Done` only for an answer it accepts as the peer's own; for the uplink that is a verified response (design/22 section 2.7).
- On `Retry`, `Fail` or a timeout, `run` reads its clock once. That instant is the breaker's record, the start of the sleep and the end of `elapsed`, which runs from the first call's instant. `run` asks the policy once for the next step, with the counter, the run's retries and no hint for `Fail` or a timeout. Then, under the lock, it decides whether the failure counts against the peer.
- A failure counts against the peer unless the peer has evidently served someone else. That is so if a success was recorded on the breaker while the call was in flight. It is also so if another caller key, seen within the budget window, had a success as its latest outcome. A failure that counts makes the breaker record a failure, timed by the step's open time, and adds one to the class's counter. A failure that does not count records nothing against the peer, and the run still follows its own step. One principal's requests that fail while others are served therefore never open the breaker those others share, and never grow their backoff. A peer that fails every caller still opens it.
- The breaker opens for the step's `open_for`: the smaller of its delay and the ceiling of the counter, so a hint delays the run's own retry and never the breaker beyond the table's cap. A breaker shared by classes opens for at most the shortest cap among them, so the class with the shortest cap, the uplink's control class, is never held back by a longer one. When the step's delay is no longer than the ceiling, an opened breaker's `until` is the instant this run's next attempt is due.
- `Fail(e)` returns `Failed(e)`. Otherwise the run sleeps until `now + delay` and calls again, or returns `GaveUp`, or `Timeout` if the last attempt timed out. A retry due at or after the caller's deadline is not made, and the run returns `Timeout`.
- `Fail` is a failure of the peer that no retry fixes, such as a certificate the operation refuses, and it counts as `Retry` does. A peer's answer that refuses one request, such as an invalid argument or a missing row, is `Done` with the operation's own error in `T`.

Probes and abandoned runs:
- A probe's deadline is its permit's instant plus the class's call timeout, which is the `timeout_ms` of its `[retry.<name>]` table, at most the `retry-bounds.timeout-ceiling` row (RFC 0007 section 6). Before the deadline every other permit is refused with `until` at it. At or after it, the next permit takes a new probe.
- A live probe can report after its deadline, because the timeout sleep completes at or after it and `run` records the report when it is next polled. A second probe may be in flight by then. Each report then follows #1850's rows for late reports (section 8): a success on `Open` makes the next permit a probe, and a failure on `Open` leaves `until` as it is.
- `run` holds a drop guard. If the future of `run` is dropped before it returns, the guard adds one to `abandoned()`. If the run held the probe, the guard frees the slot at once, so the breaker is `Open` with `until` at the probe's permit instant and the next permit probes. The guard reads no clock and calls no caller code.
- A key whose probe ended without a success is barred from the next probe while another key has called within the budget window. If the key abandoned its probe, the bar lasts until the probe's deadline. If its probe failed and the failure counted, the bar lasts until the new `until` plus one call timeout. If its probe failed and the failure did not count, the slot is freed at once and the bar lasts one call timeout. A probe granted to any key ends the bar. So the next probe goes to another caller, and one caller that abandons or fails probes can neither hold the breaker half-open nor take the probe again first.
- A probe whose future is forgotten or no longer polled runs no guard, and its deadline bounds its hold.
- An ordinary call dropped with its run records no outcome. The budget keeps the request or retry it recorded before the call began, and the drop is counted in `abandoned()`.

Common to all:
- A deadline that would pass the maximum instant is the maximum instant, as the breaker's `until` is (#282).
- The race is written over `core::future::poll_fn`, with no dependency and no runtime. Every variant keeps the attempt count and the last error.
- The future of `run` is `Send` under these bounds. A compile-time test shows it, and so also shows that no lock guard is held across an `.await`.

Callers: every port call site in the targets and the daemon (ARCH-018 forbids any other retry loop), each through the state of its port instance (R9), with its caller key and deadline (R11).

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
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Report { /* private: kit version, adapter, seed, results */ }
impl Report {
    pub fn kit_version(&self) -> &str;
    pub fn adapter(&self) -> &str;
    pub fn seed(&self) -> u64;
    pub fn results(&self) -> &[CaseResult];
    pub fn passed(&self) -> bool;
    pub fn to_toml(&self) -> String;
}
// Case<S> is Clone, Copy and Debug, and Suite<S> is Debug, for every S.
```

Rules of the runner:
- This RFC holds the one definition of `Case`, `Suite`, `Outcome`, `CaseResult`, `Report` and the runner. RFC 0002 (#1688) amends them for the storage suites: `kind` on `Case` and `CaseResult`, `Outcome::NotApplicable(Fault)`, the `Fixture` bound on each storage suite's constructor, and the arming state `run` holds. #281 builds the runner as this RFC states it.
- Only the kit builds a `Suite`, since it has no public constructor, so the cases a subject passes are the kit's own. The report's kit version is the `grdr-ports-testkit` crate version, and a change to any case is a new version. An adapter states the kit version it passed (design/03, extension points).
- `Report`'s fields are private and read through its accessors, so code outside the kit can read a report but cannot build one or edit one it holds. `Case`, `CaseResult` and `Outcome` are `#[non_exhaustive]`, so code outside the kit cannot build them, and a field or variant added by amendment breaks no caller: a match on `Outcome` outside the kit already needs a wildcard arm.
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
| The peer never answers | Each attempt is dropped at its deadline. The run ends with `Timeout` when the policy gives up after a timed-out attempt or the caller's deadline passes, or earlier with `BudgetExhausted` or `BreakerOpen` | The returned error, with the attempt count and the last error |
| The peer fails every call and callers keep starting runs | Once the breaker has opened, the instance reaches the peer once per open period; every other call ends with `BreakerOpen` and makes no call, and the counter's backoff grows across runs up to the table's cap (R8) | `BreakerOpen` to each refused caller; the open breaker in the target's health |
| The peer hangs and callers' deadlines are shorter than the call timeout | Each attempt a deadline cuts short counts as timed out, so the breaker opens and then probes once per open period (R11) | `BreakerOpen`; the open breaker in health |
| A caller drops its run | `abandoned()` adds one, and the call's outcome is not recorded. An abandoned probe frees its slot at once, and its key waits for the probe's deadline before probing again | `abandoned()` in the target's health |
| Callers drop their runs without passing their deadline, against a peer that hangs | The breaker does not open, because no outcome is recorded, and every drop is counted (R11 requires the deadline) | `abandoned()` grows with the calls |
| One principal's requests fail while the peer serves others | Those failures do not count against the peer, so the breaker stays closed and other callers' backoff does not grow | The principal's own errors |
| One principal's requests fail while no other caller has been seen within the budget window | They count, and the breaker may open; a principal that calls less often than once per budget window can then be refused for up to one open period, and while the first keeps failing | `BreakerOpen` to that principal; the open breaker in health. A port with such principals uses a table with a longer budget window |
| A caller abandons or fails each probe it takes | The slot is freed or the breaker reopens, and that caller's key is barred from the next probe while another key calls, so another caller takes it | The breaker closes on the other caller's probe |
| A peer or a proxy sends a hint far beyond the table's cap | The run's own retry honours it or gives up at `max_elapsed`; the breaker opens for at most the counter's ceiling | `GaveUp` to that run; the breaker's `until` |
| A live probe reports after its deadline | A second probe may already be in flight; each report follows the late-report rows of #1850 | The breaker's state |
| A call permitted while the breaker was closed reports after it opened | A success makes the next permit a probe; a failure leaves `until` unchanged | The breaker's state |
| `for_class` is given a table whose budget or breaker fields differ | `ShareError { field }`, naming the first field that differs | The composition root's error |
| The breaker is open | `BreakerOpen { until, last }`; no call is made and the budget is not touched | The returned error |
| The budget is spent | `BudgetExhausted { attempts, last }`; the breaker is not touched | The returned error |
| The operation returns `Fail` | `Failed(e)` after that call; the failure counts as `Retry` does | The returned error |
| The peer refuses one caller's request | The operation returns it as `Done` with its own error, so the breaker and the counter count the peer as up | The caller's error |
| The policy gives up after a `Retry` | `GaveUp { reason, attempts, last }` | The returned error |
| A probe never reports: its future is forgotten or no longer polled | The breaker stays half-open until the probe deadline; the next permit at or after it takes a new probe | `BreakerOpen { until }`, with `until` at the deadline, to calls in between |
| A resumed attempt counter is stale or altered | Any value is a valid counter. The delay stays within the table's cap, so a counter set too high makes each retry wait at most the cap, and one set too low costs at most the retries the budget allows before the breaker opens | The delays of the next run; `ManualClock::sleeps()` under test |
| The state's lock is poisoned | Taken back with `into_inner`; no step that holds the lock runs caller code or a panic path, so the state is whole | Nothing |
| The wall clock jumps during a run | No effect: elapsed time and deadlines use `monotonic()` only | #283's case with `jump_wall` between attempts |
| The host suspends during a run | A deadline that passed while the host was suspended has passed on waking, so the next attempt or the timeout comes within `clock.recheck` of waking (#1927 R8) | #1927's sleep model; #1936 on real cells |
| The system generator fails | The programs' `Entropy` never returns bytes it did not draw from the generator: zeroed or repeated bytes would make every full-jitter delay 0, and every key and nonce predictable. How the failure reaches `run` is #1850's; question 2 gives what each option does to `RetryError` | #1850's error, or the give-up reason `run` returns |
| A caller meets a `RetryError` | It maps the variant to its own subsystem's code, and its rule class decides the outcome (D-15) | The caller's error and code |

Nothing here fails open: no `RetryError` variant reads as success, a variant a caller does not map fails its build, and none of #1850's options for a failed draw returns bytes that were not drawn. A failure that does not count against the peer is still returned to its caller.

### 7. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| R1 | A third-party allow-list per crate in `architecture.toml`, empty for both crates, read by the archlint graph rules. A check that `grdr-ports-testkit` is in no layer 4 program's normal closure, resolved with all of that program's features and once per target triple of the release's support matrix (design/24 section 9) with `cargo metadata --filter-platform`. Negative fixtures: a program with the kit as a normal dependency, one that reaches it through a layer 3 crate, one that reaches it only under one of its features, and one that reaches it only under a `[target.'cfg(..)'.dependencies]` table for a target other than the host; each fails | #1580 reads the data and adds the fixtures, a constraint posted there on acceptance; the entries are the protected change filed on acceptance |
| R1, R3 and R4, the readers and implementors | design/03 ARCH-003: outside `grdr-os-clock` and the `random` module of `grdr-crypto`, the architecture lint refuses a system clock or generator call, a `clippy::disallowed_methods` allow over one, and a direct `getrandom` or `rand` dependency. Its reader entries in `architecture.toml` also name where `impl Clock` and `impl Entropy` may appear outside test code: those two readers and `grdr-ports-testkit`. A fixture crate that implements `Entropy` with its own generator fails | #1582, its ARCH-003 part; the entries are #1933's and the protected change filed on acceptance |
| R2 | The `+ Send` bounds, checked by the compiler; compile-time tests that `run`'s future is `Send`, that `RetryState` is `Send + Sync`, and that two runs on one `&RetryState` build and run | #283 |
| R4, layers 0 and 1 | ARCH-001 (no layer 0 or 1 crate depends on `grdr-ports`); ARCH-003's disallowed methods and banned crates; `cargo build -p grdr-model --target wasm32-unknown-unknown` | #1580; #1582; #281 AC-6 |
| R5 | ARCH-019; policies built only through `RetryPolicy::from_limits`; the Clock suite's parameters as named constants at section 3's values in `params.rs`, exempted from ARCH-019 by that one path | #1582; #279; #282; #281 |
| R6 | ARCH-017, reading the four exemption entries; for the exhaustive `RetryError`, the compiler on each caller's match, which fails until a new variant is mapped | #1582; the protected change filed on acceptance; #283 |
| R9 and R11 | `run` borrows a `Sync` state and `RetryState` is not `Clone`. `crates/grdr-ports/AGENTS.md` says under "Do not" that a `RetryState` is built with its port instance, never per call, and that a caller with a deadline passes it. `eval-architecture` checks both on every pull request that adds a call to `retry::run` or `RetryState::new`. No scan holds this: a constructor that builds its state and retries its first connection through `run` is correct, and a rule on the call sites would refuse it | The compiler; #283 (the AGENTS.md line); the `eval-architecture` line, filed on acceptance for lead-agent-kit; review on that event |
| R10 | The compiler on #281's and #283's tests, which unwrap the kit's results, return `Result<(), ClockError>` and format each public type with `{:?}`; `cargo public-api` lists the impls | #281; #283 |
| One retry loop | ARCH-018 | #1582 |
| One randomness trait (P17) | `pub use grdr_model::Entropy`; `eval-architecture` refuses, on every pull request that adds a trait in layers 0 to 2 with a `now`, `monotonic`, `sleep` or `fill` method, a second clock or randomness trait | #281; the `eval-architecture` line, filed on acceptance for lead-agent-kit |
| Section 3 and the runner | `clock::suite()` on `ManualClock` with the `jump_wall` case; a fixture clock whose monotonic value decreases, which fails exactly that case; the reference `splitmix64.c` output for seed 0; a future `Pending` by construction under `block_on`; `Monotonic` at 0 and at the largest instant. Compile-fail doctests outside the kit: a struct expression of `Report` (private fields), of `CaseResult` or of `Case`, and a match on `Outcome` with no wildcard arm, each fail. `to_toml` of a report whose adapter name holds a quotation mark, a backslash and a line break has one `adapter` line and no other key | #281 AC-1 to AC-5, and its doctests |
| `run`'s semantics | Under `ManualClock` and `SeededEntropy`: each recorded deadline against `RetryPolicy::next` called directly with the same seed and counts; the breaker's `until` equal to the next sleep's deadline when there is no hint; the timeout drop; the breaker and budget transitions, counted by a fixture operation; a run whose budget refuses a later call while the breaker would grant a probe, after which the next run still gets its probe; and a retry the open breaker refuses, which spends nothing, so the retry due at `until` makes the probe | #283 AC-1 to AC-3 |
| The shared state (R8, R9) | Against a reference model of section 4 over #282's types, written in the test from this text, under a test clock whose sleep waits until the test moves it. One caller that starts a new run after each error against a peer that fails every call: its calls and gaps equal the model's. The uplink's two classes on one state, each restarting after errors for an hour: calls equal the model's, and the control class is never refused for longer than its cap. Many runs on one state; `resume` continuing the backoff; a success resetting its class's counter; `for_class` returning `ShareError` for each differing field | #283 |
| Cancellation and deadlines (R11) | The E2 case against the same model: a peer that hangs, 100 callers a second for a minute, a 1 s timeout. Callers that pass a deadline of 0.5 s make no more calls than callers with none (72 and 118 in the bench), against about 6,000 when they drop at 0.5 s without one, and each of those drops is counted in `abandoned()`. A run whose deadline passes before a retry is due returns `Timeout` without the call | #283 |
| Which failures count | The E3 case: a peer that answers one principal in 20 ms and another's requests in 30 s, with a 5 s timeout and the second sending bursts of 5 and of 8. The first is refused in under 1% of calls at 50, 500 and 0.2 calls a second. Also a principal's failures during another's blip, which do not count, and failures from every caller, which open the breaker | #283 |
| Probes | The E4b case: after one opening, a caller that drops each run 1 ms after its call starts, at 1,000 a second, and another caller at 50 a second; the breaker closes within a fraction of a second of its first `until`. A probe dropped after one poll frees its slot at once, its key is refused until the old deadline while another key calls, and another key probes. The probe cases held back under D-62, given to #283's implementer through the session | #282 (the deadline, `release` and the late-report rows); #283 |
| The hint (R5) | A step whose hint is `u64::MAX` ms opens the breaker for at most the counter's ceiling, and a caller after that ceiling reaches a healthy peer | #282 (the step's `open_for`); #283 |
| The `Done` and `Fail` sort | One case in each storage suite: an invalid argument and a missing row, over two calls on one instance, leave `attempt_counter()` and `breaker()` unchanged, and the second call shows the counter continuing | RFC 0002's amendment of the runner, and the storage suite items |
| Health | `RetryState::breaker()` and `abandoned()`; each target shows an open breaker and the abandoned count in its health | #283 (the reads); #1584 and each target's health item (the display) |
| Suspended time counts | #1927 proves the sleep against scripted boot-time readings and checks each system's boot-time read on the hosted runners; real suspend and wake on each system's matrix cell | #1927; #1936 on real cells |
| Stability | The `surfaces.toml` rows, `rfc-required`, `cargo public-api`, `cargo semver-checks` | The protected change filed on acceptance; #1741 |

### 8. Stability, and what each item changes
Stability:
- Both crates enter `surfaces.toml` as `experimental` (D-60; ADR-0020; design/03 section 7: every surface starts there), through the protected-change item filed on acceptance. Each gets one row of the kind `surfaces.toml` has when the item lands; in RFC 0005 R6.1's `[[crate]]` kind that is `name`, `class = "experimental"` and `rfc = "0008"`. RFC 0002 amends this RFC for both crates and keeps the rows. `Monotonic` takes the class of the `grdr-model` row (#1850), because a class belongs to a crate (RFC 0007 section 11).
- `experimental` allows a break in any release, and every change still goes by RFC. A signature, a semantic, a variant or a suite case is an amendment: a new RFC that names RFC 0008, because an accepted RFC never returns to `Review` (RFC 0001, "RFC states"). Its pull requests name that RFC for `rfc-required`. `cargo public-api` and `cargo semver-checks` run against the class once the rows exist, and the release notes list every amendment, as `breaking` when it breaks.

Proposed for `architecture.toml`, in the protected change filed on acceptance:
- an empty third-party allow-list for each crate, with the rule that `grdr-ports-testkit` is in no layer 4 program's normal closure under any of that program's features, for each target triple of the support matrix;
- in ARCH-003's reader entries, the crates and modules where `impl Clock` and `impl Entropy` may appear outside test code: `grdr-os-clock`, `grdr-crypto`'s `random` module and `grdr-ports-testkit`;
- ARCH-017 exemption entries for `grdr_ports::retry::RetryError` and `grdr_ports::retry::ShareError` (each caller maps every variant to its own code), and for `grdr_ports_testkit::clock::ClockError` and `grdr_ports_testkit::Stalled` (test kit errors, never returned by product code);
- an ARCH-019 exemption for `crates/grdr-ports-testkit/src/clock/params.rs` by that full workspace path (#1582 comment 7075274622), because its constants define conformance cases and bound nothing the product does.

The entries take the form of the lists in force when the item lands (RFC 0002 section 14; RFC 0005 R4.1).

Proposed for the design documents, each filed on acceptance as the chief architect's design item:
- **design/03 section 10 (Retries) and design/22 section 2.7, the jitter.** The full jitter is drawn from the program's system generator (R1), not "seeded by device id, boot id and attempt". Independent draws from each device's generator keep devices out of step, which is what the seed was for. A seed built from those three values would let anyone who knows them predict a device's retries.
- **design/22 section 2.7, the origin's breaker.** "Each origin has a circuit breaker" gains: "shared by the origin's operation classes, and open for no longer than the shortest of their caps, so the control class keeps its 120 s bound". Without it, the data class's 15-minute backoff times the shared breaker. In the revision 3 bench the control class then went 2,275 s without a call, against 120 s with the rule. That is also why R8's figure is about 66 to 70 calls an hour per device, not the 51 a model without the rule gave in round 2.
- **design/02 section 3.8.** Five security requirements, from eval-security's wording in rounds 1 and 2 (#1924 comments 7076101630 and 7076812230):
  - One `RetryState` per port instance holds the attempt counter, the budget and the breaker for every call, and classes of one origin share the breaker and budget. A new run continues the counter, only a success resets it, and a program can persist and resume it.
  - A probe stops holding the breaker by its deadline. An abandoned probe frees its slot at once, and no caller chains probe holds.
  - Product code draws randomness only from the system generator. No deterministic `Entropy` is in a program's normal closure, and `Clock` and `Entropy` are implemented only where ARCH-003 names.
  - No one principal's requests open a shared breaker while the peer serves other principals.
  - A run its caller cancels is never silent, and a caller's deadline shorter than the call timeout cannot keep the breaker closed.

  Residual risks for its 3.9: a principal that calls less often than once per budget window; two or more organisations acting together, which can each corroborate the other's failures and take turns at probes; and callers that drop runs without passing their deadline.

What each item changes:
- **#281**: its route and its scope are this RFC: sections 3 and 5 as decided, with any amendment decided before it is worked. R1 gains `from_nanos` and the derives. R2: `Clock: Send + Sync`, and `monotonic` counts suspended time. R4: `ManualClock` is `Sync`. R8 becomes the runner of section 5: a `Suite<S>` only the kit builds, an unbounded `run(&subject, adapter, seed)`, cases that take `&mut SeededEntropy`, a `Failure` that names the kit's check in place of failure text, the seed in the report, a `Report` with private fields and accessors, the `#[non_exhaustive]` types with their compile-fail doctests, and `to_toml`'s escaping. R9 takes the three cases and their parameter file, so the write set gains `crates/grdr-ports-testkit/src/clock/**`. Every public type takes the derives of R10. The `Fixture` traits, case kinds, `NotApplicable`, stop points, `arm`, `reach`, `authority()`, `tenancy()` and the storage how-to page come with RFC 0002's amendment and its items.
- **#283**: its route is this RFC. R1 becomes `run(state: &RetryState<C, R, K>, key, deadline, op)` with the bounds of section 4. `RetryState` owns its policy, clock and entropy and holds the budget, the breaker, the class counters, the abandoned count and the caller record behind one lock, with `new`, `for_class`, `resume`, `policy`, `breaker`, `attempt_counter` and `abandoned`. R3 and R4 take section 4's one-step check. R5 races against the earlier of the call timeout and the caller's deadline. R7 passes the counter and the run's retries to `next` and applies the counting rule. The non-goal "Sharing `RetryState` across tasks" goes, because sharing is the point (R9). Its tests take section 7's cases for R2, `run`'s semantics, the shared state, cancellation and deadlines, which failures count, probes and the hint. The write set gains `crates/grdr-ports/AGENTS.md` for R9's line. AC-4 cites ARCH-018, a scan rule of #1582, not #1580. It needs #1850 decided for the retry types and RFC 0007 for `RetryLimits`. Its lead should split it, for example into the state and the call, then the counting rule and the probe rules.
- **#1850**, with #282, which builds its types. `Monotonic` is this RFC's, and section 4 needs these:
  1. `RetryPolicy::next` takes its entropy as `&mut R` for any `R: Entropy + ?Sized`, because `&mut dyn Entropy` cannot be formed from a generic `R` (rustc E0277).
  2. `next` takes two counts of different types: an `AttemptCounter`, which sets the ceiling (#282 R3 and R4), and the run's retries so far, a `u32`, which the `MaxAttempts` check reads (#282 R7). `AttemptCounter` is a `grdr-model` value with `new(u32)`, `get()` and a saturating `next()`, deriving `Clone`, `Copy`, `Debug`, `Default`, `PartialEq`, `Eq`, `PartialOrd`, `Ord` and `Hash`, and implementing `LogSafe`. #282's AC-3 reference draws the two counts independently, so a swap inside `next` fails it.
  3. Each `RetryStep` carries `open_for`, the smaller of its delay and the ceiling of the counter, so a hint never times the breaker beyond the table's cap. With no hint, `open_for` equals the delay, so #282's vectors hold.
  4. `RetryPolicy` exposes its call timeout, its cap (the exponential cap, or a schedule's last delay), its budget fields and `breaker_failures`, which `run` and `for_class` read.
  5. `Breaker`'s half-open state holds its probe deadline. Before the deadline a permit is refused with `until` at it; at or after it the permit takes a new probe and moves the deadline. This replaces #282 R9's `Refuse { until: now }`.
  6. `Breaker` answers, without a transition, whether a permit at `now` would be refused and until when, so `run` checks it before it spends.
  7. Three more rows for #282 R9 and its AC-4 table. `Open` and a success is `Open` with `until` at the earlier of its `until` and now, so the next permit probes and `Open` is still left only through `HalfOpen`. `Open` and a failure leaves `until` unchanged. `release(probe_until, granted_at)` on a `HalfOpen` holding that deadline is `Open { until: granted_at }`, and on any other state it changes nothing. #282 AC-4's rule that no sequence leaves `Open` except through `HalfOpen` stands.
  8. `RetryPolicy`, `RetryBudget` and `Breaker` are `Send + Sync`, so the future of `run` is `Send`. `RetryPolicy` and `RetryBudget` are `Clone` and `Debug`, since a state owns them and prints its policy. `Breaker` derives `Clone`, `Copy`, `Debug`, `PartialEq` and `Eq`, since `breaker()` returns a copy. The give-up reason derives the same and implements `LogSafe`, so `RetryError<E>` is `LogSafe` where `E` is.
  9. AC-3's use `RetryState::new(&RetryPolicy)` becomes `RetryState::new(policy, clock, entropy)`, with the policy by value.
  10. How a failed draw from the system generator reaches `run` (question 2).

  #282's non-goal "Sharing one budget or breaker across threads: the caller owns the instance" stays true: `RetryState` in `grdr-ports` shares them.
- **#1580**: the four negative fixtures of R1's closure check and the per-target resolution, posted there as a constraint on acceptance.
- **#1582**: ARCH-003 for layers 2 to 4 as design/03 has it, reading the implementors of `Clock` and `Entropy` from its reader entries, with a fixture crate that implements `Entropy` outside them (R1, R3, R4); and ARCH-019's exemption for `params.rs` by its full path.
- **#1933**: ARCH-003's reader entries for `grdr-os-clock` name it as an implementor of `Clock`.
- **#1238** (22-5, `uplink-reconnect`): one `RetryState` for the origin, with the control and data classes built by `for_class` (design/22 section 2.7). Each class's counter is written to the daemon's state directory from `attempt_counter()` and read back through `resume` when the uplink starts. Each call passes its deadline (R11).
- **lead-agent-kit**, an item filed on acceptance: two lines for `.claude/agents/eval-architecture.md`, the review duties of the R9 and R11 row and of the P17 row of section 7.
- **RFC 0002, revision 10 and its successors**: sections 3 and 4 are this RFC's, and its section 5 states its runner additions as an amendment of this RFC. Those are `kind` on `Case` and `CaseResult`, `Outcome::NotApplicable(Fault)`, the `Fixture` bound on each storage suite's constructor, and the arming state the kit holds inside `run` for every suite. Its amendment also carries:
  - `Fault` and `StoreFault` derive `Clone`, `Debug`, `PartialEq` and `Eq`, as `Outcome` needs;
  - each storage suite gets the `Done` and `Fail` sort case of section 7;
  - its adapters build one `RetryState` per port instance with the organisation as the caller key (R9).

  Its Rule 12 barrier, as revision 10 states it, applies to crates that name a capability type or an item of `tenant`, `storage` or `adapter`. The daemon, which links `grdr-ports` only for this RFC's `clock`, `entropy` and `retry`, is outside it.
- **RFC 0007, next revision or decision**: section 1's row for `Monotonic`, and its notes on `Entropy` and on `RetryError` with its ARCH-017 exemption, name this RFC in place of RFC 0002. Section 5's "the caller decides whether a new episode starts" still holds: a new run continues the attempt counter, and only a success resets it (design/22 section 2.7).
- **#1927**: builds the programs' OS `Clock`, `OsClock`, with the suspend rows of sections 6 and 7 and the Windows reader of section 3, and pairs it with `OsRandom` as the programs' `Entropy` (#1927 R11). Each program passes them to `RetryState::new`.

## Surfaces changed
- `grdr-ports` (layer 2, public): modules `clock`, `entropy` (a re-export) and `retry`. Class `experimental`.
- `grdr-ports-testkit` (layer 2, public): `ManualClock`, `ClockError`, `SeededEntropy`, `block_on` and `Stalled` at the root, the conformance runner in `conformance`, and `clock::suite`. Class `experimental`.
- `grdr-model` (layer 1, public): `Monotonic`. Class `experimental`, the crate's.
- As proposals: two `surfaces.toml` rows, and the `architecture.toml` entries of section 8; two sentences of design/03 section 10 and design/22 section 2.7, and five security requirements of design/02 (section 8).
- No spine text, protobuf package, Cedar schema, third-party dependency or same-layer edge changes.

## Alternatives
- **Keep sections 3 and 4 in RFC 0002.** #281 and #283 would wait on a tenant boundary they do not use. Rejected.
- **A runner bound to a storage `Fixture`, as RFC 0002 section 5 had it.** The Clock suite has no store, so it could not run, and #281 would wait on the tenant types the `Fixture` names. Rejected for a runner generic over its subject.
- **Case kinds and `NotApplicable` here.** A crash case needs stop points and `NotApplicable` names a store fault. Declared here, neither would have a case. Rejected; RFC 0002 adds them by amendment.
- **Exhaustive runner types and a `Report` with public fields.** A field or variant RFC 0002 adds would break every caller that builds or matches one, and any holder could clone a report and edit it into a pass. Rejected for `#[non_exhaustive]` and private fields.
- **A `Clock` over `std::time::Instant` in `grdr-ports`.** The standard library does not specify whether `Instant` counts time the host spent suspended, and says the behaviour varies by platform and release (https://doc.rust-lang.org/std/time/struct.Instant.html, read 2026-11-22). A deadline could stay in the future after a sleep, and layer 2 would read a clock. Rejected for OS adapters in the programs.
- **`async-trait` or a boxed future, for a dyn-compatible `Clock`.** A new dependency and an allocation per sleep, while each program names its clock type at compile time anyway. Rejected.
- **The breaker before the budget on every call, as the source had it, or the budget first on later calls, as revision 1 had it.** The first left a probe unmade after a budget refusal; the second spent a retry the open breaker then refused. Rejected for one step that asks the breaker without a transition first.
- **A state borrowed by one run at a time, with no counter, as revision 1 had it.** Against a dead peer, 1,000 callers in one minute with a state each make 7,000 calls, and one caller that restarts after each error makes about 1,460 an hour. Rejected for one shared state per instance.
- **A lock the caller holds over `run`.** It serialises every call of the instance through each backoff sleep, and a `std` guard held across an `.await` makes the future not `Send`. Rejected for the lock inside the state, held only in synchronous steps.
- **The clock and entropy as arguments of each run, as revision 2 had them.** One caller's clock with a distant origin, or an entropy that returns zeros, would time the breaker every other caller shares. Rejected for the state owning both.
- **One count for the backoff and the give-up checks, or two counts of one type.** Under a shared counter, one count would leave concurrent calls with no retry during a short outage. Two `u32`s can be swapped without a type error. Rejected for two counts of two types.
- **Per-principal failure counts that feed the breaker only when failures come from more than one principal.** They need a count per principal, which grows with the organisations an instance serves. They also count a principal's failures that happen to coincide with another's brief failure. Rejected for the two tests of section 4, which need one success counter and two caller entries, and which E3 shows bring other principals' refusals from about 94% to 0%.
- **A breaker per principal.** Against a dead peer every organisation would spend its own failures before its breaker opens, and probe on its own: thousands of calls per backoff instead of one. Rejected.
- **Refusing a call whose policy timeout is longer than the caller's deadline.** Deadlines vary per request, so this would refuse calls rather than bound them. Rejected for `run` taking the deadline.
- **Counting an abandoned attempt as a failure.** An OS network change that cancels the uplink's calls would then open its breaker and block design/22's immediate reconnect. A caller that drops probes would keep the breaker open. Rejected for counting abandoned runs and freeing abandoned probes.
- **Freeing an abandoned probe with no bar on its key.** The same caller could take the freed probe again at once and hold the breaker by dropping probe after probe. Rejected for the bar while another key is calling.
- **A `retry-bounds.hint-ceiling` row.** It would be a new bound to set and keep, while the counter's ceiling already bounds what the policy itself would wait. Rejected for `open_for`, which needs no row and still lets the run honour the hint for its own retry.
- **Timing a breaker shared by classes by the failing class's own delay.** The data class's 15-minute backoff would hold the control class back, and commands with it. Rejected for the shortest cap.
- **A drop guard alone, with no probe deadline.** It never runs for a future that is forgotten or no longer polled. Rejected for both.
- **`Fail` that leaves the breaker and the counter alone.** The breaker would never see a failure no retry fixes. Rejected for `Fail` counting, with a peer's refusal of one request returned as `Done`.
- **`RetryError` as `#[non_exhaustive]`.** Each caller maps every variant to its own code, so a wildcard arm would map a variant added later with no decision. Rejected.

## Drawbacks
- The runner changes shape when RFC 0002 adds case kinds and `NotApplicable`. `#[non_exhaustive]` keeps that from breaking callers outside the kit, but it is still a change inside it.
- `Clock` is not dyn-compatible, so every caller is generic over its clock, and `RetryState` is generic over its clock, entropy and caller key.
- The Clock suite drives futures with `block_on`, so an OS clock runs it with a test timer that blocks, not with its runtime's timer.
- Every call of an instance takes the state's lock two or three times. Each hold is short and never spans an `.await`, but a busy instance contends for it.
- The counting rule, the probe bar and the shortest cap make `run` harder to read than a plain breaker, so its proof rests on the reference-model cases of section 7.
- A principal that calls less often than once per budget window is not protected by the second test. In the bench, a principal calling once every 120 s while another's requests kept failing was refused in about 84% of its calls. Two or more organisations acting together are not protected against either.
- Callers that drop runs without passing their deadline keep the breaker closed against a peer that hangs. They are counted, and R11 forbids it, but nothing refuses it.
- The counter spans runs, so after an outage an instance notices recovery only at its next probe, up to the shortest cap after the last failure. design/22 section 2.7 asks for this.
- A probe that never reports holds every other call of its instance for up to the call timeout.
- An operation has to sort a peer's refusals into `Done` and its failures into `Fail`. A wrong sort counts one caller's refused requests against the peer, unless the peer serves others meanwhile.
- Readers find the slice-0 surface of `grdr-ports` in two RFCs.

## Unresolved questions
1. **#1850's signatures.** The give-up reason's name (`GiveUp` here; #1850 question 5) and the uses section 8 lists for #1850 are #1850's to state. This RFC can be decided first: #1850's AC-3 holds its types to the uses here, and a difference is settled by an amendment of this RFC, or by #1850's RFC while it is in review, naming both.
2. **A failed draw from the system generator.** `run` follows #1850's decision on `Entropy::fill` (lead-core, #1850 comment 7075943583). What each option does here:
   - Option 1, a fallible `fill`, with `RetryPolicy::next` turning a failed draw into a give-up with a reason of its own and the step's ceiling, with no jitter, as its `backoff` and `open_for`: `run` times the breaker by that ceiling and returns `GaveUp { reason, .. }`. `RetryError` does not change.
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

Round 2, on blob `6db123e63261025f273cd7343c42982a75294f96`:
- eval-architecture, pass: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7076592867
- eval-api, pass: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7076593801
- eval-adversarial, fail: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7076704404
- eval-security, fail: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7076812230
- the session's rulings for revision 3: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7076826066

## Decision
None yet.
