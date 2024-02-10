import unittest
from os.path import *
from unittest.mock import patch, MagicMock

import pytest
import sys

sys.path.append('../../../main/python')

from supervisor.main import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


class MonitorTest(unittest.TestCase):

    def test_no_docker_installed(self):
        with patch("supervisor.main.docker_client_from_env", MagicMock(return_value=None)):
            self._run_test("sleep-1", RUN_CODE_NOT_ALL_UP, 1)

    def test_no_docker_noinstalled(self):
        with patch("supervisor.main.docker_client_from_env", MagicMock(return_value=None)):
            self._run_test("nonexistant", RUN_CODE_NONE_INSTALLED)

    def test_nonexistant(self):
        self._run_test("nonexistant", RUN_CODE_NONE_INSTALLED)

    def test_corrupt(self):
        self._run_test("corrupt", RUN_CODE_NONE_INSTALLED)

    def test_empty(self):
        self._run_test("empty", RUN_CODE_NONE_INSTALLED)

    def test_none(self):
        self._run_test("none", RUN_CODE_NONE_INSTALLED)

    def test_none_alien(self):
        self._run_test("none", RUN_CODE_NONE_INSTALLED, 1)

    def test_1_installed_down(self):
        self._run_test("sleep-1", RUN_CODE_NOT_ALL_UP, 0)

    def test_1_installed_up(self):
        self._run_test("sleep-1", RUN_CODE_ALL_UP, 1)

    def test_1_installed_alien(self):
        self._run_test("sleep-1", RUN_CODE_SOME_ALIENS, 3)

    def test_3_installed_down(self):
        self._run_test("sleep-3", RUN_CODE_NOT_ALL_UP, 0)

    def test_3_installed_up(self):
        self._run_test("sleep-3", RUN_CODE_ALL_UP, 3)

    def test_3_installed_1_up(self):
        self._run_test("sleep-3", RUN_CODE_NOT_ALL_UP, 1)

    def test_3_installed_up_unhealthy(self):
        self._run_test("sleep-3", RUN_CODE_NOT_ALL_UP, 3, 1)

    def setUp(self):
        self._docker_stop()

    def tearDown(self):
        self._docker_stop()

    def _docker_start(self, docker_containers_count=1, docker_healthcheck_return=0):
        for index in range(1, docker_containers_count + 1):
            docker.from_env().containers.run("alpine", "tail -f /dev/null", name="sleep-{}".format(index), detach=True, healthcheck={
                "test": "exit {}".format(docker_healthcheck_return),
                "interval": 1000000 * 250,
                "timeout": 1000000 * 1000,
                "retries": 1,
                "start_period": 1000000 * 250,

            })
        time.sleep(0.75)

    def _docker_stop(self):
        time.sleep(0.5)
        for docker_container in docker.from_env().containers.list():
            docker_container.kill()
        docker.from_env().containers.prune()

    def _run_test(self, services_file, run_code, docker_containers_count=0, docker_healthcheck_return=0):
        print("")
        sys.stdout.flush()
        with patch("supervisor.main.docker_container_status_publish", MagicMock(return_value={})):
            if docker_containers_count > 0:
                self._docker_start(docker_containers_count, docker_healthcheck_return)
            self.assertEqual(run_code, docker_container_supervise(join(DIR_ROOT, "src/test/resources/services-{}.json".format(
                services_file
            ))), "Execution failed with unexpected return")


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
