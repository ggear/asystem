from __future__ import print_function

import json
import logging
import os
import time
from decimal import Decimal

import treq

import anode
from anode.plugin.plugin import Plugin

HTTP_TIMEOUT = 10


class Netatmo(Plugin):

    def _poll(self):
        if not self.disabled:
            if self.token_access is None:
                self.http_post("https://api.netatmo.com/oauth2/token", {'grant_type': 'password',
                                                                        'username': self.netatmo_username,
                                                                        'password': self.netatmo_password,
                                                                        'client_id': self.netatmo_client_id,
                                                                        'client_secret': self.netatmo_client_secret,
                                                                        'scope': 'read_station read_homecoach'}, self.cache_tokens)
            elif self.token_expiry <= self.get_time():
                self.http_post("https://api.netatmo.com/oauth2/token", {'grant_type': 'refresh_token',
                                                                        'refresh_token': self.token_refresh,
                                                                        'client_id': os.environ['NETATMO_CLIENT_ID'],
                                                                        'client_secret': os.environ['NETATMO_CLIENT_SECRET']},
                               self.cache_tokens)
            else:
                self.http_get("https://api.netatmo.com/api/getstationsdata?access_token=" + self.token_access, self.push_getdata)
                self.http_get("https://api.netatmo.com/api/gethomecoachsdata?access_token=" + self.token_access, self.push_getdata)

    # noinspection PyShadowingNames
    def http_get(self, url, callback):
        connection_pool = self.config["pool"] if "pool" in self.config else None
        treq.get(url, timeout=HTTP_TIMEOUT, pool=connection_pool).addCallbacks(
            lambda response, url=url, callback=callback: self.http_response(response, url, callback),
            errback=lambda error, url=url: anode.Log(logging.ERROR).log("Plugin", "error",
                                                                        lambda: "[{}] error processing HTTP GET [{}] with [{}]".format(
                                                                            self.name, url, error.getErrorMessage())))

    # noinspection PyShadowingNames
    def http_post(self, url, data, callback):
        connection_pool = self.config["pool"] if "pool" in self.config else None
        treq.post(url, data, timeout=HTTP_TIMEOUT, pool=connection_pool).addCallbacks(
            lambda response, url=url, callback=callback: self.http_response(response, url, callback),
            errback=lambda error, url=url: anode.Log(logging.ERROR).log("Plugin", "error",
                                                                        lambda: "[{}] error processing HTTP GET [{}] with [{}]".format(
                                                                            self.name, url, error.getErrorMessage())))

    def http_response(self, response, url, callback):
        if response.code == 200:
            treq.text_content(response).addCallbacks(callback)
        else:
            anode.Log(logging.ERROR).log("Plugin", "error",
                                         lambda: "[{}] error processing HTTP response [{}] with [{}]".format(self.name, url, response.code))

    def cache_tokens(self, content):
        log_timer = anode.Log(logging.DEBUG).start()
        dict_content = json.loads(content)
        self.token_access = dict_content["access_token"]
        self.token_refresh = dict_content["refresh_token"]
        self.token_expiry = self.get_time() + dict_content["expires_in"] - 10 * self.config["poll_seconds"]
        anode.Log(logging.INFO).log("Plugin", "state", lambda: "[netatmo] access tokens cached, refresh [{}]"
                                    .format(time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(self.token_expiry))))
        log_timer.log("Plugin", "timer", lambda: "[{}]".format(self.name), context=self.cache_tokens)
        self.poll()

    # noinspection PyBroadException
    def push_getdata(self, content):
        log_timer = anode.Log(logging.DEBUG).start()
        try:
            dict_content = json.loads(content, parse_float=Decimal)
            bin_timestamp = self.get_time()
            for device in dict_content["body"]["devices"]:
                module_name = "__indoor__" + device["module_name" if device["type"] == "NAMain" else (
                    "station_name" if "station_name" in device else "name")].lower().encode("UTF-8")
                if module_name != "__indoor__ignore" and "dashboard_data" in device:
                    data_timestamp = device["dashboard_data"]["time_utc"]
                    self.datum_push(
                        "temperature" + module_name,
                        "current", "point",
                        self.datum_value(device, ["dashboard_data", "Temperature"], factor=10),
                        "_PC2_PB0C",
                        10,
                        data_timestamp,
                        bin_timestamp,
                        self.config["poll_seconds"],
                        "second",
                        data_version="1001",
                        data_derived_max=True,
                        data_derived_min=True
                    )
                    self.datum_push(
                        "humidity" + module_name,
                        "current", "point",
                        self.datum_value(device, ["dashboard_data", "Humidity"]),
                        "_P25",
                        1,
                        data_timestamp,
                        bin_timestamp,
                        self.config["poll_seconds"],
                        "second",
                        data_version="1001",
                        data_bound_upper=100,
                        data_bound_lower=0,
                        data_derived_max=True,
                        data_derived_min=True
                    )
                    self.datum_push(
                        "pressure" + module_name,
                        "current", "point",
                        self.datum_value(device, ["dashboard_data", "Pressure"]),
                        "mbar",
                        1,
                        data_timestamp,
                        bin_timestamp,
                        self.config["poll_seconds"],
                        "second",
                        data_version="1001",
                        data_bound_lower=0,
                        data_derived_max=True,
                        data_derived_min=True
                    )
                    self.datum_push(
                        "pressure_Dabsolute" + module_name,
                        "current", "point",
                        self.datum_value(device, ["dashboard_data", "AbsolutePressure"]),
                        "mbar",
                        1,
                        data_timestamp,
                        bin_timestamp,
                        self.config["poll_seconds"],
                        "second",
                        data_version="1001",
                        data_bound_lower=0,
                        data_derived_max=True,
                        data_derived_min=True
                    )
                    self.datum_push(
                        "carbon_Ddioxide" + module_name,
                        "current", "point",
                        self.datum_value(device, ["dashboard_data", "CO2"]),
                        "ppm",
                        1,
                        data_timestamp,
                        bin_timestamp,
                        self.config["poll_seconds"],
                        "second",
                        data_version="1001",
                        data_bound_lower=0,
                        data_derived_max=True,
                        data_derived_min=True
                    )
                    self.datum_push(
                        "noise" + module_name,
                        "current", "point",
                        self.datum_value(device, ["dashboard_data", "Noise"]),
                        "dB",
                        1,
                        data_timestamp,
                        bin_timestamp,
                        self.config["poll_seconds"],
                        "second",
                        data_version="1001",
                        data_bound_lower=0,
                        data_derived_max=True,
                        data_derived_min=True
                    )
                    if device["type"] == "NHC":
                        self.datum_push(
                            "health_Dindex" + module_name,
                            "current", "point",
                            self.datum_value(device, ["dashboard_data", "health_idx"]),
                            "scalar",
                            1,
                            data_timestamp,
                            bin_timestamp,
                            self.config["poll_seconds"],
                            "second",
                            data_version="1001",
                            data_bound_lower=0,
                            data_derived_max=True,
                            data_derived_min=True
                        )
                if "modules" in device:
                    for device_sub in device["modules"]:
                        module_name = (("__indoor__" if device_sub["type"] == "NAModule4" else "__outdoor__") +
                                       device_sub["module_name"].lower()).encode("UTF-8")
                        if module_name != "__outdoor__ignore" and "dashboard_data" in device_sub:
                            data_timestamp = device_sub["dashboard_data"]["time_utc"]
                            self.datum_push(
                                "temperature" + module_name,
                                "current", "point",
                                self.datum_value(device_sub, ["dashboard_data", "Temperature"], factor=10),
                                "_PC2_PB0C",
                                10,
                                data_timestamp,
                                bin_timestamp,
                                self.config["poll_seconds"],
                                "second",
                                data_version="0" if module_name == "__outdoor__parents" else "1001",
                                data_derived_max=True,
                                data_derived_min=True
                            )
                            self.datum_push(
                                "humidity" + module_name,
                                "current", "point",
                                self.datum_value(device_sub, ["dashboard_data", "Humidity"]),
                                "_P25",
                                1,
                                data_timestamp,
                                bin_timestamp,
                                self.config["poll_seconds"],
                                "second",
                                data_version="0" if module_name == "__outdoor__parents" else "1001",
                                data_bound_upper=100,
                                data_bound_lower=0,
                                data_derived_max=True,
                                data_derived_min=True
                            )
                            if device_sub["type"] == "NAModule4":
                                self.datum_push(
                                    "carbon_Ddioxide" + module_name,
                                    "current", "point",
                                    self.datum_value(device_sub, ["dashboard_data", "CO2"]),
                                    "ppm",
                                    1,
                                    data_timestamp,
                                    bin_timestamp,
                                    self.config["poll_seconds"],
                                    "second",
                                    data_version="0" if module_name == "__outdoor__parents" else "1001",
                                    data_bound_lower=0,
                                    data_derived_max=True,
                                    data_derived_min=True
                                )
            self.publish()
        except Exception as exception:
            anode.Log(logging.ERROR).log("Plugin", "error", lambda: "[{}] error [{}] processing response:\n{}"
                                         .format(self.name, exception, content), exception)
        log_timer.log("Plugin", "timer", lambda: "[{}]".format(self.name), context=self.push_getdata)

    def __init__(self, parent, name, config, reactor):
        super(Netatmo, self).__init__(parent, name, config, reactor)
        self.disabled = False
        self.token_access = None
        self.token_refresh = None
        self.token_expiry = None
        try:
            self.netatmo_username = os.environ['NETATMO_USERNAME']
            self.netatmo_password = os.environ['NETATMO_PASSWORD']
            self.netatmo_client_id = os.environ['NETATMO_CLIENT_ID']
            self.netatmo_client_secret = os.environ['NETATMO_CLIENT_SECRET']
        except KeyError as key_error:
            self.disabled = True
            anode.Log(logging.ERROR).log("Plugin", "error",
                                         lambda: "[{}] error getting Netatmo connection key [{}] from environment, disabling plugin"
                                         .format(self.name, key_error))
