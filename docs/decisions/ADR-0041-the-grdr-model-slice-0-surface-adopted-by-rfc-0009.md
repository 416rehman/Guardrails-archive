# ADR-0041: The slice-0 surface of grdr-model is the one RFC 0009 states, built under the constraints of its decision

- Status: accepted
- Date: 2026-11-22
- Decided by: chief architect
- Spine: D-05, D-06, D-15, D-36, D-48, D-51, D-60, D-61, D-63, P1, P5, P8, P9, P14, P15, P17
- Requires: #1979 (RFC 0009 on `main` in State: Review); RFC 0007 accepted on `main` (#1850 R5); the review of RFC 0009 on #1850 by the nine persona council seats, `eval-architecture`, `eval-api`, `eval-security` and `eval-adversarial`
- RFC: 0009 ([`rfcs/0009-grdr-model-slice-0-surface.md`](../../rfcs/0009-grdr-model-slice-0-surface.md)), accepted on #1850
- Work items: #1982; #383, #18, #282, #284, #279, #283, #1966; the owners its constraints bind; #1984 to #1990, filed on acceptance

## Context
#383 (time, `Entropy` and ids), #18 (the envelope's lane, epoch and sequence), #282 (the retry state types) and #284 (`LogSafe` and the log record) add the first public items to `grdr-model`, and RFC 0002, RFC 0003, RFC 0007 and RFC 0008 already use them. No RFC stated their signatures, and the texts disagreed: four lanes against five, `HolderId` in two crates, two names for the give-up reason, an `Entropy::fill` that could not report a failure, every id loggable against design/21's two, and a remote call able to read a `local` retry table ([RFC 0009, Motivation](../../rfcs/0009-grdr-model-slice-0-surface.md#motivation)). `grdr-model` is public in layer 1, so its surface changes only by RFC (D-61).

RFC 0009 went through three revisions on #1850. Round 1 failed on the breaker's representable states and a window literal; round 2 failed on the turn bound of a dropped call probe. The decided text is RFC file blob `e1f4f50307ec78e6610008cbe53343e7951ce837`, written against the spine pin `a80859235e7a2a4444648d6fa8d389d78dde6be9`. On that blob every evaluator the review calls for passed, each naming that blob and the base, with no blocker or major:
- `eval-api` (Sonnet, the other model from the RFC's metadata), https://github.com/416rehman/Guardrails/issues/1850#issuecomment-7085494964, no findings;
- `eval-architecture` (Sonnet), https://github.com/416rehman/Guardrails/issues/1850#issuecomment-7085509746, one minor;
- `eval-security` (Sonnet), https://github.com/416rehman/Guardrails/issues/1850#issuecomment-7085582842, three minors, with a disclosed deviation the RFC's Decision section weighs;
- `eval-adversarial` (Opus), https://github.com/416rehman/Guardrails/issues/1850#issuecomment-7085612435, three minors.

The nine seats reviewed the same blob. All nine support it with changes and none names a broken spine floor. The orchestrating session makes the owner's decisions (#1828). Its exit rule decides an RFC after the first round with no blocker or major and writes that round's minors, and the seats' changes, into the decision as constraints (https://github.com/416rehman/Guardrails/issues/1828#issuecomment-7074036273). Its rulings S1 to S7 on the seats are https://github.com/416rehman/Guardrails/issues/1850#issuecomment-7085697482, and the RFC's [Decision section](../../rfcs/0009-grdr-model-slice-0-surface.md#decision) quotes them.

## Decision
**Accepted.** The slice-0 surface of `grdr-model` is RFC 0009 at RFC file blob `e1f4f50307ec78e6610008cbe53343e7951ce837`, with the spine pin above as its base ([RFC 0009, Design](../../rfcs/0009-grdr-model-slice-0-surface.md#design)), and so are its amendments of RFC 0007 sections 5 and 6 and RFC 0008 section 8 changes 4 and 5 (section 16). In outline:
- `grdr-model` depends on `grdr-schema` only, with `grdr-proto` as a dev-dependency; it does no I/O, reads no clock or randomness, and puts every public item at its root (R1 to R3).
- `Entropy::fill` returns `Result<(), EntropyError>`. A failed source is `GRDR-MODEL-0003`, `fatal` with `failed_precondition`, never bytes the source did not produce and never a peer's fault (section 3).
- Ids come from one macro list, `IdKind`, with three mint routes; `DelegationSnapshotId` is `dls_` on UUIDv7, `HolderId` is `hld_` in this crate and the capability `Holder` stays in `grdr-ports` (section 4).
- `Lane` is `Uploaded(UploadedLane)` or `Local`; the server and the device's upload path take `UploadedLane`, and `lane_wire` holds `Lane` to the protobuf enum by walking the descriptor (section 5).
- `RetryPolicy::from_limits(table, access)` is the one constructor, with `PeerAccess::retry_peer` as the one classifier and a consistency check; `Breaker` is four states with `OpenPhase` and `HalfOpenPhase` and RFC 0008's turn timing; the failure share counts over the registered key `budget_share_attempts` (section 6, section 16).
- A log line carries only `LogValue`s: names fixed at build time, no integer type, and only `OrgId` and `DelegationSnapshotId` among the ids (section 7).
- `InstallProfile` and `Tamper` are at the crate root (section 8), and the crate enters `surfaces.toml` as `experimental` (section 13).

**No pin and no evidence.** RFC 0009 decides no pinned path, so its Decision section holds no decision line, `rfcs/pins.toml` is unchanged, and nothing is added under `rfcs/evidence/` ([RFC 0001, "RFC states"](../../rfcs/0001-adopt-the-spine.md#design); [ADR-0036](ADR-0036-the-amended-spine-is-the-baseline-adopted-by-rfc-0001.md), "Evidence added in route"). The decided RFC file differs from `e1f4f50` only in `State:`, `Decision record:` and the Decision section.

**Constraints.** The decision binds the constraints of the RFC's Decision section, each on the issues it names, and each was posted on those issues. Where a constraint and the RFC text differ, the constraint wins for those issues. A constraint narrows, orders, tests or refuses within what the RFC states; a change to a public item, variant, signature or loggable kind is an amendment. In outline:
1. The round 3 minors: the log-gate scan fails on a unit or counter constructor whose value reaches a log call, inline, through a `let` or through a helper, unless a reviewed marker allows it; a `LiteralText` takes literals only; the scan's set is derived from RFC 0007's unit list and `LogValue`; a failed draw in `Engine::step` is a typed failure on every input; `BudgetShareBelowBreaker` follows `BreakerFailuresAboveCeiling` and `narrow` compares fields first; `OwnFile` is shown from the opened handle (#1989, #1990, #1988, #1537, #1536, #279, #301, #1542, #30).
2. The seats' changes: an undecided install profile and a local default state directory (seat 1, #1987, #1610, #1286, #669); health codes, skew counting, presentation words and the breaker's state word by #1289's amendment (seat 2); a coverage-gap record after a failed draw, failures named in health and audit records, replay by outcome, stable record words (seat 3, #476, #760, #763); the rollout correlation id by #757's amendment and one retry state per cell (seat 4); the seed path, what an embedder may rely on, `Tamper` from a host and no partner id kinds (seat 5, #246, #242); the device pseudonym layer (seat 6, #1690); in-repository evidence, diagnostics, gate tools and contributor paths (seat 7, #1741, #10); labels, tokens with typed arguments, the id alphabet and one time type (seat 9, #1618, #1612).
3. Seat 8 as the session ruled: only the id kinds slice 0 uses, with `ost`, `acc`, `sup`, `exp`, `grp` and `opr` named to their items (#1596, #306, #483, #442, #755, #1584); the floor row kept and `budget_share_attempts` given a registered default (#279, #1966); one name type, fewer `LogValue` variants and crate-private breaker states declined.
4. Four amendments, each brought by its item before it is readied: the breaker's state word (#1289), the rollout correlation id (#757), two principal types if a field needs them (#1690), and an `Output` member if the embed path needs one (#246).

**What this acceptance binds.** What RFC 0009 states changes only by an amendment of RFC 0009, a new RFC that names it (section 13), and so do its amendments of RFC 0007 and RFC 0008, which an amendment names beside RFC 0009. The baseline is what RFC 0009 states together with the forms its constraints set, such as constraint 1a's allow marker and constraint 3c's registered default. Every other later change takes the lane of the table below; the lanes stack.

## Lanes for later changes
| Change | Lane |
|---|---|
| A new row of the id table, not loggable, under section 4's rules and constraint 3a | Content under RFC 0009: the item that first uses the kind adds the row, its pull request names RFC 0009 for `rfc-required`, and `eval-api` reads the prefix against section 4's table. High tier through `crates/grdr-model/**` |
| A new code in the `MODEL` area | Content under RFC 0007 and RFC 0009: the item that first constructs it registers it in `schema/codes/model.toml` with its tokens, by RFC 0007's code route |
| A change to what RFC 0009 states or to a form its constraints set: a signature, a semantic, a variant, a grammar, a code's class, the loggable kinds, the access classification, the lane mapping, the scan's marker form, and the promotion of `grdr-model` out of `experimental` | An amendment, a new RFC that names RFC 0009, reviewed by the persona council once, `eval-architecture`, `eval-api` and `eval-security`, with one evaluator on the other model. An amendment that also changes RFC 0007's retry rules or RFC 0008's breaker adds `eval-adversarial` and names those RFCs |
| A further edge of `grdr-model`, or a change to #1984's | A protected change on `Cargo.lock`, a trust-core path; a new dependency is also an amendment (R1) |
| The `[[crate]]` row of #1985 | Trust core: `eval-security`, `eval-adversarial` and two passing evaluators on different models |
| A value or range of `retry-bounds.share-attempts-ceiling` or `retry-bounds.share-multiple-floor` | Trust core, on the full lane, as RFC 0007 section 6 has every row; a change to what the rows mean is the amendment row |
| A constraint of the Decision section | Checked by the evaluators of the item it binds, on that item's pull request |

## What an embedder may rely on
Seat 5 asked for this list (constraint 2e). The class is the crate's; the wire forms are stable from the first release whatever the class (RFC 0009 section 13; RFC 0007 section 11; D-06).

| Part | Rust API | Wire form |
|---|---|---|
| Id text and prefixes | `experimental` | Stable |
| Lane words and numbers | `experimental` | Stable |
| `MODEL` codes: area, number, reason, class, Connect code | `experimental` | Stable |
| Words of `Tamper` and `InstallProfile` in stored or exported records | `experimental` | Stable, through their protobuf twins |
| Every other item of sections 2 to 8 | `experimental` | None |

The C ABI, the `wasm32` binding and the host contract keep their own classes (design/26 section 3). A partner holds no id kind of its own (constraint 2e).

## Where each item is built
| Item | Built by |
|---|---|
| `Timestamp`, `TimeError`, `Entropy`, `EntropyError`, `IdKind`, `MintRoute`, `IdError`, the typed ids, codes 0001 to 0005 | #383, after #1984 |
| `Lane`, `UploadedLane`, `Epoch`, `Seq`, `OrderError`, `lane_wire`, codes 0007 to 0011 | #1986, after #394, #17, #284 and #1984 |
| `RetryPolicy`, `RetryPolicyError`, `PeerAccess`, `RetryStep`, `GiveUp`, `AttemptCounter`, `RetryBudget`, `AttemptOutcome`, `Breaker` and its state structs and phases, `Permit`, `ProbeKind`, `CheckOutcome`, code 0006 | #282, split by its lead, after #1984, #383, #281 and #279 |
| `LogSafe`, `LogValue`, `IdRef`, `LiteralText`, the name types, `LogLevel`, `LogRecord`, the macros, the impls for RFC 0007's types | #284, after #383 and #1984 |
| `InstallProfile`, `Tamper` | #1987, after #284 |
| `budget_share_attempts`, the three rules, the two rows and the default | #279 |
| The edges of R1 | #1984 |
| The `[[crate]]` row | #1985, after #1817 and #1915 |
| The log-gate scan | #1989, after #1582 and #284 |
| The review duties | #1990 |
| Design texts | #1988 |

## Enforced by
- RFC 0009 section 12, one mechanism per decision, each built by the item it names, with the row constraint 1d adds: private source modules and `cargo public-api` (#383, #284, #1741); the wasm32 check and ARCH-003 (#1582); the failing-source fixture (#383, #282, #283, #1537); `lane_wire` (#1986); the compile-fail doctests of the gate, the names and the breaker (#284, #282); the turn and share tests (#282, #279).
- The log-gate scan of #1989, with its failing and passing fixtures (constraints 1a to 1c), and the review duties of #1990 behind it.
- ADR-0020's stability gate over #1985's row, with `cargo public-api` and `cargo semver-checks` (#1741).
- Each constraint by the issue it binds: its lead writes it into the item before readying it, and the item's evaluators check it on its pull request. Until each item lands, a constraint holds by review only.

## Consequences
- #383, #282, #284 and #1986 have one decided surface and name RFC 0009 as their route; none of them can start before #1984 adds the edges.
- RFC 0002 and RFC 0003 are not decided before they carry section 14's changes: `UploadedLane` on the server, `Holder`, the contexts' data class, `PeerAccess` in each adapter's set-up, and the root paths of `InstallProfile` and `Tamper`.
- Every function that draws can fail, so minting, `Engine::step`, the daemon's decision ids and `Setup::holder` each carry a failure that, with AWS-LC, the programs never see returned.
- A diagnostic points at a record by `(epoch, lane, seq)`, and a person can look a record up by it (constraint 2a).
- A log field whose count or duration is built in the same function, or by a helper, carries an allow marker that `eval-security` reads.
- Every retry table may omit `budget_share_attempts` and gets the floor multiple of its `breaker_failures`.
- `grdr doctor` cannot show a breaker's state word until #1289's amendment, and a rollout's jobs are not correlated in log lines until #757's.

## Alternatives rejected
- Those of [RFC 0009, Alternatives](../../rfcs/0009-grdr-model-slice-0-surface.md#alternatives).
- A pin record and evidence files: RFC 0009 decides no pinned path, and evidence without a decision line is out of route (ADR-0036).
- Writing the constraints into the RFC's Design text: the decided file may differ from the reviewed blob only in its state, its decision record and its Decision section.
- Keeping the log-gate scan as a list for review: a wrapped identifier would reach a log whenever review missed it (seat 6, `eval-security` m1; ruling S4).
- A deny list of four macros for `LiteralText`: a named constant or `include!` passes it (`eval-security` m2, `eval-adversarial`); the allow list has no such gap.
- Seat 8's single name type, `Position` and `Instant` variants and crate-private breaker states: declined for the reasons constraints 3b, 3d and 3e give.
- Seat 2's per-install backoff offset: a second randomness source in layer 1, and needless where AWS-LC aborts and #1966 R5 spreads the restart (constraint 2b).
- A seeded `Entropy` crate for replay, as seat 3 asked: RFC 0008's decision compares outcomes and keeps the kit's generator out of every program (constraint 2c).
- A field of the `[[crate]]` row for the wire-stable parts, as seat 5 asked: RFC 0005 R6.1 fixes the row's keys, and the table above holds the list.
- A reserved prefix range for partners: a partner kind would be a fork, and `native_*` fields carry partner ids (constraint 2e).

## Revisit when
- A verdict by an evaluator of RFC 0009's review fails `e1f4f50`, or a later comment shows a defect in the accepted text; either opens an amendment of RFC 0009 (`docs/design/30` section 3).
- #1289, #757, #1690 or #246 brings the amendment constraint 4 names.
- #1966 decides a share other than over recent attempts with a registered window (RFC 0009, unresolved question 1).
- RFC 0002 or RFC 0003 is decided without section 14's changes.
- The item that adds the `srv_` row decides the server's emitter type (RFC 0009, unresolved question 2).
