import os
import sys
import tempfile
import unittest
from os.path import abspath, dirname, join, realpath
from unittest import mock

import pytest

sys.path.append("../../../main/python")

import library.data
from library.env import init_env

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


class WrangleTest(unittest.TestCase):
    def test_init_env(self):
        self.assertEqual("/service/mlflow/artifacts", init_env()["MLFLOW_ARTIFACT_DIR"])


class QueryInfluxdb3Test(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()
        self.env = {"INFLUXDB3_IP_PROD": "host", "INFLUXDB3_API_PORT": "1", "INFLUXDB3_TOKEN_ADMIN": "token", "INFLUXDB3_DATABASE_HOME": "home"}

    def response(self, text, ok=True):
        return mock.Mock(ok=ok, status_code=200 if ok else 400, text=text)

    def query(self, post, **kwargs):
        with mock.patch.object(library.data, "post", post):
            return library.data.query_influxdb3(self.env, "SELECT 1", "demo_model", "training", "demo", model_dir=self.data_dir, **kwargs)

    def test_writes_csv_when_absent_then_reads_it(self):
        post = mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n"))
        first = self.query(post)
        second = self.query(post)
        self.assertEqual(first, second)
        self.assertEqual(1, post.call_count)
        self.assertEqual("1.5", first[0][1])

    def test_force_overrides_the_present_file(self):
        self.query(mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n")))
        rows = self.query(mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,2.5\n")), force=True)
        self.assertEqual("2.5", rows[0][1])
        path = library.data.data_path("demo_model", "training", "demo", model_dir=self.data_dir)
        with open(path) as data_file:
            self.assertIn("2.5", data_file.read())
        self.assertEqual(1, len(os.listdir(os.path.join(self.data_dir, "demo_model", "data", "training"))))

    def test_shared_timestamp_dir(self):
        post = mock.Mock(return_value=self.response("time,value\n"))
        self.query(post, timestamp="2026-01-01_00-00-00")
        self.assertTrue(os.path.isfile(os.path.join(self.data_dir, "demo_model", "data", "training", "2026-01-01_00-00-00", "demo.csv")))

    def test_unknown_label_fails(self):
        with self.assertRaises(ValueError):
            library.data.data_path("demo_model", "testing", "demo", model_dir=self.data_dir)

    def test_failed_query_writes_nothing(self):
        with self.assertRaises(RuntimeError):
            self.query(mock.Mock(return_value=self.response("bad", ok=False)))
        self.assertFalse(os.path.isdir(os.path.join(self.data_dir, "demo_model", "data", "training")))


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


class ConsumerProjectDirTest(unittest.TestCase):
    def test_slot_resolves_into_the_tree_or_the_output_directory(self):
        from library.project import consumer_project_dir

        self.assertTrue(consumer_project_dir("max/rackmains", "default").endswith("max/rackmains/src/build/resources/model/default"))
        with mock.patch.dict(os.environ, {"MODEL_OUTPUT_DIR": "/out"}):
            self.assertEqual("/out/max/rackmains/default", consumer_project_dir("max/rackmains", "default"))
        with self.assertRaises(ValueError):
            consumer_project_dir("max/rackmains", "other")


class DevelopmentVersionTest(unittest.TestCase):
    def test_the_workspace_version_file_is_read(self):
        from library.project import development_version

        model_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(model_dir, "demo/calc/run"))
        with open(os.path.join(model_dir, "demo/calc/run/.version"), "w") as version_file:
            version_file.write("1003-SNAPSHOT\n")
        self.assertEqual("1003-SNAPSHOT", development_version("demo/calc/run", model_dir))
