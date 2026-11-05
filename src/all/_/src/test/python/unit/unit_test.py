import contextlib
import os
import re
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


if __name__ == "__main__":
    unittest.main()
