import json
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import boundedproc
import secretsvc
from httpd import _valid_json_shape

INSTALLER_SPEC = importlib.util.spec_from_file_location(
    "fleet_install_transaction", os.path.join(ROOT, "scripts", "install_transaction.py"))
installer = importlib.util.module_from_spec(INSTALLER_SPEC)
sys.modules[INSTALLER_SPEC.name] = installer
INSTALLER_SPEC.loader.exec_module(installer)


class SecurityBoundsTests(unittest.TestCase):
    def fixture_repo(self, home):
        source = Path(ROOT)
        repo = Path(home) / "source" / "Fleet"
        repo.mkdir(parents=True)
        for name in ("fleet.py", "README.md", "CHANGELOG.md", "VERSION"):
            shutil.copy2(source / name, repo / name)
        for name in ("server", "web", "tests", "bin", "share"):
            shutil.copytree(
                source / name,
                repo / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
        hypr = Path(home) / ".config" / "hypr"
        hypr.mkdir(parents=True)
        (hypr / "bindings.lua").write_text("-- personal bindings\n", encoding="utf-8")
        (hypr / "hyprland.lua").write_text("-- personal windows\n", encoding="utf-8")
        return repo, hypr

    def home_env(self, home):
        env = mock.patch.dict(os.environ, {"HOME": home})
        env.start()
        for name in ("XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CONFIG_HOME"):
            os.environ.pop(name, None)
        self.addCleanup(env.stop)

    def test_subprocess_output_is_truncated_while_drained(self):
        p = boundedproc.run(
            [sys.executable, "-c", "import sys;sys.stdout.write('x'*200000)"],
            timeout=3, stdout_limit=1024, stderr_limit=1024)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(len(p.stdout), 1024)
        self.assertTrue(p.stdout_truncated)

    def test_subprocess_timeout_is_hard_bounded(self):
        p = boundedproc.run([sys.executable, "-c", "import time;time.sleep(5)"],
                            timeout=1, stdout_limit=1024, stderr_limit=1024)
        self.assertEqual(p.returncode, 124)
        self.assertTrue(p.timed_out)

    def test_descendant_cannot_hold_capture_pipe_forever(self):
        started = time.monotonic()
        p = boundedproc.run(["/bin/sh", "-c", "(sleep 20) & exit 0"], timeout=1,
                            stdout_limit=1024, stderr_limit=1024)
        self.assertLess(time.monotonic() - started, 3)
        self.assertTrue(p.timed_out)

    def test_json_shape_rejects_excess_cardinality_and_depth(self):
        self.assertFalse(_valid_json_shape({str(i): i for i in range(129)}))
        deep = {}
        cursor = deep
        for _ in range(14):
            cursor["x"] = {}
            cursor = cursor["x"]
        self.assertFalse(_valid_json_shape(deep))

    def test_bar_helper_output_is_small_valid_json(self):
        raw = subprocess.check_output([os.path.join(ROOT, "bin", "fleet-bar-status")],
                                      timeout=6)
        self.assertLessEqual(len(raw), 64 * 1024)
        self.assertIsInstance(json.loads(raw), dict)

    def test_bar_helper_discards_oversized_command_output(self):
        with tempfile.TemporaryDirectory() as home:
            bindir = os.path.join(home, ".local", "bin")
            os.makedirs(bindir)
            fake = os.path.join(bindir, "fleet")
            with open(fake, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\nhead -c 100000 /dev/zero\n")
            os.chmod(fake, 0o700)
            raw = subprocess.check_output(
                [os.path.join(ROOT, "bin", "fleet-bar-status")],
                env=os.environ | {"HOME": home}, timeout=6)
            payload = json.loads(raw)
            self.assertEqual(payload["state"], "error")
            self.assertLessEqual(len(raw), 64 * 1024)

    def test_credentials_fail_closed_without_secret_service(self):
        with mock.patch.object(secretsvc, "_have_secret_tool", False), \
             mock.patch.object(secretsvc, "_KEYRING", None):
            self.assertIsNone(secretsvc.get_secret("pw:test"))
            with self.assertRaises(secretsvc.SecretBackendUnavailable):
                secretsvc.set_secret("pw:test", "secret")

    def test_installer_round_trip_is_transactional(self):
        with tempfile.TemporaryDirectory() as home:
            self.home_env(home)
            repo, hypr = self.fixture_repo(home)
            before_binding = (hypr / "bindings.lua").read_bytes()
            before_window = (hypr / "hyprland.lua").read_bytes()

            transaction = installer.apply(repo, True, True)
            launcher = Path(home) / ".local" / "bin" / "fleet"
            self.assertEqual(launcher.read_bytes(), (repo / "bin" / "fleet").read_bytes())
            self.assertIn(installer.BEGIN_BINDING, (hypr / "bindings.lua").read_text())
            self.assertIn(installer.BEGIN_WINDOW, (hypr / "hyprland.lua").read_text())

            installer.rollback(transaction)
            self.assertFalse(launcher.exists())
            self.assertEqual((hypr / "bindings.lua").read_bytes(), before_binding)
            self.assertEqual((hypr / "hyprland.lua").read_bytes(), before_window)

    def test_installer_fifo_fails_before_blocking_read(self):
        with tempfile.TemporaryDirectory() as home:
            self.home_env(home)
            repo, hypr = self.fixture_repo(home)
            target = hypr / "bindings.lua"
            target.unlink()
            os.mkfifo(target, 0o600)
            started = time.monotonic()
            with self.assertRaisesRegex(installer.SafetyError, "not a regular file"):
                installer.build_operations(repo, True, True)
            self.assertLess(time.monotonic() - started, 1)
            self.assertTrue(stat.S_ISFIFO(os.lstat(target).st_mode))

    def test_installer_recovers_kill_after_first_replace(self):
        with tempfile.TemporaryDirectory() as home:
            self.home_env(home)
            repo, hypr = self.fixture_repo(home)
            before_binding = (hypr / "bindings.lua").read_bytes()
            before_window = (hypr / "hyprland.lua").read_bytes()
            pid = os.fork()
            if pid == 0:
                real_replace = installer.atomic_replace

                def replace_then_die(*args, **kwargs):
                    real_replace(*args, **kwargs)
                    os._exit(91)

                installer.atomic_replace = replace_then_die
                installer.apply(repo, True, True)
                os._exit(92)
            unused, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 91)

            tx_root = Path(home) / ".local" / "state" / "fleet" / "installer" / "transactions"
            transactions = list(tx_root.iterdir())
            self.assertEqual(len(transactions), 1)
            journal = json.loads((transactions[0] / "journal.json").read_text())
            self.assertEqual(journal["state"], "applying")
            self.assertTrue(journal["changes"])
            self.assertTrue(all(change["status"] in ("prepared", "applying")
                                for change in journal["changes"]))

            installer.recover_pending()
            self.assertEqual((hypr / "bindings.lua").read_bytes(), before_binding)
            self.assertEqual((hypr / "hyprland.lua").read_bytes(), before_window)
            self.assertFalse((Path(home) / ".local" / "bin" / "fleet").exists())

    def test_installer_migrates_and_uninstalls_exact_legacy_blocks(self):
        with tempfile.TemporaryDirectory() as home:
            self.home_env(home)
            repo, hypr = self.fixture_repo(home)
            binding_keep = "-- before\n"
            window_keep = "-- unrelated rule\n"
            (hypr / "bindings.lua").write_text(
                binding_keep + "\n" + installer.LEGACY_BINDING + "\n-- after\n",
                encoding="utf-8",
            )
            (hypr / "hyprland.lua").write_text(
                window_keep + "\n" + installer.LEGACY_WINDOW + "\n-- after\n",
                encoding="utf-8",
            )

            installer.apply(repo, True, True)
            bindings = (hypr / "bindings.lua").read_text(encoding="utf-8")
            windows = (hypr / "hyprland.lua").read_text(encoding="utf-8")
            self.assertNotIn(installer.LEGACY_BINDING, bindings)
            self.assertNotIn(installer.LEGACY_WINDOW, windows)
            self.assertEqual(bindings.count(installer.BEGIN_BINDING), 1)
            self.assertEqual(windows.count(installer.BEGIN_WINDOW), 1)

            installer.apply(repo, False, False)
            bindings = (hypr / "bindings.lua").read_text(encoding="utf-8")
            windows = (hypr / "hyprland.lua").read_text(encoding="utf-8")
            self.assertIn(binding_keep.strip(), bindings)
            self.assertIn(window_keep.strip(), windows)
            self.assertIn("-- after", bindings)
            self.assertIn("-- after", windows)
            self.assertNotIn("io.github.niraj-envision.fleet", bindings + windows)
            self.assertFalse((Path(home) / ".local" / "share" / "fleet" / "fleet.py").exists())

    def test_installer_refuses_concurrent_edit_during_rollback(self):
        with tempfile.TemporaryDirectory() as home:
            self.home_env(home)
            repo, unused = self.fixture_repo(home)
            transaction = installer.apply(repo, True, False)
            launcher = Path(home) / ".local" / "bin" / "fleet"
            launcher.write_text("#!/bin/sh\necho user edit\n", encoding="utf-8")
            launcher.chmod(0o755)

            with self.assertRaisesRegex(installer.SafetyError, "changed; refusing rollback"):
                installer.rollback(transaction)
            self.assertIn("user edit", launcher.read_text(encoding="utf-8"))

    def test_live_upgrade_stops_fleet_and_accepts_runtime_self_cleanup(self):
        with tempfile.TemporaryDirectory() as home:
            self.home_env(home)
            repo, unused = self.fixture_repo(home)
            installer.apply(repo, True, False)
            app = Path(home) / ".local" / "share" / "fleet" / "fleet.py"
            runtime = Path(home) / ".local" / "state" / "fleet" / "runtime.json"
            process = subprocess.Popen(
                [str(app), "--no-open", "--no-connect"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                deadline = time.monotonic() + 5
                while not runtime.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                if not runtime.exists():
                    output, unused = process.communicate(timeout=2)
                    self.fail("Fleet did not start for live-upgrade test:\n" + output)

                transaction = installer.apply(repo, True, False)
                self.assertTrue((transaction / "journal.json").is_file())
                output, unused = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0, output)
                self.assertFalse(runtime.exists())
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.communicate(timeout=5)
                elif process.stdout is not None and not process.stdout.closed:
                    process.stdout.close()


if __name__ == "__main__":
    unittest.main()
