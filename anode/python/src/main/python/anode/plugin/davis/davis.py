from __future__ import print_function

import json
import logging
from decimal import Decimal

import anode
from anode.plugin.plugin import DATUM_QUEUE_MIN
from anode.plugin.plugin import Plugin


# noinspection PyUnusedLocal
class Davis(Plugin):

    def _push(self, content, targets):
        # noinspection PyBroadException
        try:
            dict_content = json.loads(content, parse_float=Decimal)
            bin_timestamp = self.get_time()
            if "packet" in dict_content:
                bin_unit = "second"
                bin_width = dict_content["packet"]["interval"]
                data_timestamp = dict_content["packet"]["dateTime"]
                self.datum_push(
                    "temperature__indoor__utility",
                    "current", "point",
                    None if self.datum_value(dict_content["packet"], ["inTemp"]) is None else self.datum_value(
                        (dict_content["packet"]["inTemp"] - 32) * 5 / 9 - 1, factor=10),
                    "_PC2_PB0C",
                    10,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "humidity__indoor__utility",
                    "current", "point",
                    self.datum_value(dict_content["packet"], ["inHumidity"]),
                    "_P25",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_bound_upper=100,
                    data_bound_lower=0,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "sun__outdoor__azimuth",
                    "current", "point",
                    self.datum_value(dict_content["packet"], ["sunaz"]),
                    "_PC2_PB0",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "sun__outdoor__altitude",
                    "current", "point",
                    self.datum_value(dict_content["packet"], ["sunalt"]),
                    "_PC2_PB0",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "sun__outdoor__rise",
                    "current", "epoch",
                    self.datum_value(dict_content["packet"], ["sunrise"]),
                    "scalar",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    1,
                    "day"
                )
                self.datum_push(
                    "sun__outdoor__set",
                    "current", "epoch",
                    self.datum_value(dict_content["packet"], ["sunset"]),
                    "scalar",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    1,
                    "day"
                )
                self.datum_push(
                    "temperature__outdoor__roof",
                    "current", "point",
                    None if self.datum_value(dict_content["packet"], ["outTemp"]) is None else self.datum_value(
                        (dict_content["packet"]["outTemp"] - 32) * 5 / 9, factor=10),
                    "_PC2_PB0C",
                    10,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_derived_max=True,
                    data_derived_min=True
                )

                # TODO: Disable wind properties since weewx doesnt seem to report them any more, or at the least they are None when 0
                # self.datum_push(
                #     "wind__outdoor__speed",
                #     "current", "point",
                #     None if self.datum_value(dict_content["packet"], ["windSpeed"]) is None else self.datum_value(
                #         dict_content["packet"]["windSpeed"] * Decimal(1.60934)),
                #     "km_P2Fh",
                #     1,
                #     data_timestamp,
                #     bin_timestamp,
                #     bin_width,
                #     bin_unit,
                #     data_bound_lower=0,
                #     data_derived_max=True,
                #     data_derived_min=True
                # )
                # self.datum_push(
                #     "wind__outdoor__bearing",
                #     "current", "point",
                #     self.datum_value(dict_content["packet"], ["windDir"]),
                #     "_PC2_PB0",
                #     1,
                #     data_timestamp,
                #     bin_timestamp,
                #     bin_width,
                #     bin_unit,
                #     data_bound_lower=0,
                #     data_derived_max=True,
                #     data_derived_min=True
                # )
                # self.datum_push(
                #     "wind__outdoor__chill",
                #     "current", "point",
                #     None if self.datum_value(dict_content["packet"], ["windchill"]) is None else self.datum_value(
                #         (dict_content["packet"]["windchill"] - 32) * 5 / 9, factor=10),
                #     "_PC2_PB0C",
                #     10,
                #     data_timestamp,
                #     bin_timestamp,
                #     bin_width,
                #     bin_unit,
                #     data_derived_max=True,
                #     data_derived_min=True
                # )

                self.datum_push(
                    "wind__outdoor__gust_Dspeed",
                    "current", "point",
                    None if self.datum_value(dict_content["packet"], ["windGust"]) is None else self.datum_value(
                        dict_content["packet"]["windGust"] * Decimal(1.60934)),
                    "km_P2Fh",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_bound_lower=0,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "wind__outdoor__gust_Dbearing",
                    "current", "point",
                    self.datum_value(dict_content["packet"], ["windGustDir"]),
                    "_PC2_PB0",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_bound_lower=0,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "pressure__outdoor__roof",
                    "current", "point",
                    None if self.datum_value(dict_content["packet"], ["barometer"]) is None else self.datum_value(
                        dict_content["packet"]["barometer"] * Decimal(33.8639)),
                    "mbar",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_bound_lower=0,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "heatindex__outdoor__roof",
                    "current", "point",
                    self.datum_value(dict_content["packet"], ["heatindex"]),
                    "scalar",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_bound_lower=0,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "humidity__outdoor__roof",
                    "current", "point",
                    self.datum_value(dict_content["packet"], ["outHumidity"]),
                    "_P25",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_bound_upper=100,
                    data_bound_lower=0,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "cloud__outdoor__base",
                    "current", "point",
                    None if self.datum_value(dict_content["packet"], ["cloudbase"]) is None else self.datum_value(
                        dict_content["packet"]["cloudbase"] * Decimal(0.3048)),
                    "m",
                    1,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "rain__outdoor__roof_Ddew_Dpoint",
                    "current", "point",
                    None if self.datum_value(dict_content["packet"], ["dewpoint"]) is None else self.datum_value(
                        (dict_content["packet"]["dewpoint"] - 32) * 5 / 9, factor=10),
                    "_PC2_PB0C",
                    10,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "rain__indoor__utility_Ddew_Dpoint",
                    "current", "point",
                    None if self.datum_value(dict_content["packet"], ["inDewpoint"]) is None else self.datum_value(
                        (dict_content["packet"]["inDewpoint"] - 32) * 5 / 9, factor=10),
                    "_PC2_PB0C",
                    10,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_derived_max=True,
                    data_derived_min=True
                )
                rain_outdoor_roof_month = None if self.datum_value(dict_content["packet"], ["monthRain"]) is None else self.datum_value(
                    dict_content["packet"]["monthRain"] * Decimal(2.54), factor=100)
                self.datum_push(
                    "rain__outdoor__month",
                    "current", "integral",
                    rain_outdoor_roof_month,
                    "cm",
                    100,
                    data_timestamp,
                    bin_timestamp,
                    1,
                    "month",
                    data_bound_lower=0,
                    data_derived_min=True
                )
                rain_outdoor_roof_month_min = self.datum_get(DATUM_QUEUE_MIN, "rain__outdoor__roof", "integral", "cm", 1, "month", 1, "day")
                rain_outdoor_roof_day = rain_outdoor_roof_month - rain_outdoor_roof_month_min["data_value"] \
                    if rain_outdoor_roof_month_min is not None else 0
                self.datum_push(
                    "rain__outdoor__day",
                    "current", "integral",
                    rain_outdoor_roof_day * 10,
                    "mm",
                    100,
                    data_timestamp,
                    bin_timestamp,
                    1,
                    "day",
                    data_bound_lower=0
                )
                self.datum_push(
                    "rain__outdoor__year",
                    "current", "integral",
                    None if self.datum_value(dict_content["packet"], ["yearRain"]) is None else self.datum_value(
                        dict_content["packet"]["yearRain"] * Decimal(0.0254), factor=10000),
                    "m",
                    10000,
                    data_timestamp,
                    bin_timestamp,
                    1,
                    "year",
                    data_bound_lower=0,
                    data_derived_min=True
                )
            if "record" in dict_content:
                bin_unit = "minute"
                bin_width = dict_content["record"]["interval"]
                data_timestamp = dict_content["record"]["dateTime"]
                self.datum_push(
                    "rain__outdoor__rate",
                    "current", "mean",
                    None if self.datum_value(dict_content["record"], ["rainRate"]) is None else self.datum_value(
                        dict_content["record"]["rainRate"] * Decimal(25.4), factor=10),
                    "mm_P2Fh",
                    10,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_bound_lower=0,
                    data_derived_max=True,
                    data_derived_min=True
                )
                self.datum_push(
                    "rain__outdoor__last_D30_Dmin",
                    "current", "integral",
                    None if self.datum_value(dict_content["record"], ["rain"]) is None else self.datum_value(
                        dict_content["record"]["rain"] * Decimal(25.4), factor=10),
                    "mm",
                    10,
                    data_timestamp,
                    bin_timestamp,
                    bin_width,
                    bin_unit,
                    data_bound_lower=0,
                    data_derived_min=True
                )
            self.publish()
        except Exception as exception:
            anode.Log(logging.ERROR).log("Plugin", "error", lambda: "[{}] error [{}] processing response:\n{}"
                                         .format(self.name, exception, content), exception)

    def __init__(self, parent, name, config, reactor):
        super(Davis, self).__init__(parent, name, config, reactor)
