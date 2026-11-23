RFC: 0021
Title: grdr.config.v1alpha1 endpoint keys, defaults and location table
Author: chief-architect
Harness: Antigravity
Model: Gemini 4 Neon (pro)
State: Review
Design issue: #669
Spine: P8, P14, P16, P17, D-20, D-37, D-48, D-61, D-63, D-66, D-69
Surfaces: proto/grdr/config/v1alpha1/** (wire format), proto/grdr/common/v1alpha1/options.proto (RFC 0006 option registry amendment), surfaces.toml
Decision record: none yet

## Summary

This RFC defines the endpoint configuration schema under protobuf package `grdr.config.v1alpha1` (`Config` sections `install`, `paths`, `accounts`, `endpoints`, and `packs`), registers the configuration key options (`security`, `env_ok`, `stability`, and reserves `tier` for `#1035`) by amending [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md), sets out how `(os, profile)` defaults live as structural data rather than literals in code (`P14`, `D-69`), and fixes the canonical per-OS, per-profile tables across Linux, macOS, and Windows for both `Protected` and `User` profiles (`design/11` section 5, `design/24` section 3, `design/07` section 2).

## Motivation

Every endpoint program on the first-run path (`#1610` install profile, locations, and accounts; `#148` directory owner checks; `#157` local IPC endpoint; `#1538` R1 and `#1862` R5 read-only bundle directory; `#149` R1 and `#1660` R1 component spawning; `#150` status snapshot; `#1673` R6 state and shim directories) requires canonical configuration keys and per-OS, per-profile defaults before it can resolve a single directory, service account, or IPC endpoint.

Currently `proto/grdr/config/v1alpha1/` does not exist, `proto/grdr/common/v1alpha1/options.proto` lacks `security`, `env_ok`, `stability`, and a registry reservation for `tier`, and `design/11` section 5 omits two required location rows (the installed read-only bundle directory and the hook shim directory) while carrying minor divergences against `design/07` section 2, `design/09` section 2, `design/24` section 3, and RFC 0003 section 6. Fixing the protobuf layout, option registry, base-token mechanism, brand derivation, and complete `(os, profile)` tables in one RFC unblocks `#148`, `#157`, `#1610`, `#1862`, `#1901`, and `#1905` without assuming the layer resolver (`#1591`) or server keys (`#1035`).

## Design

### 1. Package skeleton (`grdr.config.v1alpha1`) and file layout

Following [design/04](../docs/design/04-event-model-and-schemas.md) section 1 Rule 6 (one file per message family), [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md) lint rules `SL01` to `SL13`, and Buf `STANDARD` conventions:

1. **Files under `proto/grdr/config/v1alpha1/`:**
   - `config.proto`: `package grdr.config.v1alpha1;` root `Config` message and section imports.
   - `install.proto`: `InstallConfig`, `Profile`, `FirstRunMode`, `ComponentPreset`, `Component`.
   - `paths.proto`: `PathsConfig` (configured path overrides and base-token-resolved locations).
   - `accounts.proto`: `AccountsConfig` (per-role OS service account bindings).
   - `endpoints.proto`: `EndpointsConfig`, `EndpointBinding`, `EndpointRole`, `EndpointTransport`.
   - `packs.proto`: `PacksConfig`, `PackChannel`, `PackSlot`.
   - `defaults.proto`: `OsFamily`, `InstallLayout`, `BaseToken`, `TemplatePath`, `PathDefaults`, `OsProfileDefaults`, and `EndpointDefaults`.

2. **Proto3 presence and structural rules (`RFC 0006` `SL01` to `SL13`):**
   - Scalar leaf fields in configuration sections MUST use proto3 explicit `optional` so multi-layer merging (`#1591`) distinguishes an explicitly configured value from an omitted layer entry.
   - Zero `map<K, V>` fields except where explicitly named `native` (`RFC 0006` `SL07`); none appear in the files of this RFC. All `(os, profile)` default tables and component lists use `repeated` messages or `repeated` enums.
   - Zero `google.protobuf.Any` or `google.protobuf.Struct` (`RFC 0006` `SL07`).
   - Every field in every message carries `(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL` (`SL01`).
   - Every enum value except `_UNSPECIFIED = 0` carries `(grdr.common.v1alpha1.wire_name)` (`SL04`); zero values carry no `wire_name` (`RFC 0006` `R12`).

3. **Root `Config` message and additive extension:**

```protobuf
syntax = "proto3";

package grdr.config.v1alpha1;

import "grdr/common/v1alpha1/options.proto";
import "grdr/config/v1alpha1/install.proto";
import "grdr/config/v1alpha1/paths.proto";
import "grdr/config/v1alpha1/accounts.proto";
import "grdr/config/v1alpha1/endpoints.proto";
import "grdr/config/v1alpha1/packs.proto";

// Unified schema root for endpoint and server configuration.
message Config {
  InstallConfig install = 1 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];

  PathsConfig paths = 2 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];

  AccountsConfig accounts = 3 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];

  EndpointsConfig endpoints = 4 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];

  PacksConfig packs = 5 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];
}
```

Later configuration families join additively by placing each new section in its own `.proto` file (`updates.proto`, `network.proto`, `uplink.proto`, `recorder.proto` for `#1901`; `server.proto`, `operator.proto` for `#1035`) and claiming sequential unused field tags on `Config` starting at tag `6`. `Config` leaves tags `6` onwards unreserved so `buf breaking` permits additive section registration. Layer-location keys (`local` and `user` config file paths, `#1905`) add optional fields to `PathsConfig` once `#71` fixes the layer document format.

Package stability is recorded in [surfaces.toml](../surfaces.toml) as `stability = "experimental"` (`ADR-0020`).

### 2. Key options and amendment to RFC 0006

[RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md) rule `SL10` forbids declaring custom `google.protobuf.*Options` extensions outside `proto/grdr/common/v1alpha1/options.proto`, and RFC 0006 section 2 governs the extension number registry by RFC.

This RFC amends **RFC 0006 section 2** to add three field options and one closed enum to `proto/grdr/common/v1alpha1/options.proto`, and reserves tag `50008` for `#1035`:

| Number | Extends | Name | Type | Meaning |
|---|---|---|---|---|
| `50005` | `FieldOptions` | `security` | `optional bool` | When `true`, authority layers 4 to 6 (`user`, `env`, `cli`; `design/03` section 9) are ignored in `Protected` |
| `50006` | `FieldOptions` | `env_ok` | `optional bool` | When `true` and permitted by `security` and active profile, environment variables may override the field |
| `50007` | `FieldOptions` | `stability` | `optional StabilityClass` | Per-key lifecycle stage (`experimental`, `beta`, `stable`) inside `grdr.config.v1alpha1` |
| `50008` | `FieldOptions` | `tier` | *(reserved for `#1035`)* | Registry slot reserved for server `boot` vs `runtime` classification in `#1035` |

```protobuf
// Per-key lifecycle stage on grdr.config.v1alpha1 configuration fields.
enum StabilityClass {
  STABILITY_CLASS_UNSPECIFIED = 0;
  STABILITY_CLASS_EXPERIMENTAL = 1 [(wire_name) = "experimental"];
  STABILITY_CLASS_BETA = 2 [(wire_name) = "beta"];
  STABILITY_CLASS_STABLE = 3 [(wire_name) = "stable"];
}

extend google.protobuf.FieldOptions {
  // Existing 50001..50004 from RFC 0006 unchanged.
  optional bool security = 50005;
  optional bool env_ok = 50006;
  optional StabilityClass stability = 50007;
  // 50008 reserved in registry for #1035 (`tier`); omitted from extend block so #1035 adds cleanly.
}
```

**Clarification of RFC 0006 R16:** RFC 0006 R16 forbids per-service or per-package stability options on RPC definitions because package and crate stability belong in `surfaces.toml` (`ADR-0020`). Per-key `(stability)` on configuration fields in `grdr.config.v1alpha1` serves a distinct mechanism required by `design/03` section 9 and `design/34` section 10: individual config keys within an `experimental` or `beta` package graduate independently across `experimental -> beta -> stable` and drive `grdr config explain` (`#1591`), generated docs tables, and deprecation notices. RFC 0006 R16 remains unchanged for RPC services, messages, and non-config packages.

**Normative option values on all RFC 0021 keys:** Every section and leaf key introduced by this RFC carries:
- `(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL`
- `(grdr.common.v1alpha1.security) = true`
- `(grdr.common.v1alpha1.env_ok) = false`
- `(grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL`

### 3. Defaults as data, base tokens, and Class A vs Class B brand derivation

#### 3.1 Where defaults live and who resolves them

No binary crate (`crates/*`, `programs/*`, `platform/*`) may hard-code fallback paths, service account strings, pipe names, or endpoint paths (`P14`, `D-69`, `design/03` section 10). Defaults follow the repository's schema-as-data pipeline (`schema/limits.toml`, `schema/health.toml`):

1. **Schema data source:** Canonical `(os, profile, layout)` default records live in `schema/config/endpoint-defaults.toml`, matching the schema of `grdr.config.v1alpha1.EndpointDefaults` in `defaults.proto`:

```protobuf
enum OsFamily {
  OS_FAMILY_UNSPECIFIED = 0;
  OS_FAMILY_LINUX = 1 [(grdr.common.v1alpha1.wire_name) = "linux"];
  OS_FAMILY_MACOS = 2 [(grdr.common.v1alpha1.wire_name) = "macos"];
  OS_FAMILY_WINDOWS = 3 [(grdr.common.v1alpha1.wire_name) = "windows"];
}

enum InstallLayout {
  INSTALL_LAYOUT_UNSPECIFIED = 0;
  INSTALL_LAYOUT_STANDARD = 1 [(grdr.common.v1alpha1.wire_name) = "standard"];
  INSTALL_LAYOUT_SELF_SLOTTED = 2 [(grdr.common.v1alpha1.wire_name) = "self-slotted"];
}

message TemplatePath {
  optional BaseToken base = 1 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
  optional string relative = 2 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
}

message OsProfileDefaults {
  optional OsFamily os = 1 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
  optional Profile profile = 2 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
  optional InstallLayout layout = 3 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
  PathDefaults paths = 4 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
  AccountsConfig accounts = 5 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
  EndpointsConfig endpoints = 6 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
  PacksConfig packs = 7 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
}

message EndpointDefaults {
  repeated OsProfileDefaults rows = 1 [(grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL];
}
```

2. **Layer 0 representation (`grdr-schema`):** Build/code checks compile and validate `schema/config/endpoint-defaults.toml` into constant structural tables in `grdr-schema` (`no_std`-compatible, zero I/O, zero environment reads per `ARCH-001` to `ARCH-003`). `grdr-schema` verifies table completeness across all `3 OS x 2 Profile = 6` `INSTALL_LAYOUT_STANDARD` pairs (`linux`, `macos`, `windows` x `protected`, `user`) plus the `(linux, protected, self-slotted)` row; any missing pair fails `cargo test`.
3. **Brand substitution (Layer 0 / compile-time `brand/brand.toml`):** Structural template rendering replaces brand placeholders from compile-time brand metadata (Section 3.3), returning pure descriptors carrying `(BaseToken, relative)` without touching host paths or user context.
4. **Runtime base-token resolution (Layer 3 OS adapters and `grdr-wire`):** Layer 3 OS adapters read host environment, Windows Known Folders, UID, and SID (`UserContext`) to resolve `BaseToken` values into concrete filesystem paths, or pass `BaseToken`-mapped `grdr_wire::peer_auth::Place` variants to `grdr_wire::peer_auth::resolve` (`RFC 0003` section 6) for IPC endpoints. If any required `BaseToken` cannot be resolved, startup stops before creating directories or binding endpoints.

#### 3.2 Named `BaseToken` catalogue

| Proto enum value (`BaseToken`) | Wire name | OS scope | Resolution rule and failure behaviour |
|---|---|---|---|
| `BASE_TOKEN_UNSPECIFIED` | *(none)* | Invalid | Rejected by schema validation |
| `BASE_TOKEN_ABSOLUTE` | `"absolute"` | All (`Protected`: `/opt`, `/usr`, `/etc`, `/var`, `/run`; macOS `/Library/...`, `/var/db`, `/Applications`) | Literal root-anchored path; no user or environment expansion |
| `BASE_TOKEN_XDG_DATA_HOME` | `"xdg_data_home"` | Linux `User` | `$XDG_DATA_HOME` if set, non-empty, and absolute; otherwise `$HOME/.local/share`. Fails pre-start (`GRDR-CFG-0003`) if fallback needs `$HOME` and `$HOME` is unset, empty, or relative |
| `BASE_TOKEN_XDG_CONFIG_HOME` | `"xdg_config_home"` | Linux `User` | `$XDG_CONFIG_HOME` if set, non-empty, and absolute; otherwise `$HOME/.config`. Fails (`GRDR-CFG-0003`) if `$HOME` unavailable |
| `BASE_TOKEN_XDG_STATE_HOME` | `"xdg_state_home"` | Linux `User` | `$XDG_STATE_HOME` if set, non-empty, and absolute; otherwise `$HOME/.local/state`. Fails (`GRDR-CFG-0003`) if `$HOME` unavailable |
| `BASE_TOKEN_XDG_RUNTIME_DIR` | `"xdg_runtime_dir"` | Linux `User` | `$XDG_RUNTIME_DIR` only; must be set, non-empty, and absolute. **No fallback.** Fails pre-start (`GRDR-PEER-0011` for wire endpoints; `GRDR-CFG-0003` for runtime path checks) |
| `BASE_TOKEN_HOME` | `"home"` | Linux `User` (`user_bin_dir`) | `$HOME` only; must be set, non-empty, and absolute. Fails (`GRDR-CFG-0003`) if unset |
| `BASE_TOKEN_APPLE_APP_SUPPORT` | `"apple_app_support"` | macOS `User` | `$HOME/Library/Application Support`; maps IPC endpoints to `Place::UnderHome("Library/Application Support/...")`. Fails (`GRDR-CFG-0003` / `GRDR-PEER-0011`) if `$HOME` unavailable |
| `BASE_TOKEN_WIN_LOCAL_APP_DATA` | `"win_local_app_data"` | Windows `User` | Windows `FOLDERID_LocalAppData` (`%LOCALAPPDATA%`), **never** roaming `%APPDATA%` (`FOLDERID_RoamingAppData`). Fails (`GRDR-CFG-0003`) if unavailable |
| `BASE_TOKEN_WIN_PROGRAM_FILES` | `"win_program_files"` | Windows `Protected` | Native 64-bit `FOLDERID_ProgramFiles` (`%ProgramFiles%`). Fails (`GRDR-CFG-0003`) if unavailable |
| `BASE_TOKEN_WIN_PROGRAM_DATA` | `"win_program_data"` | Windows `Protected` | Windows `FOLDERID_ProgramData` (`C:\ProgramData`). Fails (`GRDR-CFG-0003`) if unavailable |
| `BASE_TOKEN_PIPE_PREFIX` | `"pipe_prefix"` | Windows `Protected`, `User` | Windows local pipe namespace `\\.\pipe\`; in `User`, suffix appends `-<user_sid>` (`Place::PipeForCaller`, RFC 0003 section 6). Fails (`GRDR-PEER-0011`) if caller SID unavailable |

**RFC 0009 Constraint 2a compliance:** Windows `User` defaults place config, state, engine data, slots, bundle, and shims under `BASE_TOKEN_WIN_LOCAL_APP_DATA` (`%LOCALAPPDATA%`), which stays on the local disk rather than roaming `%APPDATA%`. If a host environment still redirects `%LOCALAPPDATA%`, `~/Library/Application Support`, or `$HOME/.local/state` onto a network mount or redirected profile folder, the OS adapter and store MUST NOT refuse startup on mount-type grounds (`#30`, `#301`, `#1542`).

#### 3.3 Class A vs Class B brand placeholders (`D-66`, `design/36` section 2, `design/26` section 9)

Defaults use two compile-time brand placeholders sourced from `brand/brand.toml` (`a32c7cfbf0c9197a8464581483546e74f08c545b`):

1. **`{ns}` (namespace / technical slug):**
   - In upstream Guardrails ADR, `{ns}` reads `[identity].namespace` (`"grdr"`).
   - **Class A invariants:** Protobuf package names (`grdr.*`), wire option names, error code prefixes (`GRDR-*`), and pack schema identifiers NEVER change in OEM/white-label rebuilds (`RFC 0006` R3, `design/36` section 2).
   - **Class B OS overrides (`#1856` coordination):** Local filesystem directory segments (`/etc/{ns}`, `/var/lib/{ns}`, `/run/{ns}`, `/Library/Application Support/{ns}`, `C:\ProgramData\{ns}`, user directories), OS service/role account names (`{ns}-engine`, `_{ns}-engine`, `NT SERVICE\{ns}-engine`, `{ns}-uplink`, `{ns}-proxy`), and local IPC endpoint path/pipe prefixes (`/{ns}/decide.sock`, `\\.\pipe\{ns}-decide`) constitute Class B OS identity (`design/36` section 2, `design/26` section 9). They default to `[identity].namespace` (`"grdr"`) today and allow a white-label rebuild (`#1856`) to supply a dedicated Class B `os_slug` while keeping wire/proto `grdr.*` unchanged. A build-time check MUST reject any `os_slug` not matching `^[a-z][a-z0-9-]{0,15}$` so macOS and Linux `sun_path` bounds hold.
2. **`{brand}` (human OS-display directory and policy label):**
   - Reads Class B `[identity].short_name` (`"Guardrails"` in upstream) for `/Applications/{brand}.app`, `%ProgramFiles%\{brand}\`, and `HKLM\SOFTWARE\Policies\{brand}`.
   - MDM reverse-domain preferences on macOS derive from `[identity].domain` (`"guardrailshq.com"` -> `com.guardrailshq.{ns}`).
3. **Non-branded segments:** OS daemon identities (`root`, `LocalSystem`), pack channel names (`binaries`, `schema-policy`, `detection-content`, `native-agent-config`), slot names (`active`, `lkg`, `staged`), and endpoint role names (`decide`, `local`, `provider`) are fixed schema constants, not brand data.

### 4. `install` section (`install.proto`)

`InstallConfig` carries installation-decided state from `install.toml` (`design/24` section 3 and `install.toml` row, `#1660`, `#149` R1).

```protobuf
enum Profile {
  PROFILE_UNSPECIFIED = 0;
  PROFILE_PROTECTED = 1 [(grdr.common.v1alpha1.wire_name) = "protected"];
  PROFILE_USER = 2 [(grdr.common.v1alpha1.wire_name) = "user"];
}

enum FirstRunMode {
  FIRST_RUN_MODE_UNSPECIFIED = 0;
  FIRST_RUN_MODE_SCAN = 1 [(grdr.common.v1alpha1.wire_name) = "scan"];
  FIRST_RUN_MODE_USER = 2 [(grdr.common.v1alpha1.wire_name) = "user"];
  FIRST_RUN_MODE_PROTECT = 3 [(grdr.common.v1alpha1.wire_name) = "protect"];
}

enum ComponentPreset {
  COMPONENT_PRESET_UNSPECIFIED = 0;
  COMPONENT_PRESET_FULL = 1 [(grdr.common.v1alpha1.wire_name) = "full"];
  COMPONENT_PRESET_TARGETED = 2 [(grdr.common.v1alpha1.wire_name) = "targeted"];
  COMPONENT_PRESET_CUSTOM = 3 [(grdr.common.v1alpha1.wire_name) = "custom"];
}

enum Component {
  COMPONENT_UNSPECIFIED = 0;
  COMPONENT_UPLINK = 1 [(grdr.common.v1alpha1.wire_name) = "grdr-uplink"];
  COMPONENT_PROXY = 2 [(grdr.common.v1alpha1.wire_name) = "grdr-proxy"];
  COMPONENT_INFER = 3 [(grdr.common.v1alpha1.wire_name) = "grdr-infer"];
  COMPONENT_TRAY = 4 [(grdr.common.v1alpha1.wire_name) = "grdr-tray"];
  COMPONENT_DESKTOP = 5 [(grdr.common.v1alpha1.wire_name) = "grdr-desktop"];
}

message InstallConfig {
  optional Profile profile = 1 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];

  optional FirstRunMode first_run = 2 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];

  optional ComponentPreset component_preset = 3 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];

  repeated Component components = 4 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];
}
```

Normative rules for `install`:
1. **`install.profile` parity:** `Profile::PROFILE_PROTECTED` (`"protected"`) and `Profile::PROFILE_USER` (`"user"`) map 1:1 onto `grdr_model::InstallProfile::{Protected, User}` (`#1850`, RFC 0009). A parity test in `grdr-schema` asserts exhaustive bijective conversion. No default is supplied when `install.toml` is missing: the daemon refuses to start (`GRDR-CFG-0002`, `#1610` R5).
2. **`install.first_run`:**
   - `"scan"`: discovers agents and publishes readiness/status without activating user hooks (`design/24` section 3 `scan-only`).
   - `"user"`: `User` profile interactive first-run default (`#1660` R2, R4); equips per-user agent hooks without elevation.
   - `"protect"`: `Protected` / MDM install default; configures system hooks and enters the initial policy `Mode`.
   - `first_run` governs initial installation bootstrap only; active policy packs govern `Mode` thereafter.
3. **`install.components` and `"targeted"` preset (`design/11` sections 1 and 9; `#149` R1):**
   - `grdr-daemon` and `grdr-engine` are core processes; `grdr-cli` and `grdr-hook` are command/hook binaries. None of these four are gated by `install.components`.
   - `grdr-daemon` at start step 8 (`design/11` section 1) spawns ONLY the optional workers (`grdr-uplink`, `grdr-proxy`, `grdr-infer`, `grdr-tray`, `grdr-desktop`) enabled by the resolved component set (`#149` R1).
   - In `install.toml`, string `"targeted"` maps to `component_preset = COMPONENT_PRESET_TARGETED` (`design/11` section 9), which omits local ML (`grdr-infer`), UI workers (`grdr-tray`, `grdr-desktop`), local ingest proxy (`grdr-proxy`), and omits `grdr-uplink` unless enrolled/explicitly paired. An explicit list `components = [...]` maps to `component_preset = COMPONENT_PRESET_CUSTOM` with `components` populated (for example `["grdr-tray", "grdr-desktop"]` in local first run, or `["grdr-uplink", "grdr-proxy"]` in headless targeted servers). `COMPONENT_PRESET_FULL` enables all optional workers applicable to the active profile.
4. **Ruling on `grdr-uplink` in local-only first run:** Confirmed (`#669` "Uplink in the local-only first run"). An `install.components` set **without `grdr-uplink` is valid in the `User` profile** when unenrolled (`D-48`), and the user archive's first-run `install.toml` (`#1660`, `#1862`) omits `grdr-uplink`.
5. **Other `design/24` `install.toml` keys (`update_authority`, `enrol_file`):** Those keys remain reserved to `install.toml` packaging/enrolment flows (`#1901` owns `updates.authority`; enrolment consumes `enrol_file`) and are recognised as non-unknown keys when validating `install.toml`.

### 5. Per-OS, per-profile location table (`paths.proto`)

`PathsConfig` defines eleven optional string fields (all carrying `DATA_CLASS_STRUCTURAL`, `(security) = true`, `(env_ok) = false`, `(stability) = STABILITY_CLASS_EXPERIMENTAL`), mirrored as `TemplatePath` fields in `PathDefaults`:
`programs_dir = 1`, `slots_dir = 2`, `config_dir = 3`, `state_dir = 4`, `engine_data_dir = 5`, `runtime_dir = 6`, `status_snapshot_path = 7`, `bundle_dir = 8`, `shim_dir = 9`, `app_bundle_dir = 10` (macOS `Protected` container app only), `user_bin_dir = 11` (Linux `User` launcher dir only).

In `Protected`, only an installer or privileged package action creates root directories (`#148` R8); the daemon checks ownership and refuses unsafe directories rather than creating `Protected` trees itself. In `User`, first run creates missing user-owned directories with `0700` POSIX mode / caller-only Windows ACL.

All table entries expand `{ns}` -> `"grdr"` and `{brand}` -> `"Guardrails"` in upstream builds.

#### 5.1 Protected profile

| Location item | `PathsConfig` key | Linux (`Protected`) | macOS (`Protected`) | Windows (`Protected`) |
|---|---|---|---|---|
| Programs dir (`design/11` section 5) | `programs_dir` | `managed`: `/usr/libexec/{ns}` (with CLI at `/usr/bin/{ns}`).<br>`self`: `/opt/{ns}/current/bin` (`BASE_TOKEN_ABSOLUTE`) | `/Library/Application Support/{ns}/current/bin` (`BASE_TOKEN_ABSOLUTE`) | `{WIN_PROGRAM_FILES}\{brand}\bin` |
| Update A/B slots (`design/11` section 5) | `slots_dir` | `managed`: *(none)*<br>`self`: `/opt/{ns}/slots` (`{a,b}` + `current` symlink, `BASE_TOKEN_ABSOLUTE`) | `/Library/Application Support/{ns}/slots` (`{a,b}` + `current` symlink, `BASE_TOKEN_ABSOLUTE`) | `{WIN_PROGRAM_FILES}\{brand}\slots` (`{a,b}` + `current` pointer file) |
| System extension app (`design/09` section 2, `11` section 5) | `app_bundle_dir` | *(none)* | `/Applications/{brand}.app` (`BASE_TOKEN_ABSOLUTE`) | *(none)* |
| Admin configuration (`design/11` section 5) | `config_dir` | `/etc/{ns}` (`config.toml`, `install.toml`, `config.d/`) (`BASE_TOKEN_ABSOLUTE`) | `/Library/Application Support/{ns}/config` (`config.toml`, `install.toml`, `config.d/`) + MDM domain `com.guardrailshq.{ns}` (`BASE_TOKEN_ABSOLUTE`) | `{WIN_PROGRAM_DATA}\{ns}\config` (`config.toml`, `install.toml`, `config.d/`) + GPO `HKLM\SOFTWARE\Policies\{brand}` |
| State directory (`design/11` section 5) | `state_dir` | `/var/lib/{ns}` (`BASE_TOKEN_ABSOLUTE`) | `/Library/Application Support/{ns}/state` (`BASE_TOKEN_ABSOLUTE`) | `{WIN_PROGRAM_DATA}\{ns}\state` |
| Engine data (`design/11` section 5) | `engine_data_dir` | `/var/lib/{ns}-engine` (`BASE_TOKEN_ABSOLUTE`) | `/var/db/{ns}-engine` (`BASE_TOKEN_ABSOLUTE`) | `{WIN_PROGRAM_DATA}\{ns}\engine` (ACL: `NT SERVICE\{ns}-engine` SID) |
| Runtime endpoint dir (`design/11` section 5) | `runtime_dir` | `/run/{ns}` (`BASE_TOKEN_ABSOLUTE`) | `/Library/Application Support/{ns}/run` (`BASE_TOKEN_ABSOLUTE`) | *(none; Windows named pipes use `{PIPE_PREFIX}` in `endpoints`)* |
| Status snapshot file (`design/11` section 5, `#150`) | `status_snapshot_path` | `/var/lib/{ns}/status.pb` (`BASE_TOKEN_ABSOLUTE`) | `/Library/Application Support/{ns}/state/status.pb` (`BASE_TOKEN_ABSOLUTE`) | `{WIN_PROGRAM_DATA}\{ns}\state\status.pb` (Users Read ACL) |
| Read-only bundle dir (`#1538` R1, `#1862` R5) | `bundle_dir` | `managed`: `/usr/share/{ns}/bundle`<br>`self`: `/opt/{ns}/bundle` (`BASE_TOKEN_ABSOLUTE`) | `/Library/Application Support/{ns}/bundle` (`BASE_TOKEN_ABSOLUTE`) | `{WIN_PROGRAM_FILES}\{brand}\bundle` |
| Hook shim & fail-safe dir (`#1673` R6, `design/07` section 5) | `shim_dir` | `managed`: `/usr/libexec/{ns}`<br>`self`: `/opt/{ns}/current/bin` (`BASE_TOKEN_ABSOLUTE`) | `/Library/Application Support/{ns}/current/bin` (`BASE_TOKEN_ABSOLUTE`) | `{WIN_PROGRAM_FILES}\{brand}\bin` (SYSTEM/Admins-owned; **never** `ProgramData`) |

#### 5.2 User profile

| Location item | `PathsConfig` key | Linux (`User`) | macOS (`User`) | Windows (`User`) |
|---|---|---|---|---|
| Programs dir (`design/11` section 5, `#1660`) | `programs_dir` | `{XDG_DATA_HOME}/{ns}/current/bin` | `{APPLE_APP_SUPPORT}/{ns}/current/bin` | `{WIN_LOCAL_APP_DATA}\{ns}\bin` |
| Update A/B slots (`design/11` section 5) | `slots_dir` | `{XDG_DATA_HOME}/{ns}/slots` (`{a,b}` + `current` symlink) | `{APPLE_APP_SUPPORT}/{ns}/slots` (`{a,b}` + `current` symlink) | `{WIN_LOCAL_APP_DATA}\{ns}\slots` (`{a,b}` + `current` pointer file) |
| User CLI launcher dir (`#1660` R1/R3) | `user_bin_dir` | `{HOME}/.local/bin` | *(none; CLI invokes `{programs_dir}`)* | *(none; CLI invokes `{programs_dir}`)* |
| User profile config (`design/11` section 5) | `config_dir` | `{XDG_CONFIG_HOME}/{ns}` (`config.toml`, `install.toml`, `config.d/`) | `{APPLE_APP_SUPPORT}/{ns}/config` (`config.toml`, `install.toml`, `config.d/`) | `{WIN_LOCAL_APP_DATA}\{ns}\config` (`config.toml`, `install.toml`, `config.d/`) |
| State directory (`design/11` section 5, Constraint 2a) | `state_dir` | `{XDG_STATE_HOME}/{ns}` | `{APPLE_APP_SUPPORT}/{ns}/state` | `{WIN_LOCAL_APP_DATA}\{ns}\state` |
| Engine data | `engine_data_dir` | `{XDG_STATE_HOME}/{ns}/engine` | `{APPLE_APP_SUPPORT}/{ns}/engine` | `{WIN_LOCAL_APP_DATA}\{ns}\engine` |
| Runtime endpoint dir | `runtime_dir` | `{XDG_RUNTIME_DIR}/{ns}` (**fails pre-start if `XDG_RUNTIME_DIR` unset**) | `{APPLE_APP_SUPPORT}/{ns}/run` | *(none; `{PIPE_PREFIX}` with caller SID in `endpoints`)* |
| Status snapshot file (`#150`) | `status_snapshot_path` | `{XDG_STATE_HOME}/{ns}/status.pb` | `{APPLE_APP_SUPPORT}/{ns}/state/status.pb` | `{WIN_LOCAL_APP_DATA}\{ns}\state\status.pb` |
| Read-only bundle dir (`#1538`, `#1862`, `lead-release`) | `bundle_dir` | `{XDG_DATA_HOME}/{ns}/bundle` (defaults to `~/.local/share/{ns}/bundle`) | `{APPLE_APP_SUPPORT}/{ns}/bundle` (`~/Library/Application Support/{ns}/bundle`) | `{WIN_LOCAL_APP_DATA}\{ns}\bundle` (`%LOCALAPPDATA%\{ns}\bundle`) |
| Hook shim & fail-safe dir (`#1673` R6, `design/07` section 5) | `shim_dir` | `{XDG_DATA_HOME}/{ns}/current/bin` | `{APPLE_APP_SUPPORT}/{ns}/current/bin` | `{WIN_LOCAL_APP_DATA}\{ns}\bin` |

**Note on Windows `bin` vs `current` pointer file:** Because Windows uses a plain-text `current` pointer file rather than a filesystem symlink (`design/11` section 5), `bin` on Windows (`{WIN_PROGRAM_FILES}\{brand}\bin` in `Protected`; `{WIN_LOCAL_APP_DATA}\{ns}\bin` in `User`) provides a fixed invocation directory for `grdr-hook` and the CLI beside the 4 published fail-safe table files (`design/07` section 5), while daemon, engine, and worker binaries reside in `slots\{a,b}` resolved via `current`.

### 6. `accounts` section (`accounts.proto`)

`AccountsConfig` declares optional string fields `daemon = 1`, `engine = 2`, `uplink = 3`, and `proxy = 4` (all carrying `DATA_CLASS_STRUCTURAL`, `(security) = true`, `(env_ok) = false`, `(stability) = STABILITY_CLASS_EXPERIMENTAL`):

| Role (`AccountsConfig` field) | Linux (`Protected`) | macOS (`Protected`) | Windows (`Protected`) | Any OS (`User`) |
|---|---|---|---|---|
| `daemon` | `root` | `root` | `LocalSystem` | *(unset; caller's own UID/SID)* |
| `engine` | `{ns}-engine` (`grdr-engine`) | `_{ns}-engine` (`_grdr-engine`) | `NT SERVICE\{ns}-engine` | *(unset; caller's own UID/SID)* |
| `uplink` | `{ns}-uplink` (`grdr-uplink`) | `_{ns}-uplink` (`_grdr-uplink`) | `NT SERVICE\{ns}-uplink` | *(unset; caller's own UID/SID)* |
| `proxy` | `{ns}-proxy` (`grdr-proxy`) | `_{ns}-proxy` (`_grdr-proxy`) | `NT SERVICE\{ns}-proxy` | *(unset; caller's own UID/SID)* |

In `Protected`, `root` and `LocalSystem` are fixed OS system principals, while the `{ns}` prefix comes from `brand/brand.toml` `[identity].namespace` (`"grdr"` in upstream; Class B service prefix override in white-label rebuilds under `#1856`). In `User`, every account field defaults to unset (`None` in Rust), and the OS adapter binds runtime identity dynamically from the caller's process UID/SID (`#669` R7).

### 7. `endpoints` section (`endpoints.proto`)

`EndpointsConfig` carries one `EndpointBinding` field for each role (`decide = 1`, `local = 2`, `provider = 3`; using `EndpointRole` and `EndpointTransport`), and `EndpointBinding` carries `optional EndpointTransport transport = 1`, `optional BaseToken base = 2`, and `optional string template = 3` (all carrying `DATA_CLASS_STRUCTURAL`, `(security) = true`, `(env_ok) = false`, `(stability) = STABILITY_CLASS_EXPERIMENTAL`). Each resolved entry pairs with the profile's `OwnerSpec` to build `grdr_wire::peer_auth::EndpointSpec` (`RFC 0003` section 6):

| Profile | Role | Linux | macOS | Windows |
|---|---|---|---|---|
| `Protected` | `decide` | `UNIX_SOCKET` `BASE_TOKEN_ABSOLUTE`: `/run/{ns}/decide.sock` | `UNIX_SOCKET` `BASE_TOKEN_ABSOLUTE`: `/Library/Application Support/{ns}/run/decide.sock` (49 bytes) | `NAMED_PIPE` `BASE_TOKEN_PIPE_PREFIX`: `\\.\pipe\{ns}-decide` |
| `Protected` | `local` | `UNIX_SOCKET` `BASE_TOKEN_ABSOLUTE`: `/run/{ns}/local.sock` | `UNIX_SOCKET` `BASE_TOKEN_ABSOLUTE`: `/Library/Application Support/{ns}/run/local.sock` (48 bytes) | `NAMED_PIPE` `BASE_TOKEN_PIPE_PREFIX`: `\\.\pipe\{ns}-local` |
| `Protected` | `provider` | `UNIX_SOCKET` `BASE_TOKEN_ABSOLUTE`: `/run/{ns}/provider.sock` | `UNIX_SOCKET` `BASE_TOKEN_ABSOLUTE`: `/Library/Application Support/{ns}/run/provider.sock` (51 bytes) | `NAMED_PIPE` `BASE_TOKEN_PIPE_PREFIX`: `\\.\pipe\{ns}-provider` |
| `User` | `decide` | `UNIX_SOCKET` `BASE_TOKEN_XDG_RUNTIME_DIR`: `{XDG_RUNTIME_DIR}/{ns}/decide.sock` | `UNIX_SOCKET` `BASE_TOKEN_APPLE_APP_SUPPORT`: `{APPLE_APP_SUPPORT}/{ns}/run/decide.sock` | `NAMED_PIPE` `BASE_TOKEN_PIPE_PREFIX`: `\\.\pipe\{ns}-decide-<user_sid>` |
| `User` | `local` | `UNIX_SOCKET` `BASE_TOKEN_XDG_RUNTIME_DIR`: `{XDG_RUNTIME_DIR}/{ns}/local.sock` | `UNIX_SOCKET` `BASE_TOKEN_APPLE_APP_SUPPORT`: `{APPLE_APP_SUPPORT}/{ns}/run/local.sock` | `NAMED_PIPE` `BASE_TOKEN_PIPE_PREFIX`: `\\.\pipe\{ns}-local-<user_sid>` |
| `User` | `provider` | `UNIX_SOCKET` `BASE_TOKEN_XDG_RUNTIME_DIR`: `{XDG_RUNTIME_DIR}/{ns}/provider.sock` | `UNIX_SOCKET` `BASE_TOKEN_APPLE_APP_SUPPORT`: `{APPLE_APP_SUPPORT}/{ns}/run/provider.sock` | `NAMED_PIPE` `BASE_TOKEN_PIPE_PREFIX`: `\\.\pipe\{ns}-provider-<user_sid>` |

Normative endpoint rules:
1. **Brand segment:** `{ns}` is the brand-manifest segment (`[identity].namespace`, or Class B `os_slug` under `#1856`). `run`, `decide`, `local`, `provider`, `.sock`, and `\\.\pipe\` are schema constants; `<user_sid>` is caller runtime identity formatted via `Place::PipeForCaller` (`RFC 0003` section 6).
2. **`sun_path` invariant:** Every resolved Unix domain socket path MUST satisfy `bytes.len() <= 103` on macOS (104-byte `sun_path` minus NUL) and `bytes.len() <= 107` on Linux (108-byte `sun_path` minus NUL). Exceeding this limit stops endpoint startup with `GRDR-CFG-0004` before bind (`#2036`).
3. **`OwnerSpec` alignment (`RFC 0003` section 6):** `Protected` `decide` and `local` expect `OwnerSpec::Root` on Unix (`Uid(0)`) and `OwnerSpec::Sid(LocalSystem)` with `service = "{ns}"` on Windows; `User` expects `OwnerSpec::Caller` across all three roles. `Protected` `provider` expects `OwnerSpec::Root`/`LocalSystem` when bound by the daemon, or the dedicated `proxy` role principal when bound by `grdr-proxy` (`#149`). Multi-session Windows Terminal Services suffixing (`-{user_sid}-{session_id}`) remains deferred post-slice-0 (`design/11` section 13).

### 8. `packs` section (`packs.proto`)

`PacksConfig` configures pack root naming beneath `<state_dir>` (`packs_subdir`, default `"packs"` across all OSes and both profiles), the four D-37 / `design/03` section 8 / `design/22` section 6.3 channel directories, and the three `design/11` section 8 step 3 slot directories:

```protobuf
enum PackChannel {
  PACK_CHANNEL_UNSPECIFIED = 0;
  PACK_CHANNEL_BINARIES = 1 [(grdr.common.v1alpha1.wire_name) = "binaries"];
  PACK_CHANNEL_SCHEMA_POLICY = 2 [(grdr.common.v1alpha1.wire_name) = "schema-policy"];
  PACK_CHANNEL_DETECTION_CONTENT = 3 [(grdr.common.v1alpha1.wire_name) = "detection-content"];
  PACK_CHANNEL_NATIVE_AGENT_CONFIG = 4 [(grdr.common.v1alpha1.wire_name) = "native-agent-config"];
}

enum PackSlot {
  PACK_SLOT_UNSPECIFIED = 0;
  PACK_SLOT_ACTIVE = 1 [(grdr.common.v1alpha1.wire_name) = "active"];
  PACK_SLOT_LKG = 2 [(grdr.common.v1alpha1.wire_name) = "lkg"];
  PACK_SLOT_STAGED = 3 [(grdr.common.v1alpha1.wire_name) = "staged"];
}

message PacksConfig {
  optional string packs_subdir = 1 [
    (grdr.common.v1alpha1.data_class) = DATA_CLASS_STRUCTURAL,
    (grdr.common.v1alpha1.security) = true,
    (grdr.common.v1alpha1.env_ok) = false,
    (grdr.common.v1alpha1.stability) = STABILITY_CLASS_EXPERIMENTAL
  ];
}
```

Resolved pack slot layout on every OS and in both profiles is `<state_dir>/packs/<channel>/<slot>`, giving 12 fixed directories: `{binaries, schema-policy, detection-content, native-agent-config} x {active, lkg, staged}`.

### 9. Data classes (`P8`), log safety, and unknown-key reporting

1. **Schema vs runtime classification (`P8`):**
   - Every schema key, template string, `BaseToken`, `PackChannel`, `PackSlot`, and `Protected` OS path/account is `DATA_CLASS_STRUCTURAL` (`structural`).
   - Once a Layer 3 adapter resolves any user-relative `BaseToken` (`XDG_DATA_HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `XDG_RUNTIME_DIR`, `HOME`, `APPLE_APP_SUPPORT`, `WIN_LOCAL_APP_DATA`) or any user principal (`UID`, login name, Windows caller SID `<user_sid>` in pipes), the resulting concrete OS value is classified as **`identifier`** (`DataClass::Identifier`).
   - Resolved user-path wrapper types and caller principal values (`SID`, `UID`) MUST NOT implement `LogSafe` or `Display`. No log entry, health snapshot field, `status.pb` field, error message, or telemetry event may carry a resolved per-user path or user SID/UID (`#148`, `#157`, `#1610`, `#150`, `RFC 0009`).

2. **Unknown configuration keys (`design/03` section 9, `#669` R11):**
   - **Sensor behaviour:** A sensor or endpoint daemon encountering an unrecognised key ignores that key, reports it, and **continues startup without stopping**. (Server behaviour differs and stops on unknown keys per `#1035`.)
   - **Health condition (`RFC 0016` "Content, not surface"):** The implementing lead-core item adds `config-unknown-key` to `schema/health.toml` (`severity = "warn"`, `scopes = ["device"]`, `surface = "none"`, `stale = false`, `status = "active"`, `owner = "core"`), adds the three `health.config-unknown-key.{meaning,cause,fix}` tokens to `interface/strings/src/health.mf2.toml`, and regenerates `/codes/config-unknown-key`. Because severity is `warn`, no `docs/runbooks/` page is required (`RFC 0016` section 6).
   - **Error/log code:** `GRDR-CFG-0001` (`CONFIG_UNKNOWN_KEY`, `warn`, content in `schema/codes/CFG.toml`) is emitted in the daemon log carrying ONLY `LogSafe` structural fields: the unrecognised dotted key path and configuration layer name, never any key value or resolved user path.

3. **Failure modes and diagnostic codes:**
   - `GRDR-CFG-0002` (`INSTALL_MANIFEST_MISSING_OR_INVALID`, `fatal`): `install.toml` missing or unparseable -> daemon refuses to start; `grdr status` shows daemon down (`#1610` R5).
   - `GRDR-CFG-0003` (`BASE_TOKEN_UNRESOLVED`, `fatal`): required `BaseToken` unavailable (`XDG_RUNTIME_DIR` unset, missing `$HOME`, missing `%LOCALAPPDATA%`) -> startup halts before directory creation or endpoint bind, logging only the `BaseToken` wire name (plus `GRDR-PEER-0011` inside `grdr_wire::peer_auth::resolve`).
   - `GRDR-CFG-0004` (`ENDPOINT_PATH_TOO_LONG`, `fatal`): resolved socket path exceeds host `sun_path` limit (103 bytes macOS, 107 bytes Linux) -> halts before bind, logging the endpoint role key and byte limit (never the home prefix).
   - **Table completeness failure:** Missing `(OsFamily, Profile, InstallLayout)` entry in `schema/config/endpoint-defaults.toml` -> fails `cargo test` in `grdr-schema`, naming the missing tuple.

### 10. Design document sentences amended

| Document and section | Original phrasing | Amended phrasing by RFC 0021 |
|---|---|---|
| `docs/design/07` section 2 | macOS Protected socket `/var/run/grdr/decide.sock` | `/Library/Application Support/{ns}/run/{decide,local,provider}.sock` (aligning `design/07` with `RFC 0003` section 15 and `design/11` section 5) |
| `docs/design/09` section 2 | `/Applications/<product name>.app` | `/Applications/{brand}.app` (`[identity].short_name` `"Guardrails"`, aligning with `design/11` section 5) |
| `docs/design/11` section 2 & `docs/design/24` section 3 | Names `grdr-proxy` Windows service `NT SERVICE\grdr-proxy` without explicit Linux/macOS proxy accounts | Adds `{ns}-proxy` (Linux) and `_{ns}-proxy` (macOS) symmetric with `engine` and `uplink`; clarifies `{ns}` comes from `brand/brand.toml` `[identity].namespace` (Class B `os_slug` override in `#1856`) |
| `docs/design/11` section 5 | Lists 7 location rows; omits `bundle_dir` and `shim_dir`; macOS status uses `.../grdr/state/status.pb` | Adds `bundle_dir` and `shim_dir` rows across Linux, macOS, Windows x `Protected`, `User`; fixes concrete macOS `status.pb` path `/Library/Application Support/{ns}/state/status.pb`; distinguishes Windows fixed `bin` shim dir from `slots/{a,b}` + `current` pointer file |
| `docs/design/24` section 3 | Summarises Windows Protected directory generally as `C:\ProgramData\grdr\` and names `update_authority` / `enrol_file` alongside `profile`, `first_run`, `components` in `install.toml` | Aligns Windows Protected subdirectories cleanly (`\config`, `\state`, `\engine`) with `design/11` section 5, keeps `{WIN_PROGRAM_FILES}\{brand}\bin` for hooks/shims (`design/07` section 5), and scopes `Config.install` to `{profile, first_run, component_preset, components}` (`update_authority` -> `#1901`) |
| `rfcs/0006` section 2 | Option registry stops at `50004` (`FieldOptions`) and `50011` (`EnumValueOptions`) | Adds `50005` (`security`), `50006` (`env_ok`), `50007` (`stability` / `StabilityClass`) and reserves `50008` (`tier` for `#1035`); clarifies R16 per-key config stability vs package stability |

## Surfaces changed

- `proto/grdr/config/v1alpha1/{config,install,paths,accounts,endpoints,packs,defaults}.proto`: new experimental wire package `grdr.config.v1alpha1` (`Config` sections `install`, `paths`, `accounts`, `endpoints`, `packs`, and structured defaults schema).
- `proto/grdr/common/v1alpha1/options.proto`: amends [RFC 0006](./0006-grdr-common-v1alpha1-options-and-sp1-crates.md) section 2 registry (`50005` `security`, `50006` `env_ok`, `50007` `stability` + `StabilityClass`; reserves `50008` for `tier`).
- `surfaces.toml`: registers `grdr.config.v1alpha1` (`stability = "experimental"`).
- `schema/config/endpoint-defaults.toml` & `crates/grdr-schema`: adds canonical `(os, profile, layout)` default data, `BaseToken` / brand-slot descriptors, `InstallProfile` parity test, and table-completeness test.
- Registry content additions (not schema/surface changes under RFC 0007 and RFC 0016): `schema/codes/CFG.toml` (`GRDR-CFG-0001..0004`, respecting existing `GRDR-CFG-0007` in `design/03` section 6 and `GRDR-CFG-0020` in `design/24` section 3), `schema/health.toml` (`config-unknown-key`), and `interface/strings/src/health.mf2.toml`.

## Alternatives

1. **Declare `security`, `env_ok`, and `stability` inside `proto/grdr/config/v1alpha1/options.proto` instead of amending RFC 0006:**
   - *Rejected.* Directly violates `RFC 0006` `SL10` ("no descriptor options outside common `options.proto`") and fragments option extension tag management across packages. Amending RFC 0006 section 2 preserves a single collision-free option registry (`50001..50011`).
2. **Use `map<string, ...>` for per-OS defaults tables in protobuf:**
   - *Rejected.* Violates `RFC 0006` `SL07` (no `map<>` fields not named `native`) and loses closed-enum exhaustiveness over `(OsFamily, Profile)`. Repeated row messages allow compile-time completeness testing in `grdr-schema`.
3. **Store fallback default paths in `crates/grdr-schema` or OS adapter Rust code directly:**
   - *Rejected.* Violates `P14` and `design/03` section 10 ("platform paths come from per-OS tables in configuration, never hard-coded literals"). Keeping defaults in `schema/config/endpoint-defaults.toml` matching `EndpointDefaults` preserves single-source data-driven guarantees.
4. **Hard-code literal `"grdr"` without brand placeholders across OS directories, accounts, and endpoints:**
   - *Rejected.* Violates `D-66` and `design/26` section 9 for rebuilt white-label editions, causing two editions on one machine to collide on `/var/lib/grdr`, Windows services, and pipes. Separating Class A wire invariance (`grdr.*`) from Class B `{ns}` / `{brand}` placeholders avoids collisions while keeping upstream defaults literal-compatible.

## Drawbacks

- Introduces an additional TOML-to-`grdr-schema` table verification step alongside `limits.toml` and `health.toml`.
- Class B `os_slug` white-label overrides require strict build-time length and character checks (`<= 16` chars `[a-z0-9-]`) because macOS Unix sockets remain constrained by the 104-byte `sun_path` kernel structure.
- Keeping Windows `shim_dir` at a fixed `bin` directory separately from `slots/{a,b}` + `current` pointer file requires MSI/self-update slot switches to atomically update the `grdr-hook` shim and fail-safe tables together with the `current` pointer commit.

## Unresolved questions

- **Multi-session Windows pipe naming (`design/11` section 13):** Post-slice-0 multi-user Terminal Services hosts may need `-<user_sid>-<session_id>` disambiguation on `User` pipes; left additive to `BaseToken::PIPE_PREFIX` / `RFC 0003` post-slice-0 rules.
- **Downstream Class B `os_slug` field name in `brand/brand.toml` (`#1856`):** Exact TOML key name inside `#1856` is left to `lead-brand` / LBC-3, constrained only by the `^[a-z][a-z0-9-]{0,15}$` invariant when replacing `{ns}` on Class B OS surfaces.

## Review

- **RFC file:** *(HEAD blob of `rfcs/0021-endpoint-configuration-defaults.md` on `issue/669-rfc-0021-endpoint-configuration-defaults`)*
- **Proposed text:** none
- **Base:** `a80859235e7a2a4444648d6fa8d389d78dde6be9` (`docs/design/00-decisions.md`, pinned by [RFC 0001](./0001-adopt-the-spine.md) via `rfcs/pins.toml` `993f808476d52888e4a3673da9ad685e1ce55989`)

Reference blobs read while drafting:
- `read=docs/design/00-decisions.md@a80859235e7a2a4444648d6fa8d389d78dde6be9`
- `read=docs/design/03-system-architecture-and-modularity.md@1a0d2a17dddaa30f519a52a66cb6cb6d04d6b0c6`
- `read=docs/design/04-event-model-and-schemas.md@e77880a12d2f42e715836a6da9598b86f33b20b0`
- `read=docs/design/07-control-points-and-hook-broker.md@70be1d4ee42d9eebb832cc5153699121f2a64a6f`
- `read=docs/design/08-sensor-windows.md@c80403bafe81412c56c30ff9541943a3953d2c6d`
- `read=docs/design/09-sensor-macos.md@d7ca9587ab6dbe83362b478d2d73252e8e0ae4c6`
- `read=docs/design/10-sensor-linux-containers-ci.md@ea730ec54c0731b92b7defe9bb6b855883c55b06`
- `read=docs/design/11-endpoint-engineering.md@f32185d0f3da07adcb012c4551b9b60ba5d5893a`
- `read=docs/design/22-transport-fleet-and-updates.md@ccf77d0280ae78cd1efa9491a20b48c7ebdecd27`
- `read=docs/design/24-deployment-and-packaging.md@8403bec8717c6ad5fbb42fd173d5bde1b176bb23`
- `read=docs/design/26-embedding-oem-and-white-label.md@8d9327dce0ca530e065f06a8ed287dec664e1f5b`
- `read=docs/design/30-open-source-governance-and-community.md@91f909de5f9ed9aaf6db0bbeb4641db16976adda`
- `read=docs/design/34-documentation-support-and-lifecycle.md@ef630aeaf0f5d5d7f89f5241ea1a1c950c6b5c34`
- `read=docs/design/36-legal-brand-and-commercial.md@dfcb5df2a9be6f5d58719919f17e32057301da47`
- `read=rfcs/0003-grdr-wire-surface.md@d7e4c4d174e93f3ea210be650dadf6ff37c37b53`
- `read=rfcs/0006-grdr-common-v1alpha1-options-and-sp1-crates.md@be45e4321a38f753ebd61a208bb0227f866d8be1`
- `read=rfcs/0007-grdr-model-and-grdr-schema-slice-0-surface.md@0c0a6745f04888bec8ef2e718352549f47181201`
- `read=rfcs/0009-grdr-model-slice-0-surface.md@4f36df6f0b2ce122d3b09d8109e83fb4720b1c68`
- `read=rfcs/0016-health-condition-registry.md@a05ed5df0e912fa258cb12cbf6b1e606ce38f6f5`
- `read=brand/brand.toml@a32c7cfbf0c9197a8464581483546e74f08c545b`
- `read=surfaces.toml@2c000f6b76e08117a3551251c28f3081f8991b1e`
- `read=architecture.toml@60743ee6b3f532190237a499b236784bf3587e04`

### Planned on acceptance (`#669` R12)

Once this RFC reaches `Accepted` (do not file during Phase 1 `Review`):
1. **Lead-core implementation item** (`proto/grdr/config/v1alpha1/**`, `schema/config/endpoint-defaults.toml`, `crates/grdr-schema` defaults + `InstallProfile` parity test + `(os, profile, layout)` completeness test, `schema/codes/CFG.toml`, `schema/health.toml` `config-unknown-key`, `interface/strings/src/health.mf2.toml`), citing RFC 0021; re-point `#148`, `#157`, and `#1610` `blockedBy` from `#669` to that item (and update `#1538`, `#1862`, `#149`, `#1660`, `#150`, `#1673` as needed).
2. **Option registry & surface registration** (`proto/grdr/common/v1alpha1/options.proto` RFC 0006 amendment and `surfaces.toml` registration for `grdr.config.v1alpha1`) under high-tier governance.
3. **Design document write-backs** per section 10 table (`docs/design/07`, `docs/design/09`, `docs/design/11`, `docs/design/24`, `rfcs/0006`).

## Decision

Pending review on #669: persona council seat comments, `eval-architecture`, an evaluator on the second model/provider (`D-63`), and the chief architect's decision with written reasons (`design/30` section 3).
