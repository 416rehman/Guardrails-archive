RFC: 0006
Title: `grdr.common.v1alpha1`: the option registry, the data-class enums, how `buf` gates them, and the crates SP-1 and descriptor decoding admit
Author: chief-architect
Harness: Claude Code
Model: claude-opus-5-5
State: Draft
Design issue: #1848
Spine: D-06, D-31, D-51, D-60, D-61, D-63, D-66, P8, P9, P14, P16, P17 (no spine text changes)
Surfaces: the new protobuf package `grdr.common.v1alpha1` (experimental): `proto/grdr/common/v1alpha1/options.proto` with the enums `DataClass` and `ContentKind` and five descriptor-option extensions; `buf.yaml`; the committed descriptor set `crates/grdr-proto/descriptors/proto.binpb` of the public crate `grdr-proto`; optional dependencies of `grdr-proto` behind the mutually exclusive features `sp1-buffa` and `sp1-prost`; the generated module `capture` of the public crate `grdr-schema`. As proposals: two data files of `grdr-schema` (`capture.toml`, `reclassifications.toml`), design/04 sections 1, 10, 11, 13 and 14, design/26 section 9, design/36 section 2, one `[[proto_package]]` row of `surfaces.toml`, and nine lines of `security/trust-core.paths`
Decision record: none yet

To comment, write on issue #1848 of this repository; you need no account on any service other than the code host. A security fix under embargo (D-62) may change a public surface without an RFC; open a retroactive RFC when the fix is disclosed.

This is revision 4. Round 3 passed `eval-architecture` with five minors, failed `eval-adversarial` and `eval-security`, and had support with changes from seats 3, 5 and 6. Nearly every failure was in one mechanism: a downgrade excused by a decision line parsed out of an RFC's text, checked by a lint built from the pull request's own code. The orchestrating session's ruling (https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073435306, rulings 1 to 11) binds this revision. Revision 4 removes that mechanism instead of patching it: a release now needs a once-only entry in a trust-core data file, and SL12 runs from the base's build and reads the head only as data. "Round 3 dispositions" under Review gives the place of every round 3 finding.

## Summary
The first `proto/` change is one file, `proto/grdr/common/v1alpha1/options.proto`. It holds two closed enums, `DataClass` and `ContentKind`, and the five options #353 needs: `data_class` on every field, `content_kind`, `policy_readable`, `sealable`, and `wire_name` on every enum value. Tools find the options package from each file's import and read options by full name, so neither the version nor the option numbers are literals. The capture matrix, the rank of each class and the default level are one trust-core data file with one loader. A change that lowers a field's class, takes it out of the pseudonymous class, removes it, opens a level, or changes a wire name needs a new entry in a second trust-core file, so its pull request takes the full lane and a council seat reviews it. SL12 enforces that from the base's build, counts each entry once, and fails when it cannot read its inputs. A release reaches a deployed device only through the D-31 widening step-up. The package is experimental, and `surfaces.toml` is the only source of that class. `buf` gates it under WI-0014's rules W1 to W5, with negative controls run against the real module. For SP-1 (#360), `grdr-proto` gains `buffa`, `buffa-types` and `buffa-build` 0.9.2 behind `sp1-buffa`, and `prost`, `prost-types` and `prost-build` 0.14.6 behind `sp1-prost`, never both at once. `grdr-schema-lint` decodes descriptors with `buffa-descriptor` 0.9.2.

## Motivation
- #353 cannot open its pull request without an RFC line: the package is a wire format (D-61; the #17-E1 decision on #17).
- #353 as written cannot build. Its `options.proto` needs `DataClass` as the type of `data_class`, and its `data_class.proto` needs `wire_name` on every value, so each file imports the other. Protobuf refuses import cycles.
- #360 may not admit a crate until a ruling names it (#17-E2), and #386 has no descriptor decoder until #360 lands one.
- Every later package imports this file. Its options are the mechanism P8 rests on: the capture filter, redaction, the field registry, the lake columns and every export mapping are generated from them (ADR-0007).

## Design

### 1. Package and file
- R1. One file, `proto/grdr/common/v1alpha1/options.proto`, package `grdr.common.v1alpha1`, `syntax = "proto3"`. It imports only `google/protobuf/descriptor.proto`, which `buf` carries locally, so there is no registry dependency (P16; #1697 condition 3). It is the options file: the one file of the namespace that declares a descriptor-option extension.
- R2. It holds the enums of section 3 and every extension of a `google.protobuf.*Options` message the namespace declares. It declares no message.
- R3. The package's first segment is `[identity] namespace` in `brand/brand.toml`, `grdr` today (D-66). That key is the wire namespace, class A of design/36 section 2. A rebuilt white-label manifest keeps the upstream value, and the brand manifest loader (LBC-3, #1856) refuses any other value until 04-4 (#396) moves the namespace for every distribution at once (ruling 10). Reading the namespace from the manifest keeps a literal `grdr` out of every tool; it does not make the wire rebrandable, which design/26 section 9 already lists as unchanged in a rebuild.
- R4. The other shared types design/04 section 1 lists for this package (`ActionClass`, `Mode`, `Redaction`, `Sealed` and the rest) go in their own files, one family per file (design/04 section 1 rule 6), each through its own RFC. Every file of the namespace except the options file imports `options.proto`.

One file is what removes the cycle. `buf` 1.67.0 builds and lints it, the `wire_name` used in the file that declares it included (eval-adversarial, round 3). #353 AC-1 confirms that with the pinned `buf` (#1697); if the pinned `buf` refuses it, #353 stops `blocked` and this RFC is amended. Revision 3's two-file fallback is gone, because it made the options file a set that SL10 could not hold to one (ruling 7).

### 2. The option registry
| Number | Extends | Option | Type | Required on |
|---|---|---|---|---|
| 50001 | `FieldOptions` | `data_class` | `DataClass` | every field of every message in the namespace, never `DATA_CLASS_UNSPECIFIED` |
| 50002 | `FieldOptions` | `content_kind` | `ContentKind` | exactly the fields whose class is `DATA_CLASS_CONTENT` |
| 50003 | `FieldOptions` | `policy_readable` | `bool` | optional; never on a `float` or `double` field |
| 50004 | `FieldOptions` | `sealable` | `bool` | optional; marks a field with a `Sealed` twin (D-35), whose number 04-19 assigns |
| 50011 | `EnumValueOptions` | `wire_name` | `string` | every enum value except the zero value, unique within its enum |

- R5. A number is allocated here only and never reused. A retired option stays declared with `[deprecated = true]`, so its number stays taken. `buf breaking` passes a deleted or renumbered extension and flags only a rename or retype at an existing number (eval-adversarial, round 3), so SL12 is the check: it fails a change that drops an option or gives its number to another name. The numbers stay in the in-house range 50000 to 99999 until #398 moves all five in one change to the range the protobuf global extension registry grants (external precondition, #17-E3; SL09 checks the range). Option numbers appear in descriptor sets, never in event bytes, so that move changes no event on the wire, no golden vector and no class digest.
- R6. Every tool and generator that reads an option (the lint, the registry writer, the filter and mapping generators) takes the options package of a file from that file's import: the package of the options file it imports, or the file's own package for the options file. It then resolves `<options package>.<option>` by full name, from a committed descriptor set, never by number and never through generated code. No reader holds a version literal. This is also the supported way for a third party to read our sets (Surfaces changed). When the freeze (04-29) adds a `v1` options file beside `v1alpha1`, its RFC amends SL10's one-options-file rule and no reader changes.
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
- R10. `options.proto` is the one source of the class names. Every tool under `crates/` that reads classes reads the committed descriptor set, `capture.toml` through its loader (R13), or a file generated from them: the field registry (`crates/grdr-schema/registry/fields.json`, #386 R4) and `grdr_schema::capture` (R13). The one other list is the `DataClass` enum of RFC 0004's `grdr-cabi-testkit`, which R11 holds to `grdr_schema::capture`.
- R11. The five commitment classes of design/04 section 10 are named from the wire names: `identifier`, `structural`, `derived`, `content.argument` and `content.body`. That spelling is the one `envelope.withheld`, the registry and every export use. SL13 also requires each wire name of `DataClass` and `ContentKind` to be its value's name without the enum's prefix, in lower case (`DATA_CLASS_IDENTIFIER` is `identifier`), so names cannot be permuted across values. RFC 0004's testkit describes C fields with five classes of its own (`Identifier`, `Structural`, `Derived`, `ContentArgument`, `ContentBody`). A test in the testkit, filed on acceptance, reads `grdr_schema::capture` and fails unless the testkit renders its five classes as exactly the five names there. That fixes a spelling RFC 0004 left open; no header exists yet, so no header text changes. This RFC does not change what RFC 0004 section 10 leaves to review: whether a C field's class is the right one.
- R12. A zero value carries no `wire_name` and is never rendered. A zero or undeclared value of a closed enum, read where a value is required, is a finding or an error, never a default. A `data_class` number the enum does not declare is SL01; `buf` refuses to build one (exit 100), so its fixture is a buf-built set that the test changes in memory, as #386 R7's drift test does. An export that meets an enum value it has no wire name for keeps the record, omits that field and marks the record, so one unknown value never loses the evidence around it; the mapper (04-21, #495) implements it (seat 3 F4).
- R13. `crates/grdr-schema/capture.toml` is design/04 section 11's matrix as data, with the rank of each class and the default level. It decides what leaves the device, so it is trust core (R19).
  - One loader reads it, in `grdr-schema-lint`. SL12, SL13 and `grdr-schema-lint capture` call it. `capture --out crates/grdr-schema/src/capture/generated.rs` writes typed constants with no parser behind them, and `capture --check` fails on any difference.
  - Every other reader uses those constants, `grdr_schema::capture`, and never parses the file (P17): the 04-16 filter (#117), the pack validator's class ceiling (#511), R11's testkit test, the rule linter and replay of design/13, the export mapper (04-21), the disclosure view and the tray (D-51), and the configuration schema's default upload level (design/29 section 8).
  - The loader refuses, with exit 2 and its code: an unknown key; a repeated `[[class]]` or `[[level]]` name; a name in `passes` or `redacted` that no `[[class]]` declares; a class in both lists of one level; a `pseudonymous` that is not a boolean; and a `default` that is missing or names no level (ruling 4).

```toml
# design/04 section 11 as data. Read only through grdr-schema-lint's loader (RFC 0006 R13).
# Rank is the order of [[class]] tables: later is more sensitive.
# pseudonymous declares that a value naming a human principal appears in this class only as a
# pseudonym (P8, D-51). Exports and the disclosure view read it; no check enforces it yet.
# At a level, a class in `passes` passes the filter whole, a class in `redacted` passes without
# the `original` of its redactions, and any other class is withheld.
default = "metadata"

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
passes = ["structural", "derived", "identifier"]
[[level]]
name = "redacted arguments"
passes = ["structural", "derived", "identifier"]
redacted = ["content.argument"]
[[level]]
name = "redacted content"
passes = ["structural", "derived", "identifier"]
redacted = ["content.argument", "content.body"]
[[level]]
name = "full content"
passes = ["structural", "derived", "identifier", "content.argument", "content.body"]
```

  The rank is the position of a `[[class]]` table, which orders the three metadata classes as well. `identifier` ranks above `derived` because an identifier joins records across events and back to a principal, device or artefact (D-51), while a derived value describes one event. `structural` ranks lowest because it describes shape only.

  `pseudonymous` sits on the class because D-51's two pseudonymisation layers apply wherever an identifier travels. It is a declaration, not an enforced property: no option yet marks which fields carry a human principal, so nothing can check that such a field is an `identifier` (seat 6 major 2). #18's RFC decides that marker (R14). The pseudonymiser of D-51 does not read the flag.

  `default` is the level every sink that leaves the device starts at. P8 and D-51 fix it at `metadata`, so SL13 requires it to pass and redact no content class, and SL12 fails any change of it. The flight recorder's own level stays on the device and remains a configuration default (design/04 section 11). Retention by class (D-51) is a configuration default design/20 applies, and the rule that a `secret` redaction keeps no `original` belongs to the capture step (design/16 section 11, 04-17). Neither is in the file: the matrix says only which classes pass.

  A level says what passes the filter for a sink at that level. The routes by which redacted arguments leave at the default level, an `EvidenceSpan` on a finding or a content grant (D-51), are not levels and are not in the file. Until the RFC that adds `EvidenceSpan` names them (R14), the matrix is incomplete for findings: at `metadata` the filter withholds every content leaf, `EvidenceSpan.text` included, and no generator infers a route from a leaf class (seat 3 F2).

  A rule that reads a class the organisation's level withholds reports "could not look" in the rule linter and in replay, never "no match" (P9; seat 3 F3). A mapping never assigns a class: a mapped value takes the class of the field it lands in, and a host value with no field goes to `native` as content (design/04 section 1 rule 4; seat 5 M2). Levels are ours alone: a partner or an organisation cannot define one (P8, D-51).
- R14. Left to the RFC of the first item that adds a message field (#18, 04-5):
  - an `encoding` option for bytes fields with its values (`Receipt.decision`, `native` and `Redaction.original` among the cases it is checked against);
  - the data file that names each digest's `<alg>` label;
  - the class of a field whose type is a namespace message;
  - a marker for fields that carry a human principal, an option or a data file, with a lint that it sits only on `identifier` fields (seat 6 major 2);
  - the routes of an `EvidenceSpan` and a content grant (seat 3 F2).

  The capture filter and the class-digest walk read leaf classes only (design/04 sections 10 and 11), so nothing in this RFC reads a namespace message-typed field's own class.
- R14a. Imported types (ruling 8). A namespace file may import a file outside the namespace only if it is `google/protobuf/descriptor.proto`, imported by the options file alone, or a `google/protobuf/` file whose messages have only number and `bool` leaves (`timestamp.proto` and `duration.proto` today, #368 R1). SL10 fails any other import. In the field registry each leaf of such a type takes the class of the namespace field that holds it, so a `Timestamp` on a content field is content. The 04-16 filter refuses a leaf the registry gives no class (`UnregisteredField`, #117 R8), so a classless leaf never ships. A partner's own package is outside the namespace: no lint reads it and the filter refuses its fields, so it reaches no sink except through a mapping into our fields (seat 5 M2).

### 4. Stability and releases
- R15. `grdr.common.v1alpha1` is experimental: nothing is stable before one external embed pilot completes (D-60). Its class lives in one `[[proto_package]]` row of `surfaces.toml` with the keys `package` and `class`, each a double-quoted value on its own line, the rule RFC 0004 section 2 sets for `[[c_header]]` rows (ADR-0020). `package` is the name below the namespace (`common.v1alpha1`).
- R16. `surfaces.toml` is the only source of a package's class. No option carries stability, per field or per file. The version suffix follows design/04's own naming: `v1alpha1` until the freeze, `v1` after it (04-29). A `v1` package may stay experimental, as D-60 and ADR-0020 allow. SL11 keeps the one rule that needs no second statement: a row whose class is `stable` names no package with an unstable suffix.
- R17. During `v1alpha1`, `buf breaking` uses `WIRE_JSON`, and the freeze switches it to `FILE` (design/04 section 13). Every change to `proto/**` names an accepted RFC (D-61; `rfc-required`, #1741 R1). Neither reads a field's options, and naming an accepted RFC says nothing about a class. So SL12 holds three kinds of change to an entry in `crates/grdr-schema/reclassifications.toml`:
  - a **field release**: a field moves to a lower-ranked class, moves out of a class the base declares `pseudonymous` into one it does not (`identifier` into either content class, though content ranks higher; ruling 6), or disappears;
  - a **level release**: a level passes or redacts a class that the base's form of that level withheld, or passes one the base only redacted; a level the base lacks releases each class it passes or redacts;
  - a **wire-name change**: an enum value of the namespace whose `wire_name` changes or that disappears, which breaks every saved hunt, rule and parser keyed on it (seat 3 F1).

  Ranks, levels and the `pseudonymous` declarations come from the base's `capture.toml`, never the head's. The forms:

```toml
[[field]]
message = "grdr.event.v1alpha1.Exec"
number = 3
from = "content.argument"
to = "structural"          # a class, or "removed"
rfc = "0099"
review = 7000000001

[[level]]
level = "redacted arguments"
class = "content.body"
from = "withheld"          # "withheld", "redacted", or "absent" for a level the base lacks
to = "redacted"            # "redacted" or "passes"
rfc = "0099"
review = 7000000002

[[wire_name]]
enum = "grdr.event.v1alpha1.ActionClass"
number = 2
from = "file.read"
to = "file.open"           # a wire name, or "removed"
rfc = "0099"
review = 7000000003
```

  `rfc` is the RFC that decided the change, four digits naming exactly one file `rfcs/<rfc>-*.md` on the base; SL12 reads the file's name, never its text. `review` is the id of the persona council comment that reviewed the change on that RFC's design issue: seat 6 for a release, seat 3 for a wire-name change. The loader of this file is in `grdr-schema-lint` too, and it refuses an unknown key, a missing key or a value outside its form, with exit 2.

  1. An entry counts only in the change that adds it. Every base entry must be in the head's file unchanged, in the same order within its kind, the file holds no two equal entries, and only the entries the base lacks count (ruling 1).
  2. Each change of the three kinds needs exactly one new entry with its kind, identity, `from` and `to`, and each new entry must match exactly one change the pull request makes. An entry that matches nothing fails.
  3. The file is trust core (R19), so a pull request that adds an entry takes the full lane (D-63), and the seat's comment that `review` names must exist before it lands. The lane checks that `rfc` decided the change and that `review` approves it. SL12 checks neither, because it reads no RFC text and no comment.

  A decision is therefore used once. Restoring a field's class needs no entry; lowering it again needs a new entry with its own RFC and review. These fail SL12 outright, and only an RFC that amends this rule changes them: a change to the set, order or `pseudonymous` declarations of the classes; a removed or reordered level; a change of `default`; a dropped option or an option number given to another name; and a field in a new version of a base package (R17a).
- R17a. Field identity (ruling 5). SL12 knows a field by its message's full name and its number, and an enum value by its enum's full name and its number. A field whose type changes (its scalar type, or the full name of its message or enum type) counts as removed and added, so retyping a field to a message with lower-classed leaves needs a removal entry. Renaming the field alone keeps its identity, so its class is still compared. Renaming its message or package, or moving it to another message, removes it and adds a new field. A new field's class is judged by review and by the privacy canary (04-18, #493), not by SL12. A field in a package that differs from a base package only in its last segment, a new version, fails until the RFC of the freeze (04-29) says how each such field names its predecessor and amends this rule.
- R17b. Deployed devices (ruling 9). A release never changes what a deployed device sends. The field registry and `grdr_schema::capture` carry each entry that opens a class (every entry except a removal and a wire-name change) with the base treatment it replaces; both writers read the record file for it. The 04-16 filter (#117) applies that base treatment until the organisation confirms the entry's RFC. Confirming is the capture-level widening step-up of D-31 at that class's minimum grade, with the approvers and notice of design/29 section 8, and in hosted and provider deployments it needs the organisation's own signature (D-31). Every such entry appears in the monitoring catalogue's dated diff (design/29 section 6), and the pull request that adds it carries a release note with `category = "security"` and an `action_required` naming the step-up (design/34 section 14). A wire-name change carries `category = "breaking"`. `eval-docs` and the trust-core lane check the release note on that pull request.

### 5. How `buf` gates it
- R18. `buf.yaml` at the repository root is `version: v2`, with lint `use: [STANDARD]`, `disallow_comment_ignores: true` and breaking `use: [WIRE_JSON]`, all at the top level. Its one module entry has `path: proto` and nothing else: `buf` replaces the top-level `lint` or `breaking` block in its entirety with a module's own block (buf.yaml v2 reference, https://buf.build/docs/configuration/v2/buf-yaml/, read 2026-11-21). It has no `except`, `ignore`, `ignore_only`, `ignore_unstable_packages` or `disable_builtin` key. `ignore_unstable_packages` alone would skip every `v1alpha1` package, and without `disallow_comment_ignores` a `// buf:lint:ignore` comment in any `.proto` file switches a rule off. R23's cases catch a module-level block, `ignore_unstable_packages` and comment ignores. An `except` of some other rule, or a module-level `use` that keeps the tested rules, leaves the cases at exit 100; only the trust-core lane on `buf.yaml` and the key list above hold those (eval-adversarial m5).
- R19. The gate item, worked by `lead-agent-kit` with the trust-core lane (AGENTS.md, gate configuration; D-63), lands:
  - the first `buf.yaml` and the fixtures under `schema/fixtures/buf/**`;
  - nine `security/trust-core.paths` lines: `**/buf.yaml`, `schema/fixtures/buf/**`, `crates/grdr-schema/capture.toml`, `crates/grdr-schema/reclassifications.toml`, `crates/grdr-schema-lint/**` (the lint, its tests and fixtures), and the 04-16 filter with its tests as #117 places them, `crates/grdr-model/src/capture.rs`, `crates/grdr-model/src/capture/**`, `crates/grdr-model/tests/capture_filter.rs` and `crates/grdr-model/tests/vectors/capture/**`. A line may name a path that does not exist yet, as the list already does. The `buf.yaml` glob follows the deny configuration's lines, so a nested `buf.yaml` is trust core too.

  No `proto/` exists on `main`, so the item's own criteria are R23's fresh-copy runs, never a root `buf lint`. It lands before #353, #386 and the lint item, so the lint crate and the filter are trust core from their first commit (ruling 2). The generated files, `fields.json` and `grdr_schema::capture`, need no line: a hand edit fails their drift check in the `proto` job, and changing that check means changing the lint or `.github/**`, both trust core.
- R19a. The capture item, a protected change worked by `lead-agent-kit` with the trust-core lane, lands `crates/grdr-schema/capture.toml` as R13 gives it and a `crates/grdr-schema/reclassifications.toml` that holds only a comment. It comes after the lint item, so the loader and SL13 exist when the file does. Its criteria are a byte comparison of `capture.toml` with R13, `capture --check`, and the one use of `--bootstrap` (ruling 3): `compare --base <its base> --head <its head> --bootstrap` exits 0 and prints that no base comparison of the matrix or the entries ran, and the same command without the flag exits 2. `--bootstrap` is honoured only on a base that holds neither data file. There it requires the head's descriptor set to equal the base's byte for byte, the head's `capture.toml` to load and pass SL13, and the head's record file to hold no entry. On any other base the flag is itself an error, exit 2. Every base after the capture item holds both files, so no later run can use it, and no workflow passes it.
- R20. `buf` runs only as a plain command, in a session or in the `proto` job of `verify.yml` (#1842), at the version `[tool.buf]` of `supply-chain/build-tools.toml` pins (#1697). It runs offline: no registry dependency, no remote plugin and no login (#1697 condition 3). `cargo test --workspace --locked` never runs `buf` or `protoc` (W1).
- R21. Rust reads committed descriptor sets only (W2). `crates/grdr-proto/descriptors/proto.binpb` is the output of `buf build proto --as-file-descriptor-set --exclude-source-info -o crates/grdr-proto/descriptors/proto.binpb`. It keeps its imports, because a descriptor pool needs `google/protobuf/descriptor.proto` to read options by name, so the command never takes `--exclude-imports`. Every change to `proto/` regenerates it in the same pull request.
- R22. CI rebuilds every committed set and golden vector and fails on any byte difference (W3; #1842 R5 to R7).
- R23. The negative controls run against the configuration the `proto` module actually gets (W4). For each case under `schema/fixtures/buf/<case>/`, the job works in a fresh copy of the checkout, with the root `buf.yaml`, and always names `proto` as the input.
  - A breaking case (`before/`, `after/`): place `before/` under `proto/`, run `buf build proto -o <tmp>/before.binpb`, replace it with `after/`, then `buf breaking proto --against <tmp>/before.binpb` must exit 100 and name what `expect.txt` holds. The cases are `renumbered_field` and `reused_enum_value`.
  - A lint case (`lint/`): place it under `proto/`, then `buf lint proto` must exit 100 and name the rule in `expect.txt`. The case is `comment_ignore`: an enum whose zero value lacks `_UNSPECIFIED`, under a `// buf:lint:ignore ENUM_ZERO_VALUE_SUFFIX` comment.
  - Every case's package is `<namespace>.fixture.v1alpha1` and imports nothing, so `ignore_unstable_packages`, a module-level block or allowed comment ignores turns a case to exit 0 and fails the job.
  - `stale_descriptor` (#353 R7) stays as #1842 R7 runs it.

### 6. Crates for SP-1 and for descriptor decoding
- R24. #360 adds exactly these as optional dependencies of `grdr-proto`, each at an `=` version. `sp1-buffa` and `sp1-prost` each enable only their own rows, and neither is a default feature. They are mutually exclusive: `grdr-proto` fails to compile, through `compile_error!`, when both are on, so feature unification in an embedder's workspace cannot link two codecs (seat 5 M3). #368 therefore compares each codec with the golden vectors in a build of its own. `cargo deny check` still resolves both closures, because `deny.toml` sets `all-features = true` and resolving compiles nothing. Both features are experimental, the generated types behind them are outside any stable part of `grdr-proto`, and the losing feature leaves with the item that adopts SP-1's winner.

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

  `regex` is reached only through `prost-build`'s build edge. `serde_json` is only an optional dependency of `buffa-types` behind its `json` feature, which no edge enables. A change to `crates/grdr-proto/Cargo.toml` that enabled it in a closure ARCH-004 checks would fail that check; it would not change `Cargo.lock`, because the package is already locked. #360 lists both normal-edge closures in its hand-off.
- R29. Licences. Every expression is satisfied by the permissive class of `supply-chain/licences.toml`: 36 `MIT OR Apache-2.0`, 10 `Apache-2.0`, 5 `Apache-2.0 OR MIT`, 5 `Unlicense OR MIT`, 2 `MIT`, 2 `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT`, 1 `Zlib`, 1 `(MIT OR Apache-2.0) AND Unicode-3.0`, and `r-efi`'s `MIT OR Apache-2.0 OR LGPL-2.1-or-later`, which we take under MIT. No crate is in `supply-chain/do-not-read.toml` or `deny.toml`'s bans. The licence-closure report of the `embedded` profile (design/26 section 12) lists each feature's normal-edge closure of R27 on its own and repeats the `r-efi` election (seat 5 L1).
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
unsafe = "no forbid(unsafe_code) attribute; a text search of src/ for unsafe blocks, functions and impls found none, which misses macro output, and decoding goes through buffa"
build_script = "none"
proc_macro = "none; it depends on the rustversion proc macro"
licence = "Apache-2.0"
registry_check = "present in the crates.io index at the recorded checksum, not yanked"
```

Maintainers and what they bring:
- **buffa.** All five buffa crates and `smoothutf8`, which the build graph pulls in, have one crates.io owner, `iainmcgin`; the repository is `anthropics/buffa`, pre-1.0. Unknown fields are kept by default, and `buffa-build`'s `preserve_unknown_fields` is on unless turned off. A text search of `src/` for `unsafe {`, `unsafe fn` and `unsafe impl` finds 28 lines in `buffa` and none in `buffa-types` or `buffa-descriptor`. The search misses `unsafe{` and macro output, and no crate of the three sets `forbid(unsafe_code)`.
- **prost.** Owned by `danburkert` and the team `github:tokio-rs:prost-core`. Its README marks it passively maintained: no new features, security fixes released promptly. It drops unknown fields (tokio-rs/prost#2, open since 2017-06-26), which is why design/04 section 1 pairs it with "never re-encode". The same search finds 12 lines in `prost` and none in `prost-types`.
- **Build-time code.** The two features build these build scripts: `anyhow`, `getrandom`, `libc`, `prettyplease`, `proc-macro2`, `quote`, `rustix`, `rustversion` and `thiserror`. They build these proc macros: `prost-derive`, `rustversion` and `thiserror-impl`.

What was run, on a probe manifest with R24's dependencies and the repository's `deny.toml`:
- `cargo deny ... check licenses advisories bans sources` (cargo-deny 0.21.0; the pinned 0.22.0 is not installed here): exit 0. It printed two duplicate-version warnings, `hashbrown` 0.15 and 0.17 and `syn` 2 and 3. RustSec advisory-db was at commit `55e1c3dfbd834237a05bbbf7b50ba3b5be27b662`.
- OSV `querybatch` for all 63 packages: no id.
- The crates.io sparse index for all 63: every checksum matches, and none is yanked. Only `hashbrown` 0.17.2 falls inside the cooldown (R30).

### 7. New lint rules
Filed on acceptance as one `grdr-schema-lint` item, which blocks the capture item and #18.
| Id | Fails when |
|---|---|
| SL10 | Two files of the set declare a descriptor-option extension, at the top level or inside a message, or none does, or the one that does is outside a `<namespace>.common.<version>` package. The options file declares a message, or imports anything but `google/protobuf/descriptor.proto`. A namespace file other than the options file lacks a direct import of it in `FileDescriptorProto.dependency`, imports it as public or weak, or imports `google/protobuf/descriptor.proto`. A namespace file imports a file outside the namespace that R14a does not allow. An option from any other package does not count, so the field or value then fails SL01 or SL04 |
| SL11 | A package of the namespace has no `[[proto_package]]` row or more than one, or a `stable` row names a package whose last segment is unstable as buf's `PACKAGE_VERSION_SUFFIX` rule reads it (`alpha`, `beta`, `test`) |
| SL12 | `compare` finds a change R17 lists without a new entry that matches it, an entry R17's rules refuse, or one of R17's outright failures (exit 1). It exits 2 with its code, and never passes, when any input is missing or unreadable, base or head (ruling 3, P9); R19a's `--bootstrap` is the one exception |
| SL13 | `capture.toml`'s classes are not exactly the five names R11 derives. A `DataClass` or `ContentKind` enum is defined anywhere but the options file (ruling 7), or a wire name of either is not its value's name without the enum's prefix, in lower case. A level passes or redacts a class while withholding one of lower rank, or opens some class less far than the level before it. The default level passes or redacts a content class (P8, D-51) |

`grdr-schema-lint compare --base <dir> --head <dir>` is SL12. Each directory holds `crates/grdr-proto/descriptors/proto.binpb`, `crates/grdr-schema/capture.toml` and `crates/grdr-schema/reclassifications.toml` at those paths, and the base also holds `rfcs/`. `compare` decodes both descriptor sets itself and loads both data files with their loaders, so SL13 and every loader refusal apply to the head's files too. It reads no `fields.json`: generated files are checked against their sources in the `proto` job.

How it runs (ruling 2, as `rfc-required` runs under RFC 0001 and #1741):
- On a pull request, a job on `pull_request_target`, whose workflow file is the base's, checks out the base, builds `grdr-schema-lint` there, writes the head's three files into a temporary directory with `git show <head>:<path>`, and runs `compare` with the checkout as the base. It never builds or runs the head's code or scripts. It has read-only permissions and no secrets, and it records the zizmor exception that trigger needs, as #1741 does. The lint is `#![forbid(unsafe_code)]` (#386 R0), and a decoder fault on hostile head data exits 2.
- On every push to `main`, the same job runs with the parent as the base, built from the parent. A failure fails that run and opens an issue for the chief architect naming the commit and the finding; the revert is its own issue, as RFC 0001's detector does (security m5). This covers a pull request whose checks read an older base than the one it merged onto.
- The head-side steps stay in the `proto` job, built from the head: `check` (SL01 to SL07, SL10, SL11), `registry --check`, `capture --check` (with SL13) and `namespace --check`. They check that generated files match their sources, and their code is trust core (R19).
- Moving a file `compare` reads takes two changes: one teaches the lint the new path, then the move lands, because the base's build looks only where it knows to look.

### 8. Mechanisms
| Decision | Mechanism | Built by |
|---|---|---|
| Every field has a class; `content_kind` exactly on content; no float marked `policy_readable`; closed enums; no `Any` or `Struct`; no field in 900 to 999 | SL01 to SL07 over the committed set, walking nested messages and oneof members | #386 |
| Zero values have no `wire_name`; every other value has a unique one | SL04, amended to exempt zero values | #386 |
| One options file; the options package comes from the import; only allowed foreign imports | SL10 | Filed on acceptance (lint item) |
| `surfaces.toml` is the only source of the class | SL11, and the `[[proto_package]]` row | Filed on acceptance (two items) |
| A field release, a level release or a wire-name change needs one new entry, used once; the classes, levels, default and option numbers do not move | SL12 (`compare`) from the base's build, on pull requests and on push | Filed on acceptance (lint item); #1843 runs it |
| `capture.toml` has one loader and one shape; class names follow the wire names; levels are monotonic; the default passes no content | The loader, SL13 and the generated `grdr_schema::capture` | Filed on acceptance (lint item); the capture item creates the files |
| A gate never passes when it could not look | Exit 2 on a missing or unreadable input; `--bootstrap` honoured on one base only | Lint item; the capture item uses it once |
| A release reaches a deployed device only after the D-31 step-up | The 04-16 filter holds each entry's base treatment until the organisation confirms its RFC | #117, with the confirmation key of design/29 section 8 |
| A classless leaf never ships; imported leaves take their holder's class | R14a in the registry writer and SL10; `UnregisteredField` in the filter | #386 (registry), lint item (SL10), #117 |
| The data files, the lint and the filter change only with the full lane | Nine `security/trust-core.paths` lines | The gate item |
| Option numbers leave the in-house range together | SL09 | #398 |
| A renumbered field, a reused enum value or a comment ignore fails under the real module's configuration | R23's fixtures, run in a fresh copy | The gate item; #1842 R4 |
| Committed sets and vectors are fresh | Rebuild and byte compare, with a stale-set negative control | #1842 R5 to R7 |
| The lint's decoder agrees with `buf`'s | The registry built from `buf`'s JSON rendering of the set equals the committed one (security m6) | Filed on acceptance (lint item); #1843 runs it |
| Every `proto/**` and `crates/grdr-schema/**` change names an accepted RFC | `rfc-required` (`grdr-schema` is a layer 0 public crate) | #1741 |
| `grdr-proto` has exactly R24's crates, licences in the class, no `protoc`, one codec at a time | #360's criteria (section 10), `cargo deny check`, the admission row | #360 |
| No build reaches a schema compiler; `Cargo.lock` matches the admissions | The `rust` job runs with `PROTOC` unset and no `protoc` or `buf` on `PATH`; a step compares `Cargo.lock` with `supply-chain/admissions.toml` (eval-adversarial m7) | Filed on acceptance (lead-agent-kit) |
| The losing codec's crates leave `Cargo.lock` | The item that makes SP-1's winner the crate's codec | #368's decision record files it |

#### Seeded fixtures
The lint item adds these cases, each wrong by construction, and its tests run them. They cover every scenario of round 3: the security model (S0 to S9), the adversarial model (A3, A12, A13, N1 to N4, R1 to R3, T1, D1 to D3, M1, M2) and the seat findings. Names follow #1854 where it has one. "Passes" means exit 0.

| Fixture | Round 3 scenario | Expect |
|---|---|---|
| `sl12::downgrade_without_entry` | S0, A3 | exit 1 |
| `sl12::downgrade_with_new_entry` | the positive control | passes |
| `sl12::record_reuse`: the base holds the entry, the field is back at its old class, the head lowers it again | S1; R1 to R3; adversarial M1; security M2; architecture m3 | exit 1 |
| `sl12::duplicate_entry`: the head adds an entry equal to a base entry | the same | exit 1 |
| `sl12::entry_edited` and `sl12::entry_removed` | the same | exit 1 |
| `sl12::unmatched_entry`: a new entry for a change the head does not make | security M2 | exit 1 |
| `sl12::entry_rfc_missing` and `sl12::entry_rfc_two_files`: `rfc` names no base file, or two | adversarial M2; security m2 | exit 1 |
| `sl12::rfc_text_not_read`: an entry whose RFC on the base reads `Draft`, holds a line only under a `### Surfaces changed` in Decision, in an HTML comment, in a fence, in a quote, or nothing at all | S7, S8, N1 to N4, T1, A13; security M1 and m1; seat 6 1b | passes with the new entry, exit 1 without it, whatever the text |
| `sl12::identifier_to_content` | S2; security M4 | exit 1 |
| `sl12::removed_field`: with and without a `to = "removed"` entry | M2; seat 6 minor 5 | passes; exit 1 |
| `sl12::rename_is_removal`: `argv` removed and `argv_v2` added, and a renamed message | M2; adversarial m2 | exit 1 without a removal entry |
| `sl12::retype_is_removal`: a field retyped from `Detail` to `Detail2` | M1; adversarial m2 | exit 1 without a removal entry |
| `sl12::version_without_predecessor`: `v1` beside `v1alpha1` | S6; security M5 | exit 1 |
| `sl12::level_release`: `redacted arguments` gains `content.body` | A12 | exit 1 without an entry, passes with one |
| `sl12::new_level`: a level the base lacks passes every class | S4; seat 6 1c | exit 1 without five entries, passes with them |
| `sl12::level_removed`, `sl12::level_reordered`, `sl12::default_changed`, `sl12::class_order_changed`, `sl12::pseudonymous_lost` | A12; security M8 | exit 1, entries or not |
| `sl12::wire_name_changed` | seat 3 F1 | exit 1 without an entry, passes with one |
| `sl12::option_dropped`, `sl12::option_renumbered` | A6 | exit 1 |
| `sl12::missing_base`: no base descriptor set, `capture.toml` or record file, one at a time | S5; security B1; adversarial m1; seat 6 1a | exit 2 |
| `sl12::missing_head`: no head `capture.toml`, and the descriptor set moved | architecture m4 | exit 2 |
| `sl12::bootstrap`: on a base with neither data file, then on a base with one | ruling 3 | passes; exit 2 |
| `capture_toml::repeated_name`: a second `[[level]] name = "metadata"`, and a second `[[class]]` | S3; D1; adversarial M4 | exit 2 |
| `capture_toml::undeclared_class`: `metadata` passes `"content"` | D2 | exit 2 |
| `capture_toml::unknown_key` | D3 | exit 2 |
| `capture_toml::class_in_both_lists` | adversarial M4 | exit 2 |
| `capture_toml::default_level`: `default` missing, or naming no level | ruling 4 | exit 2 |
| `sl13::default_passes_content`: `metadata` passes `content.argument` | A12 (revision 3's seeded case); seat 6 minor 4 | exit 1 |
| `sl13::permuted_wire_names` | S9; security M6 | exit 1 |
| `sl13::second_data_class`: a `DataClass` in another file | security M6; ruling 7 | exit 1 |
| `sl10::second_options_package`: `common/v9/options.proto` | security M6 | exit 1 |
| `sl10::import_public` and `sl10::nested_extension` | adversarial m6; security m4 | exit 1 |
| `sl10::foreign_message_with_text`: `x.v1.Blob` with a `string` and a map | security M7 | exit 1 |
| `registry::imported_type_classes`: a `Timestamp` on a structural and on a content field | ruling 8 | the leaves take each holder's class |
| `filter::classless_leaf` (#117) | security M7 | `UnregisteredField`, no copy |
| SL01 oneof, nested message and map cases, and an undeclared number set in memory (#386) | adversarial m3 and m4 | exit 1 each |

One property no fixture of the lint can show is that the head's code never runs (security M3). #1843's criteria hold it: on a local branch that edits `crates/grdr-schema-lint/src/` to skip SL12 and lowers a field, the job's commands, run as written from the base, exit 1.

### 9. Proposed changes to design documents and gate files
Each lands through an item whose write set names its file, filed on acceptance.
- **design/04 section 1.** The code block becomes `options.proto` as sections 2 and 3 give it. The naming rules gain: `proto3` for every `v1alpha1` file; descriptor-option extensions only in the options file; the options package taken from the import (R6); zero values without a `wire_name`; foreign imports only as R14a allows.
- **design/04 section 10.** The commitment classes are spelt `content.argument` and `content.body`, as `withheld` already does.
- **design/04 section 11.** The matrix points to `crates/grdr-schema/capture.toml` as its data and states R13's rank and default level, that `pseudonymous` is a declaration of the `identifier` class at every level, that levels do not carry the evidence-span and content-grant routes, and R17b's rule for deployed devices.
- **design/04 section 13.** The check table gains SL10 to SL13, and its wire-compatibility row names the release and wire-name check of R17.
- **design/04 section 14.** A mapping never assigns a class (R13).
- **design/26 section 9 and design/36 section 2.** `[identity] namespace` is the wire namespace, class A, which a rebuilt manifest keeps (R3).
- **`surfaces.toml`.** `[[proto_package]]` with `package = "common.v1alpha1"` and `class = "experimental"`, created by whichever of this item and #1817 lands first.
- **`security/trust-core.paths`.** The nine lines of R19, in the gate item.

### 10. What each item changes
This RFC is normative. Each lead writes these changes back into its item before readying it.
- **#353.** The write set loses `buf.yaml` and `schema/fixtures/buf/**` to the gate item (R19), and the item is blocked by it. R2 and R3 become sections 1 to 3: one `options.proto` with two enums and five extensions, values named in full (`DATA_CLASS_IDENTIFIER = 1`), `syntax = "proto3"`, and no fallback file. R5's command keeps imports (R21). AC-1 stays `buf lint` at the root. AC-2, AC-3 and AC-5 move to the gate item. The pull request names `RFC: 0006`.
- **#360.** R1's list is R24's table, and R2's decoder is `buffa-descriptor` 0.9.2 (R26). It holds `hashbrown` at 0.17.1 (R30) and writes the admission row of R31. Its write set gains `supply-chain/admissions.toml`, which #1575 has created on `main`. AC-4 builds each feature on its own (`--features sp1-buffa`, then `--features sp1-prost`) with no `protoc` and no `buf` on `PATH`. New criteria: `cargo check --locked -p grdr-proto --features sp1-buffa,sp1-prost` fails with the `compile_error!` message; `cargo check --locked --target wasm32-unknown-unknown -p grdr-proto --features <feature>` exits 0 for each feature on its own (seat 5 M3); and every package `Cargo.lock` gains is a row of the admission with the same version and checksum. The pull request names `RFC: 0006`.
- **#386.** R0's decoder is R26's. R1 takes the options package from the import (R6). SL01 walks every message, nested ones included, and every field, oneof members included; a map field's entry message is skipped, and its key and value take the map field's class. Fixtures for oneof, nested and map cases, and the undeclared-number case set in memory (R12). The registry gives each leaf of an imported type its holder's class (R14a) and records each field's message full name and number. A new failure mode: a file whose options package is missing from the set exits 2 with a code lead-core registers, never `Clean`. SL04 exempts zero values. The blocked-by link to #368 is removed. "Trust core: no" becomes yes: the crate is on the gate item's list, so the item takes the full lane.
- **#368.** It compares each codec with the golden vectors in a build of its own (R24). If prost wins, its decision record may propose an amendment of this RFC to move the lint to `prost-reflect` (R26).
- **#398.** Moves 50001 to 50004 and 50011 together (R5).
- **#1842.** R4 runs R23's cases in a fresh copy of the checkout with `proto` as the input, breaking and lint cases both, and AC-2 and AC-3 follow. It waits on the gate item.
- **#1843.** It runs SL12 as section 7 says: a `pull_request_target` job from the base's build and a run on every push to `main`, with the issue on failure. The `proto` job gains `capture --check` and a step that renders the set with `buf build proto --as-file-descriptor-set --exclude-source-info -o "$RUNNER_TEMP/proto.json"` and checks that the registry built from that JSON equals the committed one; the lint item adds that reading of `buf`'s JSON, through `serde_json`, which #1575's closure already locks, with its own consumer entry. It is blocked by the capture item, and it blocks #18 and every later change to `proto/**`, so no class changes before SL12 runs (eval-adversarial m9). Its criteria include section 8's head-code case.
- **#117.** The filter reads `grdr_schema::capture`, holds each entry's base treatment until the organisation confirms its RFC (R17b), and refuses a classless leaf, imported leaves included (R14a). Its paths become trust core.
- **#1856.** The loader refuses a manifest whose `[identity] namespace` differs from the upstream value (R3).
- **#1854.** Its rows follow the accepted text. SR-53's base inputs are the descriptor set, `capture.toml` and `reclassifications.toml`, not the field registry. SR-54's loader is in `grdr-schema-lint`, with the generated constants in `grdr-schema`, and it refuses a default level that passes or redacts a content class rather than one named other than `metadata`. `sl13::duplicate_level` is `capture_toml::repeated_name`.
- **#493.** The privacy canary is the check for a new field's class (R17a). Running it on every pull request that touches `proto/**` once it exists is that item's lead's call (security M5).

Filed on acceptance, each citing this RFC and its decision record:
- the gate item of R19: the first `buf.yaml`, the four fixture cases and the nine `security/trust-core.paths` lines (lead-agent-kit, trust core, blocked by #1697, blocking #353, #386, #1842, the lint item and the capture item). Its criteria are R23's fresh-copy runs;
- the capture item of R19a (lead-agent-kit, trust core, blocked by the lint item, blocking #1843, #117 and the testkit test);
- the `[[proto_package]]` row of `surfaces.toml`, a protected trust-core change (chief-architect);
- `grdr-schema-lint` SL10 to SL13, the two loaders, `capture`, `compare`, the JSON reading and the fixtures of section 8 (squad core, trust core, blocked by #386, the gate item and the row item, blocking the capture item and #18);
- R11's test in `grdr-cabi-testkit` (squad core, blocked by #1778 and the capture item);
- the `rust` job and lockfile checks of section 8 (lead-agent-kit, trust core);
- the "could not look" rule of R13 for design/13's rule linter and replay, and R17b's entries in design/29's monitoring catalogue (E4.2), each to its squad's lead;
- the design document amendments of section 9 (chief-architect).

### 11. Failure modes
| Failure | Outcome | Visible as |
|---|---|---|
| The pinned `buf` refuses an option used in its own file | #353 stops `blocked`; this RFC is amended | #353's hand-off |
| A file's options package is missing from the set | The lint exits 2 with its code; it never reports `Clean` | stderr and the CI step |
| A manifest's `[identity] namespace` differs from the upstream value | The brand manifest loader refuses it (#1856); the lint reads no other namespace | The loader's error |
| A `data_class` number the enum does not declare | SL01 at that field | The lint's finding |
| A field release, a level release or a wire-name change without a new matching entry | SL12 exits 1, naming the field, level or value, both values and the entry it needs | The SL12 check |
| An entry already on the base, edited, removed, repeated or matching no change | SL12 exits 1, naming the entry | The SL12 check |
| A base or head input of `compare` is missing or unreadable (security B1) | Exit 2 with its code; never a pass | The SL12 check |
| `--bootstrap` on a base that holds a data file | Exit 2 | The SL12 check |
| A pull request changes SL12's code or fixtures (security M3) | No effect on its own check: SL12 runs from the base's build; the change takes the full lane | The SL12 check and the evaluators |
| `capture.toml` has an unknown key, a repeated name, an undeclared class or a class in both lists (security M8) | The loader exits 2 with its code, for every reader | `capture --check` and the SL12 check |
| A leaf has no class, imported leaves included (security M7) | The filter produces no copy (`UnregisteredField`), and the caller counts it in `health.coverage` | #117's error and the coverage count |
| A change merges onto a newer base than its checks read (security m5) | The push run fails and opens an issue for the chief architect; the revert is its own issue | The push run and the issue |
| A release reaches a deployed device before the step-up | The filter keeps the entry's base treatment until the confirmation | #117's tests; the monitoring catalogue diff |
| Both codec features are enabled | `grdr-proto` does not compile | The build error |
| A configuration change makes a fixture case pass | R23's step fails, naming the case | Job log |
| A committed descriptor set or vector is stale | #1842 R5 or R6 fails, naming the file and the rebuild command | Job log |
| A codec's build script needs `protoc` or `buf` | #360 or #368 stops `blocked` (W2); the `rust` job's check fails | The hand-off and the job log |
| A resolve differs from R27 at implementation time | Listed for `eval-licence` and `eval-security` (R31) | #360's hand-off |

## Surfaces changed
| Surface | Class | At the freeze (04-29) |
|---|---|---|
| Package `grdr.common.v1alpha1`: `options.proto`, the enums, the option names | experimental (`surfaces.toml`) | renamed `v1`; option and value names kept |
| The wire names of `DataClass` and `ContentKind`, and the class names of R11 | experimental | kept; a change needs an entry (R17) |
| The capture level names in `capture.toml` | experimental | kept; the level set changes only as R17 allows |
| Option numbers 50001 to 50004 and 50011 | experimental | not kept: #398 moves them. Read options by full name (R6). An embedder with its own options on the same extendees keeps clear of these five numbers |
| `crates/grdr-proto/descriptors/proto.binpb` | experimental | regenerated with every change |
| The features `sp1-buffa` and `sp1-prost` of `grdr-proto` | experimental | not kept: the loser leaves with SP-1's adopting item, and the winner stops being a feature |
| The generated module `grdr_schema::capture` | experimental | follows `capture.toml` |
| `buf.yaml`, `capture.toml`, `reclassifications.toml` | gate data, trust core | not a product surface |

- `options.proto` defines no message, so no event changes. The default build of `grdr-proto` and its closure are unchanged.
- As proposals: design/04 sections 1, 10, 11, 13 and 14, design/26 section 9, design/36 section 2, a `surfaces.toml` row and nine `security/trust-core.paths` lines. No spine text, pinned path, Cedar schema, licence policy or same-layer edge changes.
- This RFC releases no field and no level and changes no wire name, so it adds no entry to `reclassifications.toml`.

Data classes (P8): this RFC adds the class mechanism and no data field. The lint and the build scripts read schema descriptors and data files only, which are `structural`, and log no event data. Assurance effect (P1): none. No action class changes `visibility`, `control`, `on_failure` or `tamper`.

## Alternatives
- **Two files, `options.proto` and `data_class.proto` (#353 as written).** An import cycle. Rejected for one file.
- **A `wire_name.proto` fallback (revisions 2 and 3).** `buf` 1.67.0 accepts an option used in its own file, and a second options file is what ruling 7 forbids. Removed.
- **The options package as a literal in each reader (revision 1).** It breaks at the freeze and cannot serve N and N-1 at once. Rejected for R6.
- **The options package as a key of the `[[proto_package]]` row.** It works, but it is a second statement of what the import already says. Rejected for the import.
- **The stability class stated by the suffix and the row, held equal by SL12 (revision 1).** Two sources, and it forbids an experimental `v1`, which D-60 and ADR-0020 allow. Rejected for SL11's one-way rule.
- **A per-field or per-file `stability` option.** A second source beside `surfaces.toml` (ADR-0020, P17). Rejected.
- **`encoding` now (revision 1).** #353 and #360 have no bytes field, and a closed set fixed now would have to fit `Receipt.decision`, `native` and `Redaction.original` unseen. Deferred to #18's RFC (R14).
- **Reclassification held by reading the registry diff (revision 1).** Any accepted RFC satisfies `rfc-required`, so a downgrade passes every check. Rejected for SL12.
- **A record that cites any RFC number (revision 2).** The pull request that downgrades a field can write its own excuse. Rejected.
- **Decision lines read from an accepted RFC's text (revision 3).** The lint has to parse Markdown, whose open cases (HTML comments, nested headings, quotes) each let a line count or not by accident; an accepted RFC can gain a line later through a low-tier edit; and a line, once accepted, excuses the same change again and again. Rejected for a once-only entry in a trust-core file, which forces the full lane and a seat's review (ruling 1).
- **SL12 built from the head, with its code made trust core only.** The lane would review a change to SL12, but the check would still pass mechanically on the pull request that changes it. Rejected for the base's build, with the trust-core lines kept as well (ruling 2).
- **A missing base file passes (revisions 1 to 3).** "Could not look" read as "nothing found" (P9). Rejected for exit 2 and a bootstrap flag honoured on one base only.
- **One gate item that also creates `capture.toml` (revision 3).** It lands before the lint exists, so the bootstrap flag of ruling 3 would have no run to use it, and nothing would check the file's first form. Rejected for the capture item, which comes after the lint and runs the flag once.
- **Field identity by path (revision 3).** A field at a new path had no floor. Rejected for the message's full name and number, with a retype or move as a removal (ruling 5).
- **A fixed class per imported leaf.** A `Timestamp` on a content field would be structural. Rejected for the holder's class.
- **Enforcing `pseudonymous` now.** No option marks a principal-bearing field, so a check would have nothing to read. Deferred to #18's RFC; the flag is a declaration until then (ruling 6).
- **The default level only in configuration (eval-architecture round 3, not a finding).** Two homes for the floor P8 sets. Rejected: the file holds it and the configuration default is generated from it (ruling 4).
- **Each reader parsing `capture.toml`.** Five parsers that can disagree on a repeated table (SD-04). Rejected for one loader and generated constants.
- **Codec features that may be on together (revision 3).** Feature unification in an embedder's workspace would link two codecs. Rejected for `compile_error!`.
- **Matching a record to an RFC that merely mentions the path.** A mention is not a decision. Rejected; entries name the decision and the review.
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
- buffa is pre-1.0, and one crates.io account owns six of the crates. The lint depends on it even if prost wins, unless an amendment moves it. If buffa wins, the gate's decoder and the codec generator share one crate, so a decoding defect is common to both; the comparison with `buf`'s JSON rendering (section 8) is the independent reading.
- The option numbers stay in the in-house range until a third party grants a registered one (#398).
- A release or a wire-name change needs an RFC, an entry, a seat's review and the full lane, and reaches a deployed device only after the organisation's step-up. A retired option keeps its declaration.
- SL12 checks that an entry exists and is new, not that its RFC decided the change or that its review approves it. The full lane on the record file holds that, and every comment and verdict is made under one login (ADR-0035).
- A genuinely new field or message gets its class from review and the privacy canary, not from SL12. A new version of a package cannot land until the freeze RFC defines predecessors.
- The lint crate, the filter, `buf.yaml`, its fixtures and both data files become trust core, so #386, #117 and every later change to them take the full lane. #353 waits on the gate item, and every proto change after it waits on #1843.
- Moving a file SL12 reads takes two changes, because the base's build looks only at the paths it knows.
- The negative controls need a fresh copy of the checkout per case.

## Unresolved questions
1. **The registered extension range.** It waits on the protobuf global extension registry (#398, #17-E3). Until then a pool that merges an embedder's set with ours can meet one of our five numbers twice if the embedder used it; Surfaces changed tells embedders to keep clear of them, and a later option takes a new in-house number by RFC.
2. **If prost wins SP-1.** An amendment of this RFC may move the lint to `prost-reflect` (R26).
3. **Map order.** `buffa`'s default map type is a hash map, so two encodings of one map need not match byte for byte. The schema allows one map, `native` (design/04 section 1 rule 4), and SP-1's schema has none. Integrity hashes the bytes as first encoded and nothing re-encodes before verifying (rule 8). #368's lead decides whether SP-1 adds a `native`-shaped case.
4. **Left to #18's RFC** (R14): `encoding`, the digest labels, the class of a namespace message-typed field, the principal marker that would let `pseudonymous` be enforced, and the evidence-span and content-grant routes.
5. **Left to the freeze RFC** (04-29): how a field in `v1` names its predecessor, and a second options file.
6. **Not checked here.**
   - The pinned `buf`: no pin exists yet (#1697). `eval-adversarial` ran `buf` 1.67.0 on section 1's layout and on R23's cases in round 3; #353 AC-1 and the gate item's criteria are the first runs at the pin.
   - The pinned cargo-deny 0.22.0; 0.21.0 ran.
   - Either codec's behaviour, which is SP-1's job.
   - `buffa-descriptor`'s reading of custom options was read in its published source, not run.
   - That `buf`'s JSON rendering of the set names extension options in the form the lint item reads; the lint item confirms it on its first run.

## Review
Round 4, set by the session (ruling, https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073435306):
- `eval-architecture` on the delta from revision 3;
- `eval-security`, on Opus and on Sonnet;
- `eval-adversarial`, bounded to the seeds below;
- persona council seats 3 (`persona-soc-analyst`), 5 (`persona-oem-partner`), 6 (`persona-privacy-officer`) and 8 (`persona-simplicity`, checking the simplification).

Each puts one comment on #1848. Each comment opens with three role lines, then the other blobs it read:
- `RFC file: <blob of rfcs/0006-grdr-common-v1alpha1-options-and-sp1-crates.md at the commit reviewed>`;
- `Proposed text: none`;
- `Base: a80859235e7a2a4444648d6fa8d389d78dde6be9`, the spine pin;
- `read=<path>@<blob>` for every other file it relied on.

A comment without these lines does not count. This RFC changes no pinned path, so its decision has no RFC 0001 decision line (ADR-0036). The decided file may differ from the reviewed blob only where RFC 0001's "Review binds the decision" allows.

Round 1, on blob `b9f2b99aa9f46dffbeacd71f0a2c9deeddcccb22`:
- `eval-architecture` (Sonnet): fail, four majors and seven minors. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7072892832

Round 2, on blob `a916eaaa12f51817ce999fd5c6e17a017f340a2f`:
- `eval-architecture` (Opus, delta): fail, one major and four minors. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073095604

Round 3, on blob `4a8a30ed8f754ec15901532ca9cbc70719bf422d`:
- Seat 3, SOC analyst: support with changes. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073200737
- Seat 6, privacy officer: support with changes. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073213867
- Seat 5, OEM partner: support with changes. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073219623
- `eval-architecture` (Sonnet, delta): pass, five minors. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073232910
- `eval-adversarial` (Sonnet): fail, four majors and nine minors. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073366794
- `eval-security` (Opus): fail, one blocker, eight majors and six minors. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073422577
- The session's rulings 1 to 11 for revision 4. https://github.com/416rehman/Guardrails/issues/1848#issuecomment-7073435306

This text was written against these blobs, on `main` unless named:
- `docs/design/00-decisions.md`: `a80859235e7a2a4444648d6fa8d389d78dde6be9`;
- `docs/design/04-event-model-and-schemas.md`: `e77880a12d2f42e715836a6da9598b86f33b20b0`;
- `docs/design/16-data-protection.md`: `2a1b57f0a0979d5ff0d5df9760db50d24b336bc3`;
- `docs/design/26-embedding-oem-and-white-label.md`: `8d9327dce0ca530e065f06a8ed287dec664e1f5b`;
- `docs/design/29-compliance-and-privacy.md`: `dc26184909208f3d50ac670158cc505efad3e003`;
- `docs/design/36-legal-brand-and-commercial.md`: `dfcb5df2a9be6f5d58719919f17e32057301da47`;
- `rfcs/0001-adopt-the-spine.md`: `353436cd2f9cff08037783ca66678c52cd7d6be4`;
- `rfcs/0004-c-header-generation-and-drift-check.md`: `1f998f42db6c6ea6640c55df0a655e450759340f`;
- `security/trust-core.paths`: `d773ad485f0f7e4bfca5ff8d84e72d354e7dca5e`;
- `brand/brand.toml`: `a32c7cfbf0c9197a8464581483546e74f08c545b`;
- `supply-chain/licences.toml`: `65338a382a81c1ac500c533e22fa6ee22397928d`;
- `supply-chain/admissions.toml`: `1b25c164ade9d313e80bd6286444e289062d7f1f`;
- `deny.toml`: `2d0457ff71ea5c9bba91de0a580cd80f650d1479`;
- ADR-0007: `5b6cdffc1648817f3e48a821ef2b34383b24b8f1`;
- ADR-0020: `e0a2998b7baed6c2aa21629ce25d61f2fa12ad20`.

`eval-adversarial` checks these seeds and what they reveal. It does not run an open search. Each seed asks whether the text, as written, lets the case through:
- A1. A field whose `data_class` comes from a same-named extension in another package.
- A2. A `data_class` number the enum does not declare.
- A3. A field moved from `content.argument` to `structural` in a change that names some accepted RFC and adds no entry, or relies on one already on the base.
- A4. A oneof member, a nested message's field or a map field with no class.
- A5. A committed descriptor set that drops a field the tree has.
- A6. An option declared outside the options file under number 50001, or a retired option's number given to a new one.
- A7. A look-alike crate name, or a version outside R24, in `Cargo.lock`.
- A8. A build script that can reach `protoc` or `buf`.
- A9. A `stable` row over a `v1alpha1` package.
- A10. A module-level `lint` or `breaking` block, `ignore_unstable_packages`, or a `// buf:lint:ignore` comment.
- A11. A file that imports the options file as public or weak, or a second file that declares an extension or a `DataClass`.
- A12. A level that passes more, a level the base lacks, a repeated level name, an unknown key, a changed default, or `identifier` losing `pseudonymous`.
- A13. An entry that is edited, removed, re-added, or matches no change, or whose `rfc` names no file on the base.
- A14. A pull request that changes SL12's code or fixtures and lowers a field.
- A15. A base or head input that is missing, moved or unreadable, and `--bootstrap` on a base that holds a data file.
- A16. A field renamed, retyped, moved to another message, or declared again in a new package version.
- A17. A field whose type is a message outside the namespace.
- A18. An enum value whose `wire_name` changes or that disappears.
- A19. Both codec features enabled at once.

### Round 3 dispositions
Every round 3 finding, and where revision 4 takes it. "Ruling n" is the session's comment above.

| Verdict | Finding | Disposition |
|---|---|---|
| `eval-security` | B1 SL12 passes when it cannot look | SL12 exits 2 on any missing input (section 7); bootstrap only through R19a (ruling 3) |
| `eval-security` | M1 a line added to an accepted RFC later counts | Gone: SL12 reads no RFC text (R17, ruling 1) |
| `eval-security` | M2 a record is never spent | R17 rule 1: an entry counts only in the change that adds it; append only |
| `eval-security` | M3 SL12's code and fixtures come from the head | Section 7: SL12 runs from the base's build; R19 lists the lint and the filter (ruling 2) |
| `eval-security` | M4 `identifier` to content needs no record | R17: leaving a `pseudonymous` class is a field release (ruling 6) |
| `eval-security` | M5 a field at a new path has no floor | R17a: identity by message and number; a new version fails until the freeze RFC (ruling 5); new fields are a stated residual (Drawbacks; #493) |
| `eval-security` | M6 a second options package with its own `DataClass` | SL10 and SL13 allow one options file and one `DataClass`; R11 ties each wire name to its value (ruling 7) |
| `eval-security` | M7 imported message types escape the rules | R14a and SL10; the registry gives imported leaves their holder's class; #117 refuses a classless leaf (ruling 8) |
| `eval-security` | M8 levels not closed, five parsers | R13's one loader and its refusals; R17's level rules; `default` in the file (ruling 4) |
| `eval-security` | m1 the decision line has no grammar | Gone with the lines (ruling 1) |
| `eval-security` | m2 the record's RFC and the removal form | R17: `rfc` is four digits naming one base file, no state read; `to = "removed"` |
| `eval-security` | m3 `pseudonymous` has no reader | R13: a declaration read by exports and the disclosure view; the marker goes to #18 (R14) |
| `eval-security` | m4 SL10's terms are open | SL10: one options file, direct imports only, no public or weak import, nested extensions included; section 1's fallback removed |
| `eval-security` | m5 a green SL12 on a stale base | Section 7: the push run against the parent, with an issue and a revert |
| `eval-security` | m6 the `buffa-descriptor` evidence | R31's `unsafe` wording; the `buf` JSON comparison (section 8, #1843) |
| `eval-security` | Fail-mode rows | Section 11 gains the five proposed rows and the rest of the threat model's failure table |
| `eval-security` | #1854's SR entries | #1854 follows the accepted text; the name differences are in section 10 |
| `eval-adversarial` | M1 a decided downgrade authorises itself again | R17 rule 1 |
| `eval-adversarial` | M2 the line grammar is open | Gone (ruling 1) |
| `eval-adversarial` | M3 lines outside every route | Gone (ruling 1) |
| `eval-adversarial` | M4 `capture.toml` has no structural rules | R13's loader; SL13 |
| `eval-adversarial` | m1 exit 0 when it could not look | Exit 2 (section 7) |
| `eval-adversarial` | m2 identity by path; no removal form | R17a; `to = "removed"`; new fields as a stated limit |
| `eval-adversarial` | m3 no recursion or map rule for A4 | Section 10, #386: nested messages, oneof members, map entries, with fixtures |
| `eval-adversarial` | m4 the undeclared-number clause has no fixture | R12: a set changed in memory |
| `eval-adversarial` | m5 R23 can test the wrong configuration | R23 names `proto` as the input in every command; R18 states what only the lane holds |
| `eval-adversarial` | m6 SL10 counts direct imports only | SL10 refuses a public or weak import of the options file |
| `eval-adversarial` | m7 A7 and A8 rest on review | Section 8: no schema compiler in the `rust` job and `Cargo.lock` against the admissions; #360's new criteria; R28 on `grdr-proto`'s manifest |
| `eval-adversarial` | m8 the enforcer is not trust core | R19 (ruling 2) |
| `eval-adversarial` | m9 a window before SL12 lands; one premise | R5 states what `buf breaking` checks; #1843 blocks every later proto change (section 10) |
| `eval-architecture` | m1 "decision line" names two things | Gone: only RFC 0001's decision lines remain |
| `eval-architecture` | m2 three cases of the grammar open | Gone; `to = "removed"`; no reserved `all`, because class properties change only by RFC |
| `eval-architecture` | m3 an accepted line is a standing authorisation | R17 rule 1 |
| `eval-architecture` | m4 head-side and missing-file cases | Exit 2 for base and head (section 7); repeated names refused (R13); R19a's flag |
| `eval-architecture` | m5 review of `rfcs/**` is low tier | No change needed: SL12 no longer trusts RFC text, so the residual and its sentence are gone. The remaining residual, that the lane checks `rfc` and `review`, is in Drawbacks |
| `eval-architecture` | Not a finding: the default level lives in configuration | Ruling 4: `default` is in the file and the configuration default is generated from it (R13) |
| Seat 3 | F1 a `wire_name` can change silently | R17's wire-name change and its entry (ruling 11) |
| Seat 3 | F2 the evidence-span route | R13 and R14: not a level; #18's RFC names it; the matrix is incomplete for findings until then |
| Seat 3 | F3 the rule linter, replay and mapper | R13's readers and the "could not look" rule |
| Seat 3 | F4 an export meeting an unknown value | R12; the mapper (#495) |
| Seat 5 | H1 the namespace comes from a swappable manifest | R3, section 9 and section 11 (ruling 10); #1856. The ruling cites #398; the package-rename half of 04-4 is #396, which R3 cites. Ruling 10 also binds RFC 0007 (#1710), which this RFC does not edit |
| Seat 5 | M1 the surfaces the RFC adds | The table under Surfaces changed; R6; Unresolved question 1 |
| Seat 5 | M2 partner telemetry and classes | R13 (a mapping never assigns a class; partner levels refused); R14a (partner packages) |
| Seat 5 | M3 the codec features and wasm32 | R24 (`compile_error!`); #360's new criteria |
| Seat 5 | L1 the licence-closure report | R29 |
| Seat 6 | 1a SL12 fails open | Exit 2; R19a |
| Seat 6 | 1b an accepted RFC can gain a line | Gone (ruling 1) |
| Seat 6 | 1c a new level is not a release | R17: a level the base lacks releases every class it passes or redacts |
| Seat 6 | 2 `pseudonymous` is a label | R13 wording; R14's marker (ruling 6) |
| Seat 6 | 3 no works-council path for a release | R17b (ruling 9); `review` names the seat 6 comment |
| Seat 6 | 4 default, `ships`, readers, retention and `secret` | R13: `default`, `passes`, the disclosure view and tray as readers, and where retention and the `secret` rule live |
| Seat 6 | 5 no form for a disappearing field | R17 (`to = "removed"`) and R17a |

## Decision
Not decided.
