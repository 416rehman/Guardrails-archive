RFC: 0006
Title: `grdr.common.v1alpha1`: the option registry, the data-class enums, how `buf` gates them, and the crates SP-1 and descriptor decoding admit
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Draft
Design issue: #1848
Spine: D-06, D-51, D-60, D-61, D-63, D-66, P8, P14, P16, P17 (no spine text changes)
Surfaces: the new protobuf package `grdr.common.v1alpha1` (experimental): `proto/grdr/common/v1alpha1/options.proto` with the enums `DataClass` and `ContentKind` and five descriptor-option extensions; `buf.yaml`; the committed descriptor set `crates/grdr-proto/descriptors/proto.binpb` of the public crate `grdr-proto`; optional dependencies of `grdr-proto` behind the features `sp1-buffa` and `sp1-prost`. As proposals: two data files of `grdr-schema` (`capture.toml`, `reclassifications.toml`), two line forms an RFC uses to decide a reclassification or a release, design/04 sections 1, 10, 11 and 13, one `[[proto_package]]` row of `surfaces.toml`, and four lines of `security/trust-core.paths`
Decision record: none yet

To comment, write on issue #1848 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This is revision 3. Revision 2 answered round 1's `eval-architecture` verdict (https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7072892832). Round 2's delta verdict (https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073095604) closed M1, M3, M4 and m1 to m6, and raised N1 and n1 to n4. Revision 3 answers them:
- N1 is R13, R17, R19 and SL12. SL12 reads ranks and levels from the base `capture.toml` and fails a level that releases a class the base held back. A record counts only when an RFC accepted on the base carries the same decision line (R17). Both data files are trust core.
- n1 is SL10, n2 is R13, n3 is R31, and n4 is in Alternatives. R19 states that the gate item's own criteria are fresh-copy runs.

## Summary
The first `proto/` change is one file, `proto/grdr/common/v1alpha1/options.proto`. It holds two closed enums, `DataClass` and `ContentKind`, and the five options #353 needs: `data_class` on every field, `content_kind`, `policy_readable`, `sealable`, and `wire_name` on every enum value. Tools find the options package from each file's import and read options by full name, so neither the version nor the option numbers are literals. The capture-level matrix and the rank of each class are one trust-core data file. A check against the base fails any field that moves to a lower class, and any level that releases a class, unless an RFC accepted on the base carries that exact decision line. The package is experimental, and `surfaces.toml` is the only source of that class. `buf` gates it under WI-0014's rules W1 to W5, and its configuration lands as trust core with negative controls run against the real module. For SP-1 (#360), `grdr-proto` gains `buffa`, `buffa-types` and `buffa-build` 0.9.2 behind `sp1-buffa`, and `prost`, `prost-types` and `prost-build` 0.14.6 behind `sp1-prost`. `grdr-schema-lint` decodes descriptors with `buffa-descriptor` 0.9.2.

## Motivation
- #353 cannot open its pull request without an RFC line: the package is a wire format (D-61; the #17-E1 decision on #17).
- #353 as written cannot build. Its `options.proto` needs `DataClass` as the type of `data_class`, and its `data_class.proto` needs `wire_name` on every value, so each file imports the other. Protobuf refuses import cycles.
- #360 may not admit a crate until a ruling names it (#17-E2), and #386 has no descriptor decoder until #360 lands one.
- Every later package imports this file. Its options are the mechanism P8 rests on: the capture filter, redaction, the field registry, the lake columns and every export mapping are generated from them (ADR-0007).

## Design

### 1. Package and file
- R1. One file, `proto/grdr/common/v1alpha1/options.proto`, package `grdr.common.v1alpha1`, `syntax = "proto3"`. It imports only `google/protobuf/descriptor.proto`, which `buf` carries locally, so there is no registry dependency (P16; #1697 condition 3).
- R2. It holds the enums of section 3 and every extension of a `google.protobuf.*Options` message the namespace declares. It declares no message.
- R3. The package's first segment is `[identity] namespace` in `brand/brand.toml`, `grdr` today (D-66). Regeneration under another namespace is 04-4's (#398).
- R4. The other shared types design/04 section 1 lists for this package (`ActionClass`, `Mode`, `Redaction`, `Sealed` and the rest) go in their own files, one family per file (design/04 section 1 rule 6), each through its own RFC. Every file of the namespace except the options files imports `options.proto`.

One file is what removes the cycle. If the pinned `buf` refuses an option used in the file that declares it, `wire_name` alone moves to `proto/grdr/common/v1alpha1/wire_name.proto`, which `options.proto` imports. Both are then options files: R2, R4 and SL10 read "the options files" for "`options.proto`", and nothing else changes. #353's hand-off records which layout landed.

### 2. The option registry
| Number | Extends | Option | Type | Required on |
|---|---|---|---|---|
| 50001 | `FieldOptions` | `data_class` | `DataClass` | every field of every message in the namespace, never `DATA_CLASS_UNSPECIFIED` |
| 50002 | `FieldOptions` | `content_kind` | `ContentKind` | exactly the fields whose class is `DATA_CLASS_CONTENT` |
| 50003 | `FieldOptions` | `policy_readable` | `bool` | optional; never on a `float` or `double` field |
| 50004 | `FieldOptions` | `sealable` | `bool` | optional; marks a field with a `Sealed` twin (D-35), whose number 04-19 assigns |
| 50011 | `EnumValueOptions` | `wire_name` | `string` | every enum value except the zero value, unique within its enum |

- R5. A number is allocated here only and never reused. A retired option stays declared with `[deprecated = true]`, so its number stays taken. SL12 fails a change that drops an option or gives its number to another name. The numbers stay in the in-house range 50000 to 99999 until #398 moves all five in one change to the range the protobuf global extension registry grants (external precondition, #17-E3; SL09 checks the range). Option numbers appear in descriptor sets, never in event bytes, so that move changes no event on the wire, no golden vector and no class digest.
- R6. Every tool and generator that reads an option (the lint, the registry writer, the filter and mapping generators) takes the options package of a file from that file's import: the package of the options file it imports, which is `<namespace>.common.<version>`. For an options file, which uses `wire_name` on its own enums, it is the file's own package. It then resolves `<options package>.<option>` by full name, from a committed descriptor set, never by number and never through generated code. The namespace comes from the brand manifest and the version from the import, so a `v1alpha1` file and a `v1` file can coexist during the N and N-1 overlap (design/04 section 13 rule 2), and no reader holds a version literal.
- R7. `options.proto` changes only by RFC. Its enums are closed (design/04 section 13 rule 3), and its options are what every filter and mapping is generated from.
- R8. The extensions describe the schema, not data, so they carry no `data_class`.

### 3. The classes and their source of truth
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
```
- R9. Both enums are closed: no `_OTHER` value, and each is listed in `crates/grdr-schema/enums.toml` (#386 R5).
- R10. `options.proto` is the one source of the class names. Every tool under `crates/` that reads classes reads the committed descriptor set, `capture.toml` (R13) or a file generated from them: the field registry (`crates/grdr-schema/registry/fields.json`, #386 R4), the capture filter generator (04-16), the lake column manifest, the Cedar schema and the pack validator. The one other list is the `DataClass` enum of RFC 0004's `grdr-cabi-testkit`, which R11 holds to `capture.toml`.
- R11. The five commitment classes of design/04 section 10 are named from the wire names: `identifier`, `structural`, `derived`, `content.argument` and `content.body`. That spelling is the one `envelope.withheld`, the registry and every export use. RFC 0004's testkit describes C fields with five classes of its own (`Identifier`, `Structural`, `Derived`, `ContentArgument`, `ContentBody`). A test in the testkit, filed on acceptance, reads `capture.toml` and fails unless the testkit renders its five classes as exactly the five names there. That fixes a spelling RFC 0004 left open; no header exists yet, so no header text changes. This RFC does not change what RFC 0004 section 10 leaves to review: whether a C field's class is the right one.
- R12. A zero value carries no `wire_name` and is never rendered. A zero or undeclared value of a closed enum, read where a value is required, is a finding or an error, never a default. A `data_class` number the enum does not declare is SL01.
- R13. `crates/grdr-schema/capture.toml` is design/04 section 11's matrix as data, with the rank of each class. SL12, SL13, the 04-16 filter generator, the pack validator's class ceiling and R11's testkit test read it, and none keeps its own copy (P14, P17). It decides what leaves the device, so it is a trust-core path (R19), and SL12 fails a change that releases anything the base held back unless an accepted RFC decided it (R17). Its content:

```toml
# design/04 section 11 as data. Rank is table order: later is more sensitive.
# pseudonymous: a value that identifies a human principal appears in this class only as a
# pseudonym, at every level (P8, D-51). Changes only through an RFC's decision lines (RFC 0006 R17).
[[class]]
name = "structural"
[[class]]
name = "derived"
[[class]]
name = "identifier"
pseudonymous = true
[[class]]
name = "content.argument"
[[class]]
name = "content.body"

[[level]]
name = "metadata"
ships = ["structural", "derived", "identifier"]
[[level]]
name = "redacted arguments"
ships = ["structural", "derived", "identifier"]
redacted = ["content.argument"]
[[level]]
name = "redacted content"
ships = ["structural", "derived", "identifier"]
redacted = ["content.argument", "content.body"]
[[level]]
name = "full content"
ships = ["structural", "derived", "identifier", "content.argument", "content.body"]
```

  The rank is the position of a `[[class]]` table, which orders the three metadata classes as well. `pseudonymous` is a property of the class, not of a level, because D-51's two pseudonymisation layers apply wherever an identifier travels. `identifier` ranks above `derived` because an identifier joins records across events and back to a principal, device or artefact (D-51), while a derived value describes one event. `structural` ranks lowest because it describes shape only.
- R14. Left to the RFC of the first item that adds a message field (#18, 04-5): an `encoding` option for bytes fields with its values (`Receipt.decision`, `native` and `Redaction.original` among the cases it is checked against), the data file that names each digest's `<alg>` label, and the class of a field whose type is a message. The capture filter and the class-digest walk read leaf classes only (design/04 sections 10 and 11), so nothing in this RFC reads a message-typed field's own class.

### 4. Stability
- R15. `grdr.common.v1alpha1` is experimental: nothing is stable before one external embed pilot completes (D-60). Its class lives in one `[[proto_package]]` row of `surfaces.toml` with the keys `package` and `class`, each a double-quoted value on its own line, the rule RFC 0004 section 2 sets for `[[c_header]]` rows (ADR-0020). `package` is the name below the namespace (`common.v1alpha1`), so a namespace rename edits no row (04-4).
- R16. `surfaces.toml` is the only source of a package's class. No option carries stability, per field or per file. The version suffix follows design/04's own naming: `v1alpha1` until the freeze, `v1` after it (04-29). A `v1` package may stay experimental, as D-60 and ADR-0020 allow. SL11 keeps the one rule that needs no second statement: a row whose class is `stable` names no package with an unstable suffix.
- R17. During `v1alpha1`, `buf breaking` uses `WIRE_JSON`, and the freeze switches it to `FILE` (design/04 section 13). Every change to `proto/**` names an accepted RFC (D-61; `rfc-required`, #1741 R1). `buf breaking` reads no options, and naming any accepted RFC proves nothing about a class, so SL12 holds two kinds of release to a decision:
  - a **reclassification**: a field that moves to a lower-ranked class, or disappears;
  - a **level release**: a capture level that ships or redacts a class the base `capture.toml` withheld there, or ships one the base only redacted, or a class that loses `pseudonymous`.

  Each needs a record in `crates/grdr-schema/reclassifications.toml`, as `[[field]]` with `path`, `from`, `to` and `rfc`, or as `[[level]]` with `level`, `class`, `from`, `to` and `rfc`. A record counts only when `rfcs/<rfc>-*.md` on the pull request's base reads `Accepted` or `Implemented` and holds, in its "Surfaces changed" section and outside any fence, the decision line with the same values:

  `reclassify path="<field path>" from="<class>" to="<class>"`

  `release level="<capture level>" class="<class>" from="<withheld|redacted|pseudonymous>" to="<redacted|ships|plain>"`

  For the `pseudonymous` property, `level` is `all`. That is #1741 R2's base-read rule applied to the record, so a pull request cannot excuse its own change. The line sits in "Surfaces changed", not in "Decision", because RFC 0001's "Review binds the decision" lets the Decision section change after review and the reviewed text must hold the line. A change to the order or the set of classes, which SL13 ties to `options.proto`, is outside both forms: SL12 fails it, and it needs an RFC that amends this rule.

### 5. How `buf` gates it
- R18. `buf.yaml` at the repository root is `version: v2`, with lint `use: [STANDARD]`, `disallow_comment_ignores: true` and breaking `use: [WIRE_JSON]`, all at the top level. Its one module entry has `path: proto` and nothing else: `buf` replaces the top-level `lint` or `breaking` block in its entirety with a module's own block (buf.yaml v2 reference, https://buf.build/docs/configuration/v2/buf-yaml/, read 2026-11-21). It has no `except`, `ignore`, `ignore_only`, `ignore_unstable_packages` or `disable_builtin` key. `ignore_unstable_packages` alone would skip every `v1alpha1` package, and without `disallow_comment_ignores` a `// buf:lint:ignore` comment in any `.proto` file switches a rule off.
- R19. One gate item, worked by `lead-agent-kit` with the trust-core lane (AGENTS.md, gate configuration; D-63), lands:
  - the first `buf.yaml` and the fixtures under `schema/fixtures/buf/**`;
  - `crates/grdr-schema/capture.toml` as R13 gives it, and an empty `crates/grdr-schema/reclassifications.toml`, the exemption file of R17;
  - four `security/trust-core.paths` lines: `**/buf.yaml`, `schema/fixtures/buf/**`, `crates/grdr-schema/capture.toml` and `crates/grdr-schema/reclassifications.toml`. The glob form follows the deny configuration's lines, so a nested `buf.yaml` is trust core too.

  No `proto/` exists on `main`, so the item's own criteria are R23's fresh-copy runs, never a root `buf lint`. #353 waits on it and writes none of these files.
- R20. `buf` runs only as a plain command, in a session or in the `proto` job of `verify.yml` (#1842), at the version `[tool.buf]` of `supply-chain/build-tools.toml` pins (#1697). It runs offline: no registry dependency, no remote plugin and no login (#1697 condition 3). `cargo test --workspace --locked` never runs `buf` or `protoc` (W1).
- R21. Rust reads committed descriptor sets only (W2). `crates/grdr-proto/descriptors/proto.binpb` is the output of `buf build proto --as-file-descriptor-set --exclude-source-info -o crates/grdr-proto/descriptors/proto.binpb`. It keeps its imports, because a descriptor pool needs `google/protobuf/descriptor.proto` to read options by name, so the command never takes `--exclude-imports`. Every change to `proto/` regenerates it in the same pull request.
- R22. CI rebuilds every committed set and golden vector and fails on any byte difference (W3; #1842 R5 to R7).
- R23. The negative controls run against the configuration the `proto` module actually gets (W4). For each case under `schema/fixtures/buf/<case>/`, the job works in a fresh copy of the checkout and places the case's files under `proto/`.
  - A breaking case (`before/`, `after/`): `buf build -o <tmp>/before.binpb` on `before/`, then `buf breaking --against <tmp>/before.binpb` on `after/` must exit 100 and name what `expect.txt` holds. The cases are `renumbered_field` and `reused_enum_value`.
  - A lint case (`lint/`): `buf lint` must exit 100 and name the rule in `expect.txt`. The case is `comment_ignore`: an enum whose zero value lacks `_UNSPECIFIED`, under a `// buf:lint:ignore ENUM_ZERO_VALUE_SUFFIX` comment.
  - Every case's package is `<namespace>.fixture.v1alpha1` and imports nothing, so `ignore_unstable_packages`, a module-level block or allowed comment ignores turns a case to exit 0 and fails the job.
  - `stale_descriptor` (#353 R7) stays as #1842 R7 runs it.

### 6. Crates for SP-1 and for descriptor decoding
- R24. #360 adds exactly these as optional dependencies of `grdr-proto`, each at an `=` version. `sp1-buffa` and `sp1-prost` each enable only their own rows, and neither is a default feature.

| Crate | Version | Edge, feature | Features | Licence | crates.io owners | Published | crates.io checksum |
|---|---|---|---|---|---|---|---|
| `buffa` | 0.9.2 | normal, `sp1-buffa` | `default-features = false`, `std` | Apache-2.0 | `iainmcgin` | 2026-09-03 | `a92f2f5df67a9d5ccfc65237bfc954c56328aee40a04a9b92381ecba370be246` |
| `buffa-types` | 0.9.2 | normal, `sp1-buffa` | default | Apache-2.0 | `iainmcgin` | 2026-09-03 | `b15b05c8418f1e200e406e5b19df97400dffa833e2450e4392c506896cbc97ac` |
| `buffa-build` | 0.9.2 | build, `sp1-buffa` | default | Apache-2.0 | `iainmcgin` | 2026-09-03 | `eee6b6b4a8d23f1f98a043f188f4d9d2ef8bee43191f42e93ac577f3c3b0f334` |
| `prost` | 0.14.6 | normal, `sp1-prost` | default (`derive`, `std`) | Apache-2.0 | `danburkert`, `github:tokio-rs:prost-core` | 2026-11-12 | `3ef0b569d1d907ab3a28596aee62cf1f61dacb0529a4bedcd8e7460e2d5228b4` |
| `prost-types` | 0.14.6 | normal, `sp1-prost` | default | Apache-2.0 | as `prost` | 2026-11-12 | `f29a7c4c7a84cef41a53d338a2d10d4f1b043ea5c3dde26db22ee2c9c1b1c75b` |
| `prost-build` | 0.14.6 | build, `sp1-prost` | `default-features = false` | Apache-2.0 | as `prost` | 2026-11-12 | `b6e4d69d0fa3e7f6f9cf6b53a0e83e4fc99ba3586f65ce166cff30bd13bb4ad2` |

`buffa-types` and `prost-types` carry `google.protobuf.Timestamp`, which the SP-1 schema uses (#368 R1).

- R25. Build scripts generate only from committed sets and never run `protoc` or `buf` (W2). buffa uses `buffa_build::Config::descriptor_set`, never `use_buf`. prost uses `prost_build::Config::skip_protoc_run` with `file_descriptor_set_path`, or `compile_fds` over the set decoded with `prost-types`; the `prost` and `prost-types` build-dependencies that `compile_fds` needs are already in the closure.
- R26. `grdr-schema-lint` (#386) decodes with `buffa-descriptor` 0.9.2 (checksum `2b7dd79a6898e70dac8adae959c8ad2cae51ed96397935c91c996280cedcb55e`) and its feature `reflect`, whatever SP-1 decides. The lint builds a pool with `DescriptorPool::decode` over the committed set and reads each option through `DynamicMessage::from_options` and `DescriptorPool::extension_by_name` (R6). The crate enters `Cargo.lock` in #360 as a dependency of `buffa-codegen`, and `reflect` adds no package, so #386 adds its own entry and no third-party package (#360 R2). Moving the lint to another decoder, `prost-reflect` included, amends this RFC (R31). #386 therefore no longer needs #368.
- R27. Closure, resolved with cargo 1.99.1 and resolver 3 for every target, at `7d2de57`. `main` is now at `84187e7`, which changed only `supply-chain/admissions.toml`, so its lockfile still holds no third-party package.
  - `sp1-buffa` builds 32 packages, 13 of them on normal edges, the part a release would link if buffa wins.
  - `sp1-prost` builds 35 packages, 11 of them on normal edges.
  - The lint's decoder closure is 13 packages, all inside `sp1-buffa`'s.
  - `Cargo.lock` gains 63 packages: the 50 either feature builds, and 13 that Cargo locks as optional dependencies no enabled feature reaches (`aho-corasick`, `itoa`, `jiff`, `jiff-core`, `jiff-static`, `memchr`, `portable-atomic`, `portable-atomic-util`, `serde`, `serde_core`, `serde_derive`, `serde_json`, `zmij`).
  - 16 of the 63 are also rows of #1575's admission, which is on `main`. If one of its consumers locks them first, #360 adds 47.
- R28. ARCH-004 (`architecture.toml` `[arch004]`). `grdr-proto` is admitted as a decoder with `admits = []`. Neither feature's normal-edge closure holds a `content_parsers` entry:
  - `sp1-buffa` links `buffa`, `buffa-types`, `bytes`, `foldhash`, `hashbrown` 0.15.5 and `once_cell`, with the proc macros `rustversion` and `thiserror-impl` and their `proc-macro2`, `quote`, `syn` 3 and `unicode-ident`, and `thiserror`;
  - `sp1-prost` links `prost`, `prost-types` and `bytes`, with the proc macro `prost-derive` and its `anyhow`, `either`, `itertools`, `proc-macro2`, `quote`, `syn` 2 and `unicode-ident`.

  `regex` is reached only through `prost-build`'s build edge. `serde_json` is only an optional dependency of `buffa-types` behind its `json` feature, which no edge enables. A change that enabled it in a closure ARCH-004 checks would fail that check. #360 lists both normal-edge closures in its hand-off.
- R29. Licences. Every expression is satisfied by the permissive class of `supply-chain/licences.toml`: 36 `MIT OR Apache-2.0`, 10 `Apache-2.0`, 5 `Apache-2.0 OR MIT`, 5 `Unlicense OR MIT`, 2 `MIT`, 2 `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT`, 1 `Zlib`, 1 `(MIT OR Apache-2.0) AND Unicode-3.0`, and `r-efi`'s `MIT OR Apache-2.0 OR LGPL-2.1-or-later`, taken as MIT. No crate is in `supply-chain/do-not-read.toml` or `deny.toml`'s bans.
- R30. `hashbrown` stays at 0.17.1, #1575's row. A fresh resolve picks 0.17.2, published 2026-11-22T01:08:02Z, inside the three-day cooldown of design/35 section 2.6.
- R31. #360 records the admission in `supply-chain/admissions.toml` in #1575's format. That is the 63 closure rows with name, version, licence and checksum, the build scripts and proc macros, and one justification per direct crate, `buffa-descriptor` included. Each consumer entry of a feature-gated edge carries a `feature` key, which this row adds to the format. A resolve at implementation time that differs from R27 goes in #360's hand-off for `eval-licence` and `eval-security`. Only a different direct crate or version amends this RFC. The head of the row and the decoder's justification:

```toml
[[admission]]
issue = 360
crates = ["buffa", "buffa-types", "buffa-build", "prost", "prost-types", "prost-build", "buffa-descriptor"]
consumers = [
  { crate = "grdr-proto", kind = "normal", feature = "sp1-buffa", only = ["buffa", "buffa-types"], issue = 360 },
  { crate = "grdr-proto", kind = "build", feature = "sp1-buffa", only = ["buffa-build"], issue = 360 },
  { crate = "grdr-proto", kind = "normal", feature = "sp1-prost", only = ["prost", "prost-types"], issue = 360 },
  { crate = "grdr-proto", kind = "build", feature = "sp1-prost", only = ["prost-build"], issue = 360 },
  { crate = "grdr-schema-lint", kind = "normal", only = ["buffa-descriptor"], issue = 386 },
]
resolver = "cargo 1.99.1, resolver 3, the features of RFC 0006 R24 and R26"

[[admission.justification]]
crate = "buffa-descriptor"
purpose = "grdr-schema-lint decodes committed descriptor sets and reads custom options by full name (#386, RFC 0006 R6 and R26)"
why_not_std = "std decodes no protobuf; prost-types drops custom options with every unknown field; a decoder of our own would be a second protobuf decoder (P17)"
maintainers = ["iainmcgin"]
maintainer_risk = "one owner account, pre-1.0; it reaches grdr-schema-lint, a tool crate no shipped crate may depend on (ARCH-001), and the sp1-buffa build script of grdr-proto through buffa-codegen; it is linked into no shipped program, and the lint's tests read the repository's own set, so a decoding defect fails them"
unsafe = "none: no unsafe block, function or impl in src/ by a text search"
build_script = "none"
proc_macro = "none; it depends on the rustversion proc macro"
licence = "Apache-2.0"
registry_check = "present in the crates.io index at the recorded checksum, not yanked"
```

Maintainers and what they bring:
- **buffa.** All five buffa crates and `smoothutf8`, which the build graph pulls in, have one crates.io owner, `iainmcgin`; the repository is `anthropics/buffa`, pre-1.0. Unknown fields are kept by default, and `buffa-build`'s `preserve_unknown_fields` is on unless turned off. A text search of `src/` for `unsafe {`, `unsafe fn` and `unsafe impl` finds 28 lines in `buffa` and none in `buffa-types` or `buffa-descriptor`.
- **prost.** Owned by `danburkert` and the team `github:tokio-rs:prost-core`. Its README marks it passively maintained: no new features, security fixes released promptly. It drops unknown fields (tokio-rs/prost#2, open since 2017-06-26), which is why design/04 section 1 pairs it with "never re-encode". The same search finds 12 lines in `prost` and none in `prost-types`.
- **Build-time code.** The two features build these build scripts: `anyhow`, `getrandom`, `libc`, `prettyplease`, `proc-macro2`, `quote`, `rustix`, `rustversion` and `thiserror`. They build these proc macros: `prost-derive`, `rustversion` and `thiserror-impl`.

What was run, on a probe manifest with R24's dependencies and the repository's `deny.toml`:
- `cargo deny ... check licenses advisories bans sources` (cargo-deny 0.21.0; the pinned 0.22.0 is not installed here): exit 0. It printed two duplicate-version warnings, `hashbrown` 0.15 and 0.17 and `syn` 2 and 3. RustSec advisory-db was at commit `55e1c3dfbd834237a05bbbf7b50ba3b5be27b662`.
- OSV `querybatch` for all 63 packages: no id.
- The crates.io sparse index for all 63: every checksum matches, and none is yanked. Only `hashbrown` 0.17.2 falls inside the cooldown (R30).

### 7. New lint rules
Filed on acceptance as one `grdr-schema-lint` item, which blocks #18.
| Id | Fails when |
|---|---|
| SL10 | A descriptor-option extension is declared outside the options files of a `<namespace>.common.<version>` package, or an options file declares a message. Also when a file of the namespace other than the options files, enum-only files included, imports the options files of no such package, or of more than one version. An option from any other package does not count, so the field or value then fails SL01 or SL04 |
| SL11 | A package of the namespace has no `[[proto_package]]` row or more than one, or a `stable` row names a package whose last segment is unstable as buf's `PACKAGE_VERSION_SUFFIX` rule reads it (`alpha`, `beta`, `test`) |
| SL12 | `registry --check --against <base dir>`, where the base dir holds the base's `fields.json`, `capture.toml` and `rfcs/`. Ranks and levels are read from the base `capture.toml`, never the head's. It fails on a reclassification or a level release (R17) without a record that counts. It fails when the head `capture.toml` changes the order or set of classes. It fails when an option of the base registry is missing at head, or its number names another option; the registry gains an `options` section (name, number, extendee). With no base `fields.json` or no base `capture.toml` it prints which is missing and exits 0 |
| SL13 | `capture.toml`'s classes are not exactly the five names R11 derives from the `DataClass` and `ContentKind` wire names, or a level ships or redacts a class while withholding one of lower rank |

### 8. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| Every field has a class; `content_kind` exactly on content; no float marked `policy_readable`; closed enums; no `Any` or `Struct`; no field in 900 to 999 | SL01 to SL07 over the committed set | #386 |
| Zero values have no `wire_name`; every other value has a unique one | SL04, amended to exempt zero values | #386 |
| The options package comes from the import; options only in options files | SL10, and a fixture whose options package is `v1` beside one at `v1alpha1` | Filed on acceptance |
| `surfaces.toml` is the only source of the class | SL11, and the `[[proto_package]]` row | Filed on acceptance (two items) |
| No field moves to a lower class, no level releases a class, and no option number is reused, without a decision an RFC accepted on the base holds | SL12 in the CI lint steps, reading the base `capture.toml` and `rfcs/`. Seeded fixtures that must fail: a downgrade whose record cites an accepted RFC without the line; a downgrade whose RFC holds the line but reads `Draft`; `metadata` gaining `content.argument` with no record; `identifier` losing `pseudonymous`. One that must pass: a downgrade whose accepted RFC holds the line | Filed on acceptance; #1843 runs it |
| Class ranks and the capture matrix have one home | `capture.toml`; SL13; R11's testkit test | The gate item creates the file; filed on acceptance (lint item; testkit test) |
| `capture.toml` and the record file change only with the full lane | Two `security/trust-core.paths` lines | The gate item |
| Option numbers leave the in-house range together | SL09 | #398 |
| A renumbered field, a reused enum value or a comment ignore fails under the real module's configuration | R23's fixtures, run in a fresh copy | The gate item; #1842 R4 |
| Committed sets and vectors are fresh | Rebuild and byte compare, with a stale-set negative control | #1842 R5 to R7 |
| `buf.yaml` and its fixtures change only with the full lane | Its first text and two `security/trust-core.paths` lines in one gate item | Filed on acceptance (lead-agent-kit) |
| Every `proto/**` and `crates/grdr-schema/**` change names an accepted RFC | `rfc-required` (`grdr-schema` is a layer 0 public crate) | #1741 |
| `grdr-proto` has exactly R24's crates, licences in the class, no `protoc` | #360 AC-1 to AC-4, `cargo deny check`, the admission row | #360 |
| The losing codec's crates leave `Cargo.lock` | The item that makes SP-1's winner the crate's codec | #368's decision record files it |

### 9. Proposed changes to design documents and gate files
Each lands through an item whose write set names its file, filed on acceptance.
- **design/04 section 1.** The code block becomes `options.proto` as sections 2 and 3 give it. The naming rules gain: `proto3` for every `v1alpha1` file; descriptor-option extensions only in options files; the options package taken from the import (R6); zero values without a `wire_name`.
- **design/04 section 10.** The commitment classes are spelt `content.argument` and `content.body`, as `withheld` already does.
- **design/04 section 11.** The matrix points to `crates/grdr-schema/capture.toml` as its data, states R13's rank, and states that pseudonymity is a property of the `identifier` class at every level.
- **design/04 section 13.** The check table gains SL10 to SL13, and its wire-compatibility row names the reclassification and level-release check.
- **`surfaces.toml`.** `[[proto_package]]` with `package = "common.v1alpha1"` and `class = "experimental"`, created by whichever of this item and #1817 lands first.
- **`security/trust-core.paths`.** The four lines of R19, in the gate item.
- **`rfcs/0000-template.md`.** Its "Surfaces changed" note names R17's two decision lines, through #1819.

### 10. What each item changes
This RFC is normative. Each lead writes these changes back into its item before readying it.
- **#353.** The write set loses `buf.yaml` and `schema/fixtures/buf/**` to the gate item (R19), and the item is blocked by it. R2 and R3 become sections 1 to 3: one `options.proto` with two enums and five extensions, values named in full (`DATA_CLASS_IDENTIFIER = 1`), and `syntax = "proto3"`. R5's command keeps imports (R21). AC-1 stays `buf lint` at the root. AC-2, AC-3 and AC-5 move to the gate item. The pull request names `RFC: 0006`.
- **#360.** R1's list is R24's table, and R2's decoder is `buffa-descriptor` 0.9.2 (R26). It holds `hashbrown` at 0.17.1 (R30) and writes the admission row of R31. Its write set gains `supply-chain/admissions.toml`, which #1575 has created on `main`. The pull request names `RFC: 0006`.
- **#386.** R0's decoder is R26's. R1 takes the options package from the import (R6). A new failure mode: a file whose options package is missing from the set exits 2 with a code lead-core registers, never `Clean`. SL04 exempts zero values. The blocked-by link to #368 is removed.
- **#368.** No change. If prost wins, its decision record may propose an amendment of this RFC to move the lint to `prost-reflect` (R26).
- **#398.** Moves 50001 to 50004 and 50011 together (R5).
- **#1842.** R4 runs R23's cases in a fresh copy of the checkout under `proto/`, breaking and lint cases both, and AC-2 and AC-3 follow. It waits on the gate item.
- **#1843.** It gains the SL12 step. `git archive <base> crates/grdr-schema/registry/fields.json crates/grdr-schema/capture.toml rfcs` is unpacked into a temporary base dir, then `grdr-schema-lint registry --check --against` reads that dir.

Filed on acceptance, each citing this RFC and its decision record:
- the gate item of R19: the first `buf.yaml`, the four fixture cases, `capture.toml`, the empty `reclassifications.toml` and the four `security/trust-core.paths` lines (lead-agent-kit, trust core, blocked by #1697, blocking #353, #1842 and the lint item). Its criteria are R23's fresh-copy runs and a byte comparison of `capture.toml` with R13;
- the `[[proto_package]]` row of `surfaces.toml`, a protected trust-core change (chief-architect);
- `grdr-schema-lint` SL10 to SL13, the registry's `options` section and their fixtures (squad core, blocked by #386, the gate item and the row item, blocking #18);
- R11's test in `grdr-cabi-testkit` (squad core, blocked by #1778 and the lint item);
- the design/04 amendments of section 9 (chief-architect);
- a comment on #1819 asking for R17's two decision lines in the template.

### 11. Failure modes
| Failure | Outcome | Visible as |
|---|---|---|
| The pinned `buf` refuses an option used in its own file | #353 takes section 1's fallback | #353's hand-off |
| A file's options package is missing from the set, or its namespace differs from the manifest's | The lint exits 2 with its code; it never reports `Clean` | stderr and the CI step |
| A `data_class` number the enum does not declare | SL01 at that field | The lint's finding |
| A field moves to a lower class, or a level releases a class, without a record an RFC accepted on the base holds | SL12 fails, naming the field or level, both values and the missing decision line | The CI lint step |
| A configuration change makes a fixture case pass | R23's step fails, naming the case | Job log |
| A committed descriptor set or vector is stale | #1842 R5 or R6 fails, naming the file and the rebuild command | Job log |
| A codec's build script needs `protoc` or `buf` | #360 or #368 stops `blocked` (W2) | The hand-off |
| A resolve differs from R27 at implementation time | Listed for `eval-licence` and `eval-security` (R31) | #360's hand-off |

## Surfaces changed
- The new protobuf package `grdr.common.v1alpha1`, experimental: `options.proto` with the enums and extensions of sections 2 and 3. It defines no message, so no event changes.
- `buf.yaml`, and the committed descriptor set in `grdr-proto`, a public layer 0 crate whose class is experimental.
- `grdr-proto` gains optional dependencies behind two features that are not defaults. The default build and its closure are unchanged.
- As proposals: `crates/grdr-schema/capture.toml` and `reclassifications.toml`, R17's two decision lines, design/04 sections 1, 10, 11 and 13, a `surfaces.toml` row and four `security/trust-core.paths` lines. No spine text, pinned path, Cedar schema, licence policy or same-layer edge changes.
- This RFC reclassifies no field and releases no class, so it carries no decision line of R17.

Data classes (P8): this RFC adds the class mechanism and no data field. The lint and the build scripts read schema descriptors and data files only, which are `structural`, and log no event data. Assurance effect (P1): none. No action class changes `visibility`, `control`, `on_failure` or `tamper`.

## Alternatives
- **Two files, `options.proto` and `data_class.proto` (#353 as written).** An import cycle. Rejected for one file.
- **The options package as a literal in each reader (revision 1).** It breaks at the freeze and cannot serve N and N-1 at once. Rejected for R6.
- **The options package as a key of the `[[proto_package]]` row.** It works, but it is a second statement of what the import already says. Rejected for the import.
- **The stability class stated by the suffix and the row, held equal by SL12 (revision 1).** Two sources, and it forbids an experimental `v1`, which D-60 and ADR-0020 allow. Rejected for SL11's one-way rule.
- **A per-field or per-file `stability` option.** A second source beside `surfaces.toml` (ADR-0020, P17). Rejected.
- **`encoding` now (revision 1).** #353 and #360 have no bytes field, and a closed set fixed now would have to fit `Receipt.decision`, `native` and `Redaction.original` unseen. Deferred to #18's RFC (R14).
- **Reclassification held by reading the registry diff (revision 1).** Any accepted RFC satisfies `rfc-required`, so a downgrade passes every check. Rejected for SL12.
- **A record that cites any RFC number (revision 2).** The pull request that downgrades a field can write its own excuse, and nothing compared `capture.toml` with its base. Rejected for R17's decision lines read from the base, and for trust-core data files.
- **Matching a record to an RFC that merely mentions the path.** A mention is not a decision, and an RFC may discuss a field it rejects reclassifying. Rejected for an exact line.
- **Editions instead of `proto3`.** Both SP-1 candidates would have to generate them, and design/04's rules are written in `proto3` terms. Deferred to an RFC.
- **`prost-reflect` 0.16.5 as the lint's decoder** (MIT OR Apache-2.0, owner `andrewhickman`; `DescriptorPool::decode` keeps extension options; read 2026-11-21 on docs.rs). It works and adds one package. If buffa wins, design/04's first choice, it would keep the prost crates in the lockfile for a tool crate alone, while `buffa-descriptor` costs nothing. It is the decoder an amendment would name (R26).
- **`prost-types` alone.** It drops custom options with every other unknown field, so it cannot read `data_class`. Rejected.
- **Reading option numbers from raw `FieldOptions` bytes in the lint.** A protobuf decoder of our own in a gate, beside the codec (P17). Rejected.
- **Reading options through `grdr-proto`'s generated extension constants.** This ties the lint to the SP-1 outcome and to the numbers #398 moves. Rejected for R6.
- **A third SP-1 candidate.** `protobuf` 3.7.2 (MIT) has had no release since 2025-03-10, and the crate name now carries the official 4.x line, published as semver pre-releases such as `4.36.2-release` over `google-protobuf`; D-63 admits no pre-release. Design/04 names two candidates. Rejected.
- **`--exclude-imports` on the committed set.** A pool could not decode options without `descriptor.proto`. Rejected.
- **`prost-build` with default features.** `format` adds `prettyplease` 0.3 and `syn` 3 to a build script whose output nobody reads. Rejected.
- **Breaking fixtures checked with `--config buf.yaml` from their own directories (revision 1).** A module-level block in `buf.yaml` would apply to `proto` only, so those runs would not see it. Rejected for R23's fresh copy.

Sources, all read 2026-11-21: the crates.io API and sparse index for every crate named here; https://docs.rs/buffa-build/0.9.2/buffa_build/struct.Config.html; https://docs.rs/prost-build/0.14.6/prost_build/struct.Config.html; https://docs.rs/buffa/0.9.2/buffa/; https://docs.rs/prost-reflect/0.16.5/prost_reflect/struct.DescriptorPool.html; https://raw.githubusercontent.com/anthropics/buffa/main/README.md; https://raw.githubusercontent.com/tokio-rs/prost/master/README.md; https://api.github.com/repos/tokio-rs/prost/issues/2; https://buf.build/docs/configuration/v2/buf-yaml/; the published source of `buffa-descriptor` 0.9.2 (`src/pool.rs`, `src/reflect/dynamic.rs`).

## Drawbacks
- A spike locks 63 packages, which stay until the adopting item removes the losing codec's crates.
- buffa is pre-1.0, and one crates.io account owns six of the crates. The lint depends on it even if prost wins, unless an amendment moves it. If buffa wins, the gate's decoder and the codec generator share one crate, so a decoding defect is common to both. `buf` stays the independent producer of the sets.
- The option numbers stay in the in-house range until a third party grants a registered one (#398).
- A reclassification or a level release needs a decision line in an accepted RFC and a record beside it, and a retired option keeps its declaration.
- SL12 trusts the text of an accepted RFC on the base. An edit that adds a decision line to an RFC already accepted is out of route; review of `rfcs/**` holds it, not SL12.
- `buf.yaml`, its fixtures, `capture.toml` and the record file become trust core, so a change to any of them takes the full lane, and #353 waits on the gate item.
- The negative controls need a fresh copy of the checkout per case.

## Unresolved questions
1. **The registered extension range.** It waits on the protobuf global extension registry (#398, #17-E3). Nothing here depends on it.
2. **If prost wins SP-1.** An amendment of this RFC may move the lint to `prost-reflect` (R26).
3. **Map order.** `buffa`'s default map type is a hash map, so two encodings of one map need not match byte for byte. The schema allows one map, `native` (design/04 section 1 rule 4), and SP-1's schema has none. Integrity hashes the bytes as first encoded and nothing re-encodes before verifying (rule 8). #368's lead decides whether SP-1 adds a `native`-shaped case.
4. **Not checked here.**
   - `buf`: no pin exists yet (#1697), so `buf build` and `buf lint` have not run on section 1's layout or R23's cases. #353 AC-1 and the gate item's criteria are the first runs, with section 1's fallback.
   - The pinned cargo-deny 0.22.0; 0.21.0 ran.
   - Either codec's behaviour, which is SP-1's job.
   - `buffa-descriptor`'s reading of custom options was read in its published source, not run.

## Review
Round 3, the last, set by the session:
- `eval-architecture` on the delta from revision 2;
- `eval-security`;
- `eval-adversarial`, bounded to the seeds below;
- persona council seats 3 (`persona-soc-analyst`: wire names and class names in exports), 5 (`persona-oem-partner`: embedding, the stability class and the option numbers) and 6 (`persona-privacy-officer`: data classes, the capture matrix and ranks, `pseudonymous`, and reclassification).

Each puts one comment on #1848. Each comment opens with the blobs it read, one per line:
- `rfc-file=<blob of rfcs/0006-grdr-common-v1alpha1-options-and-sp1-crates.md at the commit reviewed>`;
- `base=a80859235e7a2a4444648d6fa8d389d78dde6be9`, the spine pin;
- `read=<path>@<blob>` for every other file it relied on.

A comment without these lines does not count. This RFC changes no pinned path, so its decision has no decision line (ADR-0036). The decided file may differ from the reviewed blob only where RFC 0001's "Review binds the decision" allows.

Round 1, on blob `b9f2b99aa9f46dffbeacd71f0a2c9deeddcccb22`:
- `eval-architecture` (Sonnet): fail, four majors and seven minors. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7072892832

Round 2, on blob `a916eaaa12f51817ce999fd5c6e17a017f340a2f`:
- `eval-architecture` (Opus, delta): fail, one major and four minors. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073095604

This text was written against these blobs, on `main` unless named:
- `docs/design/04-event-model-and-schemas.md`: `e77880a12d2f42e715836a6da9598b86f33b20b0`;
- `rfcs/0004-c-header-generation-and-drift-check.md`: `1f998f42db6c6ea6640c55df0a655e450759340f`;
- `supply-chain/licences.toml`: `65338a382a81c1ac500c533e22fa6ee22397928d`;
- `supply-chain/admissions.toml`: `1b25c164ade9d313e80bd6286444e289062d7f1f`;
- `deny.toml`: `2d0457ff71ea5c9bba91de0a580cd80f650d1479`;
- ADR-0007: `5b6cdffc1648817f3e48a821ef2b34383b24b8f1`;
- ADR-0020: `e0a2998b7baed6c2aa21629ce25d61f2fa12ad20`.

`eval-adversarial` checks these seeds and what they reveal. It does not run an open search. Each seed asks whether the text, as written, lets the case through:
- A1. A field whose `data_class` comes from a same-named extension in another package.
- A2. A `data_class` number the enum does not declare.
- A3. A field moved from `content.argument` to `structural` in a change that names some accepted RFC.
- A4. A oneof member, a nested message's field or a map field with no class.
- A5. A committed descriptor set that drops a field the tree has.
- A6. An option declared outside the options files under number 50001, or a retired option's number given to a new one.
- A7. A look-alike crate name, or a version outside R24, in `Cargo.lock`.
- A8. A build script that can reach `protoc` or `buf`.
- A9. A `stable` row over a `v1alpha1` package.
- A10. A module-level `lint` or `breaking` block, `ignore_unstable_packages`, or a `// buf:lint:ignore` comment.
- A11. A file that imports the options files of two versions, an enum-only file among them.
- A12. A level of `capture.toml` that gains a class, or `identifier` losing `pseudonymous`, in a change that names some accepted RFC.
- A13. A record whose cited RFC holds the decision line only at head, only in its Decision section, or with other values.

## Decision
Not decided.
