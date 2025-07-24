import os
import os.path
import subprocess

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


def query_influxdb(env, query):
    response = post(
        url="http://{}:{}/api/v2/query?org={}".format(env["INFLUXDB_IP_PROD"], env["INFLUXDB_HTTP_PORT"], env["INFLUXDB_ORG"]),
        headers={
            'Accept': 'application/csv',
            'Content-type': 'application/vnd.flux',
            'Authorization': 'Token {}'.format(env["INFLUXDB_TOKEN"])
        }, data=query)
    rows = []
    for row in response.text.strip().split("\n")[1:]:
        cols = row.strip().split(",")
        if len(cols) > 4:
            rows.append([parse(cols[3])] + cols[4:])
    return rows


def show_plot(label, data_pl, data_x, data_y, type='-'):
    plt.rcParams["figure.figsize"] = (16, 8)
    plt.plot(data_pl.select(data_x), data_pl.select(data_y), type, label=label)
    plt.xlabel(data_x)
    plt.ylabel(data_y)
    plt.legend(loc='upper right')
