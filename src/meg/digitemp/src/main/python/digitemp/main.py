import json
import traceback
from os.path import *

import sys
import time
from digitemp.device import TemperatureSensor
from digitemp.master import UART_Adapter

SERIAL_DEVICE = "/dev/ttyUSBTempProbe"
STACKTRACE_REFERENCE_LIMIT = 1

FORMAT_TEMPLATE = "digitemp,metric={},rom_id={},run_code={}{},run_ms={} {}"

if __name__ == "__main__":
    metadata_digitemp_path = abspath(join("/asystem/runtime/sensors.json"))
    with open(metadata_digitemp_path, 'r') as metadata_digitemp_file:
        for metadata_digitemp_dict in json.load(metadata_digitemp_file):
            run_code = 0
            temperature = None
            run_time_start = time.time()
            try:
                temperature = TemperatureSensor(UART_Adapter(SERIAL_DEVICE),
                                                metadata_digitemp_dict["connection_mac"].replace("0x", "")).get_temperature()
            except Exception as error:
                print("Error getting temperature sensor with name [{}], ID [{}] and serial device [{}] value:".format(
                    metadata_digitemp_dict["unique_id"],
                    metadata_digitemp_dict["connection_mac"],
                    SERIAL_DEVICE,
                ), end="", file=sys.stderr)
                traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
                run_code = 1
            print(FORMAT_TEMPLATE.format(
                metadata_digitemp_dict["unique_id"],
                metadata_digitemp_dict["connection_mac"],
                run_code,
                ",temp_celcius={}".format(temperature) if run_code == 0 else "",
                int((time.time() - run_time_start) * 1000),
                int(time.time() * 1000000000),
            ))
