import json
import time

import requests
import weecfg
import weewx
from weewx.almanac import Almanac
from weewx.engine import StdService

URL_DEV = "http://192.168.2.45:8091/rest/?sources=davis"
URL_PROD = "http://127.0.0.1:8091/rest/?sources=davis"


class ANode(StdService):

    def __init__(self, engine, config_dict):
        super(ANode, self).__init__(engine, config_dict)
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def new_loop_packet(self, event):
        self.post_and_forget(URL_PROD, {"packet": self.add_interval(self.add_almanac(event.packet), 2)})
        if weewx.debug:
            self.post_and_forget(URL_DEV, {"packet": self.add_interval(self.add_almanac(event.packet), 2)})
            self.post_and_forget(URL_DEV, {"record": self.add_interval(self.add_record(event.packet), 2)})

    def new_archive_record(self, event):
        self.post_and_forget(URL_PROD, {"record": event.record})
        if weewx.debug:
            self.post_and_forget(URL_DEV, {"record": event.record})

    def add_almanac(self, data):
        almanac = Almanac(time.time(), float(weecfg.get_station_info(self.config_dict)['latitude']),
                          float(weecfg.get_station_info(self.config_dict)['longitude']),
                          float(weecfg.get_station_info(self.config_dict)['altitude'][0]))
        data["sunrise"] = almanac.sun.rise.raw
        data["sunset"] = almanac.sun.set.raw
        data["sunaz"] = almanac.sun.az
        data["sunalt"] = almanac.sun.alt
        return data

    @staticmethod
    def add_interval(data, interval):
        data["interval"] = interval
        return data

    @staticmethod
    def add_record(data):
        data["highOutTemp"] = data["outTemp"]
        data["lowOutTemp"] = data["outTemp"]
        data["windrun"] = 0
        return data

    @staticmethod
    def post_and_forget(url, event):
        data = json.dumps(event)
        # noinspection PyBroadException
        try:
            requests.post(url, data=data)
        except:
            pass
