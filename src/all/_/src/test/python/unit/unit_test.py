import contextlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from os.path import dirname, join, realpath

ROOT = realpath(join(dirname(__file__), "../../../../../.."))
BASH = "/opt/homebrew/bin/bash" if os.path.exists("/opt/homebrew/bin/bash") else "bash"
GNU = {"find": "gfind", "date": "gdate"}


class GenerateRulesTest(unittest.TestCase):
    def module(self, restore, backup):
        base = tempfile.mkdtemp()
        root = join(base, "mod")
        os.makedirs(join(root, "src/build/resources"))
        os.makedirs(join(root, "src/build/python/mod"))
        with open(join(root, "src/build/resources/restore.sh"), "w") as handle:
            handle.write(restore)
        with open(join(root, "src/build/resources/backup.sh"), "w") as handle:
            handle.write(backup)
        return root

    def generate(self, root):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        from asystem import container

        original = sys.argv[0]
        sys.argv[0] = join(root, "src/build/python/mod/generate.py")
        try:
            container.write_container_restore(module_name="mod", working_dir=join(root, "out"))
        finally:
            sys.argv[0] = original

    def snippet(self):
        from asystem import container

        return container.RESTORE_CONTRACT + "\n\nrestore_merged() { :; }\n"

    def generated_backup(self, body):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        from asystem import container

        base = tempfile.mkdtemp()
        root = join(base, "mod")
        os.makedirs(join(root, "src/build/resources"))
        os.makedirs(join(root, "src/build/python/mod"))
        with open(join(root, "src/build/resources/backup.sh"), "w") as handle:
            handle.write(container.BACKUP_CONTRACT + "\n\n" + body)
        original = sys.argv[0]
        sys.argv[0] = join(root, "src/build/python/mod/generate.py")
        try:
            container.write_container_backup(module_name="mod", working_dir=join(root, "out"))
        finally:
            sys.argv[0] = original
        return root

    def run_generated(self, root, *args, **extra):
        bin_dir = join(root, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        for name, target in GNU.items():
            found = subprocess.run(["which", target], capture_output=True, text=True).stdout.strip()
            if found and not os.path.exists(join(bin_dir, name)):
                os.symlink(found, join(bin_dir, name))
        os.makedirs(join(root, "data", "latest"), exist_ok=True)
        environment = dict(os.environ, PATH=bin_dir + ":" + os.environ["PATH"], BACKUP_SOURCE_PATH=join(root, "data", "latest"), **extra)
        return subprocess.run([BASH, join(root, "out", "backup.sh"), *args], capture_output=True, text=True, env=environment)

    def test_the_generated_backup_script_hands_the_run_to_the_engine_and_keeps_only_hooks(self):
        root = self.generated_backup('backup_written() { echo "full=${BACKUP_FORCE_FULL} skip=${BACKUP_SKIP_HOURS}"; }\n')
        script = join(root, "out", "backup.sh")
        with open(script) as handle:
            text = handle.read()
        self.assertIn("backup_supervised run", text)
        for retired in (r"backup_pruned\b", r"backup_pruned_gfs", "backup_gfs_kept", "backup_kept_next", "Prune disagreement", "backup_manifested", "backup_regression"):
            self.assertIsNone(re.search(retired, text), retired)
        os.makedirs(join(root, "data", "latest"), exist_ok=True)
        environment = dict(os.environ, BACKUP_SOURCE_PATH=join(root, "data", "latest"), BACKUP_FORCE_FULL="true", BACKUP_SKIP_HOURS="0")
        done = subprocess.run([BASH, "-c", f'source "{script}"; backup_written; type -t backup_target backup_files backup_parent backup_epoch'], capture_output=True, text=True, env=environment)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split("\n")[:5], ["full=true skip=0", "function", "function", "function", "function"])

    def test_the_generated_restore_script_hands_the_run_to_the_engine_and_keeps_only_hooks(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        root = self.module(self.snippet().replace("restore_merged() { :; }", "restore_applied() { :; }"), "backup_written() { :; }\n")
        self.generate(root)
        script = join(root, "out", "restore.sh")
        with open(script) as handle:
            text = handle.read()
        self.assertIn("restore_supervised", text)
        for retired in ("restore_chain_resolved", "restore_drilled", "restore_merge\\b", "asystem_locked", "backup_fingerprinted_default"):
            self.assertIsNone(re.search(retired, text), retired)
        environment = dict(os.environ, RESTORE_CHAIN_LIST="/a\n/b", RESTORE_SOURCE_PATH=join(root, "data"))
        os.makedirs(join(root, "data"), exist_ok=True)
        done = subprocess.run(
            [BASH, "-c", f'source "{script}"; echo "${{RESTORE_SOURCE_FILE}} ${{#RESTORE_CHAIN_FILES[@]}}"; type -t restore_files restore_service_state'],
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split("\n")[:3], ["/b 2", "function", "function"])

    def test_a_module_defining_restore_merged_without_deltas_fails_generate(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        root = self.module(self.snippet(), "backup_written() { :; }\n")
        with self.assertRaises(ValueError) as caught:
            self.generate(root)
        self.assertIn("emits no deltas", str(caught.exception))

    def test_a_module_defining_restore_merged_with_deltas_generates(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        root = self.module(self.snippet(), 'backup_target "${BACKUP_DELTA_SUFFIX}" tar.gz\n')
        self.generate(root)
        self.assertTrue(os.path.exists(join(root, "out", "restore.sh")))


class GenerateRestartTest(unittest.TestCase):
    def generated(self, body, env="", contract=None):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        from asystem import container

        base = tempfile.mkdtemp()
        root = join(base, "mod-x")
        os.makedirs(join(root, "src/build/resources"))
        os.makedirs(join(root, "src/build/python/mod"))
        with open(join(root, "src/build/resources/restart.sh"), "w") as handle:
            handle.write((container.RESTART_CONTRACT if contract is None else contract) + "\n\n" + body)
        out = join(root, "out")
        original = sys.argv[0]
        sys.argv[0] = join(root, "src/build/python/mod/generate.py")
        try:
            container.write_container_restart(module_name="mod-x", working_dir=out)
        finally:
            sys.argv[0] = original
        if env:
            with open(join(out, ".env"), "w") as handle:
                handle.write(env)
        return join(out, "restart.sh")

    def run_script(self, script, *args):
        return subprocess.run([BASH, script, *args], capture_output=True, text=True)

    def test_a_module_is_enrolled_only_by_its_own_switch_in_its_env(self):
        script = self.generated('restart_policy() { echo "requires=mount:/share/10"; }\n')
        self.assertEqual(self.run_script(script, "enabled").returncode, 1)
        script = self.generated('restart_policy() { echo "requires=mount:/share/10"; }\n', env="MOD_X_RESTART=off\n")
        self.assertEqual(self.run_script(script, "enabled").returncode, 1)
        script = self.generated('restart_policy() { echo "requires=mount:/share/10"; }\n', env="MOD_X_RESTART=on\n")
        self.assertEqual(self.run_script(script, "enabled").returncode, 0)

    def test_the_policy_and_ready_hooks_are_the_snippets_and_default_to_nothing_asked(self):
        script = self.generated('restart_policy() { echo "requires=mount:/share/10"; }\nrestart_ready() { return 3; }\n')
        self.assertEqual(self.run_script(script, "policy").stdout, "requires=mount:/share/10\n")
        self.assertEqual(self.run_script(script, "ready").returncode, 3)
        script = self.generated("# nothing else\n")
        self.assertEqual(self.run_script(script, "policy").stdout, "")
        self.assertEqual(self.run_script(script, "ready").returncode, 0)

    def test_the_script_can_be_sourced_without_running_anything(self):
        script = self.generated('restart_policy() { echo "requires=mount:/share/10"; }\n', env="MOD_X_RESTART=on\n")
        result = subprocess.run(
            [BASH, "-c", f'. "{script}"; echo "enabled=${{RESTART_ENABLED}} module=${{RESTART_MODULE_NAME}}"; declare -F restart_policy restart_ready restart_enabled | wc -l | tr -d " "'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["enabled=on module=mod-x", "3"])

    def test_a_snippet_that_does_not_start_with_the_contract_fails_generate(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))

        with self.assertRaises(ValueError):
            self.generated("restart_policy() { :; }\n", contract="# a different comment")

    def test_generating_twice_gives_the_same_bytes(self):
        body = 'restart_policy() { echo "requires=mount:/share/10"; }\n'
        first = self.generated(body)
        second = self.generated(body)
        with open(first) as one, open(second) as two:
            self.assertEqual(one.read(), two.read())


class InstallRestartTest(unittest.TestCase):
    STUB_DOCKER = """#!/bin/bash
echo "$*" >>"${STUB_DIR}/docker.calls"
case "$1" in
ps) [[ "${STUB_RUNNING}" == "true" && ! -e "${STUB_DIR}/removed" ]] && echo "${SERVICE_NAME}" ;;
rm) : >"${STUB_DIR}/removed" ;;
restart) [[ "${STUB_RESTART_FAILS}" == "true" ]] && exit 1 ;;
esac
exit 0
"""

    def run_install(self, *args, running="true", restart_fails="false", asleep=False, broker=False):
        base = tempfile.mkdtemp()
        install_root = join(base, "install")
        service = join(install_root, "svc", "1.0.0")
        os.makedirs(join(service, "image"))
        with open(join(service, "image", "checkexecuting.sh"), "w") as handle:
            handle.write("#!/bin/bash\nexit 0\n")
        if broker:
            with open(join(service, "image", "broker.sh"), "w") as handle:
                handle.write('#!/bin/bash\necho "broker $*" >>"${STUB_DIR}/broker.calls"\n')
            os.chmod(join(service, "image", "broker.sh"), 0o755)
        if asleep:
            open(join(install_root, "svc", ".sleep"), "w").close()
        bin_dir = join(base, "bin")
        os.makedirs(bin_dir)
        with open(join(bin_dir, "docker"), "w") as handle:
            handle.write(self.STUB_DOCKER)
        os.chmod(join(bin_dir, "docker"), 0o755)
        gtimeout = subprocess.run(["which", "gtimeout"], capture_output=True, text=True).stdout.strip()
        if gtimeout and not subprocess.run(["which", "timeout"], capture_output=True).stdout.strip():
            os.symlink(gtimeout, join(bin_dir, "timeout"))
        with open(join(ROOT, "..", "install.sh")) as handle:
            source = handle.read().replace("/var/lib/asystem/install", install_root)
        script = join(base, "install.sh")
        with open(script, "w") as handle:
            handle.write(source)
        environment = dict(
            os.environ,
            PATH=bin_dir + ":" + os.environ["PATH"],
            STUB_DIR=base,
            STUB_RUNNING=running,
            STUB_RESTART_FAILS=restart_fails,
            SERVICE_NAME="svc",
            SERVICE_VERSION_ABSOLUTE="1.0.0",
        )
        result = subprocess.run([BASH, script, *args], capture_output=True, text=True, env=environment)
        return result, self.lines(join(base, "docker.calls")), base

    def lines(self, path):
        if not os.path.exists(path):
            return []
        with open(path) as handle:
            return handle.read().splitlines()

    def test_restart_restarts_a_running_service_and_exits_zero(self):
        result, calls, _ = self.run_install("restart")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("restart svc", calls)
        self.assertIn("Restarted [svc]", result.stdout)

    def test_restart_exits_ten_for_a_service_that_is_not_running(self):
        result, calls, _ = self.run_install("restart", running="false")
        self.assertEqual(result.returncode, 10, result.stderr)
        self.assertNotIn("restart svc", calls)

    def test_restart_exits_one_when_docker_restart_fails(self):
        result, calls, _ = self.run_install("restart", restart_fails="true")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("restart svc", calls)
        self.assertNotIn("Restarted [svc]", result.stdout)

    def test_restart_exits_ten_for_a_service_put_to_sleep_and_never_clears_the_marker(self):
        result, calls, base = self.run_install("restart", asleep=True)
        self.assertEqual(result.returncode, 10, result.stderr)
        self.assertNotIn("restart svc", calls)
        self.assertTrue(os.path.exists(join(base, "install", "svc", ".sleep")))

    def test_sleep_removes_the_container_marks_the_service_and_exits_zero(self):
        result, calls, base = self.run_install("sleep")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("rm -f svc", calls)
        self.assertTrue(os.path.exists(join(base, "install", "svc", ".sleep")))
        self.assertIn("Slept [svc]", result.stdout)

    def test_stop_removes_the_container_and_clears_the_marker(self):
        result, calls, base = self.run_install("stop", asleep=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("rm -f svc", calls)
        self.assertFalse(os.path.exists(join(base, "install", "svc", ".sleep")))
        self.assertIn("Stopped [svc]", result.stdout)

    def test_sleep_and_stop_of_a_service_that_is_not_running_still_reach_their_state_and_exit_zero(self):
        for verb, marker in (("sleep", True), ("stop", False)):
            with self.subTest(verb=verb):
                result, calls, base = self.run_install(verb, running="false", asleep=not marker)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("rm -f svc", calls)
                self.assertEqual(os.path.exists(join(base, "install", "svc", ".sleep")), marker)

    def test_a_skipped_restart_names_the_service_and_why(self):
        asleep, _, _ = self.run_install("restart", asleep=True)
        self.assertIn("Restart skipped, asleep [svc]", asleep.stderr)
        stopped, _, _ = self.run_install("restart", running="false")
        self.assertIn("Restart skipped, not running [svc]", stopped.stderr)

    def test_schema_still_restarts_the_service_before_it_republishes(self):
        result, calls, base = self.run_install("schema", "broker", broker=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Restarting service to republish its retained topics [svc]", result.stdout)
        self.assertIn("restart svc", calls)
        self.assertEqual(self.lines(join(base, "broker.calls")), ["broker publish"])

    def test_schema_republishes_even_when_the_restart_fails(self):
        result, _, base = self.run_install("schema", "broker", broker=True, restart_fails="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.lines(join(base, "broker.calls")), ["broker publish"])


class ReportTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))

    def test_a_subject_and_its_stages_print_in_the_shape_of_go_test(self):
        import io
        import re

        from asystem.report import stage, subject

        output = io.StringIO()
        with contextlib.redirect_stdout(output), subject("notebook a/b/c"):
            with stage("compile") as entry:
                entry.detail = "interpreted"
            with contextlib.suppress(ValueError), stage("replay"):
                raise ValueError("boom")
        lines = output.getvalue().splitlines()
        self.assertEqual("=== RUN   notebook a/b/c", lines[0])
        self.assertRegex(lines[1], r"^    compile      \.\.\. done \[interpreted\] \(\d+\.\d\ds\)$")
        self.assertRegex(lines[2], r"^    replay       \.\.\. FAILED \(\d+\.\d\ds\)$")
        self.assertTrue(re.fullmatch(r"--- PASS: notebook a/b/c \(\d+\.\d\ds\)", lines[3]))

    def test_a_stage_with_nothing_to_say_still_prints_a_bracketed_value(self):
        import io

        from asystem.report import stage

        output = io.StringIO()
        with contextlib.redirect_stdout(output), stage("setup"):
            pass
        self.assertRegex(output.getvalue(), r"^    setup        \.\.\. done \[none\] \(\d+\.\d\ds\)$")

    def test_a_stage_prints_its_progress_notes_under_its_name_and_resumes_the_line(self):
        import io

        from asystem.report import stage

        output = io.StringIO()
        with contextlib.redirect_stdout(output), stage("serve") as entry:
            entry.note("poll [  5/ 90] seconds state [LOADING]")
            entry.detail = "ready"
        lines = output.getvalue().splitlines()
        self.assertEqual(["    serve        ...", "        poll [  5/ 90] seconds state [LOADING]"], lines[:2])
        self.assertRegex(lines[2], r"^    serve        \.\.\. done \[ready\] \(\d+\.\d\ds\)$")


if __name__ == "__main__":
    unittest.main()
