from __future__ import print_function

import datetime
import json
import logging

import pytz
import requests
import treq
import urllib3
from astral import Astral
from treq.client import HTTPClient
from twisted.internet import ssl
from twisted.web.client import Agent
from twisted.web.iweb import IPolicyForHTTPS
from zope.interface import implementer

import anode
from anode.plugin.plugin import DATUM_QUEUE_LAST
from anode.plugin.plugin import DATUM_QUEUE_MIN
from anode.plugin.plugin import Plugin

HTTP_TIMEOUT = 10

BRIDGE_IP = "192.168.2.12"
BRIDGE_TOKEN = "o6PRIGF-uz17Gbp8JSWG1haIAAmnPVA-Zv7b3a9S"

LIGHT_STATE = {}
LIGHT_STATES = {
    "default": {
        "power": {"LTW001": 7, "LCT010": 7, "LCT012": 5},
        "state": {"ct": 366, "bri": 254}
    },
    "daylight": {
        "power": {"LTW001": 8, "LCT010": 8, "LCT012": 6},
        "state": {"ct": 233, "bri": 254}
    },
    "evening": {
        "power": {"LTW001": 7, "LCT010": 7, "LCT012": 5},
        "state": {"ct": 366, "bri": 254}
    },
    "witching": {
        "power": {"LTW001": 2, "LCT010": 2, "LCT012": 2},
        "state": {"ct": 447, "bri": 50}
    }
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@implementer(IPolicyForHTTPS)
class DoNotVerifySSLContextFactory(object):

    def creatorForNetloc(self, hostname, port):
        return ssl.CertificateOptions(verify=False)


class Hue(Plugin):

    def _poll(self):
        self.light_state = self.get_light_state()
        self.http_get("https://" + BRIDGE_IP + "/api/" + BRIDGE_TOKEN + "/lights", self.lights_adjust)

    def http_get(self, url, callback):
        connection_pool = self.config["pool"] if "pool" in self.config else None
        HTTPClient(Agent(self.reactor, contextFactory=DoNotVerifySSLContextFactory())) \
            .get(url, timeout=HTTP_TIMEOUT, pool=connection_pool).addCallbacks(
            lambda response, url=url, callback=callback: self.http_response(response, url, callback),
            errback=lambda error, url=url: anode.Log(logging.ERROR).log("Plugin", "error",
                                                                        lambda: "[{}] error processing HTTP GET [{}] with [{}]".format(
                                                                            self.name, url, error.getErrorMessage())))

    def http_put(self, url, data, callback=None):
        connection_pool = self.config["pool"] if "pool" in self.config else None
        HTTPClient(Agent(self.reactor, contextFactory=DoNotVerifySSLContextFactory())) \
            .put(url, data, timeout=HTTP_TIMEOUT, pool=connection_pool).addCallbacks(
            lambda response, url=url, callback=callback: self.http_response(response, url, callback),
            errback=lambda error, url=url: anode.Log(logging.ERROR).log("Plugin", "error",
                                                                        lambda: "[{}] error processing HTTP GET [{}] with [{}]".format(
                                                                            self.name, url, error.getErrorMessage())))

    def http_response(self, response, url, callback):
        if response.code == 200:
            if callback is not None:
                treq.text_content(response).addCallbacks(callback)
        else:
            anode.Log(logging.ERROR).log("Plugin", "error",
                                         lambda: "[{}] error processing HTTP response [{}] with [{}]".format(self.name, url, response.code))

    def lights_adjust(self, content):
        log_timer = anode.Log(logging.DEBUG).start()
        try:
            bin_timestamp = self.get_time()
            lights = json.loads(content)
            for group in self.groups:
                power = 0
                group_on = True
                group_adjust = False
                for light in self.groups[group]["lights"]:
                    if lights[light]["state"]["on"] and lights[light]["state"]["reachable"]:
                        if light not in LIGHT_STATE or \
                                {k: lights[light]["state"][k] for k in ("ct", "bri")} == LIGHT_STATES["default"]["state"]:
                            LIGHT_STATE[light] = "default"
                        if {k: lights[light]["state"][k] for k in ("ct", "bri")} == LIGHT_STATES[LIGHT_STATE[light]]["state"]:
                            if LIGHT_STATES[self.light_state]["state"]["ct"] != LIGHT_STATES[LIGHT_STATE[light]]["state"]["ct"] or \
                                    LIGHT_STATES[self.light_state]["state"]["bri"] != LIGHT_STATES[LIGHT_STATE[light]]["state"]["bri"]:
                                LIGHT_STATE[light] = self.light_state
                                group_adjust = True
                        power = LIGHT_STATES[LIGHT_STATE[light]]["power"][lights[light]["modelid"]]
                    else:
                        group_on = False
                        LIGHT_STATE.pop(light, None)
                if group_adjust:
                    self.http_put("https://" + BRIDGE_IP + "/api/" + BRIDGE_TOKEN + "/groups/" + group + "/action",
                                  json.dumps(LIGHT_STATES[self.light_state]["state"]), self.light_adjusted)

                power_second_bin = power * len(self.groups[group]["lights"]) if group_on else 0
                self.datum_push(
                    "power__consumption__" + self.groups[group]["name"].lower() + "_Dlights",
                    "current", "point",
                    power_second_bin,
                    "W",
                    1,
                    bin_timestamp,
                    bin_timestamp,
                    self.config["poll_seconds"],
                    "second",
                    data_bound_lower=0,
                    data_derived_max=True,
                    data_derived_min=True
                )
                energy_consumption_day = self.datum_get(
                    DATUM_QUEUE_LAST, "energy__consumption__" + self.groups[group]["name"].lower() + "_Dlights",
                    "integral", "mWh", "1", "day")
                if energy_consumption_day is not None and self.get_time_period(bin_timestamp, Plugin.get_seconds(1, "day")) != \
                        self.get_time_period(energy_consumption_day["bin_timestamp"], Plugin.get_seconds(1, "day")):
                    energy_consumption_day = None
                energy_consumption_day = int((0 if energy_consumption_day is None else energy_consumption_day["data_value"]) +
                                             (float(power_second_bin) / (60 * 60) * 10000))
                self.datum_push(
                    "energy__consumption__" + self.groups[group]["name"].lower() + "_Dlights",
                    "current", "integral",
                    energy_consumption_day,
                    "mWh",
                    10,
                    bin_timestamp,
                    bin_timestamp,
                    1,
                    "day",
                    data_bound_lower=0
                )
                energy_consumption_alltime_min = self.datum_get(
                    DATUM_QUEUE_MIN, "energy__consumption__" + self.groups[group]["name"].lower() + "_Dlights",
                    "integral", "Wh", 1, "all_Dtime", 1, "day")
                energy_consumption_alltime_min = int((0 if energy_consumption_alltime_min is None
                                                      else energy_consumption_alltime_min["data_value"]))
                self.datum_push(
                    "energy__consumption__" + self.groups[group]["name"].lower() + "_Dlights",
                    "current", "integral",
                    int(energy_consumption_alltime_min + energy_consumption_day / 10000),
                    "Wh",
                    1,
                    bin_timestamp,
                    bin_timestamp,
                    1,
                    "all_Dtime",
                    data_bound_lower=0,
                    data_derived_min=True
                )
            self.publish()
        except Exception as exception:
            anode.Log(logging.ERROR).log("Plugin", "error", lambda: "[{}] error [{}] processing response:\n"
                                         .format(self.name, exception), exception)
        log_timer.log("Plugin", "timer", lambda: "[{}]".format(self.name), context=self.lights_adjust)

    def light_adjusted(self, content):
        anode.Log(logging.DEBUG).log("Plugin", "state", lambda: "[{}] updated light group state {}"
                                     .format(self.name, json.dumps([d["success"] for d in json.loads(content)])))

    def get_light_state(self):
        astral = Astral()
        astral.solar_depression = "civil"
        astral_city = astral["Perth"]
        now = datetime.datetime.now(pytz.timezone('Australia/Perth'))
        astral_city_sun = astral_city.sun(date=now, local=True)
        if (astral_city_sun['sunrise'] - datetime.timedelta(hours=1)) < now < astral_city_sun['sunset']:
            return "daylight"
        elif 1 <= now.hour <= 5:
            return "witching"
        else:
            return "evening"

    def __init__(self, parent, name, config, reactor):
        super(Hue, self).__init__(parent, name, config, reactor)
        self.light_state = None
        self.groups = requests.get("https://" + BRIDGE_IP + "/api/" + BRIDGE_TOKEN + "/groups", verify=False).json()
