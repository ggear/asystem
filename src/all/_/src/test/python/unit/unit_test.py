import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from os.path import dirname, isdir, join, realpath

ROOT = realpath(join(dirname(__file__), "../../../../../.."))
RESTORE = join(ROOT, "max/letsencrypt/src/main/resources/restore.sh")
BASH = "/opt/homebrew/bin/bash" if os.path.exists("/opt/homebrew/bin/bash") else "bash"
GNU = {"find": "gfind", "date": "gdate"}


class RestoreWrapperTest(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.bin = join(self.workdir, "bin")
        os.makedirs(self.bin)
        for name, target in GNU.items():
            found = subprocess.run(["which", target], capture_output=True, text=True).stdout.strip()
            if found:
                os.symlink(found, join(self.bin, name))
        self.latest = join(self.workdir, "letsencrypt", "latest")
        self.root = join(self.workdir, "letsencrypt", "backup")
        os.makedirs(self.latest)
        os.makedirs(self.root)

    def run_restore(self, *args):
        environment = dict(os.environ, PATH=self.bin + ":" + os.environ["PATH"], RESTORE_SOURCE_PATH=self.latest)
        return subprocess.run([BASH, RESTORE, *args], capture_output=True, text=True, env=environment)

    def source(self, body):
        script = f'set -uo pipefail\nsource "{RESTORE}"\nRESTORE_RUN_TIMESTAMP=2026-10-28_01-00-00\n{textwrap.dedent(body)}'
        environment = dict(os.environ, PATH=self.bin + ":" + os.environ["PATH"], RESTORE_SOURCE_PATH=self.latest)
        return subprocess.run([BASH, "-c", script], capture_output=True, text=True, env=environment)

    def archive(self, stamp, files, kind="full", verdict=None, parent="", units=None, truncate=False):
        run = join(self.root, stamp)
        os.makedirs(run, exist_ok=True)
        source = join(self.workdir, f"src-{stamp}")
        for path, size in files.items():
            os.makedirs(join(source, dirname(path)), exist_ok=True)
            with open(join(source, path), "wb") as handle:
                handle.write(b"x" * size)
        target = join(run, f"letsencrypt_at_{stamp}_from_10.200.1_{kind}.tar.gz")
        subprocess.run(["tar", "-czf", target, "-C", source, *sorted({path.split("/")[0] for path in files})], check=True)
        if truncate:
            with open(target, "r+b") as handle:
                handle.truncate(os.path.getsize(target) // 2)
        if verdict is not None:
            meta = join(run, ".meta")
            os.makedirs(meta, exist_ok=True)
            body = ",\n".join(f'    "{unit}": {count}' for unit, count in (units or {}).items())
            with open(join(meta, "manifest.json"), "w") as handle:
                handle.write(
                    f'{{\n  "kind": "{kind}",\n  "parent": "{parent}",\n  "source_version": "x",\n  "verdict": "{verdict}",\n  "accepted": false,\n  "baseline": "",\n  "evidence": [\n  ],\n  "fingerprint": {{\n{body}\n  }}\n}}\n'
                )
        return run

    def test_a_bare_restore_plans_the_newest_run_and_changes_nothing(self):
        self.archive("2026-10-27_01-00-00", {"live/a": 10}, verdict="success", units={"live": 10})
        self.archive("2026-10-28_01-00-00", {"live/a": 10}, verdict="success", units={"live": 10})
        done = self.run_restore()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("taken     [2026-10-28_01-00-00]", done.stdout)
        self.assertIn("Restore plan resolved", done.stdout)

    def test_the_default_run_skips_a_regressed_one_and_naming_it_needs_force(self):
        self.archive("2026-10-27_01-00-00", {"live/a": 10}, verdict="success", units={"live": 10})
        self.archive("2026-10-28_01-00-00", {"live/a": 1}, verdict="regressed", units={"live": 1})
        self.assertIn("taken     [2026-10-27_01-00-00]", self.run_restore().stdout)
        named = self.run_restore("--from=2026-10-28_01-00-00")
        self.assertEqual(named.returncode, 1)
        self.assertIn("refusing to restore the regressed run", named.stderr)

    def test_a_delta_resolves_its_whole_chain_oldest_first(self):
        self.archive("2026-10-26_01-00-00", {"live/a": 10}, verdict="success", units={"live": 10})
        self.archive("2026-10-27_01-00-00", {"live/a": 10}, kind="delta", verdict="success", parent="2026-10-26_01-00-00", units={"live": 10})
        self.archive("2026-10-28_01-00-00", {"live/a": 10}, kind="delta", verdict="success", parent="2026-10-27_01-00-00", units={"live": 10})
        done = self.run_restore()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("kind [delta] chain [3]", done.stdout)

    def test_a_manifest_naming_the_full_as_parent_still_resolves_every_delta_between(self):
        self.archive("2026-10-26_01-00-00", {"live/a": 10}, verdict="success", units={"live": 10})
        self.archive("2026-10-27_01-00-00", {"live/a": 10}, kind="delta", verdict="success", parent="2026-10-26_01-00-00", units={"live": 10})
        self.archive("2026-10-28_01-00-00", {"live/a": 10}, kind="delta", verdict="success", parent="2026-10-26_01-00-00", units={"live": 10})
        done = self.run_restore()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("chain [3]", done.stdout)
        self.assertNotIn("differs from the preceding run", done.stdout)
        verbose = subprocess.run(
            [BASH, RESTORE],
            capture_output=True,
            text=True,
            env=dict(os.environ, PATH=self.bin + ":" + os.environ["PATH"], RESTORE_SOURCE_PATH=self.latest, RESTORE_VERBOSE="true"),
        )
        self.assertIn("manifest parent [2026-10-26_01-00-00] of [2026-10-28_01-00-00] differs from the preceding run [2026-10-27_01-00-00]", verbose.stdout)

    def test_a_delta_without_a_full_is_a_fault(self):
        self.archive("2026-10-28_01-00-00", {"live/a": 10}, kind="delta", verdict="success", parent="", units={"live": 10})
        done = self.run_restore()
        self.assertEqual(done.returncode, 1)
        self.assertIn("has no run before it to hang off", done.stderr)

    def test_a_truncated_artifact_fails_by_name(self):
        self.archive("2026-10-28_01-00-00", {"live/a": 5000}, verdict="success", units={"live": 5000}, truncate=True)
        done = self.run_restore("--mode=drill")
        self.assertEqual(done.returncode, 1)
        self.assertIn("failed its integrity check", done.stderr)
        self.assertIn("letsencrypt_at_2026-10-28_01-00-00", done.stderr)

    def test_a_drill_passes_records_its_verdict_and_leaves_no_scratch(self):
        run = self.archive("2026-10-28_01-00-00", {"live/a": 100, "live/b": 50, "archive/c": 7}, verdict="success", units={"live": 150, "archive": 7})
        done = self.run_restore("--mode=drill", "--record=primary")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("drill     passed", done.stdout)
        with open(join(run, ".meta", "primary", "drill.json")) as handle:
            self.assertIn('"verdict": "success"', handle.read())
        self.assertFalse(isdir(join(self.workdir, "letsencrypt", "restore", "2026-10-28_01-00-00")))

    def test_a_drill_fails_when_the_backup_holds_less_than_its_manifest_says(self):
        run = self.archive("2026-10-28_01-00-00", {"live/a": 100}, verdict="success", units={"live": 9000})
        done = self.run_restore("--mode=drill", "--record=secondary")
        self.assertEqual(done.returncode, 1)
        self.assertIn("short     [live] wants [9000] holds [100]", done.stdout)
        with open(join(run, ".meta", "secondary", "drill.json")) as handle:
            self.assertIn('"verdict": "failure"', handle.read())

    def sql_run(self, stamp, text, units):
        run = join(self.root, stamp)
        os.makedirs(join(run, ".meta"), exist_ok=True)
        target = join(run, f"letsencrypt_at_{stamp}_from_10.200.1_full.sql.gz")
        subprocess.run(f"gzip -c > {target}", shell=True, input=text.encode(), check=True)
        body = ",\n".join(f'    "{unit}": {count}' for unit, count in units.items())
        with open(join(run, ".meta", "manifest.json"), "w") as handle:
            handle.write(
                f'{{\n  "kind": "full",\n  "parent": "",\n  "source_version": "x",\n  "verdict": "success",\n  "accepted": false,\n  "baseline": "",\n  "evidence": [\n  ],\n  "fingerprint": {{\n{body}\n  }}\n}}\n'
            )
        return run

    def test_a_sql_dump_drills_on_its_artifact_fingerprint_alone(self):
        text = "-- Current Database: `alpha`\nINSERT 1;\n-- Current Database: `beta`\nINSERT 22;\n"
        run = self.sql_run("2026-10-28_01-00-00", text, {"alpha": len("INSERT 1;") + 1, "beta": len("INSERT 22;") + 1})
        done = self.run_restore("--mode=drill", "--record=primary")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("drill     passed", done.stdout)
        with open(join(run, ".meta", "primary", "drill.json")) as handle:
            self.assertIn('"verdict": "success"', handle.read())

    def test_a_sql_dump_holding_less_than_its_manifest_fails_the_drill(self):
        text = "-- Current Database: `alpha`\nINSERT 1;\n"
        self.sql_run("2026-10-28_01-00-00", text, {"alpha": 5000})
        done = self.run_restore("--mode=drill")
        self.assertEqual(done.returncode, 1)
        self.assertIn("short     [alpha]", done.stdout)

    def test_settling_drops_dated_units_from_the_day_before_the_run_onwards(self):
        body = """
            printf '%s\\n' "t/2026-10-26 5" "t/2026-10-27 6" "t/2026-10-28 7" "live 9" | restore_settled
            """
        done = self.source(body)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "t/2026-10-26 5\nlive 9\n")

    def test_a_failing_module_check_fails_the_drill_and_records_it(self):
        run = self.archive("2026-10-28_01-00-00", {"live/a": 100}, verdict="success", units={"live": 100})
        body = f"""
            RESTORE_CHAIN_FILES=("{self.root}/2026-10-28_01-00-00/letsencrypt_at_2026-10-28_01-00-00_from_10.200.1_full.tar.gz")
            restore_checked() {{ return 1; }}
            RESTORE_RECORD=primary
            restore_drilled; echo "status=$?"
            """
        done = self.source(body)
        self.assertIn("status=1", done.stdout)
        self.assertIn("the module check of scratch", done.stderr)
        with open(join(run, ".meta", "primary", "drill.json")) as handle:
            self.assertIn('"verdict": "failure"', handle.read())

    def test_merge_is_refused_by_name_for_a_module_without_restore_merged(self):
        self.archive("2026-10-28_01-00-00", {"live/a": 10}, verdict="success", units={"live": 10})
        done = self.run_restore("--mode=merge")
        self.assertEqual(done.returncode, 1)
        self.assertIn("module [letsencrypt] defines no restore_merged", done.stderr)

    def test_an_unknown_mode_is_refused(self):
        done = self.run_restore("--mode=wipe")
        self.assertEqual(done.returncode, 1)
        self.assertIn("unknown mode [wipe]", done.stderr)

    def merge_body(self, force, pre_merged=""):
        return f"""
            RESTORE_FORCE={force}
            RESTORE_VERIFY_SLEEP=0
            RESTORE_VERIFY_ATTEMPTS=2
            RESTORE_CHAIN_FILES=("{self.root}/2026-10-28_01-00-00/letsencrypt_at_2026-10-28_01-00-00_from_10.200.1_full.tar.gz")
            backup_fingerprinted() {{
              case "$1" in
              live) cat "{self.workdir}/live.txt" ;;
              *) printf 'a/2026-10-20 5\\na/2026-10-21 7\\nb/2026-10-20 3\\n' ;;
              esac
            }}
            restore_staged() {{ mkdir -p "{self.workdir}/scratch"; echo "{self.workdir}/scratch"; }}
            restore_sealed() {{ :; }}
            restore_backed() {{ :; }}
            restore_restarted() {{ printf 'a/2026-10-20 5\\na/2026-10-21 7\\nb/2026-10-20 3\\n' > "{self.workdir}/live.txt"; }}
            restore_merged() {{ echo "$1" >> "{self.workdir}/merged.log"; }}
            RESTORE_LIVE_ADDRESS=live
            {pre_merged}
            restore_merge; echo "status=$?"; echo "faults=$RESTORE_FAULTS"
            """

    def test_merge_plans_only_units_that_differ_and_applies_them_with_force(self):
        with open(join(self.workdir, "live.txt"), "w") as handle:
            handle.write("a/2026-10-20 5\na/2026-10-21 2\nlive-only/2026-10-30 9\n")
        planned = self.source(self.merge_body("false"))
        self.assertIn("[2] closed unit(s) differ from live", planned.stdout)
        self.assertIn("plan      [a/2026-10-21]", planned.stdout)
        self.assertIn("plan      [b/2026-10-20]", planned.stdout)
        self.assertNotIn("live-only", planned.stdout)
        self.assertNotIn("a/2026-10-20]", planned.stdout)
        self.assertFalse(os.path.exists(join(self.workdir, "merged.log")))
        applied = self.source(self.merge_body("true"))
        self.assertIn("status=0", applied.stdout)
        with open(join(self.workdir, "merged.log")) as handle:
            self.assertEqual(sorted(handle.read().split()), ["a/2026-10-21", "b/2026-10-20"])

    def test_merge_faults_when_live_still_holds_less_after_the_restart(self):
        with open(join(self.workdir, "live.txt"), "w") as handle:
            handle.write("a/2026-10-20 5\n")
        body = self.merge_body("true").replace("restore_restarted() {", "restore_restarted() { return 0; }\n            restore_restarted_unused() {")
        done = self.source(body)
        self.assertIn("status=1", done.stdout)
        self.assertIn("holds [0] after the merge, wants at least [7]", done.stderr)

    def test_merge_waits_for_live_counts_to_settle_after_the_restart(self):
        calls = join(self.workdir, "calls")
        body = f"""
            RESTORE_FORCE=true
            RESTORE_VERIFY_SLEEP=0
            RESTORE_CHAIN_FILES=("{self.root}/x")
            backup_fingerprinted() {{
              case "$1" in
              live)
                n=$(cat "{calls}" 2>/dev/null || echo 0)
                echo $((n + 1)) > "{calls}"
                if [ "$n" -lt 3 ]; then printf 'a/2026-10-20 5\\n'; else printf 'a/2026-10-20 5\\na/2026-10-21 7\\n'; fi
                ;;
              *) printf 'a/2026-10-20 5\\na/2026-10-21 7\\n' ;;
              esac
            }}
            restore_staged() {{ mkdir -p "{self.workdir}/scratch"; echo "{self.workdir}/scratch"; }}
            restore_sealed() {{ :; }}
            restore_backed() {{ :; }}
            restore_restarted() {{ :; }}
            restore_merged() {{ :; }}
            RESTORE_LIVE_ADDRESS=live
            restore_merge; echo "status=$?"
            """
        done = self.source(body)
        self.assertIn("status=0", done.stdout)
        with open(calls) as handle:
            self.assertGreaterEqual(int(handle.read()), 4)

    def test_merge_still_faults_when_live_never_catches_up(self):
        body = f"""
            RESTORE_FORCE=true
            RESTORE_VERIFY_SLEEP=0
            RESTORE_VERIFY_ATTEMPTS=3
            RESTORE_CHAIN_FILES=("{self.root}/x")
            backup_fingerprinted() {{
              case "$1" in
              live) printf 'a/2026-10-20 5\\n' ;;
              *) printf 'a/2026-10-20 5\\na/2026-10-21 7\\n' ;;
              esac
            }}
            restore_staged() {{ mkdir -p "{self.workdir}/scratch"; echo "{self.workdir}/scratch"; }}
            restore_sealed() {{ :; }}
            restore_backed() {{ :; }}
            restore_restarted() {{ :; }}
            restore_merged() {{ :; }}
            RESTORE_LIVE_ADDRESS=live
            restore_merge; echo "status=$?"
            """
        done = self.source(body)
        self.assertIn("status=1", done.stdout)
        self.assertIn("unit [a/2026-10-21] holds [0] after the merge, wants at least [7]", done.stderr)

    def parallel_body(self, failing=""):
        return f"""
            RESTORE_FORCE=true
            RESTORE_MERGE_JOBS=3
            RESTORE_VERIFY_SLEEP=0
            RESTORE_VERIFY_ATTEMPTS=1
            RESTORE_CHAIN_FILES=("{self.root}/x")
            backup_fingerprinted() {{
              case "$1" in
              live) cat "{self.workdir}/live.txt" ;;
              *) for d in 01 02 03 04 05 06 07 08 09 10; do echo "t/2026-10-$d 5"; done ;;
              esac
            }}
            restore_staged() {{ mkdir -p "{self.workdir}/scratch"; echo "{self.workdir}/scratch"; }}
            restore_sealed() {{ :; }}
            restore_backed() {{ :; }}
            restore_restarted() {{ for d in 01 02 03 04 05 06 07 08 09 10; do echo "t/2026-10-$d 5"; done > "{self.workdir}/live.txt"; }}
            restore_merged() {{
              sleep 0.05
              [ "$1" = "{failing}" ] && return 1
              echo "$1" >> "{self.workdir}/merged.log"
            }}
            RESTORE_LIVE_ADDRESS=live
            restore_merge; echo "status=$?"; echo "changed=$RESTORE_CHANGED"
            """

    def test_concurrent_merge_applies_every_unit_exactly_once(self):
        with open(join(self.workdir, "live.txt"), "w") as handle:
            handle.write("")
        done = self.source(self.parallel_body())
        self.assertIn("status=0", done.stdout)
        self.assertIn("changed=10", done.stdout)
        with open(join(self.workdir, "merged.log")) as handle:
            self.assertEqual(sorted(handle.read().split()), [f"t/2026-10-{day:02d}" for day in range(1, 11)])

    def test_concurrent_merge_reports_the_unit_that_failed_and_stops_before_verifying(self):
        with open(join(self.workdir, "live.txt"), "w") as handle:
            handle.write("")
        done = self.source(self.parallel_body(failing="t/2026-10-04"))
        self.assertIn("status=1", done.stdout)
        self.assertIn("could not merge [t/2026-10-04]", done.stderr)

    def test_status_lines_never_leak_into_a_captured_scratch_address(self):
        body = """
            restore_staged() { restore_stamped "starting scratch"; echo "the-address"; }
            captured="$(restore_staged)"
            echo "captured=[${captured}]"
            """
        done = self.source(body)
        self.assertIn("captured=[the-address]", done.stdout)
        self.assertIn("starting scratch", done.stderr)

    def test_merge_reports_progress_with_volume_and_rate_at_each_pause(self):
        with open(join(self.workdir, "live.txt"), "w") as handle:
            handle.write("")
        body = (
            self.parallel_body()
            .replace("RESTORE_MERGE_JOBS=3", "RESTORE_MERGE_JOBS=3\n            RESTORE_PROGRESS_SECONDS=0")
            .replace(
                'echo "$1" >> "{self.workdir}/merged.log"'.replace("{self.workdir}", self.workdir),
                'echo "$1" >> "' + self.workdir + '/merged.log"; echo "500 2097152" >> "$RESTORE_STATS_FILE"',
            )
        )
        done = self.source(body)
        self.assertIn("status=0", done.stdout)
        self.assertRegex(done.stderr, r"staging +\d\d:\d\d:\d\d \[1\] artifact\(s\) into scratch")
        self.assertRegex(done.stderr, r"counting +\d\d:\d\d:\d\d fingerprinting live")
        self.assertRegex(done.stderr, r"merge +\d\d:\d\d:\d\d merging \[10\] unit\(s\) with \[3\] job\(s\)")
        self.assertRegex(done.stderr, r"merge +\d\d:\d\d:\d\d merged \[\d+\] of \[10\] units \[\d+\]%, \[\d+\] rows, \[\d\.\d\d\] GiB at \[\d+\] MiB/s, \[\d+\] units a minute")
        self.assertRegex(done.stderr, r"merged \[10\] of \[10\] units \[100\]%, \[5000\] rows")
        self.assertRegex(done.stderr, r"verify +\d\d:\d\d:\d\d merge written, restarting \[live\]")
        self.assertRegex(done.stderr, r"verify +\d\d:\d\d:\d\d every merged unit holds at least the backup's count")

    def test_a_rerun_skips_units_already_merged(self):
        with open(join(self.workdir, "live.txt"), "w") as handle:
            handle.write("a/2026-10-20 5\n")
        pre = f'mkdir -p "{self.workdir}/letsencrypt/restore/2026-10-28_01-00-00"; echo "a/2026-10-21" > "{self.workdir}/letsencrypt/restore/2026-10-28_01-00-00.merged"; RESTORE_INTERNAL_SOURCE_DIR="{self.latest}"'
        done = self.source(self.merge_body("true", pre_merged=pre))
        with open(join(self.workdir, "merged.log")) as handle:
            self.assertNotIn("a/2026-10-21", handle.read())
        self.assertIn("status=0", done.stdout)

    def test_a_sweep_removes_stale_scratch_and_keeps_merge_progress(self):
        restore = join(self.workdir, "letsencrypt", "restore")
        for name in ("2026-10-29_01-00-38", "2026-10-30_01-00-38"):
            os.makedirs(join(restore, name))
        with open(join(restore, "2026-10-29_01-00-38.merged"), "w") as handle:
            handle.write("a/2026-10-21\n")
        done = self.source(f'RESTORE_INTERNAL_SOURCE_DIR="{self.latest}"\nrestore_swept\necho "status=$?"')
        self.assertIn("status=0", done.stdout)
        self.assertEqual(sorted(os.listdir(restore)), ["2026-10-29_01-00-38.merged"])


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


if __name__ == "__main__":
    unittest.main()


class ModelProjectTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(contextlib.chdir(fresh_mlruns_dir()))
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        from asystem.model import build_signature, golden_document, golden_step, signature_input, signature_output, signature_state

        self.project_dir = join(tempfile.mkdtemp(), "project")
        self.signature = build_signature(
            "demo_calc",
            [signature_input("demo_clock_seconds", "seconds", "Time of the call."), signature_input("demo_state_in", "state", "Carried state.", required=False, shape=[-1])],
            [signature_output("demo_limit_seconds", "seconds", "A limit."), signature_output("demo_state_out", "state", "Next state.", required=False, shape=[-1])],
            state=[signature_state("last_seconds", "seconds", "The previous call.")],
        )
        steps = [
            golden_step(self.signature, "s-0", {"demo_clock_seconds": 10.0}, {"demo_limit_seconds": 5}),
            golden_step(self.signature, "s-1", {"demo_clock_seconds": 11.0, "demo_state_in": [10.0]}, {"demo_limit_seconds": 5}),
            golden_step(self.signature, "s-2", {"demo_state_in": [10.0]}, error="signature"),
        ]
        self.golden = golden_document([("calls", steps)])

    def write(self, **overrides):
        from asystem.model import write_project

        arguments = {
            "project_dir": self.project_dir,
            "name": "demo_calc",
            "flavour": "static",
            "signature": self.signature,
            "golden": self.golden,
            "provenance": {"source": "manual", "inputs": []},
            "constants": {"demo_limit_seconds": 5},
        }
        return write_project(**{**arguments, **overrides})

    def rules(self, **overrides):
        from asystem.model import lint_project

        with contextlib.suppress(ValueError):
            self.write(**overrides)
        return sorted({rule for rule, _ in lint_project(self.project_dir)})

    def test_valid_project_has_no_findings(self):
        self.assertEqual("static", self.write()["flavour"])
        self.assertEqual([], self.rules())

    def test_tampered_file_is_found(self):
        self.write()
        with open(join(self.project_dir, "golden.json"), "a") as golden:
            golden.write(" ")
        from asystem.model import lint_project

        self.assertEqual(["PJ003"], sorted({rule for rule, _ in lint_project(self.project_dir)}))

    def test_unknown_flavour_and_source_are_found(self):
        self.assertEqual(["PJ002"], self.rules(flavour="guess", provenance={"source": "guess", "inputs": []}))

    def test_provenance_inputs_must_be_a_list(self):
        self.assertEqual(["PJ002"], self.rules(provenance={"source": "manual"}))

    def test_model_flavour_needs_its_file(self):
        self.assertEqual(["PJ003"], self.rules(flavour="wasm", evaluation=self.evaluation(), provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"}))

    def test_model_file_is_copied_into_the_project_and_hashed(self):
        model_path = self.model_file()
        manifest = self.write(
            flavour="pyfunc",
            model_path=model_path,
            constants=None,
            evaluation=self.evaluation(),
            provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"},
        )
        self.assertEqual("model.py", manifest["files"]["model"]["path"])
        self.assertTrue(os.path.isfile(join(self.project_dir, "model.py")))

    def test_implementation_must_say_something(self):
        for implementation in ("demo", "TBD", "to be determined", "", None):
            self.assertEqual(["PJ002", "PJ003"], self.rules(flavour="wasm", evaluation=self.evaluation(), provenance={"source": "manual", "inputs": [], "implementation": implementation}))

    def test_a_wasm_module_may_import_only_the_maths_functions(self):
        import wasmtime

        from asystem.model import lint_project

        def rules(wat):
            project_dir = demo_project("wasm")
            with open(join(project_dir, "model.wasm"), "wb") as model_file:
                model_file.write(wasmtime.wat2wasm(wat))
            return {rule for rule, _ in lint_project(project_dir)}

        body = '(memory (export "memory") 1) (func (export "predict") (param i32 i32 i32))'
        self.assertNotIn("PJ016", rules(f'(module (import "asystem_math" "atan" (func (param f64) (result f64))) {body})'))
        self.assertIn("PJ016", rules(f'(module (import "env" "atan" (func (param f64) (result f64))) {body})'))
        self.assertIn("PJ016", rules(f'(module (import "asystem_math" "pow" (func (param f64) (result f64))) {body})'))
        self.assertIn("PJ016", rules(f'(module (import "asystem_math" "atan" (func (param f64 f64) (result f64))) {body})'))

    def test_a_pyfunc_declares_the_packages_its_model_imports_beyond_the_base(self):
        def rules(source, python_deps):
            model_path = join(tempfile.mkdtemp(), "model.py")
            with open(model_path, "w") as model_file:
                model_file.write(source)
            return self.rules(flavour="pyfunc", model_path=model_path, python_deps=python_deps)

        body = "import json\nimport pandas\nfrom mlflow.models import set_model\n"
        self.assertNotIn("PJ017", rules(body, []))
        self.assertNotIn("PJ017", rules(body + "import polars as pl\n", ["polars"]))
        self.assertNotIn("PJ017", rules(body + "from sklearn.linear_model import Ridge\n", ["Scikit-Learn"]))
        self.assertIn("PJ017", rules(body + "import polars as pl\n", []))
        self.assertIn("PJ017", rules(body, ["polars"]))
        self.assertIn("PJ017", rules(body, ["pandas"]))

    def test_a_wasm_runtime_must_equal_the_module_imports(self):
        import wasmtime

        from asystem.model import lint_project

        project_dir = demo_project("wasm")
        with open(join(project_dir, "model.wasm"), "wb") as model_file:
            model_file.write(wasmtime.wat2wasm('(module (import "asystem_math" "tanh" (func (param f64) (result f64))) (memory (export "memory") 1) (func (export "predict") (param i32 i32 i32)))'))
        with open(join(project_dir, "project.json")) as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual({"wasm": []}, manifest["runtime"])
        self.assertIn("PJ017", {rule for rule, _ in lint_project(project_dir)})
        for runtime, expected in (({"wasm": ["tanh"]}, False), ({"wasm": ["sin"]}, True), ({"wasm": ["tanh"], "python": []}, True), ({}, True)):
            with open(join(project_dir, "project.json"), "w") as manifest_file:
                json.dump({**manifest, "runtime": runtime}, manifest_file)
            self.assertEqual(expected, "PJ017" in {rule for rule, _ in lint_project(project_dir)})

    def test_a_flavour_with_no_runtime_takes_no_python_dependencies(self):
        with self.assertRaises(ValueError):
            self.write(python_deps=["polars"])
        self.write()
        with open(join(self.project_dir, "project.json")) as manifest_file:
            manifest = json.load(manifest_file)
        with open(join(self.project_dir, "project.json"), "w") as manifest_file:
            json.dump({**manifest, "runtime": {"python": []}}, manifest_file)
        from asystem.model import lint_project

        self.assertEqual(["PJ017"], sorted({rule for rule, _ in lint_project(self.project_dir)}))

    def test_pyfunc_project_is_registered_as_a_pyfunc_model(self):
        from asystem.model import build_signature, golden_document, golden_step, register_project, signature_input, signature_output

        signature = build_signature("demo_calc", [signature_input("demo_in_seconds", "seconds", "Input.")], [signature_output("demo_out_seconds", "seconds", "Output.")])
        golden = golden_document([("calls", [golden_step(signature, "s-0", {"demo_in_seconds": 1.0}, {"demo_out_seconds": 2.0}), golden_step(signature, "s-1", {}, error="signature")])])
        model_path = join(tempfile.mkdtemp(), "model.py")
        with open(model_path, "w") as model_file:
            model_file.write(
                "import pandas as pd\nfrom mlflow.models import set_model\nfrom mlflow.pyfunc import PythonModel\n\n\n"
                "class Demo(PythonModel):\n    def predict(self, context, model_input: pd.DataFrame, params=None):\n"
                '        return pd.DataFrame({"demo_out_seconds": model_input["demo_in_seconds"] * 2})\n\n\nset_model(Demo())\n'
            )
        self.write(
            flavour="pyfunc",
            model_path=model_path,
            signature=signature,
            golden=golden,
            constants=None,
            evaluation=self.evaluation(output="demo_out_seconds"),
            provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"},
        )
        root_dir = tempfile.mkdtemp()
        uri = f"sqlite:///{join(root_dir, 'mlflow.db')}"
        import mlflow.pyfunc

        version = register_project(self.project_dir, "demo_calc", uri, snapshot_version="10.200.1951-SNAPSHOT")
        mlflow.set_tracking_uri(uri)
        client = mlflow.MlflowClient()
        registered = client.get_model_version("demo_calc", str(version))
        self.assertEqual("10.200.1951-SNAPSHOT", registered.tags["snapshot_version"])
        self.assertEqual("datascience", client.get_run(registered.run_id).data.tags["mlflow.source.name"])
        register_project(self.project_dir, "demo_calc", uri, snapshot_version="10.200.1952-SNAPSHOT")
        self.assertEqual("10.200.1951-SNAPSHOT", client.get_model_version("demo_calc", str(version)).tags["snapshot_version"])
        loaded = mlflow.pyfunc.load_model("models:/demo_calc@preview")
        self.assertEqual([2.0], list(loaded.predict({"demo_in_seconds": [1.0]})["demo_out_seconds"]))
        self.assertEqual("1", str(version))

    def test_pyfunc_registration_refuses_a_state_vector_signature(self):
        from asystem.model import register_project

        model_path = self.model_file()
        self.write(
            flavour="pyfunc",
            model_path=model_path,
            constants=None,
            evaluation=self.evaluation(),
            provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"},
        )
        with self.assertRaises(ValueError):
            register_project(self.project_dir, "demo_calc", f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}")

    def model_file(self, flavour="pyfunc"):
        path = join(tempfile.mkdtemp(), {"wasm": "model.wasm", "onnx": "model.onnx"}.get(flavour, "model.py"))
        if flavour == "wasm":
            with open(path, "wb") as model_file:
                model_file.write(b"\0asm\x01\x00\x00\x00")
        elif flavour == "onnx":
            import onnx
            from onnx import TensorProto, helper

            node = helper.make_node("Identity", ["x"], ["y"])
            graph = helper.make_graph([node], "demo", [helper.make_tensor_value_info("x", TensorProto.DOUBLE, [1])], [helper.make_tensor_value_info("y", TensorProto.DOUBLE, [1])])
            onnx.save(helper.make_model(graph), path)
        else:
            with open(path, "w") as model_file:
                model_file.write("VALUE = 1\n")
        return path

    def evaluation(self, passing=True, output="demo_limit_seconds", checks=None):
        from asystem.model import evaluate_acceptance

        dataset_dir = join(tempfile.mkdtemp(), "2026-11-03_10-00-00")
        os.makedirs(dataset_dir)
        dataset = join(dataset_dir, "demo_calc_limit_2026-11-01_2026-11-02.csv")
        with open(dataset, "w") as dataset_file:
            dataset_file.write("a,b\n1,2\n")
        value = 0.5 if passing else 9.0
        return evaluate_acceptance(lambda: checks or [{"split": "backtest", "output": output, "name": "rmse", "value": value, "limit": 1.0, "direction": "max"}], {"backtest": [dataset]})

    def test_measure_matches_the_definitions(self):
        from asystem.model import measure

        measures = measure([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 6.0])
        self.assertAlmostEqual(1.0, measures["rmse"])
        self.assertAlmostEqual(0.5, measures["mae"])
        self.assertAlmostEqual(2.0, measures["max_abs_error"])
        self.assertAlmostEqual(0.5, measures["bias"])
        self.assertAlmostEqual(1.0 - 4.0 / 5.0, measures["r2"])
        self.assertAlmostEqual(8.0 / 70.0**0.5, measures["pearson_r"])
        constant = measure([2.0, 2.0], [2.0, 3.0])
        self.assertIsNone(constant["r2"])
        self.assertIsNone(constant["pearson_r"])
        with self.assertRaises(ValueError):
            measure([1.0], [1.0, 2.0])

    def test_outcome_and_budget_follow_the_value_limit_and_direction(self):
        evaluation = self.evaluation()
        self.assertEqual((True, 0.5, 0.5), (evaluation["passed"], evaluation["budget"], evaluation["checks"][0]["budget"]))
        self.assertEqual("2026-11-03_10-00-00/demo_calc_limit_2026-11-01_2026-11-02.csv", evaluation["datasets"]["backtest"][0]["path"])
        failing = self.evaluation(passing=False)
        self.assertEqual((False, 9.0), (failing["passed"], failing["budget"]))
        checks = [
            {"split": "backtest", "output": "demo_limit_seconds", "name": "recall", "value": 0.8, "limit": 0.5, "direction": "min"},
            {"split": "backtest", "output": "demo_limit_seconds", "name": "over", "value": -2.0, "limit": 0.0, "direction": "max"},
            {"split": "validation", "output": "demo_limit_seconds", "name": "mae", "value": 99.0, "limit": 1.0, "direction": "max", "gate": False},
        ]
        mixed = self.evaluation(checks=checks)
        self.assertEqual([True, True, False], [entry["passed"] for entry in mixed["checks"]])
        self.assertEqual([0.625, 0.0, 99.0], [entry["budget"] for entry in mixed["checks"]])
        self.assertEqual((True, 0.625), (mixed["passed"], mixed["budget"]))
        unmeasured = self.evaluation(checks=[{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": None, "limit": 1.0, "direction": "max"}])
        self.assertEqual((False, None), (unmeasured["passed"], unmeasured["budget"]))

    def test_a_malformed_check_is_refused(self):
        base = {"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": 1.0, "limit": 1.0, "direction": "max"}
        for checks in ([], None, [{**base, "direction": "avg"}], [{**base, "limit": -1.0}], [{**base, "direction": "min", "limit": 0}], [{**base, "limit": "1"}]):
            with self.assertRaises(ValueError, msg=checks):
                self.evaluation(checks=checks) if checks else __import__("asystem.model", fromlist=["x"]).evaluate_acceptance(lambda checks=checks: checks, {})

    def test_project_with_an_evaluation_has_no_findings(self):
        manifest = self.write(evaluation=self.evaluation())
        self.assertEqual(["evaluation", "golden", "signature"], sorted(manifest["files"]))
        self.assertEqual([], self.rules(evaluation=self.evaluation()))

    def test_a_model_project_without_an_evaluation_is_refused(self):
        self.assertEqual(["AC001"], self.rules(**{**self.fitted_overrides(), "evaluation": None}))

    def test_every_required_output_needs_a_gating_check(self):
        checks = [{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": 0.5, "limit": 1.0, "direction": "max", "gate": False}]
        self.assertEqual(["AC001"], self.rules(evaluation=self.evaluation(checks=checks)))

    def test_checks_are_validated(self):
        base = {"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": 0.5, "limit": 1.0, "direction": "max"}
        for entry in ({**base, "split": "training"}, {**base, "name": "Bad-Name"}, {**base, "output": "demo_other_seconds"}):
            self.assertIn("AC002", self.rules(evaluation=self.evaluation(checks=[entry, {**base, "name": "mae"}])), entry)
        evaluation = self.evaluation()
        evaluation["checks"][0]["gate"] = "yes"
        self.assertIn("AC002", self.rules(evaluation=evaluation))
        evaluation = self.evaluation()
        evaluation["checks"][0]["value"] = "0.5"
        self.assertIn("AC002", self.rules(evaluation=evaluation))

    def test_a_tampered_evaluation_is_found(self):
        evaluation = self.evaluation(passing=False)
        evaluation["checks"][0]["passed"] = True
        self.assertIn("AC003", self.rules(evaluation=evaluation))
        evaluation = self.evaluation(passing=False)
        evaluation["passed"] = True
        self.assertIn("AC003", self.rules(evaluation=evaluation))
        evaluation = self.evaluation()
        evaluation["budget"] = 0.1
        self.assertIn("AC003", self.rules(evaluation=evaluation))
        evaluation = self.evaluation()
        del evaluation["datasets"]["backtest"]
        self.assertIn("AC003", self.rules(evaluation=evaluation))

    def test_registration_logs_metrics_datasets_and_the_verdict(self):
        import mlflow
        from asystem.model import register_project

        self.write(evaluation=self.evaluation())
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        register_project(self.project_dir, "demo_calc", uri)
        mlflow.set_tracking_uri(uri)
        run = mlflow.search_runs(experiment_names=["demo_calc"], output_format="list")[0]
        self.assertEqual(("passed", "0.5"), (run.data.tags["acceptance"], run.data.tags["acceptance_budget"]))
        self.assertEqual((1.0, 0.5, 0.5), (run.data.metrics["acceptance_passed"], run.data.metrics["acceptance_budget"], run.data.metrics["backtest/demo_limit_seconds/rmse"]))
        assert run.inputs is not None
        self.assertEqual("backtest", run.inputs.dataset_inputs[0].tags[0].value)

    def other_project(self, **overrides):
        other_dir = join(tempfile.mkdtemp(), "project")
        with contextlib.suppress(ValueError):
            self.write(project_dir=other_dir, **overrides)
        return other_dir

    def fitted_overrides(self, passing=True):
        model_path = self.model_file("wasm")
        return {
            "flavour": "wasm",
            "model_path": model_path,
            "constants": None,
            "evaluation": self.evaluation(passing=passing),
            "provenance": {"source": "manual", "inputs": [], "implementation": "demo module built by hand"},
        }

    def test_release_check_needs_a_passing_evaluation(self):
        from asystem.model import GateError, check_release

        self.write()
        self.assertEqual(["PM004"], [rule for rule, _ in check_release(self.project_dir)])
        with self.assertRaises(GateError) as raised:
            self.write(**self.fitted_overrides(passing=False))
        self.assertEqual(("Evaluate", "acceptance"), (raised.exception.stage, raised.exception.gate))
        self.assertEqual(["PM004"], [rule for rule, _ in check_release(self.project_dir)])
        self.write(**self.fitted_overrides())
        self.assertEqual([], check_release(self.project_dir))

    def test_registering_an_unchanged_project_creates_nothing_new(self):
        import mlflow
        from asystem.model import register_project

        self.write()
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        first = register_project(self.project_dir, "demo_calc", uri)
        second = register_project(self.project_dir, "demo_calc", uri, aliases=("preview", "release"))
        self.assertEqual(first, second)
        mlflow.set_tracking_uri(uri)
        self.assertEqual(1, len(mlflow.search_runs(experiment_names=["demo_calc"])))
        self.assertEqual(second, mlflow.MlflowClient().get_model_version_by_alias("demo_calc", "release").version)
        self.write(provenance={"source": "manual", "inputs": [], "notes": "changed"})
        self.assertNotEqual(first, register_project(self.project_dir, "demo_calc", uri))

    def test_a_measured_check_needs_a_recorded_dataset(self):
        from asystem.model import evaluate_acceptance

        measured = evaluate_acceptance(lambda: [{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": 0.1, "limit": 1.0, "direction": "max"}], {"backtest": []})
        self.assertIn("AC003", self.rules(evaluation=measured))
        unmeasured = evaluate_acceptance(lambda: [{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": None, "limit": 1.0, "direction": "max"}], {"backtest": []})
        self.assertNotIn("AC003", self.rules(evaluation=unmeasured))

    def test_static_flavour_refuses_a_model_file(self):
        with self.assertRaises(ValueError):
            self.write(model_path=join(self.project_dir, "signature.json"))

    def test_model_flavour_needs_its_implementation(self):
        self.assertEqual(["PJ002", "PJ003"], self.rules(flavour="wasm", evaluation=self.evaluation()))

    def test_name_must_match_signature_and_style(self):
        self.assertIn("PJ004", self.rules(name="Demo-Calc"))

    def test_output_must_be_module_prefixed_with_a_unit_suffix(self):
        self.signature["outputs"][0]["name"] = "other_limit"
        self.assertIn("PJ007", self.rules(constants={"other_limit": 5}))

    def test_constant_outside_signature_is_found(self):
        self.assertIn("PJ008", self.rules(constants={"demo_limit_seconds": 5, "demo_misspelt_seconds": 1}))

    def test_static_must_cover_required_outputs(self):
        self.assertIn("PJ008", self.rules(constants={}))

    def test_golden_step_must_have_required_inputs(self):
        del self.golden["sequences"][0]["steps"][0]["request"]["inputs"][0]
        self.assertIn("PJ010", self.rules())

    def test_golden_needs_an_error_step_and_a_stateless_first_call(self):
        del self.golden["sequences"][0]["steps"][2]
        self.assertEqual(["PJ011"], self.rules())
        del self.golden["sequences"][0]["steps"][0]
        self.assertEqual(["PJ011"], self.rules())

    def test_static_responses_must_equal_the_constants(self):
        self.golden["sequences"][0]["steps"][0]["response"]["outputs"][0]["data"] = [6]
        self.assertEqual(["PJ012"], self.rules())

    def test_package_project_builds_golden_from_samples(self):
        from asystem.model import lint_project, package_project

        rows = [
            {"demo_clock_seconds": 10.0, "expect": "ok"},
            {"demo_clock_seconds": 11.0, "demo_state_in": "10.0 11.0", "expect": "ok"},
            {"expect": "error"},
        ]
        manifest = package_project(self.project_dir, "demo_calc", "static", self.signature, rows, {"source": "manual", "inputs": []}, constants={"demo_limit_seconds": 5})
        self.assertEqual("static", manifest["flavour"])
        self.assertEqual([], lint_project(self.project_dir))

    def test_render_rust_names_every_tensor_with_optional_fields(self):
        from asystem.model import render_rust

        rust = render_rust(self.signature)
        self.assertIn("pub demo_clock_seconds: f64,", rust)
        self.assertIn("pub demo_state_in: Option<Vec<f64>>,", rust)
        self.assertIn('pub const REQUIRED_OUTPUT_NAMES: &[&str] = &["demo_limit_seconds"];', rust)

    def test_registered_name_and_check_name(self):
        from asystem.model import check_name, registered_name

        self.assertEqual("rackmains_ups_battery", registered_name("rackmains", "ups", "battery"))
        self.assertEqual("example_static_constant", registered_name("example", "static", "constant"))
        with self.assertRaises(ValueError):
            check_name("Bad-Name")


class ReplayTest(unittest.TestCase):
    def test_each_flavour_replays_its_golden_exactly(self):
        from asystem.replay import replay_project

        for flavour in ("pyfunc", "wasm", "onnx"):
            self.assertEqual([], replay_project(demo_project(flavour)), flavour)

    def test_a_response_that_differs_from_the_golden_is_a_finding(self):
        from asystem.replay import replay_project

        for flavour in ("pyfunc", "wasm", "onnx"):
            self.assertEqual(["RP003"], [rule for rule, _ in replay_project(demo_project(flavour, golden_out=3.5))], flavour)

    def test_a_stated_tolerance_accepts_a_small_difference_and_rejects_a_large_one(self):
        from asystem.replay import replay_project

        bounds = {"demo_out": {"absolute": 1e-3}}
        for flavour in ("pyfunc", "wasm", "onnx"):
            self.assertEqual([], replay_project(demo_project(flavour, golden_out=3.0000001, tolerance=bounds)), flavour)
            self.assertEqual(["RP003"], [rule for rule, _ in replay_project(demo_project(flavour, golden_out=3.5, tolerance=bounds))], flavour)
            self.assertEqual(["RP003"], [rule for rule, _ in replay_project(demo_project(flavour, golden_out=3.0000001))], flavour)

    def test_a_relative_tolerance_scales_with_the_expected_value(self):
        from asystem.replay import replay_project

        self.assertEqual([], replay_project(demo_project("pyfunc", golden_out=3.003, tolerance={"demo_out": {"relative": 0.002}})))
        self.assertEqual(["RP003"], [rule for rule, _ in replay_project(demo_project("pyfunc", golden_out=3.01, tolerance={"demo_out": {"relative": 0.002}}))])

    def test_a_malformed_tolerance_is_a_finding(self):
        for bounds in ({"demo_other": {"absolute": 1}}, {"demo_out": {"absolute": -1}}, {"demo_out": {}}, {"demo_out": {"scale": 1}}, {"demo_out": {"absolute": True}}):
            with self.assertRaises(ValueError) as refused:
                demo_project("pyfunc", tolerance=bounds)
            self.assertIn("PJ015", str(refused.exception), bounds)


class MetadataTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        self.workspace = tempfile.mkdtemp()
        os.makedirs(join(self.workspace, "data", "training", "2026-01-01_00-00-00"))
        with open(join(self.workspace, "data", "training", "2026-01-01_00-00-00", "a.csv"), "w") as data_file:
            data_file.write("x\n1\n")
        self.write_notebook(["x = 1\n"], ["# a heading\n"])
        self.project_dir = demo_project("wasm")

    def write_notebook(self, code, markdown):
        with open(join(self.workspace, "notebook.ipynb"), "w") as notebook_file:
            json.dump({"cells": [{"cell_type": "code", "source": code}, {"cell_type": "markdown", "source": markdown}]}, notebook_file)

    def metadata(self, **changes):
        from asystem.metadata import METADATA_SCHEMA, content_sha256

        return {
            "schema": METADATA_SCHEMA,
            "inputs_sha256": "a" * 64,
            "content_sha256": content_sha256(self.project_dir),
            "runtime": json.load(open(join(self.project_dir, "project.json"))).get("runtime", {}),
            "released_version": None,
            "snapshot_version": None,
            "released_by": None,
            "released_at": None,
            "targets": [{"kind": "served"}, {"kind": "embedded", "language": "go"}],
            "passed": [],
            **changes,
        }

    def place(self, metadata):
        from asystem.metadata import PROJECT_DIR, write_metadata

        shutil.copytree(self.project_dir, join(self.workspace, PROJECT_DIR), dirs_exist_ok=True)
        write_metadata(self.workspace, metadata)

    def rules(self):
        from asystem.metadata import lint_metadata

        return sorted({rule for rule, _ in lint_metadata(self.workspace, "wasm")})

    def test_a_consistent_workspace_has_no_findings(self):
        self.place(self.metadata())
        self.assertEqual([], self.rules())

    def test_a_missing_metadata_or_field_or_project_is_a_finding(self):
        self.assertEqual(["MD001"], self.rules())
        self.place(self.metadata())
        shutil.rmtree(join(self.workspace, "project"))
        self.assertEqual(["MD003"], self.rules())
        from asystem.metadata import write_metadata

        write_metadata(self.workspace, {"schema": 1})
        self.assertEqual(["MD002"], self.rules())

    def test_a_runtime_that_differs_from_the_project_or_has_no_pin_is_a_finding(self):
        from asystem.metadata import lint_metadata

        self.place(self.metadata(runtime={"python": ["polars"]}))
        self.assertEqual(["MD005"], self.rules())
        with open(join(self.project_dir, "project.json")) as manifest_file:
            manifest = json.load(manifest_file)
        with open(join(self.project_dir, "project.json"), "w") as manifest_file:
            json.dump({**manifest, "runtime": {"python": ["polars"]}}, manifest_file)
        self.place(self.metadata())
        pins_path = join(self.workspace, "py_deps.txt")
        source_dir = join(self.workspace, "source")
        served_dir = join(source_dir, "host", "mlserver", "src", "main", "python")
        os.makedirs(served_dir)
        with open(pins_path, "w") as pins_file:
            pins_file.write("numpy==2.0.0\n")
        with open(join(served_dir, "py_deps.txt"), "w") as served_file:
            served_file.write("numpy\n")
        self.assertEqual(["MD005"], [rule for rule, _ in lint_metadata(self.workspace, "wasm", pins_path)])
        with open(pins_path, "a") as pins_file:
            pins_file.write("Polars==2.1.0\n")
        self.assertEqual([], lint_metadata(self.workspace, "wasm", pins_path))
        self.assertEqual(["MD005"], [rule for rule, _ in lint_metadata(self.workspace, "wasm", pins_path, source_dir)])
        with open(join(served_dir, "py_deps.txt"), "a") as served_file:
            served_file.write("polars\n")
        self.assertEqual([], lint_metadata(self.workspace, "wasm", pins_path, source_dir))

    def test_the_changed_command_reports_a_notebook_that_packages_nothing(self):
        import contextlib
        import io

        from asystem.model import main

        pins_path = join(self.workspace, "py_deps.txt")
        with open(pins_path, "w") as pins_file:
            pins_file.write("numpy==2.0.0\n")

        def state():
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main(["changed", self.workspace, pins_path])
            return output.getvalue().strip()

        self.assertEqual("unpackaged", state())
        self.write_notebook(["manifest = package_project(project_dir)\n"], ["# a heading\n"])
        self.assertEqual("changed", state())

    def test_a_project_that_differs_from_its_hash_is_a_finding(self):
        self.place(self.metadata(content_sha256="b" * 64))
        self.assertEqual(["MD003"], self.rules())

    def test_a_target_with_no_wrapper_or_a_passed_target_not_declared_is_a_finding(self):
        self.place(self.metadata(targets=[{"kind": "embedded", "language": "java"}]))
        self.assertEqual(["MD004"], self.rules())
        self.place(self.metadata(passed=[{"kind": "served"}], targets=[{"kind": "embedded", "language": "go"}]))
        self.assertEqual(["MD004"], self.rules())

    def test_a_released_version_must_look_like_a_release_version(self):
        self.place(self.metadata(released_version="10.200.1949"))
        self.assertEqual([], self.rules())
        self.place(self.metadata(released_version="1000"))
        self.assertEqual(["MD002"], self.rules())

    def test_a_snapshot_version_must_look_like_one_and_a_released_project_has_none(self):
        self.place(self.metadata(snapshot_version="10.200.1951-SNAPSHOT"))
        self.assertEqual([], self.rules())
        self.place(self.metadata(snapshot_version="10.200.1951"))
        self.assertEqual(["MD002"], self.rules())
        self.place(self.metadata(snapshot_version="10.200.1951-SNAPSHOT", released_version="10.200.1951"))
        self.assertEqual(["MD002"], self.rules())

    def test_the_inputs_hash_moves_with_code_data_and_pins_but_not_with_markdown(self):
        from asystem.metadata import inputs_sha256

        pins = {"numpy": "2.0"}
        before = inputs_sha256(self.workspace, pins)
        self.write_notebook(["x = 1\n"], ["# another heading\n"])
        self.assertEqual(before, inputs_sha256(self.workspace, pins))
        self.write_notebook(["x = 2\n"], ["# a heading\n"])
        self.assertNotEqual(before, inputs_sha256(self.workspace, pins))
        self.write_notebook(["x = 1\n"], ["# a heading\n"])
        self.assertNotEqual(before, inputs_sha256(self.workspace, {"numpy": "2.1"}))
        with open(join(self.workspace, "data", "training", "2026-01-01_00-00-00", "a.csv"), "a") as data_file:
            data_file.write("2\n")
        self.assertNotEqual(before, inputs_sha256(self.workspace, pins))

    def test_the_pins_are_read_for_the_named_runtime_packages_only(self):
        from asystem.metadata import read_pins

        path = join(tempfile.mkdtemp(), "py_deps_prod.txt")
        with open(path, "w") as pins_file:
            pins_file.write("numpy==2.5.4\nruff==0.17.3\nwasmtime==50.0.1\n# comment\n")
        self.assertEqual({"numpy": "2.5.4", "wasmtime": "50.0.1"}, read_pins(path))


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(contextlib.chdir(fresh_mlruns_dir()))
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        from asystem.release import NOTEBOOK_ROOT

        self.TARGETS = [{"kind": "served"}, {"kind": "embedded", "language": "python"}]

        self.source = tempfile.mkdtemp()
        self.workspace = join(self.source, NOTEBOOK_ROOT, "demo", "replay", "double")
        os.makedirs(join(self.workspace, "data"))
        with open(join(self.workspace, "notebook.ipynb"), "w") as notebook_file:
            json.dump({"cells": [{"cell_type": "code", "source": ["x = 1\n"]}]}, notebook_file)
        self.pins = join(tempfile.mkdtemp(), "pins.txt")
        with open(self.pins, "w") as pins_file:
            pins_file.write("numpy==2.0\n")
        self.consumer = join(self.source, "max", "consumer")
        self.slot = join(self.consumer, "src", "build", "resources", "model")
        os.makedirs(dirname(self.slot))
        shutil.copytree(demo_project("wasm", golden_out=3.5), self.slot)

    def record(self, project_dir=None, targets=None):
        from asystem.metadata import record_project

        return record_project(self.workspace, project_dir or demo_project("wasm"), self.TARGETS if targets is None else targets, self.pins)

    def version_file(self, text):
        path = join(tempfile.mkdtemp(), ".version")
        with open(path, "w") as version_file:
            version_file.write(text)
        return path

    def passed(self):
        from asystem.metadata import read_metadata, write_metadata

        metadata = read_metadata(self.workspace)
        write_metadata(self.workspace, {**metadata, "passed": metadata["targets"]})

    def release(self, version="10.200.1", **options):
        from asystem.release import release_workspaces

        return release_workspaces(self.source, version, "someone", **options)

    def test_a_project_is_recorded_and_a_workspace_with_no_target_is_not(self):
        from asystem.metadata import METADATA_FILE

        recorded = self.record()
        assert recorded is not None
        self.assertEqual("served", recorded["targets"][0]["kind"])
        self.assertTrue(os.path.isfile(join(self.workspace, METADATA_FILE)))
        os.remove(join(self.workspace, METADATA_FILE))
        self.assertIsNone(self.record(targets=[]))
        self.assertFalse(os.path.isfile(join(self.workspace, METADATA_FILE)))

    def test_a_release_needs_every_target_to_have_passed_and_keeps_the_version_while_content_is_unchanged(self):
        from asystem.errors import GateError
        from asystem.metadata import read_metadata

        self.record()
        with self.assertRaises(GateError) as raised:
            self.release()
        self.assertEqual(("Release", "targets"), (raised.exception.stage, raised.exception.gate))
        self.passed()
        self.assertEqual(["demo_replay_double"], self.release())
        self.assertEqual("10.200.1", read_metadata(self.workspace)["released_version"])
        self.record()
        self.release("10.200.2")
        self.assertEqual("10.200.1", read_metadata(self.workspace)["released_version"])
        self.record(project_dir=demo_project("wasm", golden_out=3.5))
        self.assertIsNone(read_metadata(self.workspace)["released_version"])

    def test_an_unreleased_project_carries_the_snapshot_until_its_content_changes_or_it_is_released(self):
        from asystem.metadata import read_metadata, record_project

        def record(project_dir, version):
            return record_project(self.workspace, project_dir, self.TARGETS, self.pins, self.version_file(version))

        self.assertEqual("10.200.1951-SNAPSHOT", record(demo_project("wasm"), "10.200.1951-SNAPSHOT\n")["snapshot_version"])
        self.assertEqual("10.200.1951-SNAPSHOT", record(demo_project("wasm"), "10.200.1952-SNAPSHOT")["snapshot_version"])
        self.assertEqual("10.200.1952-SNAPSHOT", record(demo_project("wasm", golden_out=3.5), "10.200.1952-SNAPSHOT")["snapshot_version"])
        self.assertEqual("10.200.1952-SNAPSHOT", record(demo_project("wasm", golden_out=3.5), "10.200.1953")["snapshot_version"])
        self.assertIsNone(record(demo_project("wasm", golden_out=4.5), "10.200.1953")["snapshot_version"])
        record(demo_project("wasm"), "10.200.1954-SNAPSHOT")
        self.passed()
        self.release()
        self.assertEqual((None, "10.200.1"), (read_metadata(self.workspace)["snapshot_version"], read_metadata(self.workspace)["released_version"]))
        self.assertIsNone(record(demo_project("wasm"), "10.200.1955-SNAPSHOT")["snapshot_version"])

    def test_the_fixtures_module_is_never_released(self):
        from asystem.release import NOTEBOOK_ROOT

        fixture = join(self.source, NOTEBOOK_ROOT, "example", "replay", "double")
        os.makedirs(join(fixture, "data"))
        shutil.copy(join(self.workspace, "notebook.ipynb"), fixture)
        from asystem.metadata import record_project

        record_project(fixture, demo_project("wasm"), self.TARGETS, self.pins)
        self.assertEqual([], self.release())

    def test_a_consumer_embeds_the_released_project_and_is_stale_until_it_does(self):
        from asystem.release import embed_consumer, slot_findings, stale_consumers

        self.record()
        self.passed()
        self.assertEqual("none", embed_consumer(self.consumer, self.source, "demo_replay_double"))
        self.release()
        self.assertEqual([self.consumer], stale_consumers(self.source))
        self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))
        self.assertEqual(("unchanged", []), (embed_consumer(self.consumer, self.source, "demo_replay_double"), stale_consumers(self.source)))
        self.assertEqual([], slot_findings(self.slot, self.source))
        with open(join(self.slot, "project.json"), "a") as manifest_file:
            manifest_file.write(" ")
        self.assertEqual(["CP004"], [rule for rule, _ in slot_findings(self.slot, self.source)])
        self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))

    def test_inputs_change_with_the_pins(self):
        from asystem.metadata import inputs_changed

        self.assertTrue(inputs_changed(self.workspace, self.pins))
        self.record()
        self.assertFalse(inputs_changed(self.workspace, self.pins))
        with open(self.pins, "w") as pins_file:
            pins_file.write("numpy==2.1\n")
        self.assertTrue(inputs_changed(self.workspace, self.pins))

    def test_a_passed_target_is_recorded_once_and_only_when_declared(self):
        from asystem.metadata import read_metadata, record_passed

        self.record()
        record_passed(self.workspace, self.TARGETS[0])
        record_passed(self.workspace, self.TARGETS[0])
        record_passed(self.workspace, {"kind": "embedded", "language": "go"})
        self.assertEqual([self.TARGETS[0]], read_metadata(self.workspace)["passed"])

    def test_an_embedded_only_project_is_not_registered(self):
        from asystem.model import register_preview

        self.assertIsNone(register_preview(demo_project("wasm"), "demo_replay_double", "http://127.0.0.1:9", [{"kind": "embedded", "language": "rust"}]))

    def test_the_signature_may_grow_but_not_change_what_was_released(self):
        from asystem.errors import GateError
        from asystem.metadata import read_metadata, signature_findings

        self.record()
        self.passed()
        self.release()
        released = read_metadata(self.workspace)["released_signature"]
        grown = json.loads(json.dumps(released))
        grown["outputs"].append({**grown["outputs"][0], "name": "demo_extra"})
        grown["inputs"].append({**grown["inputs"][0], "name": "demo_optional", "parameters": {**grown["inputs"][0]["parameters"], "required": False}})
        self.assertEqual([], signature_findings(released, grown))
        for change in (
            lambda signature: signature["outputs"].pop(0),
            lambda signature: signature["inputs"][0].update({"datatype": "INT64"}),
            lambda signature: signature["inputs"].append({**signature["inputs"][0], "name": "demo_new"}),
        ):
            broken = json.loads(json.dumps(released))
            change(broken)
            self.assertTrue(signature_findings(released, broken))
        with self.assertRaises(GateError) as raised:
            self.record(project_dir=self.project_with_signature(lambda signature: signature["outputs"].pop(0)))
        self.assertEqual(("Package", "signature"), (raised.exception.stage, raised.exception.gate))

    def project_with_signature(self, change):
        project_dir = demo_project("wasm")
        with open(join(project_dir, "signature.json")) as signature_file:
            signature = json.load(signature_file)
        change(signature)
        with open(join(project_dir, "signature.json"), "w") as signature_file:
            json.dump(signature, signature_file)
        return project_dir

    def test_publishing_registers_by_content_sets_the_tags_moves_release_and_clears_preview(self):
        from asystem.release import clear_preview, publish_workspace, wait_served
        from mlflow import MlflowClient

        self.record()
        self.passed()
        self.release()
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        from asystem.model import register_project

        previewed = register_project(join(self.workspace, "project"), "demo_replay_double", uri)
        self.assertEqual("published", publish_workspace("demo_replay_double", self.workspace, uri))
        client = MlflowClient(uri, uri)
        model = client.get_registered_model("demo_replay_double")
        self.assertEqual({"release": str(previewed)}, {alias: str(version) for alias, version in model.aliases.items()})
        tags = client.get_model_version("demo_replay_double", previewed).tags
        self.assertEqual("10.200.1", tags["release_version"])
        self.assertEqual("someone", json.loads(tags["metadata"])["released_by"])
        self.assertEqual("published", publish_workspace("demo_replay_double", self.workspace, uri))
        register_project(join(self.workspace, "project"), "demo_replay_double", uri)
        clear_preview("demo_replay_double", uri)
        self.assertNotIn("preview", client.get_registered_model("demo_replay_double").aliases)
        self.assertEqual("unreachable", wait_served("http://127.0.0.1:9", "demo_replay_double", "10.200.1", timeout=1))

    def test_status_names_a_stale_consumer_and_nothing_else_when_everything_matches(self):
        from asystem.release import embed_consumer, status_lines

        self.record()
        self.passed()
        self.release()
        self.assertEqual(["WARN"], [level for level, _ in status_lines(self.source)])
        embed_consumer(self.consumer, self.source, "demo_replay_double")
        self.assertEqual([], status_lines(self.source))


class RegistryToolsTest(unittest.TestCase):
    def test_the_registry_address_must_be_the_proxy_name_and_not_a_published_port(self):
        from asystem.model import registry_address

        self.assertEqual("https://mlflow.proxy.example.com", registry_address("https://mlflow.proxy.example.com"))
        for uri in ("http://macmini-may.local:32413", "", None):
            with self.assertRaises(ValueError):
                registry_address(uri)

    def test_a_finding_maps_to_one_hint_and_a_repeat_is_not_repeated(self):
        from asystem.model import fix_hints

        self.assertEqual(1, len(fix_hints(["PJ003", "PJ013", "PJ015"])))
        self.assertEqual(2, len(fix_hints(["PJ003", "CP004"])))
        self.assertEqual([], fix_hints(["ZZ999"]))


class NotebookLintTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        self.root = tempfile.mkdtemp()
        self.notebook_dir = join(self.root, "demo", "calc", "run")
        os.makedirs(self.notebook_dir)
        with open(join(self.notebook_dir, "plan.md"), "w") as plan:
            plan.write("# run\n")
        self.path = join(self.notebook_dir, "notebook.ipynb")

    def notebook(self, **changes):
        import json

        title = "# demo / calc / run\n\nA calculation.\n\n| Term | In This Notebook |\n|---|---|\n" + "\n".join(f"| **{term}** | Value |" for term in ("Intent", "Project Flavour", "Data Splits"))
        section = "## {}\n\n- **Stage:** {}\n- **Intent:** Do it."
        cells = [
            {"cell_type": "markdown", "metadata": {}, "source": title},
            {"cell_type": "markdown", "metadata": {}, "source": section.format("Setup", "none")},
            {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": 'WORKSPACE = "demo/calc/run"\nMODEL_NAME = "demo_calc_run"\n'},
            {"cell_type": "markdown", "metadata": {}, "source": section.format("Package", "5, package")},
        ]
        notebook = {"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        notebook.update(changes)
        with open(self.path, "w") as notebook_file:
            json.dump(notebook, notebook_file)
        return notebook

    def rules(self):
        from asystem.notebook import lint_notebook

        return sorted({rule for rule, _, _ in lint_notebook(self.path)})

    def test_valid_notebook_has_no_findings(self):
        self.notebook()
        self.assertEqual([], self.rules())

    def test_outputs_are_found_and_stripped(self):
        from asystem.notebook import fix_notebook

        notebook = self.notebook()
        notebook["cells"][2]["outputs"] = [{"output_type": "stream"}]
        notebook["cells"][2]["execution_count"] = 3
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB002"], self.rules())
        self.assertTrue(fix_notebook(self.path))
        self.assertEqual([], self.rules())
        self.assertFalse(fix_notebook(self.path))

    def test_wrong_title_is_found(self):
        notebook = self.notebook()
        notebook["cells"][0]["source"] = notebook["cells"][0]["source"].replace("# demo / calc / run", "# demo / calc / other")
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB003"], self.rules())

    def test_section_without_stage_is_found(self):
        notebook = self.notebook()
        notebook["cells"][3]["source"] = "## Package\n\n- **Intent:** Do it."
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB006"], self.rules())

    def test_sections_out_of_order_are_found(self):
        notebook = self.notebook()
        notebook["cells"][1], notebook["cells"][3] = notebook["cells"][3], notebook["cells"][1]
        self.notebook(cells=notebook["cells"])
        self.assertIn("NB005", self.rules())

    def test_magic_path_and_secret_are_found(self):
        notebook = self.notebook()
        notebook["cells"][2]["source"] += '%matplotlib inline\npath = "/Users/someone/file"\ntoken = "abc"\n'
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB007"], self.rules())

    def test_wrong_model_name_is_found(self):
        notebook = self.notebook()
        notebook["cells"][2]["source"] = 'WORKSPACE = "demo/calc/run"\nMODEL_NAME = "demo"\n'
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB008"], self.rules())

    def test_missing_plan_is_found(self):
        self.notebook()
        os.remove(join(self.notebook_dir, "plan.md"))
        self.assertEqual(["NB010"], self.rules())

    def test_star_import_and_sys_path_are_found(self):
        notebook = self.notebook()
        notebook["cells"][2]["source"] += "from workbench.data import *\nimport sys\nsys.path.append('x')\n"
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB011", "NB012"], self.rules())

    def test_command_line_accepts_new_and_lint_and_the_old_lint_form(self):
        from asystem.notebook import main

        root = tempfile.mkdtemp()
        self.assertEqual(0, main(["new", "egcli", "calc", "run", "static", "--root", root]))
        path = join(root, "egcli", "calc", "run", "notebook.ipynb")
        self.assertEqual(0, main(["lint", path]))
        self.assertEqual(0, main([path]))
        self.assertEqual(1, main(["new", "egcli", "calc", "run", "static", "--root", root]))

    def test_scaffold_passes_every_check_and_refuses_to_overwrite(self):
        from asystem.notebook import lint_notebook, scaffold_notebook
        from asystem.workspace import lint_workspace

        root = tempfile.mkdtemp()
        for flavour in ("static", "wasm"):
            created = scaffold_notebook(root, "example", "calc", flavour, flavour)
            self.assertEqual([], lint_notebook(join(root, "example", "calc", flavour, "notebook.ipynb")))
            self.assertEqual([], lint_workspace(join(root, "example", "calc", flavour)))
            self.assertTrue(all(os.path.exists(path) for path in created))
        with self.assertRaises(ValueError):
            scaffold_notebook(root, "example", "calc", "static", "static")
        with self.assertRaises(ValueError):
            scaffold_notebook(root, "example", "calc", "other", "guess")
        with self.assertRaises(ValueError):
            scaffold_notebook(root, "Bad-Name", "calc", "run", "static")


class WorkspaceLintTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        self.notebook_dir = join(tempfile.mkdtemp(), "demo", "calc", "run")
        os.makedirs(join(self.notebook_dir, "data/golden/2026-01-01_00-00-00"))
        for path in ("notebook.ipynb", "plan.md", "data/golden/2026-01-01_00-00-00/calc_run_golden.csv", "data/golden/.gitkeep"):
            open(join(self.notebook_dir, path), "w").close()

    def rules(self):
        from asystem.workspace import lint_workspace

        return sorted({rule for rule, _ in lint_workspace(self.notebook_dir)})

    def test_valid_workspace_has_no_findings(self):
        self.assertEqual([], self.rules())

    def test_stray_file_and_second_notebook_are_found(self):
        open(join(self.notebook_dir, "notes.txt"), "w").close()
        open(join(self.notebook_dir, "other.ipynb"), "w").close()
        self.assertEqual(["WS002", "WS003"], self.rules())

    def test_two_model_files_are_found(self):
        open(join(self.notebook_dir, "model.wasm"), "w").close()
        self.assertEqual([], self.rules())
        open(join(self.notebook_dir, "model.onnx"), "w").close()
        self.assertEqual(["WS007"], self.rules())

    def test_unknown_label_is_found(self):
        os.makedirs(join(self.notebook_dir, "data/testing"))
        self.assertEqual(["WS004"], self.rules())

    def test_non_timestamp_directory_is_found(self):
        os.makedirs(join(self.notebook_dir, "data/golden/latest"))
        self.assertEqual(["WS005"], self.rules())

    def test_dataset_must_be_a_csv_named_for_the_model_and_notebook(self):
        open(join(self.notebook_dir, "data/golden/2026-01-01_00-00-00/other_golden.csv"), "w").close()
        open(join(self.notebook_dir, "data/golden/2026-01-01_00-00-00/calc_run_golden.txt"), "w").close()
        self.assertEqual(["WS006"], self.rules())

    def test_readings_must_end_with_their_date_range(self):
        os.makedirs(join(self.notebook_dir, "data/training/2026-01-01_00-00-00"))
        path = join(self.notebook_dir, "data/training/2026-01-01_00-00-00")
        open(join(path, "calc_run_voltage.csv"), "w").close()
        self.assertEqual(["WS006"], self.rules())
        os.remove(join(path, "calc_run_voltage.csv"))
        open(join(path, "calc_run_voltage_2026-01-01_2026-01-31.csv"), "w").close()
        self.assertEqual([], self.rules())

    def test_bad_notebook_name_is_found(self):
        bad = join(os.path.dirname(self.notebook_dir), "Run-Two")
        os.rename(self.notebook_dir, bad)
        self.notebook_dir = bad
        self.assertIn("WS001", self.rules())


class ReportTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))

    def test_a_subject_and_its_stages_print_in_the_shape_of_go_test(self):
        import contextlib
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


class SpecSyncTest(unittest.TestCase):
    SPEC = join(ROOT, "rue/datascience/src/build/resources/doc/model.md")

    def setUp(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        with open(self.SPEC) as spec:
            self.spec = spec.read()

    def section(self, heading):
        start = self.spec.index(heading)
        end = self.spec.find("\n#", start + len(heading))
        return self.spec[start : end if end != -1 else len(self.spec)]

    def test_check_identifiers_agree_both_ways(self):
        import re

        in_spec = set(re.findall(r"^\| ((?:PJ|NB|WS|PM|AC|CP|RP|MD)\d{3}) \|", self.spec, re.MULTILINE))
        in_code = set()
        for module in ("model", "notebook", "replay", "workspace", "metadata", "release"):
            with open(join(ROOT, f"all/_/src/build/python/asystem/{module}.py")) as source:
                in_code |= set(re.findall(r'"((?:PJ|NB|WS|PM|AC|CP|RP|MD)\d{3})"', source.read()))
        self.assertTrue(in_spec and in_code)
        self.assertEqual(in_spec, in_code)

    def test_every_requirement_is_covered_by_a_check_or_by_review(self):
        import re

        enforced = {}
        for identifier, requirements in re.findall(r"^\| ((?:PJ|NB|WS|PM|AC|CP|RP|MD)\d{3}) \|.*\| (R[0-9, R]+) \|$", self.spec, re.MULTILINE):
            for requirement in re.findall(r"R\d+", requirements):
                enforced.setdefault(requirement, set()).add(identifier)
        coverage = {}
        for requirement, checked_by in re.findall(r"^\| (R\d+) \| ([^|]+) \|$", self.section("### 10.3 Coverage of the requirements"), re.MULTILINE):
            coverage[requirement] = set() if checked_by.strip() == "Review" else {item.strip() for item in checked_by.split(",")}
        defined = set(re.findall(r"^\| (R\d+) \| (?:Standard|Parity|Delivery|Change) \|", self.spec, re.MULTILINE))
        self.assertTrue(enforced and coverage and defined)
        self.assertEqual(defined, set(coverage))
        self.assertEqual({requirement: ids for requirement, ids in coverage.items() if ids}, enforced)

    def test_flavours_splits_and_sections_agree(self):
        import re

        from asystem.model import PROJECT_FLAVOURS, PROJECT_SPLITS
        from asystem.notebook import NOTEBOOK_SECTIONS

        flavours = re.findall(r"^\| `(\w+)` \|", self.section("### 3.2 Flavours"), re.MULTILINE)
        splits = re.findall(r"^\| `(\w+)` \|", self.section("### 6.3 Splits"), re.MULTILINE)
        sections = re.findall(r"^\| ([A-Z][A-Za-z ]+?) \| (?:None|\d) \|", self.section("### 6.7 Notebook style guide"), re.MULTILINE)
        self.assertTrue(flavours and splits and sections)
        self.assertEqual(sorted(PROJECT_FLAVOURS), sorted(flavours))
        self.assertEqual(sorted(PROJECT_SPLITS), sorted(splits))
        self.assertEqual(list(NOTEBOOK_SECTIONS), sections)


def demo_project(*arguments, **options):
    sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
    from asystem.demo import demo_project as build

    return build(*arguments, **options)


def fresh_mlruns_dir():
    directory = join(ROOT, "all/_/target/mlruns-test")
    shutil.rmtree(directory, ignore_errors=True)
    os.makedirs(directory)
    return directory
