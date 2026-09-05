import os
import os.path
import subprocess
from csv import reader

import matplotlib.pyplot as plt
from dateutil.parser import parse
from requests import post


def init_env(prod_env=True):
    def _load_env(_env, _env_path):
        with open(os.path.join(os.path.dirname(__file__), _env_path), 'r') as env_file:
            for env_line in env_file:
                env_line = env_line.replace("export ", "").rstrip()
                if not env_line.startswith("#") and "=" in env_line:
                    env_key, env_value = env_line.split("=", 1)
                    env[env_key] = env_value

    env = {}
    os.chdir(os.path.dirname(__file__))
    _load_env(env, "../../../../.env")
    if prod_env:
        _load_env(env, "../../../../.env_prod")
        mount_script_path = os.path.join(os.path.dirname(__file__), "../../resources/mount.sh")
        if subprocess.run(mount_script_path, shell=True).returncode != 0:
            raise Exception("Execution of [{}] failed".format(mount_script_path))
    return env


def query_influxdb3(env, query, database=None):
    response = post(
        url="http://{}:{}/api/v3/query_sql".format(env["INFLUXDB3_IP_PROD"], env["INFLUXDB3_API_PORT"]),
        headers={
            'Accept': 'application/csv',
            'Content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(env["INFLUXDB3_TOKEN_ADMIN"])
        }, json={
            "db": database if database is not None else env["INFLUXDB3_DATABASE_HOME"],
            "q": query,
            "format": "csv"
        })
    response.raise_for_status()
    lines = response.text.strip().split("\n")
    if len(lines) < 2:
        return []
    header = next(reader([lines[0]]))
    rows = []
    for cols in reader(lines[1:]):
        rows.append([parse(col) if key == "time" and col else col for key, col in zip(header, cols)])
    return rows


def show_plot(label, data_pl, data_x, data_y, type='-'):
    plt.rcParams["figure.figsize"] = (16, 8)
    plt.plot(data_pl.select(data_x), data_pl.select(data_y), type, label=label)
    plt.xlabel(data_x)
    plt.ylabel(data_y)
    plt.legend(loc='upper right')
