import contextlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from os.path import dirname, isdir, join, realpath

ROOT = realpath(join(dirname(__file__), "../../../../../.."))
SCRIPT = join(ROOT, "mad/postgres/src/main/resources/backup.sh")
RESTORE = join(ROOT, "max/letsencrypt/src/main/resources/restore.sh")
BASH = "/opt/homebrew/bin/bash" if os.path.exists("/opt/homebrew/bin/bash") else "bash"
GNU = {"find": "gfind", "date": "gdate"}


class BackupWrapperTest(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.bin = join(self.workdir, "bin")
        os.makedirs(self.bin)
        for name, target in GNU.items():
            found = subprocess.run(["which", target], capture_output=True, text=True).stdout.strip()
            if found:
                os.symlink(found, join(self.bin, name))
        self.latest = join(self.workdir, "postgres", "latest")
        self.root = join(self.workdir, "postgres", "backup")
        os.makedirs(self.latest)
        os.makedirs(self.root)

    def shell(self, body, **env):
        script = textwrap.dedent(
            """
            set -o pipefail
            source "{script}"
            {body}
            """
        ).format(script=SCRIPT, body=textwrap.dedent(body))
        environment = dict(os.environ, PATH=self.bin + ":" + os.environ["PATH"], BACKUP_SOURCE_PATH=self.latest, **{k: str(v) for k, v in env.items()})
        return subprocess.run([BASH, "-c", script], capture_output=True, text=True, env=environment)

    def run_dir(self, stamp, files=None):
        path = join(self.root, stamp)
        os.makedirs(path, exist_ok=True)
        for name, content in (files or {}).items():
            with open(join(path, name), "wb") as handle:
                handle.write(content)
        return path

    def artifact(self, stamp, kind="full", extension="tar.gz"):
        return f"postgres_at_{stamp}_from_10.200.1_{kind}.{extension}"

    def manifest(self, stamp, units, verdict="success", parent="", kind="full"):
        meta = join(self.run_dir(stamp), ".meta")
        os.makedirs(meta, exist_ok=True)
        body = ",\n".join(f'    "{unit}": {count}' for unit, count in units.items())
        with open(join(meta, "manifest.json"), "w") as handle:
            handle.write(
                f'{{\n  "kind": "{kind}",\n  "parent": "{parent}",\n  "source_version": "x",\n  "verdict": "{verdict}",\n  "accepted": false,\n  "baseline": "",\n  "evidence": [\n  ],\n  "fingerprint": {{\n{body}\n  }}\n}}\n'
            )

    def test_fingerprint_of_a_tar_sums_bytes_per_declared_include(self):
        source = join(self.workdir, "src")
        os.makedirs(join(source, "db"))
        os.makedirs(join(source, "other"))
        for path, size in (("db/a.db", 100), ("db/b.db", 50), ("other/c.txt", 7), ("top.txt", 3)):
            with open(join(source, path), "wb") as handle:
                handle.write(b"x" * size)
        archive = join(self.workdir, "a_full.tar.gz")
        subprocess.run(["tar", "-czf", archive, "-C", source, "db", "other", "top.txt"], check=True)
        done = self.shell(f'BACKUP_FINGERPRINT_INCLUDES=("db"); backup_fingerprinted "{archive}"')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split("\n")[:-1], ["db 150", "other 7", "top.txt 3"])

    def test_fingerprint_of_a_zip_counts_bytes_per_entry_including_names_with_spaces(self):
        archive = join(self.workdir, "z_full.zip")
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("coordinator_backup.json", "x" * 40)
            handle.writestr("a name with spaces.json", "y" * 9)
        done = self.shell(f'backup_fingerprinted "{archive}"')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(sorted(done.stdout.split("\n")[:-1]), ["a name with spaces.json 9", "coordinator_backup.json 40"])

    def test_fingerprint_of_a_postgres_dump_counts_copy_rows_per_database_table(self):
        dump = join(self.workdir, "d_full.sql.gz")
        text = "\\connect hass\n\nCOPY public.states (a, b) FROM stdin;\n1\t2\n3\t4\n5\t6\n\\.\n\nCOPY public.events (a) FROM stdin;\n\\.\n\\connect other\nCOPY public.t (a) FROM stdin;\n9\n\\.\n"
        subprocess.run(f"gzip -c > {dump}", shell=True, input=text.encode(), check=True)
        done = self.shell(f'backup_fingerprinted "{dump}"')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split("\n")[:-1], ["hass.public.events 0", "hass.public.states 3", "other.public.t 1"])

    def test_fingerprint_of_a_mariadb_dump_sums_bytes_per_database(self):
        dump = join(self.workdir, "m_full.sql.gz")
        text = "-- Current Database: `alpha`\nCREATE TABLE t;\nINSERT 1;\n-- Current Database: `beta`\nINSERT 2;\n"
        subprocess.run(f"gzip -c > {dump}", shell=True, input=text.encode(), check=True)
        done = self.shell(f'backup_fingerprinted "{dump}"')
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = dict(line.rsplit(" ", 1) for line in done.stdout.split("\n")[:-1])
        self.assertEqual(set(lines), {"alpha", "beta"})
        self.assertEqual(int(lines["beta"]), len("INSERT 2;") + 1)

    def regress(self, current, baseline_units, **env):
        self.manifest("2026-10-01_01-00-00", baseline_units)
        body = f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; backup_regression "{current}" "2026-10-01_01-00-00"; echo "$BACKUP_INTERNAL_VERDICT"; printf "%s\\n" "${{BACKUP_INTERNAL_EVIDENCE[@]}}"'
        return self.shell(body, **env)

    def test_a_missing_durable_unit_regresses_with_evidence(self):
        done = self.regress("a 10", {"a": 10, "b": 5})
        lines = done.stdout.split("\n")
        self.assertEqual(lines[0], "regressed")
        self.assertIn("missing [b] was [5]", done.stdout)
        self.assertIn("regressed [1] closed units missing", done.stdout)

    def test_a_total_drop_beyond_the_threshold_regresses_and_zero_disables_it(self):
        self.assertEqual(self.regress("a 70", {"a": 100}).stdout.split("\n")[0], "regressed")
        self.assertEqual(self.regress("a 85", {"a": 100}).stdout.split("\n")[0], "success")
        self.assertEqual(self.regress("a 70", {"a": 100}, BACKUP_SHRINK_PERCENT=0).stdout.split("\n")[0], "success")

    def test_growth_and_new_units_never_regress(self):
        self.assertEqual(self.regress("a 200\nnew 5", {"a": 100}).stdout.split("\n")[0], "success")

    def test_no_baseline_is_success(self):
        done = self.shell(f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; backup_regression "a 1" ""; echo "$BACKUP_INTERNAL_VERDICT"')
        self.assertEqual(done.stdout.strip(), "success")

    def test_a_regressed_run_is_not_a_baseline(self):
        self.manifest("2026-10-01_01-00-00", {"a": 100})
        self.manifest("2026-10-02_01-00-00", {}, verdict="regressed")
        done = self.shell(f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; backup_baseline "2026-10-03_01-00-00"')
        self.assertEqual(done.stdout.strip(), "2026-10-01_01-00-00")

    def test_manifested_writes_kind_parent_fingerprint_and_the_regressed_verdict(self):
        self.run_dir("2026-10-01_01-00-00", {self.artifact("2026-10-01_01-00-00"): b"x"})
        self.manifest("2026-10-01_01-00-00", {"a": 100})
        stamp = "2026-10-02_01-00-00"
        self.run_dir(stamp, {self.artifact(stamp, "delta"): b"x"})
        fingerprint = join(self.workdir, "fp.sh")
        with open(fingerprint, "w") as handle:
            handle.write('backup_fingerprinted() { echo "a 1"; }\n')
        body = """
            source "{fp}"
            BACKUP_INTERNAL_ROOT_DIR="{root}"; BACKUP_RUN_TIMESTAMP="{stamp}"
            BACKUP_TARGET_PATH="{root}/{stamp}/{name}"
            backup_manifested
            """.format(fp=fingerprint, root=self.root, stamp=stamp, name=self.artifact(stamp, "delta"))
        done = self.shell(body)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(join(self.root, stamp, ".meta", "manifest.json")) as handle:
            text = handle.read()
        self.assertIn('"kind": "delta"', text)
        self.assertIn('"parent": "2026-10-01_01-00-00"', text)
        self.assertIn('"verdict": "regressed"', text)
        self.assertIn('"a": 1', text)
        self.assertIn("total [-99]% beyond [20]%", text)
        self.assertIn("Backup regressed", done.stderr)

    def test_accepting_a_regressed_run_releases_it(self):
        self.manifest("2026-10-02_01-00-00", {"a": 1}, verdict="regressed")
        done = self.shell(
            f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; backup_accepted "2026-10-02_01-00-00"; backup_manifest_field "2026-10-02_01-00-00" verdict; backup_manifest_field "2026-10-02_01-00-00" accepted'
        )
        self.assertEqual(done.stdout.split("\n")[1:3], ["success", "true"])

    def test_shadow_prune_removes_a_run_both_windows_would_delete(self):
        old, newest = "2026-01-01_01-00-00", "2026-10-28_01-00-00"
        for stamp in (old, newest):
            self.run_dir(stamp, {self.artifact(stamp): b"x"})
        done = self.shell(f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; BACKUP_RETAIN_DAYS=1; backup_pruned')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(isdir(join(self.root, old)))
        self.assertTrue(isdir(join(self.root, newest)))
        self.assertIn(f"Pruned backup [{old}]", done.stdout)
        self.assertNotIn("Prune disagreement", done.stdout)

    def test_shadow_prune_disagreement_holds_the_run_the_new_window_keeps(self):
        old, newest = "2026-10-20_01-00-00", "2026-10-28_01-00-00"
        for stamp in (old, newest):
            self.run_dir(stamp, {self.artifact(stamp): b"x"})
        body = f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; BACKUP_RETAIN_DAYS=1; BACKUP_NEXT_RETAIN_DAYS=10000; backup_pruned'
        done = self.shell(body)
        self.assertIn(f"Prune disagreement run [{old}] old [delete] new [keep]", done.stdout)
        self.assertTrue(isdir(join(self.root, old)))

    def test_a_delta_is_refused_without_a_local_full_to_hang_off(self):
        stamp = "2026-10-28_01-00-00"
        done = self.shell(f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; BACKUP_RUN_TIMESTAMP="{stamp}"; backup_target "$BACKUP_DELTA_SUFFIX" tar.gz; echo "status=$?"')
        self.assertIn("status=1", done.stdout)
        self.assertIn("no full backup is held locally", done.stderr)
        self.assertFalse(isdir(join(self.root, stamp)))

    def test_a_delta_is_named_when_a_local_full_exists(self):
        full, stamp = "2026-10-27_01-00-00", "2026-10-28_01-00-00"
        self.run_dir(full, {self.artifact(full): b"x"})
        done = self.shell(f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; BACKUP_RUN_TIMESTAMP="{stamp}"; backup_target "$BACKUP_DELTA_SUFFIX" tar.gz; echo "status=$?"; echo "$BACKUP_TARGET_PATH"')
        self.assertIn("status=0", done.stdout)
        self.assertIn("_delta.tar.gz", done.stdout)

    def test_the_anchor_chain_survives_when_the_newest_run_is_regressed(self):
        full, delta, bad = "2026-10-01_01-00-00", "2026-10-02_01-00-00", "2026-10-28_01-00-00"
        self.run_dir(full, {self.artifact(full): b"x"})
        self.run_dir(delta, {self.artifact(delta, "delta"): b"x"})
        self.run_dir(bad, {self.artifact(bad): b"x"})
        self.manifest(full, {"a": 1})
        self.manifest(delta, {"a": 1}, parent=full, kind="delta")
        self.manifest(bad, {}, verdict="regressed")
        body = f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; BACKUP_RETAIN_DAYS=1; backup_pruned'
        done = self.shell(body)
        self.assertIn(f"Prune disagreement run [{delta}]", done.stdout)
        self.assertTrue(isdir(join(self.root, delta)))
        self.assertTrue(isdir(join(self.root, full)))

    def test_a_delta_keeps_its_manifest_parent_even_outside_the_window(self):
        full, delta = "2026-01-01_01-00-00", "2026-10-28_01-00-00"
        self.run_dir(full, {self.artifact(full): b"x"})
        self.run_dir(delta, {self.artifact(delta, "delta"): b"x"})
        self.manifest(full, {"a": 1})
        self.manifest(delta, {"a": 1}, parent=full, kind="delta")
        body = f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; BACKUP_RETAIN_DAYS=1; backup_pruned'
        done = self.shell(body)
        self.assertIn(f"Prune disagreement run [{full}]", done.stdout)
        self.assertTrue(isdir(join(self.root, full)))

    def test_gfs_prune_still_applies_the_tiers_and_removes_the_rest(self):
        stamps = [f"2026-0{month}-01_01-00-00" for month in range(1, 9)]
        for stamp in stamps:
            self.run_dir(stamp, {self.artifact(stamp): b"x"})
        body = f'BACKUP_INTERNAL_ROOT_DIR="{self.root}"; BACKUP_KEEP_DAILY=2; BACKUP_KEEP_WEEKLY=1; BACKUP_KEEP_MONTHLY=1; backup_pruned_gfs'
        done = self.shell(body)
        self.assertEqual(done.returncode, 0, done.stderr)
        remaining = sorted(os.listdir(self.root))
        self.assertIn(stamps[-1], remaining)
        self.assertIn(stamps[-2], remaining)
        self.assertLess(len(remaining), len(stamps))
        self.assertIn("grandfather-father-son", done.stdout)


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

    def test_full_forces_a_full_and_skips_the_throttle(self):
        root = self.generated_backup(f'backup_written() {{ echo "full=${{BACKUP_FORCE_FULL}} skip=${{BACKUP_SKIP_HOURS}}" > "{tempfile.gettempdir()}/full-probe"; return 1; }}\n')
        probe = join(tempfile.gettempdir(), "full-probe")
        self.run_generated(root)
        with open(probe) as handle:
            self.assertEqual(handle.read().strip(), "full=false skip=1")
        self.run_generated(root, "--full")
        with open(probe) as handle:
            self.assertEqual(handle.read().strip(), "full=true skip=0")
        os.remove(probe)

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
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        from asystem.model import build_signature, golden_document, golden_step, signature_input, signature_output, signature_state

        self.project_dir = join(tempfile.mkdtemp(), "project")
        self.signature = build_signature(
            "demo_calc",
            ["1"],
            [signature_input("demo_clock_seconds", "seconds", "Time of the call."), signature_input("demo_state_in", "state", "Carried state.", required=False, shape=[-1])],
            [signature_output("demo_limit_seconds", "seconds", "A limit."), signature_output("demo_state_out", "state", "Next state.", required=False, shape=[-1])],
            state=[signature_state("last_seconds", "seconds", "The previous call.")],
        )
        steps = [
            golden_step(self.signature, "1", "s-0", {"demo_clock_seconds": 10.0}, {"demo_limit_seconds": 5}),
            golden_step(self.signature, "1", "s-1", {"demo_clock_seconds": 11.0, "demo_state_in": [10.0]}, {"demo_limit_seconds": 5}),
            golden_step(self.signature, "1", "s-2", {"demo_state_in": [10.0]}, error="signature"),
        ]
        self.golden = golden_document("1", [("calls", steps)])

    def write(self, **overrides):
        from asystem.model import write_project

        arguments = {
            "project_dir": self.project_dir,
            "name": "demo_calc",
            "model_version": "1",
            "flavor": "static",
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
        self.assertEqual("static", self.write()["flavor"])
        self.assertEqual([], self.rules())

    def test_tampered_file_is_found(self):
        self.write()
        with open(join(self.project_dir, "golden.json"), "a") as golden:
            golden.write(" ")
        from asystem.model import lint_project

        self.assertEqual(["PJ003"], sorted({rule for rule, _ in lint_project(self.project_dir)}))

    def test_unknown_flavor_and_source_are_found(self):
        self.assertEqual(["PJ002"], self.rules(flavor="guess", provenance={"source": "guess", "inputs": []}))

    def test_provenance_inputs_must_be_a_list(self):
        self.assertEqual(["PJ002"], self.rules(provenance={"source": "manual"}))

    def test_model_flavor_needs_its_file(self):
        self.assertEqual(["PJ003"], self.rules(flavor="wasm", provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"}))

    def test_model_file_is_copied_into_the_project_and_hashed(self):
        model_path = join(tempfile.mkdtemp(), "model.py")
        with open(model_path, "w") as model_file:
            model_file.write("VALUE = 1\n")
        manifest = self.write(flavor="pyfunc", model_path=model_path, constants=None, provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"})
        self.assertEqual("model.py", manifest["files"]["model"]["path"])
        self.assertTrue(os.path.isfile(join(self.project_dir, "model.py")))

    def test_implementation_must_say_something(self):
        for implementation in ("demo", "TBD", "to be determined", "", None):
            self.assertEqual(["PJ002", "PJ003"], self.rules(flavor="wasm", provenance={"source": "manual", "inputs": [], "implementation": implementation}))

    def test_pyfunc_project_is_registered_as_a_pyfunc_model(self):
        from asystem.model import build_signature, golden_document, golden_step, pull_model, register_project, signature_input, signature_output

        signature = build_signature("demo_calc", ["1"], [signature_input("demo_in_seconds", "seconds", "Input.")], [signature_output("demo_out_seconds", "seconds", "Output.")])
        golden = golden_document("1", [("calls", [golden_step(signature, "1", "s-0", {"demo_in_seconds": 1.0}, {"demo_out_seconds": 2.0}), golden_step(signature, "1", "s-1", {}, error="signature")])])
        model_path = join(tempfile.mkdtemp(), "model.py")
        with open(model_path, "w") as model_file:
            model_file.write(
                "import pandas as pd\nfrom mlflow.models import set_model\nfrom mlflow.pyfunc import PythonModel\n\n\n"
                "class Demo(PythonModel):\n    def predict(self, context, model_input, params=None):\n"
                '        return pd.DataFrame({"demo_out_seconds": model_input["demo_in_seconds"] * 2})\n\n\nset_model(Demo())\n'
            )
        self.write(
            flavor="pyfunc", model_path=model_path, signature=signature, golden=golden, constants=None, provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"}
        )
        root_dir = tempfile.mkdtemp()
        uri = f"sqlite:///{join(root_dir, 'mlflow.db')}"
        import mlflow.pyfunc

        version = register_project(self.project_dir, "demo_calc", uri)
        mlflow.set_tracking_uri(uri)
        loaded = mlflow.pyfunc.load_model("models:/demo_calc@candidate")
        self.assertEqual([2.0], list(loaded.predict({"demo_in_seconds": [1.0]})["demo_out_seconds"]))
        self.assertEqual("pyfunc", pull_model("demo_calc", "candidate", join(root_dir, "pulled"), uri)["flavor"])
        self.assertEqual("1", str(version))

    def test_pyfunc_registration_refuses_a_state_vector_signature(self):
        from asystem.model import register_project

        model_path = join(tempfile.mkdtemp(), "model.py")
        with open(model_path, "w") as model_file:
            model_file.write("VALUE = 1\n")
        self.write(flavor="pyfunc", model_path=model_path, constants=None, provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"})
        with self.assertRaises(ValueError):
            register_project(self.project_dir, "demo_calc", f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}")

    def acceptance(self, rows=None, passing=True):
        from asystem.model import acceptance_row, build_acceptance, evaluate_acceptance

        dataset_dir = join(tempfile.mkdtemp(), "2026-11-03_10-00-00")
        os.makedirs(dataset_dir)
        dataset = join(dataset_dir, "demo_calc_limit_2026-11-01_2026-11-02.csv")
        with open(dataset, "w") as dataset_file:
            dataset_file.write("a,b\n1,2\n")
        acceptance = build_acceptance(rows or [acceptance_row("backtest", "demo_limit_seconds", "rmse", "<=", 1.0, "the guard tolerates one second")])
        predicted = [5.0, 5.5] if passing else [5.0, 9.0]
        evaluation = evaluate_acceptance(acceptance, {"backtest": {"demo_limit_seconds": ([5.0, 5.0], predicted)}}, {"backtest": [dataset]})
        return acceptance, evaluation

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

    def test_acceptance_is_evaluated_and_a_missing_measure_fails(self):
        _, evaluation = self.acceptance()
        self.assertTrue(evaluation["passed"])
        self.assertEqual("2026-11-03_10-00-00/demo_calc_limit_2026-11-01_2026-11-02.csv", evaluation["datasets"]["backtest"][0]["path"])
        _, evaluation = self.acceptance(passing=False)
        self.assertFalse(evaluation["passed"])
        from asystem.model import acceptance_row

        _, evaluation = self.acceptance(
            rows=[acceptance_row("backtest", "demo_limit_seconds", "rmse", "<=", 1.0, "x"), acceptance_row("validation", "demo_limit_seconds", "mae", "<=", 1.0, "x", gate=False)]
        )
        self.assertFalse(evaluation["passed"] and evaluation["results"][1]["passed"])
        self.assertTrue(evaluation["passed"])

    def test_project_with_acceptance_has_no_findings(self):
        acceptance, evaluation = self.acceptance()
        manifest = self.write(acceptance=acceptance, evaluation=evaluation)
        self.assertEqual(["acceptance", "evaluation", "golden", "signature"], sorted(manifest["files"]))
        self.assertEqual([], self.rules(acceptance=acceptance, evaluation=evaluation))

    def test_acceptance_and_evaluation_come_together(self):
        acceptance, _ = self.acceptance()
        with self.assertRaises(ValueError):
            self.write(acceptance=acceptance)

    def test_every_output_needs_a_gating_row(self):
        from asystem.model import acceptance_row

        acceptance, evaluation = self.acceptance(rows=[acceptance_row("backtest", "demo_limit_seconds", "rmse", "<=", 1.0, "x", gate=False)])
        self.assertEqual(["AC001"], self.rules(acceptance=acceptance, evaluation=evaluation))

    def test_acceptance_rows_are_checked(self):
        from asystem.model import acceptance_row

        for row in (
            acceptance_row("training", "demo_limit_seconds", "rmse", "<=", 1.0, "x"),
            acceptance_row("backtest", "demo_limit_seconds", "median", "<=", 1.0, "x"),
            acceptance_row("backtest", "demo_limit_seconds", "rmse", "<", 1.0, "x"),
            acceptance_row("backtest", "demo_limit_seconds", "rmse", "<=", "1", "x"),
            acceptance_row("backtest", "demo_limit_seconds", "rmse", "<=", 1.0, " "),
            acceptance_row("backtest", "demo_other_seconds", "rmse", "<=", 1.0, "x"),
        ):
            acceptance, evaluation = (
                self.acceptance(rows=[row, acceptance_row("backtest", "demo_limit_seconds", "mae", "<=", 1.0, "x")])
                if row["metric"] != "median" and row["op"] != "<" and row["bound"] == 1.0
                else (None, None)
            )
            if acceptance is None:
                acceptance = {"rows": [row, acceptance_row("backtest", "demo_limit_seconds", "mae", "<=", 1.0, "x")]}
                evaluation = {"acceptance_sha256": "", "datasets": {"backtest": []}, "results": [], "passed": True}
            self.assertIn("AC002", self.rules(acceptance=acceptance, evaluation=evaluation), row)

    def test_evaluation_must_belong_to_the_acceptance(self):
        acceptance, evaluation = self.acceptance()
        other, _ = self.acceptance(rows=[__import__("asystem.model", fromlist=["x"]).acceptance_row("backtest", "demo_limit_seconds", "rmse", "<=", 2.0, "x")])
        self.assertIn("AC003", self.rules(acceptance=other, evaluation=evaluation))
        del evaluation["datasets"]["backtest"]
        self.assertIn("AC003", self.rules(acceptance=acceptance, evaluation=evaluation))

    def test_promotion_needs_acceptance_passed(self):
        from asystem.model import check_acceptance

        self.write()
        self.assertEqual(["PM004"], [rule for rule, _ in check_acceptance(self.project_dir)])
        acceptance, evaluation = self.acceptance(passing=False)
        self.write(acceptance=acceptance, evaluation=evaluation)
        self.assertEqual(["PM004"], [rule for rule, _ in check_acceptance(self.project_dir)])
        acceptance, evaluation = self.acceptance()
        self.write(acceptance=acceptance, evaluation=evaluation)
        self.assertEqual([], check_acceptance(self.project_dir))

    def test_registration_logs_metrics_datasets_and_the_verdict(self):
        import mlflow
        from asystem.model import register_project

        acceptance, evaluation = self.acceptance()
        self.write(acceptance=acceptance, evaluation=evaluation)
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        register_project(self.project_dir, "demo_calc", uri)
        mlflow.set_tracking_uri(uri)
        run = mlflow.search_runs(experiment_names=["demo_calc"], output_format="list")[0]
        self.assertEqual("passed", run.data.tags["acceptance"])
        self.assertAlmostEqual(0.5 / 2**0.5, run.data.metrics["backtest/demo_limit_seconds/rmse"])
        self.assertEqual("backtest", run.inputs.dataset_inputs[0].tags[0].value)

    def test_static_flavor_refuses_a_model_file(self):
        with self.assertRaises(ValueError):
            self.write(model_path=join(self.project_dir, "signature.json"))

    def test_model_flavor_needs_its_implementation(self):
        self.assertEqual(["PJ002", "PJ003"], self.rules(flavor="wasm"))

    def test_name_must_match_signature_and_style(self):
        self.assertIn("PJ004", self.rules(name="Demo-Calc"))

    def test_signature_version_and_model_version_are_checked(self):
        self.assertEqual(["PJ005"], self.rules(model_version="2", golden={**self.golden, "model_version": "2"}))

    def test_output_must_be_module_prefixed_with_a_unit_suffix(self):
        self.signature["outputs"][0]["name"] = "other_limit"
        self.assertIn("PJ007", self.rules(constants={"other_limit": 5}))

    def test_constant_outside_signature_is_found(self):
        self.assertIn("PJ008", self.rules(constants={"demo_limit_seconds": 5, "demo_misspelt_seconds": 1}))

    def test_static_must_cover_required_outputs(self):
        self.assertIn("PJ008", self.rules(constants={}))

    def test_golden_version_mismatch_is_found(self):
        self.assertEqual(["PJ009"], self.rules(golden={**self.golden, "model_version": "2"}))

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
        manifest = package_project(self.project_dir, "demo_calc", "1", "static", self.signature, rows, {"source": "manual", "inputs": []}, constants={"demo_limit_seconds": 5})
        self.assertEqual("static", manifest["flavor"])
        self.assertEqual([], lint_project(self.project_dir))

    def test_diff_signature_names_what_changed(self):
        from asystem.model import diff_signature

        other = json.loads(json.dumps(self.signature))
        other["inputs"][0]["parameters"]["unit"] = "minutes"
        del other["outputs"][1]
        other["parameters"]["state"] = []
        differences = diff_signature(self.signature, other)
        self.assertTrue(any("input [demo_clock_seconds] changed" in item for item in differences))
        self.assertTrue(any("output [demo_state_out] is missing" in item for item in differences))
        self.assertTrue(any("state slots changed" in item for item in differences))
        self.assertEqual([], diff_signature(self.signature, {**self.signature, "versions": ["9"]}))

    def test_render_rust_and_go_name_every_tensor_with_optional_fields(self):
        from asystem.model import render_go, render_rust

        rust = render_rust(self.signature)
        self.assertIn("pub demo_clock_seconds: f64,", rust)
        self.assertIn("pub demo_state_in: Option<Vec<f64>>,", rust)
        self.assertIn('pub const REQUIRED_OUTPUT_NAMES: &[&str] = &["demo_limit_seconds"];', rust)
        go = render_go(self.signature, "model")
        self.assertIn("DemoClockSeconds", go)
        self.assertIn("[]float64", go)
        self.assertIn('`json:"demo_clock_seconds"`', go)

    def test_gate_must_cover_every_host_and_architecture_for_this_project(self):
        from asystem.model import check_gate

        gate = {"project_sha256": "abc", "results": [{"host": "python", "arch": "x86_64", "passed": True}, {"host": "python", "arch": "aarch64", "passed": False}]}
        findings = check_gate(gate, "abc", ["python"], ["x86_64", "aarch64"], "graham")
        self.assertEqual(["PM001"], [rule for rule, _ in findings])
        self.assertEqual(["PM002", "PM003"], sorted(rule for rule, _ in check_gate({**gate, "project_sha256": "xyz"}, "abc", ["python"], ["x86_64"], "")))
        self.assertEqual([], check_gate(gate, "abc", ["python"], ["x86_64"], "graham"))

    def test_same_signature_ignores_only_the_versions(self):
        from asystem.model import same_signature

        other = {**self.signature, "versions": ["2"]}
        self.assertTrue(same_signature(self.signature, other))
        other["outputs"] = other["outputs"][:1]
        self.assertFalse(same_signature(self.signature, other))

    def test_registered_name_and_check_name(self):
        from asystem.model import check_name, registered_name

        self.assertEqual("rackmains_ups_battery", registered_name("rackmains", "ups", "battery"))
        self.assertEqual("example_static_constant", registered_name("example", "static", "constant"))
        with self.assertRaises(ValueError):
            check_name("Bad-Name")


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

        title = "# demo / calc / run\n\nA calculation.\n\n| Term | In This Notebook |\n|---|---|\n" + "\n".join(f"| **{term}** | Value |" for term in ("Intent", "Project Flavor", "Data Splits"))
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
        notebook["cells"][2]["source"] += "from library.data import *\nimport sys\nsys.path.append('x')\n"
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
        for flavor in ("static", "wasm"):
            created = scaffold_notebook(root, "example", "calc", flavor, flavor)
            self.assertEqual([], lint_notebook(join(root, "example", "calc", flavor, "notebook.ipynb")))
            self.assertEqual([], lint_workspace(join(root, "example", "calc", flavor)))
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
        self.model_dir = join(tempfile.mkdtemp(), "demo", "calc", "run")
        os.makedirs(join(self.model_dir, "data/golden/2026-01-01_00-00-00"))
        for path in ("notebook.ipynb", "plan.md", "data/golden/2026-01-01_00-00-00/calc_run_golden.csv", "data/golden/.gitkeep"):
            open(join(self.model_dir, path), "w").close()

    def rules(self):
        from asystem.workspace import lint_workspace

        return sorted({rule for rule, _ in lint_workspace(self.model_dir)})

    def test_valid_workspace_has_no_findings(self):
        self.assertEqual([], self.rules())

    def test_stray_file_and_second_notebook_are_found(self):
        open(join(self.model_dir, "notes.txt"), "w").close()
        open(join(self.model_dir, "other.ipynb"), "w").close()
        self.assertEqual(["WS002", "WS003"], self.rules())

    def test_two_model_files_are_found(self):
        open(join(self.model_dir, "model.wasm"), "w").close()
        self.assertEqual([], self.rules())
        open(join(self.model_dir, "model.onnx"), "w").close()
        self.assertEqual(["WS007"], self.rules())

    def test_unknown_label_is_found(self):
        os.makedirs(join(self.model_dir, "data/testing"))
        self.assertEqual(["WS004"], self.rules())

    def test_non_timestamp_directory_is_found(self):
        os.makedirs(join(self.model_dir, "data/golden/latest"))
        self.assertEqual(["WS005"], self.rules())

    def test_dataset_must_be_a_csv_named_for_the_model_and_notebook(self):
        open(join(self.model_dir, "data/golden/2026-01-01_00-00-00/other_golden.csv"), "w").close()
        open(join(self.model_dir, "data/golden/2026-01-01_00-00-00/calc_run_golden.txt"), "w").close()
        self.assertEqual(["WS006"], self.rules())

    def test_readings_must_end_with_their_date_range(self):
        os.makedirs(join(self.model_dir, "data/training/2026-01-01_00-00-00"))
        path = join(self.model_dir, "data/training/2026-01-01_00-00-00")
        open(join(path, "calc_run_voltage.csv"), "w").close()
        self.assertEqual(["WS006"], self.rules())
        os.remove(join(path, "calc_run_voltage.csv"))
        open(join(path, "calc_run_voltage_2026-01-01_2026-01-31.csv"), "w").close()
        self.assertEqual([], self.rules())

    def test_bad_notebook_name_is_found(self):
        bad = join(os.path.dirname(self.model_dir), "Run-Two")
        os.rename(self.model_dir, bad)
        self.model_dir = bad
        self.assertIn("WS001", self.rules())


class SpecSyncTest(unittest.TestCase):
    SPEC = join(ROOT, "may/mlflow/src/build/resources/doc/spec.md")

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

        in_spec = set(re.findall(r"^\| ((?:PJ|NB|WS|PM|AC)\d{3}) \|", self.spec, re.MULTILINE))
        in_code = set()
        for module in ("model", "notebook", "workspace"):
            with open(join(ROOT, f"all/_/src/build/python/asystem/{module}.py")) as source:
                in_code |= set(re.findall(r'"((?:PJ|NB|WS|PM|AC)\d{3})"', source.read()))
        self.assertTrue(in_spec and in_code)
        self.assertEqual(in_spec, in_code)

    def test_every_requirement_is_covered_by_a_check_or_by_review(self):
        import re

        enforced = {}
        for identifier, requirements in re.findall(r"^\| ((?:PJ|NB|WS|PM|AC)\d{3}) \|.*\| (R[0-9, R]+) \|$", self.spec, re.MULTILINE):
            for requirement in re.findall(r"R\d+", requirements):
                enforced.setdefault(requirement, set()).add(identifier)
        coverage = {}
        for requirement, checked_by in re.findall(r"^\| (R\d+) \| ([^|]+) \|$", self.section("### 10.3 Coverage of the requirements"), re.MULTILINE):
            coverage[requirement] = set() if checked_by.strip() == "Review" else {item.strip() for item in checked_by.split(",")}
        defined = set(re.findall(r"^\| (R\d+) \| (?:Standard|Parity|Delivery|Change) \|", self.spec, re.MULTILINE))
        self.assertTrue(enforced and coverage and defined)
        self.assertEqual(defined, set(coverage))
        self.assertEqual({requirement: ids for requirement, ids in coverage.items() if ids}, enforced)

    def test_flavors_splits_and_sections_agree(self):
        import re

        from asystem.model import PROJECT_FLAVORS, PROJECT_SPLITS
        from asystem.notebook import NOTEBOOK_SECTIONS

        flavors = re.findall(r"^\| `(\w+)` \|", self.section("### 3.2 Flavors"), re.MULTILINE)
        splits = re.findall(r"^\| `(\w+)` \|", self.section("### 6.3 Splits"), re.MULTILINE)
        sections = re.findall(r"^\| ([A-Z][A-Za-z ]+?) \| (?:None|\d) \|", self.section("### 6.7 Notebook style guide"), re.MULTILINE)
        self.assertTrue(flavors and splits and sections)
        self.assertEqual(sorted(PROJECT_FLAVORS), sorted(flavors))
        self.assertEqual(sorted(PROJECT_SPLITS), sorted(splits))
        self.assertEqual(list(NOTEBOOK_SECTIONS), sections)
