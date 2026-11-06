import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from os.path import abspath, dirname, exists, join, realpath

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
BACKUP = join(DIR_ROOT, "src/main/resources/backup.sh")
RESTORE = join(DIR_ROOT, "src/main/resources/restore.sh")
BASH = "/opt/homebrew/bin/bash" if exists("/opt/homebrew/bin/bash") else "bash"
GNU = {"find": "gfind", "date": "gdate", "split": "gsplit"}
STAMP = "%Y-%m-%d_%H-%M-%S"
DOCKER = """#!/usr/bin/env bash
case "$*" in
*"status backup"*) echo "Status: completed" ;;
*"create backup"*)
  echo "$*" >>"${FAKE_CALLS}"
  name="" parent="" args=("$@")
  for ((index = 0; index < ${#args[@]}; index++)); do
    [ "${args[index]}" = "--name" ] && name="${args[index + 1]}"
    [ "${args[index]}" = "--parent" ] && parent="${args[index + 1]}"
  done
  if [ -n "${parent}" ]; then mkdir -p "${FAKE_STORE}/${parent}/incremental/${name}"; else mkdir -p "${FAKE_STORE}/${name}"; fi
  ;;
esac
"""
MERGE_DOCKER = """#!/usr/bin/env bash
case "$*" in
*"information_schema"*) echo '[{"column_name":"host","data_type":"Dictionary(Int32, Utf8)"},{"column_name":"value","data_type":"Float64"},{"column_name":"time","data_type":"Timestamp(Nanosecond, None)"}]' ;;
*"--format jsonl"*) echo '{"time_ns":1700000000000000000,"host":"a","value":1.5}' ;;
*"bash -c"*)
  echo "$*" >>"${FAKE_ARGV}"
  cat >>"${FAKE_STDIN}"
  printf '%s' "${FAKE_CODE}"
  ;;
esac
"""
SUPERVISOR = """#!/usr/bin/env bash
shift
verb="$1"
case "${verb}" in
epoch) stamp="${2: -19}"; date -d "${stamp:0:10} ${stamp:11:2}:${stamp:14:2}:${stamp:17:2}" +%s ;;
parent) echo "${FAKE_PARENT}" ;;
target)
  mkdir -p "${FAKE_ROOT}/${BACKUP_RUN_TIMESTAMP}"
  echo "${FAKE_ROOT}/${BACKUP_RUN_TIMESTAMP}/influxdb3_at_${BACKUP_RUN_TIMESTAMP}_from_x${@: -2:1}.${@: -1}"
  ;;
esac
"""


class BackupWrittenTest(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.bin = join(self.workdir, "bin")
        os.makedirs(self.bin)
        for name, target in GNU.items():
            found = shutil.which(target)
            if found:
                os.symlink(found, join(self.bin, name))
        for name, body in (("docker", DOCKER), ("supervisor", SUPERVISOR)):
            with open(join(self.bin, name), "w") as handle:
                handle.write(body)
            os.chmod(join(self.bin, name), 0o755)
        self.source = join(self.workdir, "influxdb3", "10.200.2")
        self.root = join(self.workdir, "influxdb3", "backup")
        self.store = join(self.source, "cluster_1", "backups")
        self.calls = join(self.workdir, "calls")
        os.makedirs(self.store)
        os.makedirs(self.root)

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def plant_full(self, days_ago, source_version):
        run = (datetime.now(UTC).astimezone() - timedelta(days=days_ago)).strftime(STAMP)
        os.makedirs(join(self.store, f"full-{run}"))
        os.makedirs(join(self.root, run, ".meta"))
        with open(join(self.root, run, ".meta", "manifest.json"), "w") as handle:
            handle.write(f'{{\n  "kind": "full",\n  "source_version": "{source_version}"\n}}\n')
        return run

    def written(self, parent, force_full="false"):
        environment = dict(
            os.environ,
            PATH=self.bin + ":" + os.environ["PATH"],
            BACKUP_SOURCE_PATH=self.source,
            BACKUP_SUPERVISOR=join(self.bin, "supervisor"),
            BACKUP_RUN_TIMESTAMP=datetime.now(UTC).astimezone().strftime(STAMP),
            BACKUP_FORCE_FULL=force_full,
            FAKE_CALLS=self.calls,
            FAKE_STORE=self.store,
            FAKE_ROOT=self.root,
            FAKE_PARENT=parent,
        )
        done = subprocess.run([BASH, "-c", f'. "{BACKUP}"; backup_written'], capture_output=True, text=True, env=environment)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(self.calls) as handle:
            return handle.read()

    def test_a_delta_hangs_off_a_full_written_by_the_same_version_this_week(self):
        run = self.plant_full(0, "10.200.2")
        self.assertIn("--incremental", self.written(run))

    def test_a_full_written_by_another_version_cannot_parent_a_delta(self):
        run = self.plant_full(0, "10.200.1")
        self.assertNotIn("--incremental", self.written(run))

    def test_a_full_with_no_manifest_cannot_parent_a_delta(self):
        run = self.plant_full(0, "10.200.2")
        os.remove(join(self.root, run, ".meta", "manifest.json"))
        self.assertNotIn("--incremental", self.written(run))

    def test_a_full_from_an_earlier_iso_week_cannot_parent_a_delta(self):
        run = self.plant_full(14, "10.200.2")
        self.assertNotIn("--incremental", self.written(run))

    def test_asking_for_a_full_overrides_a_usable_parent(self):
        run = self.plant_full(0, "10.200.2")
        self.assertNotIn("--incremental", self.written(run, force_full="true"))


class RestoreMergedTest(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.bin = join(self.workdir, "bin")
        os.makedirs(self.bin)
        for name, target in GNU.items():
            found = shutil.which(target)
            if found:
                os.symlink(found, join(self.bin, name))
        with open(join(self.bin, "docker"), "w") as handle:
            handle.write(MERGE_DOCKER)
        os.chmod(join(self.bin, "docker"), 0o755)
        self.source = join(self.workdir, "influxdb3", "10.200.2")
        os.makedirs(self.source)
        self.argv = join(self.workdir, "argv")
        self.stdin = join(self.workdir, "stdin")

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def merged(self, code, token):
        environment = dict(
            os.environ,
            PATH=self.bin + ":" + os.environ["PATH"],
            RESTORE_SOURCE_PATH=self.source,
            RESTORE_RUN_TIMESTAMP="2026-11-06_01-00-53",
            INFLUXDB3_RESTORE_WRITE_TOKEN=token,
            FAKE_ARGV=self.argv,
            FAKE_STDIN=self.stdin,
            FAKE_CODE=code,
        )
        os.makedirs(join(self.workdir, "influxdb3", "restore"), exist_ok=True)
        return subprocess.run([BASH, "-c", f'. "{RESTORE}"; restore_merged sensor/2023-11-14 influxdb3_restore'], capture_output=True, text=True, env=environment)

    def read(self, path):
        with open(path) as handle:
            return handle.read()

    def test_rows_are_written_into_the_live_container_with_the_token_on_stdin_only(self):
        done = self.merged("204", "secret")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.read(self.stdin).splitlines(), ["Authorization: Bearer secret", "sensor,host=a value=1.5 1700000000000000000"])
        self.assertIn("exec --interactive influxdb3 bash -c", self.read(self.argv))
        self.assertNotIn("secret", self.read(self.argv))

    def test_no_token_sends_an_empty_header_line(self):
        done = self.merged("204", "")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.read(self.stdin).splitlines()[0], "")

    def test_a_write_that_is_not_accepted_fails_the_unit(self):
        self.assertNotEqual(self.merged("500", "secret").returncode, 0)


if __name__ == "__main__":
    unittest.main()
