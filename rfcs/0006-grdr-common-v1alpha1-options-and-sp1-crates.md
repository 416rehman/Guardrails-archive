RFC: 0006
Title: `grdr.common.v1alpha1`: the option registry, the data-class enums, how `buf` gates them, and the crates SP-1 and descriptor decoding admit
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Draft
Design issue: #1848
Spine: D-06, D-51, D-60, D-61, D-63, D-66, P8, P14, P16, P17 (no spine text changes)
Surfaces: the new protobuf package `grdr.common.v1alpha1` (experimental): `proto/grdr/common/v1alpha1/options.proto` with the enums `DataClass`, `ContentKind` and `Encoding` and six descriptor-option extensions; `buf.yaml`; the committed descriptor set `crates/grdr-proto/descriptors/proto.binpb` of the public crate `grdr-proto`; optional dependencies of `grdr-proto` behind the features `sp1-buffa` and `sp1-prost`. As proposals: design/04 sections 1, 10 and 13, one `[[proto_package]]` row of `surfaces.toml`, and two lines of `security/trust-core.paths`
Decision record: none yet

To comment, write on issue #1848 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

## Summary
The first `proto/` change is one file, `proto/grdr/common/v1alpha1/options.proto`. It holds the three closed annotation enums (`DataClass`, `ContentKind`, `Encoding`) and every option the schema uses: `data_class` on every field, `content_kind`, `policy_readable`, `sealable`, a new `encoding` option on every bytes field, and `wire_name` on every enum value. Readers resolve options by full name from committed descriptor sets, never by number, so the move to a registered range (#398) changes no reader and no event byte. The package is experimental, and its class lives in `surfaces.toml`, not in an option. `buf` gates it as WI-0014's rules W1 to W5 say. For SP-1 (#360), `grdr-proto` gains `buffa`, `buffa-types` and `buffa-build` 0.9.2 behind `sp1-buffa`, and `prost`, `prost-types` and `prost-build` 0.14.6 behind `sp1-prost`. `grdr-schema-lint` decodes descriptors with `buffa-descriptor` 0.9.2, which those crates already bring.

## Motivation
- #353 cannot open its pull request without an RFC line: the package is a wire format (D-61; the #17-E1 decision on #17).
- #353 as written cannot build. Its `options.proto` needs `DataClass` as the type of `data_class`, and its `data_class.proto` needs `wire_name` on every value, so each file imports the other. Protobuf refuses import cycles.
- #360 may not admit a crate until a ruling names it (#17-E2), and #386 has no descriptor decoder until #360 lands one.
- Every later package imports this file. Its options are the mechanism P8 rests on: the capture filter, redaction, the field registry, the lake columns and every export mapping are generated from them (ADR-0007).

## Design

### 1. Package and file
- R1. One file, `proto/grdr/common/v1alpha1/options.proto`, package `grdr.common.v1alpha1`, `syntax = "proto3"`. It imports only `google/protobuf/descriptor.proto`, which `buf` carries locally, so there is no registry dependency (P16; #1697 condition 3).
- R2. The file holds the enums of section 3 and every extension of a `google.protobuf.*Options` message in the namespace (section 2). No other file under `proto/` extends a descriptor options message.
- R3. The package's first segment is `[identity] namespace` in `brand/brand.toml`, `grdr` today (D-66). Regeneration under another namespace is 04-4's (#398).
- R4. The other shared types design/04 section 1 lists for this package (`ActionClass`, `Mode`, `Redaction`, `Sealed` and the rest) go in their own files, one family per file (design/04 section 1 rule 6), each through its own RFC. Every file in the namespace imports `options.proto`.

One file is what removes the cycle. If the pinned `buf` refuses an option used in the file that declares it, `wire_name` alone moves to `proto/grdr/common/v1alpha1/wire_name.proto`, which `options.proto` imports, and R2 and SL11 name both files. Nothing else changes, and #353's hand-off records it.

### 2. The option registry
| Number | Extends | Option | Type | Required on |
|---|---|---|---|---|
| 50001 | `FieldOptions` | `data_class` | `DataClass` | every field of every message in the namespace, never `DATA_CLASS_UNSPECIFIED` |
| 50002 | `FieldOptions` | `content_kind` | `ContentKind` | exactly the fields whose class is `DATA_CLASS_CONTENT` |
| 50003 | `FieldOptions` | `policy_readable` | `bool` | optional; never on a `float` or `double` field |
| 50004 | `FieldOptions` | `sealable` | `bool` | optional; marks a field with a `Sealed` twin (D-35), whose number 04-19 assigns |
| 50005 | `FieldOptions` | `encoding` | `Encoding` | every field whose type, or map value type, is `bytes`, and no other field |
| 50011 | `EnumValueOptions` | `wire_name` | `string` | every enum value except the zero value, unique within its enum |

- R5. These numbers are allocated here only and never reused, also after a removal. They stay in the in-house range 50000 to 99999 until #398 moves all six in one change to the range the protobuf global extension registry grants (external precondition, #17-E3). Option numbers appear in descriptor sets, never in event bytes, so that move changes no event on the wire, no golden vector and no class digest.
- R6. Every tool and generator that reads an option (the lint, the registry writer, the filter and mapping generators) resolves it by full name, `<namespace>.common.v1alpha1.<option>`, from a committed descriptor set, never by number and never through generated code.
- R7. `options.proto` changes only by RFC. Its enums are closed (design/04 section 13 rule 3), and its options are what every filter and mapping is generated from.
- R8. The six extensions describe the schema, not data, so they carry no `data_class`.

### 3. The enums and their source of truth
```proto
enum DataClass {
  DATA_CLASS_UNSPECIFIED = 0;
  DATA_CLASS_IDENTIFIER = 1 [(wire_name) = "identifier"];
  DATA_CLASS_STRUCTURAL = 2 [(wire_name) = "structural"];
  DATA_CLASS_DERIVED = 3 [(wire_name) = "derived"];
  DATA_CLASS_CONTENT = 4 [(wire_name) = "content"];
}
enum ContentKind {
  CONTENT_KIND_UNSPECIFIED = 0;
  CONTENT_KIND_ARGUMENT = 1 [(wire_name) = "argument"];
  CONTENT_KIND_BODY = 2 [(wire_name) = "body"];
}
enum Encoding {
  ENCODING_UNSPECIFIED = 0;
  ENCODING_DIGEST = 1 [(wire_name) = "digest"];
  ENCODING_OPAQUE = 2 [(wire_name) = "opaque"];
}
```
- R9. The three enums are closed: no `_OTHER` value, and each is listed in `crates/grdr-schema/enums.toml` (#386 R5).
- R10. `options.proto` is the one source of these names. The field registry (`crates/grdr-schema/registry/fields.json`, #386 R4), the capture filter (04-16), the lake column manifest, the Cedar schema and the pack validator read the committed descriptor set or files generated from it. None keeps its own list (P17).
- R11. The five commitment classes of design/04 section 10 are named from the wire names: `identifier`, `structural`, `derived`, `content.argument` and `content.body`. That spelling is the one `envelope.withheld`, the registry and every export use. RFC 0004's testkit describes C fields with the same five classes. RFC 0004 section 10 leaves the comparison of C classes with the wire's to review of the contract, and this RFC does not change that.
- R12. `digest` is the output of a hash or keyed hash whose algorithm `schema_rev` fixes, rendered `<alg>:<lowercase hex>` in JSON, feeds, Cedar and exports (design/04 section 1 rule 3). `opaque` is bytes no reader interprets, such as salts, signatures and ciphertext, rendered as proto3 JSON renders bytes. A generator that meets any other value fails. Text is always `string`, which protobuf holds to UTF-8.
- R13. A zero value carries no `wire_name` and is never rendered. A zero or undeclared value of a closed enum, read where a value is required, is a finding or an error, never a default. A `data_class` number the enum does not declare is SL01.
- R14. Leaves. A leaf field's class is its own. A field whose type is a message outside the namespace, a well-known type such as `google.protobuf.Timestamp`, is a leaf, and its class covers everything below it. A map entry's key and value take their map field's class. A field whose type is a message of the namespace carries the most sensitive class of the leaves below it, ranked by the capture level at which a class first leaves the device (design/04 section 11): `content.body`, then `content.argument`, then the three metadata classes, which rank equal. A pack that reads the whole message is then held to its most sensitive part.

### 4. Stability
- R15. `grdr.common.v1alpha1` is experimental: nothing is stable before one external embed pilot completes (D-60). Its class lives in one `[[proto_package]]` row of `surfaces.toml` with the keys `package` and `class`, each a double-quoted value on its own line, the rule RFC 0004 section 2 sets for `[[c_header]]` rows (ADR-0020).
- R16. No option carries stability, per field or per file. The class has one source (ADR-0020, P17), and the `v1alpha1` suffix already states it. SL12 holds each package's suffix to its row: `alpha` for experimental, `beta` for beta, none for stable.
- R17. During `v1alpha1`, `buf breaking` uses `WIRE_JSON` (design/04 section 13), and the freeze (04-29) renames the package to `v1` and switches to `FILE`. Every change to `proto/**` names an accepted RFC (D-61; `rfc-required`, #1741 R1). A change that moves a field to a class that leaves the device at a lower capture level is a breaking change under rule 9, although `buf breaking` does not read options. The committed field registry shows it as a diff line, and the RFC that makes it lists it under "Surfaces changed".

### 5. How `buf` gates it
- R18. `buf.yaml` at the repository root is `version: v2` with one module at `proto`, lint `STANDARD` and breaking `WIRE_JSON` (#353 R1). It sets `lint.disallow_comment_ignores: true`, because `buf` otherwise honours a `// buf:lint:ignore` comment in any `.proto` file. It has no `except`, `ignore`, `ignore_only`, `ignore_unstable_packages` or `disable_builtin` key, at the top level or on the module: `ignore_unstable_packages` alone would skip every `v1alpha1` package (buf.yaml v2 reference, https://buf.build/docs/configuration/v2/buf-yaml/, read 2026-11-21). It is lint configuration, so it changes only through an item whose write set names it. On acceptance it and `schema/fixtures/buf/**` join `security/trust-core.paths` (section 8).
- R19. `buf` runs only as a plain command, in a session or in the `proto` job of `verify.yml` (#1842), at the version `[tool.buf]` of `supply-chain/build-tools.toml` pins (#1697). It runs offline: no registry dependency, no remote plugin and no login (#1697 condition 3). `cargo test --workspace --locked` never runs `buf` or `protoc` (W1).
- R20. Rust reads committed descriptor sets only (W2). `crates/grdr-proto/descriptors/proto.binpb` is the output of `buf build proto --as-file-descriptor-set --exclude-source-info -o crates/grdr-proto/descriptors/proto.binpb`. It keeps its imports, because a descriptor pool needs `google/protobuf/descriptor.proto` to read options by name, so the command never takes `--exclude-imports`. Every change to `proto/` regenerates it in the same pull request.
- R21. CI rebuilds every committed set and golden vector and fails on any byte difference (W3; #1842 R5 to R7). It runs the breaking fixtures under `schema/fixtures/buf/<case>/` as negative controls (W4; #1842 R4).

### 6. Crates for SP-1 and for descriptor decoding
- R22. #360 adds exactly these as optional dependencies of `grdr-proto`, each at an `=` version. `sp1-buffa` and `sp1-prost` each enable only their own rows, and neither is a default feature.

| Crate | Version | Edge, feature | Features | Licence | crates.io owners | Published | crates.io checksum |
|---|---|---|---|---|---|---|---|
| `buffa` | 0.9.2 | normal, `sp1-buffa` | `default-features = false`, `std` | Apache-2.0 | `iainmcgin` | 2026-09-03 | `a92f2f5df67a9d5ccfc65237bfc954c56328aee40a04a9b92381ecba370be246` |
| `buffa-types` | 0.9.2 | normal, `sp1-buffa` | default | Apache-2.0 | `iainmcgin` | 2026-09-03 | `b15b05c8418f1e200e406e5b19df97400dffa833e2450e4392c506896cbc97ac` |
| `buffa-build` | 0.9.2 | build, `sp1-buffa` | default | Apache-2.0 | `iainmcgin` | 2026-09-03 | `eee6b6b4a8d23f1f98a043f188f4d9d2ef8bee43191f42e93ac577f3c3b0f334` |
| `prost` | 0.14.6 | normal, `sp1-prost` | default (`derive`, `std`) | Apache-2.0 | `danburkert`, `github:tokio-rs:prost-core` | 2026-11-12 | `3ef0b569d1d907ab3a28596aee62cf1f61dacb0529a4bedcd8e7460e2d5228b4` |
| `prost-types` | 0.14.6 | normal, `sp1-prost` | default | Apache-2.0 | as `prost` | 2026-11-12 | `f29a7c4c7a84cef41a53d338a2d10d4f1b043ea5c3dde26db22ee2c9c1b1c75b` |
| `prost-build` | 0.14.6 | build, `sp1-prost` | `default-features = false` | Apache-2.0 | as `prost` | 2026-11-12 | `b6e4d69d0fa3e7f6f9cf6b53a0e83e4fc99ba3586f65ce166cff30bd13bb4ad2` |

`buffa-types` and `prost-types` carry `google.protobuf.Timestamp`, which the SP-1 schema uses (#368 R1).

- R23. Build scripts generate only from committed sets and never run `protoc` or `buf` (W2). buffa uses `buffa_build::Config::descriptor_set`, never `use_buf`. prost uses `prost_build::Config::skip_protoc_run` with `file_descriptor_set_path`, or `compile_fds` over the set decoded with `prost-types`; the `prost` and `prost-types` build-dependencies that `compile_fds` needs are already in the closure.
- R24. `grdr-schema-lint` (#386) decodes with `buffa-descriptor` 0.9.2 and its feature `reflect`, whatever SP-1 decides. The crate enters `Cargo.lock` in #360 as a dependency of `buffa-codegen`, and `reflect` adds no package, so #386 adds its own entry and no third-party package (#360 R2). The lint builds a pool with `DescriptorPool::decode` over the committed set, then reads each option through `DynamicMessage::from_options` and `DescriptorPool::extension_by_name` (R6). #386 therefore no longer needs #368.
- R25. Closure, resolved with cargo 1.99.1 and resolver 3 for every target, against `main` at `7d2de57`, whose lockfile holds no third-party package:
  - `sp1-buffa` builds 32 packages, 13 of them on normal edges, the part a release would link if buffa wins;
  - `sp1-prost` builds 35 packages, 11 of them on normal edges;
  - the lint's decoder closure is 13 packages, all inside `sp1-buffa`'s;
  - `Cargo.lock` gains 63 packages: the 50 either feature builds, and 13 that Cargo locks as optional dependencies no enabled feature reaches (`aho-corasick`, `itoa`, `jiff`, `jiff-core`, `jiff-static`, `memchr`, `portable-atomic`, `portable-atomic-util`, `serde`, `serde_core`, `serde_derive`, `serde_json`, `zmij`);
  - 16 of the 63 are also rows of #1575's admission, so #360 adds 47 if #1575 lands first.
- R26. Licences. Every expression is satisfied by the permissive class of `supply-chain/licences.toml`: 36 `MIT OR Apache-2.0`, 10 `Apache-2.0`, 5 `Apache-2.0 OR MIT`, 5 `Unlicense OR MIT`, 2 `MIT`, 2 `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT`, 1 `Zlib`, 1 `(MIT OR Apache-2.0) AND Unicode-3.0`, and `r-efi`'s `MIT OR Apache-2.0 OR LGPL-2.1-or-later`, taken as MIT. No crate is in `supply-chain/do-not-read.toml` or `deny.toml`'s bans.
- R27. `hashbrown` stays at 0.17.1, #1575's row. A fresh resolve picks 0.17.2, published 2026-11-22T01:08:02Z, inside the three-day cooldown of design/35 section 2.6.
- R28. #360 records the admission in `supply-chain/admissions.toml` in #1575's format: the 63 rows with name, version, licence and checksum, the build scripts and proc macros, and a justification per direct crate. Its write set gains that file, and it waits on #1575, which creates it. A resolve at implementation time that differs from R25 goes in #360's hand-off for `eval-licence` and `eval-security`. Only a different direct crate or version amends this RFC.

Maintainers and what they bring:
- **buffa.** All five buffa crates and `smoothutf8`, which the build graph pulls in, have one crates.io owner, `iainmcgin`; the repository is `anthropics/buffa`, pre-1.0. Unknown fields are kept by default, and `buffa-build`'s `preserve_unknown_fields` is on unless turned off. A text search of `src/` for `unsafe {`, `unsafe fn` and `unsafe impl` finds 28 lines in `buffa` and none in `buffa-types` or `buffa-descriptor`. The risk of one owner account reaches `grdr-proto` only behind `sp1-buffa` until SP-1 is decided, and `grdr-schema-lint`, a tool crate no shipped crate may depend on (ARCH-001).
- **prost.** Owned by `danburkert` and the team `github:tokio-rs:prost-core`. Its README marks it passively maintained: no new features, security fixes released promptly. It drops unknown fields (tokio-rs/prost#2, open since 2017-06-26), which is why design/04 section 1 pairs it with "never re-encode". The same search finds 12 lines in `prost` and none in `prost-types`.
- **Build-time code.** The two features build these build scripts: `anyhow`, `getrandom`, `libc`, `prettyplease`, `proc-macro2`, `quote`, `rustix`, `rustversion` and `thiserror`. They build these proc macros: `prost-derive`, `rustversion` and `thiserror-impl`.

What was run, on the probe manifest of R22 with the repository's `deny.toml`:
- `cargo deny ... check licenses advisories bans sources` (cargo-deny 0.21.0; the pinned 0.22.0 is not installed here): exit 0. It printed two duplicate-version warnings, `hashbrown` 0.15 and 0.17 and `syn` 2 and 3. RustSec advisory-db was at commit `55e1c3dfbd834237a05bbbf7b50ba3b5be27b662`.
- OSV `querybatch` for all 63 packages: no id.
- The crates.io sparse index for all 63: every checksum matches, and none is yanked. Only `hashbrown` 0.17.2 falls inside the cooldown (R27).

### 7. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| Every field has a class; `content_kind` exactly on content; no float marked `policy_readable`; closed enums; no `Any` or `Struct`; no field in 900 to 999 | SL01 to SL07 over the committed set | #386 |
| Zero values have no `wire_name`; every other value has a unique one | SL04, amended to exempt zero values | #386 |
| `encoding` on bytes fields and nowhere else; the registry records it | SL10; a `fields.json` key | Filed on acceptance |
| Descriptor-option extensions only in `options.proto` | SL11 | Filed on acceptance |
| A package's suffix matches its `surfaces.toml` class | SL12, and the `[[proto_package]]` row | Filed on acceptance (two items) |
| A namespace-typed field carries its most sensitive leaf class | SL13 | Filed on acceptance |
| Options are read by name, so numbers can move | #386 AC-4's namespace fixture, and a fixture with renumbered options in the SL10 to SL13 item | #386; filed on acceptance |
| A renumbered field or a reused enum value fails | The breaking fixtures, run by the `proto` job | #353; #1842 R4 |
| Committed sets and vectors are fresh | Rebuild and byte compare, with a stale-set negative control | #1842 R5 to R7 |
| `buf.yaml` holds R18's rules, and it and its fixtures change only with the full lane | #353 AC-1 for the first text; two lines in `security/trust-core.paths` for every later change | #353; filed on acceptance (lead-agent-kit) |
| Every `proto/**` change names an accepted RFC | `rfc-required` | #1741 |
| `grdr-proto` has exactly R22's crates, licences in the class, no `protoc` | #360 AC-1 to AC-4, `cargo deny check`, the admission row | #360 |
| The losing codec's crates leave `Cargo.lock` | The item that makes SP-1's winner the crate's codec | #368's decision record files it |

### 8. Proposed changes to design documents and gate files
Each lands through an item whose write set names its file, filed on acceptance.
- **design/04 section 1.** The code block becomes `options.proto` as sections 2 and 3 give it, with `encoding` (50005) and the three enums. The naming rules gain: `proto3` for every `v1alpha1` file; every descriptor-option extension in `options.proto`; options read by full name; zero values without a `wire_name`; the leaf rule of R14.
- **design/04 section 10.** The commitment classes are spelt `content.argument` and `content.body`, as `withheld` already does.
- **design/04 section 13.** The check table gains a row for SL10 to SL13 under `grdr-schema-lint`.
- **`surfaces.toml`.** `[[proto_package]]` with `package = "grdr.common.v1alpha1"` and `class = "experimental"`; created by whichever of this item and #1817 lands first.
- **`security/trust-core.paths`.** `buf.yaml` and `schema/fixtures/buf/**`.

### 9. What each item changes
This RFC is normative. Each lead writes these changes back into its item before readying it.
- **#353.** R1 gains R18's two rules for `buf.yaml`. R2 and R3 become sections 1 to 3: one `options.proto` with three enums and six extensions, values named in full (`DATA_CLASS_IDENTIFIER = 1`), and `syntax = "proto3"`. Fixture messages carry `encoding` on bytes fields as well as `data_class` on every field. R5's command keeps imports (R20). The pull request names `RFC: 0006`.
- **#360.** R1's list is R22's table, and R2's decoder is `buffa-descriptor` 0.9.2 (R24). It holds `hashbrown` at 0.17.1 (R27), writes the admission row (R28), gains `supply-chain/admissions.toml` in its write set, and is blocked by #1575. The pull request names `RFC: 0006`.
- **#386.** R0's decoder is R24's. R1 reads options by full name (R6). A new failure mode: a set that lacks an option of section 2 exits 2 with a code lead-core registers, never `Clean`. SL04 exempts zero values. R5 lists `Encoding` as well. The blocked-by link to #368 is removed.
- **#368.** No change. Its decision record names the winner. If prost wins, the record also says whether `grdr-schema-lint` stays on `buffa-descriptor` or moves to `prost-reflect` 0.16.5 (MIT OR Apache-2.0, one more package).
- **#398.** Moves 50001 to 50005 and 50011 together (R5).
- **#1842.** No change.

Filed on acceptance, each citing this RFC and its decision record:
- the `[[proto_package]]` row of `surfaces.toml`, a protected trust-core change (chief-architect);
- SL10 to SL13, the registry's `encoding` key and a fixture with renumbered options in `grdr-schema-lint`, blocked by #386 and the row item (squad core);
- the two `security/trust-core.paths` lines, after #353 (lead-agent-kit);
- the design/04 amendments of section 8 (chief-architect).

### 10. Failure modes
| Failure | Outcome | Visible as |
|---|---|---|
| The pinned `buf` refuses an option used in its own file | #353 takes section 1's fallback | #353's hand-off |
| A descriptor set lacks an option of section 2, or the namespace in it differs from the manifest's | The lint exits 2 with its code; it never reports `Clean` | stderr and the CI step |
| A `data_class` number the enum does not declare | SL01 at that field | The lint's finding |
| A generator meets an `Encoding` value it does not know | The generator fails, naming the field | Build or job log |
| A committed descriptor set or vector is stale | #1842 R5 or R6 fails, naming the file and the rebuild command | Job log |
| A codec's build script needs `protoc` or `buf` | #360 or #368 stops `blocked` (W2) | The hand-off |
| A resolve differs from R25 at implementation time | Listed for `eval-licence` and `eval-security` (R28) | #360's hand-off |

## Surfaces changed
- The new protobuf package `grdr.common.v1alpha1`, experimental: `options.proto` with the enums and extensions of sections 2 and 3. It defines no message, so no event changes.
- `buf.yaml`, and the committed descriptor set in `grdr-proto`, a public layer 0 crate whose class is experimental.
- `grdr-proto` gains optional dependencies behind two features that are not defaults. The default build and its closure are unchanged.
- As proposals: design/04 sections 1, 10 and 13, a `surfaces.toml` row and two `security/trust-core.paths` lines. No spine text, pinned path, Cedar schema, licence policy or same-layer edge changes.

Data classes (P8): this RFC adds the class mechanism and no data field. The lint and the build scripts read schema descriptors only, which are `structural`, and log no event data. Assurance effect (P1): none. No action class changes `visibility`, `control`, `on_failure` or `tamper`.

## Alternatives
- **Two files, `options.proto` and `data_class.proto` (#353 as written).** An import cycle. Rejected for one file.
- **A per-field or per-file `stability` option.** A second source beside `surfaces.toml` (ADR-0020, P17), and the package suffix already states the class. Rejected. If a stable package ever needs an experimental field, its RFC adds what it needs then.
- **No `encoding` option until the first bytes field (04-5).** Every generator would then guess digest fields from names or a side table, which ADR-0007 rejected for classes. Rejected: it costs one option now.
- **Editions instead of `proto3`.** Both SP-1 candidates would have to generate them, and design/04's rules are written in `proto3` terms. Deferred to an RFC.
- **`prost-reflect` 0.16.5 as the lint's decoder** (MIT OR Apache-2.0, owner `andrewhickman`; `DescriptorPool::decode` keeps extension options; read 2026-11-21 on docs.rs). It works and adds one package. If buffa wins, design/04's first choice, it would keep the prost crates in the lockfile for a tool crate alone, while `buffa-descriptor` costs nothing. It stays the fallback of #368's decision record.
- **`prost-types` alone.** It drops custom options with every other unknown field, so it cannot read `data_class`. Rejected.
- **Reading option numbers from raw `FieldOptions` bytes in the lint.** A protobuf decoder of our own in a gate, beside the codec (P17). Rejected.
- **Reading options through `grdr-proto`'s generated extension constants.** This ties the lint to the SP-1 outcome and to the numbers #398 moves. Rejected for R6.
- **A third SP-1 candidate.** `protobuf` 3.7.2 (MIT) has had no release since 2025-03-10, and the crate name now carries the official 4.x line, published as semver pre-releases such as `4.36.2-release` over `google-protobuf`; D-63 admits no pre-release. Design/04 names two candidates. Rejected.
- **`--exclude-imports` on the committed set.** A pool could not decode options without `descriptor.proto`. Rejected.
- **`prost-build` with default features.** `format` adds `prettyplease` 0.3 and `syn` 3 to a build script whose output nobody reads. Rejected.

Sources, all read 2026-11-21: the crates.io API and sparse index for every crate named here; https://docs.rs/buffa-build/0.9.2/buffa_build/struct.Config.html; https://docs.rs/prost-build/0.14.6/prost_build/struct.Config.html; https://docs.rs/buffa/0.9.2/buffa/; https://docs.rs/prost-reflect/0.16.5/prost_reflect/struct.DescriptorPool.html; https://raw.githubusercontent.com/anthropics/buffa/main/README.md; https://raw.githubusercontent.com/tokio-rs/prost/master/README.md; https://api.github.com/repos/tokio-rs/prost/issues/2; the published source of `buffa-descriptor` 0.9.2 (`src/pool.rs`, `src/reflect/dynamic.rs`).

## Drawbacks
- A spike locks 63 packages, which stay until the adopting item removes the losing codec's crates.
- buffa is pre-1.0, and one crates.io account owns six of the crates. The lint depends on it even if prost wins, unless #368's record moves it.
- The option numbers stay in the in-house range until a third party grants a registered one (#398).
- `encoding` is one more option on every bytes field. R14 makes the class of a namespace-typed field a derived fact that SL13 keeps in step.
- `buf.yaml` and its fixtures become trust core, so a rule change takes the full lane.

## Unresolved questions
1. **The registered extension range.** It waits on the protobuf global extension registry (#398, #17-E3). Nothing here depends on it.
2. **If prost wins SP-1.** #368's decision record decides the lint's decoder (section 9).
3. **Map order.** `buffa`'s default map type is a hash map, so two encodings of one map need not match byte for byte. The schema allows one map, `native` (design/04 section 1 rule 4), and SP-1's schema has none. Integrity hashes the bytes as first encoded and nothing re-encodes before verifying (rule 8). #368's lead decides whether SP-1 adds a `native`-shaped case.
4. **Not checked here.**
   - `buf`: no pin exists yet (#1697), so `buf build` and `buf lint` have not run on section 1's layout. #353 AC-1 and AC-4 are the first runs, with the fallback of section 1.
   - The pinned cargo-deny 0.22.0; 0.21.0 ran.
   - Either codec's behaviour, which is SP-1's job.
   - `buffa-descriptor`'s reading of custom options was read in its published source, not run.

## Review
The lane is the one the session set on #17 for this surface:
- `eval-architecture`;
- `eval-security`;
- `eval-adversarial`, bounded to the seeds below;
- persona council seats 3 (`persona-soc-analyst`: wire names, digest rendering and class names in exports), 5 (`persona-oem-partner`: embedding, the stability class and the option numbers) and 6 (`persona-privacy-officer`: data classes, the leaf rule and reclassification).

Each puts one comment on #1848. Each comment opens with the blobs it read, one per line:
- `rfc-file=<blob of rfcs/0006-grdr-common-v1alpha1-options-and-sp1-crates.md at the commit reviewed>`;
- `base=a80859235e7a2a4444648d6fa8d389d78dde6be9`, the spine pin;
- `read=<path>@<blob>` for every other file it relied on.

A comment without these lines does not count. This RFC changes no pinned path, so its decision has no decision line (ADR-0036). The decided file may differ from the reviewed blob only where RFC 0001's "Review binds the decision" allows.

This text was written against these blobs, on `main` unless named:
- `docs/design/04-event-model-and-schemas.md`: `e77880a12d2f42e715836a6da9598b86f33b20b0`;
- `rfcs/0004-c-header-generation-and-drift-check.md`: `1f998f42db6c6ea6640c55df0a655e450759340f`;
- `supply-chain/licences.toml`: `65338a382a81c1ac500c533e22fa6ee22397928d`;
- `deny.toml`: `2d0457ff71ea5c9bba91de0a580cd80f650d1479`;
- ADR-0007: `5b6cdffc1648817f3e48a821ef2b34383b24b8f1`;
- ADR-0020: `e0a2998b7baed6c2aa21629ce25d61f2fa12ad20`;
- `supply-chain/admissions.toml` on `issue/1575`: `1b25c164ade9d313e80bd6286444e289062d7f1f`.

`eval-adversarial` checks these seeds and what they reveal. It does not run an open search. Each seed asks whether the text, as written, lets the case through:
- A1. A field whose `data_class` comes from a same-named extension in another package.
- A2. A `data_class` number the enum does not declare.
- A3. A namespace-typed field marked `structural` over a content leaf.
- A4. A oneof member, a nested message's field or a map field with no class.
- A5. A committed descriptor set that drops a field the tree has.
- A6. An option declared outside `options.proto` under number 50001.
- A7. A look-alike crate name, or a version outside R22, in `Cargo.lock`.
- A8. A build script that can reach `protoc` or `buf`.
- A9. A package suffix that disagrees with its `surfaces.toml` class.
- A10. A `buf.yaml` or a `.proto` comment that switches off a lint or breaking rule for some files.

## Decision
Not decided.
