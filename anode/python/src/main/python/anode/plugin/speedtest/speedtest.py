from __future__ import print_function

import json
import logging
from decimal import Decimal

import anode
from anode.plugin.plugin import Plugin

SPEEDTEST_ID_METRIC = {
    "2627": "perth",
    "5029": "new_Dyork_Dcity",
    "27260": "london"
}


# noinspection PyBroadException
class Speedtest(Plugin):

    def _push(self, content, targets):
        latency_ping = 0
        throughput_upload = 0
        throughput_download = 0
        packet_type = "latency_throughput"
        bin_timestamp = self.get_time()
        try:
            dict_content = json.loads(content, parse_float=Decimal)
            if "ping-icmp" in dict_content and "ping" not in dict_content:
                packet_type = "latency"
            elif "ping" in dict_content and "ping-icmp" not in dict_content:
                packet_type = "throughput"
            if packet_type != "latency":
                throughput_upload = self.datum_value(dict_content["upload"] / 8000, factor=10)
                if not isinstance(throughput_upload, int): raise Exception
                throughput_download = self.datum_value(dict_content["download"] / 8000000, factor=100)
                if not isinstance(throughput_download, int): raise Exception
            if packet_type != "throughput":
                latency_ping = self.datum_value(dict_content["ping-icmp"], factor=100)
                if not isinstance(latency_ping, int): raise Exception
        except Exception as exception:
            latency_ping = 0
            throughput_upload = 0
            throughput_download = 0
            packet_type = "latency_throughput"
        try:
            for target in targets or []:
                if target in SPEEDTEST_ID_METRIC:
                    if packet_type != "latency":
                        self.datum_push(
                            "internet__speed_Dtest__upload_D" + SPEEDTEST_ID_METRIC[target],
                            "current", "point",
                            throughput_upload,
                            "KB_P2Fs",
                            10,
                            bin_timestamp,
                            bin_timestamp,
                            4,
                            "hour",
                            data_bound_lower=0,
                            data_derived_max=True,
                            data_derived_min=True
                        )
                        self.datum_push(
                            "internet__speed_Dtest__download_D" + SPEEDTEST_ID_METRIC[target],
                            "current", "point",
                            throughput_download,
                            "MB_P2Fs",
                            100,
                            bin_timestamp,
                            bin_timestamp,
                            4,
                            "hour",
                            data_bound_lower=0,
                            data_derived_max=True,
                            data_derived_min=True
                        )
                    if packet_type != "throughput":
                        self.datum_push(
                            "internet__speed_Dtest__ping_D" + SPEEDTEST_ID_METRIC[target],
                            "current", "point",
                            latency_ping,
                            "ms",
                            100,
                            bin_timestamp,
                            bin_timestamp,
                            5,
                            "minute",
                            data_bound_lower=0,
                            data_derived_max=True,
                            data_derived_min=True
                        )
                self.publish()
        except Exception as exception:
            anode.Log(logging.ERROR).log("Plugin", "error", lambda: "[{}] error [{}] processing response:\n{}"
                                         .format(self.name, exception, content), exception)

    def __init__(self, parent, name, config, reactor):
        super(Speedtest, self).__init__(parent, name, config, reactor)
