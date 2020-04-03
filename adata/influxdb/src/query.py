# -*- coding: utf-8 -*-

import re

from dateutil import tz
from influxdb import DataFrameClient
from tabulate import tabulate

HOST = "macmini-delila"
PORT = 8086
USER = ""
PASSWORD = ""
DATABASE = "home_assistant"


def print_series_summary(client, measurement, entity_id, time_window):
    query = """
        SHOW SERIES
        WHERE "entity_id" = '{}'
    """.format(entity_id)
    print("\nSERIES [{}]:".format(re.sub("\s+", " ", query.strip()).strip()))
    series_all = client.query(query)
    for series in series_all.get_points():
        print("{}".format(series["key"].encode('utf-8')))

    query = """
        SELECT count(*) AS count FROM {}
        WHERE "entity_id" = '{}'
    """.format(measurement, entity_id)
    print("\nCOUNT [{}]:".format(re.sub("\s+", " ", query.strip()).strip()))
    series_filter_power_count = client.query(query)[measurement]
    print("{}".format(series_filter_power_count["count_value"].iloc[0]))

    query = """
        SELECT * FROM {}
        WHERE "entity_id" = '{}' AND time > now() - {}
        ORDER BY time DESC
    """.format(measurement, entity_id, time_window)
    print("\nLAST {} [{}]:".format(time_window, re.sub("\s+", " ", query.strip()).strip()))
    series_filter_power_latest = client.query(query)[measurement]
    series_filter_power_latest.set_index(series_filter_power_latest["value"].index.tz_convert(tz.tzlocal()), inplace=True)
    series_filter_power_latest["measurement"] = measurement
    print(tabulate(series_filter_power_latest, headers='keys', tablefmt='psql'))


if __name__ == "__main__":
    client = DataFrameClient(HOST, PORT, USER, PASSWORD, DATABASE)
    print_series_summary(client, "W", "filter_power", "30s")
    print_series_summary(client, "W", "servers_power", "30s")
    print_series_summary(client, "W", "office_lights_power", "12h")
