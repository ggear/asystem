import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from os.path import abspath, dirname, join, realpath

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
BACKUP_SCRIPT = join(DIR_ROOT, "src/main/resources/image/backup.sh")


def _gnu_userland():
    for command in (["date", "-d", "2026-09-09 19:37:49", "+%s"], ["stat", "-c", "%Y", "."]):
        if subprocess.run(command, capture_output=True).returncode != 0:
            return False
    return shutil.which("jq") is not None


GNU_USERLAND = _gnu_userland()
NEEDS_GNU = unittest.skipUnless(GNU_USERLAND, "needs a GNU userland, backup.sh only ever runs on one")


class BackupShellTest(unittest.TestCase):

    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.makedirs(join(self.home, "supervisor/backup/x"))

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def shell(self, snippet, arguments=(), **environment):
        script = 'set -uo pipefail\nsource "{}" {}\n{}'.format(BACKUP_SCRIPT, " ".join(arguments), snippet)
        env = dict(os.environ)
        env.update({
            "BACKUP_SOURCE_ONLY": "1",
            "BACKUP_HOME_ROOT": self.home,
            "BACKUP_INSTALL_ROOT": join(self.home, "install"),
            "BACKUP_RUN_PATH": join(self.home, "supervisor/backup/x"),
        })
        env.update({key: str(value) for key, value in environment.items()})
        done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, "stderr: {}".format(done.stderr))
        return done.stdout.strip()

    def parse(self, *arguments, **environment):
        return self.shell(
            'printf "%s %s %s %s %s" "${BACKUP_COMMAND}" "${BACKUP_STAGE}" "${BACKUP_RUN_GIVEN:--}"'
            ' "${BACKUP_SCRUB}" "${BACKUP_SCRUB_FORCED}"',
            arguments=arguments, **environment)

    def invoke(self, *arguments):
        return subprocess.run([BACKUP_SCRIPT, *arguments], capture_output=True, text=True,
                              env=dict(os.environ, BACKUP_HOME_ROOT=self.home))

    def scrub(self, run, stage, **fields):
        path = join(self.home, "supervisor/backup", run, "stage", stage)
        os.makedirs(path, exist_ok=True)
        with open(join(path, "scrub.json"), "w") as handle:
            json.dump(fields, handle, indent=2)

    def document(self, run, stage, **fields):
        path = join(self.home, "supervisor/backup", run, "stage", stage)
        os.makedirs(path, exist_ok=True)
        with open(join(path, "status.json"), "w") as handle:
            json.dump(fields, handle, indent=2)
        open(join(path, "output.log"), "a").close()
        return join(path, "status.json")

    def test_elapsed_is_zero_padded_and_fixed_width(self):
        self.assertEqual(self.shell("backup_elapsed 0"), "00h00m00s")
        self.assertEqual(self.shell("backup_elapsed 3725"), "01h02m05s")
        self.assertEqual(self.shell("backup_elapsed 359999"), "99h59m59s")

    def test_field_reads_rsync_thousands_separators(self):
        stats = "Total transferred file size: 9,437,184 bytes\nNumber of regular files transferred: 2\n"
        self.assertEqual(self.shell('backup_field "{}" "Total transferred file size: "'.format(stats)), "9437184")
        self.assertEqual(self.shell('backup_field "{}" "Number of regular files transferred: "'.format(stats)), "2")

    def test_field_cannot_read_human_readable_sizes(self):
        stats = "Total transferred file size: 9.44M bytes\n"
        self.assertEqual(self.shell('backup_field "{}" "Total transferred file size: "'.format(stats)), "944")

    def test_count_accumulates_a_stats_block(self):
        stats = ("Number of created files: 3\n"
                 "Number of deleted files: 0\n"
                 "Number of regular files transferred: 2\n"
                 "Total transferred file size: 9,437,184 bytes\n"
                 "Total bytes sent: 9,439,689\n")
        counted = self.shell(
            'BACKUP_STAGE_DIR="${{BACKUP_HOME_ROOT}}"; BACKUP_FILES=0; BACKUP_SIZE=0; BACKUP_FILES_HELD=0\n'
            'BACKUP_FILES_CREATED=0; BACKUP_FILES_DELETED=0; BACKUP_SIZE_HELD=0; BACKUP_SENT=0; BACKUP_TOTAL=0\n'
            'BACKUP_USAGE=0\n'
            'backup_count "{}"\n'
            'printf "%s %s %s" "${{BACKUP_FILES}}" "${{BACKUP_SIZE}}" "${{BACKUP_FILES_CREATED}}"'.format(stats))
        self.assertEqual(counted, "2 9 3")

    def test_usage_rejects_an_unknown_command(self):
        done = self.invoke("bogus")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown command [bogus]", done.stderr)
        self.assertIn("Usage:", done.stderr)

    def test_usage_rejects_an_unknown_option(self):
        done = self.invoke("start", "--wat")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown option [--wat]", done.stderr)

    def test_usage_rejects_an_unknown_stage(self):
        done = self.invoke("start", "--stage", "quaternary")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown stage [quaternary]", done.stderr)

    def test_help_is_a_command_and_prints_to_stdout(self):
        done = self.invoke("help")
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stderr, "")
        for command in ("start", "stop", "tail", "list", "manual", "help"):
            self.assertIn("  {}".format(command), done.stdout)
        self.assertIn("minting a run id when given none", done.stdout)
        self.assertIn("--stage <name>", done.stdout)

    def test_promotion_namespaces_supervisor_by_host_and_nothing_else(self):
        head = 'BACKUP_HOST=raspbpi-jen\n'
        self.assertEqual(self.shell(head + 'backup_promotion supervisor /share/10'),
                         "/share/10/backup/supervisor/raspbpi-jen")
        self.assertEqual(self.shell(head + 'backup_promotion mariadb /share/10'),
                         "/share/10/backup/mariadb")
        self.assertEqual(self.shell('BACKUP_HOST=macmini-mad\nbackup_promotion supervisor /share/10'),
                         "/share/10/backup/supervisor/macmini-mad")

    def test_readings_are_tab_separated_so_a_field_can_never_split(self):
        head = 'backup_used() { echo 0; }\nbackup_rate() { echo "150 default"; }\n'
        for reader in ("backup_promoting /nowhere/status.json", "backup_mirroring /nowhere"):
            line = self.shell(head + 'printf "%s" "$(' + reader + ' | tr "\\t" "|")"')
            self.assertEqual(len(line.split("|")), 6, "got [{}] from {}".format(line, reader))

    def test_attached_refuses_anything_that_is_not_the_backup_disk(self):
        head = 'BACKUP_STAGE_DIR="${BACKUP_HOME_ROOT}"\n'
        self.assertEqual(self.shell(head + 'mountpoint() { return 1; }\n'
                                           'backup_attached && echo attached || echo detached'), "detached")
        self.assertEqual(self.shell(head + 'mountpoint() { return 0; }\n'
                                           'backup_attached && echo attached || echo detached'), "attached")
        self.assertEqual(self.shell(head + 'echo 2049 >"${BACKUP_HOME_ROOT}/disk-device"\n'
                                           'mountpoint() { return 0; }\nstat() { echo 2049; }\n'
                                           'backup_attached && echo attached || echo detached'), "attached")
        self.assertEqual(self.shell(head + 'echo 2049 >"${BACKUP_HOME_ROOT}/disk-device"\n'
                                           'mountpoint() { return 0; }\nstat() { echo 65024; }\n'
                                           'backup_attached && echo attached || echo detached'), "detached")

    def test_manual_reports_a_publish_that_did_not_happen(self):
        done = self.shell('backup_publish() { return 1; }\n'
                          'backup_manual off 2>&1 || echo "exit=$?"')
        self.assertIn("could not publish [OFF] to [supervisor/cluster-all/backup/reaper]", done)
        self.assertIn("exit=1", done)

    def test_publish_says_when_it_cannot_reach_a_broker(self):
        self.assertEqual(self.shell('BROKER_HOST=""; backup_publish topic payload; echo "exit=$?"'), "exit=1")

    def test_manual_publishes_the_reaper_switch_both_ways(self):
        probe = ('backup_publish() { printf "%s %s\\n" "$1" "$2"; }\n'
                 'backup_log() { :; }\n'
                 'backup_manual {}')
        self.assertEqual(self.shell(probe.replace("{}", "")), "supervisor/cluster-all/backup/reaper OFF")
        self.assertEqual(self.shell(probe.replace("{}", "off")), "supervisor/cluster-all/backup/reaper OFF")
        self.assertEqual(self.shell(probe.replace("{}", "on")), "supervisor/cluster-all/backup/reaper ON")

    def test_manual_keeps_its_argument_out_of_the_run_id_slot(self):
        self.assertEqual(self.parse("manual", "on"), "manual all - 0 0")
        self.assertEqual(self.shell('backup_publish() { printf "%s" "$2"; }\nbackup_log() { :; }\n'
                                    'backup_manual "${BACKUP_ARGUMENT}"', arguments=("manual", "on")), "ON")

    def test_manual_refuses_a_word_it_does_not_know(self):
        done = self.invoke("manual", "sideways")
        self.assertEqual(done.returncode, 2)
        self.assertIn("manual takes [off] to pause the reaper or [on] to arm it, not [sideways]", done.stderr)

    def test_command_is_first_and_defaults_to_help_rather_than_a_run(self):
        self.assertEqual(self.parse(), "help all - 0 0")
        self.assertEqual(self.parse("start"), "start all - 0 0")
        self.assertEqual(self.parse("stop"), "stop all - 0 0")
        self.assertEqual(self.parse("list"), "list all - 0 0")

    def test_a_naked_invocation_explains_itself_and_starts_nothing(self):
        done = self.invoke()
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stderr, "")
        self.assertIn("Usage:", done.stdout)
        self.assertEqual(os.listdir(join(self.home, "supervisor/backup")), ["x"])

    def test_run_id_is_the_one_positional_after_the_command(self):
        self.assertEqual(self.parse("tail", "2026-09-08_00-00-00"), "tail all 2026-09-08_00-00-00 0 0")
        self.document("2026-09-08_00-00-00", "primary", state="complete")
        self.assertEqual(self.parse("stop", "2026-09-08_00-00-00"), "stop all 2026-09-08_00-00-00 0 0")

    def test_stage_is_a_switch_rather_than_a_positional(self):
        self.assertEqual(self.parse("start", "--stage", "tertiary"), "start tertiary - 0 0")
        self.assertEqual(self.parse("start", "--stage=primary"), "start primary - 0 0")
        self.assertEqual(self.parse("start", "2026-09-08_00-00-00", "--stage", "secondary"),
                         "start secondary 2026-09-08_00-00-00 0 0")

    def test_scrub_is_off_by_hand_and_on_when_scheduled(self):
        self.assertEqual(self.parse("start"), "start all - 0 0")
        self.assertEqual(self.parse("start", BACKUP_RUN_ID_PASSED=1), "start all - 1 0")

    def test_scrub_flag_forces_one_a_hand_run_would_not_do(self):
        self.assertEqual(self.parse("start", "--scrub"), "start all - 1 1")
        self.assertEqual(self.parse("start", "--scrub", BACKUP_RUN_ID_PASSED=1), "start all - 1 1")

    def test_scrub_is_suppressed_by_env_since_there_is_no_flag_for_it(self):
        done = self.invoke("start", "--no-scrub")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown option [--no-scrub]", done.stderr)
        self.assertEqual(self.parse("start", BACKUP_RUN_ID_PASSED=1, BACKUP_SCRUB=0), "start all - 0 0")

    def test_scrub_refusal_reads_this_command_line_not_an_inherited_flag(self):
        self.assertEqual(self.parse("start", "--stage", "primary", BACKUP_SCRUB_FORCED=1, BACKUP_SCRUB=1),
                         "start primary - 1 1")
        done = self.invoke("start", "--stage", "primary", "--scrub")
        self.assertEqual(done.returncode, 2)

    def test_scrub_is_refused_against_a_stage_that_cannot_scrub(self):
        for stage in ("primary", "secondary"):
            done = self.invoke("start", "--stage", stage, "--scrub")
            self.assertEqual(done.returncode, 2)
            self.assertIn("only tertiary scrubs, not stage [{}]".format(stage), done.stderr)
        self.assertEqual(self.parse("start", "--stage", "tertiary", "--scrub"), "start tertiary - 1 1")

    def test_marker_names_its_stage_beside_the_level(self):
        for stage, rendered in (("tertiary", "tertiary "), ("secondary", "secondary"), ("primary", "primary  ")):
            self.assertRegex(self.shell('backup_marker {} "mirrored [ 1] GB"'.format(stage)),
                             r"^\[INFO " + rendered + r" \d{2}:\d{2}:\d{2}\] mirrored \[ 1\] GB$")

    def test_log_matches_the_marker_column(self):
        marker = self.shell('backup_marker tertiary "mirrored [ 1739] GB"')
        for level, rendered in (("WARN", "WARN"), ("ERROR", "ERRS"), ("INFO", "INFO")):
            line = self.shell('backup_log {} "no bytes copied" 2>&1'.format(level))
            self.assertRegex(line, r"^\[" + rendered + r" {11}\d{2}:\d{2}:\d{2}\] no bytes copied$")
            self.assertEqual(len(line.split("]")[0]), len(marker.split("]")[0]))

    def test_log_keeps_a_wall_clock_and_drops_the_stage(self):
        line = self.shell('BACKUP_STAGE=tertiary; backup_log INFO "mirroring [/share/40]"')
        self.assertRegex(line, r"^\[INFO {11}\d{2}:\d{2}:\d{2}\] mirroring \[/share/40\]$")

    def test_marker_blanks_the_stage_for_a_whole_run_rather_than_naming_it(self):
        self.assertRegex(self.shell('backup_marker all "no active run"'),
                         r"^\[INFO {11}\d{2}:\d{2}:\d{2}\] no active run$")

    @NEEDS_GNU
    def test_epoch_reads_the_run_id_as_a_timestamp(self):
        self.assertEqual(
            self.shell('backup_epoch 2026-09-09_19-37-49'),
            subprocess.run(["date", "-d", "2026-09-09 19:37:49", "+%s"], capture_output=True, text=True).stdout.strip())

    @NEEDS_GNU
    def test_previous_defaults_to_complete_but_accepts_any_terminal_state(self):
        self.document("2026-09-08_00-00-00", "tertiary", state="failed", duration_s=900, total_mb=2594000)
        self.assertEqual(self.shell('backup_previous tertiary total_mb'), "0")
        self.assertEqual(self.shell('backup_previous tertiary total_mb ""'), "2594000")

    @NEEDS_GNU
    def test_previous_prefers_the_newest_completed_run(self):
        self.document("2026-09-07_00-00-00", "tertiary", state="complete", duration_s=100, size_mb=1000)
        self.document("2026-09-08_00-00-00", "tertiary", state="complete", duration_s=200, size_mb=8000)
        self.assertEqual(self.shell('backup_previous tertiary size_mb'), "8000")

    @NEEDS_GNU
    def test_actives_ignores_a_stale_running_document(self):
        stale = self.document("2026-09-08_00-00-00", "tertiary", state="running")
        os.utime(stale, (0, 0))
        self.assertEqual(self.shell("backup_actives"), "")
        self.document("2026-09-08_01-00-00", "tertiary", state="running")
        self.assertEqual(self.shell("backup_actives"), "2026-09-08_01-00-00")

    @NEEDS_GNU
    def test_actives_reports_the_newest_when_several_are_live(self):
        self.document("2026-09-08_01-00-00", "tertiary", state="running")
        self.document("2026-09-08_02-00-00", "tertiary", state="running")
        self.assertEqual(self.shell("backup_active"), "2026-09-08_02-00-00")

    @NEEDS_GNU
    def test_pending_falls_back_to_a_default_for_a_service_stage(self):
        self.assertEqual(self.shell("backup_pending primary"), "<10")

    @NEEDS_GNU
    def test_pending_reads_the_last_duration_for_a_service_stage(self):
        self.document("2026-09-08_00-00-00", "secondary", state="complete", duration_s=420, size_mb=5)
        self.assertEqual(self.shell("backup_pending secondary"), "7")

    @NEEDS_GNU
    def test_result_maps_a_status_document_to_one_word(self):
        run = "2026-09-08_00-00-00"
        self.document(run, "primary", state="complete", success_bool=True)
        self.document(run, "secondary", state="failed", success_bool=False)
        self.document(run, "tertiary", state="running", success_bool=False)
        base = join(self.home, "supervisor/backup", run, "stage")
        self.assertEqual(self.shell('backup_result "{}/primary/status.json"'.format(base)), "success")
        self.assertEqual(self.shell('backup_result "{}/secondary/status.json"'.format(base)), "failed")
        self.assertEqual(self.shell('backup_result "{}/tertiary/status.json"'.format(base)), "running")
        self.assertEqual(self.shell('backup_result "{}/absent/status.json"'.format(base)), "-")

    def test_result_tells_stopped_and_timeout_from_a_genuine_failure(self):
        for state in ("stopped", "timeout", "failed"):
            document = self.document("2026-09-08_00-00-0{}".format(len(state)), "tertiary",
                                     state=state, success_bool=False)
            self.assertEqual(self.shell('backup_result "{}"'.format(document)), state)

    def test_interrupted_records_why_the_stage_ended(self):
        probe = ('BACKUP_STAGE_DIR="${BACKUP_HOME_ROOT}"; BACKUP_STARTED=0\n'
                 'stage_stop() { :; }\nbackup_settle() { :; }\nbackup_log() { :; }\n'
                 'backup_document() { printf "%s" "$1"; exit 0; }\n'
                 '{}\nbackup_interrupted')
        self.assertEqual(self.shell(probe.replace("{}", ":")), "failed")
        self.assertEqual(self.shell(probe.replace("{}", ': >"${BACKUP_HOME_ROOT}/.stopped"')), "stopped")
        self.assertEqual(self.shell(probe.replace("{}", ': >"${BACKUP_HOME_ROOT}/.timeout"')), "timeout")

    def test_bar_fills_in_proportion_and_stays_one_width(self):
        widths = set()
        for percent, expected in ((0, "[..................]   0%"), (8, "[#.................]   8%"),
                                  (74, "[#############.....]  74%"), (100, "[##################] 100%"),
                                  (140, "[##################] 100%")):
            drawn = self.shell("backup_bar {}".format(percent))
            self.assertEqual(drawn, expected)
            widths.add(len(drawn))
        self.assertEqual(widths, {25})
        self.assertEqual(self.shell('backup_bar ""'), "-")
        self.assertEqual(self.shell("backup_bar"), "-")

    def test_megabytes_is_the_one_unit_the_table_shows(self):
        for megabytes, expected in ((0, "-"), (4, "4 MB"), (1024, "1024 MB"), (19940000, "19940000 MB")):
            self.assertEqual(self.shell("backup_megabytes {}".format(megabytes)), expected)

    @NEEDS_GNU
    def test_list_draws_one_aligned_row_per_run(self):
        shutil.rmtree(join(self.home, "supervisor/backup/x"))
        for stage in ("primary", "secondary", "tertiary"):
            self.document("2026-09-08_00-00-00", stage, state="complete", success_bool=True,
                          trigger="scheduled", file_count=7, size_mb=2048, disk_usage_perc=61,
                          finished_ts="2026-09-08T00:10:00+08:00")
        self.document("2026-09-08_01-00-00", "primary", state="complete", success_bool=True, trigger="manual")
        self.document("2026-09-08_01-00-00", "tertiary", state="stopped", success_bool=False, trigger="manual")
        os.makedirs(join(self.home, "supervisor/backup", "2026-09-08_02-00-00"), exist_ok=True)
        listed = self.shell('backup_running() { return 1; }\nbackup_list')
        widths = {len(line) for line in listed.splitlines() if line}
        self.assertEqual(len(widths), 1, "every row must be the same width, got {}".format(sorted(widths)))
        self.assertIn("| RUN-ID ", listed)
        self.assertRegex(listed, r"2026-09-08_02-00-00 .*\|\s+-\s+\|")
        self.assertRegex(listed, r"2026-09-08_00-00-00 .*success .*success .*success .*\[#+\.*\]\s+61%.*complete")
        self.assertRegex(listed, r"2026-09-08_01-00-00 .*success .*-  .*stopped .*halted")

    @NEEDS_GNU
    def test_rollup_counts_halted_apart_from_failed(self):
        run = "2026-09-08_00-00-00"
        self.document(run, "primary", state="complete", success_bool=True)
        self.document(run, "secondary", state="timeout", success_bool=False)
        self.document(run, "tertiary", state="failed", success_bool=False)
        path = join(self.home, "supervisor/backup", run)
        self.shell('BACKUP_RUN_PATH="{}"; BACKUP_RUN_ID="{}"; BACKUP_TRIGGER=scheduled\n'
                   'backup_rollup "$(date +%s)"'.format(path, run))
        with open(join(path, "status.json")) as handle:
            document = json.load(handle)
        self.assertEqual(document["stages_run"], 3)
        self.assertEqual(document["stages_failed"], 1)
        self.assertEqual(document["stages_halted"], 1)
        self.assertEqual(document["state"], "failed")

    @NEEDS_GNU
    def test_rollup_calls_a_run_halted_when_nothing_actually_failed(self):
        run = "2026-09-08_01-00-00"
        self.document(run, "primary", state="complete", success_bool=True)
        self.document(run, "tertiary", state="stopped", success_bool=False)
        path = join(self.home, "supervisor/backup", run)
        self.shell('BACKUP_RUN_PATH="{}"; BACKUP_RUN_ID="{}"; BACKUP_TRIGGER=manual\n'
                   'backup_rollup "$(date +%s)"'.format(path, run))
        with open(join(path, "status.json")) as handle:
            document = json.load(handle)
        self.assertEqual(document["stages_failed"], 0)
        self.assertEqual(document["stages_halted"], 1)
        self.assertEqual(document["state"], "halted")
        self.assertFalse(document["success_bool"])

    @NEEDS_GNU
    def test_list_prefers_the_verdict_the_run_recorded(self):
        shutil.rmtree(join(self.home, "supervisor/backup/x"))
        run = "2026-09-08_00-00-00"
        for stage in ("primary", "secondary", "tertiary"):
            self.document(run, stage, state="complete", success_bool=True)
        with open(join(self.home, "supervisor/backup", run, "status.json"), "w") as handle:
            json.dump({"run_id": run, "state": "halted", "success_bool": False,
                       "stages_run": 3, "stages_halted": 1}, handle)
        listed = self.shell('backup_running() { return 1; }\nbackup_list')
        self.assertRegex(listed, r"2026-09-08_00-00-00 .*success .*success .*success .*halted")

    @NEEDS_GNU
    def test_list_still_computes_a_verdict_for_a_run_that_never_rolled_up(self):
        shutil.rmtree(join(self.home, "supervisor/backup/x"))
        run = "2026-09-08_00-00-00"
        self.document(run, "primary", state="complete", success_bool=True)
        self.document(run, "tertiary", state="timeout", success_bool=False)
        listed = self.shell('backup_running() { return 1; }\nbackup_list')
        self.assertRegex(listed, r"2026-09-08_00-00-00 .*success .*timeout .*halted")

    @NEEDS_GNU
    def test_list_ranks_running_over_failed_over_halted(self):
        shutil.rmtree(join(self.home, "supervisor/backup/x"))
        for name, states in (("2026-09-08_00-00-00", ("complete", "stopped", "complete")),
                             ("2026-09-08_01-00-00", ("failed", "stopped", "complete")),
                             ("2026-09-08_02-00-00", ("failed", "running", "complete"))):
            for stage, state in zip(("primary", "secondary", "tertiary"), states):
                self.document(name, stage, state=state, success_bool=state == "complete")
        listed = self.shell('backup_running() { return 1; }\nbackup_list')
        rows = {line.split("|")[1].strip(): line.split("|")[-2].strip()
                for line in listed.splitlines() if "2026-09-08_" in line}
        self.assertEqual(rows["2026-09-08_00-00-00"], "halted")
        self.assertEqual(rows["2026-09-08_01-00-00"], "failed")
        self.assertEqual(rows["2026-09-08_02-00-00"], "running")

    @NEEDS_GNU
    def test_scrub_document_records_the_cancel_deadline(self):
        written = self.shell(
            'BACKUP_STAGE_DIR="${{BACKUP_HOME_ROOT}}/stage"; BACKUP_RUN_ID=2026-09-08_00-00-00\n'
            'backup_scrub_document running false $(date +%s) 4096 12.5 0 0 0 "" 0 $(( $(date +%s) + 600 ))\n'
            'cat "${{BACKUP_STAGE_DIR}}/scrub.json"'.format())
        document = json.loads(written)
        self.assertEqual(document["state"], "running")
        self.assertEqual(document["scrubbed_mb"], 4096)
        self.assertEqual(document["progress_perc"], 12.5)
        self.assertNotEqual(document["expires_ts"], "")

    @NEEDS_GNU
    def test_progress_reports_the_scrub_rather_than_the_mirror_it_follows(self):
        run = "2026-09-08_00-00-00"
        self.document(run, "tertiary", state="running", size_mb=818461, total_mb=800086, duration_s=6940)
        self.scrub(run, "tertiary", state="running", duration_s=345, scrubbed_mb=62873, progress_perc=1.51,
                   expires_ts=subprocess.run(["date", "--iso-8601=seconds", "-d", "+47 min"],
                                             capture_output=True, text=True).stdout.strip())
        reported = self.shell(
            'backup_used() {{ echo $(( 4170 * 1073741824 )); }}\n'
            'mountpoint() {{ return 0; }}\n'
            'backup_progress "{}"'.format(join(self.home, "supervisor/backup", run)))
        self.assertIn("scrubbed [   61] GB of [ 4170] GB", reported)
        self.assertIn("at [  1] percent complete", reported)
        self.assertRegex(reported, r"estimated to complete in \[\s*4[67]\] min")
        self.assertIn("at [182] MB/s", reported)

    @NEEDS_GNU
    def test_progress_reports_the_mirror_when_no_scrub_is_running(self):
        run = "2026-09-08_00-00-00"
        self.document(run, "primary", state="running", size_mb=512, total_mb=1024, duration_s=64)
        reported = self.shell('backup_progress "{}"'.format(join(self.home, "supervisor/backup", run)))
        self.assertIn("exported [    0] GB of [    1] GB", reported)
        self.assertIn("at [ 50] percent complete", reported)

    @NEEDS_GNU
    def test_expected_is_what_the_mirror_last_moved_not_the_disk_against_the_sources(self):
        detached = 'backup_mounted() { :; }\nmountpoint() { return 1; }\n'
        self.assertEqual(self.shell(detached + 'backup_expected'), "0")
        self.document("2026-09-08_00-00-00", "tertiary", state="complete", size_mb=4096, duration_s=600)
        self.assertEqual(self.shell(detached + 'backup_expected'), str(4096 * 1048576))

    @NEEDS_GNU
    def test_expected_reads_zero_from_an_in_sync_run_rather_than_calling_it_no_history(self):
        self.document("2026-09-08_00-00-00", "tertiary", state="complete", size_mb=0, duration_s=31)
        self.assertEqual(self.shell('backup_mounted() { echo /share/40; }\n'
                                    'mountpoint() { return 1; }\n'
                                    'backup_used() { echo $(( 200 * 1073741824 )); }\n'
                                    'backup_expected'), "0")
        self.assertEqual(self.shell('mountpoint() { return 1; }\nbackup_pending tertiary'), "0")

    @NEEDS_GNU
    def test_expected_prefers_what_is_left_over_what_a_big_earlier_run_moved(self):
        self.document("2026-09-08_00-00-00", "tertiary", state="complete", size_mb=5000000, duration_s=36000)
        expected = self.shell('backup_mounted() { echo /share/40; }\n'
                              'mountpoint() { return 0; }\n'
                              'backup_used() { case "$1" in /backup) echo $(( 190 * 1073741824 ));; '
                              '*) echo $(( 200 * 1073741824 ));; esac; }\n'
                              'backup_expected')
        self.assertEqual(expected, str(10 * 1073741824))

    @NEEDS_GNU
    def test_expected_counts_only_what_a_resumed_mirror_has_left_to_move(self):
        expected = self.shell('backup_mounted() { echo /share/40; }\n'
                              'mountpoint() { return 0; }\n'
                              'backup_used() { case "$1" in /backup) echo $(( 30 * 1073741824 ));; '
                              '*) echo $(( 200 * 1073741824 ));; esac; }\n'
                              'backup_expected')
        self.assertEqual(expected, str(170 * 1073741824))

    @NEEDS_GNU
    def test_expected_falls_back_to_the_whole_source_for_a_first_mirror(self):
        mirrored = self.shell('backup_mounted() { echo /share/40; }\n'
                            'mountpoint() { return 1; }\n'
                            'backup_used() { echo $(( 200 * 1073741824 )); }\n'
                            'backup_expected')
        self.assertEqual(mirrored, str(200 * 1073741824))

    @NEEDS_GNU
    def test_pending_prices_tertiary_from_what_is_left_not_a_previous_duration(self):
        self.document("2026-09-08_00-00-00", "tertiary", state="complete", size_mb=1, duration_s=28800)
        self.assertEqual(self.shell('backup_mounted() { :; }\nmountpoint() { return 1; }\n'
                                    'backup_pending tertiary'), "0")

    @NEEDS_GNU
    def test_pending_prices_the_expected_bytes_at_the_measured_rate(self):
        self.document("2026-09-08_00-00-00", "tertiary", state="complete", size_mb=36000, duration_s=360)
        self.assertEqual(self.shell('backup_mounted() { :; }\nmountpoint() { return 1; }\n'
                                    'backup_pending tertiary'), "6")

    @NEEDS_GNU
    def test_rate_discounts_the_scrub_from_the_run_it_shared_a_stage_with(self):
        self.document("2026-09-08_00-00-00", "tertiary", state="complete", size_mb=6000, duration_s=3600)
        self.assertEqual(self.shell("backup_rate tertiary"), "1 measured")
        self.scrub("2026-09-08_00-00-00", "tertiary", state="interrupted", duration_s=3540)
        self.assertEqual(self.shell("backup_rate tertiary"), "100 measured")

    @NEEDS_GNU
    def test_counted_floors_the_size_by_what_the_disk_actually_grew(self):
        head = ('BACKUP_STAGE=tertiary; BACKUP_STAGE_DIR="${BACKUP_HOME_ROOT}"\n'
                'BACKUP_TOTAL=0; BACKUP_USAGE=0; BACKUP_FILES=0; BACKUP_FILES_HELD=0\n'
                'BACKUP_FILES_CREATED=0; BACKUP_FILES_DELETED=0; BACKUP_SIZE_HELD=0; BACKUP_SENT=0\n'
                'echo $(( 2242 * 1073741824 )) >"${BACKUP_HOME_ROOT}/disk-start"\n'
                'mountpoint() { return 0; }\n'
                'backup_used() { echo $(( 3094 * 1073741824 )); }\n')
        self.assertEqual(self.shell(head + 'BACKUP_SIZE=34\nbackup_counted; echo "${BACKUP_SIZE}"'),
                         str(852 * 1024))
        self.assertEqual(self.shell(head + 'BACKUP_SIZE=999999999\nbackup_counted; echo "${BACKUP_SIZE}"'),
                         "999999999")
        self.assertEqual(self.shell(head.replace("BACKUP_STAGE=tertiary", "BACKUP_STAGE=primary") +
                                    'BACKUP_SIZE=34\nbackup_counted; echo "${BACKUP_SIZE}"'), "34")

    def test_reaped_returns_at_once_when_nothing_holds_the_disk(self):
        self.assertEqual(self.shell('pattern="zzznothing""holdsthis"\n'
                                    'backup_reaped "${pattern}" && echo gone'), "gone")

    def test_reaped_gives_up_and_warns_rather_than_waiting_forever(self):
        out = self.shell('sleep 30 & backup_reaped "sleep 30" || echo waited\nkill %1 2>/dev/null',
                         BACKUP_REAP_WAIT=1)
        self.assertIn("waited", out)

    @NEEDS_GNU
    def test_mirroring_withholds_the_rate_and_estimate_until_the_window_answers(self):
        raw, path = self.ramp()
        fields = self.shell('backup_used() {{ echo {}; }}\n'
                            'backup_mirroring "{}" | tr "\\t" " "'.format(raw, path))
        copied, total, percent, remaining, rate, _ = fields.split()
        self.assertEqual(copied, "852")
        self.assertEqual(total, "900")
        self.assertEqual(percent, "94")
        self.assertEqual(rate, "-")
        self.assertEqual(remaining, "-")

    @NEEDS_GNU
    def test_mirroring_rates_the_span_the_window_covers(self):
        raw, path = self.ramp()
        stage = join(path, "stage/tertiary")
        now = int(time.time())
        with open(join(stage, "samples"), "w") as handle:
            handle.write("{} {}\n".format(now - 300, raw - 200 * 300 * 1048576))
            handle.write("{} {}\n".format(now - 10, raw - 200 * 10 * 1048576))
        self.assertAlmostEqual(int(self.rated(raw, path)), 200, delta=3)

    def test_heartbeat_never_sleeps_on_a_disabled_progress_interval(self):
        with open(BACKUP_SCRIPT) as handle:
            body = handle.read()
        self.assertNotIn('sleep "${BACKUP_TAIL_PROGRESS', body)

    def test_counted_is_reached_only_from_the_interrupted_path(self):
        with open(BACKUP_SCRIPT) as handle:
            calls = [line for line in handle if line.strip() == "backup_counted"]
        self.assertEqual(len(calls), 1)

    @NEEDS_GNU
    def test_mirroring_rates_early_once_enough_bytes_have_landed(self):
        raw, path = self.ramp()
        with open(join(path, "stage/tertiary/samples"), "w") as handle:
            handle.write("{} {}\n".format(int(time.time()) - 30, raw - 4 * 1073741824))
        self.assertAlmostEqual(int(self.rated(raw, path)), 4096 // 30, delta=4)

    @NEEDS_GNU
    def test_mirroring_withholds_the_rate_below_both_the_span_and_the_evidence(self):
        raw, path = self.ramp()
        stage = join(path, "stage/tertiary")
        with open(join(stage, "samples"), "w") as handle:
            handle.write("{} {}\n".format(int(time.time()) - 60, raw - 1073741824))
        self.assertEqual(self.rated(raw, path), "-")

    @NEEDS_GNU
    def test_mirroring_ignores_a_truncated_sample_rather_than_rating_the_whole_disk(self):
        raw, path = self.ramp()
        with open(join(path, "stage/tertiary/samples"), "w") as handle:
            handle.write("{}\n".format(int(time.time()) - 300))
        self.assertEqual(self.rated(raw, path), "-")

    @NEEDS_GNU
    def test_mirroring_records_a_sample_and_forgets_what_falls_out_of_the_window(self):
        raw, path = self.ramp()
        samples = join(path, "stage/tertiary/samples")
        now = int(time.time())
        with open(samples, "w") as handle:
            handle.write("{} 1\n{} {}\n".format(now - 900, now - 200, raw - 200 * 200 * 1048576))
        self.assertAlmostEqual(int(self.rated(raw, path, record="record")), 200, delta=3)
        with open(samples) as handle:
            kept = [line.split()[0] for line in handle if line.strip()]
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0], str(now - 200))
        self.assertGreaterEqual(int(kept[1]), now)

    def ramp(self):
        run = "2026-09-08_00-00-00"
        path = join(self.home, "supervisor/backup", run)
        self.document(run, "tertiary", state="running", size_mb=0, total_mb=900 * 1024, duration_s=6733)
        with open(join(path, "stage/tertiary/disk-start"), "w") as handle:
            handle.write(str(2242 * 1073741824))
        return 3094 * 1073741824, path

    def rated(self, raw, path, record=""):
        return self.shell('backup_used() {{ echo {}; }}\n'
                          'backup_mirroring "{}" "{}" | cut -f5'.format(raw, path, record))

    @NEEDS_GNU
    def test_progress_measures_the_bytes_this_run_moved_not_what_the_disk_holds(self):
        run = "2026-09-08_00-00-00"
        path = join(self.home, "supervisor/backup", run)
        self.document(run, "tertiary", state="running", size_mb=0, total_mb=100 * 1024, duration_s=60)
        with open(join(path, "stage/tertiary/disk-start"), "w") as handle:
            handle.write(str(4000 * 1073741824))
        reported = self.shell(
            'backup_used() {{ echo $(( 4025 * 1073741824 )); }}\n'
            'mountpoint() {{ return 0; }}\n'
            'backup_progress "{}"'.format(path))
        self.assertIn("mirrored [   25] GB of [  100] GB", reported)
        self.assertIn("at [ 25] percent complete", reported)

    @NEEDS_GNU
    def test_progress_can_no_longer_report_more_than_it_set_out_to_move(self):
        run = "2026-09-08_00-00-00"
        path = join(self.home, "supervisor/backup", run)
        self.document(run, "tertiary", state="running", size_mb=1, total_mb=1, duration_s=34)
        with open(join(path, "stage/tertiary/disk-start"), "w") as handle:
            handle.write(str(4170 * 1073741824))
        reported = self.shell(
            'backup_used() {{ echo $(( 4170 * 1073741824 )); }}\n'
            'mountpoint() {{ return 0; }}\n'
            'backup_progress "{}"'.format(path))
        self.assertEqual(reported, "")

    @NEEDS_GNU
    def test_usage_publishes_the_percentage_from_the_btrfs_route_as_well_as_df(self):
        sysfs = join(self.home, "sysfs", "deadbeef")
        os.makedirs(join(sysfs, "devices/sdc1"))
        with open(join(sysfs, "devices/sdc1/size"), "w") as handle:
            handle.write("11721043086")
        for allocation, value in (("data", 4458681745408), ("metadata", 9624403968), ("system", 458752)):
            os.makedirs(join(sysfs, "allocation", allocation))
            with open(join(sysfs, "allocation", allocation, "bytes_used"), "w") as handle:
                handle.write(str(value))
        published = self.shell(
            'BACKUP_STAGE_DIR="${BACKUP_HOME_ROOT}"; BACKUP_USAGE=0; BACKUP_TOTAL=0; BACKUP_FILES=0\n'
            'BACKUP_SIZE=0; BACKUP_FILES_HELD=0; BACKUP_FILES_CREATED=0; BACKUP_FILES_DELETED=0\n'
            'BACKUP_SIZE_HELD=0; BACKUP_SENT=0\n'
            'btrfs() { echo "Label: \'backup_04\'  uuid: deadbeef"; }\n'
            'backup_usage /backup\n'
            'printf "%s %s" "${BACKUP_USAGE}" "$(cut -d" " -f2 "${BACKUP_HOME_ROOT}/counters")"',
            BACKUP_SYSFS_BTRFS=join(self.home, "sysfs"))
        self.assertEqual(published, "74 74")

    def test_detach_is_silent_when_another_process_won_the_unmount(self):
        head = ('MARK="${BACKUP_HOME_ROOT}/mounted"; touch "${MARK}"\n'
                'backup_targets() { echo /backup; }\n'
                'sync() { :; }\n'
                'mountpoint() { [ -f "${MARK}" ]; }\n')
        self.assertEqual(self.shell(head + 'umount() { rm -f "${MARK}"; return 0; }\nbackup_detach 2>&1'), "")
        self.assertEqual(self.shell(head + 'umount() { rm -f "${MARK}"; echo "umount: /backup: not mounted." >&2; return 1; }\n'
                                           'backup_detach 2>&1'), "")

    def test_detach_still_warns_when_the_mount_survives(self):
        reported = self.shell('backup_targets() { echo /backup; }\n'
                              'sync() { :; }\n'
                              'mountpoint() { return 0; }\n'
                              'umount() { echo "umount: /backup: target is busy." >&2; return 1; }\n'
                              'backup_detach 2>&1')
        self.assertIn("unmount of [/backup] failed with [umount: /backup: target is busy.], detaching lazily", reported)
        self.assertIn("could not detach [/backup]", reported)

    @NEEDS_GNU
    def test_tail_field_reads_json(self):
        document = self.document("2026-09-08_00-00-00", "primary", state="complete", size_mb=388)
        self.assertEqual(self.shell('backup_tail_field "{}" size_mb'.format(document)), "388")
        self.assertEqual(self.shell('backup_tail_field "{}" absent'.format(document)), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
