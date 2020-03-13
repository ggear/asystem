from __future__ import print_function

import json
import logging

from twisted.internet.protocol import DatagramProtocol

import anode
from anode.plugin.plugin import DATUM_QUEUE_MIN
from anode.plugin.plugin import Plugin

PLUGS = {
    "adhoc": "192.168.2.60",
    "filter": "192.168.2.61",
    "fridge": "192.168.2.62",
    "freezer": "192.168.2.63",
    "booster": "192.168.2.64",
    "servers": "192.168.2.65",
    "fan": "192.168.2.66",
}


# noinspection PyPep8Naming
class KasaMeter(DatagramProtocol):
    PORT = 9999
    ENCRYPT_KEY = 0xAB

    @staticmethod
    def encrypt(value, key):
        values = list(value)
        for i in range(len(values)):
            encoded = ord(values[i])
            values[i] = chr(encoded ^ int(key))
            key = ord(values[i])
        return "".join(values)

    @staticmethod
    def decrypt(value, key):
        values = list(value.decode("latin_1"))
        for i in range(len(values)):
            encoded = ord(values[i])
            values[i] = chr(encoded ^ key)
            key = encoded
        return "".join(values)

    def startProtocol(self):
        self.transport.connect(self.ip, KasaMeter.PORT)

    def datagramRequest(self):
        try:
            self.transport.write(KasaMeter.encrypt('{"emeter": {"get_realtime": {}}}', KasaMeter.ENCRYPT_KEY))
        except Exception as exception:
            anode.Log(logging.ERROR).log("Plugin", "state", lambda: "[kasa] write failed to [{}:{}:{}]"
                                         .format(self.name, self.ip, KasaMeter.PORT), exception)

    def datagramReceived(self, data, (host, port)):
        try:
            bin_timestamp = self.plugin.get_time()
            decrypted = KasaMeter.decrypt(data, KasaMeter.ENCRYPT_KEY)
            meter = json.loads(decrypted)
            self.plugin.datum_push(
                "power__consumption__" + self.name,
                "current", "point",
                int(self.plugin.datum_value(meter, ["emeter", "get_realtime", "power_mw"], 0, 1) / 1000) if self.plugin.datum_value(
                    meter, ["emeter", "get_realtime", "power_mw"], 0) < 10000000 else 0,
                "W",
                1,
                bin_timestamp,
                bin_timestamp,
                self.plugin.config["poll_seconds"],
                "second",
                data_bound_lower=0,
                data_derived_max=True,
                data_derived_min=True
            )
            energy_consumption_alltime = self.plugin.datum_value(meter, ["emeter", "get_realtime", "total_wh"], 0, 1)
            self.plugin.datum_push(
                "energy__consumption__" + self.name,
                "current", "integral",
                energy_consumption_alltime,
                "Wh",
                1,
                bin_timestamp,
                bin_timestamp,
                1,
                "all_Dtime",
                data_bound_lower=0,
                data_derived_min=True
            )
            energy_consumption_alltime_min = self.plugin.datum_get(
                DATUM_QUEUE_MIN, "energy__consumption__" + self.name, "integral", "Wh", 1, "all_Dtime", 1, "day")
            energy_consumption_day = (energy_consumption_alltime - energy_consumption_alltime_min["data_value"]) \
                if energy_consumption_alltime_min is not None else 0
            self.plugin.datum_push(
                "energy__consumption__" + self.name,
                "current", "integral",
                energy_consumption_day,
                "Wh",
                1,
                bin_timestamp,
                bin_timestamp,
                1,
                "day",
                data_bound_lower=0
            )
            self.plugin.publish()
        except Exception as exception:
            anode.Log(logging.ERROR).log("Plugin", "error",
                                         lambda: "[kasa] error [{}] processing response length [{}] and decrypted as [{}] from [{}:{}:{}]"
                                         .format(exception, len(data), decrypted if 'decrypted' in vars() else "",
                                                 self.name, self.ip, KasaMeter.PORT), exception)

    def connectionRefused(self):
        anode.Log(logging.ERROR).log("Plugin", "state", lambda: "[kasa] connection refused to [{}:{}:{}]"
                                     .format(self.name, self.ip, KasaMeter.PORT))

    def __init__(self, plugin, name, ip):
        self.plugin = plugin
        self.name = name
        self.ip = ip


class Kasa(Plugin):

    def _poll(self):
        for plug in self.meters:
            plug.datagramRequest()

    def __init__(self, parent, name, config, reactor):
        super(Kasa, self).__init__(parent, name, config, reactor)
        self.meters = [KasaMeter(self, name, ip) for name, ip in PLUGS.iteritems()]
        if "listenUDP" in dir(reactor):
            for plug in self.meters:
                reactor.listenUDP(0, plug)
