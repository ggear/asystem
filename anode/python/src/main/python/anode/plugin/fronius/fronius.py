from __future__ import division
from __future__ import print_function

import calendar
import datetime
import json
import logging
from decimal import Decimal

import dateutil.parser
import treq

import anode
from anode.plugin.plugin import DATUM_QUEUE_LAST
from anode.plugin.plugin import DATUM_QUEUE_MIN
from anode.plugin.plugin import Plugin

HOST = "192.168.2.10"

HTTP_TIMEOUT = 5
POLL_METER_ITERATIONS = 5

SUPPLY_CHARGE = 1.015493
TARIFF_FEEDIN = 0.000007135
TARIFF_PEAK = 0.0000538714
TARIFF_SHOULDER = 0.0000282139
TARIFF_OFFPEAK = 0.0000148405
TARIFF_FLAT = 0.0000283272

HOUR_SHOULDER_START = 7
HOUR_PEAK_START = 15
HOUR_OFFPEAK_START = 21


# noinspection PyBroadException
class Fronius(Plugin):

    def _poll(self):
        self.http_get("http://" + HOST + "/solar_api/v1/GetPowerFlowRealtimeData.fcgi", self.push_flow)
        if self.is_clock or self.poll_meter_iteration == POLL_METER_ITERATIONS:
            self.poll_meter_iteration = 0
            self.http_get("http://" + HOST + "/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System", self.push_meter)
        else:
            self.poll_meter_iteration += 1

    # noinspection PyShadowingNames
    def http_get(self, url, callback):
        connection_pool = self.config["pool"] if "pool" in self.config else None
        treq.get(url, timeout=HTTP_TIMEOUT, pool=connection_pool).addCallbacks(
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

    def push_flow(self, content):
        log_timer = anode.Log(logging.DEBUG).start()
        try:
            dict_content = json.loads(content, parse_float=Decimal)
            bin_timestamp = self.get_time()
            data_timestamp = int(calendar.timegm(dateutil.parser.parse(dict_content["Head"]["Timestamp"]).timetuple()))
            self.datum_push(
                "power__export__grid",
                "current", "point",
                self.datum_value(dict_content, ["Body", "Data", "Site", "P_Grid"], 0, -1) if self.datum_value(
                    dict_content, ["Body", "Data", "Site", "P_Grid"], 0) <= 0 else 0,
                "W",
                1,
                data_timestamp,
                bin_timestamp,
                self.config["poll_seconds"],
                "second",
                data_bound_lower=0,
                data_derived_max=True,
                data_derived_min=True
            )
            self.datum_push(
                "power__production__inverter",
                "current", "point",
                self.datum_value(dict_content, ["Body", "Data", "Inverters", "1", "P"], 0, 1),
                "W",
                1,
                data_timestamp,
                bin_timestamp,
                self.config["poll_seconds"],
                "second",
                data_bound_lower=0,
                data_derived_max=True,
                data_derived_min=True
            )
            self.datum_push(
                "power__consumption__grid",
                "current", "point",
                self.datum_value(dict_content, ["Body", "Data", "Site", "P_Grid"], 0, 1) if self.datum_value(
                    dict_content, ["Body", "Data", "Site", "P_Grid"], 0) >= 0 else 0,
                "W",
                1,
                data_timestamp,
                bin_timestamp,
                self.config["poll_seconds"],
                "second",
                data_bound_lower=0,
                data_derived_max=True,
                data_derived_min=True
            )
            self.datum_push(
                "power__consumption__inverter",
                "current", "point",
                self.datum_value(dict_content, ["Body", "Data", "Site", "P_Load"], 0, -1) -
                (self.datum_value(dict_content, ["Body", "Data", "Site", "P_Grid"], 0, 1) if self.datum_value(
                    dict_content, ["Body", "Data", "Site", "P_Grid"], 0) >= 0 else 0),
                "W",
                1,
                data_timestamp,
                bin_timestamp,
                self.config["poll_seconds"],
                "second",
                data_bound_lower=0,
                data_derived_max=True,
                data_derived_min=True
            )
            self.datum_push(
                "power__utilisation__inverter",
                "current", "point",
                self.datum_value(dict_content, ["Body", "Data", "Site", "rel_SelfConsumption"], 0),
                "_P25",
                1,
                data_timestamp,
                bin_timestamp,
                self.config["poll_seconds"],
                "second",
                data_bound_upper=100,
                data_bound_lower=0,
                data_derived_max=True,
                data_derived_min=True
            )
            self.datum_push(
                "power__utilisation__grid",
                "current", "point",
                self.datum_value(100 - self.datum_value(dict_content, ["Body", "Data", "Site", "rel_Autonomy"], 0)),
                "_P25",
                1,
                data_timestamp,
                bin_timestamp,
                self.config["poll_seconds"],
                "second",
                data_bound_upper=100,
                data_bound_lower=0,
                data_derived_max=True,
                data_derived_min=True
            )
            self.datum_push(
                "power__utilisation__array",
                "current", "point",
                0 if self.datum_value(dict_content, ["Body", "Data", "Site", "P_PV"], 0) == 0 else (
                    self.datum_value(self.datum_value(dict_content, ["Body", "Data", "Inverters", "1", "P"], 0) / self.datum_value(
                        dict_content, ["Body", "Data", "Site", "P_PV"], 0) * 100)),
                "_P25",
                1,
                data_timestamp,
                bin_timestamp,
                self.config["poll_seconds"],
                "second",
                data_bound_upper=100,
                data_bound_lower=0,
                data_derived_max=True,
                data_derived_min=True
            )
            self.datum_push(
                "energy__production__inverter",
                "current", "integral",
                self.datum_value(dict_content, ["Body", "Data", "Site", "E_Year"], factor=10),
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "year",
                data_bound_lower=0,
                data_derived_min=True
            )
            energy_production_inverter_alltime = self.datum_value(dict_content, ["Body", "Data", "Site", "E_Total"], factor=10)
            self.datum_push(
                "energy__production__inverter",
                "current", "integral",
                energy_production_inverter_alltime,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "all_Dtime",
                data_bound_lower=0,
                data_derived_min=True
            )
            energy_production_inverter_alltime_min = self.datum_get(
                DATUM_QUEUE_MIN, "energy__production__inverter", "integral", "Wh", 1, "all_Dtime", 1, "day")
            energy_production_inverter_day = (energy_production_inverter_alltime - energy_production_inverter_alltime_min["data_value"]) \
                if energy_production_inverter_alltime_min is not None else 0
            self.datum_push(
                "energy__production__inverter",
                "current", "integral",
                energy_production_inverter_day,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            self.publish()
        except Exception as exception:
            anode.Log(logging.ERROR).log("Plugin", "error", lambda: "[{}] error [{}] processing response:\n"
                                         .format(self.name, exception), exception)
        log_timer.log("Plugin", "timer", lambda: "[{}]".format(self.name), context=self.push_flow)

    def push_meter(self, content):
        log_timer = anode.Log(logging.DEBUG).start()
        try:
            dict_content = json.loads(content, parse_float=Decimal)
            bin_timestamp = self.get_time()
            data_timestamp = int(calendar.timegm(dateutil.parser.parse(dict_content["Head"]["Timestamp"]).timetuple()))
            energy_export_grid_alltime = self.datum_value(dict_content, ["Body", "Data", "0", "EnergyReal_WAC_Minus_Absolute"], factor=10)
            self.datum_push(
                "energy__export__grid",
                "current", "integral",
                energy_export_grid_alltime,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "all_Dtime",
                data_bound_lower=0,
                data_derived_min=True
            )
            energy_export_grid_alltime_min = self.datum_get(
                DATUM_QUEUE_MIN, "energy__export__grid", "integral", "Wh", 1, "all_Dtime", 1, "day")
            energy_export_grid_day = (energy_export_grid_alltime - energy_export_grid_alltime_min["data_value"]) \
                if energy_export_grid_alltime_min is not None else 0
            self.datum_push(
                "energy__export__grid",
                "current", "integral",
                energy_export_grid_day,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            energy_production_inverter_alltime_last = self.datum_get(
                DATUM_QUEUE_LAST, "energy__production__inverter", "integral", "Wh", "1", "all_Dtime")
            energy_production_inverter_alltime_min = self.datum_get(
                DATUM_QUEUE_MIN, "energy__production__inverter", "integral", "Wh", 1, "all_Dtime", 1, "day")
            energy_production_inverter_day = (energy_production_inverter_alltime_last["data_value"] -
                                              energy_production_inverter_alltime_min["data_value"]) \
                if (energy_production_inverter_alltime_last is not None and energy_production_inverter_alltime_min is not None) else 0
            energy_consumption_inverter_day = energy_production_inverter_day - energy_export_grid_day
            self.datum_push(
                "energy__consumption__inverter",
                "current", "integral",
                energy_consumption_inverter_day,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            energy_consumption_grid_alltime = self.datum_value(
                dict_content, ["Body", "Data", "0", "EnergyReal_WAC_Plus_Absolute"], factor=10)
            self.datum_push(
                "energy__consumption__grid",
                "current", "integral",
                energy_consumption_grid_alltime,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "all_Dtime",
                data_bound_lower=0,
                data_derived_min=True
            )
            energy_consumption_grid_min = self.datum_get(
                DATUM_QUEUE_MIN, "energy__consumption__grid", "integral", "Wh", 1, "all_Dtime", 1, "day")
            energy_consumption_grid_day = (energy_consumption_grid_alltime - energy_consumption_grid_min["data_value"]) \
                if energy_consumption_grid_min is not None else 0
            self.datum_push(
                "energy__consumption__grid",
                "current", "integral",
                energy_consumption_grid_day,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            energy_consumption_shoulder_inverter = self.datum_get(
                DATUM_QUEUE_LAST, "energy__consumption_Dshoulder__inverter", "integral", "Wh", 1, "all_Dtime")
            energy_consumption_shoulder_grid = self.datum_get(
                DATUM_QUEUE_LAST, "energy__consumption_Dshoulder__grid", "integral", "Wh", 1, "all_Dtime")
            if energy_consumption_shoulder_grid is not None and \
                    self.get_time_period(energy_consumption_shoulder_grid["data_timestamp"], Plugin.get_seconds(1, "day")) != \
                    self.get_time_period(bin_timestamp, Plugin.get_seconds(1, "day")):
                energy_consumption_shoulder_grid = None
            if energy_consumption_shoulder_grid is None and bin_timestamp >= \
                    (self.get_time_period(bin_timestamp, Plugin.get_seconds(1, "day")) + HOUR_SHOULDER_START * 60 * 60):
                self.datum_push(
                    "energy__consumption_Dshoulder__grid",
                    "current", "integral",
                    energy_consumption_grid_alltime,
                    "Wh",
                    10,
                    bin_timestamp,
                    bin_timestamp,
                    1,
                    "all_Dtime",
                    data_bound_lower=0
                )
                self.datum_push(
                    "energy__consumption_Dshoulder__inverter",
                    "current", "integral",
                    energy_production_inverter_day - energy_export_grid_day,
                    "Wh",
                    10,
                    bin_timestamp,
                    bin_timestamp,
                    1,
                    "all_Dtime",
                    data_bound_lower=0
                )
            energy_consumption_peak_inverter = self.datum_get(
                DATUM_QUEUE_LAST, "energy__consumption_Dpeak__inverter", "integral", "Wh", 1, "all_Dtime")
            energy_consumption_peak_grid = self.datum_get(
                DATUM_QUEUE_LAST, "energy__consumption_Dpeak__grid", "integral", "Wh", 1, "all_Dtime")
            if energy_consumption_peak_grid is not None and \
                    self.get_time_period(energy_consumption_peak_grid["data_timestamp"], Plugin.get_seconds(1, "day")) != \
                    self.get_time_period(bin_timestamp, Plugin.get_seconds(1, "day")):
                energy_consumption_peak_grid = None
            if energy_consumption_peak_grid is None and bin_timestamp >= \
                    (self.get_time_period(bin_timestamp, Plugin.get_seconds(1, "day")) + HOUR_PEAK_START * 60 * 60):
                self.datum_push(
                    "energy__consumption_Dpeak__grid",
                    "current", "integral",
                    energy_consumption_grid_alltime,
                    "Wh",
                    10,
                    bin_timestamp,
                    bin_timestamp,
                    1,
                    "all_Dtime",
                    data_bound_lower=0
                )
                self.datum_push(
                    "energy__consumption_Dpeak__inverter",
                    "current", "integral",
                    energy_production_inverter_day - energy_export_grid_day,
                    "Wh",
                    10,
                    bin_timestamp,
                    bin_timestamp,
                    1,
                    "all_Dtime",
                    data_bound_lower=0
                )
            energy_consumption_offpeak_inverter = self.datum_get(
                DATUM_QUEUE_LAST, "energy__consumption_Doff_Dpeak__inverter", "integral", "Wh", 1, "all_Dtime")
            energy_consumption_offpeak_grid = self.datum_get(
                DATUM_QUEUE_LAST, "energy__consumption_Doff_Dpeak__grid", "integral", "Wh", 1, "all_Dtime")
            if energy_consumption_offpeak_grid is not None and \
                    self.get_time_period(energy_consumption_offpeak_grid["data_timestamp"], Plugin.get_seconds(1, "day")) != \
                    self.get_time_period(bin_timestamp, Plugin.get_seconds(1, "day")):
                energy_consumption_offpeak_grid = None
            if energy_consumption_offpeak_grid is None and bin_timestamp >= \
                    (self.get_time_period(bin_timestamp, Plugin.get_seconds(1, "day")) + HOUR_OFFPEAK_START * 60 * 60):
                self.datum_push(
                    "energy__consumption_Doff_Dpeak__grid",
                    "current", "integral",
                    energy_consumption_grid_alltime,
                    "Wh",
                    10,
                    bin_timestamp,
                    bin_timestamp,
                    1,
                    "all_Dtime",
                    data_bound_lower=0
                )
                self.datum_push(
                    "energy__consumption_Doff_Dpeak__inverter",
                    "current", "integral",
                    energy_production_inverter_day - energy_export_grid_day,
                    "Wh",
                    10,
                    bin_timestamp,
                    bin_timestamp,
                    1,
                    "all_Dtime",
                    data_bound_lower=0
                )
            energy_consumption_offpeak_morning_grid_day = 0
            if energy_consumption_shoulder_grid is None:
                energy_consumption_offpeak_morning_grid_day = (energy_consumption_grid_alltime -
                                                               energy_consumption_grid_min["data_value"]) \
                    if energy_consumption_grid_min is not None else 0
            else:
                energy_consumption_offpeak_morning_grid_day = \
                    (energy_consumption_shoulder_grid["data_value"] - energy_consumption_grid_min["data_value"]) \
                        if energy_consumption_grid_min is not None else 0
            self.datum_push(
                "energy__consumption_Doff_Dpeak_Dmorning__grid",
                "current", "integral",
                energy_consumption_offpeak_morning_grid_day,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            energy_consumption_shoulder_grid_day = 0
            if energy_consumption_peak_grid is None and energy_consumption_shoulder_grid is not None:
                energy_consumption_shoulder_grid_day = energy_consumption_grid_alltime - energy_consumption_shoulder_grid["data_value"]
            elif energy_consumption_peak_grid is not None and energy_consumption_shoulder_grid is not None:
                energy_consumption_shoulder_grid_day = energy_consumption_peak_grid["data_value"] - \
                                                       energy_consumption_shoulder_grid["data_value"]
            self.datum_push(
                "energy__consumption_Dshoulder__grid",
                "current", "integral",
                energy_consumption_shoulder_grid_day,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            energy_consumption_peak_grid_day = 0
            if energy_consumption_offpeak_grid is None and energy_consumption_peak_grid is not None:
                energy_consumption_peak_grid_day = energy_consumption_grid_alltime - energy_consumption_peak_grid["data_value"]
            elif energy_consumption_offpeak_grid is not None and energy_consumption_peak_grid is not None:
                energy_consumption_peak_grid_day = energy_consumption_offpeak_grid["data_value"] - \
                                                   energy_consumption_peak_grid["data_value"]
            self.datum_push(
                "energy__consumption_Dpeak__grid",
                "current", "integral",
                energy_consumption_peak_grid_day,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            energy_consumption_offpeak_evening_grid_day = 0
            if energy_consumption_offpeak_grid is not None:
                energy_consumption_offpeak_evening_grid_day = energy_consumption_grid_alltime - \
                                                              energy_consumption_offpeak_grid["data_value"]
            self.datum_push(
                "energy__consumption_Doff_Dpeak_Devening__grid",
                "current", "integral",
                energy_consumption_offpeak_evening_grid_day,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            energy_consumption_grid_offpeak_day = energy_consumption_offpeak_morning_grid_day + \
                                                  energy_consumption_offpeak_evening_grid_day
            self.datum_push(
                "energy__consumption_Doff_Dpeak__grid",
                "current", "integral",
                energy_consumption_grid_offpeak_day,
                "Wh",
                10,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            self.datum_push(
                "energy__export__yield",
                "current", "integral",
                self.datum_value(energy_export_grid_day * Decimal(TARIFF_FEEDIN), factor=100),
                "_P24",
                100,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            self.datum_push(
                "energy__consumption__savings",
                "current", "integral",
                self.datum_value((energy_production_inverter_day - energy_export_grid_day) * Decimal(TARIFF_FLAT), factor=100),
                "_P24",
                100,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            self.datum_push(
                "energy__consumption__cost_Dhome",
                "current", "integral",
                self.datum_value(Decimal(SUPPLY_CHARGE) +
                                 energy_consumption_grid_day * Decimal(TARIFF_FLAT), factor=100),
                "_P24",
                100,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            self.datum_push(
                "energy__consumption__cost_Dsmart_Dhome",
                "current", "integral",
                self.datum_value(Decimal(SUPPLY_CHARGE) +
                                 energy_consumption_shoulder_grid_day * Decimal(TARIFF_SHOULDER) +
                                 energy_consumption_peak_grid_day *
                                 Decimal(TARIFF_PEAK if datetime.datetime.fromtimestamp(bin_timestamp).weekday() < 5 else TARIFF_SHOULDER) +
                                 energy_consumption_grid_offpeak_day * Decimal(TARIFF_OFFPEAK), factor=100),
                "_P24",
                100,
                data_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            self.publish()
        except Exception as exception:
            anode.Log(logging.ERROR).log("Plugin", "error", lambda: "[{}] error [{}] processing response:\n{}"
                                         .format(self.name, exception, content), exception)
        log_timer.log("Plugin", "timer", lambda: "[{}]".format(self.name), context=self.push_meter)

    def __init__(self, parent, name, config, reactor):
        super(Fronius, self).__init__(parent, name, config, reactor)
        self.poll_meter_iteration = POLL_METER_ITERATIONS
