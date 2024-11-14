import os

import matplotlib.pyplot as plt
from dateutil.parser import parse
from requests import post


def load_env():
    env_load = {}
    with open(os.path.join(os.getcwd(), "../../../../.env"), 'r') as env_file:
        for env_load_line in env_file:
            env_load_line = env_load_line.replace("export ", "").rstrip()
            if "=" not in env_load_line:
                continue
            if env_load_line.startswith("#"):
                continue
            env_load_key, env_load_value = env_load_line.split("=", 1)
            env_load[env_load_key] = env_load_value
    return env_load


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
