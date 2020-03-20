from __future__ import print_function

import datetime
import logging
import os
import re
import time

import pandas
from scipy.stats import norm

import anode
from anode.application import APP_MODEL_ENERGYFORECAST_INTERDAY_PROD_VERSION
from anode.application import APP_MODEL_ENERGYFORECAST_INTRADAY_PROD_VERSION
from anode.plugin.plugin import DATUM_QUEUE_LAST
from anode.plugin.plugin import DATUM_QUEUE_MAX
from anode.plugin.plugin import Plugin


class Energyforecast(Plugin):

    def _poll(self):
        log_timer = anode.Log(logging.DEBUG).start()
        try:
            bin_timestamp = self.get_time()
            model_day_inter = self.pickled_get(os.path.join(self.config["db_dir"], "amodel"), name="energyforecastinterday")
            model_day_intra = self.pickled_get(os.path.join(self.config["db_dir"], "amodel"), name="energyforecastintraday")
            if "energyforecastinterday" in model_day_inter and "energyforecastintraday" in model_day_intra and \
                    APP_MODEL_ENERGYFORECAST_INTRADAY_PROD_VERSION in model_day_intra["energyforecastintraday"] and \
                    self.anode.get_plugin("davis") is not None and \
                    self.anode.get_plugin("darksky") is not None:
                energy_production_today = self.anode.get_plugin("fronius").datum_get(
                    DATUM_QUEUE_LAST, "energy__production__inverter", "integral", "Wh", 1, "day")
                energy_production_today = energy_production_today["data_value"] / energy_production_today["data_scale"] \
                    if energy_production_today is not None else None
                sun_rise = self.anode.get_plugin("davis").datum_get(
                    DATUM_QUEUE_LAST, "sun__outdoor__rise", "epoch", "scalar", 1, "day")
                sun_rise = sun_rise["data_value"] / sun_rise["data_scale"] \
                    if sun_rise is not None else None
                sun_set = self.anode.get_plugin("davis").datum_get(
                    DATUM_QUEUE_LAST, "sun__outdoor__set", "epoch", "scalar", 1, "day")
                sun_set = sun_set["data_value"] / sun_set["data_scale"] \
                    if sun_set is not None else None
                sun_azimuth = self.anode.get_plugin("davis").datum_get(
                    DATUM_QUEUE_LAST, "sun__outdoor__azimuth", "point", "_PC2_PB0", 2, "second")
                sun_azimuth = sun_azimuth["data_value"] / sun_azimuth["data_scale"] \
                    if sun_azimuth is not None else None
                sun_altitude = self.anode.get_plugin("davis").datum_get(
                    DATUM_QUEUE_LAST, "sun__outdoor__altitude", "point", "_PC2_PB0", 2, "second")
                sun_altitude = sun_altitude["data_value"] / sun_altitude["data_scale"] \
                    if sun_altitude is not None else None
                current = int(time.time())
                sun_percentage = (0 if current < sun_rise else (100 if current > sun_set else (
                        (current - sun_rise) / float(sun_set - sun_rise) * 100))) \
                    if (sun_set is not None and sun_rise is not None and (sun_set - sun_rise) != 0) else 0
                for day in range(1, 4):
                    temperature_forecast = self.anode.get_plugin("darksky").datum_get(
                        DATUM_QUEUE_MAX if day == 1 else DATUM_QUEUE_LAST,
                        "temperature__forecast__darlington", "point", "_PC2_PB0C", day, "day")
                    temperature_forecast = temperature_forecast["data_value"] / temperature_forecast["data_scale"] \
                        if temperature_forecast is not None else None
                    rain_forecast = self.anode.get_plugin("darksky").datum_get(
                        DATUM_QUEUE_MAX if day == 1 else DATUM_QUEUE_LAST,
                        "rain__forecast__darlington", "integral", "mm", day, "day_Dtime")
                    rain_forecast = rain_forecast["data_value"] / rain_forecast["data_scale"] \
                        if rain_forecast is not None else 0
                    humidity_forecast = self.anode.get_plugin("darksky").datum_get(
                        DATUM_QUEUE_MAX if day == 1 else DATUM_QUEUE_LAST,
                        "humidity__forecast__darlington", "mean", "_P25", day, "day")
                    humidity_forecast = humidity_forecast["data_value"] / humidity_forecast["data_scale"] \
                        if humidity_forecast is not None else None
                    wind_forecast = self.anode.get_plugin("darksky").datum_get(
                        DATUM_QUEUE_LAST,
                        "wind__forecast__darlington", "mean", "km_P2Fh", day, "day")
                    wind_forecast = wind_forecast["data_value"] / wind_forecast["data_scale"] \
                        if wind_forecast is not None else None
                    conditions_forecast = self.anode.get_plugin("darksky").datum_get(
                        DATUM_QUEUE_LAST,
                        "conditions__forecast__darlington", "enumeration", "__", day, "day")
                    conditions_forecast = conditions_forecast["data_string"] \
                        if conditions_forecast is not None else None
                    model_features_dict = {
                        "datum__bin__date": datetime.datetime.fromtimestamp(bin_timestamp + (86400 * (day - 1))).strftime('%Y/%m/%d'),
                        "energy__production__inverter": 0,
                        "temperature__forecast__darlington": temperature_forecast,
                        "rain__forecast__darlington": rain_forecast,
                        "humidity__forecast__darlington": humidity_forecast,
                        "wind__forecast__darlington": wind_forecast,
                        "sun__outdoor__rise": sun_rise,
                        "sun__outdoor__set": sun_set,
                        "sun__outdoor__azimuth": sun_azimuth,
                        "sun__outdoor__altitude": sun_altitude,
                        "conditions__forecast__darlington": conditions_forecast
                    }
                    model_features = pandas.DataFrame([model_features_dict]).apply(pandas.to_numeric, errors='ignore')
                    for model_version in model_day_inter["energyforecastinterday"]:
                        if model_version >= APP_MODEL_ENERGYFORECAST_INTERDAY_PROD_VERSION:
                            energy_production_forecast = 0
                            model_classifier = "" if model_version == APP_MODEL_ENERGYFORECAST_INTERDAY_PROD_VERSION \
                                else ("_D" + model_version)
                            if day > 1 or sun_percentage <= 65 or \
                                    self.datum_get(DATUM_QUEUE_LAST, "energy__production_Dforecast" + model_classifier + "__inverter",
                                                   "high", "Wh", day, "day") is None:
                                model = model_day_inter["energyforecastinterday"][model_version][1]
                                try:
                                    energy_production_forecast = model['execute'](model=model, features=model['execute'](
                                        features=model_features, engineering=True), prediction=True)[0]
                                except Exception as exception:
                                    anode.Log(logging.ERROR).log("Plugin", "error",
                                                                 lambda: "[{}] error [{}] executing model [{}] with features {}".format(
                                                                     self.name, exception, model_version, model_features_dict), exception)
                                self.datum_push(
                                    "energy__production_Dforecast" + model_classifier + "__inverter",
                                    "forecast", "high" if day == 1 else "integral",
                                    self.datum_value(energy_production_forecast, factor=10),
                                    "Wh",
                                    10,
                                    bin_timestamp,
                                    bin_timestamp,
                                    day,
                                    "day",
                                    asystem_version=model_day_inter["energyforecastinterday"][model_version][0],
                                    data_version=model_version,
                                    data_bound_lower=0)
                            if day == 1:
                                model = model_day_intra["energyforecastintraday"][APP_MODEL_ENERGYFORECAST_INTRADAY_PROD_VERSION][1]
                                energy_production_forecast = self.datum_get(DATUM_QUEUE_LAST,
                                                                            "energy__production_Dforecast" + model_classifier +
                                                                            "__inverter", "high", "Wh", day, "day")
                                energy_production_forecast = energy_production_forecast["data_value"] / \
                                                             energy_production_forecast["data_scale"] \
                                    if energy_production_forecast is not None else 0
                                energy_production_forecast_scaled = 0
                                energy_production_forecast_scaled_features_dict = \
                                    {"energy__production_Dforecast_Ddaylight__inverter": int(sun_percentage * 10)}
                                try:
                                    energy_production_forecast_scaled = energy_production_forecast * model['execute'](
                                        model=model, features=pandas.DataFrame([energy_production_forecast_scaled_features_dict])
                                            .apply(pandas.to_numeric, errors='ignore'), prediction=True).iloc[0][0].item()
                                except Exception as exception:
                                    anode.Log(logging.ERROR).log("Plugin", "error",
                                                                 lambda: "[{}] error [{}] executing model [{}] with features {}".format(
                                                                     "energyforecastintraday", exception, model_version,
                                                                     energy_production_forecast_scaled_features_dict), exception)
                                self.datum_push(
                                    "energy__production_Dforecast" + model_classifier + "__inverter",
                                    "forecast", "integral",
                                    self.datum_value(energy_production_forecast_scaled, factor=10),
                                    "Wh",
                                    10,
                                    bin_timestamp,
                                    bin_timestamp,
                                    day,
                                    "day",
                                    asystem_version=model_day_inter["energyforecastinterday"][model_version][0],
                                    data_version=model_version,
                                    data_bound_lower=0)
                                if model_classifier == "":
                                    self.datum_push(
                                        "energy__production_Dforecast_Ddaylight__inverter",
                                        "forecast", "point",
                                        self.datum_value(sun_percentage, factor=10),
                                        "_P25",
                                        10,
                                        bin_timestamp,
                                        bin_timestamp,
                                        day,
                                        "day",
                                        asystem_version=model_day_inter["energyforecastinterday"][model_version][0],
                                        data_version=model_version,
                                        data_bound_lower=0,
                                        data_bound_upper=100)
                                energy_production_forecast_actual = 100 if energy_production_today is not None else 0
                                if energy_production_today is not None and energy_production_today != 0:
                                    energy_production_forecast_actual = int(((energy_production_forecast_scaled -
                                                                              energy_production_today) * norm.cdf(sun_percentage, 40, 15) +
                                                                             energy_production_today) / energy_production_today * 100)
                                self.datum_push(
                                    "energy__production_Dforecast_Dactual" + model_classifier + "__inverter",
                                    "forecast", "point",
                                    self.datum_value(energy_production_forecast_actual),
                                    "_P25",
                                    1,
                                    bin_timestamp,
                                    bin_timestamp,
                                    day,
                                    "day",
                                    asystem_version=model_day_inter["energyforecastinterday"][model_version][0],
                                    data_version=model_version,
                                    data_bound_lower=0,
                                    data_derived_max=True)
            self.publish()
        except Exception as exception:
            anode.Log(logging.ERROR).log("Plugin", "error", lambda: "[{}] error [{}] processing model"
                                         .format(self.name, exception), exception)
        log_timer.log("Plugin", "timer", lambda: "[{}]".format(self.name), context=self._poll)

    def __init__(self, parent, name, config, reactor):
        super(Energyforecast, self).__init__(parent, name, config, reactor)

        def metric_drop(metric):
            for datum_metric, datum in self.datums.items():
                model_version = re.match(metric + "_D([1-9][0-9]{3})__inverter", datum_metric)
                if model_version is not None:
                    del self.datums[datum_metric]

        metric_drop("energy__production_Dforecast")
        metric_drop("energy__production_Dforecast_Dactual")
