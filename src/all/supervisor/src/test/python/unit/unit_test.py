import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime
from os.path import abspath, dirname, exists, join, realpath

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
BACKUPS_SCRIPT = join(DIR_ROOT, "src/main/resources/image/backups.sh")


class BackupsShellTest(unittest.TestCase):

    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.config = join(self.workdir, "config.json")

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def hosts(self, *names):
        with open(self.config, "w") as handle:
            json.dump({"asystem": {"schema": [{"host": name} for name in names]}}, handle)

    def shell(self, snippet, keep_blanks=False, **environment):
        script = 'set -uo pipefail\nsource "{}"\n{}'.format(BACKUPS_SCRIPT, snippet)
        env = {key: value for key, value in os.environ.items() if not key.startswith("BACKUPS_")}
        env.update({"BACKUPS_SOURCE_ONLY": "1", "BACKUPS_CONFIG": self.config})
        env.update({key: str(value) for key, value in environment.items()})
        done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, "stderr: {}".format(done.stderr))
        return done.stdout.rstrip("\n") if keep_blanks else done.stdout.strip()

    def invoke(self, *arguments, **environment):
        env = {key: value for key, value in os.environ.items() if not key.startswith("BACKUPS_")}
        env.update({key: str(value) for key, value in environment.items()})
        return subprocess.run([BACKUPS_SCRIPT, *arguments], capture_output=True, text=True, env=env)

    def test_hosts_reads_the_schema_list_out_of_config_json(self):
        self.hosts("macmini-mad", "macmini-max", "raspbpi-jen")
        self.assertEqual(self.shell("backups_hosts"), "macmini-mad\nmacmini-max\nraspbpi-jen")

    def test_each_reaches_every_host_even_when_the_action_drains_stdin(self):
        self.hosts("macmini-mad", "macmini-max", "macmini-may", "raspbpi-jen")
        reached = self.shell('drains() { cat >/dev/null; printf "%s\\n" "$1"; }\n'
                             'backups_each drains')
        self.assertEqual(reached.split(),
                         ["macmini-mad", "macmini-max", "macmini-may", "raspbpi-jen"],
                         "ssh reading stdin must not swallow the remaining hosts")

    def test_each_starts_no_further_host_once_interrupted(self):
        self.hosts("macmini-mad", "macmini-max", "macmini-may")
        reached = self.shell('names() { printf "%s\\n" "$1"; '
                             '[ "$1" = "macmini-mad" ] && backups_interrupt 2>/dev/null; return 0; }\n'
                             'backups_each names; printf "exit=%s" "$?"')
        self.assertIn("macmini-mad", reached)
        self.assertNotIn("macmini-max", reached, "an interrupt must stop the loop reaching later hosts")
        self.assertIn("exit=130", reached)

    def test_start_scrubs_only_when_asked(self):
        self.hosts("h1")
        capture = join(self.workdir, "ssh-args")
        probe = ('ssh() { for a in "$@"; do c="$a"; done; printf "%s\\n" "${c}" >>"' + capture + '"; }\n'
                 'BACKUPS_RUN_ID=2026-09-15_00-00-00 BACKUPS_RUN_HOURS=9\n'
                 'backups_each backups_start_one >/dev/null')
        self.shell(probe, BACKUPS_SETTLE_SECONDS=0)
        with open(capture) as handle:
            self.assertNotIn("--scrub", handle.read(),
                             "a cluster backup run must not force an hours-long scrub by default")
        os.remove(capture)
        self.shell(probe, BACKUPS_SCRUB=1, BACKUPS_SETTLE_SECONDS=0)
        with open(capture) as handle:
            self.assertIn("--scrub", handle.read())

    def test_scrub_is_refused_against_a_command_that_cannot_scrub(self):
        self.hosts("h1")
        done = self.invoke("list", "--scrub", BACKUPS_CONFIG=self.config)
        self.assertIn("[--scrub] is only valid for [start]", done.stdout + done.stderr)
        self.assertEqual(done.returncode, 2)

    def test_an_unknown_option_is_refused_with_exit_2(self):
        self.hosts("h1")
        done = self.invoke("start", "--nope", BACKUPS_CONFIG=self.config)
        self.assertIn("[--nope] is not an option", done.stdout + done.stderr)
        self.assertEqual(done.returncode, 2)

    def test_dispatch_returns_the_status_ssh_gave_it(self):
        self.hosts()
        self.assertEqual(self.shell('ssh() { return 255; }\n'
                                    'backups_dispatch macmini-mad stop >/dev/null 2>&1; printf "exit=%s" "$?"'),
                         "exit=255")
        self.assertEqual(self.shell('ssh() { return 0; }\n'
                                    'backups_dispatch macmini-mad stop >/dev/null 2>&1; printf "exit=%s" "$?"'),
                         "exit=0")

    def test_timeout_never_outlives_the_scheduled_run(self):
        scheduled = datetime(2026, 9, 15, 1, 0).timestamp()
        for hour, minute, expected in ((10, 19, 14), (18, 0, 6), (23, 30, 1), (0, 30, 1), (1, 30, 23)):
            now = datetime(2026, 9, 15, hour, minute).timestamp()
            stub = ('date() { case "$*" in\n'
                    '  "+%s") printf "%s" ' + str(int(now)) + ' ;;\n'
                    '  "-d today 1:00:00 +%s") printf "%s" ' + str(int(scheduled)) + ' ;;\n'
                    '  *) command date "$@" ;;\n'
                    'esac; }\n'
                    'backups_timeout_hours')
            hours = int(self.shell(stub))
            self.assertEqual(hours, expected, "started at [{:02d}:{:02d}]".format(hour, minute))
            self.assertGreaterEqual(hours, 1, "a run always gets at least an hour")

    def test_tail_is_a_command_the_dispatcher_accepts(self):
        self.hosts()
        done = self.invoke("tail", BACKUPS_CONFIG=self.config)
        self.assertNotIn("unknown command", done.stdout + done.stderr)

    def test_hosts_is_empty_and_not_an_error_over_an_empty_schema(self):
        self.hosts()
        self.assertEqual(self.shell("backups_hosts"), "")

    def test_hosts_fails_loudly_when_config_json_is_missing(self):
        done = self.shell('backups_hosts >/dev/null 2>&1; echo "exit=$?"')
        self.assertEqual(done, "exit=1")

    def test_timeout_hours_honours_an_explicit_override(self):
        self.hosts()
        self.assertEqual(self.shell("backups_timeout_hours", BACKUPS_TIMEOUT_HOURS="9"), "9")

    def test_timeout_hours_is_computed_and_always_at_least_one(self):
        self.hosts()
        computed = int(self.shell("backups_timeout_hours"))
        self.assertGreaterEqual(computed, 1)
        self.assertLessEqual(computed, 24)

    def test_timeout_hours_falls_back_when_the_scheduled_run_cannot_be_resolved(self):
        self.hosts()
        broken = 'backups_scheduled() { printf ""; }\nbackups_timeout_hours 2>/dev/null'
        self.assertEqual(self.shell(broken), str(6))

    def test_help_lists_start_stop_list_help(self):
        done = self.invoke("help")
        self.assertEqual(done.returncode, 0)
        for word in ("start", "stop", "list", "help"):
            self.assertIn(word, done.stdout)

    def test_unknown_command_is_refused_with_exit_2(self):
        done = self.invoke("bogus")
        self.assertEqual(done.returncode, 2)
        self.assertIn("[bogus] is not a command", done.stderr)

    def test_start_reports_no_enrolled_hosts_rather_than_silently_doing_nothing(self):
        self.hosts()
        done = self.invoke("start", BACKUPS_CONFIG=self.config)
        self.assertEqual(done.returncode, 1)
        self.assertIn("[none] enrolled hosts found", done.stderr)

    def test_start_one_dispatches_a_detached_run_with_the_computed_timeout(self):
        self.hosts()
        capture = join(self.workdir, "ssh-args")
        probe = ('ssh() { for a in "$@"; do c="$a"; done; printf "%s\\n" "${c}" >>"' + capture + '"; }\n'
                 'BACKUPS_RUN_ID=2026-09-15_00-00-00 BACKUPS_RUN_HOURS=9\n'
                 'backups_start_one macmini-mad >/dev/null')
        self.shell(probe)
        with open(capture) as handle:
            line = handle.read()
        self.assertIn("BACKUP_TIMEOUT_HOURS=9", line)
        self.assertIn("abackup start 2026-09-15_00-00-00", line)
        self.assertNotIn("--scrub", line)
        self.assertIn("nohup", line)
        self.assertIn("disown", line)
        os.remove(capture)
        self.shell(probe, BACKUPS_SCRUB=1)
        with open(capture) as handle:
            self.assertIn("--scrub", handle.read())

    def test_start_one_names_the_host_it_dispatched_to(self):
        self.hosts()
        probe = ('ssh() { return 0; }\n'
                 'BACKUPS_RUN_ID=2026-09-15_00-00-00 BACKUPS_RUN_HOURS=9\n'
                 'backups_start_one macmini-mad')
        self.assertRegex(self.shell(probe).split("\n")[-1],
                         r"^\d\d-\d\dT\d\d:\d\d:\d\d INFO  backup\s+start\s+0ms launched "
                         r"\[2026-09-15_00-00-00\] dispatched to \[macmini-mad\] with timeout \[9\] hours and scrub \[off\]$")

    def test_start_one_says_nothing_about_a_host_that_did_not_answer(self):
        self.hosts()
        probe = ('ssh() { echo "ssh: could not resolve" >&2; return 255; }\n'
                 'BACKUPS_RUN_ID=r BACKUPS_RUN_HOURS=9\n'
                 'backups_start_one raspbpi-jil 2>&1 || printf "exit=%s" "$?"')
        reported = self.shell(probe)
        self.assertNotIn("raspbpi-jil", reported.replace("exit=255", ""))
        self.assertIn("exit=255", reported)

    def test_dispatch_sends_the_plain_subcommand_for_every_read_verb(self):
        self.hosts()
        probe = 'ssh() {{ shift 5; echo "$*"; }}\nbackups_dispatch macmini-mad {command}'
        for command in ("tail", "stop", "list", "clean"):
            self.assertIn("/usr/local/bin/abackup " + command, self.shell(probe.format(command=command)),
                          "[{}] must reach the host as the bare remote subcommand".format(command))

    def test_each_hands_its_extra_arguments_to_the_action_after_the_host(self):
        self.hosts("h1", "h2")
        reached = self.shell('names() { printf "%s/%s\\n" "$1" "$2"; }\n'
                             'backups_each names clean')
        self.assertEqual(reached.split(), ["h1/clean", "h2/clean"],
                         "one dispatch serves every verb, so the verb travels with the host")

    def test_dispatch_connects_as_root_with_a_bounded_connect_timeout(self):
        self.hosts()
        probe = 'ssh() { printf "ARG %s\\n" "$@"; }\nbackups_dispatch macmini-mad stop'
        args = [line[4:] for line in self.shell(probe).splitlines() if line.startswith("ARG ")]
        self.assertEqual(args[:5], ["-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"],
                         "stdin must be closed so a host list read by the loop is never swallowed")
        self.assertIn("root@macmini-mad", args)

    def test_dispatch_hides_a_host_that_did_not_answer(self):
        self.hosts()
        probe = ('ssh() { echo "ssh: could not resolve hostname" >&2; return 255; }\n'
                 'backups_dispatch macmini-mad stop 2>&1 || printf "exit=%s" "$?"')
        reported = self.shell(probe)
        self.assertNotIn("== macmini-mad", reported, "an unreachable host prints no header")
        self.assertNotIn("could not resolve", reported, "its ssh error is hidden too")
        self.assertIn("exit=255", reported, "but the status still records it")

    def test_dispatch_prints_one_blank_line_around_a_host_block(self):
        self.hosts()
        probe = ('ssh() { printf "\\n\\n+----+\\n| row |\\n\\n\\n| row |\\n+----+\\n\\n\\n"; }\n'
                 'backups_dispatch macmini-mad stop')
        lines = self.shell(probe, keep_blanks=True).split("\n")
        self.assertEqual(lines, ["", "\033[1;35m== macmini-mad stop ==\033[0m", "", "+----+", "| row |", "", "| row |", "+----+"],
                         "blank runs collapse to one and trailing blanks are dropped")

    def test_messages_name_the_installed_command_not_the_script_path(self):
        self.hosts()
        helped = self.shell('backups_help help 2>&1', keep_blanks=True)
        self.assertIn("Usage: abackups [command]", helped,
                      "help must name the command an operator can type, not the script it reaches")
        interrupted = self.shell('backups_interrupt 2>&1')
        self.assertIn("[abackups tail]", interrupted)
        self.assertIn("[abackups stop]", interrupted)
        self.assertNotIn("backups.sh", helped + interrupted,
                         "the script path is not a command anyone can run")

    def test_every_log_line_shares_the_supervisor_column_layout(self):
        self.hosts()
        header = "TIME           LEVEL SOURCE           SUBJECT                   ACTION     DURATION DETAIL"
        lines = self.shell('backups_log INFO start launched "[a] message"').split("\n")
        self.assertEqual(lines[0], header,
                         "the header must match scribe's own, since abackups tail interleaves both scripts' output")
        self.assertRegex(lines[1],
                         r"^\d\d-\d\dT\d\d:\d\d:\d\d INFO  backup                                     "
                         r"start           0ms launched \[a\] message$")
        warned = self.shell('backups_log WARN stop faulting "[b] warning" 2>&1').split("\n")
        self.assertEqual(warned[0], header)
        self.assertRegex(warned[1],
                         r"^\d\d-\d\dT\d\d:\d\d:\d\d WARN  backup                                     "
                         r"stop            0ms faulting \[b\] warning$")

    def test_the_header_is_printed_once_however_many_lines_follow(self):
        self.hosts()
        lines = self.shell('backups_log INFO start launched "[a] one"\nbackups_log INFO stop finished "[a] two"').split("\n")
        self.assertEqual(len(lines), 3, "one header and two lines")
        self.assertNotIn("SUBJECT", lines[2])

    def test_each_continues_past_a_failing_host_and_still_reaches_every_other(self):
        self.hosts("h1", "h2", "h3")
        probe = ('ssh() { local d; for d; do case "${d}" in *@*) break ;; esac; done\n'
                 '  case "${d}" in *h2) return 1 ;; *) echo "reached ${d}" ;; esac; }\n'
                 'backups_each backups_dispatch stop; echo "exit=$?"')
        lines = self.shell(probe).splitlines()
        self.assertIn("reached root@h1", lines)
        self.assertIn("reached root@h3", lines)
        self.assertNotIn("reached root@h2", lines)
        self.assertEqual(lines[-1], "exit=3", "a host that did not answer must reach the exit code")

    def test_every_command_carries_a_failing_host_through_to_its_exit_code(self):
        self.hosts("h1", "h2")
        for command in ("backups_stop", "backups_list", "backups_tail"):
            self.assertEqual(self.shell('ssh() { return 255; }\n'
                                        + command + ' >/dev/null 2>&1; printf "exit=%s" "$?"'),
                             "exit=3", "[{}] must not swallow a host that did not answer".format(command))
            self.assertEqual(self.shell('ssh() { echo reached; }\n'
                                        + command + ' >/dev/null 2>&1; printf "exit=%s" "$?"'),
                             "exit=0", "[{}] must exit clean when every host answered".format(command))

    def test_start_dispatches_every_host_then_tails_every_host(self):
        self.hosts("h1", "h2", "h3")
        capture = join(self.workdir, "ssh-hosts")
        probe = ('ssh() { local d; for d; do case "${d}" in *@*) break ;; esac; done\n'
                 '  printf "%s\\n" "${d}" >>"' + capture + '"; }\n'
                 'backups_start >/dev/null')
        self.shell(probe, BACKUPS_SETTLE_SECONDS=0)
        with open(capture) as handle:
            order = [line for line in handle.read().splitlines() if line.startswith("root@")]
        self.assertEqual(order, ["root@h1", "root@h2", "root@h3",
                                 "root@h1", "root@h2", "root@h3"],
                         "every host is dispatched first, so the runs proceed in parallel, then tailed")


INSTALL_PREP_SCRIPT = join(DIR_ROOT, "install_prep.sh")


class InstallPrepShellTest(unittest.TestCase):

    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.mount = join(self.workdir, "backup")
        self.fstab = join(self.workdir, "fstab")
        self.stubs = join(self.workdir, "stubs")
        os.makedirs(self.stubs)
        self.stub("chattr", 0)
        self.stub("mountpoint", 1)

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def stub(self, name, status):
        path = join(self.stubs, name)
        with open(path, "w") as handle:
            handle.write('#!/bin/sh\nprintf "%s %s\\n" "{}" "$*" >>"{}"\nexit {}\n'
                         .format(name, join(self.workdir, "calls"), status))
        os.chmod(path, 0o755)

    def declare(self):
        with open(self.fstab, "w") as handle:
            handle.write("# a comment  {}  btrfs  noauto  0 2\n".format(self.mount))
            handle.write("PARTLABEL=backup_02  {}  btrfs  noauto  0 2\n".format(self.mount))

    def invoke(self):
        env = dict(os.environ, PATH=self.stubs + ":" + os.environ["PATH"],
                   BACKUP_MOUNT=self.mount, BACKUP_FSTAB=self.fstab)
        done = subprocess.run(["bash", INSTALL_PREP_SCRIPT], capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, "the hook must never fail an install: " + done.stderr)
        return done.stdout + done.stderr

    def calls(self):
        try:
            with open(join(self.workdir, "calls")) as handle:
                return handle.read()
        except FileNotFoundError:
            return ""

    def test_a_host_declaring_no_backup_mount_is_left_alone(self):
        with open(self.fstab, "w") as handle:
            handle.write("/dev/sda1  /home  ext4  defaults  0 2\n")
        self.assertEqual(self.invoke(), "")
        self.assertNotIn("chattr", self.calls())
        self.assertFalse(os.path.exists(self.mount), "it must not create a mountpoint the host never declared")

    def test_a_declared_mountpoint_is_created_and_made_immutable(self):
        self.declare()
        self.assertIn("Protected", self.invoke())
        self.assertTrue(os.path.isdir(self.mount))
        self.assertIn("chattr +i", self.calls())

    def test_a_mounted_backup_disk_is_never_touched(self):
        self.declare()
        os.makedirs(self.mount)
        self.stub("mountpoint", 0)
        self.assertIn("it is mounted", self.invoke())
        self.assertNotIn("chattr", self.calls(), "making the mounted disk immutable would break every backup")

    def test_data_written_while_unmounted_is_reported_rather_than_frozen(self):
        self.declare()
        os.makedirs(self.mount)
        open(join(self.mount, "stray"), "w").close()
        reported = self.invoke()
        self.assertIn("written while unmounted", reported)
        self.assertNotIn("chattr", self.calls(), "freezing stray data would make it undeletable")

    def test_a_filesystem_without_immutable_support_warns_and_carries_on(self):
        self.declare()
        self.stub("chattr", 1)
        self.assertIn("Could not make", self.invoke())


INSTALL_POST_SCRIPT = join(DIR_ROOT, "install_post.sh")


class InstallPostShellTest(unittest.TestCase):

    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.bin = join(self.workdir, "bin")
        self.install = join(self.workdir, "install", "supervisor", "latest")
        os.makedirs(self.bin)
        os.makedirs(self.install)
        with open(join(self.install, ".env"), "w") as handle:
            handle.write("BACKUP_TIMEOUT_HOURS=9\n")
        with open(join(self.install, "supervisor"), "w") as handle:
            handle.write('#!/bin/bash\necho "${BACKUP_TIMEOUT_HOURS:-unset} $*"\n')

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def invoke(self, form_factor):
        script = open(INSTALL_POST_SCRIPT).read() \
            .replace("/var/lib/asystem/install", join(self.workdir, "install")) \
            .replace("/usr/local/bin", self.bin)
        done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env={
            "PATH": os.environ["PATH"], "SERVICE_NAME": "supervisor", "SERVICE_FORM_FACTOR": form_factor})
        self.assertEqual(done.returncode, 0, "stderr: {}".format(done.stderr))

    def test_abackup_execs_the_binary_with_the_module_environment(self):
        self.invoke("server")
        wrapper = open(join(self.bin, "abackup")).read()
        self.assertIn('. "{}/.env"'.format(self.install), wrapper)
        self.assertIn('{}/supervisor backup "$@"'.format(self.install), wrapper)
        self.assertNotIn("backup.sh", wrapper)

    def test_a_client_host_is_given_no_abackup_wrapper(self):
        self.invoke("client")
        self.assertFalse(exists(join(self.bin, "abackup")))
        self.assertTrue(exists(join(self.bin, "atops")))

    def test_the_wrapper_exports_what_it_sources_and_forwards_its_arguments(self):
        self.invoke("edge")
        done = subprocess.run([join(self.bin, "abackup"), "start", "--scrub"], capture_output=True, text=True,
                              env={"PATH": os.environ["PATH"]})
        self.assertEqual(done.returncode, 0, "stderr: {}".format(done.stderr))
        self.assertEqual(done.stdout.strip(), "9 backup start --scrub")


if __name__ == "__main__":
    unittest.main(verbosity=2)
