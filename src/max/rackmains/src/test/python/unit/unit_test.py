import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from os.path import abspath, dirname, join, realpath

import pytest

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
INSTALL_PREP_SCRIPT = join(DIR_ROOT, "install_prep.sh")
INSTALL_PRE_SCRIPT = join(DIR_ROOT, "install_pre.sh")
DEVICE = "/run/nut/nutdrv_qx-powershield"
RESTART = "systemctl restart nut-driver@powershield.service nut-server.service"


class ShellHookTest(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.stubs = join(self.workdir, "stubs")
        os.makedirs(self.stubs)

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def stub(self, name, status):
        path = join(self.stubs, name)
        with open(path, "w") as handle:
            handle.write('#!/bin/sh\nprintf "%s %s\\n" "{}" "$*" >>"{}"\nexit {}\n'.format(name, join(self.workdir, "calls"), status))
        os.chmod(path, 0o755)

    def calls(self):
        try:
            with open(join(self.workdir, "calls")) as handle:
                return handle.read().splitlines()
        except FileNotFoundError:
            return []


class InstallPrepShellTest(ShellHookTest):
    def setUp(self):
        super().setUp()
        self.conf = join(self.workdir, "ups")
        self.env_file = join(self.workdir, ".env")
        os.makedirs(self.conf)
        for name in ("systemctl", "chown", "rpm", "dnf"):
            self.stub(name, 0)

    def environment(self, form_factor="server", command="install", device=DEVICE):
        with open(self.env_file, "w") as handle:
            handle.write(f"SERVICE_FORM_FACTOR={form_factor}\nSERVICE_COMMAND={command}\nRACKMAINS_DEVICE={device}\n")

    def invoke(self):
        env = dict(os.environ, PATH=self.stubs + ":" + os.environ["PATH"], ENV_FILE=self.env_file, NUT_CONF_DIR=self.conf)
        done = subprocess.run(["bash", INSTALL_PREP_SCRIPT], capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, "the hook must never fail an install: " + done.stderr)
        return done.stdout + done.stderr

    def read(self, name):
        with open(join(self.conf, name)) as handle:
            return handle.read()

    def write(self, name, text):
        with open(join(self.conf, name), "w") as handle:
            handle.write(text)

    def test_the_first_run_writes_the_configuration_and_starts_the_units(self):
        self.environment()
        reported = self.invoke()
        self.assertIn("MODE=standalone", self.read("nut.conf"))
        self.assertIn("LISTEN 127.0.0.1 3493", self.read("upsd.conf"))
        ups = self.read("ups.conf")
        for line in ("[powershield]", "driver = nutdrv_qx", "vendorid = 0665", "productid = 5161", "protocol = voltronic-qs", "pollfreq = 4"):
            self.assertIn(line, ups)
        self.assertEqual(reported.count("Updated ["), 3)
        calls = self.calls()
        self.assertIn("systemctl enable --now nut-driver@powershield.service nut-server.service", calls)
        self.assertEqual(calls.count(RESTART), 1, "three changed files still restart the units once")
        self.assertTrue([call for call in calls if call.startswith("chown root:nut ") and call.endswith("ups.conf")])

    def test_a_second_run_changes_nothing(self):
        self.environment()
        self.invoke()
        before = {name: self.read(name) for name in ("nut.conf", "ups.conf", "upsd.conf")}
        calls_before = len(self.calls())
        reported = self.invoke()
        self.assertNotIn("Updated", reported)
        self.assertEqual({name: self.read(name) for name in before}, before)
        self.assertNotIn(RESTART, self.calls()[calls_before:], "an unchanged configuration must not restart the driver or upsd")

    def test_a_drifted_file_is_corrected_and_the_units_restart_once(self):
        for name, drifted in (("ups.conf", "[powershield]\n    driver = other\n"), ("upsd.conf", "LISTEN 0.0.0.0 3493\n"), ("nut.conf", "MODE=none\n")):
            with self.subTest(name=name):
                self.environment()
                self.invoke()
                good = self.read(name)
                self.write(name, drifted)
                calls_before = len(self.calls())
                reported = self.invoke()
                self.assertEqual(reported.count("Updated ["), 1)
                self.assertEqual(self.read(name), good)
                self.assertEqual(self.calls()[calls_before:].count(RESTART), 1)

    def test_missing_packages_are_installed_once_and_present_ones_are_not(self):
        self.environment()
        self.invoke()
        self.assertNotIn("dnf install -y nut nut-client", self.calls())
        self.stub("rpm", 1)
        self.invoke()
        self.assertIn("dnf install -y nut nut-client", self.calls())

    def test_a_failed_package_install_leaves_the_host_alone(self):
        self.environment()
        self.stub("rpm", 1)
        self.stub("dnf", 1)
        self.assertIn("could not install", self.invoke())
        self.assertEqual(os.listdir(self.conf), [])
        self.assertNotIn("systemctl", " ".join(self.calls()))

    def test_other_commands_and_form_factors_do_nothing(self):
        for form_factor, command in (("server", "start"), ("server", "schema"), ("client", "install")):
            self.environment(form_factor=form_factor, command=command)
            self.assertEqual(self.invoke(), "")
        self.assertEqual(os.listdir(self.conf), [])
        self.assertEqual(self.calls(), [])

    def test_a_device_that_is_not_a_nutdrv_qx_socket_is_left_alone(self):
        for device in ("/run/nut/powershield", "/run/nut/usbhid-ups-powershield", "/run/nut/nutdrv_qx-"):
            self.environment(device=device)
            self.assertIn("Left [", self.invoke())
        self.assertEqual(os.listdir(self.conf), [])
        self.assertEqual(self.calls(), [])

    def test_the_ups_name_comes_from_the_device(self):
        self.environment(device="/run/nut/nutdrv_qx-rack")
        self.invoke()
        self.assertIn("[rack]", self.read("ups.conf"))
        self.assertIn("systemctl enable --now nut-driver@rack.service nut-server.service", self.calls())

    def test_a_unit_that_will_not_start_warns_and_carries_on(self):
        self.environment()
        self.stub("systemctl", 1)
        self.assertIn("Could not enable", self.invoke())


class InstallPreShellTest(ShellHookTest):
    def setUp(self):
        super().setUp()
        self.module = join(self.workdir, "module")
        os.makedirs(join(self.module, "image"))
        shutil.copy(INSTALL_PRE_SCRIPT, self.module)
        self.broker = join(self.module, "image", "broker.sh")

    def broker_script(self):
        with open(self.broker, "w") as handle:
            handle.write(f'#!/bin/sh\necho "broker $*" >>"{join(self.workdir, "calls")}"\n')
        os.chmod(self.broker, 0o755)

    def invoke(self, changed):
        env = {key: value for key, value in os.environ.items() if key != "SERVICE_VERSION_CHANGED"}
        if changed is not None:
            env["SERVICE_VERSION_CHANGED"] = changed
        done = subprocess.run(["bash", join(self.module, "install_pre.sh")], capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, "the hook must never fail an install: " + done.stderr)

    def test_the_discovery_is_published_only_when_the_version_changed(self):
        self.broker_script()
        for changed in ("false", "", None):
            self.invoke(changed)
        self.assertEqual(self.calls(), [])
        self.invoke("true")
        self.assertEqual(self.calls(), ["broker "])

    def test_a_module_with_no_generated_broker_script_is_left_alone(self):
        self.invoke("true")
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    sys.exit(
        pytest.main(
            [
                "-s",
                "-v",
                "--durations=50",
                "-o",
                f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}",
                __file__,
            ]
        )
    )
