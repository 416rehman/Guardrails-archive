# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: The Guardrails ADR Authors
"""Unit and R4/R5 oracle tests for .github/install-smoke/."""

import os
import pathlib
import re
import sys
import tempfile
import unittest
import unittest.mock

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import claude_settings
import runner_exec
import smoke
import snapshot

SEEDED_BYTES = (HERE / "fixtures" / "claude-settings.json").read_bytes()


class RootsConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = snapshot.load_roots_config(HERE / "roots.toml")

    def test_required_os_profiles_and_roots_present(self) -> None:
        for os_key in ("linux", "macos", "windows"):
            for prof in ("user", "protected"):
                table = self.cfg["os"][os_key][prof]
                self.assertTrue(table["scan_roots"])
                self.assertTrue(table["ours"])
                self.assertIn("~/.claude", table["scan_roots"])
        self.assertIn("/etc", self.cfg["os"]["linux"]["user"]["scan_roots"])
        self.assertIn("/usr", self.cfg["os"]["linux"]["user"]["scan_roots"])
        self.assertIn("/var/lib", self.cfg["os"]["linux"]["user"]["scan_roots"])
        self.assertIn("/Library", self.cfg["os"]["macos"]["user"]["scan_roots"])
        self.assertIn("%ProgramFiles%", self.cfg["os"]["windows"]["user"]["scan_roots"])
        self.assertIn("%ProgramData%", self.cfg["os"]["windows"]["user"]["scan_roots"])
        self.assertIn("%LOCALAPPDATA%", self.cfg["os"]["windows"]["user"]["scan_roots"])
        self.assertEqual(self.cfg["os"]["windows"]["windows_registry"], ["HKCU\\Software", "HKLM\\SOFTWARE"])
        self.assertTrue(self.cfg["os"]["windows"]["windows_tasks"])
        self.assertTrue(self.cfg["os"]["windows"]["windows_services"])

    def test_ours_path_boundary_enforcement(self) -> None:
        env = {"HOME": "/home/alice", "USERPROFILE": "C:\\Users\\alice", "LOCALAPPDATA": "C:\\Users\\alice\\AppData\\Local"}
        linux_ours = snapshot.ours_patterns(self.cfg, snapshot.OsName.LINUX, snapshot.Profile.USER, env)
        self.assertTrue(snapshot.is_under_ours("/home/alice/.local/share/grdr/bin/grdr-hook", linux_ours, snapshot.OsName.LINUX))
        self.assertFalse(snapshot.is_under_ours("/home/alice/.local/share/grdr-evil/bin/grdr-hook", linux_ours, snapshot.OsName.LINUX))
        self.assertFalse(snapshot.is_under_ours("/home/alice/.config/other-file", linux_ours, snapshot.OsName.LINUX))

        win_ours = snapshot.ours_patterns(self.cfg, snapshot.OsName.WINDOWS, snapshot.Profile.USER, env)
        self.assertTrue(snapshot.is_under_ours("reg://HKCU/Software/grdr::version", win_ours, snapshot.OsName.WINDOWS))
        self.assertFalse(snapshot.is_under_ours("reg://HKCU/Software/grdr-evil::version", win_ours, snapshot.OsName.WINDOWS))
        self.assertTrue(snapshot.is_under_ours("task://\\grdr-daemon", win_ours, snapshot.OsName.WINDOWS))
        self.assertFalse(snapshot.is_under_ours("task://\\other\\grdr-daemon", win_ours, snapshot.OsName.WINDOWS))


class PlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = snapshot.load_roots_config(HERE / "roots.toml")

    def test_missing_smoke_toml_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cells = smoke.load_cells(pathlib.Path(tmp) / "smoke.toml", self.cfg, missing_ok=True)
            self.assertEqual(cells, [])

    def test_missing_key_fails_naming_cell_and_key(self) -> None:
        base = (
            '[[cell]]\nid = "linux-x64"\nrunner = "ubuntu-26.04"\nprofile = "user"\n'
            'build = "deploy/archive/build.sh"\ninstall = "install.sh"\n'
            'choose = "choose.sh"\nuninstall = "uninstall.sh"\n'
        )
        for key in smoke.REQUIRED_CELL_KEYS:
            lines = [ln for ln in base.splitlines() if not ln.startswith(f"{key} =")]
            with tempfile.TemporaryDirectory() as tmp:
                path = pathlib.Path(tmp) / "smoke.toml"
                path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                with self.assertRaises(snapshot.OracleError) as ctx:
                    smoke.load_cells(path, self.cfg, missing_ok=False)
                self.assertIn(key, str(ctx.exception))
                if key != "id":
                    self.assertIn("linux-x64", str(ctx.exception))

    def test_rejects_build_outside_deploy_and_traversal(self) -> None:
        for bad in ("scripts/build.sh", "deploy/../evil.sh", "bash deploy/a.sh\necho hi"):
            text = (
                '[[cell]]\nid = "c1"\nrunner = "ubuntu-26.04"\nprofile = "user"\n'
                f'build = """{bad}"""\ninstall = "i"\nchoose = "c"\nuninstall = "u"\n'
            )
            with tempfile.TemporaryDirectory() as tmp:
                path = pathlib.Path(tmp) / "smoke.toml"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(snapshot.OracleError):
                    smoke.load_cells(path, self.cfg, missing_ok=False)

    def test_unit_lint_missing_tool_never_skips(self) -> None:
        with unittest.mock.patch.object(smoke.shutil, "which", return_value=None):
            ns = smoke.argparse.Namespace(roots=HERE / "roots.toml", os="linux", github_output=None)
            with self.assertRaises(snapshot.OracleError) as ctx:
                smoke.cmd_unit_lint(ns)
            self.assertIn("systemd-analyze", str(ctx.exception))


class ClaudeSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.patterns = ["/home/alice/.local/share/grdr"]
        self.seeded = SEEDED_BYTES

    def test_preserving_append_and_new_event_pass(self) -> None:
        text = self.seeded.decode("utf-8")
        entry = (
            '      {\n'
            '        "matcher": "*",\n'
            '        "hooks": [\n'
            '          {\n'
            '            "type": "command",\n'
            '            "command": "/home/alice/.local/share/grdr/bin/grdr-hook --agent claude-code --event PreToolUse",\n'
            '            "timeout": 5\n'
            '          }\n'
            '        ]\n'
            '      }'
        )
        updated = text.replace("      }\n    ]", f"      }},\n{entry}\n    ]", 1)
        updated = updated.replace(
            "\n  },\n",
            ',\n    "PermissionRequest": [\n' + entry.replace("PreToolUse", "PermissionRequest") + "\n    ]\n  },\n",
            1,
        )
        count, errs = claude_settings.verify_user_claude_settings(
            self.seeded, updated.encode("utf-8"), self.patterns, snapshot.OsName.LINUX
        )
        self.assertEqual(errs, [])
        self.assertEqual(count, 2)

    def test_two_leading_ours_entries_pass(self) -> None:
        text = self.seeded.decode("utf-8")
        e1 = '      {"matcher": "*", "hooks": [{"type": "command", "command": "/home/alice/.local/share/grdr/bin/grdr-hook --a"}]}'
        e2 = '      {"matcher": "*", "hooks": [{"type": "command", "command": "/home/alice/.local/share/grdr/bin/grdr-hook --b"}]}'
        updated = text.replace('"PreToolUse": [\n', f'"PreToolUse": [\n{e1},\n{e2},\n', 1)
        count, errs = claude_settings.verify_user_claude_settings(
            self.seeded, updated.encode("utf-8"), self.patterns, snapshot.OsName.LINUX
        )
        self.assertEqual(errs, [])
        self.assertEqual(count, 2)

    def test_single_byte_vendor_mutation_rejected(self) -> None:
        text = self.seeded.decode("utf-8").replace('"timeout": 10', '"timeout": 11', 1)
        e1 = '      {"matcher": "*", "hooks": [{"type": "command", "command": "/home/alice/.local/share/grdr/bin/grdr-hook"}]}'
        updated = text.replace("      }\n    ]", f"      }},\n{e1}\n    ]", 1)
        _, errs = claude_settings.verify_user_claude_settings(
            self.seeded, updated.encode("utf-8"), self.patterns, snapshot.OsName.LINUX
        )
        self.assertNotEqual(errs, [])

    def test_command_outside_ours_or_shell_meta_rejected(self) -> None:
        text = self.seeded.decode("utf-8")
        for bad_cmd in (
            "/tmp/evil-hook",
            "grdr-hook --relative",
            "/home/alice/.local/share/grdr/../evil",
            "/home/alice/.local/share/grdr/bin/grdr-hook; echo pwn",
        ):
            e1 = f'      {{"matcher": "*", "hooks": [{{"type": "command", "command": "{bad_cmd}"}}]}}'
            updated = text.replace("      }\n    ]", f"      }},\n{e1}\n    ]", 1)
            _, errs = claude_settings.verify_user_claude_settings(
                self.seeded, updated.encode("utf-8"), self.patterns, snapshot.OsName.LINUX
            )
            self.assertNotEqual(errs, [], bad_cmd)

    def test_diff_never_prints_file_contents(self) -> None:
        marker = "UNIQUE_CONTENT_MARKER_DO_NOT_PRINT"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "cfg"
            root.mkdir()
            target = root / "secret.json"
            target.write_text(marker, encoding="utf-8")
            cfg = snapshot.load_roots_config(HERE / "roots.toml")
            s0 = snapshot.capture_snapshot(cfg, snapshot.detect_host_os(), snapshot.Profile.USER, override_roots=[str(root)])
            target.write_text(marker + "_CHANGED", encoding="utf-8")
            s1 = snapshot.capture_snapshot(cfg, snapshot.detect_host_os(), snapshot.Profile.USER, override_roots=[str(root)])
            lines = "\n".join(snapshot.format_diff(snapshot.diff_snapshots(s0, s1)))
        self.assertNotIn(marker, lines)
        self.assertIn(str(target), lines)

    def test_protected_dropin_passes_with_untouched_user_settings(self) -> None:
        cfg = snapshot.load_roots_config(HERE / "roots.toml")
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            home = root / "home"
            dropin_dir = root / "etc" / "claude-code" / "managed-settings.d"
            user_file = home / ".claude" / "settings.json"
            user_file.parent.mkdir(parents=True)
            user_file.write_bytes(self.seeded)

            fake_cfg = {
                **cfg,
                "os": {
                    **cfg["os"],
                    "linux": {
                        **cfg["os"]["linux"],
                        "claude_dropin_dir": str(dropin_dir).replace("\\", "/"),
                    },
                },
            }
            env = {"HOME": str(home).replace("\\", "/")}
            s1 = {
                user_file.as_posix(): snapshot.SnapshotEntry(
                    user_file.as_posix(), snapshot.EntryKind.FILE, "0600", "1000:1000", snapshot.sha256_bytes(self.seeded)
                )
            }
            dropin_dir.mkdir(parents=True)
            dropin_file = dropin_dir / "50-grdr.json"
            dropin_bytes = (
                b'{"hooks":{"PreToolUse":[{"matcher":"*","hooks":[{"type":"command",'
                b'"command":"/usr/libexec/grdr/grdr-hook --agent claude-code --event PreToolUse"}]}]}}'
            )
            dropin_file.write_bytes(dropin_bytes)
            s_choose = {
                **s1,
                dropin_dir.as_posix(): snapshot.SnapshotEntry(dropin_dir.as_posix(), snapshot.EntryKind.DIR, "0755", "0:0", ""),
                dropin_file.as_posix(): snapshot.SnapshotEntry(
                    dropin_file.as_posix(), snapshot.EntryKind.FILE, "0644", "0:0", snapshot.sha256_bytes(dropin_bytes)
                ),
            }
            errs = claude_settings.verify_choose_changes(
                s1, s_choose, fake_cfg, snapshot.OsName.LINUX, snapshot.Profile.PROTECTED, self.seeded, env
            )
            self.assertEqual(errs, [])


class R4AndR5LocalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = snapshot.load_roots_config(HERE / "roots.toml")
        self.os_name = snapshot.detect_host_os()
        self.runner = next(r for r, o in self.cfg["runners"].items() if o == self.os_name.value)

    def _run_fixture(self, cell_id: str) -> smoke.CellOutcome:
        cmd = f"python3 -I -B .github/install-smoke/fixtures/fixture_cell.py {cell_id}"
        cell = smoke.CellSpec(
            id=cell_id,
            runner=self.runner,
            profile=snapshot.Profile.USER,
            build=f"{cmd} build",
            install=f"{cmd} install",
            choose=f"{cmd} choose",
            uninstall=f"{cmd} uninstall",
        )
        orig_run = smoke.run_step_command

        def local_run(command, os_name, profile, env, cwd, timeout_seconds, *, elevated=False):
            if elevated and ((os.name == "nt" and not runner_exec.is_windows_elevated()) or (os.name != "nt" and os.geteuid() != 0)):
                return runner_exec.CommandResult(1, "", "simulated elevated refusal")
            return orig_run(command, os_name, profile, env, cwd, timeout_seconds, elevated=elevated)

        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp) / "home"
            home.mkdir()
            env = smoke.isolated_env(home, os.environ)
            user_roots = [
                snapshot.expand_path("~/.claude", self.os_name, env),
                snapshot.expand_path("~/.config", self.os_name, env),
                snapshot.expand_path("~/.local/share", self.os_name, env),
                snapshot.expand_path("~/.local/state", self.os_name, env),
                snapshot.expand_path("~/.local/bin", self.os_name, env),
            ]
            if self.os_name == snapshot.OsName.WINDOWS:
                user_roots.append(snapshot.expand_path("%LOCALAPPDATA%", self.os_name, env))

            def fast_capture(cfg, os_n, prof, run_env=None, override_roots=None):
                return snapshot.capture_snapshot(cfg, os_n, prof, run_env, override_roots=user_roots)

            with (
                unittest.mock.patch.object(smoke, "capture_snapshot", fast_capture),
                unittest.mock.patch.object(smoke, "run_step_command", local_run),
            ):
                return smoke.run_r4_cell(cell, self.cfg, ROOT, env)

    def test_clean_fixture_passes_all_steps(self) -> None:
        outcome = self._run_fixture("clean")
        self.assertIsInstance(outcome, smoke.CellPassed, outcome.step_log)

    def test_seeded_fixture_cells_fail_at_expected_steps(self) -> None:
        expected = {
            "writes-outside-ours": smoke.StepName.INSTALL,
            "leaves-file-behind": smoke.StepName.UNINSTALL,
            "mutates-vendor-hook": smoke.StepName.CHOOSE,
        }
        cells = smoke.load_cells(HERE / "fixtures" / "cells.toml", self.cfg, missing_ok=False, allow_fixture_prefix=True)
        self.assertEqual({c.id for c in cells}, set(expected))
        for cell_id, step in expected.items():
            with self.subTest(cell=cell_id):
                outcome = self._run_fixture(cell_id)
                if not isinstance(outcome, smoke.CellFailed):
                    self.fail(f"{cell_id}: expected CellFailed, got {outcome}")
                self.assertEqual(outcome.failed_step, step, outcome.step_log)

    def test_fixtures_contain_no_token_shaped_strings(self) -> None:
        token_re = re.compile(
            r"(?:gh[pousr]_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9-]{16,}|xox[baprs]-[A-Za-z0-9-]+|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]+ KEY)"
        )
        for path in sorted((HERE / "fixtures").rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(token_re.search(text), f"token-shaped string in {path}")


if __name__ == "__main__":
    unittest.main()
