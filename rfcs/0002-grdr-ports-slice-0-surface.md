RFC: 0002
Title: The slice-0 public surface of grdr-ports and grdr-ports-testkit
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Review
Design issue: #1688
Spine: D-05, D-11, D-33, D-34, D-35, D-51, D-57, D-61, D-63, D-69, P1, P4, P5, P6, P8, P9, P10, P14, P15, P17 (no spine text changes)
Surfaces: public crates `grdr-ports` and `grdr-ports-testkit`, and the storage format of lake and blob objects (key layout and `grdr-aad-v1`)
Decision record: none yet

To comment, write on issue #1688 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This is revision 10. The dispositions of every review are comments on #1688. The text below is normative on its own. Where it differs from the eight items it adopts, this RFC wins, and section 15 tells each lead what to write back. Sections 3 and 4 are now RFC 0008 (#1924), and section 5 amends RFC 0008's conformance runner.

## Summary
Slice 0 adds the first public types and traits to `grdr-ports` and `grdr-ports-testkit`: identifiers, the tenant contexts and object paths, the Blobs, Jobs (leases), Bus, Relational and Events ports, and the conformance kit with a reference adapter and a suite per port. This RFC states every signature and its semantics in full, sets twelve rules every port follows, assigns the error codes, says how an adapter from outside the workspace is tested, verified and selected, and enters both crates as `experimental`. Who may mint a tenant context, implement a port, build a fence or act for an organisation in a given lifecycle state or under a delegation is held by types: sealed port traits, a mint authority issued once per process with the process's one tenancy table and clock, and one check at every store operation of the organisation's current lifecycle answer, the context's delegation and its expiry. A register check over macro-expanded code keeps `unsafe` away from the code that holds these types. It changes no spine text and proposes amendments to design/03, design/20 and design/21 (section 14).

## Motivation
`grdr-ports` is the seam P6 and P14 rest on. The release-gating adapters of each profile and every contrib or embedder adapter meet the product only through these traits, and they are admitted only by passing the test kit (design/03 extension points; design/20 extension point 1). Every server target in slice 0 calls them; `grdr-daemon` links the crate only for what RFC 0008 defines. A public crate changes only by RFC (D-61, design/30 R7), and `experimental` sets the break rules, not the route (ruling on #1535).

The eight items (#281, #297, #298, #299, #300, #1535, #312, #313) were specified one at a time. Read together they disagree in places a later adapter would turn into a defect: two fence rules, an unfenced lake write path, one error variant with two classes, a `Set` context that reaches a per-organisation lake read, methods with no semantics, and no rule for how Events rows cross the port. Review also found barriers that held only where a source scan ran or a caller kept a convention: who may mint a context, who may implement a port, who may build a fence, where an organisation's lifecycle state and a provider's delegation are checked, and what a test hook may run. This RFC puts each of those in a type wherever a type can hold it. If nothing changes, nine implementers build against conflicting signatures and the first adapter items (#1546, #1547, #1554) inherit the conflicts.

## Design

### 1. Rules for every port
Terms used below:
- A **tenant witness** is a value only a tenant context can produce (Rule 3).
- A **deployment-scoped** method works on a resource that belongs to no organisation: leases, bus partitions and offsets, bucket maps, migrations, a partition's flush. `architecture.toml` lists each one (section 14).
- A **port trait** is what module code calls; an **adapter trait** is what an adapter implements; `Admitted<A>` joins them (Rule 12).
- The **mint authority** is `MintAuthority`, issued once per process with the process's tenancy table and clock (section 2). The **composition root** is the module of `grdr-server` that builds the adapters from configuration, issues the mint authority, admits the adapters and starts the runners. `architecture.toml` names it and the runners it hands the authority to.
- A **fence** is a lease name and the fencing token one `Leases::acquire` call granted. No caller builds one (section 7).
- A **call token** is `PortsCall<S>` (section 2), a value branded with the type `S` whose method takes it. It has no public constructor, and only the `tenant` module of `grdr-ports` builds one. An adapter can implement a method that takes one. Code outside `grdr-ports` can neither call that method nor pass a token it received to another type's method, because the brand differs.
- A **work kind** is an `OrgWork` value and an **answer** an `Admission` value: what an organisation's lifecycle state allows for that work (section 2).
- A **capability type** is a type whose value carries a power: `MintAuthority`, `MemberReadAuthority`, `VerifiedAudience`, `VerifiedWorkbenchToken`, `JobRecord`, `PortsCall`, `Admitted`, `Fence`, `Lease`, `HolderId`, the contexts and the other tenant witnesses of Rule 3. Code outside `grdr-ports` gets a value of one only from a function section 2 or 7 names.
- **ARCH-nnn** is a rule of the architecture lint: registered in design/03 section 2, configured in `architecture.toml`, run by `cargo run --locked -p grdr-archlint -- check` (#1580, #1582). Until design/03 section 2 is amended, new numbers come from the register comment on #1688: this RFC's `context-mint` is ARCH-029.
- A **protected change** is a change to a path on the protected-path list of `docs/team/06` section 2.1, such as `architecture.toml`, `surfaces.toml`, `dist.toml`, `limits.toml` or `.github/`. It is its own issue whose write set names the path, worked by `lead-agent-kit` or the chief architect, and it lands after `eval-security` and an evaluator on the other model pass (D-63). Review and CI hold it, not a session permission (ADR-0035).
- **`rfc-required`** is the check of design/30 section 3, which #1741 builds: it fails a pull request that touches an RFC-gated surface unless the pull request names an RFC whose state on its base is `Accepted` or `Implemented` (RFC 0001, "What holds the rule").

Rule 1. **Dependencies.** `grdr-ports` depends on `grdr-model` and `grdr-schema` and on no other crate, third-party crates included. The privileged daemon links it and layer 2 has no Cargo features (design/03 section 8), so whatever it links is in the daemon's closure. `grdr-ports-testkit` may also depend on the Arrow crates #1532 admits, at the same pins, for `MemEvents`, once #1475 has landed (Rule 12). It is never in the normal-dependency closure of a layer 4 program under any feature set a release or distribution build enables. An adapter crate may expose a `testkit` feature for its own tests, which adds only its fixture and the hook statements of section 5, and which is the only thing that brings `grdr-ports-testkit` into the crate's normal dependencies; no program and no `dist.toml` enables it. The distribution build runs an adapter's conformance tests in a cargo invocation of their own, never in the program build, so feature unification cannot carry `testkit` into a program (section 12).

Rule 2. **Async shape.** Every port and adapter trait has `Send + Sync` as supertraits. A method that reaches a back end is declared `fn name(&self, ...) -> impl Future<Output = Result<T, E>> + Send`, which an implementation may write as an `async fn`. A stream is a pull method of the same shape, not a `Stream` trait. No `async-trait`, no boxed futures and no `futures` crate in `grdr-ports`. The storage traits are therefore not dyn-compatible; section 12 says how a build selects an adapter. `Clock` and `Entropy` have the shapes RFC 0008 gives them, and each adapter builds one `RetryState` per port instance and policy (RFC 0008 R9). There is no second, non-`Send` shape: the storage ports serve server targets only, and a WebAssembly host passes `now` and `Entropy` to the engine as values (layers 0 and 1 take them as arguments), so it implements none of these traits.

Rule 3. **Tenant witnesses.** A tenant witness is `&SingleCtx`, `&TenantCtx`, `&SetCtx`, an `OrgRead`, a `TenantPath`, a `ReadPath`, a `ListPrefix`, a `Planned` Events plan, an `OrgRows` result stream, a relational transaction, an `OrgBatch` or a `LakeBatch`. Every port method that takes tenant data in takes a witness derived from a `SingleCtx`. Every method that returns tenant data to module code takes a witness or returns the data inside one. A read takes the widest context its store can bind: `&TenantCtx` for the relational port, whose row-level security binds a `Set` through `delegation_snapshot`, and an `OrgRead` for Events and Blobs, whose keys are per organisation. An `OrgRead` comes from a `SingleCtx` or from a `MemberCtx`, the read-only context for one organisation of a delegation snapshot (section 2), so a provider's cross-organisation lake read is one plan per member and never holds a write witness. A deployment-scoped method takes no context. Two of them handle tenant data, `Subscription::fetch` and `Events::flush`. `flush` hands none out. `fetch` takes a call token, so only `grdr-ports` calls it: `bus::fetch_batches`, which takes the mint authority and returns the messages inside `OrgBatch` values, and the `Admitted` and `Dispatch` forwarders (section 8). `ResultStream::next` takes one too, called only by `OrgRows` and the forwarders (section 10). Where module code passes an adapter's own value back in, the port takes it inside a type only `tenant` builds: `Events::execute` takes `Planned<Self::Plan>`, and `Events::append` takes a `LakeBatch` (section 2). Section 14 gives the reading of D-35 this rests on.

Rule 4. **No organisation in inputs.** No input type of a port method has an organisation field. The organisation, and the delegation a context carries, come from the context, and the adapter writes them: the bus `org` header and the delegation stored beside it (section 8), the lake's `organisation_id` column (section 10), the `org=` segment of every path (section 2). The one exemption is `MemberCursor`, a page cursor over a snapshot's organisations, which names no organisation the caller acts for; `architecture.toml` lists it.

Rule 5. **Fences.** A fence is current while its token equals the newest token issued for its lease. Tokens only grow, and every `acquire` that returns `Held` issues a new one (section 7), so a fence names one acquisition, not one holder or one process. A fenced commit takes one of two forms, and every fenced commit on the surface names its form:
- *Lease-checked*, where the commit runs in the store that holds the lease table: the commit of a transaction opened with `Relational::write_fenced`, each migration's transaction inside `Migrator::apply`, and the catalogue transaction of `Events::flush`. Inside that transaction the adapter takes a lock on the lease row that `acquire` and `renew` conflict with, holds it until the commit ends, and commits only if the fence is current. The admitted locks are `SELECT ... FOR SHARE` on the lease row in PostgreSQL, the single writer (`BEGIN IMMEDIATE`) in SQLite, and the shared hold in `MemLeases`. An isolation level is not a substitute for the lock: under SERIALIZABLE, a read of the lease row followed by another holder's `acquire` is one read-write dependency, which PostgreSQL does not abort, so the stale commit would land.
- *Row-stamped*, for the bus, whose tables may live in another database (design/20 section 7, `bus.database`). `Bus::subscribe` stamps each claimed partition's consumer row with the claim's fence and holder in one compare-and-set that never lowers the stored fence, and returns the committed position from the same statement. `Bus::commit` succeeds only while the row holds the caller's fence, in one conditional row update (section 8).

Neither form trusts a caller's token. A fence comes only from a lease grant: no caller can build a `Fence`, a `FencingToken` or a `Lease`, and only the holder of the mint authority mints a `HolderId`, which nothing parses (section 7). The fence of a claim or a commit must be of the partition's own lease, which `Admitted` checks before the adapter sees it (section 8). `Leases::check` is a point-in-time read. It protects no commit by itself; it lets a holder stop early. A superseded fence has one code wherever it is found (section 11), and no error carries a token.

Rule 6. **Nothing without a reference and a case.** Every method and every enum variant on the surface has a reference implementation in the test kit and at least one named conformance case. Where the variants of a data enum behave the same at the port, the port section says so and one case covers them. A method or query node whose semantics are not yet specified is not declared; it enters with its item by amendment (section 12). Each port section names the caller of each method and says when that caller is not in slice 0.

Rule 7. **Bounds are parameters.** Page and fetch limits, lease terms, query limits, stream byte bounds, flush thresholds, deadlines, cleanup grace, the age past which a replica's tenancy copy is stale, the life of a relational transaction, identifier lengths and bucket maps are values the caller passes or the adapter is built with, read from `limits.toml` (#279). No port type or reference adapter holds a tunable bound (ARCH-019). The storage format has two fixed ceilings, which are part of the format and not tunables: an identifier is at most 255 bytes, and each additional-data field at most 65,535 bytes (section 2).

Rule 8. **Errors.** Each port module has one error enum, and `Coded` (#280) binds each variant to one registered code (section 11). Faults of the back end itself are one shared type, `StoreFault`, which every port error carries as `Store(StoreFault)`, so a full disk or a serialisation failure has one code whichever port met it. An operation that the check of section 2 does not admit, for the organisation's current state, the context's delegation or its expiry, is one shared value, `Refusal`, which every port error carries as `Refused(Refusal)`. Callers act on the code's class, never on the variant, so error enums are `#[non_exhaustive]`. Errors carry structural values only (keys, offsets, ids, byte indexes) and implement `LogSafe` (#284); an error about a rejected identifier carries the fault and the byte index, never the rejected text. No port type holds a person-facing string. Each code's sentence is the `code.<code>.message` and `code.<code>.fix` language tokens of design/03 section 10, and a key or name inside it reaches the reader as a typed argument rendered in a left-to-right isolate (UX6), never by `Display` concatenation. Test kit types have no code of their own and hold no free text: a fixture that cannot open reports the `StoreFault` it met (section 5). They are listed in the ARCH-017 exemption list of `architecture.toml` (section 14), so the lint reads data and special-cases no name.

Rule 9. **Exhaustive data enums.** `TenantCtx`, `TenantScope`, `OrgRead`, `SetPurpose`, `Lifecycle`, `OrgWork`, `Admission`, `StateRead`, `DelegationRead`, `Dispatch`, `StorageClass`, `Partition`, `LeaseState`, `Acquire`, `Renew`, `Grant`, `Renewal`, `Stream`, `LakeTable`, `QueryIr`, `Direction`, `Comparison`, `Literal`, `Step`, `StepKind`, `ExpandKind`, `Completion`, `LimitReason`, `Coverage`, `StopPoint` and `Fault` are exhaustive, so a new variant fails every adapter's build until it handles it. Adding one is an amendment with its suite cases.

Rule 10. **Identifiers are ASCII.** `ObjectName`, `LeaseName`, `ConsumerGroup`, `ViewName`, `ColumnName` and `CheckpointRef` hold 1 to `max` bytes, each a lower-case ASCII letter, an ASCII digit, `-`, `_` or `.`, and are neither `.` nor `..`. `max` comes from `limits.toml` and may not exceed 255. Anything else fails `parse` with `IdentError` (code `GRDR-TENANT-0001`): no normalisation, no case folding, no width folding. Ids from grdr-model (`OrgId`, `DelegationId`, `DelegationSnapshotId`, `DeviceId`, `SessionId`) render as ASCII by their own format (#1710). A name a person chooses (an organisation, a device, a group named in Arabic or Japanese) lives in a relational column and never in a path, a key or additional data. This keeps the bytes the additional data authenticates identical across adapters, file systems and locales.

Rule 11. **Order is numeric or byte-wise.** Every order on the surface compares integers and times numerically and strings, identifiers and object keys by their bytes, never by a locale's collation. That covers `Blobs::list`, `Relational::snapshot_members`, the Events orders and positions, and `Lt`, `Le`, `Gt` and `Ge` on text literals. A PostgreSQL adapter sets `COLLATE "C"` on these comparisons; its fixture runs the ordering cases on a database whose default collation is `ja-JP` (section 5).

Rule 12. **Sealed ports.** The traits in sections 6 to 10 are port traits. Each has the supertrait `seal::Sealed`, whose module is private to `grdr-ports`, so no other crate implements one, by hand or through a macro. An adapter implements the adapter trait of the same port, in `grdr_ports::adapter`: `BlobsAdapter`, `LeasesAdapter`, `BusAdapter`, `SubscriptionAdapter`, `RelationalAdapter`, `ReadTxAdapter`, `WriteTxAdapter`, `MigratorAdapter`, `EventsAdapter` and `ResultStreamAdapter`. An adapter trait has its port trait's methods and semantics, except that its associated types are the adapter's own types under the matching adapter traits, `LeasesAdapter::acquire` and `renew` return plain grant values (section 7), and `ReadTxAdapter` and `WriteTxAdapter` have no `adapter_mut`.
- `grdr-ports` implements every port trait for `Admitted<A>`, where `A` implements the adapter trait, and for nothing else. The implementations live in the trust-core `tenant::admit`. They forward each call to `A` and wrap each associated type in `Admitted`; build every `Lease` from a grant (section 7); refuse a claim or a commit whose fence is not of the partition's own lease (section 8); and run the check of section 2 on every witness before `A` sees the call.
- `Admitted::new(adapter, &MintAuthority)` is the only public constructor, and ARCH-029 fails a call of it outside the composition root and the kit (section 2), so only they admit an adapter. The generated dispatch of section 12 implements the adapter traits and is admitted like any adapter.
- No `unsafe` reaches the types. A type barrier holds only where no `unsafe` reaches the code that holds the type, since a zeroed call token or a transmuted context passes any type check. The barrier is the register check of SP-9 (design/35 section 2.4, #1475), and it covers every capability type. It reads each crate after macro expansion and name resolution, on the workspace and on the distribution build's resolved closure. Every crate in the dependency closure of a crate that depends on `grdr-ports`, build and proc-macro dependencies included, holds and emits no `unsafe`, or `security/unsafe-register.toml` lists it for what it holds or emits; the toolchain's crates are one entry. Every `unsafe` block, `unsafe fn`, `unsafe impl`, `unsafe extern` block, unsafe attribute and inline or global assembly in a crate the register does not list fails the build, whatever produced its tokens: the crate's source, another crate's macro or derive, or a proc macro. `#![forbid(unsafe_code)]`, which ARCH-029 requires of every workspace crate other than the OS adapter crates and `grdr-ffi`, and the distribution build's compile of each closure crate that depends on `grdr-ports` with `unsafe_code` forbidden and lint capping off, stay as a first check. They are not the barrier, because the lint does not see what another crate's macro emits. Until #1475 has landed, no crate that names a capability type or an item of `tenant`, `storage` or `adapter`, judged by ARCH-029 on resolved paths, takes a registry dependency or a proc macro. The daemon names only RFC 0008's `clock`, `entropy` and `retry`, so this interim rule does not reach it; if it ever names one of those items, the rule does.

Data classes (P8): every type on the surface is `structural`, except payload bytes (blob objects, bus payloads, the archive bytes of a `LakeBatch`, `ArrowIpc`), which carry the classes of what they hold and are never logged, and positions and predicate literals, which carry their columns' classes. The port records no per-object data class. `StorageClass`, with the lane for archive objects, is enough for slice 0: retention is by class and lane, erasure of content is by destroying the root session's content key, and reduction rewrites by lane (design/04 section 10), so none needs a class inside an object. A per-object class that must be authenticated would be a new additional-data tag (section 2), which is the costly kind of change and needs its own RFC.

Assurance effect (P1): none. No action class changes `visibility`, `control`, `on_failure` or `tamper`.

### 2. Identifiers, tenancy and object paths (#312, #313)
The `tenant` module is trust core.

```rust
// grdr_ports::ident
pub struct IdentMax { /* private: 1..=255 */ }
impl IdentMax { pub fn new(bytes: u16) -> Option<IdentMax>; pub fn get(&self) -> u16; }
pub struct ObjectName { /* private */ }
pub struct LeaseName { /* private */ }
pub struct ConsumerGroup { /* private */ }
pub struct ViewName { /* private */ }
pub struct ColumnName { /* private */ }
pub struct CheckpointRef { /* private */ }
// Each of the six identifier types is Clone, Eq, Ord and Hash and has these two methods:
impl ObjectName {
    pub fn parse(text: &str, max: IdentMax) -> Result<ObjectName, IdentError>;
    pub fn as_str(&self) -> &str;
}
pub struct IdentError { pub kind: IdentKind, pub fault: NameFault }
pub enum IdentKind { Object, Lease, ConsumerGroup, View, Column, Checkpoint }
pub enum NameFault { Empty, TooLong { len: usize, max: u16 }, Byte { index: usize }, DotSegment }

// grdr_ports::tenant::authority
pub struct MintAuthority { /* private: Arc<dyn TenancyTable>, the clock's `now` and `monotonic`; neither Clone, Copy nor Default */ }
impl MintAuthority { pub fn issue<C: Clock + 'static>(table: Arc<dyn TenancyTable>, clock: Arc<C>) -> Result<MintAuthority, AlreadyIssued>; }
pub struct AlreadyIssued;
pub struct MemberReadAuthority<A> { /* private: Arc<Admitted<A>>; neither Clone, Copy nor Default */ }
impl<A: RelationalAdapter> MemberReadAuthority<A> { pub fn new(relational: Arc<Admitted<A>>, authority: &MintAuthority) -> MemberReadAuthority<A>; }

// grdr_ports::tenant::ctx
pub use grdr_model::{DelegationId, DelegationSnapshotId, OrgId, ProviderId};
pub enum TenantCtx { Single(SingleCtx), Set(SetCtx) }
pub struct SingleCtx { /* private: OrgId, Lifecycle, OrgWork, Option<DelegationRef> */ }
pub struct SetCtx { /* private: DelegationSnapshotId, ProviderId, SetPurpose, Timestamp (the token's expiry) */ }
pub struct MemberCtx { /* private: OrgId, DelegationSnapshotId, DelegationRef, Timestamp (the set's expiry) */ }
pub enum SetPurpose { Workbench }
pub enum TenantScope<'a> { Single(&'a OrgId), Set(&'a DelegationSnapshotId) }
pub enum OrgRead<'a> { Single(&'a SingleCtx), Member(&'a MemberCtx) }
pub enum Lifecycle { Provisioning, Active, Suspended, KeyUnavailable, Detached, Migrating, Migrated, Deleting, Shredded, Unconfirmed }
pub enum OrgWork { Ingest(Lane), Process, Enrol, Read, Change, Export, Maintain }
pub enum Admission { Allowed, Deferred, Refused }
#[non_exhaustive]
pub enum Refusal { Deferred { state: Lifecycle, work: OrgWork }, Refused { state: Lifecycle, work: OrgWork }, LifecycleUnknown, DelegationNotActive, DelegationUnconfirmed, Expired }
pub struct DelegationRef { /* private: DelegationId, epoch u64 */ }

impl SingleCtx {
    pub fn org(&self) -> &OrgId; pub fn lifecycle(&self) -> Lifecycle; pub fn work(&self) -> OrgWork;
    pub fn delegation(&self) -> Option<&DelegationRef>; pub fn answer(&self) -> Admission;
}
impl Lifecycle { pub fn answer(self, work: OrgWork) -> Admission; }
impl OrgWork { pub fn writes(self) -> bool; }
impl DelegationRef { pub fn new(id: DelegationId, epoch: u64) -> DelegationRef; pub fn id(&self) -> &DelegationId; pub fn epoch(&self) -> u64; }
impl SetCtx { pub fn snapshot(&self) -> &DelegationSnapshotId; pub fn provider(&self) -> &ProviderId; pub fn purpose(&self) -> SetPurpose; pub fn expires_at(&self) -> Timestamp; }
impl MemberCtx { pub fn org(&self) -> &OrgId; pub fn snapshot(&self) -> &DelegationSnapshotId; pub fn delegation(&self) -> &DelegationRef; pub fn expires_at(&self) -> Timestamp; }
impl TenantCtx { pub fn scope(&self) -> TenantScope<'_>; }
impl<'a> OrgRead<'a> { pub fn org(&self) -> &'a OrgId; }
impl From<SingleCtx> for TenantCtx;
impl<'a> From<&'a SingleCtx> for OrgRead<'a>;
impl<'a> From<&'a MemberCtx> for OrgRead<'a>;

pub trait TenancyTable: Send + Sync {
    fn lifecycle(&self, org: &OrgId) -> StateRead;
    fn delegation(&self, id: &DelegationId) -> DelegationRead;
}
pub enum StateRead { Current(Lifecycle), Stale, Unknown }
pub enum DelegationRead { Current(DelegationStatus), Stale, Unknown }
pub struct DelegationStatus { pub org: OrgId, pub provider: ProviderId, pub in_force: bool, pub epoch: u64 }

pub struct VerifiedAudience { /* private: OrgId, Option<DelegationRef> */ }
pub struct VerifiedWorkbenchToken { /* private: DelegationSnapshotId, ProviderId, SetPurpose, Timestamp */ }
impl VerifiedAudience { pub fn new(org: OrgId, delegation: Option<DelegationRef>, authority: &MintAuthority) -> VerifiedAudience; }
impl VerifiedWorkbenchToken { pub fn new(snapshot: DelegationSnapshotId, provider: ProviderId, purpose: SetPurpose, expires_at: Timestamp, authority: &MintAuthority) -> VerifiedWorkbenchToken; }
pub struct JobRecord { /* private: OrgId, OrgWork, Option<DelegationRef>; built only inside tenant, from what J-1's claim returns */ }
impl JobRecord { pub fn org(&self) -> &OrgId; pub fn work(&self) -> OrgWork; }

pub struct TenantMinter;
impl TenantMinter {
    pub fn single_from_token(token: &VerifiedAudience, work: OrgWork, authority: &MintAuthority) -> Result<SingleCtx, MintError>;
    pub fn set_from_exchange(token: &VerifiedWorkbenchToken, authority: &MintAuthority) -> SetCtx;
    pub fn single_for_step(job: &JobRecord, authority: &MintAuthority) -> Result<SingleCtx, MintError>;
}
#[non_exhaustive]
pub enum MintError { LifecycleUnknown, DelegationNotActive, DelegationUnconfirmed }

pub struct MemberCursor { /* private: OrgId */ }
impl MemberCursor { pub fn after(org: OrgId) -> MemberCursor; pub fn org(&self) -> &OrgId; }
pub struct SnapshotMember { pub org: OrgId, pub delegation: DelegationRef }
pub struct SnapshotPage { pub members: Vec<SnapshotMember>, pub next: Option<MemberCursor> }
pub struct MemberPage { pub members: Vec<MemberCtx>, pub withdrawn: Vec<OrgId>, pub unconfirmed: Vec<OrgId>, pub next: Option<MemberCursor> }
pub async fn members<A: RelationalAdapter>(reads: &MemberReadAuthority<A>, set: &SetCtx, after: Option<&MemberCursor>, limit: PageLimit) -> Result<MemberPage, RelError>;

pub struct TenantKey<K> { /* private: OrgId, K */ }
impl<K> TenantKey<K> { pub fn new(ctx: OrgRead<'_>, key: K) -> TenantKey<K>; }

// grdr_ports::tenant::mint (re-exported from grdr_ports::storage, ::storage::bus and ::storage::events)
pub struct PortsCall<S: ?Sized> { /* private: PhantomData<fn(&S) -> &S>; built only inside tenant; neither Clone, Copy nor Default */ }
pub struct Admitted<A> { /* private: A, the authority's table and clock, and the witness and opening time of a transaction or result stream */ }
impl<A> Admitted<A> { pub fn new(adapter: A, authority: &MintAuthority) -> Admitted<A>; }
pub enum Dispatch<A, B> { First(A), Second(B) }
impl<A: SubscriptionAdapter, B: SubscriptionAdapter> SubscriptionAdapter for Dispatch<A, B>;
impl<A: ResultStreamAdapter, B: ResultStreamAdapter> ResultStreamAdapter for Dispatch<A, B>;

pub struct OrgBatch { /* private: PartitionId, OrgId, Option<DelegationRef>, Result<SingleCtx, MintError>, Vec<Message> */ }
impl OrgBatch {
    pub fn partition(&self) -> PartitionId; pub fn org(&self) -> &OrgId;
    pub fn ctx(&self) -> Result<&SingleCtx, &MintError>; pub fn messages(&self) -> &[Message];
    pub fn lake_batch(&self, message: usize, rows: Vec<TableRows>) -> Option<LakeBatch>;
}
pub struct Fetched { pub batches: Vec<OrgBatch>, pub unattributed: Vec<Unattributed> }
pub struct Unattributed { pub partition: PartitionId, pub offset: Offset }
pub async fn fetch_batches<S: Subscription>(subscription: &mut S, max: FetchLimit, authority: &MintAuthority) -> Result<Fetched, BusError>;
pub struct LakeBatch { /* private: SingleCtx, Offset, Headers, ArchiveBatch, Vec<TableRows> */ }
impl LakeBatch {
    pub fn ctx(&self) -> &SingleCtx; pub fn source(&self) -> Offset; pub fn headers(&self) -> &Headers;
    pub fn archive(&self) -> &ArchiveBatch; pub fn rows(&self) -> &[TableRows];
}

pub struct Planned<P> { /* private: OrgId, P, its context's work kind, delegation and expiry; built only inside tenant */ }
impl<P> Planned<P> { pub fn org(&self) -> &OrgId; pub fn into_inner(self) -> P; }
impl<A, B> Planned<Dispatch<A, B>> { pub fn split(self) -> Dispatch<Planned<A>, Planned<B>>; }
pub async fn plan_query<E: Events>(events: &E, ctx: OrgRead<'_>, query: QueryIr, limits: QueryLimits) -> Result<Planned<E::Plan>, EventsError>;
pub struct OrgRows<R> { /* private: R; built only inside tenant */ }
impl<R: ResultStream> OrgRows<R> { pub async fn next(&mut self) -> Result<Next, EventsError>; }
pub async fn run_query<E: Events>(events: &E, plan: Planned<E::Plan>) -> Result<OrgRows<E::Results>, EventsError>;

// grdr_ports::tenant::path
pub struct TenantPath { /* private: ReadPath */ }
pub struct ReadPath { /* private: ObjectKey and its parts, its context's work kind, delegation and expiry */ }
pub struct ListPrefix { /* private: the prefix, its context's work kind, delegation and expiry */ }
pub struct ObjectKey { /* private: ASCII */ }
pub enum StorageClass { Decision, Activity, Content, Observable, AggDaily, Archive { lane: Lane } }
pub enum Partition { Day(Date), Month(YearMonth) }
pub enum PartitionKind { Day, Month }
pub struct Date { /* private */ }
pub struct YearMonth { /* private */ }
impl TenantPath {
    pub fn new(ctx: &SingleCtx, class: StorageClass, partition: Partition, name: ObjectName) -> Result<TenantPath, PathError>;
    pub fn read(&self) -> &ReadPath;
}
impl ReadPath {
    pub fn new(ctx: OrgRead<'_>, class: StorageClass, partition: Partition, name: ObjectName) -> Result<ReadPath, PathError>;
    pub fn key(&self) -> &ObjectKey;
}
impl ListPrefix {
    pub fn partition(ctx: OrgRead<'_>, class: StorageClass, partition: Partition) -> Result<ListPrefix, PathError>;
    pub fn as_str(&self) -> &str;
}
impl ObjectKey {
    pub fn under(prefix: &ListPrefix, key: &str) -> Option<ObjectKey>;
    pub fn as_str(&self) -> &str;
}
impl Date { pub fn parse(text: &str) -> Result<Date, PathError>; pub fn from_timestamp(at: Timestamp) -> Date; pub fn as_str(&self) -> &str; }
impl YearMonth { pub fn parse(text: &str) -> Result<YearMonth, PathError>; pub fn of(date: Date) -> YearMonth; pub fn as_str(&self) -> &str; }
#[non_exhaustive]
pub enum PathError {
    PartitionForClass { class: StorageClass, partition: PartitionKind },
    Date(DateFault),
    KeyId(KeyIdFault),
    ClassForMember { class: StorageClass },
}
pub enum DateFault { Format { index: usize }, Range }
pub enum KeyIdFault { Empty, TooLong { len: usize }, Byte { index: usize } }

// grdr_ports::tenant::aad
pub struct KeyId { /* private: printable ASCII */ }
pub struct Aad { /* private */ }
impl KeyId { pub fn parse(text: &str) -> Result<KeyId, PathError>; pub fn as_str(&self) -> &str; }
impl Aad { pub fn for_object(path: &ReadPath, key_id: &KeyId) -> Aad; pub fn as_bytes(&self) -> &[u8]; }
```

`OrgId`, `DelegationId`, `DelegationSnapshotId`, `ProviderId`, `Timestamp` and `Lane` are grdr-model types (#18, settled by the RFC of #1710). The four ids are `Clone`, `Eq`, `Ord` and `Hash`, parse from and render to ASCII (`as_str`), and carry no authority: holding an id builds no context. `Lane` is `Decision`, `Spine`, `Bulk` or `Evidence`; there is no second lane enum (P17). `PageLimit` is `grdr_ports::storage::PageLimit` (section 6). `TenantScope` is named so because RFC 0007 (#1710) states `grdr_schema::limits::Scope`, and #1710 AC-3 refuses a type name both RFCs state; RFC 0002 renames its own while it is in review.

Contexts:
- No code outside `grdr-ports` constructs `SingleCtx`, `SetCtx`, `MemberCtx`, `JobRecord`, `OrgBatch`, `LakeBatch`, `Planned`, `OrgRows` or `PortsCall`, and none builds an `Admitted` or a `MemberReadAuthority` without the mint authority. Fields are private, and none implements `Default`, `Deserialize` or a `From` from a string or an id. The three `TenantMinter` methods, `tenant::members` and `tenant::mint::fetch_batches` are the only places that build a context.
- Every minting site is under `crates/grdr-ports/src/tenant/`, which `security/trust-core.paths` lists. `PortsCall`, `Admitted`, `Dispatch`, `OrgBatch`, `LakeBatch`, `fetch_batches`, `Planned`, `plan_query`, `OrgRows` and `run_query` live in `tenant::mint`, the port trait implementations for `Admitted` in `tenant::admit`, and their constructors are visible only inside `tenant` (`pub(in crate::tenant)`). `storage`, `storage::bus` and `storage::events` re-export the public items, so their paths in sections 6, 8 and 10 are unchanged. A change to the token, the seal, the forwarders, the grouping that keeps a batch to one organisation, the pairing of a plan with its organisation, the lifecycle table or any constructor therefore takes the trust-core review.
- There is no conversion from `SetCtx`, `MemberCtx` or `TenantCtx` to `SingleCtx`, and no way to change a context's work kind: other work needs its own mint. A write takes `&SingleCtx` or a value built from one, so a `Set` or member context calling a write does not compile.
- `TenantCtx::scope` returns the organisation or the snapshot id; adapters bind storage with its `as_str` form (`SET LOCAL grdr.orgs` or `grdr.orgset`, row-level security; object prefixes). A `SetCtx` exposes no organisation list. Its members come only from `tenant::members` (below).
- `TenantKey<K>` compares and hashes on `(OrgId, K)`, so a cache keyed by it cannot return one organisation's entry for another.
- The contexts are `Send + Sync + Clone + Debug + LogSafe`. They print and log only the organisation id or the snapshot id (data class `structural`) and implement neither `Serialize` nor `Deserialize`, so a context cannot be written out and read back. A clone kept inside the process is safe only because every store operation checks it again (Lifecycle, below), against the organisation's current state, the context's delegation and, for a set or member context, its expiry by the authority's clock.
- The contexts will also carry the acting principal and the purpose from the token (D-35), behind private fields filled from the verified input types. Adding them changes no port signature. The accessors the audit and usage-ledger adapters read arrive with the audit item by amendment (section 12).

Minting boundary. Every way to a context needs the mint authority or a value only the authority could have made. The boundary stops module code that is mistaken or unreviewed. Hostile code compiled into the server process is ADV-9 (design/02), which dependency admission and the trust-core evaluators answer, not this boundary.
- **The authority.** `MintAuthority::issue(table, clock)` succeeds once per process and fails `AlreadyIssued` (`GRDR-TENANT-0009`) after that. It binds the process's one tenancy table and its `Clock` (RFC 0008): every mint, every check below and `tenant::members` read the table and the time from the authority, and no function takes a table or a `now`. The composition root builds the replica's table, which answers `Unknown` until it has loaded, and issues the authority with it and the process clock before any other code of the program runs. The server does not start if `issue` fails, so code that took the authority first stops the start rather than holding it unseen. The composition root passes the authority only to the runners `architecture.toml` lists: the authentication middleware of `api` and `ingest`, the partition consumer runners, and with J-1 the job runner. It also needs the authority to admit adapters (Rule 12), to mint the process's `HolderId` (section 7) and, with D-35's workbench, to build the `MemberReadAuthority` its read path holds. In a test process the kit is the composition root: `grdr_ports_testkit::authority()` issues it on first use with the kit's `MemTenancy` and `ManualClock`, and no program links the kit (Rule 1).
- **Types, not names.** ARCH-029 `context-mint` reads the type of every expression, binding, argument and return value after name resolution and type inference, so an alias, a re-export, a generic parameter, an inferred binding and a macro's output are judged as the types they are. A value holds a capability type when its type is one or contains one through a field, an enum variant, a reference, a generic argument or a closure's captures, and a value coerced to a trait object or a function pointer is judged by its type before the coercion. For each capability type `architecture.toml` lists the modules that may hold a value of it: `MintAuthority` the composition root, the listed runners and the kit; `MemberReadAuthority` the workbench read path; `VerifiedAudience` and `VerifiedWorkbenchToken` the middleware; `JobRecord` the job runner; `PortsCall` the adapter trait methods that receive it; every other capability type any module, because only `tenant` builds one. A value that holds a capability type fails wherever it reaches a module the list does not give that type: as an argument, a return value, a field, a binding or a capture. So a handle, a closure or a boxed function that carries the authority fails in an unlisted module as the authority itself does. A listed module keeps no such value in a `static` or a thread-local, except the kit's `authority()`. Every holder of the authority could build an `Admitted`, so ARCH-029 also fails a call of `Admitted::new`, judged by resolved path, outside the composition root and the kit.
- **Entry points.** The middleware builds `VerifiedAudience` and `VerifiedWorkbenchToken` after it has verified the token, which takes the authority, and mints with `single_from_token` and `set_from_exchange`.
- **Stored records.** `fetch_batches` (section 8) and, with J-1, `single_for_step` take the authority. A claimed job yields a `JobRecord`, whose only use is `single_for_step`; it exposes no value another mint accepts. There is no mint from a bare organisation id.
- **Delegation snapshots.** `tenant::members` takes the `SetCtx` and a `MemberReadAuthority`, which the composition root builds from the authority and the store's own admitted `Relational` and which does nothing else: it admits no adapter, mints no single context and reaches no `fetch_batches`. So member ids come from the store's snapshot rows only, the authority's table decides which are in force, and a row whose delegation the table records for another organisation, or for a provider other than the set's, is withdrawn (below).

No adapter is a minting site: adapters return plain ids and `grdr-ports` mints, so adding an adapter needs no protected change.

Adapter-defined witnesses. `Events::Plan`, `Events::Results`, `Relational::ReadTx`, `Relational::WriteTx` and `Bus::Subscription` are types the adapter chooses. The port closes each by type:
- An Events plan reaches `execute` only inside `Planned<P>`, which only `plan_query` builds: it calls the adapter's `plan` under the context and pairs the result with the context's organisation. `Planned` gives no `&mut` to the plan, and `execute` takes `Planned<Self::Plan>`, so a plan module code builds itself, from the adapter's own type, does not reach the adapter (E0308), and a `Planned` it builds does not compile (E0451). `execute` serves the organisation of `Planned::org` and no other (section 10).
- Rows reach module code only through `OrgRows<R>`, which only `run_query` builds, from the stream the adapter's `execute` returned for a `Planned`. `ResultStream::next` takes a call token, so a stream module code builds itself cannot be read (E0624), and an `OrgRows` it builds does not compile (E0451).
- A subscription is held as `Admitted<S>`, which gives module code no access to `S`, and `fetch_batches` accepts only the sealed `Subscription`.
- A transaction is held as `Admitted<T>`. A repository is implemented on the adapter's transaction type (question 2) and reaches it through `ReadTx::adapter_mut` or `WriteTx::adapter_mut`. Code that holds a `&mut T` could put another `T` in its place, which matters only if it can build one bound to another organisation. So ARCH-029 checks, on macro-expanded code, that a type an adapter names as its `ReadTx` or `WriteTx` has no public field, no public function that returns it outside its adapter trait implementation, and none of `Default`, `Deserialize`, `From`, `TryFrom` and `FromStr`. An enum each of whose variants holds such a type passes, which covers the generated dispatch's transaction enums. The slice-0 lint item has a case for each: a `WriteTx` with a public field fails, one that implements `Default` fails, and a generated two-variant enum passes.

Forwarders. Generated code holds no token, so a generated dispatch cannot pass `PortsCall<Dispatch>` on to an adapter. Every adapter trait with a method that takes `PortsCall<Self>` is therefore implemented for `Dispatch` in `tenant::mint`, and the generated dispatch names `Dispatch` as that type, nested for more than two adapters. In slice 0 these are `SubscriptionAdapter` and `ResultStreamAdapter`. A generated Events dispatch passes a plan on with `Planned::split`, which keeps the plan's organisation. The RFC that adds a later token-taking method adds its `Dispatch` implementation in the same text. J-1's claim method is the first: its amendment either puts the method on an associated type that `Dispatch` implements, or implements the Jobs adapter trait for `Dispatch` in `tenant::mint`, and the lead of J-1 plans that forwarder.

Lifecycle. Every `SingleCtx` carries the work kind it was minted for and the organisation's lifecycle state as its minting site read it from the replica's `TenancyTable`, which the minting site uses to choose its response; every store operation reads the state again (below). `TenancyTable` is the replica's in-memory copy of each organisation's state and of each delegation's state and epoch, refreshed by bus notification as design/21 section 5 refreshes delegation epochs; how it reads the rows is question 3. It is not a port. The server implements it over that copy, and the composition root binds that one implementation when it issues the authority, so every mint and every check reads the same table.
- `StateRead::Current(s)` mints with `s`. `Stale`, a copy older than its `limits.toml` bound, mints with `Unconfirmed`, which is not a state of design/21 section 13: it counts as the most restrictive state that still serves P4, so its row defers every work but reads, and the replica raises Degraded. `Unknown` fails `LifecycleUnknown` (`GRDR-TENANT-0008`) at a mint and at every store operation, and the replica raises Degraded with that code, so a replica that holds no state for the organisation refuses the work and shows it; it never assumes one.
- The work kind comes from the minting site: the kind the request's route declares, as data, at the middleware; `Process` at `fetch_batches`, for every consumer of admitted messages; the kind the job's kind declares at J-1's step, which J-1's job-kind registration records.
- `Lifecycle::answer(work)` reads the table below. `grdr-schema` generates it as a constant from `schema/tenancy/lifecycle.toml`, and generation fails on a missing, extra or unparseable cell, so `answer` is total and the table is data (P14).
- Every store operation runs one check, in `Admitted`, which keeps the authority's table and clock. Each port method that takes a witness, each use of a relational transaction (`adapter_mut` and `commit`, section 9) and each `OrgRows::next` run it before the adapter sees the call. Every witness carries the organisation, work kind (`Read` for a member context), delegation and expiry of the context it was built under:
  - an expiry the authority's clock has passed fails `Expired`;
  - a delegation is judged in the order below ("Provider work and delegations");
  - the state is read from the table as a mint reads it, so a state the table does not hold fails `LifecycleUnknown`; a read needs the state's answer for the work kind to be `Allowed`, and a write also a work kind that writes (every kind but `Read` and `Export`).

  A failure is the port's `Refused(Refusal)`. A `Set` read names no organisation and no delegation, so its check is the expiry. The snapshot binding of design/21 section 2, as section 14 amends it, drops a member from the rows it reaches at the next statement once the member's delegation is revoked, expired or rebound, or the member is `shredded` (section 9). A context, path, plan or transaction kept past a change of state or delegation therefore reads and writes nothing the new state or delegation refuses, except rows `append` already buffered (section 10) and a borrow of a relational transaction already taken, which the transaction's bound ends (section 9). `Bus::append` to the `usage` stream needs only the current answer to be `Allowed`, whatever the kind, because a usage record meters work that was allowed to start.
- A minting site reads `SingleCtx::answer` to choose its response, and nothing branches on `Lifecycle`: `ingest` answers `Deferred` with a spread `retry_after_ms` and `Refused` with the code; `api` refuses with the code, for reads as for changes; a consumer handles its batch as below.

| State | Ingest `decision`, `spine` | Ingest `bulk`, `evidence` | Process | Enrol | Read | Change | Export | Maintain | From |
|---|---|---|---|---|---|---|---|---|---|
| `provisioning` | refused | refused | refused | refused | allowed | allowed | refused | allowed | proposed: the move to `active` needs keys, a roster or provider owner, and a first group |
| `active` | allowed | allowed | allowed | allowed | allowed | allowed | allowed | allowed | |
| `suspended` | allowed | deferred | allowed | refused | allowed | refused | allowed | allowed | section 13; `bulk` and `evidence` deferred, so devices keep them, and Process proposed |
| `key_unavailable` | deferred | deferred | deferred | deferred | allowed | refused | deferred | allowed | section 11 for ingest, processing ("detection pauses") and reads, which fail at the Keys port and show "could not look"; design/20 section 4 step 7; the other cells proposed |
| `detached` | allowed | allowed | allowed | allowed | allowed | allowed | allowed | allowed | section 13: a running state |
| `migrating` | allowed | allowed | allowed | allowed | allowed | allowed | allowed | allowed | proposed: it runs until its devices are redirected |
| `migrated` | refused | refused | refused | refused | allowed | refused | allowed | allowed | section 13: a read-only copy; Process and Maintain proposed |
| `deleting` | allowed | deferred | allowed | refused | allowed | refused | allowed | allowed | proposed: as `suspended`, so the owner can export and cancel (section 12) |
| `shredded` | refused | refused | refused | refused | refused | refused | refused | allowed | section 13; Maintain is the purge after the point-in-time window |
| `unconfirmed` | deferred | deferred | deferred | deferred | allowed | deferred | deferred | deferred | not a state: the replica's copy is stale |

Process is a consumer handling messages that `ingest` already admitted. Maintain is retention, compaction, reduction, erasure and the purge, which D-57 requires in every state that holds data. `key_unavailable` refuses a change because every change writes its `audit.admin` record through the outbox into the checkpoint chain (design/21 section 12), which waits for the key, and a change with no record never exists. The proposals go to design/21 (section 14).

Consumers. A batch whose answer for Process is `Allowed` is processed. One that is `Deferred` is skipped as design/20 section 4 step 7 skips an organisation whose key cannot be unwrapped: the consumer records the skipped device ranges and lets the partition advance, and `ingest` rewinds those lanes once the answer is `Allowed` again. One that is `Refused` is skipped and counted: a `migrated` or `shredded` organisation's data has no home here. A batch whose context failed to mint is handled as `Deferred` for `LifecycleUnknown` and `DelegationUnconfirmed` and as `Refused` for `DelegationNotActive`, and the consumer reports the code. A consumer that writes a non-allowed batch anyway is refused by the port, so the rule fails closed.

Provider work and delegations. Work that writes into several organisations, such as a baseline rollout ring by ring (D-11), runs as one job per organisation; no cross-organisation write context exists. A context carries the delegation and epoch of the token its work began under, and every way work reaches a store checks them against the authority's table, whose answer is a `DelegationRead`:
- `Current` for the context's organisation at the recorded epoch with the delegation in force (`active` or `expiring`, design/21 section 5) passes.
- `Current` for another organisation, or at the recorded epoch and not in force, or at an epoch above the recorded one, fails `DelegationNotActive` (`GRDR-TENANT-0005`): the delegation is not this organisation's, or was revoked, expired or rebound after the work began, so the work is refused.
- `Current` at an epoch below the recorded one, `Stale` (a copy older than its `limits.toml` bound) and `Unknown` fail `DelegationUnconfirmed` (`GRDR-TENANT-0012`), so the work is deferred: the replica cannot confirm the delegation, and a delegated read does not serve P4.

The checks are these:
- `single_from_token` checks the token's delegation, as the API checks epochs on each request.
- The bus stores the context's delegation with each message it appends (Rule 4), and `fetch_batches` checks it before it mints the batch's context. A provider's command still queued on the `control` stream when the owner revokes is not dispatched.
- With J-1, a job records the delegation of the context that enqueued it, and `single_for_step` checks it at every step. Revocation increments the epoch, so it takes effect at the job's next step, as it does at the API's next request (design/21 section 5: "Revocation by the organisation owner is immediate").
- Every store operation under a delegated context, or a path, plan, batch or transaction built from one, checks it (Lifecycle, above), so a kept context, a running step's included, fails at its next call.
- A delegated relational transaction reads its delegation's revocation marker when it opens and in a write's commit step, and only that commit step takes a share lock on the delegation row, which closes the race between the check and the commit. Revocation commits the marker first, so it takes effect at once, and no open delegated transaction, nor a chain of them, holds its row update back past the transaction bound (section 9).
- `tenant::members` checks each member's delegation (below).

A job the organisation itself enqueued records no delegation. When `erase` arrives (section 12) it takes `&SingleCtx` only.

Member contexts. `tenant::members` calls `Relational::snapshot_members` (section 9) for the members of the snapshot, read under the set's binding, each with the delegation and epoch the snapshot recorded, and checks each delegation as above. It also withdraws a member whose delegation the table records for a provider other than the set's, the token's `prv` (design/21 section 5). It mints a `MemberCtx` with the set's snapshot id and expiry for each member that passes, lists in `withdrawn` those that fail `DelegationNotActive` and in `unconfirmed` those that fail `DelegationUnconfirmed`, so the reader shows "could not look" for them rather than nothing. A `MemberCtx` holds the delegation as its page read it, and every operation under it checks that delegation again, so revocation stops a provider read at its next call, and a result stream at its next batch. A `SetCtx` and each `MemberCtx` carry the workbench token's expiry (a life of 5 minutes, design/21 section 5), and every path, prefix and plan built under them carries it too. `tenant::members` and every operation under them fail `Expired` (`GRDR-TENANT-0011`) once the authority's clock has passed it, and no caller supplies the time, so a context kept past its token reads nothing more.

Each check stops one thing:
- the seal and the mint authority stop module code from minting at all;
- the authority's one table stops work the state does not permit, where the work starts and at every store operation, however long ago the context was minted;
- the delegation checks stop a provider's queued, running, stored or kept work after revocation, wherever it is picked up;
- the `Set` and member contexts stop a provider read from writing.

The middleware item and J-1 each carry their cases (section 13).

Who looked (P8, D-35). Reads through the port record nothing. The read audit entry is written above the port by `api` and `query`. A read under a `MemberCtx` records the snapshot id the context carries, which is the cross-organisation case a person most needs to see.

Paths:
- `TenantPath::new` is the only way to a writable path, and the organisation segment comes from `ctx`. A path and a prefix keep their context's work kind, delegation and expiry, which every Blobs call checks (Lifecycle, above). `ReadPath::new` builds the same key from an `OrgRead`; `TenantPath::read` returns the `ReadPath` of a writable path.
- `ReadPath::new` and `ListPrefix::partition` fail `ClassForMember` for `Content` and `Archive` under an `OrgRead::Member`: content never forwards through a delegation (design/21 section 4), and an archive segment holds content fields until its reduction.
- `AggDaily` takes only `Partition::Month`; every other class takes only `Partition::Day`; a mismatch is `PathError::PartitionForClass`.
- The rendered key is `org=<id>/class=<class>/day=<yyyy-mm-dd>/<name>`, `org=<id>/class=agg_daily/month=<yyyy-mm>/<name>`, or `org=<id>/class=archive/lane=<lane>/day=<yyyy-mm-dd>/<name>`. Class names render as `decision`, `activity`, `content`, `observable`, `agg_daily` and `archive`; lanes as `decision`, `spine`, `bulk` and `evidence`. The path vectors of #313 pin one key per class and lane, which is the case Rule 6 needs for each `StorageClass` variant.
- `ListPrefix::partition` renders the partition directory with its trailing `/`, so retention, cleanup and restore list one partition, never a whole organisation. A `Set` context cannot reach a prefix. `ObjectKey::under` turns a key an adapter listed into an `ObjectKey`, and returns `None` for a key outside the prefix or one that breaks Rule 10, so a listing cannot return a key from another organisation's prefix.
- `Date::parse` accepts exactly `YYYY-MM-DD` and `YearMonth::parse` exactly `YYYY-MM`, in ASCII digits `0` to `9` on the proleptic Gregorian calendar; Arabic-Indic or full-width digits fail with `DateFault::Format`. `Date::from_timestamp` takes the UTC date. A partition date is UTC, and retention arithmetic runs on UTC dates. It is never shown to a person as the event's local date; a view converts the event's time to the viewer's zone (D-69).
- `KeyId::parse` accepts 1 to 65,535 bytes of printable ASCII (`0x21` to `0x7E`), so a KMS key id or ARN fits and `for_object` is total.

Additional data. `Aad::for_object` produces `org_id ‖ class ‖ partition ‖ key_id` of design/21 section 2: the 11 ASCII bytes `grdr-aad-v1`, one `0x00` byte, then the organisation id, the class field, the partition value and the key id, each as a 2-byte big-endian length followed by its bytes. The class field is the class name, and for `Archive { lane }` it is `archive.<lane>`, for example `archive.decision`, so a segment does not authenticate under another lane's path. Lane decides retention (13 months for `decision`, 184 days for the others; values from configuration, read by R-3) and reduction. The partition value is `yyyy-mm-dd`, or `yyyy-mm` for `AggDaily`. Test vectors shared with `grdr-tenancy-ref` pin the bytes (#311, #313).

The object key layout, the identifier rule of Rule 10 and this encoding are a storage format. Changing any of them needs an RFC, a new tag (`grdr-aad-v2`), readers that accept the old tag for the longest retention (13 months), and a rewrite job that ships in the same release. These strings are format constants of the code namespace `grdr`, not brand strings, and do not change under a rebrand.

Callers in slice 0: the composition root issues the authority and admits the adapters; the authentication middleware mints, and `ingest` and `api` act on the answer; `store` calls `fetch_batches` and writes paths (#1547); the lake read path (#1554) builds read paths and prefixes, and `query` reads through `plan_query` and `run_query`. The provider workbench read path (D-35) and J-1, which are not in slice 0, call `tenant::members` and `single_for_step`; the minting boundary is declared whole now so the trust-core review sees every minting site once.

### 3 and 4. Clock, Entropy and the retry executor
Moved to RFC 0008 (#1924). This RFC uses `Clock`, `Entropy`, `Monotonic`, `ManualClock`, `SeededEntropy`, `block_on` and `Stalled` as RFC 0008 defines them.

### 5. Conformance kit (the storage kit item, with every port item)
```rust
// grdr_ports_testkit
pub use conformance::{reach, Reached, StopPoint};
pub fn authority() -> Result<&'static MintAuthority, AlreadyIssued>;
pub fn tenancy() -> &'static MemTenancy;
pub fn clock() -> &'static ManualClock;

// grdr_ports_testkit::conformance
pub trait Fixture: Send + Sync {
    type Adapter: Send + Sync + 'static;
    type Leases: LeasesAdapter + 'static;
    fn open(&self) -> impl Future<Output = Result<Arc<Self::Adapter>, FixtureError>> + Send;
    fn leases(&self) -> Arc<Self::Leases>;
    fn block_on<T: Send>(&self, future: impl Future<Output = T> + Send) -> Result<T, Stalled>;
    fn spawn(&self, task: Pin<Box<dyn Future<Output = ()> + Send + 'static>>);
    fn settle(&self) -> Result<(), Stalled>;
    fn stop_at(&self, point: StopPoint, mode: StopMode) -> Result<Stop, FixtureError>;
    fn induce(&self, fault: Fault) -> Result<(), FixtureError>;
}
pub trait RelationalFixture: Fixture {
    fn snapshot(&self, id: &DelegationSnapshotId, members: &[SnapshotMember]) -> impl Future<Output = Result<(), FixtureError>> + Send;
}
pub enum StopPoint {
    FlushAfterSegments, FlushAfterLakeFiles, FlushBeforeNotify, CommitAfterFenceCheck,
    AppendBeforeVisible, BusSubscribeAfterRead, BusCommitBeforeUpdate, TailBeforeRead,
}
pub enum StopMode { Crash, Pause }
pub struct Stop { /* private */ }
impl Stop { pub fn reached(&self) -> bool; pub fn resume(self); }
pub fn arm(point: StopPoint, mode: StopMode) -> Stop;
pub fn reach(point: StopPoint) -> impl Future<Output = Result<(), Reached>> + Send;
pub struct Reached { /* private: StopPoint */ }
pub enum Fault { Store(StoreFault), TailUnavailable }
pub enum FixtureError { CannotStop(StopPoint), CannotInduce(Fault), Open(StoreFault) }

pub enum CaseKind { Contract, Crash, Differential }

// Amendments of RFC 0008 section 5: Case<S> and CaseResult gain `pub kind: CaseKind`, and Outcome gains
// NotApplicable(Fault). Each storage suite's constructor takes a Fixture as the subject, for example
// grdr_ports_testkit::storage::blobs::conformance:
pub fn suite<F: Fixture>() -> Suite<F> where F::Adapter: BlobsAdapter;

// grdr_ports_testkit::tenancy
pub struct MemTenancy { /* private */ }
impl MemTenancy {
    pub fn new() -> MemTenancy;
    pub fn set_state(&self, org: &OrgId, state: StateRead);
    pub fn set_delegation(&self, id: &DelegationId, read: DelegationRead);
    pub fn unknown_answers(&self) -> u64;
}
impl TenancyTable for MemTenancy;
```

This section amends RFC 0008 section 5 (#1924), whose `Case`, `Failure`, `Suite`, `Outcome`, `CaseResult`, `Report` and runner rules stand. It adds `kind` to `Case` and `CaseResult`, the outcome `NotApplicable(Fault)` and the storage suites. `passed()` stays true when no case failed, so a `NotApplicable` case, which names its fault, does not fail a report.

Rules of the kit:
- A storage suite is generic over a `Fixture` whose `Adapter` implements its port's adapter trait. The suite admits it with the kit's authority and drives it through the port trait, so every case also exercises the `Admitted` forwarder. Cases share the fixture's store. Each case isolates itself with organisation ids, names and lease names drawn fresh from `SeededEntropy` seeded by `seed`, and none assumes an empty store, so a suite runs against a shared PostgreSQL database or bucket. The report records the seed, so a failure replays.
- `open` returns a handle over the fixture's durable state; a second call models a process restart, or a second process where the fixture keeps the first handle open. `leases` returns the lease store the adapter's fenced commits check: for Events and Relational it is the lease table in the same store (Rule 5).
- No fixture method takes or returns a tenant context. `RelationalFixture::snapshot` writes the rows of a delegation snapshot with the given id and members, by the adapter's own SQL behind its `testkit` feature. The suite mints every context a case uses with the kit's authority, whose table is `tenancy()`, the kit's `MemTenancy`, and whose clock is `clock()`. A case sets in the table the states and delegations it needs, sets each expiry from the clock's reading, and advances the clock to pass one. `unknown_answers` counts the `Unknown` answers the table gave, which stand for the replica's Degraded signal in a case. `Suite::run` holds the clock with the arming state, so no other suite moves it.
- `block_on`, `spawn` and `settle` run futures on the adapter's own executor. The in-memory fixtures use the kit's `block_on` with their own poll bound; a network adapter uses its runtime. `Stalled` means the future did not finish within the fixture's own wait bound.
- `stop_at` arms one point in the adapter's next operation that reaches it. `Crash` makes that operation return at the point and leaves durable state as a process kill there would, with no clean-up; the case then calls `open` again. `Pause` holds the operation at the point until `resume`. The bus points sit just before the stamping statement of `subscribe`, after any read the adapter makes, and just before the conditional update of `commit`, so a case can place a second operation inside the first. `FlushBeforeNotify` sits in a flush after its catalogue commit is visible and its rows are dropped from the buffer, and before any file-list cache learns of the commit. `TailBeforeRead` sits in a holder's answer to a tail read after it reads its buffer and before it checks its fence and reads its floor (section 10). A Crash case uses only `Crash`; a Contract case may use `Pause`.
- Arming lives in the kit. `stop_at` arms a point through `arm`, or returns `CannotStop` for a point the adapter has no hook for. `reach` is the kit's hook function: while its point is unarmed it is ready on its first poll with `Ok(())` and changes nothing; armed with `Pause` it waits for `resume`; armed with `Crash` it returns `Reached`, which the kit converts into each port's error as `Store(StoreFault::Unavailable)`. Arming is per process, and `Suite::run` holds it for the whole run, so two suites in one test process do not see each other's points.
- An adapter crate's `testkit` feature may add only two things:
  - the fixture, in a module named `testkit`;
  - hook points. A hook point is the one statement `::grdr_ports_testkit::reach(StopPoint::<point>).await?`. The leading `::` names the extern crate, so no local module or `use ... as` alias of that name can stand in for the kit, and the only argument is the point.

  The `testkit` scan of ARCH-029 fails any other use of the feature, judged on macro-expanded code and on `cargo metadata`:
  - in the crate, a `cfg` or `cfg_attr` on any other item or statement, `cfg!(feature = "testkit")` in an expression, or a hook statement of any other form;
  - in its manifest, a build script, since one can turn the feature into a `cfg` the source never names and no reading of the script tells reliably whether it does; an entry of `[features] testkit` other than an optional dependency, or a feature of one, that only the `testkit` module and the hook statements use; and a dependency named `grdr-ports-testkit` that is renamed or is not the release's own `grdr-ports-testkit` package.

  It runs on the workspace and on the distribution build's resolved closure. A crate that needs a build script moves it into a crate without the feature.
- The first case of every suite is `unarmed_reach_is_inert`: with nothing armed, `reach` is ready on its first poll with `Ok(())` for every `StopPoint`, and the kit's arming state is unchanged afterwards. The case shows that the kit's `reach` is inert, and the scan shows that every hook statement calls that `reach`; together they show that an unarmed hook does nothing. Neither says anything of the fixture module (section 12). Every report, a contrib adapter's included, must pass it.
- `induce` creates a fault the adapter must map: the in-memory references inject it; a filesystem or SQLite fixture creates the real condition (a small full volume, a read-only directory, a file held by another process). A fixture that cannot create a fault returns `CannotInduce`, and the case reports `NotApplicable` with the fault named. A release-gating adapter's item names the faults its fixture must induce.
- A fixture error carries a `StoreFault`, a stop point or a fault and never text, as RFC 0008's `Failure` does, so a driver error that echoes a connection string never reaches a report or a CI log (SD-11).
- A Differential case drives one operation sequence generated from the seed through the adapter and through the port's reference adapter (built by the suite over its own `ManualClock` and `MemLeases`) and compares every observable result. Opaque values such as offsets are compared by the pattern of equality and order they show, not by value.

Running the kit against an adapter outside this workspace:
1. Depend on `grdr-ports`, and on `grdr-ports-testkit` as an optional dependency that only your `testkit` feature enables (`testkit = ["dep:grdr-ports-testkit"]`), not renamed, both at the version of the server release you target. Until the crates are published to a registry, use a git dependency pinned to that release's tag.
2. Implement your port's adapter trait (Rule 12). Implement `Fixture` in a module named `testkit` behind your crate's `testkit` feature, with `Adapter` set to your adapter type, and a public function that builds the fixture. `open` connects to the store your own test environment names (your environment variable or configuration file; the kit reads no environment). `leases` returns a Leases adapter on the same store where Rule 5 requires it. `block_on`, `spawn` and `settle` use your runtime. `stop_at` arms a point with `arm`, and `induce` creates the fault's real condition. Put a hook statement (above) at each stop point your adapter has; it is the only other thing the feature may add, and the crate has no build script.
3. Add one test per suite, for example `let report = grdr_ports_testkit::storage::blobs::conformance::suite().run(&fixture, "example-blobs", seed); assert!(report.passed(), "{}", report.to_toml());`, and run it with `cargo test --locked -p <your crate> --features testkit`.
4. The kit runs the same test on itself with `MemBlobsFixture` and the other reference fixtures; read them as the worked example.
5. List the adapter in your `dist.toml` with its adapter type, the function that builds its fixture, and the fixture environment its conformance test needs (section 12). The distribution build generates one test per suite of the port, which calls that function under the bound `F: Fixture<Adapter = <the listed type>>`, so a fixture that hands the suite any other type, a reference adapter included, does not compile. It runs those tests in a cargo invocation of their own and admits the adapter only on its own passing report. Nothing is submitted to Loonaro or to any service.
6. A PostgreSQL fixture also runs the ordering cases on a database whose default collation is `ja-JP` (Rule 11).

A how-to page, "Write a storage adapter", under `docs/product/how-to/` (design/34) summarises on one page the adapter trait of each port, the witness each method takes, the fence form each commit uses, the code each fault returns, and these steps. The storage kit item writes it.

### 6. Blobs (#297)
```rust
// grdr_ports::storage
pub struct PageLimit { /* private: non-zero */ }
impl PageLimit { pub fn new(entries: u32) -> Option<PageLimit>; pub fn get(&self) -> u32; }
pub use crate::tenant::{ctx::Refusal, mint::{Admitted, PortsCall}};

// grdr_ports::storage::blobs (BlobsAdapter has the same methods)
pub trait Blobs: Send + Sync + Sealed {
    fn put(&self, path: &TenantPath, bytes: Vec<u8>) -> impl Future<Output = Result<ObjectMeta, BlobError>> + Send;
    fn get(&self, path: &ReadPath) -> impl Future<Output = Result<Vec<u8>, BlobError>> + Send;
    fn get_range(&self, path: &ReadPath, range: ByteRange) -> impl Future<Output = Result<Vec<u8>, BlobError>> + Send;
    fn list(&self, prefix: &ListPrefix, after: Option<&ObjectKey>, limit: PageLimit) -> impl Future<Output = Result<Page, BlobError>> + Send;
    fn delete(&self, path: &TenantPath) -> impl Future<Output = Result<(), BlobError>> + Send;
}
pub struct ObjectMeta { pub key: ObjectKey, pub len: u64 }
pub struct ByteRange { /* private: start < end */ }
impl ByteRange { pub fn new(start: u64, end: u64) -> Option<ByteRange>; pub fn start(&self) -> u64; pub fn end(&self) -> u64; }
pub struct Page { pub keys: Vec<ObjectKey>, pub next: Option<ObjectKey> }
#[non_exhaustive]
pub enum BlobError { NotFound { key: ObjectKey }, Range { key: ObjectKey, len: u64 }, Refused(Refusal), Store(StoreFault) }
```

- `put` writes an object; a `get` of that path afterwards returns exactly those bytes. The port promises nothing about a second `put` to the same path. Conditional put is used where a store has it and never required (design/20 section 3); callers name every immutable object uniquely.
- `get` returns the bytes last written; a path never written, or deleted, fails `NotFound`.
- `get_range` returns exactly the bytes `[start, end)`; an `end` beyond the object's length fails `Range` and returns no bytes.
- `list` returns at most `limit` keys under the prefix, in ascending byte order of the rendered key, strictly after `after`, with `next` set when more remain. The adapter builds each key with `ObjectKey::under`, so it never returns another organisation's key.
- `delete` removes the object: afterwards `get` and `get_range` fail `NotFound` and `list` omits the key. Deleting a path that does not exist succeeds, so a restarted job repeats no visible side effect. Noncurrent versions a versioned bucket keeps for backup expire by the bucket's lifecycle within the backup window (design/20 section 9) and are not reachable through the port. Erasure of content is by key destruction, never by `delete` alone.
- Every method runs the check of section 2 on its path or prefix and fails `Refused` before the adapter sees the call.
- Object bytes are opaque and never logged. Errors carry the rendered key only.
- Whole objects pass as `Vec<u8>`, which fits slice 0's flush outputs (32 MB); a streaming put is an amendment with L-4.
- Deployment-scoped objects (`state-log/`, `ephemeral/detect/`, the content repository) are not on this trait (question 1).

Callers in slice 0: `store` writes lake files and archive segments (#1547, `put`); the lake read path reads Parquet footers and pages (#1554, `get`, `get_range`); `store` removes objects an interrupted flush left unreferenced (#1547, `list`, `delete`).

Cleanup of unreferenced objects. Holders of different bus partitions write into the same `org=/class=/day=` prefix, so a lister sees objects another holder has written and not yet committed. `store` therefore removes an object only when no catalogue row references it and it is older than a grace from `limits.toml`, which must exceed the largest flush deadline plus the lease term. The age is measured by a clock the writer does not set, because a writer whose wall clock runs behind would otherwise name a new object old and see it deleted before its commit; #1547 chooses between an intent row written before the object and the store's own modification time, which would need a Blobs amendment.

Suite `storage::blobs::conformance`, reference adapter `MemBlobs`: one case per bullet above, `put` under a path built while the organisation was active and used after it moved to `key_unavailable` among them; `put` and `get` through paths built under a delegated context, after its delegation is revoked, and `get` and `list` through a member context's path and prefix after the kit's clock passes its expiry, each `Refused`; a cross-organisation case (objects under organisation A are never returned by a read or list under B); every `StoreFault` the fixture can induce maps to `Store` with that fault; listing order with keys that differ only in byte order. A property test in #297 compares `MemBlobs` with a `BTreeMap` model over generated sequences.

### 7. Jobs: leases (#298)
```rust
// grdr_ports::storage::jobs
pub trait Leases: Send + Sync + Sealed {
    fn acquire(&self, name: &LeaseName, holder: &HolderId, term: LeaseTerm) -> impl Future<Output = Result<Acquire, JobsError>> + Send;
    fn renew(&self, lease: &Lease, term: LeaseTerm) -> impl Future<Output = Result<Renew, JobsError>> + Send;
    fn release(&self, lease: &Lease) -> impl Future<Output = Result<(), JobsError>> + Send;
    fn check(&self, fence: &Fence) -> impl Future<Output = Result<(), JobsError>> + Send;
}
pub struct HolderId { /* private: ASCII */ }
impl HolderId { pub fn mint(clock: &impl Clock, entropy: &mut dyn Entropy, authority: &MintAuthority) -> HolderId; pub fn as_str(&self) -> &str; }
pub struct HolderLabel { /* private: ASCII; display only */ }
impl HolderLabel { pub fn new(text: &str) -> HolderLabel; pub fn as_str(&self) -> &str; }
pub struct FencingToken { /* private: u64 */ }
impl FencingToken { pub fn get(&self) -> u64; }
pub struct Fence { /* private: LeaseName, FencingToken */ }
impl Fence { pub fn name(&self) -> &LeaseName; pub fn token(&self) -> FencingToken; }
pub struct Lease { /* private: LeaseName, HolderId, FencingToken, Timestamp; built only by Admitted from a grant */ }
impl Lease { pub fn name(&self) -> &LeaseName; pub fn holder(&self) -> &HolderId; pub fn expires_at(&self) -> Timestamp; pub fn fence(&self) -> Fence; }
pub struct LeaseTerm { pub ttl: Duration }
pub enum Acquire { Held(Lease), Busy { holder: HolderLabel, expires_at: Timestamp } }
pub enum Renew { Renewed(Lease), Lost }
#[non_exhaustive]
pub enum JobsError { StaleFence, Store(StoreFault) }

// grdr_ports::adapter: what a Leases adapter returns from acquire and renew, and stores
pub enum Grant { Held { token: u64, expires_at: Timestamp }, Busy { holder: HolderLabel, expires_at: Timestamp } }
pub enum Renewal { Renewed { expires_at: Timestamp }, Lost }
pub enum LeaseState { Free { last: u64 }, Held { holder: HolderLabel, token: u64, expires_at: Timestamp } }
```

- Each lease name is in one `LeaseState`, the type every adapter and `MemLeases` store per name. A name never acquired is `Free { last: 0 }`. `release` and expiry move to `Free` with `last` set to the newest token issued, so the high-water mark survives every transition; an adapter never deletes a lease row. No boolean "held" flag exists.
- `acquire` returns `Held` with a new token, strictly greater than `last` or the held token, when the name is free, expired, or already held by the same holder. `Busy` is returned when another holder holds it unexpired. Re-acquiring by the same holder therefore supersedes that holder's earlier `Lease`: a task restarted inside one process, which shares the process's `HolderId`, gets a fence its stalled predecessor does not have.
- `renew` returns `Renewed` with a later `expires_at` and the same token while the caller's token is the newest and unexpired, and `Lost` once a newer token was issued or the lease expired.
- `release` frees the name only if the caller's token is the newest; releasing a lost lease does nothing.
- `expires_at` comes from the store's own clock and `LeaseTerm::ttl`; no method takes the caller's wall time. The 5 s renewal and 15 s expiry are `limits.toml` values the caller passes.
- `check` fails `StaleFence` unless the fence's token equals the newest token issued for the name (Rule 5). `acquire` and `renew` wait while a lease-checked commit holds the row.
- No caller builds a `Fence`, a `FencingToken` or a `Lease`. The adapter returns a `Grant` or a `Renewal`, `Admitted` builds the `Lease` from it with the name and holder the call named, and a fence comes only from `Lease::fence`. An adapter receives fences and reads their name and token. `JobsError::StaleFence`, like every `StaleFence`, carries no token.
- `HolderId` is minted once per process start through grdr-model's id constructor (ARCH-020), and minting one takes the mint authority, so only the composition root, and in a test process the kit, makes one. Nothing parses one: an adapter stores its text and compares it, and returns the stored text as a `HolderLabel`, which names the process for `Busy` and which no method accepts.
- A holder whose fence is superseded moves to `Lost` and re-enters `acquire`. That is normal after a sleep or a failover; the job runner (J-1) raises health only when it repeats past a `limits.toml` bound, so a laptop that slept shows no false alert.
- Leases belong to no organisation (a bus partition and a singleton serve every organisation on them), so the methods take no context and are deployment-scoped. The composition root hands a Leases port only to the runners that hold leases. The tenant-scoped Jobs methods (`enqueue`, `claim`, `step`, `complete`) are J-1's amendment.

Callers in slice 0: the partition consumer runner (`store` on each `events` partition) and the `migrate` lease of `Migrator::apply`.

Suite `storage::jobs::conformance`, reference adapter `MemLeases` over an injected `Clock`. `MemLeases` clones cheaply and shares its state, so the other references check fences against it. Cases: one per bullet above; many tasks racing to acquire one name, after which exactly one is `Held`; a holder that pauses past expiry while a second acquires, after which the first's `check` and `renew` fail and the second's succeed; two tasks with one `HolderId`, the second acquiring while the first holds, after which the first's `check` fails and its lease-checked commit does not land; release then acquire, and expiry then acquire, each giving a token strictly greater than any before; module code that builds a `Fence`, a `Lease` or a `HolderId`, or passes a `HolderLabel` to `acquire`, does not compile (compile-fail doctests in `grdr-ports`).

### 8. Bus (#299)
```rust
// grdr_ports::storage::bus (BusAdapter and SubscriptionAdapter have the same methods)
pub trait Bus: Send + Sync + Sealed {
    type Subscription: Subscription;
    fn append(&self, ctx: &SingleCtx, stream: Stream, bucket: VirtualBucket, messages: Vec<Outgoing>) -> impl Future<Output = Result<Appended, BusError>> + Send;
    fn subscribe(&self, group: &ConsumerGroup, stream: Stream, claims: Vec<Claim>) -> impl Future<Output = Result<Subscribed<Self::Subscription>, BusError>> + Send;
    fn commit(&self, group: &ConsumerGroup, stream: Stream, partition: PartitionId, position: Position, fence: &Fence) -> impl Future<Output = Result<(), BusError>> + Send;
    fn lag(&self, group: &ConsumerGroup, stream: Stream) -> impl Future<Output = Result<Vec<PartitionLag>, BusError>> + Send;
    fn set_bucket_map(&self, stream: Stream, map: BucketMap) -> impl Future<Output = Result<(), BusError>> + Send;
}
pub trait Subscription: Send + Sealed {
    fn fetch(&mut self, max: FetchLimit, call: PortsCall<Self>) -> impl Future<Output = Result<Vec<StoredMessage>, BusError>> + Send;
}
pub use crate::tenant::mint::{fetch_batches, Dispatch, Fetched, OrgBatch, Unattributed};
pub fn partition_lease(group: &ConsumerGroup, stream: Stream, partition: PartitionId) -> Result<LeaseName, IdentError>;

pub enum Stream { Events, DetectKeyed, Findings, Control, Usage }
pub struct VirtualBucket(pub u32);
pub struct PartitionId(pub u32);
pub struct Offset(pub u64);
pub struct MapVersion(pub u64);
pub struct BucketMap { pub version: MapVersion, pub partitions: Vec<PartitionId> }
pub struct Outgoing { pub headers: Headers, pub payload: Vec<u8> }
pub struct Appended { pub partition: PartitionId, pub first: Offset, pub last: Offset }
pub struct Claim { /* private: PartitionId, Fence, HolderId */ }
impl Claim { pub fn new(partition: PartitionId, lease: &Lease) -> Claim; pub fn partition(&self) -> PartitionId; pub fn fence(&self) -> &Fence; pub fn holder(&self) -> &HolderId; }
pub struct Position { pub offset: Offset, pub checkpoint: Option<CheckpointRef> }
pub struct PartitionPosition { pub partition: PartitionId, pub committed: Option<Position> }
pub struct Subscribed<S> { pub subscription: S, pub positions: Vec<PartitionPosition> }
pub struct StoredMessage { pub partition: PartitionId, pub offset: Offset, pub org: Option<OrgId>, pub delegation: Option<DelegationRef>, pub headers: Headers, pub payload: Vec<u8> }
pub struct Message { pub offset: Offset, pub headers: Headers, pub payload: Vec<u8> }
pub struct PartitionLag { pub partition: PartitionId, pub oldest_unprocessed: Option<Timestamp> }
pub struct FetchLimit { /* private: non-zero */ }
impl FetchLimit { pub fn new(messages: u32) -> Option<FetchLimit>; pub fn get(&self) -> u32; }
#[non_exhaustive]
pub enum BusError {
    Full { stream: Stream, partition: PartitionId },
    Regress { partition: PartitionId, committed: Offset },
    BeyondLog { partition: PartitionId, last: Option<Offset> },
    Bucket { bucket: VirtualBucket, count: u32 },
    MapVersion { current: MapVersion },
    StaleFence { partition: PartitionId },
    Refused(Refusal),
    Store(StoreFault),
}
```

`Headers` is a closed struct with one typed field per header of design/20 section 4 step 4 other than `org`, `received_at` among them, and no free key (#299). The bus writes `org` and the delegation itself and returns them only as `StoredMessage::org` and `StoredMessage::delegation`.

- `append` writes every message to the one partition the current `BucketMap` gives the bucket, and returns that partition and the first and last offsets, contiguous and ascending in input order. A bucket at or above the map's length fails `Bucket`. Each stored message carries the context's organisation as its `org` header and the context's delegation, if it has one, beside it. When the stream's byte bound (a value the adapter is built with) would be exceeded, `append` fails `Full`, stores nothing, and names the stream and partition so `ingest` can answer with a spread `retry_after_ms`.
- Offsets within a partition are strictly increasing in the order appends become visible: a consumer never sees offset n+1 before n.
- The fence of every claim and of every commit must be of the partition's own lease, `partition_lease(group, stream, partition)`, which renders `<group>.<stream>.<partition>` and fails `IdentError` when that would pass 255 bytes. `Admitted` refuses any other fence with `StaleFence` before the adapter sees it, so the fence of one partition's lease cannot claim or commit another partition. A runner acquires that name for each partition it consumes, and a `Claim` comes only from `Claim::new(partition, &lease)`.
- `subscribe` handles each claim as one compare-and-set on the partition's consumer row `(group, stream, partition)`: create the row with fence 0 if absent, then set `fence` and `holder` to the claim's where the stored fence is at or below the claim's, returning the committed position from the same statement. In PostgreSQL that is `UPDATE bus_consumer SET fence = :f, holder = :h WHERE ... AND fence <= :f RETURNING committed_offset, checkpoint`. Zero rows updated means a greater fence is stored, and `subscribe` fails `StaleFence`; claims stamped earlier in the same call stay stamped, which is harmless because each names its own acquisition. A read followed by a separate update is not this rule: at READ COMMITTED a lower fence would overwrite a higher one. `positions` returns the positions read, and the subscription starts each partition after its committed offset.
- `fetch` returns at most `max` stored messages in offset order per partition, each with the organisation from its `org` header or `None` if it has none, and the delegation stored with it. It takes a call token, so module code cannot call it: module code holds the subscription only as `Admitted<S>`, the token is zero-sized, neither `Clone` nor `Copy`, and branded `PortsCall<Self>`, and a token a wrapper receives is branded with the wrapper's type, which the inner `fetch` does not accept. The forwarding implementations are `Admitted`'s and `Dispatch`'s, inside `grdr-ports`; the generated dispatch uses `Dispatch` as its subscription type, nested for more than two adapters (section 2, "Forwarders").
- Module code calls `fetch_batches`, which takes the mint authority, builds the token, calls `fetch`, and groups consecutive messages of one partition, one organisation and one delegation into `OrgBatch` values, built inside `grdr-ports`, so a batch never mixes organisations whatever the adapter returns. Each batch carries the context `fetch_batches` minted for it, with work `Process`, the state the authority's table holds and the delegation checked (section 2), or the `MintError` that stopped it. The first message of a partition with no organisation comes back in `unattributed` with its partition and offset (`GRDR-BUS-0005`). Nothing at or after it on that partition is returned; the batches before it, and the other partitions' batches, are. The consumer stops on that partition and reports the code, because committing past a message nobody attributed would lose it (design/21 section 2).
- `commit` records the offset and the optional checkpoint in one conditional update of the consumer row: `SET committed_offset = :o, checkpoint = :c WHERE ... AND fence = :f AND (committed_offset IS NULL OR committed_offset <= :o) AND :o <= <the partition's last offset>`. A new group's row has no committed offset, so its first commit lands at any offset up to the last. When no row is updated the adapter reads the row and the partition's last offset once to say which condition failed: another fence is `StaleFence`, a higher committed offset is `Regress`, an offset past the last appended one is `BeyondLog`; none changes the row. `detect` puts its snapshot's object name in `checkpoint`, so the offset and the snapshot key move together (design/20 section 7); `store` passes `None`.
- Why the row-stamped form is safe. Between a new holder's `acquire` and its `subscribe`, the old holder's commits still land. Each one records progress the old holder made under its own fenced writes, since its lake flush is lease-checked (section 10). The new holder reads the position in the statement that stamps it, so it never starts below a commit that landed, and the old holder's later commits fail. Two `subscribe` calls with different fences end with the greater one stored, in either order. The rule other consumer groups follow is the same: commit only progress a lease-checked write or an idempotent effect has confirmed. The bus checks no lease, so `bus.database` may stay a separate instance.
- A serialisation failure, where an adapter runs these statements at a stricter isolation level, is `Store(StoreFault::Conflict)` and retryable.
- `lag` gives, per partition, the `received_at` of the oldest message after the committed offset, or `None` when the group is caught up.
- `set_bucket_map` accepts only a version greater than the current one, else `MapVersion`. Earlier versions are kept as design/20 section 6 keeps them. Removing a partition from a stream is not on the surface.
- Every `Stream` behaves the same at the port, except that `append` to `usage` checks only the current answer, whatever the work kind (section 2); partition counts and byte bounds come from configuration. Payloads are opaque bytes at the capture level the device applied; headers are `structural`. Errors carry stream, partition and offset only.
- `subscribe`, `commit`, `lag`, `set_bucket_map` and `Subscription::fetch` are deployment-scoped. `fetch` is the one that returns tenant data, so it is the one that takes the call token.
- Every shipped Bus adapter is durable on disk: the log on SQLite in WAL mode for `embedded`, the log on PostgreSQL for `ha`, NATS JetStream with file storage for `distributed` (design/20 section 7). `MemBus` is a reference only.

Callers in slice 0: `ingest` appends; `store` subscribes, calls `fetch_batches`, commits and reads lag; server bootstrap writes the first bucket map version; the dispatch #1593 generates uses `Dispatch`. `detect` uses `checkpoint` once D-1 is built; until then every commit passes `None`, and the reference and cases still cover it.

Suite `storage::bus::conformance`, reference adapter `MemBus` over an injected `Clock`. Cases: one per bullet above; an append and a fetch on every `Stream`; two `subscribe` calls with fences 6 and 7 on one row, the first paused at `BusSubscribeAfterRead` while the second runs, in both orders, after which the row holds 7 and only the holder of 7 can commit; the old holder commits after the new holder's `acquire` and before its `subscribe`, the commit lands, and the new holder's `positions` start at that offset; the old holder paused at `BusCommitBeforeUpdate` while the new holder subscribes, after which the old commit fails `StaleFence`; the first commit on a new group lands and the next `subscribe` returns it; a commit with a checkpoint returned by the next `subscribe`; a commit past the partition's last offset fails `BeyondLog` and changes nothing; a claim and a commit with the genuine fence of another partition's lease each fail `StaleFence`; module code that implements `Subscription`, by hand or through `macro_rules!`, calls `Subscription::fetch`, or relays a token through a wrapping adapter subscription, does not compile (compile-fail doctests in `grdr-ports`); `fetch_batches` over each variant of a `Dispatch` returns that variant's batches; appends from four organisations to one partition fetched in small steps, after which every batch holds one organisation and the concatenation equals the append order; a partition with a message that has no organisation returns its batches before that message, nothing at or after it, and every other partition's batches; a batch of an organisation the tenancy table holds as `shredded` carries a context whose answer for Process is `Refused`, and one it holds nothing for carries `LifecycleUnknown`; a message appended under a delegated context whose delegation is then revoked yields `DelegationNotActive`, and one whose delegation the table holds as stale yields `DelegationUnconfirmed`; an `append` under a delegated context kept after its delegation's revocation fails `Refused`; a crash at `AppendBeforeVisible`, after which no offset of that append is visible and later offsets stay contiguous.

### 9. Relational (#300)
```rust
// grdr_ports::storage::relational (the adapter traits have the same methods, except that ReadTxAdapter and WriteTxAdapter have no adapter_mut and RelationalAdapter also has `fn transaction_life(&self) -> Duration`, the bound it was built with)
pub trait Relational: Send + Sync + Sealed {
    type ReadTx: ReadTx;
    type WriteTx: WriteTx;
    fn read(&self, ctx: &TenantCtx) -> impl Future<Output = Result<Self::ReadTx, RelError>> + Send;
    fn write(&self, ctx: &SingleCtx) -> impl Future<Output = Result<Self::WriteTx, RelError>> + Send;
    fn write_fenced(&self, ctx: &SingleCtx, fence: Fence) -> impl Future<Output = Result<Self::WriteTx, RelError>> + Send;
    fn snapshot_members(&self, set: &SetCtx, after: Option<&MemberCursor>, limit: PageLimit) -> impl Future<Output = Result<SnapshotPage, RelError>> + Send;
}
pub trait ReadTx: Send + Sealed {
    type Inner;
    fn adapter_mut(&mut self) -> Result<&mut Self::Inner, RelError>;
}
pub trait WriteTx: Send + Sealed {
    type Inner;
    fn adapter_mut(&mut self) -> Result<&mut Self::Inner, RelError>;
    fn commit(self) -> impl Future<Output = Result<(), RelError>> + Send;
}
pub trait Migrator: Send + Sync + Sealed {
    fn apply(&self, plan: &MigrationPlan, fence: &Fence) -> impl Future<Output = Result<Applied, MigrationError>> + Send;
    fn check_compatible(&self, plan: &MigrationPlan, binary_release: Release) -> impl Future<Output = Result<(), MigrationError>> + Send;
}
pub struct Release(pub u32);
pub struct MigrationId { pub release: Release, pub seq: u32 }
pub struct Migration { pub id: MigrationId, pub step: Step }
pub enum Step { Expand(ExpandKind), Contract { of: MigrationId } }
pub enum StepKind { Expand, Contract }
pub enum ExpandKind { AddTable, AddColumnNullable, AddColumnWithDefault, AddIndex, AddPolicy }
pub struct RecordedMigration { pub id: MigrationId, pub step: StepKind }
pub struct MigrationPlan { /* private: ordered migrations */ }
impl MigrationPlan {
    pub fn new(migrations: Vec<Migration>) -> Result<MigrationPlan, PlanError>;
    pub fn migrations(&self) -> &[Migration];
    pub fn check_compatible(&self, recorded: &[RecordedMigration], binary_release: Release) -> Result<(), MigrationError>;
}
pub struct Applied { pub applied: Vec<MigrationId> }
#[non_exhaustive]
pub enum RelError { StaleFence, Constraint, SingleOrganisation, Timeout, Refused(Refusal), Store(StoreFault) }
#[non_exhaustive]
pub enum PlanError { Duplicate { id: MigrationId }, Order { id: MigrationId }, ContractWithoutExpand { id: MigrationId }, ContractTooEarly { id: MigrationId } }
#[non_exhaustive]
pub enum MigrationError { SchemaTooNew { id: MigrationId }, Rel(RelError) }
```

- `read`, `write` and `write_fenced` are the only ways to open a transaction. The adapter binds the context at the start of each transaction (`SET LOCAL grdr.orgs` or `grdr.orgset` from the scope's `as_str`, design/21 section 2). `ReadTx` has no write method.
- Repositories are traits implemented on an adapter's transaction types, so the transaction is the witness; they reach that type through `adapter_mut` (section 2). Where module repository traits live is question 2.
- `commit` makes the writes visible. A transaction opened with `write_fenced` holds its fence from the start and its `commit` is lease-checked by Rule 5, so code that holds the transaction cannot skip the check. On `StaleFence` the transaction rolls back and is consumed, so no stale write can be committed afterwards. Request handlers use `write`. The J-1 step API hands each step a handle whose only way to open a write is `write_fenced` with the step's fence, so a job step cannot skip it either (design/20 section 8, "every write checks").
- A delegated transaction, one opened under a context that carries a delegation, takes no lock on the delegation when it opens. Its first statement reads the delegation's revocation marker (design/21 section 5), and the opener fails `Refused(Refusal::DelegationNotActive)` if a marker newer than the context's epoch exists. A write's commit step reads the marker again, then takes `SELECT ... FOR SHARE` on the delegation row and commits only while the row holds the delegation in force at the context's epoch; otherwise it rolls back with the same refusal. Revocation, expiry and rebinding commit the marker before they update the row. Once the marker is visible no delegated transaction opens, and the row update waits at most for transactions opened before it, each refused at its next use once the replicas hold the new epoch and ended by the bound below. Open delegated transactions, however many overlap, hold a revocation back no longer than that bound.
- Every transaction ends within the `limits.toml` row `relational.transaction-life`, in `ms` and `fixed`, whose `max` is the single-organisation token's life (design/21 section 5; RFC 0007 section 6). The adapter is built with it and enforces it in the store: PostgreSQL sets `SET LOCAL transaction_timeout` in the transaction's first statement, each other adapter item names its equivalent, and `MemRelational` uses the kit's clock. `Admitted` records the opening time on the authority's clock and fails `adapter_mut` and `commit` past the bound with `Timeout` (`GRDR-REL-0008`).
- `read`, `write`, `write_fenced`, `snapshot_members`, every `adapter_mut` and `commit` run the check of section 2, against the context the transaction was opened under, and fail `Refused` before the adapter acts; a refused `commit` rolls back. A revocation or a change of state therefore stops a transaction at its next use, and a borrow already taken at the transaction's bound.
- A `Set` read transaction runs at READ COMMITTED, so each statement applies the snapshot binding (design/21 section 2, as section 14 amends it) to the latest revocation marker and delegation row.
- A dropped `WriteTx` makes none of its writes visible. The adapter may finish the rollback when the connection is next used, because `Drop` cannot await.
- `Constraint` is a constraint violation and carries no row data. A serialisation failure is `Store(StoreFault::Conflict)` and retryable.
- `snapshot_members` returns the members of the set's delegation snapshot, each with the delegation and epoch the snapshot recorded, read under the set's binding, in ascending byte order of `OrgId`, strictly after `after`, at most `limit`. Module code that needs a `MemberCtx` calls `tenant::members`, which checks each delegation and wraps each id (section 2). It takes no call token: a direct call returns only the members of the snapshot the caller's `SetCtx` already names, and ids carry no authority.
- A store that binds one organisation only (SQLite in `embedded`, D-34) fails `SingleOrganisation` for `snapshot_members`, for `read` with a `Set` context, for a `SingleCtx` of a second organisation, and for a context that carries a delegation, rather than serving any of them unisolated.
- `MigrationPlan::new` refuses duplicate ids, ids out of ascending order, a `Contract` whose `of` is not an `Expand` in the plan, and a `Contract` whose release is below its `Expand`'s release plus 2 (release N adds, N+1 reads the new form, N+2 drops the old). The SQL of each migration lives in the adapter crate, keyed by `MigrationId` (ARCH-015). `ExpandKind`'s variants behave the same at the port: the plan rules do not depend on the kind, so one case covers them.
- `MigrationPlan::check_compatible` is pure. It accepts recorded ids that are all in the plan, or whose ids outside the plan all belong to `binary_release + 1` and are all `Expand` steps (the previous binary runs on the new schema). Any other id outside the plan fails `SchemaTooNew { id }`.
- `Migrator::apply` applies, in order, each migration not yet recorded. Migrations belong to no organisation, so the adapter runs each in its own deployment-scoped transaction inside its crate, never a `WriteTx`. That transaction records the migration's id and commits by the lease-checked form of Rule 5 under the `migrate` fence.
- `Migrator::check_compatible` reads the recorded migrations once and calls the pure function. The server runs it once at start, before it serves anything; when it passes it costs one read and blocks nothing after. When it fails the server does not start, so a binary rolled back onto a newer schema is refused with `GRDR-REL-0007`, never run silently.
- `Migrator` is deployment-scoped. Tables without an organisation (runtime settings and the operator realm, D-70) need a deployment-scoped transaction for module code, which this trait does not offer (question 3).

Callers in slice 0: every module's repositories (`read`, `write`); `store`'s catalogue writes inside the Events adapter and every job step (`write_fenced`); server start (`check_compatible`) and `grdr server migrate` (`apply`). The provider workbench read path calls `snapshot_members` through `tenant::members`; it is not in slice 0 and is declared with the minting boundary of section 2.

Test kit:
```rust
// grdr_ports_testkit::storage::relational
pub struct ProbeKey { /* private: identifier */ }
pub trait ProbeRepo: RelationalAdapter {
    fn probe_put(tx: &mut Self::WriteTx, key: &ProbeKey, value: Vec<u8>) -> impl Future<Output = Result<(), RelError>> + Send;
    fn probe_get(tx: &mut Self::ReadTx, key: &ProbeKey) -> impl Future<Output = Result<Option<Vec<u8>>, RelError>> + Send;
}
pub struct MemRelational { /* per-organisation maps, snapshot table, delegation rows and revocation markers, MemLeases handle, recorded migrations */ }
```
`ProbeRepo` is a `(key, value)` repository per organisation that each adapter implements behind its `testkit` feature with its own SQL. `MemRelational` is the reference: it implements `RelationalAdapter`, `ReadTxAdapter`, `WriteTxAdapter`, `MigratorAdapter` and `ProbeRepo` over per-organisation maps, holds a `MemLeases` handle for fenced commits and delegation rows and markers for the delegated commit step, keeps a snapshot table for `snapshot_members`, and drops uncommitted writes. Suite `storage::relational::conformance`, generic over a `RelationalFixture` whose adapter is `RelationalAdapter + MigratorAdapter + ProbeRepo`. Cases: a write in organisation A is never returned by a read in B; a dropped `WriteTx` leaves nothing visible; a crash at `CommitAfterFenceCheck` leaves nothing visible; a fenced commit under a superseded fence fails and leaves nothing visible; a fenced commit paused at `CommitAfterFenceCheck` while another holder acquires, after which `acquire` was still waiting when the commit ended; a transaction under a delegated context paused at `CommitAfterFenceCheck` while the delegation is revoked, after which the revocation was still waiting when the commit ended, and a transaction opened after the revocation, a `read` included, fails `Refused`; a delegated transaction whose delegation expires before its commit fails `Refused` and leaves nothing visible; a `write` under a context minted for `Read`, and under one whose answer is `Deferred`, each fails `Refused`; a transaction opened while the organisation is active and committed after it moves to `key_unavailable` fails `Refused` and leaves nothing visible; `read` under a `Set` context, once the kit's clock passes its expiry, fails `Refused`; a read transaction opened before a revocation, or before a move to `shredded`, fails `Refused` at its next `adapter_mut`, and one kept past `relational.transaction-life` fails `Timeout` at `adapter_mut` and `commit` and has ended in the store; a kept delegated write, and overlapping delegated transactions whose share locks would chain, each leave a revocation waiting no longer than the bound (the PostgreSQL fixture); a `Set` read after a member's revocation, and after its move to `shredded`, returns none of that member's rows at its next statement; `apply` applies in order, records ids, and is a no-op on a second run; `check_compatible` accepts and refuses per the rule above; `tenant::members` returns exactly the snapshot's members whose delegations pass, lists the refused ones in `withdrawn`, rows whose delegation the table records for another organisation or another provider among them, and the deferred ones in `unconfirmed`, and pages without gap or repeat; a member context and a `Set` context cannot reach `write`, and module code that implements `Relational` or passes `tenant::members` an adapter of its own does not compile (compile-fail doctests); `SingleOrganisation` for each of its four cases on a single-organisation fixture; and a Differential case against `MemRelational`. These cases run on `MemRelational` in #300, and on SQLite and PostgreSQL in their adapter items.

### 10. Events and QueryIr (#1535)
```rust
// grdr_ports::storage::events (EventsAdapter and ResultStreamAdapter have the same methods)
pub trait Events: Send + Sync + Sealed {
    type Plan: Send;
    type Results: ResultStream;
    fn append(&self, fence: &Fence, batch: LakeBatch) -> impl Future<Output = Result<Buffered, EventsError>> + Send;
    fn flush(&self, fence: &Fence, due: FlushDue, deadline: Monotonic) -> impl Future<Output = Result<Flushed, EventsError>> + Send;
    fn plan(&self, ctx: OrgRead<'_>, query: QueryIr, limits: QueryLimits) -> impl Future<Output = Result<Self::Plan, EventsError>> + Send;
    fn execute(&self, plan: Planned<Self::Plan>) -> impl Future<Output = Result<Self::Results, EventsError>> + Send;
}
pub trait ResultStream: Send + Sealed {
    fn next(&mut self, call: PortsCall<Self>) -> impl Future<Output = Result<Next, EventsError>> + Send;
}
pub use crate::tenant::mint::{plan_query, run_query, LakeBatch, OrgRows, Planned};

pub struct ArrowIpc { /* private: bytes */ }
impl ArrowIpc { pub fn new(bytes: Vec<u8>) -> ArrowIpc; pub fn as_bytes(&self) -> &[u8]; pub fn into_bytes(self) -> Vec<u8>; }
pub struct ArchiveBatch { pub lane: Lane, pub day: Date, pub bytes: Vec<u8> }
pub struct TableRows { pub table: LakeTable, pub rows: ArrowIpc }
pub enum LakeTable { Decision, Activity }
pub struct Buffered { pub added: u64, pub duplicate: u64 }
pub enum FlushDue { Thresholds, All }
pub struct Flushed { pub committed_through: Option<Offset> }

pub enum QueryIr {
    Timeline { root_session_id: SessionId, time: TimeBounds, order: Direction, after: Option<Resume> },
    Scan {
        view: ViewName, time: TimeBounds, predicates: Vec<Predicate>,
        projection: Vec<ColumnName>, order: Direction, after: Option<Resume>,
    },
}
pub enum Direction { Ascending, Descending }
pub struct TimeBounds { /* private: from < to */ }
impl TimeBounds { pub fn new(from: Timestamp, to: Timestamp) -> Result<TimeBounds, EventsError>; pub fn from(&self) -> Timestamp; pub fn to(&self) -> Timestamp; }
pub struct RowPosition { pub observed_time: Timestamp, pub device_id: DeviceId, pub epoch: Epoch, pub monotonic_ns: u64, pub lane: Lane, pub seq: Seq }
pub struct Resume { pub position: RowPosition, pub coverage: Coverage }
pub struct Predicate { pub column: ColumnName, pub op: Comparison, pub values: Vec<Literal> }
pub enum Comparison { Eq, Ne, Lt, Le, Gt, Ge, In }
pub enum Literal { Bool(bool), Int(i64), UInt(u64), Text(String), Bytes(Vec<u8>), Time(Timestamp) }
pub struct QueryLimits { pub rows: u64, pub bytes: u64, pub wall_time: Duration, pub in_values: u32 }

pub enum Next { Batch(ArrowIpc), End(Ending) }
pub struct Ending { pub completion: Completion, pub coverage: Coverage }
impl Ending { pub fn resume(&self) -> Option<Resume>; }
pub enum Completion { Complete, Limited { reason: LimitReason, last: Option<RowPosition> } }
pub enum LimitReason { Rows, Bytes, WallTime }
pub enum Coverage { Full, WithoutTail }

#[non_exhaustive]
pub enum EventsError {
    View { view: ViewName },
    Column { column: ColumnName },
    Predicate { column: ColumnName },
    TimeBounds,
    BatchSchema { table: LakeTable },
    BatchHeader { table: LakeTable },
    BatchUnreadable,
    StaleFence,
    Refused(Refusal),
    Store(StoreFault),
}
```

`SessionId`, `DeviceId`, `Epoch` and `Seq` are grdr-model types (#1710). The adapter takes the lake column manifest (#510's type, in `grdr-schema`) and a `Clock` when it is built.

Rows cross the port as Arrow IPC. `ArrowIpc` holds one Arrow IPC stream: Arrow columnar format 1.x, a schema message and then record batches, with no dictionary deltas and no body compression. Its schema is the column manifest of the batch's table, or of the plan's projection. The contract is the Arrow format, a published standard (P10), not an arrow-rs release, and `grdr-ports` links no Arrow (Rule 1). The cost is one encode and one decode per batch.

Write path:
- A `LakeBatch` is one bus message of the `events` stream, built only by `OrgBatch::lake_batch` from a message of that batch. It carries the batch's context, the message's offset as `source`, its headers, and its bytes unchanged as the archive, with the message's lane and the UTC date of its `received_at`; the bytes keep the device-side pseudonyms the batch was signed with (D-39). `store` supplies only the rows of each table, decoded from those bytes, flattened by the column manifest, with server pseudonyms in place of device-side ones (D-51), and with no `organisation_id` column (Rule 4). The adapter adds `organisation_id` from the batch's context. It refuses with `BatchSchema` a batch whose columns differ from the manifest, `organisation_id` included, and with `BatchHeader` a row whose device, epoch, lane or sequence number lies outside the message's headers, so rows decoded from one message cannot be written under another. Bytes that are not a valid Arrow IPC stream of that profile fail `BatchUnreadable`.
- `append` takes the fence of the `store` lease on the bus partition the batch came from. It fails `StaleFence` if that fence is already superseded when called (a point-in-time check), and otherwise buffers the rows and the archive batch. A row whose key `(device, epoch, lane, seq)` is already appended or committed adds nothing; `Buffered` counts added and duplicate rows. Before `append` returns, the adapter has durably recorded the partition (its fence's lease name) in its partition record for the organisation, if it was not there yet. Once `append` returns, an `execute` that starts afterwards returns the added rows.
- `flush` commits the buffers that are due, one organisation at a time. `Thresholds` takes each organisation with a table buffer past the size or age the adapter was built with; `All` takes every organisation, and runs at the partition's bus retention bound and on lease release. For each organisation it writes the archive segments of the due batches first (`org=<id>/class=archive/lane=<lane>/day=<date>/<uuidv7>.seg`), then one Parquet object per table, then one catalogue transaction, lease-checked by Rule 5, that records the lake files, their statistics and data key ids, and the segments in `lake_archive_segment`. Only after that commit is visible does it drop the committed rows from the buffer.
- A flush that cannot seal an organisation's rows, because its key is unavailable or destroyed, drops that organisation's buffer, records its device ranges as skipped (design/20 section 4 step 7) and lets `committed_through` pass them, so one organisation never stops its partition.
- `flush` takes no witness and does not check again: it commits rows `append` admitted. A batch appended before its organisation moved to a state that refuses Process, such as `migrated`, is committed after the move by the next due flush; a `shredded` organisation's buffer is dropped as above, its key destroyed. No tenant is crossed: each row was appended under its own batch's context, from which the adapter writes `organisation_id` and the `org=` segment, and each commit covers one organisation.
- A crash anywhere before that commit leaves no catalogue row; the objects written before it are unreferenced and uniquely named, and `store` removes them after the grace of section 6. A crash after it leaves rows, files and segments all visible. No batch is ever committed without its archive segment.
- `flush` stops starting new organisation commits once `deadline` passes on the adapter's clock, and returns what committed. What it did not commit stays buffered or, on release, is dropped; the bus delivers it again because the bus offset never passes `committed_through`. Closing a laptop lid therefore never hangs the daemon on a flush.
- `committed_through` is the greatest offset `o` such that every batch appended under this fence with `source <= o` has its rows and segment committed or recorded as skipped, or `None`. `store` commits the bus offset to that value (design/20 section 5.2). It is not the sensor-facing `durable_through` of design/20 section 9, which is later and also needs backup health.
- A flush under a superseded fence fails `StaleFence` and drops that fence's buffers; the bus delivers the rows again to the new holder. A crash or forced power-off loses only buffered rows, which the bus still holds.
- `LakeTable` has no `Content` variant until content sealing (L-3) exists, so no path can write content unsealed (D-51; #1546 R5).
- Pseudonyms. `ArrowIpc` columns carry the pseudonym class, and the port cannot tell a device-side value from a server one. The guarantee that the lake holds server pseudonyms only is #1690's test (no stored `decision` or `activity` value equals its device-side source). The Events conformance suite does not claim it.

Read path:
- `plan` validates the query against the manifest and prepares it; it reads no catalogue snapshot and no buffer. An unregistered view fails `View`, an unregistered column `Column`; a predicate fails `Predicate` when a literal's kind differs from its column's manifest type, when `Eq` to `Ge` do not have exactly one value, or when `In` has none or more than `in_values`. `TimeBounds::new` fails `TimeBounds` unless `from < to`; bounds are half-open `[from, to)` on `observed_time`.
- Module code plans and reads through `tenant::mint` (section 2): `plan_query` calls `plan` and returns the plan inside `Planned`, paired with the context's organisation, work kind, delegation and expiry, which `execute` and each `next` check again (section 2); `run_query` calls `execute` with it and returns the stream inside `OrgRows`, whose `next` builds the call token `ResultStream::next` takes. `execute` serves the organisation of `Planned::org` and no other: the adapter's plan holds no organisation it reads, so a plan prepared for another organisation, paired with this one, returns this one's rows.
- `Scan` orders on `(observed_time, device_id, epoch, lane, seq)` and `Timeline` on `(epoch, monotonic_ns, lane, seq)` within its root session, ascending or descending per `order`, compared by Rule 11. `after` returns only rows strictly after `after.position` in that order.
- `execute` returns the plan's organisation's rows from committed lake files and from rows appended but not yet flushed, de-duplicated on `(device, epoch, lane, seq)`, merged in the query's order. The union is inside the port, so no caller can forget it. Buffered rows come from the adapter's own buffers and, where the buffer lives in another process, from the tail source the adapter was built with (`grdr.internal.v1alpha1.StoreTail` in `distributed`, design/20 section 5.2).
- `execute` asks for buffered rows on every partition in the adapter's partition record for the organisation: every partition under whose fence a row of the organisation was appended. `append` writes the record before it returns, so a row appended before `execute` starts is on a partition the record names. `execute` reads the record where it is written: in one process from the adapter's own state, otherwise from the catalogue's primary (`lake_org_partition`, design/20 section 5.4), never from a cache, because a cached record from before a partition's first row for the organisation would not ask that partition and no answer could say so. Removing a partition from a stream is not on the surface (section 8), so no partition leaves a record in slice 0. The amendment that adds removal also removes a drained partition from each record, in the flush commit that empties it, and keeps that commit's version as a floor of every later read.
- `execute` reads the buffered rows first, then fixes the catalogue snapshot it selects files from. A flush drops rows from its buffer only after its catalogue commit is visible.
- Each answer, from the adapter's own buffers or from the tail source, carries a floor for that organisation. A floor belongs to one fence, never to a `HolderId`, so a holder that re-acquires (section 7) starts a new one. It is the greater of two catalogue versions (`lake_org_head` snapshots, design/20 section 5.4):
  - the newest one whose commit dropped rows from that fence's buffer;
  - the one the fence's holder read on the catalogue's primary, where commits are made, after its `acquire` returned. The holder reads it the first time it answers for the organisation under that fence.

  Rule 5 makes every lease-checked commit under an earlier fence end before `acquire` returns, so the second version covers every row an earlier holder, or an earlier tenure of the same holder, committed.
- A holder answers in this order: it reads its buffer, checks its fence with `Leases::check`, then reads its floor. A fence that is no longer the newest answers as a failed tail, so an answer from a holder that has lost its lease never counts. The floor is read after the buffer, or in the same step, because a drop between a floor read and a later buffer read would leave the row in neither.
- The snapshot `execute` fixes is at or after the greatest floor among the answers. A cached file list (design/20 section 5.8) at or after that floor may serve as the snapshot. A source older than the floor, such as a cache whose invalidation has not arrived or a catalogue replica that lags, is not used, and `execute` reads the file list from the catalogue's primary. The floor is internal to the adapter and its tail source; no port type carries it.
- A partition with no holder, whose holder does not answer, or whose holder's fence was superseded before it answered, is a failed tail, so the read ends `WithoutTail` (below).
- A row appended before `execute` starts is therefore in the buffer read or in the files selected, never missing from both. That holds whenever `plan` ran, however late a cache learns of a commit, whichever holder committed the row, and whichever partition the organisation was on. The one exception is a row whose holder lost its lease before committing it. That holder drops its buffers, and the row is on the bus only until the next holder appends it again. The window opens when the old fence is superseded and closes when the new holder has re-appended everything up to the old holder's last appended offset; a read inside it can end `Full` without that row. `Bus::lag` shows the window, and a read run after it returns the row.
- Coverage. An ending's `coverage` is `Full` when the buffered rows of every partition were read. It is `WithoutTail` when the tail source failed or passed its own budget, or when a partition had no holder or no holder under a current fence, and in that case the stream still returns the lake rows. The ending holds its coverage once, in `Ending::coverage`. `Ending::resume` returns `Resume { position: last, coverage }` for a `Limited` ending that returned a row and `None` otherwise, so the position and the coverage a caller resumes with come from one value. A read resumed from a `Resume` whose coverage is `WithoutTail` also ends `WithoutTail`, because buffered rows before the resume position were never returned. A paging that missed the tail on any page therefore ends `WithoutTail` on its last page and never reports `Full` for rows it skipped. A caller that keeps a `Resume` between requests keeps both its fields; the console's page token (#1555) carries the whole `Resume`. The caller shows "could not look" for unflushed events (P9), and a run from the start fills them in once the tail is back.
- Limits. Reaching `rows`, `bytes` or `wall_time` ends the stream `Limited { reason, last }`, where `last` is the position of the last row returned, or `None` if no row was returned. The caller continues with `after: ending.resume()`, and the projection does not need the key columns. When `last` is `None` the read returned nothing and skipped nothing, so the caller retries with the `Resume` it already held. A limit and a missed tail are reported together: the reason in `completion`, the tail in `coverage`.
- A read with `after: Some(r)` returns every row strictly after `r.position` that is present when it executes. A row that arrives later with a position before it is not returned; re-run from the start to see it.
- After `End`, `next` returns the same `End` again and does no work.
- `Timeline` and `Scan` are the only query nodes until the amendments of section 12 are accepted. `retain`, `erase`, `hold` and `manifest` are not declared: a `NotSupported` default would let an adapter pass the kit without erasure (D-57).

Callers in slice 0: `store` builds lake batches, appends and flushes (#1546, #1547); `query` plans and reads `Scan` and `Timeline` through `plan_query` and `run_query` (#1554) for the CLI and console reads (#1555), including resume.

Suite `storage::events::conformance`, reference adapter `MemEvents`. `MemEvents` keeps:
- a buffer per fence;
- a committed store with a version per organisation;
- a file-list cache that a flush updates only after its commit;
- a partition record per organisation, written at `append` before it returns;
- the floor of each fence and organisation, read from its committed store the first time that fence answers.

It knows each partition by the lease name of the fences appended under it, asks every partition in the organisation's record, treats a partition whose lease is free or expired in its `MemLeases` handle as having no holder, and answers in the order buffer, fence check, floor. It checks the fence at `append` and at `flush`, writes in-memory segments with each flush, and supports the stop points and the tail fault. Cases: an appended key is idempotent; a batch with an `organisation_id` column or another schema fails `BatchSchema`; a row outside its message's headers fails `BatchHeader`; an unregistered view or column fails; one `Scan` per `Comparison` and per `Literal` kind, and a literal whose kind differs from its column fails `Predicate`; `Limited` at each limit; `Timeline` and `Scan` paged to the end through `resume`, with no gap and no repeat, in both orders; a row appended and not flushed is returned by `execute`; row R appended, then `plan`, then a flush that commits R, then `execute`, returns R exactly once; R appended, `execute` started, a flush, the stream finished, returns R exactly once; R appended, a read that fills the file-list cache, a flush paused at `FlushBeforeNotify`, then `execute`, returns R exactly once, and where the fixture's `open` gives a second process the flush and the `execute` run on different handles; the same with a holder change: R appended under holder 1, a read that fills the cache, holder 1's `flush(All)` paused at `FlushBeforeNotify`, holder 1 releases and holder 2 acquires, then `execute` returns R exactly once with `coverage: Full`; after that release and before any `acquire`, `execute` ends `WithoutTail`; the same with one `HolderId`: holder P appends R, a read fills the cache, P's flush of R paused at `FlushBeforeNotify`, P acquires again, then `execute` returns R exactly once with `Full`; a re-partition: R appended under partition A's fence, a later row of the organisation appended under partition B's fence, a read through B that fills the cache, A's flush of R paused at `FlushBeforeNotify`, then `execute` returns R exactly once with `Full`, and once A's lease is released and before it is acquired again, `execute` ends `WithoutTail`; a new partition: a read fills the cache while the organisation has rows on partition A only, then R is appended under partition B's fence, then `execute` returns R; a drop between the reads: R appended, `execute` paused at `TailBeforeRead` after the holder's buffer read, the holder commits and drops R with no notify, then the answer resumes and `execute` returns R exactly once with `Full`; a superseded holder: `execute` reaches holder 1, paused at `TailBeforeRead`, holder 1's lease expires, holder 2 acquires and appends R again, holder 1 drops its buffers, then the answer resumes and the read either returns R exactly once or ends `WithoutTail`, never `Full` without R; a failed tail source ends with `coverage: WithoutTail`, never `Full`; a limit reached while the tail is down ends `Limited` with `WithoutTail`, `resume()` of that ending carries `WithoutTail`, and the read resumed from it ends `WithoutTail` even once the tail is back; a flush after another holder acquired fails `StaleFence`; an `append` under a superseded fence fails `StaleFence`; an `append` that the organisation's current answer does not allow fails `Refused`, also when the batch's context was minted under an allowed one; a batch appended while the organisation is `active` and flushed after it moves to `migrated` is committed under that organisation only; a plan made under a member context fails `Refused` at `execute` once the kit's clock passes its expiry, and a stream under a delegated context fails at its next `next` after the revocation; `committed_through` never covers an unflushed batch; a flush whose organisation's key is unavailable skips it and lets `committed_through` pass; crashes at `FlushAfterSegments` and `FlushAfterLakeFiles` leave no catalogue row and no change to `committed_through`, and a later flush commits the batch with its segment; every committed batch has its segment; a `flush(All)` past its deadline returns what committed; `next` after `End`; rows of organisation A never returned under a context for B; the kit wraps the adapter in its own adapter-trait wrapper whose `plan` prepares the plan for organisation B, plans under A's context and runs the result, and no row of B comes back; `run_query` over each variant of a `Dispatch` returns that variant's rows; a `Set` context cannot reach `plan`, and module code cannot implement `Events`, build a `Planned` (E0451) or a `LakeBatch` (E0451), pass `execute` a plan of the adapter's own type (E0308), build an `OrgRows` (E0451), call `ResultStream::next` (E0624) or relay its token through a wrapping adapter stream (E0308), each a compile-fail doctest; a Differential case against `MemEvents`. A property test in #1535 compares `MemEvents` with a `Vec` model.

### 11. Error codes
Areas for `schema/codes/areas.toml` (#278 R1):

| Area | Subsystem | Owner |
|---|---|---|
| `TENANT` | Identifiers, tenant context, mint authority, lifecycle answers and object paths | design/21 |
| `STORE` | Faults of a storage back end, shared by every storage port | design/20 |
| `BLOBS` | Blob store (Blobs port) | design/20 |
| `JOBS` | Jobs and leases (Jobs port) | design/20 |
| `BUS` | Event bus (Bus port) | design/20 |
| `REL` | Relational store and schema migrations | design/20 |
| `EVENTS` | Event store (Events port) | design/20 |

```rust
// grdr_ports::storage
#[non_exhaustive]
pub enum StoreFault { Unavailable, Busy, Conflict, Full, ReadOnly, PermissionDenied, Missing, Integrity }
```

Each cause maps to one variant: a lost connection or a timeout is `Unavailable`; a file held or locked by another process, such as a scanner, is `Busy`; a serialisation failure is `Conflict`; no space or quota on the volume or bucket is `Full`; a read-only file system or volume is `ReadOnly`; refused credentials or file permissions are `PermissionDenied`; a bucket, database or data directory that does not exist is `Missing`; stored bytes that fail the store's checksum or authentication are `Integrity`. The port error's type tells which port met it, and its `LogSafe` form logs the port name beside the code.

| Code | Reason | Class | Connect | Bound by | Next step (`code.<code>.fix`) |
|---|---|---|---|---|---|
| `GRDR-TENANT-0001` | `IDENTIFIER_INVALID` | input | `invalid_argument` | `IdentError` | Use lower-case ASCII letters, digits, `-`, `_` and `.` |
| `GRDR-TENANT-0002` | `PARTITION_FOR_CLASS` | input | `invalid_argument` | `PathError::PartitionForClass` | |
| `GRDR-TENANT-0003` | `DATE_INVALID` | input | `invalid_argument` | `PathError::Date` | |
| `GRDR-TENANT-0004` | `KEY_ID_INVALID` | input | `invalid_argument` | `PathError::KeyId` | |
| `GRDR-TENANT-0005` | `DELEGATION_NOT_ACTIVE` | fatal | `permission_denied` | `MintError::DelegationNotActive`, `Refusal::DelegationNotActive` | Ask the organisation owner to approve a new delegation, then start the work again |
| `GRDR-TENANT-0006` | `WORK_DEFERRED` | retryable | `unavailable` | `Refusal::Deferred`, in `Refused` of `BlobError`, `BusError`, `RelError`, `EventsError` | Retried once the organisation's state allows this work; devices keep their data until then |
| `GRDR-TENANT-0007` | `WORK_REFUSED` | fatal | `failed_precondition` | `Refusal::Refused`, in the same variants | The organisation's state does not allow this work; check its state in the console |
| `GRDR-TENANT-0008` | `LIFECYCLE_UNKNOWN` | retryable | `unavailable` | `MintError::LifecycleUnknown`, `Refusal::LifecycleUnknown`; a replica's Degraded signal | Retried once this replica holds the organisation's state; check its bus notifications if it persists |
| `GRDR-TENANT-0009` | `AUTHORITY_ALREADY_ISSUED` | fatal | `internal` | `AlreadyIssued` | Remove the code that issued the mint authority before the composition root; the server does not start until then |
| `GRDR-TENANT-0010` | `CLASS_FOR_MEMBER` | input | `permission_denied` | `PathError::ClassForMember` | |
| `GRDR-TENANT-0011` | `CONTEXT_EXPIRED` | fatal | `unauthenticated` | `Refusal::Expired` | Exchange a new workbench token, then read again |
| `GRDR-TENANT-0012` | `DELEGATION_UNCONFIRMED` | retryable | `unavailable` | `MintError::DelegationUnconfirmed`, `Refusal::DelegationUnconfirmed` | Retried once this replica's copy of the delegation is current; check its bus notifications if it persists |
| `GRDR-STORE-0001` | `STORE_UNAVAILABLE` | retryable | `unavailable` | `StoreFault::Unavailable` | Check that this host reaches the store; the call is retried under its policy |
| `GRDR-STORE-0002` | `STORE_BUSY` | retryable | `unavailable` | `StoreFault::Busy` | Exclude the data directory from scanning and backup locks |
| `GRDR-STORE-0003` | `SERIALISATION_CONFLICT` | retryable | `aborted` | `StoreFault::Conflict` | Retried under its policy |
| `GRDR-STORE-0004` | `STORE_FULL` | fatal | `resource_exhausted` | `StoreFault::Full` | Free space on the volume or raise the quota, or move the data directory |
| `GRDR-STORE-0005` | `STORE_READ_ONLY` | fatal | `failed_precondition` | `StoreFault::ReadOnly` | Mount the volume read-write, or move the data directory |
| `GRDR-STORE-0006` | `STORE_PERMISSION_DENIED` | fatal | `permission_denied` | `StoreFault::PermissionDenied` | Give the service account read and write access to the store |
| `GRDR-STORE-0007` | `STORE_MISSING` | fatal | `failed_precondition` | `StoreFault::Missing` | Create the bucket, database or directory, or correct its configuration key |
| `GRDR-STORE-0008` | `OBJECT_INTEGRITY` | fatal | `data_loss` | `StoreFault::Integrity` | Restore the object from backup; this is an alarm, not a retry |
| `GRDR-BLOBS-0001` | `OBJECT_NOT_FOUND` | input | `not_found` | `BlobError::NotFound` | |
| `GRDR-BLOBS-0002` | `RANGE_OUT_OF_BOUNDS` | input | `out_of_range` | `BlobError::Range` | |
| `GRDR-JOBS-0001` | `FENCE_SUPERSEDED` | fatal | `aborted` | `StaleFence` of `JobsError`, `BusError`, `RelError`, `EventsError` | None while it is rare: the holder reacquires; repeats raise health (section 7) |
| `GRDR-BUS-0001` | `STREAM_FULL` | retryable | `resource_exhausted` | `BusError::Full` | Sensors back off and retry; check the stream's consumers if it persists |
| `GRDR-BUS-0002` | `OFFSET_REGRESSION` | internal | `internal` | `BusError::Regress` | |
| `GRDR-BUS-0003` | `BUCKET_OUT_OF_RANGE` | input | `invalid_argument` | `BusError::Bucket` | |
| `GRDR-BUS-0004` | `BUCKET_MAP_NOT_NEWER` | input | `failed_precondition` | `BusError::MapVersion` | |
| `GRDR-BUS-0005` | `MESSAGE_WITHOUT_ORGANISATION` | fatal | `data_loss` | `Unattributed` | Report it; a stored message lost its organisation header |
| `GRDR-BUS-0006` | `OFFSET_BEYOND_LOG` | internal | `internal` | `BusError::BeyondLog` | |
| `GRDR-REL-0001` | `CONSTRAINT_VIOLATION` | input | `failed_precondition` | `RelError::Constraint` | |
| `GRDR-REL-0002` | `SINGLE_ORGANISATION_STORE` | input | `failed_precondition` | `RelError::SingleOrganisation` | Use the `ha` profile for more than one organisation (D-34) |
| `GRDR-REL-0003` | `MIGRATION_ID_DUPLICATE` | internal | `internal` | `PlanError::Duplicate` | |
| `GRDR-REL-0004` | `MIGRATION_OUT_OF_ORDER` | internal | `internal` | `PlanError::Order` | |
| `GRDR-REL-0005` | `CONTRACT_WITHOUT_EXPAND` | internal | `internal` | `PlanError::ContractWithoutExpand` | |
| `GRDR-REL-0006` | `CONTRACT_TOO_EARLY` | internal | `internal` | `PlanError::ContractTooEarly` | |
| `GRDR-REL-0007` | `SCHEMA_TOO_NEW` | fatal | `failed_precondition` | `MigrationError::SchemaTooNew` | Install the release that wrote this schema, or a later one |
| `GRDR-REL-0008` | `TRANSACTION_TIMEOUT` | retryable | `deadline_exceeded` | `RelError::Timeout` | Retried in a new transaction; split work that needs longer than `relational.transaction-life` |
| `GRDR-EVENTS-0001` | `VIEW_NOT_REGISTERED` | input | `invalid_argument` | `EventsError::View` | |
| `GRDR-EVENTS-0002` | `COLUMN_NOT_REGISTERED` | input | `invalid_argument` | `EventsError::Column` | |
| `GRDR-EVENTS-0003` | `PREDICATE_INVALID` | input | `invalid_argument` | `EventsError::Predicate` | |
| `GRDR-EVENTS-0004` | `TIME_BOUNDS_INVALID` | input | `invalid_argument` | `EventsError::TimeBounds` | |
| `GRDR-EVENTS-0005` | `BATCH_SCHEMA_MISMATCH` | internal | `internal` | `EventsError::BatchSchema` | |
| `GRDR-EVENTS-0006` | `BATCH_UNREADABLE` | internal | `internal` | `EventsError::BatchUnreadable` | |
| `GRDR-EVENTS-0007` | `BATCH_HEADER_MISMATCH` | internal | `internal` | `EventsError::BatchHeader` | |

`MigrationError::Rel` carries a `RelError` and takes its code, and every `Refused(Refusal)` and `Store(StoreFault)` takes the code of the value it carries. The next-step column is the English source of each code's `fix` token for the codes an operator acts on; the item that registers a code writes the rest. A target that reports a fatal `STORE` code in its health shows Degraded, re-attempts at its next scheduled run and never in a retry loop, and that health code gets a runbook in `docs/runbooks/` (design/34), as does `GRDR-TENANT-0008` when a replica raises it.

A superseded fence, a refused write and each store fault have one cause wherever they are found, so each has one code and one docs page (P17). Each code's page lists every variant bound to it, from the registry, and each area's index links the shared codes its enums use, so a Bus author finds `FENCE_SUPERSEDED` and `STORE_FULL` from the Bus page. Until the generator of #1636 publishes `/codes/<code>`, an adapter author reads this table and `schema/codes/<area>.toml`. Each item registers the entries its area constructs, because ARCH-017 requires every registered code to be constructed somewhere: the `STORE` entries by #297, the first port item to land; `GRDR-TENANT-0005` to `0009`, `0011` and `0012` by #312, whose minting, read and write checks construct them; `GRDR-TENANT-0010` by #313. The `GRDR-` prefix is the code namespace and does not change under a rebrand, so an embedder's support pages can quote codes.

### 12. Stability, adapter selection and later change
Stability:
- Both crates enter `surfaces.toml` as `experimental` (ADR-0020; design/03 section 7: every surface starts there), through the protected-change item #1688 R3 files after acceptance, unless RFC 0008's entered them first.
- `experimental` allows a break in any release, and every change still goes by RFC: a signature, a semantic, a variant, a suite case, a lifecycle cell, the key layout, the identifier rule or the additional-data encoding is an amendment. An amendment is a new RFC that names RFC 0002 and goes through the same route; RFC 0002's text does not change after its decision, because an accepted RFC never returns to `Review` and a later change is a new RFC (RFC 0001, "RFC states"; design/30 section 3). Its pull requests name that RFC for `rfc-required`. One amendment may carry every change that is ready at the same time. `cargo public-api` and `cargo semver-checks` run against the class once the entry exists.
- What an adapter author can rely on: two versions describe the surface, the crates' semver and the kit version, and each server release names both. Every amendment is listed in the release notes, as `breaking` when it breaks. There is no compatibility window while the class is `experimental`. An adapter pins a kit version and moves when it moves to a new server release.
- The storage ports become `beta` when the server's packages freeze (design/03 section 7), by an RFC that changes `surfaces.toml` and sets the notice the beta class gives (ADR-0020). Its prerequisites are the deployment-scoped amendment of question 1, the Keys port RFC (design/21 K2) and the answer to question 2. The first embedding guide for storage has the same prerequisites.

Adapter selection and admission (P6, P14, design/03 E2):
- Adapters enter a build through `dist.toml`. The distribution build (#1593) generates, for each storage port, a dispatch type over the adapter types the distribution lists, which implements the port's adapter traits by delegation, and `server.profile` or the storage configuration keys pick the variant at start. The composition root admits that dispatch with `Admitted::new` (Rule 12). The Bus dispatch's subscription type and the Events dispatch's plan and results types are `Dispatch` over the listed adapters' types, because the call token cannot be passed on and a `Planned` cannot be built outside `tenant` (section 2, "Forwarders"). The three named profiles are the default `dist.toml`. No adapter is named in `grdr-server` source outside the generated module, so adding one is data plus a build, never a code change in the server.
- An embedder or contrib author lists its own adapter crate in its own `dist.toml`, with its adapter type, the function that builds its fixture, and the fixture environment its conformance test needs (a store the builder supplies, for example a container image or a connection setting). The distribution build generates each suite's test against the release's own `grdr-ports-testkit` under the bound `F: Fixture<Adapter = <the listed type>>`, so the suite drives the listed type and no other. It runs those tests in a cargo invocation separate from the program build (Rule 1), and admits the adapter only on a passing report it produced itself. A report the author wrote elsewhere is not evidence. Nothing is patched, nothing is forked, and nothing is sent to Loonaro.
- What admission shows, and what it does not. The `testkit` scan (section 5) holds the admitted build to the shipped code plus the fixture module and hook statements that call the release kit's `reach`, and every report includes `unarmed_reach_is_inert`. So the listed type behaves under the suite as the shipped type does, whenever no hook is armed. The report does not show that the author's fixture is honest: the fixture module is part of the adapter crate, can reach its private state, and could repair the store behind the adapter during the run. A report on an adapter from outside the project is therefore evidence of that adapter under its author's fixture. This is one reason a contrib adapter is Tier 2 and never part of a named profile (design/03 section 6).
- The same build runs the register check of Rule 12 and ARCH-029 over the resolved closure, after macro expansion and name resolution: the capability-type rule and the transaction-type rule of section 2 and the `testkit` scan of section 5. Its compile of each closure crate that depends on `grdr-ports` with `unsafe_code` forbidden is the first check of Rule 12.

Amendments already expected, each with its item:
- Blobs: `put_versioned` and deployment-scoped objects (question 1); a streaming put (L-4); `ListPrefix::org` and `ListPrefix::class` with organisation removal and retention (R-3); the store's modification time in `ObjectMeta` and `Page`, if #1547 chooses it for cleanup (section 6).
- Events: `retain`, `erase` (taking `&SingleCtx` only), `hold` and `manifest` (L-5, R-3); `QueryIr` nodes `Aggregate`, `Lookup`, `Hunt` and `Export` (L-6, L-7). `Export`'s projection names stable manifest columns only and it resumes through `Resume`, so there is no second cursor type. `LakeTable::Content` (L-3).
- Jobs: the methods of J-1, where `claim` returns the claimed job's organisation, work kind and delegation as plain values from a method that takes the call token, which `tenant` wraps into a `JobRecord`; the job-kind registration, where each kind declares its work kind; the `Dispatch` forwarder for the token-taking method (section 2); and the step handle whose only write opener is `write_fenced`.
- Tenancy: the actor and purpose accessors, with the audit item.
- Bus: removing a partition from a stream, with the removal of a drained partition from each Events partition record (section 10).
- Deployment-scoped transactions (question 3) and the Keys port (design/21 K2).
- The endpoint ports (`SensorBackend` and `Actuator` #589, `SandboxBackend` #458, `JudgeBackend` #765, `DetectorPort` #1019, `DeclaredSource` #811, `Meter`) follow Rules 1, 2, 6, 7 and 8 and get their own RFCs.

### 13. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| Rule 1 | A third-party allow-list per crate in `architecture.toml`, read by the archlint graph rules, and a check that `grdr-ports-testkit` is in no layer 4 program's normal closure under any feature set a release or distribution build enables | #1580 reads the data; the entries are a protected change filed on acceptance |
| Rule 2 | The `+ Send` bound in every signature, checked by the compiler | Each item |
| Rules 3 and 4 | ARCH-015 restated: every method of a port trait takes or returns a tenant witness unless `architecture.toml` lists it as deployment-scoped, a deployment-scoped method that returns tenant data takes a `PortsCall`, and no input type of a port method has an `OrgId` field except `MemberCursor` | A slice-0 lint item split from #1582, filed on acceptance |
| Rule 12, the seal | `seal::Sealed` in a private module; port traits implemented only for `Admitted`, in `tenant::admit`; `Admitted::new` takes the mint authority; compile-fail doctests that module code implementing `Subscription`, `Events` or `Relational`, by hand or through `macro_rules!`, does not compile | #312 (`Admitted`, `tenant::admit`); each port item (its port and adapter traits and doctest) |
| Rule 12, no `unsafe` | The register check over each crate after macro expansion and name resolution, on the workspace and on the distribution build's resolved closure, failing every `unsafe` block, `unsafe fn`, `unsafe impl`, `unsafe extern` block, unsafe attribute and assembly in a crate the register does not list; cases for each capability type, each failing: `unsafe` written in a closure crate, emitted by another crate's `macro_rules!`, by a derive and by an attribute or function-like proc macro, and held by a helper crate behind a safe function; as the first check, ARCH-029's check that each workspace crate other than the OS adapter crates and `grdr-ffi` declares `#![forbid(unsafe_code)]`, and the closure compile with `unsafe_code` forbidden and uncapped; the interim rule, failing a registry dependency or a proc macro in a crate that names a capability type or a `tenant`, `storage` or `adapter` item until #1475 lands, with a case that the daemon, which names only RFC 0008's items, passes | #1475 (the register check, on the closure once #1593 exists); the slice-0 lint item (the attribute and the interim rule); #1593 (the closure compile) |
| Minting boundary | `MintAuthority::issue(table, clock)` once per process, binding both, with cases that a second call fails `AlreadyIssued`, that a build script's generated mint gets nothing once the composition root has issued, and that a mint, `tenant::members` or `fetch_batches` given a table of module code's own, and `tenant::members` given an adapter of module code's own, does not compile (compile-fail doctests); the authority argument on every mint, `MemberReadAuthority::new`, `fetch_batches`, `Admitted::new` and `HolderId::mint`; ARCH-029's capability-type rule by resolved type, failing a value of a capability type in a module `architecture.toml` does not list for it, with cases for a `macro_rules!` use, an `include!` from `OUT_DIR`, a type alias, a generic parameter and an inferred binding, one for each capability type with a holder list; values that hold a capability type, with named cases that a wrapper handle holding `&MintAuthority` passed to an unlisted module fails, that a `MintAuthority` value in the workbench read path fails, and that a closure capture, a boxed function and a `static` fail, each from the composition root and from a listed runner; and its rule that only the composition root and the kit call `Admitted::new`, with a case that a call in the workbench read path fails; the transaction-type rule with its cases (section 2); the composition root and `grdr-archlint` in `security/trust-core.paths` | #312; the slice-0 lint item; #1593 for the closure run; the item that builds `grdr-server`'s composition root; protected changes filed on acceptance |
| Lifecycle | `Lifecycle::answer` over the constant `grdr-schema` generates from `schema/tenancy/lifecycle.toml`, generation failing on a missing, extra or unparseable cell; the check in `Admitted` against the authority's table at every store operation; cases: a context carries the state the table held and `Unconfirmed` for a stale copy, an unknown organisation fails `LifecycleUnknown` at a mint and at a store operation and raises Degraded, a write under a `Read` context or a non-allowed answer fails `Refused`, a context, path or plan kept across a move to `key_unavailable` and to `shredded`, a read under one after `shredded` included, and a transaction opened before the move and committed after it each fail `Refused`, `ingest` answers `Deferred` with retry-after and `Refused` with its code, a consumer skips `Deferred` and `Refused` batches and the partition advances | #312 (with the generated constant); the authentication middleware item and #1547 (their cases); the data file is a protected change filed on acceptance |
| Delegation | The delegation in `VerifiedAudience`, `SingleCtx`, `MemberCtx` and stored bus messages; `DelegationRead` and the epoch order; the checks in `single_from_token`, `fetch_batches`, `single_for_step`, `tenant::members` and every store operation; the revocation marker read at a delegated open and commit step, and the `FOR SHARE` lock in that commit step only, committing only while the delegation is in force; the transaction bound and the check at every `adapter_mut`; the expiry of `SetCtx` and `MemberCtx`, carried by their paths and plans and judged by the authority's clock; cases: a revoked delegation refuses at the next request, the next stored message, the next step, the next page of members and the next read or write of a kept context, path or plan; a snapshot row whose delegation the table records for another organisation or another provider is withdrawn; the kept-transaction, share-lock and `Set` cases of section 9; a stale or unknown copy, or one behind the record's epoch, defers with `DelegationUnconfirmed`, and one ahead of it refuses; a transaction open across a revocation or an expiry either commits before it or fails; a set or member context, and a path or plan built under one, read past its expiry fails `Expired` | #312; #299 (stored delegation); #300 (marker, lock and bound); J-1; the authentication middleware item |
| Grouping, members, lifecycle and delegation against reference models | A differential test of `fetch_batches`, `tenant::members`, `Lifecycle::answer` and the delegation checks against four models in `grdr-tenancy-ref`: `batches` (groups by partition, organisation and delegation; per partition, a stop at the first message with no organisation, nothing after it, every other partition returned), `members` (passing members in byte order, the refused ones withdrawn and the deferred ones unconfirmed, paged without gap or repeat), `lifecycle` (every cell) and `delegation` (the outcome for an organisation, a record's delegation and the table's `DelegationRead`, in the order of section 2) | #311 (the models, by a different worker); #312 (the test, beside its R8 test); J-1 (the step cases against `delegation`) |
| Rule 5 | Fence cases in the Jobs, Bus, Relational and Events suites: the paused fenced commit, the two-task holder, the concurrent and paused `subscribe` and `commit` cases, the other partition's fence, `BeyondLog`; compile-fail doctests that a `Fence`, a `Lease`, a `Claim` and a `HolderId` cannot be built | #298, #299, #300, #1535 |
| Rule 6 | `eval-architecture` checks, on every pull request that names RFC 0002 or an amendment, that each new public item has a reference implementation, a named case and a caller | Review, on each such pull request |
| Rule 7 | ARCH-019 | #1582 |
| Rule 8 | `Coded` (#280) with an exhaustive match, the registry (#278), ARCH-017 with its exemption list in `architecture.toml` | #280, #278, #1582; the list is a protected change |
| Rules 10 and 11 | `parse` of each identifier type; suite cases with an Arabic name, a Japanese name, an NFC and NFD pair, bidi controls (U+202E, U+2066 to U+2069), full-width Latin and Arabic-Indic digits in a date, all refused; ordering cases on byte-wise keys; the PostgreSQL fixture's `ja-JP` run | #313 (identifiers and dates), #297, #1535, the PostgreSQL adapter items |
| Member paths | `PathError::ClassForMember` with a case per class | #313 |
| Archive with the lake commit | The crash cases at `FlushAfterSegments` and `FlushAfterLakeFiles`, "every committed batch has its segment", the `BatchHeader` case and the compile-fail doctest for a hand-built `LakeBatch` | #1535 (cases), #312 (`LakeBatch`), #1547 (adapter) |
| Union and coverage inside `execute` | The buffered-row, plan-flush-execute, flush-window, `WithoutTail` and limit-with-tail-down cases; coverage held once in `Ending`, with `resume()` derived from it | #1535 |
| `Planned::org` only | The kit's own wrapper case of section 10, in every Events suite | #1535 |
| File selection at the answers' floor | The partition record, written at `append` and read where it is written; the floor in every buffer answer, kept per fence, including the version the fence's holder read on the primary after `acquire`; the answer order buffer, fence check, floor; a partition with no holder or a superseded one as a failed tail; the `FlushBeforeNotify` and `TailBeforeRead` stop points; the delayed-invalidation case in one process, across two, across a holder change, across a re-acquire by one `HolderId` and across a re-partition; the new-partition, drop-between-reads, no-holder and superseded-holder cases | #1535 (`MemEvents` and the cases), #1554 (the lake adapter's partition record, file-list cache and the partitions it asks), #1547 (the holder's floor read, order and fence check) |
| Coverage across requests | The page token carries the whole `Resume`, with a case that a token from a `WithoutTail` page resumes to a `WithoutTail` ending | #1555 |
| Cleanup grace | A `limits.toml` bound, an age from a clock the writer does not set, and a case in #1547 that a lister leaves another holder's uncommitted object alone, also when that writer's wall clock runs behind | #1547 |
| Conformance kit | This RFC's amendment of RFC 0008's runner, with Crash and Differential cases, the stop points, `arm` and `reach` at the crate root, the case `unarmed_reach_is_inert` first in every suite, `authority()` issued with `tenancy()` and `clock()`, `MemRelational`, fixture errors without text, and the how-to page | The storage kit item; #300 |
| Adapter selection and admission | Dispatch generated from `dist.toml` and admitted by the composition root; the distribution build generates each listed adapter's conformance tests under `F: Fixture<Adapter = <the listed type>>`, runs them in a cargo invocation separate from the program build, and admits only on its own passing report; the `testkit` scan, with cases that a hook statement without the leading `::` fails, a local module or alias named like the kit is never called, a build script fails, a renamed kit or another package under its name fails, and a `[features] testkit` entry beyond optional dependencies that only the `testkit` module and hooks use fails; the Bus and Events dispatch over `Dispatch`; a sample contrib adapter that builds and passes the kit, and a fixture whose `Adapter` is a reference adapter, which fails to compile | #1593; the slice-0 lint item (the `testkit` scan); #281 (`reach`) |
| Stability | The `surfaces.toml` entries, `rfc-required`, `cargo public-api`, `cargo semver-checks` | The protected-change item of #1688 R3 |
| Additional-data encoding | Vectors shared by #311 and #313 | #311, #313 |

### 14. Proposed changes to design documents and `architecture.toml`
Each lands after acceptance as a protected change (section 1): its own issue whose write set names its file, landed after `eval-security` and an evaluator on the other model pass (D-63, ADR-0035). The design/21 change also takes `eval-adversarial`, because it restates the rule the trust-core `tenant` module implements (`security/trust-core.paths`).

How D-35, design/21 principle 2 and design/21 R2 are read. "No code path reads without a tenant context" is read as "no tenant data reaches module code without a tenant witness". Two deployment-scoped methods handle tenant data inside an adapter and `grdr-ports`: `Subscription::fetch` and `Events::flush`. `fetch` takes a branded call token that module code can neither build nor relay; the port traits are sealed, so module code cannot supply a subscription of its own; and `fetch_batches`, the one way to its messages, takes the mint authority, which only the composition root and the runners it lists hold. Module code therefore receives stored messages only inside an `OrgBatch` that a listed runner fetched. `flush` hands no tenant data out. Events rows reach module code only through an `OrgRows` built from a `Planned`, which only a context can produce. This is a reading of the spine, not a change to its text. If the council or an evaluator reads D-35 more strictly, the spine changes by its own RFC and this one waits for it.

- **design/20 section 3.** `Set(Vec<OrgId>, ReadOnly)` becomes `Set(DelegationSnapshotId, ReadOnly)`, as design/21 section 2 has it. "Every method takes 21's `TenantCtx`" becomes Rule 3. "It can be built only by the authentication middleware of `api` and `ingest` and by the job runner" becomes the minting boundary of section 2: the mint authority, which the composition root issues and hands to the listed runners. Port traits are sealed and adapters implement adapter traits (Rule 12). The Events row lists `append(fence, LakeBatch)`, `flush(fence, due, deadline)`, `plan(OrgRead, ...)` and `execute(Planned)`, with reads through `plan_query` and `run_query`, and names the methods that come later.
- **design/20 section 4 step 7** (refines). A consumer skips a batch whose answer for Process is `Deferred`, as step 7 skips an organisation whose key cannot be unwrapped, and `ingest` rewinds those lanes once the answer is `Allowed` again; a `Refused` batch is skipped and counted. A flush that cannot seal an organisation's rows drops them as skipped, so the partition keeps advancing.
- **design/20 section 5.2** (refines). The archive segment travels in `LakeBatch`, which `OrgBatch::lake_batch` builds from one bus message, and is committed in the same lease-checked catalogue transaction. The commit unit is the organisation, all its due tables and segments together, which refines "a flush is per organisation and table". "Tail reads": the Events adapter unions buffered rows inside `execute`, through `StoreTail` in `distributed`; `query` no longer unions, and a missed tail is reported as `Coverage::WithoutTail`. A flush drops rows from the memtable only after its catalogue commit is visible. A read asks every partition in the adapter's partition record for the organisation, which `append` writes before it returns and the read takes from where it is written. Every memtable answer, `StoreTail`'s included, carries a floor per organisation, kept per fence: the greater of the newest `lake_org_head` snapshot whose commit dropped rows from that fence's memtable and the snapshot its holder read on the catalogue's primary after acquiring the partition under that fence. An owner answers in the order memtable read, fence check, floor read, and only while its fence is current. The item that defines `StoreTail` adds the floor. A partition with no owner, an owner that does not answer, or an owner whose fence was superseded, is a failed tail read, shown as "could not look". The bus watermark the flush returns is named `committed_through`, apart from the sensor-facing `durable_through` of section 9. Unreferenced objects are removed after a grace measured by a clock the writer does not set.
- **design/20 section 5.4** (adds). A sidecar table `lake_org_partition (organisation_id, partition)`: the Events adapter's partition record, one row per partition under whose fence a row of the organisation was appended.
- **design/20 section 5.8** (refines). The file-list cache serves a read only when it is at or after the greatest floor the read's memtable answers carry (section 5.2), so it covers commits by the current holders, by every earlier one and by the partitions an organisation has left. Otherwise the read takes its file list from the catalogue's primary, never from a replica that lags. Invalidation by catalogue commit notification stays, but correctness no longer rests on its timing, on the partition keeping its holder, or on the organisation keeping its partitions.
- **design/20 section 7** (refines). `bus_consumer`'s `holder, fence` columns are stamped by `subscribe` in one compare-and-set that never lowers the fence, and checked by `commit` in one conditional update that also bounds the offset by the partition's last one: the row-stamped form of Rule 5. That is what lets `bus.database` stay a separate instance. A consumer's lease for a partition is `<group>.<stream>.<partition>`. `bus_message` stores the delegation of the context that appended it, beside `organisation_id`. `commit` carries the detect snapshot key in the same row update, as the section already says.
- **design/20 section 8** (refines). "A claim takes a lease with a fencing token that every write checks": a job step's writes go through `write_fenced`, and every `acquire` issues a new token, also for the same holder. Each job kind declares its work kind. A provider's job records the delegation and epoch it was enqueued under; each step's context is minted only while that delegation is in force at that epoch (`GRDR-TENANT-0005`), and its writes hold a share lock on the delegation row.
- **design/21 section 2** (contradicted today). Principle 2: "a `TenantCtx` value required by every repository and store call" becomes "a tenant witness (RFC 0002 Rule 3) required by every repository and store call that touches tenant data; the deployment-scoped methods `architecture.toml` lists take none, and tenant data they handle reaches module code only inside a witness". R2: "No server read or write executes without a tenant context; a missing context fails closed" becomes "No server read or write of tenant data executes without a tenant witness; a missing witness fails closed. A deployment-scoped method that returns tenant data takes a call token, so only `grdr-ports` calls it and its data reaches module code only inside a witness." Service framework row: "minted only by the auth middleware and the job runner" becomes "minted only by `grdr-ports`, for holders of the mint authority, which the composition root issues once with the replica's tenancy table and clock and hands to the authentication middleware, the partition consumer runners and the job runner, and from which it builds the workbench read path's `MemberReadAuthority`"; a single-organisation context carries the organisation's lifecycle state, the work kind it was minted for and the token's delegation; every store operation checks the current state's answer for that work, the delegation and the expiry; "Every method of the relational, lake, bus, blob and cache ports takes it" becomes Rule 3; port traits are sealed (Rule 12); a `Set` has no write methods, and its lake and blob reads go through `MemberCtx`, which cannot reach `content` or archive objects. Set policy: a snapshot row counts only while its delegation is the set's provider's, `active` or `expiring` at the epoch the snapshot recorded, with no revocation marker newer than that epoch, so a revoked, expired or rebound member leaves every `Set` read at its next statement. Lake and blobs row: "N per-organisation plans", each under a `MemberCtx` from `tenant::members`. Bus row: the consumer read of `bus_message` across organisations runs under a deployment binding that only the bus consumer path sets, and its rows reach module code only inside an `OrgBatch`; the binding's form is question 3, and this row is a placeholder until that RFC settles it.
- **design/21 section 5** (refines). Revocation, and any change to a delegation's bindings, increments its epoch. Revocation, expiry and rebinding first commit a revocation marker for the delegation and its new epoch, a row no transaction locks, and notify the replicas from that commit; only then do they update the delegation row, so they wait on no open delegated transaction (RFC 0002 section 9). A delegation in state `active` or `expiring` is in force. Besides the API's check on each request, a stored message, a job step, a page of members and every store operation each re-check the delegation they carry, which must be the organisation's own (RFC 0002 section 2). A replica whose copy of the delegation is stale, unknown or behind the epoch the work carries defers the work; one whose copy is ahead of it refuses. The workbench token's expiry ends every read under its snapshot, and the revocation test includes a workbench `Set` read and a delegated transaction kept open across the revocation.
- **design/21 section 13** (refines). The lifecycle table of section 2 is added beside the diagram as the rule each minting site and every store operation applies, with `schema/tenancy/lifecycle.toml` as its data and typed answers. Its rows for `suspended`, `detached`, `migrated` and `shredded` restate the section's bullets, and the `key_unavailable` row restates section 11 for ingest, processing and reads. The rest is new text the sections do not have: `provisioning` reads and changes but takes no devices; `migrating` runs as `active` until its devices are redirected; `deleting` behaves as `suspended`, so the owner can export (section 12) and cancel; in `suspended` and `deleting` the `bulk` and `evidence` lanes are deferred and admitted messages are processed; in `key_unavailable` enrolment and exports wait for the key and changes are refused, because their audit records cannot be stored; `migrated` processes nothing more; Maintain runs in every state that holds data; the move to `shredded` ends every delegation of the organisation in the order of section 5. Replicas hold each organisation's state the way they hold delegation epochs (section 5), refreshed by bus notification; a copy older than its bound counts as `unconfirmed`, and no copy refuses the work.
- **design/03 section 2.** The ARCH-015 rule becomes the restatement in section 13, including the call-token check. A new row adds ARCH-029 `context-mint`: the capability-type rule, judged by resolved type; the `Admitted::new` call rule; the transaction-type rule; the `testkit` scan; and the `forbid(unsafe_code)` check, which is a first check only, because the `unsafe` barrier is the register check of design/35 section 2.4. ARCH-029 reads code after macro expansion and name resolution and runs on the workspace and on the distribution build's resolved closure. The number is the one the register comment on #1688 assigned: ARCH-027 is `os-adapter-only` (#1751) and ARCH-028 is `wire-seams` (RFC 0003, #1757). The amendment that adds the row cites that register.
- **design/03 section 6.** The adapter guide path `docs/extending/storage-adapter.md` becomes the how-to page of section 5. Adapters implement the adapter traits of Rule 12. Contrib dispatch is generated from `dist.toml`, which names each adapter's type and fixture function, and the distribution build runs each listed adapter's conformance tests under the bound of section 12, in their own cargo invocation.
- **design/03 section 10, Errors.** "One enum per crate" becomes "one enum per crate, and one per port module in `grdr-ports`, which share `StoreFault` and `Refusal`".
- **`architecture.toml`.** An empty third-party allow-list for `grdr-ports`; the Arrow crates of #1532 for `grdr-ports-testkit`, with the program-closure rule over every release and distribution feature set; the deployment-scoped list (`Leases`, `Migrator`, `Bus::subscribe`, `Bus::commit`, `Bus::lag`, `Bus::set_bucket_map`, `Subscription::fetch`, `Events::flush`), with `Subscription::fetch` marked as returning tenant data; the modules that may hold each capability type (section 2): for `MintAuthority` the composition root, the middleware modules of `api` and `ingest`, the partition consumer runners, with J-1 the job runner, and `grdr-ports-testkit`; for `MemberReadAuthority` D-35's workbench read path; the callers of `Admitted::new`, the composition root and `grdr-ports-testkit`; the transaction-type rule (`ReadTx` and `WriteTx` adapter types, the constructor traits it refuses, and the enums it accepts); the `testkit` scan's hook form and its manifest rules; the Rule 4 exemption `MemberCursor`; the ARCH-017 exemption list (every error type of `grdr-ports-testkit`, each with its reason; RFC 0008 adds `RetryError`).
- **`security/trust-core.paths`.** `schema/tenancy/lifecycle.toml`, because the trust-core `tenant` module reads it; `crates/grdr-archlint/**`, because ARCH-029 holds the minting boundary where a type cannot; and the composition root of `grdr-server` (`programs/grdr-server/src/compose.rs` and `programs/grdr-server/src/compose/**`), because it decides who holds the mint authority.

### 15. What each item changes
This RFC's text is normative. Under #1688 R4 each lead writes these changes back into its item before readying it. Every item's `cargo xtask` criterion becomes the `grdr-verify` gates or `cargo run --locked -p grdr-archlint -- check`, since ADR-0029 removed `xtask`.

- **#281**: its scope is RFC 0008's, and this RFC adds nothing to it.
- **The storage kit item**, filed on acceptance and blocked by #281: section 5 as an amendment of RFC 0008's runner: `CaseKind` and `NotApplicable`, the `Fixture` traits, the stop points, `arm`, `reach`, `StopPoint` and `Reached` at the crate root, `unarmed_reach_is_inert` first in every suite, `authority()` issued with the kit's `MemTenancy` and `ManualClock`, `tenancy()`, `clock()`, fixture errors without text and suites that drive adapters through `Admitted`. It writes the how-to page, whose steps are those of section 5.
- **#297**: section 6: the sealed `Blobs` with `BlobsAdapter`; `get` and `get_range` take `ReadPath`, `list` takes `ListPrefix` and builds keys with `ObjectKey::under`; `put_versioned` and `VersionId` go; `delete` gains its semantics and case; `ByteRange` and `PageLimit` gain accessors; `BlobError` is `NotFound`, `Range`, `Refused`, `Store`, and every method runs the check of section 2. It registers the `STORE` codes. AC-3 waits on the slice-0 lint item.
- **#298**: section 7. R3 changes: every `acquire` that returns `Held` issues a new token, also for the same holder. R2's `LeaseState::Free` carries `last`, and a lease row is never deleted. `Fence`, `FencingToken` and `Lease` lose their public fields, `LeasesAdapter` returns `Grant` and `Renewal`, `HolderId::mint` takes the authority and `parse` goes, `Busy` carries a `HolderLabel`, and `JobsError::StaleFence` carries no token. The lead-core comment on ARCH-015 is replaced by the deployment-scoped entry.
- **#299**: section 8: the sealed `Bus` and `Subscription` with their adapter traits; claims from `Claim::new` and the partition-lease check; the compare-and-set `subscribe`; `commit` as one conditional update bounded by the last offset (`BeyondLog`); `poll` becomes `fetch(FetchLimit, PortsCall<Self>)`; `fetch_batches` with the authority, returning `Fetched` with `Unattributed` stops, so the item's error for a message with no organisation goes; the delegation stored with each message; `Headers` as a closed struct. `PortsCall`, `Admitted`, `OrgBatch`, `Fetched`, `fetch_batches` and `Dispatch` come from `tenant::mint` (#312).
- **#300**: section 9: the sealed `Relational`, `ReadTx`, `WriteTx` and `Migrator` with their adapter traits and `adapter_mut`; `guard` goes and `write_fenced` arrives, lease-checked by `FOR SHARE`; the revocation marker read at a delegated open and commit step, and the share lock on a delegation row in that commit step only; `relational.transaction-life`, enforced in the store and by `Timeout`; `adapter_mut` returns `Result`, and it, every opener and `commit` run the check of section 2; a `Set` read at READ COMMITTED; `RelError::Conflict` moves to `StoreFault::Conflict`, and `Refused` arrives; `snapshot_members` returns `SnapshotMember`s; `SingleOrganisation` covers a delegated context; `Migrator::apply` uses the adapter's own transaction; codes `REL-0001` to `0008`; the cases of section 9 for kept transactions, chained share locks and `Set` reads after a revocation. `MemRelational` and the suite run in this item.
- **#1535**: section 10, the largest change, so the lead should split it into the traits and types, and `MemEvents` with its suite. Against the item as written: reads take `OrgRead`; `append` takes a fence and a `LakeBatch`; `flush` is new; rows are `ArrowIpc`; `LakeTable` loses `Content`; `QueryIr` keeps `Timeline` and `Scan` with order and `Resume`; `tail` goes and `execute` unions under the partition record and the floor rule; `execute` takes `Planned<Self::Plan>` and serves `Planned::org` only; `execute` and each `next` run the check of section 2; the ending carries `Completion` and `Coverage`; R6 goes. It now also requires #298, #299, #510 (the manifest type), #1532 (Arrow for the test kit) and #1475 (before the kit takes Arrow, Rule 12).
- **#312**: section 2. `RecordedJobOrg`, `single_for_job` and the mint from a recorded organisation go. `DelegationSnapshotId` and `DelegationId` are grdr-model ids, constructible like `OrgId`, which replaces R2's non-constructible snapshot id; the contexts stay non-constructible. The item builds `tenant::authority`, whose `issue` binds the tenancy table and the clock, with `MemberReadAuthority`; `tenant::ctx` with the lifecycle table, `DelegationRead` and its order, and the expiry of set and member contexts; `tenant::admit`, whose check runs at every store operation and every use of a relational transaction, with the transaction bound; and `tenant::mint`, so every minting site is under the trust-core `tenant` paths. The item's call-site list is replaced by ARCH-029's capability-type rule. R4 follows Rule 3. Beside R8's test it adds the differential test of section 13 against the four models of #311, with zero disagreements over generated inputs and a soak run like AC-3's. It registers `GRDR-TENANT-0005` to `0009`, `0011` and `0012`. The lead should split the item, for example into the authority and contexts, `tenant::admit` and `tenant::mint`, and the lifecycle table. It is blocked by the slice-0 lint item, by #311's new models and by RFC 0008's `Clock`, and AC-5 needs a criterion that does not use `cargo xtask matrix-run`.
- **#311**: four models, written by a worker who is not #312's and from this text and design/21 only. R10, `batches(messages) -> (Vec<Batch>, Vec<Stop>)`: consecutive messages of one partition, one organisation and one delegation form one batch, partition and offset order is kept, and per partition the first message with no organisation is a stop, with nothing at or after it on that partition returned and every other partition returned. R11, `members(snapshot, members, table, after, limit)`: one member per passing delegation, each carrying `snapshot`, in ascending byte order, strictly after `after`, at most `limit`, the refused ones withdrawn, a delegation of another organisation or another provider included, and the deferred ones unconfirmed, with the next cursor. R12, `lifecycle(state, work) -> Admission`: the table of section 2 written from design/21 sections 11 and 13 and this text. R13, `delegation(org, record, read) -> Admission`, for a token, a stored message, a job step, a member, every store operation and every use of a relational transaction: `Current` for `org` at the record's epoch and in force is `Allowed`; the record's epoch above the table's, `Stale` and `Unknown` are `Deferred`; `Current` for another organisation, the table's epoch above the record's, or the same epoch not in force, is `Refused`. The vectors of R9 gain one per row of the table. This is the "organisation lifecycle model" the item's non-goals defer.
- **#313**: the `ident` module and Rule 10 are added; `TenantPath::prefix` becomes `ListPrefix::partition`; `ReadPath` and `ObjectKey::under` are added; `PathError::SetContext` and `PathError::Name` go, and `ClassForMember` arrives; `ReadPath` and `ListPrefix` keep their context's work kind, delegation and expiry; the AAD uses `archive.<lane>`; `Date` and `YearMonth` follow section 2; codes `TENANT-0001` to `0004` and `0010`. AC-4 adds compile-fail cases for a `Set` prefix and a member write, and a case per class for `ClassForMember`. AC-5 needs the same fix as #312.
- **#1475**: the register check is Rule 12's barrier. It reads each crate after macro expansion and name resolution, on the workspace and, once #1593 exists, on the distribution build's resolved closure, and it lands before any crate that depends on `grdr-ports` takes a registry dependency or a proc macro.
- **#1710**: the alphabet of `OrgId`, `DelegationId` and `DelegationSnapshotId` is pinned so that no rendering contains `/`, `=` or `.`, with a case that an id containing `/` or `..` cannot be built, so `org=<id>/` keeps listings apart; `DelegationId` and `ProviderId` join the ids it settles.

Downstream:
- #1546 moves flattening to the `store` target and builds each `LakeBatch` with `OrgBatch::lake_batch`.
- #1547 commits through `Events::flush`, skips batches whose answer is not `Allowed`, measures cleanup age as section 6 says, keeps its floor per fence, reads each organisation's head on the catalogue's primary after `acquire`, and answers in the order buffer, fence check, floor.
- #1554 takes `OrgRead`, keeps the partition record in `lake_org_partition` and reads it where it is written, and its file-list cache serves a read only at or after the answers' floor.
- The authentication middleware item builds `VerifiedAudience` with the authority and the token's delegation and `VerifiedWorkbenchToken` with the token's `prv` and expiry, mints with the route's declared work kind, and answers on `SingleCtx::answer`.
- J-1 declares each job kind's work kind, records a job's delegation, and mints each step with `single_for_step`.
- The item that builds `grdr-server`'s composition root issues the authority first, with the replica's tenancy table and the process clock, admits the generated dispatch, mints the process's `HolderId`, builds the workbench read path's `MemberReadAuthority` and hands the authority only to the runners `architecture.toml` lists.
- #1555 pages through `Ending::resume`, keeps the whole `Resume` in its page token, and shows "could not look" on `WithoutTail`.
- #1690 keeps its pseudonym test.
- #1593 builds the dispatch over the adapter traits with `Dispatch` where a token is passed on, generates and runs each listed adapter's conformance tests as section 12 says, compiles the closure as Rule 12 says, and runs the register check and ARCH-029 over it.
- #1636's pages list every variant bound to a code.

Constraints. Each issue named below must meet its lines; this RFC does not design them.
- The slice-0 lint item: the `testkit` scan refuses a crate-root item named `grdr_ports_testkit`, an `extern crate ... as` included.
- The slice-0 lint item: the `testkit` scan refuses a crate with the feature whose edition is below 2018.
- The slice-0 lint item: the `testkit` scan compares the macro-expanded code of the conformance build with that of the program build and refuses a difference outside the fixture module and the hook statements.
- #1535 and #312: a `Deferred` batch on a stream with no device lanes rewinds its partition or writes a durable skip record.
- #1535 and #312: the outcome for a refused batch is stated, a batch that `Events::append` refuses with `BatchHeader`, `BatchSchema` or `BatchUnreadable` included.
- The authentication middleware item and J-1: `control` consumers dispatch under a `Change` mint.
- #298 and #312: `Fence`, `FencingToken` and `Lease` are defined under `tenant` and re-exported.
- #312 and #1535: `LakeBatch` carries its partition, and `Events::append` refuses a fence of another partition.
- #312: a trust-core registry lists the work kinds each minting site may mint.
- #1859: SR-58 also requires that every use of a relational transaction re-checks its delegation and that every transaction ends within `relational.transaction-life`.
- #1475, #1593 and the slice-0 lint item: the register check expands every target and feature set a build ships, names `no_mangle`, `export_name` and `link_section` in every edition, generates its toolchain entry as a list of forms, and counts a crate that depends on `grdr-ports` through other crates.
- The slice-0 lint item: the comparison of expanded code redacts environment values, so no fixture setting reaches a log (SD-11).
- Seat 8's cuts C1 and C5 to C8 (comment 7075408097) are build order: their text stays, and the leads order that work within their items.

## Surfaces changed
- `grdr-ports` (layer 2, public): modules `ident`, `tenant` (`authority`, `ctx`, `mint`, `path`, `aad`), `adapter` (the adapter traits and the grant types) and `storage` (`blobs`, `jobs`, `bus`, `relational`, `events`, `PageLimit`, `StoreFault`, and the re-exports of `Admitted`, `PortsCall` and `Refusal`); RFC 0008 adds `clock`, `entropy` and `retry`. Class `experimental`.
- `grdr-ports-testkit` (layer 2, public): `authority`, `tenancy`, `clock`, `reach`, `StopPoint` and `Reached` at the root, the amendment of RFC 0008's conformance runner (section 5) and the fixtures, `arm`, `MemTenancy`, `MemBlobs`, `MemLeases`, `MemBus`, `MemRelational`, `MemEvents`, `ProbeRepo` and one suite per port. Class `experimental`.
- The storage format of lake and blob objects: the key layout of section 2, the identifier rule of Rule 10 and the additional-data encoding `grdr-aad-v1`.
- Data files and protected paths, as proposals: seven code areas in `schema/codes`, the lifecycle table `schema/tenancy/lifecycle.toml`, the `limits.toml` row `relational.transaction-life`, entries in `security/trust-core.paths`, `surfaces.toml` and `architecture.toml`, and the adapter entries `dist.toml` takes.
- No spine text and no protobuf package changes.

## Alternatives
- **Ship the surface `experimental` without an RFC, or one RFC per port.** Both rejected in the ruling on #1535: the class sets break rules, not the route, and the parts share the context, the error shape and the runner. `Clock`, `Entropy` and the retry executor share none of them, so they are RFC 0008.
- **Re-export arrow-rs types from `grdr-ports`.** Zero-copy, but the daemon would link Arrow, and every arrow-rs major (up to one a quarter, https://github.com/apache/arrow-rs/blob/main/README.md, read 2026-11-20) would break the port and every partner adapter. Rejected for Arrow IPC, whose format has stayed backward compatible within version 1 since 1.0 (https://github.com/apache/arrow/blob/main/docs/source/format/Versioning.rst, read 2026-11-20). Brief 11 already recommends Arrow and Parquet as the event format.
- **A row and value model of our own in `grdr-ports`.** It invents a second columnar format beside Arrow (P10, P17) and adds a conversion to every adapter. Rejected.
- **`async-trait` or boxed `dyn` ports, for runtime selection.** A new dependency and an allocation per call. Selection by generated dispatch from `dist.toml` gives the same reach with neither. Rejected.
- **A generic server builder that an embedder calls from its own `main`.** It works, but every embedder writes and maintains composition code, and the release build would select by a second route. Rejected for the one `dist.toml` route design/03 already names.
- **Source scans instead of the seal and the mint authority.** A scan of who implements a port or who calls a minting function holds only where it runs and only over what it reads: a macro, a build script or an `include!` emits what a source scan does not see, and a function pointer or an alias hides a call. Rejected for types. The checks that remain, the register check and ARCH-029, read each crate after macro expansion and name resolution.
- **The `unsafe_code` lint as the `unsafe` barrier.** It fires on `unsafe` written in the crate, not on what another crate's macro, derive or proc macro emits into it, and not on a safe function of another crate that wraps `unsafe`. Rejected for the register check over expanded code and every crate of the closure; the lint stays as a first check.
- **One open trait per port, with admission checked by each `grdr-ports` function.** It needs no adapter traits, but a module implementation could still be handed to other module code, and every adapter would carry the check. Rejected for sealed port traits that only `Admitted` implements, with the check in one trust-core place.
- **An unpublished minting crate restricted by a dependency-graph rule.** It adds a crate and a same-layer edge and still rests on a rule a build must run. Rejected for the mint authority, which the compiler checks at every call.
- **A mint authority without the once-per-process issue.** Any crate could call its constructor. Rejected: issuing once, first, by the composition root makes a second issuer either fail or stop the start.
- **Split `Bus` into an append trait and a consumer trait.** A claim needs a `Lease` and a commit the fence of the partition's lease, so a holder of `Bus` without `Leases` cannot consume. The split would add a trait and stop nothing more. Rejected.
- **One fence form everywhere, lease-checked.** The bus tables may live in a separate database from the lease table (design/20 section 7), so the bus cannot check the lease inside its own transaction. Rejected for two named forms.
- **SERIALIZABLE as a lease-checked form.** A read of the lease row followed by another holder's `acquire` is a single read-write dependency, which serialisable snapshot isolation does not abort, so the stale commit lands. Rejected; only a lock on the lease row counts.
- **Storage-side fencing on the bus with the token stored at first commit, as #299 had it.** It leaves a window in which the old holder commits after the new one starts from an older position, and the new holder's correct offset then reads as `Regress`. Rejected for the compare-and-set stamp at `subscribe`.
- **The same token for a re-acquiring holder, as #298 R3 had it.** Every task of one process shares the token, so a stalled task and its replacement both hold a current fence. Rejected for a new token on every acquisition.
- **`guard(&mut self, &Fence)` or `commit_fenced` chosen at commit time.** A failed guard leaves the transaction usable, and a commit-time choice lets code holding a transaction skip the check. Rejected for `write_fenced`, which binds the fence when the transaction opens.
- **`tail` as a port method that callers union.** A caller that forgets the union, or drops a failed tail, shows "nothing happened" when the product could not look (P9). Rejected for the union inside `execute`.
- **One `Partial` reason for both a hit limit and a missed tail.** One of the two is lost: either paging ends `Complete` with tail rows missing, or a long read against a down tail cannot be paged. Rejected for `Completion` and `Coverage` side by side, with coverage carried in `Resume`.
- **Coverage stored in both the ending and the `Resume` it returns.** The two copies can disagree, and a caller can keep the wrong one. Rejected for one copy in `Ending`, from which `resume()` derives the `Resume`.
- **Read the catalogue head and file list on every `execute`, with no file-list cache.** Correct, but every row read pays the catalogue round trip the cache exists to save. Rejected for the version in the buffer answer, which lets the cache serve whenever it is new enough.
- **A Bus read that returns every partition a kept bucket-map version assigns an organisation, with a key-history table.** The lake adapter would need ingest's bucket function and key rule a second time, and a change to that rule in `ingest` would leave reads asking the wrong partitions. Rejected for the adapter's own partition record, which `append` writes.
- **A cached partition record.** A copy from before a partition's first row for the organisation does not ask that partition, and no answer the read receives can tell it so. Rejected for reading the record where it is written, at one indexed read.
- **The new partition's holder re-reads the head after the old partition's last commit for the organisation.** It needs a signal from the old holder to the new one, and a read during the move still has to ask the old partition. Rejected for asking every partition in the record.
- **Floors kept per `HolderId`.** A task restarted inside one process keeps its predecessor's floor while its new buffer has no drop version, so a stale cache can serve and the row is missing with `Full`. Rejected for floors per fence.
- **Counting any answer from the holder a read reached.** A holder that lost its lease between the lookup and its answer has dropped its buffers and still reports its old floor. Rejected for an answer only under a current fence.
- **Closing the handover window by answering as a failed tail until the new tenure has caught up.** Each tenure would need the partition's last offset at `acquire` passed into the Events adapter, and every handover would end reads `WithoutTail` until the catch-up. Rejected; the window is stated and `Bus::lag` shows it.
- **Lifecycle cells that say yes or no.** `key_unavailable` ingest answers with retry-after and other refusals do not, so `ingest` would branch on the state in code (P14), and a model comparing booleans would not catch it. Rejected for typed answers.
- **Refusing to mint for a `suspended` organisation.** design/21 section 13 keeps `decision` and `spine` ingest, a read-only console and exports for that state, and each needs a context. Rejected for a context that carries the state and the work kind, and a check where work starts and at every store operation.
- **A context from a stored message with no state.** Every consumer then needs its own rule for `None`, and the easy one fails open. Rejected for the state the replica holds, `Unconfirmed` when stale and a refusal when unknown.
- **Delegated `control`-stream work only as jobs.** It leaves the gap between a step's append and the consumer's dispatch, and every other stream needs its own rule. Rejected for the delegation stored with each message and checked by `fetch_batches`.
- **Hook callees written by the adapter, with review checking that each does nothing while unarmed.** A contrib adapter gets no project review, and a callee that takes the adapter's state can change what the suite sees. Rejected for the kit's own `reach`, which takes only a constant, named through the leading `::`.
- **A build script allowed in a `testkit` crate when it does not read `CARGO_FEATURE_TESTKIT`.** A script can build the variable's name at run time or read every variable, so no reading of it tells reliably; whether a crate has a build script is a fact in `cargo metadata`. Rejected.
- **Refuse the file-list cache whenever a buffer answer has dropped nothing since its holder's `acquire`.** Correct, but after every handover each read misses the cache until the new holder's first flush, which can be the whole flush age. Rejected for the floor the holder reads once per organisation after `acquire`.
- **Compile the hook points into every build, inert unless armed, with the fixture in a separate test-only crate.** The admitted type would be the shipped code byte for byte, but every shipped binary would carry crash and fault points, and the arming call would be public API. Rejected for hook points behind the feature, held to one statement form by the `testkit` scan.
- **Per-organisation token exchange for provider hunts.** It gives every hunt a write-capable `SingleCtx` per customer. Rejected for `MemberCtx`.
- **Adapters mint contexts through public hidden constructors.** Every adapter, contrib included, becomes a minting site. Rejected: adapters return plain ids and `grdr-ports` mints.
- **A wrapper for transactions that gives no `&mut` to the adapter's type.** Repositories are implemented on that type and need `&mut` to it. Rejected for `adapter_mut` with the transaction-type rule.
- **A forwarder per token-taking trait, `SubscriptionDispatch` beside a `ResultsDispatch`.** Each is the same two-variant enum. Rejected for one `Dispatch` that implements each such trait.
- **Non-ASCII identifiers with NFC, a bidi-control refusal and a byte bound.** It works but puts Unicode normalisation into the storage format, and every adapter and file system must agree on it byte for byte. Rejected: names people choose go in columns.
- **A per-port copy of the store fault codes.** Twelve codes for one set of causes, each with a page. Rejected for `StoreFault` and the `STORE` area.
- **Declare `retain`, `erase`, `hold`, `manifest`, `put_versioned` and the other query nodes now, returning `NotSupported`.** An adapter could pass the kit without erasure. Rejected under Rule 6.
- **One error enum for the whole crate,** as design/03 section 10 reads today. An adapter crate implements one port and would return variants that cannot happen. Rejected.

## Drawbacks
- Each storage port is two traits, a sealed port trait and an adapter trait, and every call passes through a forwarder in `tenant::admit`.
- The mint authority is issued once per process, so a test process has one authority, held by the kit, and the composition root must issue it before any other code runs.
- Every append and every result batch is encoded and decoded once as Arrow IPC.
- `MemEvents` needs the Arrow crates, so the test kit builds more slowly and #1535 waits on #1532 and splits.
- The storage traits are not dyn-compatible, so the distribution build must generate a dispatch type per port before a contrib adapter can be selected.
- Two fence forms are more to learn than one.
- A new token on every acquisition means a process that re-acquires by mistake invalidates its own earlier fence and loses that work to a retry.
- The Events adapter carries the union, its tail source, the partition record, the coverage rule and the version check on its file-list cache, so it is larger than a plain lake reader. Each `execute` across processes pays one indexed read on the catalogue's primary for the partition record; a read whose cache is older than its buffer answers' floor pays one catalogue read more, and a holder pays one read on the catalogue's primary per organisation after each `acquire`.
- `Subscription::fetch` and `ResultStream::next` take a parameter their adapter receives and does nothing with, and the generated Bus and Events dispatch must nest `Dispatch` for more than two adapters.
- A read asks every partition its organisation has used, so after a re-partition it pays one more tail request per partition the organisation left, and ends `WithoutTail` while any of them is between holders. Each tail answer also pays one fence check.
- Every mint and every store operation reads the replica's tenancy table, every delegated write takes one more row lock, and a provider's job step re-reads its delegation before it is minted. An operation in flight when the state or a delegation changes still completes, bounded by its one call or statement, and a borrow of a relational transaction by the transaction's bound; rows `append` buffered before a move commit at the next flush (section 10). Every relational transaction has a life bound, so a long read or export pages across transactions.
- No crate that depends on `grdr-ports` takes a registry dependency or a proc macro until #1475 lands, so the test kit's Arrow, and every adapter and program that needs one, waits on it.
- While a replica's tenancy copy is stale, its organisations defer everything but reads, and delegated work defers reads too.
- The `testkit` scan limits how an adapter adds test hooks: no other test-only code behind the feature, and no build script in a crate that has the feature.
- The distribution build needs each listed adapter's store to run its conformance tests, which makes a contrib build heavier than a plain compile.
- The `Fixture` trait asks an adapter author for stop and fault hooks, which a small adapter may find heavy; `NotApplicable` keeps the bar honest without hiding what was not run.
- Each deferred method and node costs an amendment RFC when its item arrives.

## Unresolved questions
1. **Deployment-scoped objects.** `state-log/`, `ephemeral/detect/` and the content repository have no organisation, so they cannot be `TenantPath` values. Lean: a separate deployment-scoped trait over a closed `DeploymentPath`, with `put_versioned`, listing and removal, never an org-less `TenantPath`. Settled by an amendment drafted when R-1 or D-1 is specified. It is a prerequisite of the filesystem Blobs adapter item and of the `embedded` profile's first-run slice, so neither assumes it.
2. **Where module repository traits live.** They are implemented on an adapter's transaction types and reached through `adapter_mut`. In `grdr-ports`, every repository change is an RFC. In an unpublished layer 2 crate such as `grdr-repos`, as `grdr-messages` does, it costs one RFC for the crate and its same-layer edge. Lean: the second, with class `internal`: no stability promise to an outside relational adapter until an RFC gives one. An embedder can implement the adapter traits and `ProbeRepo` today, but not the module repositories with any promise. Settled before S-2's first module repository.
3. **The deployment-scoped transaction.** Runtime settings and the operator realm (D-70, design/20 O-3 and O-4) need one, with a witness from the operator realm (design/21 O1). So does the bus log's consumer read: `fetch` reads `bus_message` across organisations, and the application role has no `BYPASSRLS`, so the bus tables need a deployment binding that only the bus adapter's consumer path can set. The bus adapter writes its own tables inside its crate (ARCH-015 allows SQL there), so it does not need this through the Relational port, but design/21 section 2 must state the binding (the placeholder in section 14). The tenancy table each replica holds (section 2) reads organisation states and delegations from rows outside any one organisation's binding too, and the same RFC states how, and names the writer of `delegation_snapshot` rows, which decide what a `SetCtx` can read. Lean: a separate database role for each of these paths with a policy on its tables only. Settled by its own RFC with O-3, which is a prerequisite of the log Bus adapter item and of the authentication middleware item.
4. **The slice-0 surfaces of `grdr-model` and `grdr-schema`** (#18, #278, #279, #282, #284). These signatures name their types (`OrgId`, `DelegationId`, `DelegationSnapshotId`, `Timestamp`, `Lane`, `SessionId`, `DeviceId`, `Epoch`, `Seq`, the column manifest). Settled by the RFC of #1710.

## Review
How review binds the decision (RFC 0001, "Review binds the decision"; ADR-0036):
- RFC 0002 decides no pinned path, so its decision adds no decision line and no file under `rfcs/evidence/`.
- The review set is the `[kinds] rfc` row of `.claude/risk-tiers.toml` on the base, which names `eval-architecture`, plus `eval-security` and `eval-adversarial`. Section 2 governs the trust-core paths `crates/grdr-ports/src/tenant.rs` and `crates/grdr-ports/src/tenant/**`, so the passing evaluators run on two models (D-63, owner instruction 7). #1821 makes those two part of the row for every RFC.
- Each verdict by an evaluator of the set, and each persona council seat comment, gives the three role lines of RFC 0001: `RFC file:` the blob of this file it read (`git rev-parse <commit>:rfcs/0002-grdr-ports-slice-0-surface.md`); `Proposed text: none`, because no pinned path changes; and `Base:` the spine blob in force when it read the RFC, `a80859235e7a2a4444648d6fa8d389d78dde6be9` today (`rfcs/pins.toml`). This RFC's reading of D-35 (section 14) rests on that spine text, so a spine change before the decision means a new revision that names the new base (RFC 0001, "If the spine moves first").
- The decision rests on an `eval-architecture` pass on the blob it decides, with no fail by an evaluator of the set on that blob. Before deciding, the chief architect checks that the seats commented on that blob. ADR-0033 names the pass by its comment link and the blob.
- The file the decision commits differs from that blob only in `State:`, `Decision record:`, lines under `Review` that each hold one comment link, and the `Decision` section. It reaches `main` in `Review` before the commit that decides it, because a file is added only as `Draft` or `Review` (RFC 0001, "RFC states").

Verdicts and seat comments on earlier revisions, and the dispositions of each, are comments on #1688. Verdicts and seat comments on revision 9 are linked below, one per line.

## Decision
Pending.
