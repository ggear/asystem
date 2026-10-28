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
        self.assertIn("drill passed", done.stdout)
        with open(join(run, ".meta", "primary", "drill.json")) as handle:
            self.assertIn('"verdict": "success"', handle.read())
        self.assertFalse(isdir(join(self.workdir, "letsencrypt", "restore", "2026-10-28_01-00-00")))

    def test_a_drill_fails_when_the_backup_holds_less_than_its_manifest_says(self):
        run = self.archive("2026-10-28_01-00-00", {"live/a": 100}, verdict="success", units={"live": 9000})
        done = self.run_restore("--mode=drill", "--record=secondary")
        self.assertEqual(done.returncode, 1)
        self.assertIn("short [live] wants [9000] holds [100]", done.stdout)
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
        self.assertIn("drill passed", done.stdout)
        with open(join(run, ".meta", "primary", "drill.json")) as handle:
            self.assertIn('"verdict": "success"', handle.read())

    def test_a_sql_dump_holding_less_than_its_manifest_fails_the_drill(self):
        text = "-- Current Database: `alpha`\nINSERT 1;\n"
        self.sql_run("2026-10-28_01-00-00", text, {"alpha": 5000})
        done = self.run_restore("--mode=drill")
        self.assertEqual(done.returncode, 1)
        self.assertIn("short [alpha]", done.stdout)

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
        self.assertIn("staging [1] artifact(s) into scratch", done.stderr)
        self.assertIn("fingerprinting live", done.stderr)
        self.assertIn("merging [10] unit(s) with [3] job(s)", done.stderr)
        self.assertRegex(done.stderr, r"merged \[\d+\] of \[10\] units \[\d+\]%, \[\d+\] rows, \[\d\.\d\d\] GiB at \[\d+\] MiB/s, \[\d+\] units a minute")
        self.assertIn("merged [10] of [10] units [100]%, [5000] rows", done.stderr)
        self.assertIn("restarting [live]", done.stderr)
        self.assertIn("verified, every merged unit holds at least the backup's count", done.stderr)

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
