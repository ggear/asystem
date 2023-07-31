import json

import time
from os.path import *
from digitemp.device import TemperatureSensor
from digitemp.master import UART_Adapter

DEV_SERIAL = "/dev/ttyUSBTempProbe"

FORMAT_TEMPLATE = "digitemp,metric=temperature,rom_id={},run_code={}{},run_ms={} {}"

if __name__ == "__main__":

    metadata_digitemp_path = abspath(join("/asystem/runtime/sensors.json"))
    with open(metadata_digitemp_path, 'w') as metadata_digitemp_file:
        bus = UART_Adapter(DEV_SERIAL)
        for metadata_digitemp_dict in json.load(metadata_digitemp_file):
            sensor = TemperatureSensor(bus, rom=metadata_digitemp_dict["connection_mac"])
            print(
                "{} {} {}".format(metadata_digitemp_dict["unique_id"], metadata_digitemp_dict["connection_mac"], sensor.get_temperature()))

            # print(FORMAT_TEMPLATE.format(
            #     "108739A80208006F",
            #     0,
            #     ",temp_cel={}".format(10),
            #     "10",
            #     int(time.time() * 1000000000),
            # ))
