import os
import subprocess
import tempfile
import textwrap
import unittest
import zipfile
from os.path import dirname, isdir, join, realpath

ROOT = realpath(join(dirname(__file__), "../../../../../.."))
SCRIPT = join(ROOT, "mad/postgres/src/main/resources/backup.sh")
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


if __name__ == "__main__":
    unittest.main()
