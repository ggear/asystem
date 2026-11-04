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
from pathlib import Path
from unittest import mock

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
            ["static-1"],
            [signature_input("demo_clock_seconds", "seconds", "Time of the call."), signature_input("demo_state_in", "state", "Carried state.", required=False, shape=[-1])],
            [signature_output("demo_limit_seconds", "seconds", "A limit."), signature_output("demo_state_out", "state", "Next state.", required=False, shape=[-1])],
            state=[signature_state("last_seconds", "seconds", "The previous call.")],
        )
        steps = [
            golden_step(self.signature, "static-1", "s-0", {"demo_clock_seconds": 10.0}, {"demo_limit_seconds": 5}),
            golden_step(self.signature, "static-1", "s-1", {"demo_clock_seconds": 11.0, "demo_state_in": [10.0]}, {"demo_limit_seconds": 5}),
            golden_step(self.signature, "static-1", "s-2", {"demo_state_in": [10.0]}, error="signature"),
        ]
        self.golden = golden_document("static-1", [("calls", steps)])

    def write(self, **overrides):
        from asystem.model import write_project

        arguments = {
            "project_dir": self.project_dir,
            "name": "demo_calc",
            "model_version": "static-1",
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
        self.assertEqual(["PJ003"], self.rules(flavor="wasm", evaluation=self.evaluation(), provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"}))

    def test_model_file_is_copied_into_the_project_and_hashed(self):
        model_path = self.model_file()
        manifest = self.write(
            **self.versioned("1"),
            flavor="pyfunc",
            model_path=model_path,
            constants=None,
            evaluation=self.evaluation(),
            provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"},
        )
        self.assertEqual("model.py", manifest["files"]["model"]["path"])
        self.assertTrue(os.path.isfile(join(self.project_dir, "model.py")))

    def test_implementation_must_say_something(self):
        for implementation in ("demo", "TBD", "to be determined", "", None):
            self.assertEqual(["PJ002", "PJ003"], self.rules(flavor="wasm", evaluation=self.evaluation(), provenance={"source": "manual", "inputs": [], "implementation": implementation}))

    def test_pyfunc_project_is_registered_as_a_pyfunc_model(self):
        from asystem.model import build_signature, golden_document, golden_step, pull_model, register_project, signature_input, signature_output

        signature = build_signature("demo_calc", ["1"], [signature_input("demo_in_seconds", "seconds", "Input.")], [signature_output("demo_out_seconds", "seconds", "Output.")])
        golden = golden_document("1", [("calls", [golden_step(signature, "1", "s-0", {"demo_in_seconds": 1.0}, {"demo_out_seconds": 2.0}), golden_step(signature, "1", "s-1", {}, error="signature")])])
        model_path = join(tempfile.mkdtemp(), "model.py")
        with open(model_path, "w") as model_file:
            model_file.write(
                'MODEL_VERSION = "1"\n'
                "import pandas as pd\nfrom mlflow.models import set_model\nfrom mlflow.pyfunc import PythonModel\n\n\n"
                "class Demo(PythonModel):\n    def predict(self, context, model_input, params=None):\n"
                '        return pd.DataFrame({"demo_out_seconds": model_input["demo_in_seconds"] * 2})\n\n\nset_model(Demo())\n'
            )
        self.write(
            flavor="pyfunc",
            model_version="1",
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

        version = register_project(self.project_dir, "demo_calc", uri)
        mlflow.set_tracking_uri(uri)
        loaded = mlflow.pyfunc.load_model("models:/demo_calc@candidate")
        self.assertEqual([2.0], list(loaded.predict({"demo_in_seconds": [1.0]})["demo_out_seconds"]))
        self.assertEqual("pyfunc", pull_model("demo_calc", "candidate", join(root_dir, "pulled"), uri, unpromoted=True)["flavor"])
        self.assertEqual("1000", pull_model("demo_calc", "candidate", join(root_dir, "pulled"), uri, unpromoted=True)["model_version"])
        self.assertEqual("1", str(version))

    def test_pyfunc_registration_refuses_a_state_vector_signature(self):
        from asystem.model import register_project

        model_path = self.model_file()
        self.write(
            **self.versioned("1"),
            flavor="pyfunc",
            model_path=model_path,
            constants=None,
            evaluation=self.evaluation(),
            provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"},
        )
        with self.assertRaises(ValueError):
            register_project(self.project_dir, "demo_calc", f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}")

    def model_file(self, flavor="pyfunc", version="1"):
        from asystem.model import stamp_model

        path = join(tempfile.mkdtemp(), {"wasm": "model.wasm", "onnx": "model.onnx"}.get(flavor, "model.py"))
        if flavor == "wasm":
            with open(path, "wb") as model_file:
                model_file.write(b"\0asm\x01\x00\x00\x00")
        elif flavor == "onnx":
            import onnx
            from onnx import TensorProto, helper

            node = helper.make_node("Identity", ["x"], ["y"])
            graph = helper.make_graph([node], "demo", [helper.make_tensor_value_info("x", TensorProto.DOUBLE, [1])], [helper.make_tensor_value_info("y", TensorProto.DOUBLE, [1])])
            onnx.save(helper.make_model(graph), path)
        else:
            with open(path, "w") as model_file:
                model_file.write("VALUE = 1\n")
            with open(path, "a") as model_file:
                model_file.write('MODEL_VERSION = "placeholder"\n')
        stamp_model(path, flavor, version)
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

    def test_promotion_needs_acceptance_passed(self):
        from asystem.model import check_acceptance

        self.write()
        self.assertEqual(["PM004"], [rule for rule, _ in check_acceptance(self.project_dir)])
        self.write(evaluation=self.evaluation(passing=False))
        self.assertEqual(["PM004"], [rule for rule, _ in check_acceptance(self.project_dir)])
        self.write(evaluation=self.evaluation())
        self.assertEqual([], check_acceptance(self.project_dir))

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
        self.assertEqual("backtest", run.inputs.dataset_inputs[0].tags[0].value)

    def other_project(self, **overrides):
        other_dir = join(tempfile.mkdtemp(), "project")
        self.write(project_dir=other_dir, **overrides)
        return other_dir

    def versioned(self, version):
        golden = json.loads(json.dumps(self.golden))
        golden["model_version"] = version
        for sequence in golden["sequences"]:
            for step in sequence["steps"]:
                if "response" in step:
                    step["response"]["model_version"] = version
        return {"model_version": version, "signature": {**self.signature, "versions": [version]}, "golden": golden}

    def fitted_overrides(self, passing=True):
        model_path = self.model_file("wasm")
        return {
            **self.versioned("1"),
            "flavor": "wasm",
            "model_path": model_path,
            "constants": None,
            "evaluation": self.evaluation(passing=passing),
            "provenance": {"source": "manual", "inputs": [], "implementation": "demo module built by hand"},
        }

    def test_static_project_must_reproduce_exactly(self):
        from asystem.model import compare_project

        self.write()
        self.assertEqual([], compare_project(self.other_project(), self.project_dir))
        self.assertEqual(["CP001"], [rule for rule, _ in compare_project(self.other_project(provenance={"source": "manual", "inputs": [], "notes": "edited by hand"}), self.project_dir)])

    def test_fitted_project_is_compared_by_signature_and_verdict_not_bytes(self):
        from asystem.model import compare_project

        self.write(**self.fitted_overrides())
        self.assertEqual([], compare_project(self.other_project(**self.fitted_overrides()), self.project_dir))
        self.assertEqual(["CP003"], [rule for rule, _ in compare_project(self.other_project(**self.fitted_overrides(passing=False)), self.project_dir)])
        changed = {**self.signature, "outputs": [{**self.signature["outputs"][0], "parameters": {**self.signature["outputs"][0]["parameters"], "unit": "minutes"}}, self.signature["outputs"][1]]}
        self.assertEqual({"CP002"}, {rule for rule, _ in compare_project(self.other_project(**{**self.fitted_overrides(), "signature": {**changed, "versions": ["1"]}}), self.project_dir)})

    def test_release_check_needs_a_passing_evaluation(self):
        from asystem.model import check_release

        self.write()
        self.assertEqual(["PM004"], [rule for rule, _ in check_release(self.project_dir)])
        self.write(**self.fitted_overrides(passing=False))
        self.assertEqual(["PM004"], [rule for rule, _ in check_release(self.project_dir)])
        self.write(**self.fitted_overrides())
        self.assertEqual([], check_release(self.project_dir))

    def test_registering_an_unchanged_project_creates_nothing_new(self):
        import mlflow
        from asystem.model import register_project

        self.write()
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        first = register_project(self.project_dir, "demo_calc", uri)
        second = register_project(self.project_dir, "demo_calc", uri, aliases=("candidate", "release"))
        self.assertEqual(first, second)
        mlflow.set_tracking_uri(uri)
        self.assertEqual(1, len(mlflow.search_runs(experiment_names=["demo_calc"])))
        self.assertEqual(second, mlflow.MlflowClient().get_model_version_by_alias("demo_calc", "release").version)
        self.write(provenance={"source": "manual", "inputs": [], "notes": "changed"})
        self.assertNotEqual(first, register_project(self.project_dir, "demo_calc", uri))

    def test_stamp_is_written_read_and_ignored_by_the_content_hash(self):
        from asystem.model import content_sha256, read_stamp, stamp_model

        for flavor in ("pyfunc", "wasm", "onnx"):
            path = self.model_file(flavor, "1000-SNAPSHOT")
            self.assertEqual("1000-SNAPSHOT", read_stamp(path, flavor))
            before = content_sha256(path, flavor)
            stamp_model(path, flavor, "1004")
            self.assertEqual("1004", read_stamp(path, flavor))
            self.assertEqual(before, content_sha256(path, flavor))
            stamp_model(path, flavor, "1004")
            self.assertEqual("1004", read_stamp(path, flavor))
        with self.assertRaises(ValueError):
            read_stamp(join(tempfile.mkdtemp(), "model"), "static")

    def test_content_hash_changes_with_the_model_but_not_the_stamp(self):
        from asystem.model import content_sha256, stamp_model

        first, second = self.model_file(), self.model_file()
        with open(second, "a") as model_file:
            model_file.write("OTHER = 2\n")
        stamp_model(first, "pyfunc", "1001")
        self.assertNotEqual(content_sha256(first, "pyfunc"), content_sha256(second, "pyfunc"))

    def test_wasm_stamp_keeps_the_other_sections(self):
        from asystem.model import read_stamp, stamp_model

        path = join(tempfile.mkdtemp(), "model.wasm")
        with open(path, "wb") as model_file:
            model_file.write(b"\0asm\x01\x00\x00\x00" + b"\x01\x04\x01\x60\x00\x00" + b"\x00\x06\x04name\x01")
        stamp_model(path, "wasm", "1000")
        with open(path, "rb") as model_file:
            data = model_file.read()
        self.assertIn(b"\x01\x04\x01\x60\x00\x00", data)
        self.assertIn(b"\x00\x06\x04name\x01", data)
        self.assertEqual("1000", read_stamp(path, "wasm"))
        with open(path, "wb") as model_file:
            model_file.write(b"not wasm")
        with self.assertRaises(ValueError):
            read_stamp(path, "wasm")

    def test_stamp_must_equal_the_manifest(self):
        self.assertEqual([], self.rules(**self.fitted_overrides()))
        self.assertIn("PJ013", self.rules(**{**self.fitted_overrides(), "model_path": self.model_file("wasm", "2")}))
        self.assertIn("PJ013", self.rules(**{**self.fitted_overrides(), "flavor": "pyfunc", "model_path": self.model_file("wasm", "1")}))

    def test_restamp_rewrites_every_version_and_still_verifies(self):
        from asystem.model import project_content_sha256, restamp_project

        self.write(**self.fitted_overrides())
        restamped = restamp_project(self.project_dir, "1004", join(tempfile.mkdtemp(), "project"))
        self.assertEqual("1004", restamped["model_version"])
        self.assertEqual(project_content_sha256(self.project_dir), project_content_sha256(join(os.path.dirname(self.project_dir), "project")))

    def test_a_static_version_must_have_the_static_form(self):
        self.assertEqual(["PJ014"], self.rules(**self.versioned("1")))
        self.assertEqual(["PJ014"], self.rules(**self.versioned("1004")))
        self.assertEqual([], self.rules(**self.versioned("static-7")))

    def test_a_measured_check_needs_a_recorded_dataset(self):
        from asystem.model import evaluate_acceptance

        measured = evaluate_acceptance(lambda: [{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": 0.1, "limit": 1.0, "direction": "max"}], {"backtest": []})
        self.assertIn("AC003", self.rules(evaluation=measured))
        unmeasured = evaluate_acceptance(lambda: [{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": None, "limit": 1.0, "direction": "max"}], {"backtest": []})
        self.assertNotIn("AC003", self.rules(evaluation=unmeasured))

    def test_the_standard_verdict_line_is_printed(self):
        import contextlib
        import io

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.evaluation()
            self.evaluation(passing=False)
        self.assertEqual(["acceptance [passed] budget [0.5]", "acceptance [failed] budget [9.0]"], printed.getvalue().splitlines())

    def test_static_flavor_refuses_a_model_file(self):
        with self.assertRaises(ValueError):
            self.write(model_path=join(self.project_dir, "signature.json"))

    def test_model_flavor_needs_its_implementation(self):
        self.assertEqual(["PJ002", "PJ003"], self.rules(flavor="wasm", evaluation=self.evaluation()))

    def test_name_must_match_signature_and_style(self):
        self.assertIn("PJ004", self.rules(name="Demo-Calc"))

    def test_signature_version_and_model_version_are_checked(self):
        self.assertEqual(["PJ005"], self.rules(model_version="static-2", golden={**self.golden, "model_version": "static-2"}))

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
        manifest = package_project(self.project_dir, "demo_calc", "static-1", "static", self.signature, rows, {"source": "manual", "inputs": []}, constants={"demo_limit_seconds": 5})
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


class ReplayTest(unittest.TestCase):
    def project(self, flavor, golden_out=None, tolerance=None):
        from asystem.model import build_signature, evaluate_acceptance, package_project, signature_input, signature_output, stamp_model

        work_dir = tempfile.mkdtemp()
        model_path = join(work_dir, {"wasm": "model.wasm", "onnx": "model.onnx", "pyfunc": "model.py"}[flavor])
        if flavor == "pyfunc":
            with open(model_path, "w") as model_file:
                model_file.write(
                    textwrap.dedent(
                        """
                        import pandas as pd
                        from mlflow.models import set_model
                        from mlflow.pyfunc import PythonModel

                        MODEL_VERSION = "1"


                        class Double(PythonModel):
                            def predict(self, context, model_input, params=None):
                                return pd.DataFrame({"demo_out": [x * 2.0 for x in model_input["demo_in"]]})


                        set_model(Double())
                        """
                    )
                )
        elif flavor == "wasm":
            import wasmtime

            wat = '(module (memory (export "memory") 1) (func (export "predict") (param i32 i32 i32) (f64.store (local.get 2) (f64.mul (f64.load (local.get 0)) (f64.const 2)))))'
            with open(model_path, "wb") as model_file:
                model_file.write(wasmtime.wat2wasm(wat))
        else:
            import numpy
            import onnx
            from onnx import TensorProto, helper, numpy_helper

            graph = helper.make_graph(
                [helper.make_node("Mul", ["demo_in", "two"], ["demo_out"])],
                "double",
                [helper.make_tensor_value_info("demo_in", TensorProto.DOUBLE, [1, 1])],
                [helper.make_tensor_value_info("demo_out", TensorProto.DOUBLE, [1, 1])],
                initializer=[numpy_helper.from_array(numpy.array(2.0, dtype=numpy.float64), "two")],
            )
            model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 21)])
            model.ir_version = 10
            onnx.save(model, model_path)
        if flavor != "pyfunc":
            stamp_model(model_path, flavor, "1")
        signature = build_signature("demo_replay_double", ["1"], [signature_input("demo_in", "none", "A number.")], [signature_output("demo_out", "none", "Twice the number.", datatype="FP64")])
        dataset = join(work_dir, "2026-11-03_10-00-00", "demo_replay_backtest_2026-11-01_2026-11-02.csv")
        os.makedirs(dirname(dataset))
        with open(dataset, "w") as dataset_file:
            dataset_file.write("a,b\n1,2\n")
        evaluation = evaluate_acceptance(lambda: [{"split": "backtest", "output": "demo_out", "name": "rmse", "value": 0.0, "limit": 1, "direction": "max"}], {"backtest": [dataset]})
        samples = [
            {"demo_in": 1.5, "demo_out": 3.0 if golden_out is None else golden_out},
            {"demo_in": -2.0, "demo_out": -4.0},
            {"demo_in": None, "expect": "error"},
        ]
        project_dir = join(work_dir, "project")
        package_project(
            project_dir,
            "demo_replay_double",
            "1",
            flavor,
            signature,
            samples,
            {"source": "manual", "inputs": [], "implementation": "demo built by hand"},
            model_path=model_path,
            evaluation=evaluation,
            tolerance=tolerance,
        )
        return project_dir

    def test_each_flavor_replays_its_golden_exactly(self):
        from asystem.replay import replay_project

        for flavor in ("pyfunc", "wasm", "onnx"):
            self.assertEqual([], replay_project(self.project(flavor)), flavor)

    def test_a_response_that_differs_from_the_golden_is_a_finding(self):
        from asystem.replay import replay_project

        for flavor in ("pyfunc", "wasm", "onnx"):
            self.assertEqual(["RP003"], [rule for rule, _ in replay_project(self.project(flavor, golden_out=3.5))], flavor)

    def test_a_stated_tolerance_accepts_a_small_difference_and_rejects_a_large_one(self):
        from asystem.replay import replay_project

        bounds = {"demo_out": {"absolute": 1e-3}}
        for flavor in ("pyfunc", "wasm", "onnx"):
            self.assertEqual([], replay_project(self.project(flavor, golden_out=3.0000001, tolerance=bounds)), flavor)
            self.assertEqual(["RP003"], [rule for rule, _ in replay_project(self.project(flavor, golden_out=3.5, tolerance=bounds))], flavor)
            self.assertEqual(["RP003"], [rule for rule, _ in replay_project(self.project(flavor, golden_out=3.0000001))], flavor)

    def test_a_relative_tolerance_scales_with_the_expected_value(self):
        from asystem.replay import replay_project

        self.assertEqual([], replay_project(self.project("pyfunc", golden_out=3.003, tolerance={"demo_out": {"relative": 0.002}})))
        self.assertEqual(["RP003"], [rule for rule, _ in replay_project(self.project("pyfunc", golden_out=3.01, tolerance={"demo_out": {"relative": 0.002}}))])

    def test_a_malformed_tolerance_is_a_finding(self):
        for bounds in ({"demo_other": {"absolute": 1}}, {"demo_out": {"absolute": -1}}, {"demo_out": {}}, {"demo_out": {"scale": 1}}, {"demo_out": {"absolute": True}}):
            with self.assertRaises(ValueError) as refused:
                self.project("pyfunc", tolerance=bounds)
            self.assertIn("PJ015", str(refused.exception), bounds)

    def test_per_architecture_gates_merge_into_one_for_the_same_project(self):
        from asystem.replay import merge_gates

        first = {"project_sha256": "abc", "results": [{"host": "python", "arch": "x86_64", "passed": True}], "skipped": ["go"]}
        second = {"project_sha256": "abc", "results": [{"host": "python", "arch": "aarch64", "passed": True}, {"host": "go", "arch": "aarch64", "passed": True}], "skipped": []}
        merged = merge_gates([first, second])
        self.assertEqual({("python", "x86_64"), ("python", "aarch64"), ("go", "aarch64")}, {(row["host"], row["arch"]) for row in merged["results"]})
        self.assertEqual([], merged["skipped"])
        failing = {"project_sha256": "abc", "results": [{"host": "python", "arch": "x86_64", "passed": False}], "skipped": []}
        self.assertFalse(next(row for row in merge_gates([first, failing])["results"] if row["arch"] == "x86_64")["passed"])
        with self.assertRaises(ValueError):
            merge_gates([first, {**second, "project_sha256": "other"}])

    def test_gate_names_the_project_hash_and_this_architecture(self):
        from asystem.model import file_sha256
        from asystem.replay import ARCHITECTURES, gate_project

        project_dir = self.project("pyfunc")
        document, findings = gate_project(project_dir)
        self.assertEqual([], findings)
        self.assertEqual(file_sha256(join(project_dir, "project.json")), document["project_sha256"])
        self.assertEqual(1, len(document["results"]))
        self.assertIn(document["results"][0]["arch"], set(ARCHITECTURES.values()))
        self.assertTrue(document["results"][0]["passed"])


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
        self.assertEqual(2, len(fix_hints(["PJ003", "CP002"])))
        self.assertEqual([], fix_hints(["ZZ999"]))

    def test_status_joins_the_registry_with_what_the_server_has_ready(self):
        from asystem.model import status_rows

        registry = [{"name": "demo_a", "release": "1001", "latest": "1001"}, {"name": "demo_b", "release": "1002", "latest": "1002"}, {"name": "demo_c", "release": None, "latest": None}]
        served = {"demo_a": {"version": "1001", "state": "READY"}, "demo_b": {"version": "1001", "state": "READY"}}
        with mock.patch("asystem.model.list_models", return_value=registry), mock.patch("asystem.model.served_models", return_value=served):
            rows = {row["registry"]: row for row in status_rows("https://registry.example.com", "http://server", tempfile.mkdtemp()) if "registry" in row}
        self.assertEqual([True, False, False], [rows[name]["in_step"] for name in ("demo_a", "demo_b", "demo_c")])
        self.assertEqual("absent", rows["demo_c"]["served_state"])
        with mock.patch("asystem.model.list_models", return_value=registry), mock.patch("asystem.model.served_models", return_value=None):
            rows = {row["registry"]: row for row in status_rows("https://registry.example.com", "http://server", tempfile.mkdtemp()) if "registry" in row}
        self.assertEqual({"unreachable"}, {row["served_state"] for row in rows.values()})


class ServingRuntimeTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, join(ROOT, "may/mlserver/src/main/python"))
        self.addCleanup(sys.path.remove, join(ROOT, "may/mlserver/src/main/python"))

    def project(self, flavor, **options):
        return ReplayTest().project(flavor, **options)

    def test_every_flavor_serves_what_replay_computes(self):
        from asystem.replay import replay_project
        from project_runtime.project import load_project

        for flavor in ("pyfunc", "wasm", "onnx"):
            project_dir = self.project(flavor)
            self.assertEqual([], replay_project(project_dir), flavor)
            served = load_project(project_dir).predict({"demo_in": [1.5]})
            self.assertEqual({"demo_out": [3.0]}, served, flavor)

    def test_the_settings_name_the_model_its_stamped_version_and_the_signature(self):
        from project_runtime.project import RUNTIME, load_project

        settings = load_project(self.project("wasm")).settings()
        self.assertEqual(("demo_replay_double", "1", RUNTIME), (settings["name"], settings["parameters"]["version"], settings["implementation"]))
        self.assertEqual(["demo_in"], [entry["name"] for entry in settings["inputs"]])
        self.assertEqual(["demo_out"], [entry["name"] for entry in settings["outputs"]])

    def test_a_missing_required_input_is_refused(self):
        from project_runtime.project import load_project

        with self.assertRaises(ValueError):
            load_project(self.project("wasm")).predict({})

    def test_a_changed_file_or_a_failed_acceptance_is_not_loaded(self):
        from project_runtime.project import load_project

        project_dir = self.project("wasm")
        with open(join(project_dir, "model.wasm"), "ab") as model_file:
            model_file.write(b"\0")
        with self.assertRaisesRegex(ValueError, "checksum"):
            load_project(project_dir)

    def test_the_pull_keeps_a_model_only_when_it_loads(self):
        import shutil

        from project_runtime import pull

        project_dir = self.project("onnx")
        models_dir = tempfile.mkdtemp()

        def download(artifact_uri, dst_path):
            shutil.copytree(project_dir, join(dst_path, "model"))

        with (
            mock.patch.dict(os.environ, {"MLFLOW_TRACKING_URI": "http://registry.invalid", "MLFLOW_MODEL_DIR": models_dir, "MLSERVER_MODELS": "demo_replay_double"}),
            mock.patch("mlflow.artifacts.download_artifacts", download),
        ):
            self.assertEqual(0, pull.main())
            self.assertTrue(os.path.isfile(join(models_dir, "demo_replay_double", "model-settings.json")))
            self.assertTrue(os.path.isfile(join(models_dir, "settings.json")))
            with open(join(project_dir, "model.onnx"), "ab") as model_file:
                model_file.write(b"\0")
            self.assertEqual(1, pull.main())


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


class VersionRegistryTest(unittest.TestCase):
    NAME = "demo_calc_run"

    def setUp(self):
        sys.path.insert(0, join(ROOT, "all/_/src/build/python"))
        import mlflow
        from asystem.model import build_signature, signature_input, signature_output

        self.root = tempfile.mkdtemp()
        self.uri = f"sqlite:///{join(self.root, 'mlflow.db')}"
        mlflow.set_tracking_uri(self.uri)
        self.signature = build_signature(self.NAME, ["1000-SNAPSHOT"], [signature_input("demo_in_seconds", "seconds", "Input.")], [signature_output("demo_out_seconds", "seconds", "Output.")])
        self.workspaces = join(self.root, "workspaces")
        self.workspace = join(self.workspaces, "demo", "calc", "run")
        os.makedirs(self.workspace)

    def project(self, factor=2, value=0.0):
        from asystem.model import evaluate_acceptance, golden_document, golden_step, write_project

        model_path = join(tempfile.mkdtemp(), "model.py")
        with open(model_path, "w") as model_file:
            model_file.write(
                'MODEL_VERSION = "1000-SNAPSHOT"\nimport pandas as pd\nfrom mlflow.models import set_model\nfrom mlflow.pyfunc import PythonModel\n\n\n'
                f"class Demo(PythonModel):\n    def predict(self, context, model_input, params=None):\n"
                f'        return pd.DataFrame({{"demo_out_seconds": model_input["demo_in_seconds"] * {factor}}})\n\n\nset_model(Demo())\n'
            )
        dataset_dir = join(tempfile.mkdtemp(), "2026-11-03_10-00-00")
        os.makedirs(dataset_dir)
        dataset = join(dataset_dir, "demo_calc_run_2026-11-01_2026-11-02.csv")
        with open(dataset, "w") as dataset_file:
            dataset_file.write("a\n1\n")
        evaluation = evaluate_acceptance(lambda: [{"split": "backtest", "output": "demo_out_seconds", "name": "rmse", "value": value, "limit": 1.0, "direction": "max"}], {"backtest": [dataset]})
        steps = [
            golden_step(self.signature, "1000-SNAPSHOT", "s-0", {"demo_in_seconds": 1.0}, {"demo_out_seconds": float(factor)}),
            golden_step(self.signature, "1000-SNAPSHOT", "s-1", {}, error="signature"),
        ]
        project_dir = join(tempfile.mkdtemp(), "project")
        write_project(
            project_dir,
            self.NAME,
            "1000-SNAPSHOT",
            "pyfunc",
            self.signature,
            golden_document("1000-SNAPSHOT", [("calls", steps)]),
            {"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"},
            model_path=model_path,
            evaluation=evaluation,
        )
        return project_dir

    def gate(self, hosts=("python",), archs=("x86_64",)):
        from asystem.model import PROJECT_ALIAS_CANDIDATE, PROJECT_MANIFEST, file_sha256, pull_model

        pulled = join(tempfile.mkdtemp(), "pulled")
        pull_model(self.NAME, PROJECT_ALIAS_CANDIDATE, pulled, self.uri, unpromoted=True)
        path = join(tempfile.mkdtemp(), "gate.json")
        with open(path, "w") as gate_file:
            json.dump({"project_sha256": file_sha256(join(pulled, PROJECT_MANIFEST)), "results": [{"host": host, "arch": arch, "passed": True} for host in hosts for arch in archs]}, gate_file)
        return path

    def promote(self, **overrides):
        from asystem.model import promote_project

        arguments = {"released": "10.200.1926", "workspaces_dir": self.workspaces}
        return promote_project(self.NAME, self.uri, self.gate(), ["python"], ["x86_64"], "graham", **{**arguments, **overrides})

    def test_first_candidate_is_stamped_with_the_first_number_and_reregistering_reuses_it(self):
        from asystem.model import PROJECT_ALIAS_CANDIDATE, pull_model, register_project

        project = self.project()
        first = register_project(project, self.NAME, self.uri)
        self.assertEqual(first, register_project(project, self.NAME, self.uri))
        pulled = join(tempfile.mkdtemp(), "pulled")
        manifest = pull_model(self.NAME, PROJECT_ALIAS_CANDIDATE, pulled, self.uri, unpromoted=True)
        self.assertEqual("1000", manifest["model_version"])
        self.assertEqual("1000-SNAPSHOT", json.loads(Path(project, "project.json").read_text())["model_version"])

    def test_promotion_takes_its_hosts_from_the_flavor_and_needs_both_architectures(self):
        from asystem.model import promote_project, register_project

        register_project(self.project(), self.NAME, self.uri)
        arguments = {"released": "10.200.1926", "workspaces_dir": self.workspaces}
        with self.assertRaises(ValueError) as refused:
            promote_project(self.NAME, self.uri, self.gate(), None, ["x86_64", "aarch64"], "graham", **arguments)
        self.assertIn("PM001", str(refused.exception))
        self.assertTrue(promote_project(self.NAME, self.uri, self.gate(archs=("x86_64", "aarch64")), None, ["x86_64", "aarch64"], "graham", **arguments))

    def test_promotion_records_the_version_and_advances_the_development_version(self):
        from asystem.model import list_models, pull_model, register_project, resolve_model

        register_project(self.project(), self.NAME, self.uri)
        self.promote()
        for selector in ("release", "latest", "1000"):
            resolved = resolve_model(self.NAME, selector, self.uri)
            self.assertEqual(("1000", "10.200.1926", "graham", "passed"), (resolved["model_version"], resolved["service_version"], resolved["reviewed_by"], resolved["acceptance"]))
        self.assertEqual("1001-SNAPSHOT", Path(self.workspace, ".version").read_text().strip())
        self.assertEqual({"name": self.NAME, "release": "1000", "latest": "1000", "service_version": "10.200.1926", "flavor": "pyfunc"}, list_models(self.uri)[0])
        self.assertEqual("1000", pull_model(self.NAME, "1000", join(tempfile.mkdtemp(), "pulled"), self.uri)["model_version"])
        with self.assertRaises(ValueError):
            pull_model(self.NAME, "candidate", join(tempfile.mkdtemp(), "pulled"), self.uri)
        self.assertIsNone(resolve_model(self.NAME, "1009", self.uri))

    def test_a_stale_candidate_is_refused_and_a_new_one_gets_the_next_number(self):
        from asystem.model import PROJECT_ALIAS_CANDIDATE, pull_model, register_project

        register_project(self.project(), self.NAME, self.uri)
        self.promote()
        with self.assertRaises(ValueError) as stale:
            self.promote()
        self.assertIn("PM005", str(stale.exception))
        register_project(self.project(factor=3), self.NAME, self.uri)
        manifest = pull_model(self.NAME, PROJECT_ALIAS_CANDIDATE, join(tempfile.mkdtemp(), "pulled"), self.uri, unpromoted=True)
        self.assertEqual("1001", manifest["model_version"])
        self.promote()

    def test_a_pull_refuses_a_release_that_never_passed_acceptance(self):
        from asystem.model import pull_model, register_project
        from mlflow import MlflowClient

        version = register_project(self.project(value=9.0), self.NAME, self.uri)
        MlflowClient().set_registered_model_alias(self.NAME, "release", version)
        with self.assertRaises(ValueError) as refused:
            pull_model(self.NAME, "release", join(tempfile.mkdtemp(), "pulled"), self.uri)
        self.assertIn("PM004", str(refused.exception))
        self.assertIsNone(pull_model(self.NAME, "latest", join(tempfile.mkdtemp(), "pulled"), self.uri))
        self.assertEqual("1000", pull_model(self.NAME, "candidate", join(tempfile.mkdtemp(), "pulled"), self.uri, unpromoted=True)["model_version"])

    def test_a_deleted_alias_never_lets_a_number_be_reused(self):
        from asystem.model import next_model_version, register_project
        from mlflow import MlflowClient

        register_project(self.project(), self.NAME, self.uri)
        self.promote()
        client = MlflowClient()
        client.delete_registered_model_alias(self.NAME, "m1000")
        client.delete_registered_model_alias(self.NAME, "release")
        self.assertEqual(1001, next_model_version(client, self.NAME))

    def test_promotion_needs_a_release_version(self):
        from asystem.model import register_project

        register_project(self.project(), self.NAME, self.uri)
        with mock.patch("asystem.model.service_version", side_effect=ValueError("no tag")), self.assertRaises(ValueError) as refused:
            self.promote(released=None)
        self.assertIn("PM006", str(refused.exception))

    def test_service_version_is_the_latest_release_tag(self):
        import subprocess

        from asystem.model import service_version

        repo = tempfile.mkdtemp()
        with self.assertRaises(ValueError):
            service_version(repo)
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
        with self.assertRaises(ValueError):
            service_version(repo)
        for tag in ("10.200.1925", "10.200.1927", "10.200.1926", "weekly"):
            subprocess.run(["git", "-C", repo, "tag", tag], check=True)
        self.assertEqual("10.200.1927", service_version(repo))

    def test_slot_versions_lists_default_and_release(self):
        from asystem.model import slot_versions

        source = tempfile.mkdtemp()
        for slot, version in (("default", "static-1"), ("release", "1004")):
            slot_dir = join(source, "max", "demo", "src/build/resources/model", slot)
            os.makedirs(slot_dir)
            with open(join(slot_dir, "project.json"), "w") as manifest_file:
                json.dump({"name": "demo_calc_run", "flavor": "static", "model_version": version}, manifest_file)
        self.assertEqual(["static-1", "1004"], [row["model_version"] for row in slot_versions(source)])


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

    def test_development_version_file_is_checked(self):
        with open(join(self.model_dir, ".version"), "w") as version_file:
            version_file.write("1003-SNAPSHOT\n")
        self.assertEqual([], self.rules())
        for text in ("1003\n", "static-1\n", "100-SNAPSHOT\n", "\n"):
            with open(join(self.model_dir, ".version"), "w") as version_file:
                version_file.write(text)
            self.assertEqual(["WS008"], self.rules(), text)

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

        in_spec = set(re.findall(r"^\| ((?:PJ|NB|WS|PM|AC|CP|RP)\d{3}) \|", self.spec, re.MULTILINE))
        in_code = set()
        for module in ("model", "notebook", "replay", "workspace"):
            with open(join(ROOT, f"all/_/src/build/python/asystem/{module}.py")) as source:
                in_code |= set(re.findall(r'"((?:PJ|NB|WS|PM|AC|CP|RP)\d{3})"', source.read()))
        self.assertTrue(in_spec and in_code)
        self.assertEqual(in_spec, in_code)

    def test_every_requirement_is_covered_by_a_check_or_by_review(self):
        import re

        enforced = {}
        for identifier, requirements in re.findall(r"^\| ((?:PJ|NB|WS|PM|AC|CP|RP)\d{3}) \|.*\| (R[0-9, R]+) \|$", self.spec, re.MULTILINE):
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
