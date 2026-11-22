RFC: 0008
Title: Clock, Entropy, Monotonic and the retry executor: the first surface of grdr-ports and grdr-ports-testkit
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #1924
Spine: D-05, D-15, D-60, D-61, P1, P5, P6, P8, P9, P14, P15, P17 (no spine text changes)
Surfaces: the public crates `grdr-ports` (modules `clock`, `entropy` and `retry`) and `grdr-ports-testkit` (`ManualClock`, `ClockError`, `SeededEntropy`, `block_on`, `Stalled`, the conformance runner, the Clock suite and the `Health` double), and the `grdr-model` type `Monotonic`. As proposals: two rows of `surfaces.toml`; in `architecture.toml`, two third-party allow-lists, a per-target closure rule, the implementors of `Clock` and `Entropy` in ARCH-003's reader entries, the modules that serve outside requests, the callers that may pass a deadline, four ARCH-017 exemption entries and one ARCH-019 exemption; the test kit's error codes; sentences of design/03 sections 2 and 10, design/07 section 7 and design/22 section 2.7; seven security requirements of design/02. No third-party dependency, same-layer edge, wire format or Cedar schema changes
Decision record: none yet

To comment, write on issue #1924 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This RFC takes sections 3 and 4 of RFC 0002 (#1688) at blob `5227384311da574174149f1a23958502ff213877`, with the parts of that RFC they rest on. Section 1 lists where it decides otherwise than that text. This is revision 5. The disposition of every finding of rounds 1 to 4 is a comment on #1924.

## Summary
Slice 0 adds the first public items to `grdr-ports` and `grdr-ports-testkit`: the `Clock` and `Entropy` ports, the `grdr-model` instant type `Monotonic`, the one retry executor `grdr_ports::retry` with the `RetryState` it works on, their deterministic reference adapters (`ManualClock`, `SeededEntropy` and `block_on`), and the conformance runner that every later port suite extends. Layers 0 and 1 take `now` and `entropy` as arguments and do no I/O, and only the programs' OS adapters read a system clock or the system generator. Every retry bound comes from a `limits.toml` retry table through RFC 0007's `RetryLimits`.

One `RetryState` serves every call of one port instance. It owns its policy, its clock, its entropy and the port's own health call, and holds the budget, the breaker and the attempt counter of design/22 section 2.7. Operation classes of one origin share its breaker and budget and keep their own counters. What a client does never reaches the shared breaker, by construction:
- a call made for an outside request runs detached from it and takes no deadline. It keeps the request's admission permit until it returns, and once the client has gone it starts no retry;
- a failed attempt counts against the peer only when its error's registered code says the peer did not serve it, or when it got no answer before its cutoff. A state that serves many principals retries no other error;
- the breaker opens only when the port's own health call also fails. The probe after an open period is that health call, which follows the route of the calls it stands for. Only when it has failed `breaker_failures` probes in a row is the next probe a caller's call.

Against a dead peer the instance makes about one call per backoff.

Nothing here names a tenant context, a tenant witness, the seal, the mint authority, a fence or a storage port; those stay in RFC 0002, which amends this RFC's runner for its storage suites. Both crates enter `surfaces.toml` as `experimental`.

## Motivation
#281 (Clock, Entropy, the reference adapters and the runner) and #283 (the retry executor) are the first code in both crates, and the first runnable path needs them (#645, comment 7074036495): the daemon links `grdr-ports` for `Clock`, `Entropy` and the executor. RFC 0002 sections 3 and 4 stated this surface. They share no mechanism with that RFC's tenant contexts, seal, mint authority or fences, which are what RFC 0002's review is about. A public crate changes only by RFC (D-61; design/30 section 3), and `experimental` sets the break rules, not the route (the ruling on #1535). If nothing changes, #281 and #283 wait on a tenant boundary they do not use.

Rounds 1 to 3 showed that a shared retry state needs more than a shared counter. Each time it gained a rule for one kind of caller (one that cancels, one whose requests fail for its own reasons, one that passes a hint, one that brings its own clock), the next round found a caller that steered that rule. Revision 4 removes the inputs instead (the session's rulings, #1924 comment 7077594131). A client cannot cancel, shorten or time a shared call. A tenant's own errors are not the peer's failures. The breaker's decisions rest on a call no caller shapes. Round 4 found that the detached calls this created had no bound of their own, and that the daemon's decide path cannot be detached. Revision 5 bounds the first and gives the second fixed deadlines, and makes no other structural change (the session's rulings, #1924 comment 7078625688).

## Design

### 1. Scope and the split from RFC 0002
This RFC states RFC 0002 sections 3 and 4, and the parts of RFC 0002's Rules 1, 2, 7, 8 and 12 and sections 5, 12 and 14 that bear on them. RFC 0002 keeps everything else. From revision 10 it has no sections 3 and 4, points here, and amends section 5's runner (section 8).

The rules of section 2 and the failure modes of section 6 gather what RFC 0002, #281 and #283 already say. Otherwise the text follows the source, except in nine places:
1. The runner (section 5) is generic over its subject. The source bound it to a storage `Fixture`, so the Clock suite, which is generic over `A: Clock`, could not run on it. A case returns its `Outcome`, and the runner's types are `#[non_exhaustive]` or have private fields, so RFC 0002 adds case kinds, fixtures, stop points, induced faults and `NotApplicable` by amendment.
2. "The RFC of #1710" becomes #1850 for the `grdr-model` retry types and RFC 0007 for `RetryLimits` and `Coded`, as RFC 0007 section 7 asks.
3. `Monotonic` gains `from_nanos` and its derives. Without a constructor, neither an OS clock nor a test can make the instant `ManualClock::new` takes, and `monotonic() >= d` needs the order.
4. Before each call, the executor checks the breaker, then the budget, then takes the permit, in one step under the state's lock, so a refused call spends nothing.
5. One `RetryState` serves every call of one port instance (R9). It owns its policies, clock, entropy and health call, holds the budget, the breaker and design/22's attempt counter, and lets classes of one origin share its breaker and budget. The source let one run at a time borrow a state with no counter.
6. A call made for an outside request runs detached from it and takes no deadline. It keeps the request's admission permit and the organisation's concurrency slot until it returns, a `limits.toml` row bounds such calls per target, and once the client has gone the run starts no retry. Only internal callers pass a deadline, through `run_until` (R11). The source took the caller's request as it came, so a client could cancel or shorten a shared call.
7. A failure counts against the peer only when its registered class and Connect code say the peer did not serve the call, and only if the peer served no call meanwhile. A state that serves many principals retries no other error and leaves its counter alone (R12). The source counted and retried every failure, so one principal's requests could open the breaker, spend the budget and stretch the backoff for all.
8. The breaker opens only when the port's health call confirms the failures, and its probe after an open period is that health call, which follows the route of the calls it stands for (R13). After `breaker_failures` unhealthy probes in a row the next probe is the probing run's own call. An abandoned probe frees its slot at once and bars its class for one call timeout. Under #282 R9 a dropped probe held the breaker half-open for good, and a caller could hold the probe with its own request.
9. The breaker opens for at most the counter's ceiling and the shortest cap of the classes, and its health call is timed by their shortest call timeout. The source timed it by the step's delay, so a hint set how long every caller was refused.

The split needs items 1 and 2. Items 3 to 9 each fix a defect of the source that would stop #281 or #283, or leave a peer or its callers unprotected. Where the source is silent this RFC states that `start` is the call's own start; that a deadline past the maximum instant is the maximum instant, as #282 has it for the breaker; that the runner passes one seeded entropy to its cases in turn; that `RetryError` is exhaustive; that each call and each failed attempt reads the clock once; the late reports on an open breaker; the derives of every public type; how `to_toml` writes a string; and the values of the Clock suite's case parameters.

### 2. Rules
- R1. **Dependencies.** `grdr-ports` depends on `grdr-model` and `grdr-schema` and on no other crate, third-party crates included. The privileged daemon links it, so whatever it links is in the daemon's closure. `grdr-ports-testkit` depends on `grdr-ports`, through the listed same-layer edge, on layer 0 and 1 crates of the workspace, and on no third-party crate; RFC 0002 adds the Arrow crates for its Events reference adapter. It is never in the normal-dependency closure of a layer 4 program, resolved with all of that program's features for each target triple the release ships. A program's `Clock` is `grdr-os-clock`'s and its `Entropy` is `grdr-crypto`'s `OsRandom`, the system generator (#1927 R11; design/03 ARCH-003). So neither `ManualClock`, which whoever holds it can move, nor `SeededEntropy`, whose every later output one output reveals, reaches product code.
- R2. **Async shape.** `Clock` has `Send + Sync` as supertraits. `sleep_until` is declared as returning `impl Future<Output = ()> + Send`, which an implementation may write as an `async fn`. There is no `async-trait`, no boxed future and no `futures` crate, so `Clock` is not dyn-compatible and a caller is generic over `C: Clock`. `Health` has the same shape. `Entropy` is synchronous and stays dyn-compatible, because `Engine::step` takes `&mut dyn Entropy` (design/03 section 3). `RetryState<C, R, H>` is `Send + Sync` when `R: Send` and `H: Health`, so the future of `run` is `Send` while it borrows a shared state. A WebAssembly host passes `now` and an `Entropy` to the engine as values and implements no `Clock`.
- R3. **Open traits, confined implementations.** `Clock`, `Entropy` and `Health` are not sealed. Outside test code, `Clock` is implemented only in `grdr-os-clock` and `grdr-ports-testkit`, and `Entropy` only in the `random` module of `grdr-crypto` and `grdr-ports-testkit`. Each list is ARCH-003 data (section 7), and R1 keeps the kit out of every program. `Health` is implemented by each adapter that calls a peer of its own, under R13, and by the kit's double. An adapter that only calls other ports builds no state of its own. RFC 0002's seal covers its storage ports only.
- R4. **Layers 0 and 1.** Layers 0 and 1 hold no `Clock`, read no clock or randomness source and do no I/O (spine section 5; D-05). A layer 1 function that needs time takes `now: Timestamp` or a `Monotonic` as an argument, and one that needs randomness takes an `Entropy`, as `Engine::step` does. `Monotonic` and `Entropy` live in `grdr-model`, and `Monotonic` is a value that reads no clock. `Clock` lives in layer 2, so no layer 0 or 1 crate can name it (ARCH-001). Above layer 1, design/03's ARCH-003 makes `grdr-os-clock` the only crate that calls a system clock and the `random` module of `grdr-crypto` the only reader of the system generator, so nothing in `grdr-ports` or `grdr-ports-testkit` reads either (design/03 section 10, Time and Randomness).
- R5. **Bounds are parameters.** Every bound the executor applies comes from the `RetryPolicy` of the state's classes: attempts, elapsed time, delays, call timeouts, budget, breaker threshold, open time, probe and health-call timeout, quiet period, the bar on a class that abandoned a probe, and the unhealthy probes before a call probe, which is the breaker threshold again. The bound on a target's detached calls is that target's `limits.toml` row (R11). Product code builds a policy only with `RetryPolicy::from_limits`, from a `[retry.<name>]` table of `limits.toml` or a narrowing of one (RFC 0007 sections 5 and 6; #1850). `block_on`'s poll bound is an argument. No type here holds a tunable bound (ARCH-019). The Clock suite's case parameters (section 3) are part of each case's definition, not bounds the product applies. They are named constants in one file, `crates/grdr-ports-testkit/src/clock/params.rs`, which ARCH-019 exempts by its full path, and a change to one is a new kit version and an amendment (section 8).
- R6. **Errors.** `RetryError<E>` has no code. Its caller maps every variant to a code of the subsystem that failed, and the caller's rule class decides what the failure means (D-15). It is exhaustive, so a variant added by amendment fails every caller's build until the caller maps it. `ShareError` has no code either: the composition root that calls `for_class` or `set_policy` maps it. The kit's errors, `ClockError` and `Stalled`, have no code and hold no free text. All four are entries of the ARCH-017 exemption list in `architecture.toml`, each with its reason, so the lint reads data and special-cases no name (section 8). The kit's `ScriptedFault` does carry codes, because `Health::Error` and every operation error are `Coded`: one registered code per class and Connect pairing that section 7's cases need, in the kit's own area, `GRDR-KIT-0001` to `GRDR-KIT-0007` (section 4). #283's tests use them, so no test needs a code of another area. Each implements `LogSafe` (#1850): `RetryError<E>` where `E` does, with the `Monotonic` and the give-up reason it carries. No type here holds a person-facing string.
- R7. **Data classes and assurance.** `Monotonic`, `Timestamp`, attempt counts, the attempt counter, delays, deadlines, the breaker's state, the abandoned count, the health reading and its code, `ClientWatch`, seeds, reports and the kit's errors are `structural` (P8). Entropy output is never logged or stored. The executor never logs `E`, which keeps the class its own type declares. Assurance effect: none; no action class changes `visibility`, `control`, `on_failure` or `tamper` (P1).
- R8. **Scale.** The executor adds no request of its own beyond the health call (P15). One call makes at most `free_retries_ceiling + 1` retries in a budget window, as RFC 0007 section 5 bounds it. The health call runs at most once per confirmation and once per open period. While the breaker is closed it runs at most once per health latency plus the quiet period of one shortest call timeout. A call probe takes the place of a health probe and adds no call. Once the breaker has opened, the instance reaches a peer that fails every call once per open period, with its health call. With design/22 section 2.7's two uplink classes on one state (control at a 120 s cap, data at 15 minutes) and a breaker that opens after 5 failures, one device against a dead origin makes 58 to 71 calls an hour on average, health calls included: the figure depends on how calls due at one instant are ordered, and single runs range from 53 to 77. Counting attempts per run made about 1,460, and two separate states made about 85 in revision 3's bench. At ten million devices that is about 160,000 to 200,000 requests a second instead of about 4 million (the revision 4 and 5 benches, posted on #1924). An origin that accepts every call and fails it while its health call passes costs about 114 calls an hour per device, the counter's backoff alone (M6 in section 7).
- R9. **One state per port instance.** A `RetryState` belongs to one port instance, and every call of that instance, from any task, uses it: the adapter instance of a server port (design/20, "Stability"), or one origin of the uplink (design/22 section 2.7). Another operation class of the same origin is a state built by `for_class`. It shares the clock, entropy, health call, budget and breaker, and keeps its own policy and attempt counter, so design/22's scopes hold: a breaker per origin, a budget per uplink, and a counter and caps per class. A state and its classes are built with the instance and live as long as it, never per call. Internal code that may cancel its runs uses a class of its own (R11). The state holds nothing per principal: no key, count or history of who called (P8; RFC 0007 section 7).

  A state is built for one principal or for many (`Serves`, section 4). The uplink's origin, the daemon's verdict providers and a destination one organisation chose serve one. An adapter of a server port serves many. A port whose peer each organisation chooses, such as webhook delivery (#1275) and the export sinks of design/25, builds one state per destination peer when the destination is registered, keyed by the destination and never by the principal, so one organisation's failing endpoint shares no breaker, budget or counter with another's.
- R10. **Derives.** Every public type here implements `Debug`, and each derives what sections 3 to 5 write beside it, so a test can unwrap a kit result and compare an error. `RetryState` and `ManualClock` are not `Clone`, because a copy would split one instance's state, or one test's time, in two. `RetryState`'s `Debug` prints no entropy, clock or health call. `Outcome` is not `Copy`, so RFC 0002's `NotApplicable(Fault)` can join it.
- R11. **Outside and internal callers.** A call is outside-facing when it serves a request from outside the program and nothing bounds the request's life but its client. These are the server's API and ingest targets, each listed as such in `architecture.toml` (section 8). The daemon's IPC endpoints are not: the decide path has the shim's fixed ceiling (design/03 section 5; design/07 section 7), so its calls are internal callers with fixed deadlines.
  - An outside-facing call runs detached from its request. The target spawns the port call on its runtime and the request awaits its result, so a client's disconnect drops only the wait.
  - The spawned task holds the request's admission permit and the organisation's concurrency slot (design/20 section 4 step 3 and section 10) until the run returns. Each outside-facing target also has a `limits.toml` row, `<target>.detached-calls`, that bounds its port calls in flight. A request that would pass either bound is refused before its port call starts, with the target's admission refusal: a `retryable` code and a spread `retry_after_ms`.
  - The adapter runs the call with `run_for` and the request's `ClientWatch`, which the context the call was minted under carries (RFC 0002). Once the client has gone, the run finishes the attempt in flight, records it, and starts no retry.
  - The target drops a request whose `connect-timeout-ms` has passed before its port call starts. A client's deadline bounds the client's own wait and never reaches the executor.
  - An internal caller uses `run` with no deadline, or `run_until` with a deadline set in code or by a fixed `limits.toml` row. Examples are the uplink's own calls, the daemon's decide path, and a port method that takes a deadline, such as `Events::flush`.
  - Internal code that may drop a call it makes, directly or through a port method, detaches it in the same way, or uses its own class.
  - The architecture lint allows `run_until` only in the callers `architecture.toml` lists as passing a deadline, and refuses, in a module that serves outside requests, any call of a port method listed as taking one (section 8).
- R12. **Only the peer's failures count.** An operation's error type implements RFC 0007's `Coded`. A failed attempt counts against the peer when it ran to its cutoff without an answer, or when its error's code says the peer did not serve it. `faults_peer(class, connect)` is the one function that decides this, over the two fields of RFC 0007's registered code. It is true when both of these hold:
  - the class is `retryable` or `fatal`, so the failure is neither the caller's (`input`, `policy`) nor a defect in the product's own code (`internal`);
  - the Connect code is `unavailable`, `deadline_exceeded` or `internal`, so the peer did not serve the call. This covers a peer that is down, a peer's own timeout, a bound of our own that ended a call the peer never answered (RFC 0002's watchdog, `GRDR-REL-0008`, `fatal` with `deadline_exceeded`), and the peer's own internal error.

  Neither field alone is enough. One class, `retryable`, holds both a store that is down (`unavailable`) and a serialisation conflict (`aborted`) or back-pressure (`resource_exhausted`). One Connect code, `internal`, holds both the peer's own error and a defect of ours. Every other pairing is the peer's answer, not its failure. That includes an organisation at its own quota or under a throttle on its own data (`policy` with `resource_exhausted`, RFC 0007) and RFC 0002's tenancy refusals, which its next revision codes `retryable` with `failed_precondition` (section 8).

  The cutoff is the class's call timeout, or a `run_until` deadline when it comes first. No principal sets that deadline (R11), and a cut attempt only starts the health call, which decides whether the breaker opens. Counting only attempts that ran their full call timeout would let internal callers with a short deadline call a hanging peer without limit: about 5,900 calls in a minute in E2 b, against about 155. Counting none of the peer's own timeouts gave 6,606 calls with no opening in eval-adversarial's round 4 model; counting them gives 113 in this bench (C in section 7).

  The breaker treats the peer's answer as neither a failure nor a success: it records nothing. Recording it as a success would let one principal's cheap errors discard the failures of every call in flight beside them (section 4, "A call"), and would count an error the adapter decided on its own as the peer's answer. What else the state does with it depends on whom it serves:
  - A state that serves one principal retries it under the policy, and its class counter adds one, as design/22 section 2.7 asks of the uplink.
  - A state that serves many principals returns it to the caller at once, as `Failed`, spends no budget on it and leaves the counter as it was. One principal's own conflicts or over-limit errors therefore spend nothing another principal's retries need and stretch no other principal's backoff (M7 and the budget case in section 7). The caller retries it on its principal's own terms: the client, the bus's redelivery, or the job runner's step policy.
- R13. **The health call stands for the calls.** A port's health call follows the route, the credentials and the verification of the calls it stands for. It waits on no connection, handle or slot that a caller's request can hold or wait for. Its verdict and code show in health. An adapter's health call fails when the adapter's calls fail: the kit's admission case induces a fault that fails every call and refuses a health call that stays healthy, as `async { Ok(()) }` does (section 7). The two ways a health call and the calls can disagree each have a bounded exit, stated in section 6.

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

Each case drives its future with `block_on`, so a clock runs the suite when its sleep completes by being polled. `ManualClock`'s does. An OS clock whose sleep waits on its runtime's timer runs the suite with a test timer that blocks the thread and is ready on its first poll: #1927's `OsClock<T: Timer>` takes its timer as a parameter for this, so the suite runs it as written (lead-core, #1924 comment 7075943320). The 10 ms offset keeps that run short. Callers of `Clock`: every target, the daemon, the executor.

### 4. Retry executor (#283)
```rust
// grdr_ports::retry
pub trait Health: Send + Sync {
    type Error: Coded + Send;
    fn check(&self) -> impl Future<Output = Result<(), Self::Error>> + Send;
}

pub async fn run<T, E, C, R, H, F, Fut>(state: &RetryState<C, R, H>, op: F) -> Result<T, RetryError<E>>
where
    C: Clock, R: Entropy + Send, H: Health, E: Coded + Send,
    F: FnMut() -> Fut + Send, Fut: Future<Output = Attempt<T, E>> + Send, T: Send;
pub async fn run_until<T, E, C, R, H, F, Fut>(
    state: &RetryState<C, R, H>, deadline: Monotonic, op: F,
) -> Result<T, RetryError<E>>
where /* as for run */;
pub async fn run_for<T, E, C, R, H, F, Fut>(
    state: &RetryState<C, R, H>, client: &ClientWatch, op: F,
) -> Result<T, RetryError<E>>
where /* as for run */;
pub fn faults_peer(class: ErrorClass, connect: ConnectCode) -> bool;

#[derive(Debug, Default)]
pub struct ClientWait { /* private: held by the request while its client waits */ }
#[derive(Clone, Debug)]
pub struct ClientWatch { /* private: what the detached run reads */ }
impl ClientWait {
    pub fn new() -> ClientWait;
    pub fn watch(&self) -> ClientWatch;
}
impl ClientWatch {
    pub fn internal() -> ClientWatch;
    pub fn waiting(&self) -> bool;
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Serves { One, Many }

pub struct RetryState<C, R, H> {
    /* private: the class; shared by the classes of one state: the clock, the entropy, the health
       call, whom it serves and, behind one lock, the RetryBudget, the Breaker, each class's
       RetryPolicy and AttemptCounter, the abandoned count, the class barred from the next probe,
       the unhealthy probes in a row and the last health reading */
}
impl<C, R, H> RetryState<C, R, H> {
    pub fn new(policy: RetryPolicy, clock: Arc<C>, entropy: R, health: H, serves: Serves) -> RetryState<C, R, H>;
    pub fn for_class(&self, policy: RetryPolicy) -> Result<RetryState<C, R, H>, ShareError>;
    pub fn set_policy(&self, policy: RetryPolicy) -> Result<(), ShareError>;
    pub fn resume(self, counter: AttemptCounter) -> RetryState<C, R, H>;
    pub fn policy(&self) -> RetryPolicy;
    pub fn breaker(&self) -> Breaker;
    pub fn attempt_counter(&self) -> AttemptCounter;
    pub fn abandoned(&self) -> u64;
    pub fn health(&self) -> Option<HealthReading>;
}
// RetryState<C, R, H> implements Debug for every C, R and H.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct HealthReading { pub at: Monotonic, pub answer: HealthAnswer, pub healthy: bool, pub refuted: u32 }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HealthAnswer { Ok, Error(Code), NoAnswer }
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

// grdr_ports_testkit::health
#[derive(Debug, Default)]
pub struct ScriptedHealth { /* private */ }
impl ScriptedHealth {
    pub fn new() -> ScriptedHealth;
    pub fn set(&self, verdict: Scripted);
    pub fn calls(&self) -> u64;
}
impl Health for ScriptedHealth { type Error = ScriptedFault; /* .. */ }
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Scripted { #[default] Healthy, Unhealthy(ScriptedFault), NoAnswer }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ScriptedFault { Unavailable, PeerDeadline, Watchdog, Conflict, OverLimit, Input, Defect }
// ScriptedFault implements Coded: GRDR-KIT-0001 to GRDR-KIT-0007, in the order above.
```

`RetryPolicy`, `RetryStep`, `RetryBudget`, `Breaker`, `AttemptCounter` and the give-up reason `GiveUp` are `grdr-model` types that #282 builds and #1850 states (RFC 0007 section 1). `Code`, `Coded`, `ErrorClass`, `ConnectCode` and `RetryField` are RFC 0007's. Section 8 lists what this section needs of #1850. `RetryPolicy::from_limits` reads RFC 0007's `RetryLimits`. The kit's codes are registered in its own area, each with one class and Connect code:
- `GRDR-KIT-0001` `SCRIPTED_UNAVAILABLE`: `retryable` with `unavailable`;
- `GRDR-KIT-0002` `SCRIPTED_PEER_DEADLINE`: `retryable` with `deadline_exceeded`;
- `GRDR-KIT-0003` `SCRIPTED_WATCHDOG`: `fatal` with `deadline_exceeded`;
- `GRDR-KIT-0004` `SCRIPTED_CONFLICT`: `retryable` with `aborted`;
- `GRDR-KIT-0005` `SCRIPTED_OVER_LIMIT`: `policy` with `resource_exhausted`;
- `GRDR-KIT-0006` `SCRIPTED_INPUT`: `input` with `invalid_argument`;
- `GRDR-KIT-0007` `SCRIPTED_DEFECT`: `internal` with `internal`.

`faults_peer` is true for the first three only.

Who calls, and with which entry (R11):
- An outside-facing call uses `run_for` with its request's `ClientWatch`. Its target spawns the call on its runtime, detached from the request, and the request awaits its result. The spawned task holds the request's admission permit, the organisation's concurrency slot and a slot of the target's `<target>.detached-calls` row until the run returns. A client that disconnects or gives up drops only that wait, and its `ClientWait` with it. The call in flight runs under its own call timeout and records its true outcome, and the run starts no retry after it. So no client can cancel a shared call, shorten one, or keep one in flight at a chosen instant. A client that leaves at once also cannot keep more calls running than its target admits.
- `ClientWait::new` is made by the minting site of an outside request, which keeps it in the request's future and puts its `watch()` in the context it mints (RFC 0002). `waiting()` is false once the `ClientWait` is dropped. `ClientWatch::internal()` is the watch of a context minted for internal work, such as a job or a consumer; it always waits.
- An internal caller may use `run` with no deadline, or `run_until`, whose deadline is set in code or by a fixed `limits.toml` row. The executor never calls past it, except that a run that makes the health call waits for that call, at most the shortest call timeout of the classes.
- The daemon's decide path is internal. Each verdict provider has a state of its own (R9), built from `provider-suspend` with its call timeout narrowed to the provider's registered `deadline_ms`. Each provider call is `run_until` the smaller of that deadline and the decision's remaining budget, both from the decision's start (design/07 section 7). A provider that answers after its budget is a counted cut, so the breaker that is design/07's suspension can open. The daemon's forward to the engine is not an executor call: it makes one attempt within the decision's deadline and answers a miss from the floor table (design/03 section 5 step 3; D-15).
- An executor call sits inside the adapter, around the adapter's own call to its back end. RFC 0002's `Admitted` runs its tenant check before the adapter sees the call (its Rule 12 and section 2), so its refusals never reach the executor, and their codes do not count either way (R12).

The state:
- `RetryState::new(policy, clock, entropy, health, serves)` builds the state of one port instance (R9), for one principal or for many (R12). It owns its policy, so a state never runs under a policy it was not built from. It owns its clock and its entropy, so no caller brings a skewed clock or an entropy that returns zeros into a state others share. It owns the port's health call. The executor borrows the state shared, so any number of concurrent calls use one state. It is `Send + Sync` and not `Clone`.
- `for_class(policy)` builds another operation class of the same instance. It shares the clock, entropy, health call, budget and breaker, and keeps its own policy and attempt counter. It returns `ShareError { field }` if the policy's budget fields or `breaker_failures` differ from the state's, since one budget and one breaker cannot follow two tables. `set_policy(policy)` replaces the class's policy under the same check, keeping the budget, the breaker and every counter. A new revision of a server-set value, such as design/22's `Schedule` caps, therefore reaches a live state without resetting it.
- The budget, the breaker, the class policies and counters, the abandoned count and the barred class sit behind one `std::sync::Mutex`. The executor holds the lock only while it reads or updates them, never across an `.await` and never while the operation or the health call runs. The draw from the state's entropy happens under it. A poisoned lock is taken back with `PoisonError::into_inner`, because no step that holds it runs caller code or a panic path, and each step leaves the state whole. The state reads no clock except its own, and every instant it records is one read from that clock.
- The attempt counter is design/22 section 2.7's, one per class. On a state that serves one principal every failed attempt of the class adds one, saturating, whatever the breaker records. On a state that serves many, only a peer failure or a cutoff adds one, because any other error ends its run (R12). Only the class's `Done` sets it to 0. The executor passes its value before the failure being recorded to `RetryPolicy::next`, as the `AttemptCounter` whose ceiling the delay is drawn under, and passes the run's own retries so far, a `u32`, for the give-up checks. So a new run continues the backoff the class reached, a table's `max_attempts` and `max_elapsed` still bound one call, and the two counts cannot be swapped.
- `attempt_counter()` reads the counter, and `resume(counter)` sets it on a class just built, so a restarted program continues from it. design/22 section 2.7 keeps the uplink's counters in the daemon's state directory; #1238 (22-5, `uplink-reconnect`) writes them there and reads them back. Only the counters persist. A new process starts with an empty budget and a closed breaker, because both hold `Monotonic` instants. design/20 asks nothing more of its policies, so theirs live in memory.
- `breaker()` returns a copy of the breaker's state, and `abandoned()` the number of runs dropped before they returned. `health()` returns the last health reading: its instant, its answer with the code of a failed health call, whether it was healthy, and `refuted`, the confirmations the health call found healthy since the last call success. A target shows an open breaker, the abandoned count and the health reading in its health and on the operator plane (design/20, "Stability" and the operator plane's health list), and raises Degraded with the reading's code while `refuted` is above 0. No read changes anything, and port health adds no probe of its own (P17).

The health call:
- `Health::check` is the port's own request to its peer. No caller's request shapes it: it carries no tenant data and its cost is fixed. It follows R13: the route, credentials and verification of the calls it stands for, on a connection, handle or slot that no call holds or waits for. Examples are `SELECT 1` on a connection the store adapter keeps for it, a HEAD of a health object of the bucket over the same endpoint and credentials, and, for the uplink, a signed control-class request with no side effect that is healthy only on a verified response, as `Done` is (#1238).
- It runs to its own cutoff, the shortest call timeout of the classes. It is healthy when it returns `Ok`, or an error that `faults_peer` does not count. It is unhealthy when it returns a counted error or reaches its cutoff.

A call:
- If a `run_until` deadline has passed, the run returns `Timeout` and makes no call.
- Before each call the executor reads its clock once. Under one hold of the lock:
  - If the breaker would refuse a permit at that instant, the run ends with `BreakerOpen { until, last }`, and nothing is recorded.
  - If the permit would be a probe and the run's class is barred (below), the run ends with `BreakerOpen` with `until` at the bar's end.
  - If the permit would be a probe, the run makes the health call instead of its own call (below), and spends no budget. After `breaker_failures` unhealthy probe verdicts in a row, the probe is the run's own call instead, a call probe, which also spends no budget.
  - Otherwise it records a request in the budget for the first call, or spends from the budget for a later one. A budget refusal ends the run with `BudgetExhausted` with the breaker untouched.
- That instant is the call's `start`. The call races the operation against `clock.sleep_until(min(start + timeout, deadline))`, where `timeout` is the class's call timeout and `deadline` exists only for `run_until`. A call probe's cutoff is also no later than its `probe_until`. Each poll polls the operation first, so an operation ready on the same poll wins. If the sleep wins, the operation is dropped and the attempt counts as timed out: retryable with no hint, run to its cutoff. When the deadline ended it, or no retry follows, the run returns `Timeout`.
- On `Done(t)` the breaker records a success at the instant of the report, the class's counter goes to 0, and the run returns `Ok(t)`. The operation returns `Done` only for an answer it accepts as the peer's own; for the uplink that is a verified response (design/22 section 2.7).
- On `Retry`, `Fail` or a timeout, the executor reads its clock once. That instant is the breaker's record, the start of the sleep and the end of `elapsed`, which runs from the first call's instant. On a state that serves many principals, an error `faults_peer` does not count ends the run here with `Failed(e)`: no step, no budget, no counter. Otherwise the executor asks the policy once for the next step, with the counter, the run's retries and no hint for `Fail` or a timeout, and the class's counter adds one. The breaker records the failure only when it is a peer failure (R12) and no call on the breaker succeeded while it was in flight. If that recorded failure reaches `breaker_failures`, the run makes the health call before it goes on.
- `Fail(e)` returns `Failed(e)`. Otherwise the run sleeps until `now + delay` and calls again, or returns `GaveUp`, or `Timeout` if the last attempt timed out. A retry due at or after a `run_until` deadline is not made, and the run returns `Timeout`. A run whose `ClientWatch` no longer waits, before its sleep or after it, starts no retry and returns `Timeout`; nobody awaits that result.

The breaker:
- `Closed` counts consecutive recorded failures. A success sets the count to 0. At `breaker_failures`, and outside the quiet period below, it moves to `Checking`. The run that recorded the last failure makes the health call, and every other call still passes meanwhile.
- From `Checking`, a healthy verdict or any call's success closes the breaker again, with the count at 0 and a quiet period of one shortest call timeout. No check starts during the quiet period, though failures still count. An unhealthy verdict opens it. A recorded failure while `Checking` changes nothing until `check_until`; a recorded failure at or after it starts a new check with a new `check_until`, so a check whose run was forgotten or never polled again still ends.
- `Open { until }` refuses every permit before `until`. `until` is the failing run's `open_for`: the smaller of its step's delay and the counter's ceiling, and at most the shortest cap of the classes. A hint therefore delays only that run's own retry. A long class's backoff never holds a shorter class back, and the origin is probed at least once per shortest cap.
- At or after `until`, the first permit is a probe. The breaker moves to `HalfOpen { probe_until }`, the probing run makes the health call, and other permits are refused until `probe_until`, which is the permit's instant plus the shortest call timeout. A healthy verdict closes the breaker with the count at 0 and the same quiet period as from `Checking`, and the probing run then makes its own call. An unhealthy verdict opens it again for the probing run's `open_for`: its step is drawn with its class's counter, which adds one, and the run returns `BreakerOpen`.
- A call probe is judged as a health call is. `Done` closes the breaker and the run returns `Ok`. A peer failure or its cutoff opens it again and the run returns `BreakerOpen`. Another error closes it, because the peer answered, and the run goes on with that error as section "A call" says. After a call probe the next `breaker_failures` probes are health calls again. So a health call that fails while the calls would succeed keeps the breaker open for at most `breaker_failures + 1` open periods of at most the shortest cap each, plus their probes (section 7).
- A late report comes from a call permitted while the breaker was closed. On `Open`, a late success makes the next permit a probe, so `Open` is still left only through `HalfOpen`, and a late failure leaves `until` as it was. On `HalfOpen`, a late success closes the breaker as a healthy verdict does, and a late failure changes nothing. A verdict applies only if the breaker is still in the state the health call started from. A probe whose future is forgotten or no longer polled holds `HalfOpen` until its `probe_until`. A permit at or after `probe_until` is a new probe with a new `probe_until`, and the old health call's verdict, if it ever comes, no longer applies. A health call whose timer fires late can overlap the next probe's by its lateness, never by more.

Abandoned runs:
- Every run holds a drop guard. If its future is dropped before it returns, the guard adds one to `abandoned()`.
- If the dropped run was making a probe's health call or a call probe, the drop guard frees the slot at once, so the breaker is `Open` with `until` at that instant. It also bars the run's class from the next probe for one shortest call timeout from the drop, so another class takes the probe.
- If the dropped run was making a confirming health call, the breaker returns to `Closed` with no verdict, its count one below `breaker_failures` and a quiet period of one shortest call timeout from the drop. The next recorded failure after the quiet period starts the check again.
- The drop guard reads only the state's own clock and calls no caller code.
- An ordinary call dropped with its run records no outcome. The budget keeps the request or retry it recorded before the call began.
- Outside-facing calls are detached (R11), and internal code that may drop a call detaches it too, so a run is abandoned only by shutdown or by internal code that breaks that rule.

Common to all:
- A deadline that would pass the maximum instant is the maximum instant, as the breaker's `until` is (#282).
- The race is written over `core::future::poll_fn`, with no dependency and no runtime. Every variant keeps the attempt count and the last error.
- The futures of `run`, `run_until` and `run_for` are `Send` under these bounds. A compile-time test shows it, and so also shows that no lock guard is held across an `.await`.

Callers: every adapter's call to its back end, and every call the uplink and the daemon make to a peer except the forward to the engine (ARCH-018 forbids any other retry loop), each through the state of its port instance (R9) and with the entry of R11.

### 5. Conformance runner (#281)
```rust
// grdr_ports_testkit::conformance
#[non_exhaustive]
pub struct Case<S> { pub name: &'static str, pub run: fn(&S, &mut SeededEntropy) -> Outcome }
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
- A case returns its `Outcome`, so a storage case whose fixture cannot induce a fault returns `NotApplicable(fault)` once RFC 0002's amendment adds that variant. No side channel is needed.
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
| A deadline of the executor would pass the maximum instant | It is the maximum instant | The deadline in `ManualClock::sleeps()` |
| The peer never answers | Each attempt is dropped at its cutoff and counts as a peer failure. After `breaker_failures` of them the health call confirms and the breaker opens; each open period ends with one health call | `BreakerOpen` to refused callers; the open breaker in health |
| The peer fails every call and callers keep starting runs | Once the breaker has opened, the instance reaches the peer with one health call per open period, and every other call ends with `BreakerOpen` and no call. Each class's counter grows across runs up to its cap (R8) | `BreakerOpen`; the open breaker in health |
| A client disconnects, or asks for a short deadline, on an outside-facing call | Nothing reaches the shared accounting: the call runs detached under its own timeout and records its true outcome, then starts no retry; its task keeps the request's admission permit and concurrency slot until it returns; the client's wait ends on its own | The client's own error |
| Clients send requests and leave at once, faster than their port calls end | The target's admission permits, each organisation's concurrency slots and `<target>.detached-calls` bound the calls in flight; a request past any of them is refused before its port call starts, with a spread `retry_after_ms` | The target's admission refusals, counted per lane and organisation (design/20) |
| A request's `connect-timeout-ms` passes before its port call starts | The target drops it and starts no port call | The client's own timeout |
| One principal's requests fail for its own reasons: input, over its quota or throttle, a conflict | Not peer failures (R12): the breaker records nothing. On a state that serves many principals the run ends at once with `Failed`, spends no budget and leaves the counter as it was, so no other principal's retries or backoff change; the caller retries on that principal's terms | That principal's errors |
| One principal's requests time out at the peer while the peer serves others | Not recorded, because the peer served a call meanwhile; if no one else called, they are recorded, and the health call finds the peer healthy, so the breaker stays closed | That principal's errors; one health call at most per shortest call timeout |
| The peer ends calls with its own timeout, or a bound of ours ends a call the peer never answered (`GRDR-REL-0008`) | A peer failure (R12), like a cutoff: after `breaker_failures` the health call confirms and the breaker opens | `BreakerOpen`; the open breaker in health |
| An adapter registers a tenant-level error with a peer-failure code | The breaker records it, and the health call still finds the peer healthy, so the breaker stays closed | Health calls in the port's metrics; `refuted` in health; the codes case that walks the registry (section 7) |
| The health call passes while every call fails | The breaker stays closed. The load stays bounded by what bounds it without a breaker: callers' first attempts, retries within the budget (10% of requests plus the floor), and each class's counter, which reaches its cap. At most one health call per health latency plus quiet period. M6 in section 7: 605 retries for 5,935 first attempts in a minute; on the uplink about 114 calls an hour per device, against 58 to 71 for a dead origin | `refuted` above 0 in `health()`, which the target shows as Degraded with the code of the calls' failures |
| The health call fails while the calls would succeed, for example a filter on its path | It decides only after recorded failures, so a broken health call opens the breaker only when calls also fail. Once open, after `breaker_failures` unhealthy probes in a row the next probe is a call probe, which closes the breaker if the call succeeds: at most `breaker_failures + 1` open periods of at most the shortest cap, plus their probes (a case held back under D-62, section 7) | The health reading's code in health, against the call probe's success |
| A health call waits on a connection or slot that callers' requests hold | R13 forbids it: the adapter keeps a connection, handle or slot for the health call alone, and its item's test holds every other one with paused calls while the health call completes | The adapter item's test |
| A verdict provider answers after its deadline or the decision's remaining budget | A counted cut (R12). After `breaker_failures` of them the provider's health call confirms and the breaker opens: the provider is suspended, its `on_failure` applies at once to every decision, and the broker raises Degraded and a coverage-gap finding (design/07 section 7). If only some decisions are slow and others succeed, the breaker stays closed and design/07's failure-rate rule, the broker's own count over its receipts, raises them | `BreakerOpen` to the broker; Degraded and the finding; `provider-failure` on each receipt |
| Internal code drops a run during a probe | The slot is freed at once, its class is barred from the next probe for one shortest call timeout, and another class takes it; internal code that shares a class with others makes them wait for its bar | `abandoned()` in health |
| Internal code drops runs without passing a deadline, against a peer that hangs | Each dropped attempt records nothing, so the breaker stays closed. R11 asks such code to detach the call or pass `run_until`'s deadline | `abandoned()` grows with the calls |
| A peer or a proxy sends a hint far beyond the table's cap | That run's own retry honours it or gives up at `max_elapsed`; the breaker opens for at most the counter's ceiling | `GaveUp` to that run; the breaker's `until` |
| A live health call reports after its deadline | The verdict applies only if the breaker is still in the state it started from | The breaker's state |
| A call permitted while the breaker was closed reports after it opened | On `Open`, a success makes the next permit a probe and a failure leaves `until` unchanged; on `HalfOpen`, a success closes the breaker and a failure changes nothing | The breaker's state |
| A probe or a check is never polled again | `HalfOpen` ends at `probe_until`, when the next permit is a new probe; `Checking` ends at `check_until`, when the next recorded failure starts a new check | The breaker's state |
| `for_class` or `set_policy` is given a table whose budget or breaker fields differ | `ShareError { field }`, naming the first field that differs | The composition root's error |
| The budget is spent | `BudgetExhausted { attempts, last }`; the breaker is not touched | The returned error |
| The operation returns `Fail` | `Failed(e)` after that call; it is a peer failure only if its code says so | The returned error |
| The policy gives up after a `Retry` | `GaveUp { reason, attempts, last }` | The returned error |
| A resumed attempt counter is stale or altered | Any value is a valid counter; the delay stays within the table's cap | The delays of the next run |
| The state's lock is poisoned | Taken back with `into_inner`; no step that holds the lock runs caller code or a panic path, so the state is whole | Nothing |
| The wall clock jumps during a run | No effect: elapsed time and deadlines use `monotonic()` only | #283's case with `jump_wall` between attempts |
| The host suspends during a run | A deadline that passed while the host was suspended has passed on waking, so the next attempt or the timeout comes within `clock.recheck` of waking (#1927 R8) | #1927's sleep model; #1936 on real cells |
| The system generator fails | The programs' `Entropy` never returns bytes it did not draw from the generator: zeroed or repeated bytes would make every full-jitter delay 0, and every key and nonce predictable. How the failure reaches the executor is #1850's; question 2 gives what each option does to `RetryError` | #1850's error, or the give-up reason the run returns |
| A caller meets a `RetryError` | It maps the variant to its own subsystem's code, and its rule class decides the outcome (D-15). A caller refused with `BreakerOpen` that can wait retries once at `until`, which takes the next probe | The caller's error and code |

Nothing here fails open: no `RetryError` variant reads as success, a variant a caller does not map fails its build, and none of #1850's options for a failed draw returns bytes that were not drawn. A failure that does not count against the peer is still returned to its caller.

### 7. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| R1 | A third-party allow-list per crate in `architecture.toml`, empty for both crates, read by the archlint graph rules. A check that `grdr-ports-testkit` is in no layer 4 program's normal closure, resolved with all of that program's features and once per target triple of the release's support matrix (design/24 section 9) with `cargo metadata --filter-platform`. Negative fixtures: a program with the kit as a normal dependency, one that reaches it through a layer 3 crate, one that reaches it only under one of its features, and one that reaches it only under a `[target.'cfg(..)'.dependencies]` table for a target other than the host; each fails | #1580 reads the data and adds the fixtures, a constraint posted there on acceptance; the entries are the protected change filed on acceptance |
| R3 and R4, the readers and implementors | design/03 ARCH-003 as section 8 proposes to extend it: outside its readers it refuses a system clock or generator call, a `clippy::disallowed_methods` allow over one, and a direct `getrandom` or `rand` dependency. Outside test code it also refuses `impl Clock` except in `grdr-os-clock` and the kit, and `impl Entropy` except in `grdr-crypto`'s `random` module and the kit, each list read from `architecture.toml`. Fixture crates that implement `Entropy` and `Clock` outside them fail | #1582, its ARCH-003 part; the entries are #1933's and the protected change filed on acceptance |
| R2 | The `+ Send` bounds, checked by the compiler; compile-time tests that the futures of `run`, `run_until` and `run_for` are `Send`, that `RetryState` is `Send + Sync`, and that two runs on one `&RetryState` build and run | #283 |
| R4, layers 0 and 1 | ARCH-001 (no layer 0 or 1 crate depends on `grdr-ports`); ARCH-003's disallowed methods and banned crates; `cargo build -p grdr-model --target wasm32-unknown-unknown` | #1580; #1582; #281 AC-6 |
| R5 | ARCH-019; policies built only through `RetryPolicy::from_limits`; the Clock suite's parameters as named constants at section 3's values in `params.rs`, exempted from ARCH-019 by that one path | #1582; #279; #282; #281 |
| R6 | ARCH-017, reading the four exemption entries; for the exhaustive `RetryError`, the compiler on each caller's match, which fails until a new variant is mapped | #1582; the protected change filed on acceptance; #283 |
| R9 | The executor borrows a `Sync` state and `RetryState` is not `Clone`. `crates/grdr-ports/AGENTS.md` says under "Do not" that a `RetryState` and its classes are built with the port instance, never per call, with `for_class` and `set_policy` only at construction or on a new revision of the class's table. `eval-architecture` checks this on every pull request that calls `RetryState::new`, `for_class` or `set_policy`. No scan holds it: a constructor that builds its state and retries its first connection through `run` is correct | The compiler; #283 (the AGENTS.md line); the `eval-architecture` line, filed on acceptance for lead-agent-kit |
| R11 | `run` and `run_for` take no deadline, so no request deadline can be passed to either (a compile-fail doctest). ARCH-018 gains a clause, as section 8 proposes: `run_until` only in the callers `architecture.toml` lists as passing a deadline, and no call, in a module that serves outside requests, of a port method listed as taking one; negative fixtures for each. Each target that serves outside requests spawns its port calls detached and keeps the request's permit, slot and `<target>.detached-calls` slot in the task, with tests: a client disconnecting mid-call leaves `abandoned()` unchanged, the call's outcome recorded and the permit held until the run returns; after its client has gone a failing call starts no retry; with every client leaving 1 ms in, port calls in flight stay at the row and the next request is refused (two cases held back under D-62) | #1582 (the clause); #1534 for the server targets (the detachment, the row and their tests); #283 (the doctest and `run_for`'s case) |
| R12 | `faults_peer`, one function over RFC 0007's `ErrorClass` and `ConnectCode`, with a table test over all 45 pairings that needs no `Code`; the kit's seven codes for #283's executor tests. Each port's error codes are registered in RFC 0007's registry, a per-tenant limit or throttle takes `policy` with `resource_exhausted`, and each storage suite's codes case walks `codes::ALL` for its port's areas and asserts `faults_peer` for each code, so a new code's effect on the breaker shows in review | #283 (the function and its test); #281 (the kit's codes); RFC 0002's amendment and its storage items (their codes and the walk) |
| R13 | The kit's `ScriptedHealth`. Each storage suite's case `health_call_fails_with_its_calls`: with `induce` making every call fail, the adapter's health call is unhealthy and `breaker()` opens; with the fault lifted it closes. A fixture that cannot induce the fault fails the case for a release-gating adapter. Each adapter item's test holds every pooled connection with paused calls and its health call still completes. #1238's case for the uplink's health call: healthy only on a verified response | #281 (the double); RFC 0002's amendment and its adapter items (the cases); #1238 |
| R10 | The compiler on #281's and #283's tests, which unwrap the kit's results, return `Result<(), ClockError>` and format each public type with `{:?}`; `cargo public-api` lists the impls | #281; #283 |
| One retry loop | ARCH-018 | #1582 |
| One randomness trait (P17) | `pub use grdr_model::Entropy`; `eval-architecture` refuses, on every pull request that adds a trait in layers 0 to 2 with a `now`, `monotonic`, `sleep` or `fill` method, a second clock or randomness trait | #281; the `eval-architecture` line, filed on acceptance for lead-agent-kit |
| Section 3 and the runner | `clock::suite()` on `ManualClock` with the `jump_wall` case; a fixture clock whose monotonic value decreases, which fails exactly that case; the reference `splitmix64.c` output for seed 0; a future `Pending` by construction under `block_on`; `Monotonic` at 0 and at the largest instant. Compile-fail doctests outside the kit: a struct expression of `Report` (private fields), of `CaseResult` or of `Case`, and a match on `Outcome` with no wildcard arm, each fail. `to_toml` of a report whose adapter name holds a quotation mark, a backslash and a line break has one `adapter` line and no other key | #281 AC-1 to AC-5, and its doctests |
| `run`'s semantics | Under `ManualClock` and `SeededEntropy`: each recorded deadline against `RetryPolicy::next` called directly with the same seed and counts; the timeout drop; the breaker and budget transitions, counted by a fixture operation; a refused call that spends nothing; and a probe that is the health call, after which the probing run makes its own call | #283 AC-1 to AC-3 |
| The shared state, the counter and recovery (R8, R9) | Against a reference model of section 4 over #282's types, written in the test from this text, under a test clock whose sleep waits until the test moves it. E1: the uplink's two classes on one state against a dead origin for an hour, whose calls equal the model's; with the origin recovering at a random instant, the control class's first success within the shortest cap plus two shortest call timeouts of it, with ties in arrival order and shuffled (at most 120.1 s against a bound of 122 s in the bench). E1h: the same with the origin hanging, control's call timeout 10 s and data's 120 s, within 140 s (at most 127.7 s in this bench; 133.1 s in eval-security's round 4 model, which a probe in flight at the recovery explains). E6: data hanging while control succeeds every 50 s, after which data's counter has grown and data calls about 17 times an hour. Also `resume` continuing a class's backoff, `set_policy` keeping the breaker and counters, and `for_class` returning `ShareError` for each differing field | #283 |
| Outside and internal callers (R11) | E2: a peer that hangs, 100 callers a second for a minute, a 1 s timeout. Outside callers with no deadline, and internal callers with `run_until` at 0.5 s, about 211 and 156 calls with the breaker open, against about 6,000 for internal code that drops at 0.5 s, each drop counted in `abandoned()` | #283 |
| Which failures count (R12) and the health call | E3: one principal's slow requests in bursts of 5, with another at 50, 500 and 0.2 calls a second and once every 120 s, and two slow principals; the other refused in 0% of calls in each. A peer that fails every caller opens the breaker. C: E2's shape with the peer ending each call at 0.5 s with `retryable` `deadline_exceeded`, and with `GRDR-REL-0008`, its health call likewise; the breaker opens, about 113 and 108 calls. The cases of which errors count held back under D-62, given to #283's implementer through the session | #283 |
| The health call and the calls disagree (R13) | M6: every call fails `retryable` `unavailable` while the health call passes, 100 callers a second for a minute: no opening, 605 retries for 5,935 first attempts, one health call per quiet period, `refuted` 59; the uplink's two classes against an origin that answers 503: about 114 calls an hour, `refuted` above 0. The case of a health call that fails while calls would succeed held back under D-62: the call probe ends it within `breaker_failures + 1` open periods | #283 |
| A principal's own errors on a state that serves many (R12) | M7: victims at 5 a second, 5% of whose first attempts fail, each client waiting 10 s, with and without one principal's `policy` errors at 100 a second: a victim's `unavailable` retried and answered within the wait in 100% of cases, median 76 ms, both ways; a victim's `aborted` returned at once in 100%, both ways. The budget case held back under D-62 | #283 |
| The decide path (R11) | A provider whose calls and health call take longer than its deadline is suspended within `breaker_failures` decisions plus one health call, and every decision then gets its `on_failure` at once with Degraded and the finding raised; it is unsuspended by the first probe after it recovers. A provider slow for some decisions only stays unsuspended, and the broker's failure-rate rule raises Degraded. The forms held back under D-62 | #233 and #523 (the broker's states and the decide path); #283 (the executor's part) |
| Probes and abandoned runs | E4a: a probe dropped after one poll frees its slot at once, its class is refused until one call timeout from the drop, and another class probes. E4b: after one opening, a caller whose clients drop each request 1 ms in, at 1,000 a second; the drops never reach the state, and the breaker closes within 20 ms of opening in the bench. The same caller as internal code on its own class: closed within a second. The same caller as internal code on the shared class, over 300 s: the breaker stays open for 117 s on average and B is refused 39% of the time, the stated residual. E4c: probes against a hanging peer never overlap while timers are on time, and a late timer overlaps the next probe by its lateness only. Each row of #1850 change 5 with its case. The probe cases held back under D-62, given to #283's implementer through the session | #282 (the transitions); #283 |
| The hint (R5) | A step whose hint is `u64::MAX` ms opens the breaker for at most the counter's ceiling, and a caller after that ceiling reaches a healthy peer | #282 (the step's `open_for`); #283 |
| The codes of storage errors | One case in each storage suite: an input error, a refusal from `Admitted`'s check and an over-limit error, each over two calls on one instance, leave `breaker()` and the class counter unchanged and are returned at once; then the walk of `codes::ALL` (R12 row) | RFC 0002's amendment of the runner, and the storage suite items |
| Health | `RetryState::breaker()`, `abandoned()` and `health()`; each target shows an open breaker, the abandoned count and the health reading in its health, and Degraded while `refuted` is above 0 | #283 (the reads); #1584 and each target's health item (the display) |
| Suspended time counts | #1927 proves the sleep against scripted boot-time readings and checks each system's boot-time read on the hosted runners; real suspend and wake on each system's matrix cell | #1927; #1936 on real cells |
| Stability | The `surfaces.toml` rows, `rfc-required`, `cargo public-api`, `cargo semver-checks` | The protected change filed on acceptance; #1741 |

### 8. Stability, and what each item changes
Stability:
- Both crates enter `surfaces.toml` as `experimental` (D-60; ADR-0020; design/03 section 7: every surface starts there), through the protected-change item filed on acceptance. Each gets one row of the kind `surfaces.toml` has when the item lands; in RFC 0005 R6.1's `[[crate]]` kind that is `name`, `class = "experimental"` and `rfc = "0008"`. RFC 0002 amends this RFC for both crates and keeps the rows. `Monotonic` takes the class of the `grdr-model` row (#1850), because a class belongs to a crate (RFC 0007 section 11).
- `experimental` allows a break in any release, and every change still goes by RFC. A signature, a semantic, a variant or a suite case is an amendment: a new RFC that names RFC 0008, because an accepted RFC never returns to `Review` (RFC 0001, "RFC states"). Its pull requests name that RFC for `rfc-required`. `cargo public-api` and `cargo semver-checks` run against the class once the rows exist, and the release notes list every amendment, as `breaking` when it breaks.

Proposed for `architecture.toml`, in the protected change filed on acceptance:
- an empty third-party allow-list for each crate, with the rule that `grdr-ports-testkit` is in no layer 4 program's normal closure under any of that program's features, for each target triple of the support matrix;
- in ARCH-003's reader entries, the places `impl Clock` may appear outside test code (`grdr-os-clock` and `grdr-ports-testkit`) and those `impl Entropy` may (`grdr-crypto`'s `random` module and `grdr-ports-testkit`);
- the list of modules that serve requests from outside the program (the server's API and ingest targets), the list of callers that may pass a deadline to `run_until` (the uplink, the daemon's decide path, and the adapter methods of port methods that take a deadline), and the list of those port methods (`Events::flush`), which ARCH-018's clause reads (R11);
- ARCH-017 exemption entries for `grdr_ports::retry::RetryError` and `grdr_ports::retry::ShareError` (each caller maps every variant to its own code), and for `grdr_ports_testkit::clock::ClockError` and `grdr_ports_testkit::Stalled` (test kit errors, never returned by product code);
- an ARCH-019 exemption for `crates/grdr-ports-testkit/src/clock/params.rs` by that full workspace path (#1582 comment 7075274622), because its constants define conformance cases and bound nothing the product does.

The entries take the form of the lists in force when the item lands (RFC 0002 section 14; RFC 0005 R4.1).

Proposed for the design documents, each filed on acceptance as the chief architect's design item:
- **design/03 section 2, ARCH-003.** The row gains a sentence and its fixtures. Outside test code, `Clock` is implemented only by the clock reader and the port test kit, and `Entropy` only by the randomness reader and the kit, each named in `architecture.toml`.
- **design/03 section 2, ARCH-018 `one-retry`.** The row gains a clause and its fixtures: `run_until` appears only in the callers `architecture.toml` lists as passing a deadline, and a module that serves outside requests calls no port method listed as taking one. A fixture that calls `run_until` in a target module, and one that calls `Events::flush` from one, each fail.
- **design/03 section 10 (Retries) and design/22 section 2.7, the jitter.** The full jitter is drawn from the program's system generator (R1), not "seeded by device id, boot id and attempt". Independent draws from each device's generator keep devices out of step, which is what the seed was for. A seed built from those three values would let anyone who knows them predict a device's retries.
- **design/22 section 2.7, the origin's breaker.** "Each origin has a circuit breaker" gains this sentence: "shared by the origin's operation classes, confirmed by a health call before it opens and probed with one, and open for no longer than the shortest of the classes' caps, so the breaker closes, and the control class reaches the origin, within that cap plus two call timeouts of its recovery". The second timeout covers a probe's health call in flight when the origin recovers, which eval-security's round 4 model traced (133.1 s against a bound of 131 s with one). The bound is on recovery, not on the gap between one class's calls: a data run sleeping in its own backoff still waits out its delay. That is why R8's figure is 58 to 71 calls an hour per device, not the 51 a model without the cap rule gave in round 2.
- **design/22 section 2.7, `connect-timeout-ms`.** "Every request carries `connect-timeout-ms`, and the server drops work past it" becomes: "every request carries `connect-timeout-ms`, and the server drops work past it before the port call starts; an attempt already started finishes and records its outcome, but is not retried". R11 holds the sentence, and section 6 has its rows.
- **design/03 section 10 (Retries).** One sentence: a call made for a request from outside the program runs detached from it under its own policy timeout and keeps the request's admission permit and concurrency slot until it returns, a `limits.toml` row bounds such calls per target, a run whose client has gone starts no retry, and only internal callers bound a retry by a deadline (R11).
- **design/07 section 7, "Failure policy".** A sentence: each provider's suspension is the open breaker of the provider's own `RetryState`, built from `provider-suspend` with its call timeout narrowed to the provider's `deadline_ms`. Each provider call runs until the smaller of that deadline and the decision's remaining budget, so an answer after it is a counted failure. The provider's health call is a fixed `ProviderRequest` on the provider's own connection with the same peer check. The rule "more than 5% failures in five minutes" stays the broker's own count over its receipts and raises Degraded and the coverage-gap finding. The daemon's forward to the engine is not an executor call (R11).
- **design/02 section 3.8.** Seven security requirements, from eval-security's wording in rounds 1 to 4 (#1924 comments 7076101630, 7076812230, 7077581411 and 7078608559):
  - One `RetryState` per port instance holds the attempt counters, the budget and the breaker for every call, and classes of one origin share the breaker and budget. A new run continues its class's counter, only a success resets it, and a program can persist and resume it. A port whose peer each organisation chooses keeps one state per destination.
  - A probe stops holding the breaker by its deadline, an abandoned probe frees its slot at once, and no caller holds the probe with its own request: the probe is the port's health call, and only after `breaker_failures` unhealthy probes in a row is it a caller's call.
  - Product code draws randomness only from the system generator. No deterministic `Entropy` is in a program's normal closure, and `Clock` and `Entropy` are implemented only where ARCH-003 names.
  - No principal's requests open a shared breaker: only peer failures by their code and cutoffs count, and the breaker opens only when the port's health call also fails. On a state that serves many principals, one principal's other errors spend no budget and move no counter.
  - A client never cancels, shortens or times a shared call, and a run that internal code abandons is counted.
  - SR-new-0008-F, detached work is bounded: a detached call keeps its request's admission permit and the organisation's concurrency slot until it returns, a `limits.toml` row bounds a target's detached calls and past it new requests are refused before their port call starts, and a run whose client has gone starts no retry. Test: clients that leave 1 ms after sending hold no more port calls than the row, the next request is refused, and no retry follows.
  - SR-new-0008-G, the health call stands for the calls: a port's health call follows the route, credentials and verification of the port's own calls, waits on no resource a caller's request can occupy, and its code shows in health. Test: a fault that fails the port's calls fails its health call too, and a filter that fails only the health call is ended by the call probe.

  Residual risks for its 3.9:
  - internal code that cancels calls, directly or through a port method, on a class it shares with others; E4b over 300 s shows other callers refused 39% of the time;
  - internal code that drops runs instead of detaching them or passing `run_until`'s deadline;
  - a peer whose health call passes while its calls fail, bounded only by the budget and the counters and shown as Degraded;
  - a provider slow only for some decisions, shown by the broker's failure-rate rule, not by the executor.

  The first two are visible in `abandoned()`.

What each item changes:
- **#281**: its route and its scope are this RFC: sections 3 and 5 as decided, with any amendment decided before it is worked. R1 gains `from_nanos` and the derives. R2: `Clock: Send + Sync`, and `monotonic` counts suspended time. R4: `ManualClock` is `Sync`. R8 becomes the runner of section 5: a `Suite<S>` only the kit builds, an unbounded `run(&subject, adapter, seed)`, cases that take `&mut SeededEntropy` and return an `Outcome`, a `Failure` that names the kit's check in place of failure text, the seed in the report, a `Report` with private fields and accessors, the `#[non_exhaustive]` types with their compile-fail doctests, and `to_toml`'s escaping. R9 takes the three cases and their parameter file, so the write set gains `crates/grdr-ports-testkit/src/clock/**`. Every public type takes the derives of R10. It also builds the kit's `health` module of section 4 (`ScriptedHealth`, `Scripted`, `ScriptedFault`) and registers the seven `GRDR-KIT` codes, so the write set gains `crates/grdr-ports-testkit/src/health/**` and the kit's error registry entry. The `Fixture` traits, case kinds, `NotApplicable`, stop points, `arm`, `reach`, `authority()`, `tenancy()` and the storage how-to page come with RFC 0002's amendment and its items.
- **#283**: its route is this RFC. R1 becomes `run(state, op)`, `run_until(state, deadline, op)` and `run_for(state, client, op)` with the bounds of section 4, with `Health`, `ClientWait`, `ClientWatch`, `Serves` and `faults_peer(class, connect)`. `RetryState` owns its class policies, clock, entropy and health call, knows whom it serves, and holds the budget, the breaker, the class counters, the abandoned count, the barred class, the unhealthy probes in a row and the last health reading behind one lock. It has `new`, `for_class`, `set_policy`, `resume`, `policy`, `breaker`, `attempt_counter`, `abandoned` and `health`. R3 and R4 take section 4's one-step check, with the probe as a health call and the call probe after `breaker_failures` unhealthy ones. R5 races against the earlier of the class's call timeout and a `run_until` deadline. R7 passes the counter and the run's retries to `next`, moves the class counter as R12 says for each kind of state, ends a many-principal run at once on an error `faults_peer` does not count, starts no retry once a `ClientWatch` stops waiting, and records on the breaker only peer failures with no success in flight. The non-goal "Sharing `RetryState` across tasks" goes, because sharing is the point (R9). Its tests take section 7's cases for R2, R11, R12, R13, `run`'s semantics, the shared state, probes, the hint, C, M6 and M7, and the held-back cases given through the session. The write set gains `crates/grdr-ports/AGENTS.md` for R9's line. AC-4 cites ARCH-018, a scan rule of #1582, not #1580. It needs #1850 decided for the retry types, and RFC 0007 for `RetryLimits` and `Coded`. Its lead should split it, for example into the state and the call, the breaker with its health call, and the abandoned-run rules.
- **#1850**, with #282, which builds its types. `Monotonic` is this RFC's, and section 4 needs these:
  1. `RetryPolicy::next` takes its entropy as `&mut R` for any `R: Entropy + ?Sized`, because `&mut dyn Entropy` cannot be formed from a generic `R` (rustc E0277).
  2. `next` takes two counts of different types: an `AttemptCounter`, which sets the ceiling (#282 R3 and R4), and the run's retries so far, a `u32`, which the `MaxAttempts` check reads (#282 R7). `AttemptCounter` is a `grdr-model` value with `new(u32)`, `get()` and a saturating `next()`, deriving `Clone`, `Copy`, `Debug`, `Default`, `PartialEq`, `Eq`, `PartialOrd`, `Ord` and `Hash`, and implementing `LogSafe`. #282's AC-3 reference draws the two counts independently.
  3. Each `RetryStep` carries `open_for`, the smaller of its delay and the ceiling of the counter, so a hint never times the breaker beyond the table's cap. With no hint, `open_for` equals the delay, so #282's vectors hold.
  4. `RetryPolicy` exposes its call timeout, its cap (the exponential cap, or a schedule's last delay), its budget fields and `breaker_failures`, which the executor, `for_class` and `set_policy` read.
  5. `Breaker` has four states:
     - `Closed { consecutive_failures, quiet_until }`;
     - `Checking { check_until }`, a health call confirming recorded failures while calls still pass;
     - `Open { until }`;
     - `HalfOpen { probe_until }`, the health call probing after an open period.

     Its transitions are section 4's, one row each:
     - `Closed` and a recorded failure: count it, and at `breaker_failures` outside the quiet period, move to `Checking`.
     - `Checking` and a success or a healthy verdict: `Closed` with the count at 0 and a quiet period.
     - `Checking` and an unhealthy verdict: `Open`.
     - `Checking` and a recorded failure: unchanged before `check_until`; at or after it, `Checking` with a new `check_until` and a new health call.
     - `Open` at `until` and a permit: `HalfOpen`.
     - `Open` and a late success: `Open` with `until` at the earlier of its `until` and now.
     - `Open` and a late failure: unchanged.
     - `HalfOpen` and a healthy verdict, or a late success: `Closed` with the count at 0 and the same quiet period as from `Checking`.
     - `HalfOpen` and an unhealthy verdict: `Open`.
     - `HalfOpen` and a recorded failure: unchanged.
     - `HalfOpen` at or after `probe_until` and a permit: `HalfOpen` with a new `probe_until`, a new probe.
     - `release` of an abandoned health call: `HalfOpen` to `Open { until: now }`, and `Checking` to `Closed` with the count one below `breaker_failures` and a quiet period.

     A verdict or release applies only if the breaker is still in the state the health call started from. Whether a probe is a health call or a call probe is the state's choice, not a breaker state. #282 AC-4's rule that no sequence leaves `Open` except through `HalfOpen` stands, with a case for each row.
  6. `Breaker` answers, without a transition, whether a permit at `now` would be refused and until when, so the executor checks it before it spends.
  7. `RetryPolicy`, `RetryBudget` and `Breaker` are `Send + Sync`, so the executor's future is `Send`. `RetryPolicy` and `RetryBudget` are `Clone` and `Debug`, since a state owns them and prints its policy. `Breaker` derives `Clone`, `Copy`, `Debug`, `PartialEq` and `Eq`, since `breaker()` returns a copy. The give-up reason derives the same and implements `LogSafe`, so `RetryError<E>` is `LogSafe` where `E` is.
  8. AC-3's use `RetryState::new(&RetryPolicy)` becomes `RetryState::new(policy, clock, entropy, health, serves)`, with the policy by value.
  9. How a failed draw from the system generator reaches the executor (question 2).

  #282's non-goal "Sharing one budget or breaker across threads: the caller owns the instance" stays true: `RetryState` in `grdr-ports` shares them.
- **#1580**: the four negative fixtures of R1's closure check and the per-target resolution, posted there as a constraint on acceptance.
- **#1582**: ARCH-003 for layers 2 to 4 as design/03 has it, with the implementor lists of R3 and their fixtures; ARCH-018's clause of R11, reading the three lists of `architecture.toml`, with its fixtures; and ARCH-019's exemption for `params.rs` by its full path.
- **#1933**: ARCH-003's reader entry for `grdr-os-clock` names it as the implementor of `Clock`.
- **#1534** (the target trait and tier runtimes of `grdr-server`): each target that serves outside requests spawns its port calls detached from the request, moves the request's admission permit and the organisation's concurrency slot into the task, registers its `<target>.detached-calls` row and refuses past it before the port call starts, keeps the request's `ClientWait` in the request's future, and drops a request past `connect-timeout-ms` before its port call starts, with R11's tests.
- **#1536, #523 and #233** (the daemon's decide handler, the decision path through `grdr-broker`, and the provider failure policy): the daemon's IPC endpoints are internal callers (R11). The forward to the engine is not an executor call. Each verdict provider has one `RetryState` serving one principal, from `provider-suspend` with its call timeout narrowed to the provider's `deadline_ms`, and a health call that is a fixed `ProviderRequest` on the provider's connection. Each provider call is `run_until` the smaller of its deadline and the decision's remaining budget. #233's suspension state is that state's breaker, and its failure-rate rule is the broker's count over its receipts, with the decide-path row of section 7.
- **#1275 and the export sink items of design/25**: one `RetryState` per destination, built when the destination is registered, keyed by the destination (R9).
- **#1238** (22-5, `uplink-reconnect`): one `RetryState` for the origin, serving one principal, with the uplink's health call: a signed control-class request with no side effect, healthy only on a verified response, which the item names and tests (R13). The control and data classes come from two registered `[retry.<name>]` tables, each narrowed by the cap of the server's newest verified `Schedule` (RFC 0007's `narrow`), and built by `for_class`. A new `Schedule` revision calls `set_policy` on each class. Each class's counter is written to the daemon's state directory from `attempt_counter()` and read back through `resume` when the uplink starts. The uplink is an internal caller and may use `run_until` (R11).
- **lead-agent-kit**, an item filed on acceptance: two lines for `.claude/agents/eval-architecture.md`, the review duties of the R9 row and of the P17 row of section 7.
- **RFC 0002, revision 12 (`ef892d8`) and its successors**: sections 3 and 4 are this RFC's, and its section 5 states its runner additions as an amendment of this RFC. Those are `kind` on `Case` and `CaseResult`, `Outcome::NotApplicable(Fault)`, the `Fixture` bound on each storage suite's constructor, and the arming state the kit holds inside `run` for every suite. Revision 12 carries this RFC's revision 4: no caller key, `error_codes_spare_the_breaker`, `StoreFault::Throttled` as `GRDR-STORE-0009` (`policy` with `resource_exhausted`), the derives, and the state inside the adapter after `Admitted`'s check. Its next revision changes these for revision 5:
  - `GRDR-TENANT-0006`, `0008` and `0012` take `retryable` with `failed_precondition`, so a refusal does not count even inside an executor call, and the sentence that keeps refusals outside the executor because they count changes to say they do not.
  - `GRDR-REL-0008` is still returned as `Fail`, but `faults_peer` counts it (R12), so a watchdog ending transactions on a stalled store opens the breaker once the health call agrees. The sentence that its class keeps it off the breaker goes.
  - Its adapters build their state with `Serves::Many`, so `error_codes_spare_the_breaker` asserts that each error leaves `breaker()` and the class counter unchanged and comes back at once. The case also walks `codes::ALL` for the port's areas and asserts `faults_peer` for each code (R12).
  - The reference adapters' health call is the kit's `ScriptedHealth`, which the fixture's `induce` turns unhealthy, not one that answers `Ok`. Each storage suite carries `health_call_fails_with_its_calls` (R13). Each adapter keeps a connection, handle or slot for its health call alone, and its item tests it.
  - A context minted for an outside request carries the request's `ClientWatch`, and every other context carries `ClientWatch::internal()`. The adapter passes it to `run_for` (R11).
  - Events builds no state for its catalogue writes and lake objects, which go through `Relational` and `Blobs` and their states; only a peer of its own, such as its tail source, gets one (R3).
  - `clock()` hands out the kit's one `ManualClock` as an `Arc`, which `RetryState::new` takes, for example from a kit-private `OnceLock<Arc<ManualClock>>` (eval-api's round 4 note).

  Its interim rule under Rule 12, that no crate naming a capability type or a `tenant`, `storage` or `adapter` item takes a registry dependency or a proc macro until #1475 lands, leaves out the daemon, which links `grdr-ports` only for this RFC's `clock`, `entropy` and `retry`. Revision 12 states this.
- **RFC 0007, next revision or decision**: section 1's row for `Monotonic`, and its notes on `Entropy` and on `RetryError` with its ARCH-017 exemption, name this RFC in place of RFC 0002. Section 5's "the caller decides whether a new episode starts" still holds: a new run continues the attempt counter, and only a success resets it (design/22 section 2.7).
- **#1927**: builds the programs' OS `Clock`, `OsClock`, with the suspend rows of sections 6 and 7 and the Windows reader of section 3, and pairs it with `OsRandom` as the programs' `Entropy` (#1927 R11). Each program passes them to `RetryState::new`.

## Surfaces changed
- `grdr-ports` (layer 2, public): modules `clock`, `entropy` (a re-export) and `retry`. Class `experimental`.
- `grdr-ports-testkit` (layer 2, public): `ManualClock`, `ClockError`, `SeededEntropy`, `block_on` and `Stalled` at the root, the conformance runner in `conformance`, `clock::suite`, and `health` with `ScriptedHealth`, `Scripted` and `ScriptedFault`. Class `experimental`.
- `grdr-model` (layer 1, public): `Monotonic`. Class `experimental`, the crate's.
- The error registry: the seven `GRDR-KIT` codes of section 4.
- As proposals: two `surfaces.toml` rows, and the `architecture.toml` entries of section 8; sentences of design/03 sections 2 and 10, design/07 section 7 and design/22 section 2.7, and seven security requirements of design/02 (section 8).
- No spine text, protobuf package, Cedar schema, third-party dependency or same-layer edge changes.

## Alternatives
- **Keep sections 3 and 4 in RFC 0002.** #281 and #283 would wait on a tenant boundary they do not use. Rejected.
- **A runner bound to a storage `Fixture`, as RFC 0002 section 5 had it.** The Clock suite has no store, so it could not run, and #281 would wait on the tenant types the `Fixture` names. Rejected for a runner generic over its subject.
- **Exhaustive runner types, a `Report` with public fields, and cases that return `Result<(), Failure>`.** A field or variant RFC 0002 adds would break every caller. Any holder could edit a report into a pass, and a case could not report `NotApplicable`. Rejected for `#[non_exhaustive]`, private fields and cases that return an `Outcome`.
- **A `Clock` over `std::time::Instant` in `grdr-ports`.** The standard library does not specify whether `Instant` counts time the host spent suspended, and says the behaviour varies by platform and release (https://doc.rust-lang.org/std/time/struct.Instant.html, read 2026-11-22). A deadline could stay in the future after a sleep, and layer 2 would read a clock. Rejected for OS adapters in the programs.
- **`async-trait` or a boxed future, for a dyn-compatible `Clock`.** A new dependency and an allocation per sleep, while each program names its clock type at compile time anyway. Rejected.
- **A state borrowed by one run at a time, with no counter, as revision 1 had it.** Against a dead peer, 1,000 callers in one minute with a state each make 7,000 calls, and one caller that restarts after each error makes about 1,460 an hour. Rejected for one shared state per instance.
- **The clock and entropy as arguments of each run, as revision 2 had them.** One caller's clock with a distant origin, or an entropy that returns zeros, would time the breaker every other caller shares. Rejected for the state owning both.
- **A client's deadline passed to the executor, with a cut attempt counted against the peer, as revision 3 had it.** A 1 ms client deadline against a healthy peer opened the breaker for everyone, from one principal or two. Refusing a call whose policy timeout exceeds the client's deadline would refuse calls rather than bound them. Rejected for detached outside calls and `run_until` for internal callers only.
- **Counting an abandoned attempt as a failure.** An OS network change that cancels the uplink's calls would open its breaker and block design/22's immediate reconnect. Rejected for counting abandoned runs in `abandoned()`.
- **The operation choosing, per call, whether a failure is the peer's.** Revision 3 asked adapters to return a refusal as `Done`, and a wrong choice on one call let one principal's requests count. Rejected for `faults_peer` over each error's registered code, which is reviewed once in the registry.
- **A principal's own errors recorded as successes on the breaker.** They would discard the failures of calls in flight beside them, so a stream of cheap input errors would keep a failing peer's breaker closed. Rejected for recording nothing (R12).
- **Counting a timeout only when the attempt ran its full call timeout.** Internal callers whose `run_until` deadline is shorter than the call timeout would never open the breaker against a hanging peer: E2 b gives about 5,900 calls in a minute with the breaker closed, against about 155. Rejected, because no principal sets that deadline and the health call still decides.
- **Counts or records per principal, so failures open the breaker only when two principals fail (revision 3, and the ruling's first option).** Two principals that keep calling crowd any small record. A record large enough not to be crowded grows with the organisations an instance serves. On the hosted platform a second organisation is one sign-up. Rejected for the health call, which no principal's request shapes.
- **Opening on failures alone and probing with a caller's request.** A caller then held the probe with a slow request and could drop it just before the deadline, or take turns with a second key. Rejected for the probe being the health call.
- **A caller key for the probe bar.** With outside calls detached, only internal code abandons a probe, and its class already identifies it. Rejected for a bar per class, with no key in the state.
- **Spawning the health call, or an outside call, from `grdr-ports`.** That needs an async runtime in layer 2. Rejected: the target spawns on its own runtime, and the state's health call runs inside the run that needs it.
- **A `retry-bounds.hint-ceiling` row.** It would be a new bound to set and keep, while the counter's ceiling already bounds what the policy itself would wait. Rejected for `open_for`, which needs no row.
- **Timing a breaker shared by classes, or its health call, by the failing class's own cap or timeout.** The data class's 15-minute backoff or 120 s timeout would hold the control class back, and commands with it. Rejected for the shortest cap and the shortest call timeout.
- **`RetryError` as `#[non_exhaustive]`.** Each caller maps every variant to its own code, so a wildcard arm would map a variant added later with no decision. Rejected.
- **A detached call that keeps nothing of its request, as revision 4 had it.** A client that leaves at once frees its admission permit at once, while its port call runs on, so nothing the target counts bounds the calls in flight. Rejected for the task keeping the permit, the slot and the detached-calls row's slot.
- **A slice of the budget per principal for errors the peer did not cause.** It needs a key and a record per principal in the state, which two principals crowd or many principals grow, as the opening rule's records did. Rejected for not retrying those errors on a state that serves many principals.
- **`faults_peer` over the class alone, or the Connect code alone.** R12 names a pairing that each field alone gets wrong. Rejected for both fields.
- **Counting class `internal` as a peer failure, as revision 4 did.** It is a defect in the product's own code, so a principal that can provoke one would start health calls. Rejected.
- **Trusting the health call for ever once the breaker is open.** A filter on the health call's path alone held the breaker open with no limit in round 4. Rejected for the call probe after `breaker_failures` unhealthy probes.
- **Opening the breaker after `breaker_failures` refuted confirmations.** It would let one principal's failures open the breaker after all, which the health call exists to prevent. Rejected: a health call that passes while calls fail is bounded by the budget and the counters and shown as Degraded.
- **Detaching the daemon's IPC calls like the server's.** The decide path's deadline is the shim's fixed ceiling, and a provider's late answer has to count, so design/07's suspension works. Rejected for fixed deadlines through `run_until`.

## Drawbacks
- The runner changes shape when RFC 0002 adds case kinds and `NotApplicable`. `#[non_exhaustive]` keeps that from breaking callers outside the kit, but it is still a change inside it.
- `Clock` is not dyn-compatible, so every caller is generic over its clock, and `RetryState` is generic over its clock, entropy and health call.
- The Clock suite drives futures with `block_on`, so an OS clock runs it with a test timer that blocks, not with its runtime's timer.
- Every port that calls a peer needs a health call that follows its calls' route on a connection of its own. Its cost is one call per confirmation and per open period, and a confirmation adds up to one shortest call timeout before a dead peer's breaker opens. In E2 that is about 211 calls in the first minute, against 118 in revision 3's bench. A provider whose calls all fail while its health call passes gets one health call per health latency plus quiet period, and its quiet period is its deadline.
- A run that makes the health call returns up to one shortest call timeout after its `run_until` deadline.
- Outside-facing targets must spawn their port calls and hold the request's permit in the task. A call whose client has gone still runs its attempt to its outcome, up to one call timeout, and holds its permit that long.
- `ClientWatch` travels in RFC 0002's contexts, so the minting site, the context and the adapter all carry it.
- On a state that serves many principals, a conflict or a back-pressure answer comes back to the caller at once instead of being retried there. The caller retries it on its principal's terms. On the uplink, which serves one principal, a class's counter still counts every failed attempt, as design/22 asks.
- After `breaker_failures` unhealthy probes in a row the probe is a caller's call, so a caller can shape that one probe. It is cut at `probe_until`, and it comes only while the health call is already failing.
- A health call that passes while the calls fail keeps the breaker closed. The budget and the counters bound the load, and health shows it, but the instance keeps calling: about 114 calls an hour per device on the uplink, against 58 to 71 for a dead origin.
- Internal code that cancels runs on a class it shares with others can make them wait at each probe. The bench shows it: with every run dropped 1 ms in, the breaker stays open for most of 30 s, and over 300 s others are refused 39% of the time. R9 and R11 give such code its own class or ask it to detach, and `abandoned()` shows it.
- Every call of an instance takes the state's lock two or three times. Each hold is short and never spans an `.await`, but a busy instance contends for it.
- The counter spans runs, so after an outage an instance notices recovery only at its next probe, up to the shortest cap after the last failure. design/22 section 2.7 asks for this.
- Readers find the slice-0 surface of `grdr-ports` in two RFCs.

## Unresolved questions
1. **#1850's signatures.** The give-up reason's name (`GiveUp` here; #1850 question 5) and the uses section 8 lists for #1850 are #1850's to state. This RFC can be decided first: #1850's AC-3 holds its types to the uses here, and a difference is settled by an amendment of this RFC, or by #1850's RFC while it is in review, naming both.
2. **A failed draw from the system generator.** The executor follows #1850's decision on `Entropy::fill` (lead-core, #1850 comment 7075943583). What each option does here:
   - Option 1, a fallible `fill`, with `RetryPolicy::next` turning a failed draw into a give-up with a reason of its own and the step's ceiling, with no jitter, as its `backoff` and `open_for`: the executor times the breaker by that ceiling and returns `GaveUp { reason, .. }`. `RetryError` does not change.
   - Option 1, with `next` returning the entropy error instead: the executor needs a new `RetryError` variant, by amendment of this RFC, and each caller maps it (R6).
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

Round 3, on blob `ad4bfa98b1c6a583a23e3273b3f186babebf8e4c`:
- eval-architecture, pass: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7077278921
- eval-api, pass: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7077324403
- eval-adversarial, fail: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7077552063
- eval-security, fail: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7077581411
- the session's rulings for revision 4: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7077594131

Round 4, on blob `83a4a096353abfa259374ffda79bb98cc293caa8`:
- eval-architecture, pass: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7078370903
- eval-api, pass: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7078395336
- eval-adversarial, fail: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7078508922
- eval-security, fail: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7078608559
- the session's rulings for revision 5: https://github.com/416rehman/Guardrails/issues/1924#issuecomment-7078625688

## Decision
None yet.
