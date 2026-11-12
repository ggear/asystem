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
