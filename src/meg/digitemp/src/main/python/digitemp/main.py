import json
import traceback
from os.path import *

import sys
import time
from digitemp.device import TemperatureSensor
from digitemp.master import UART_Adapter

FILE_SERIAL_DEVICE = "/dev/ttyUSB0"
FILE_SENSORS = "/asystem/runtime/sensors.json"
FORMAT_TEMPLATE = "digitemp,metric=temperature{},run_code={} {}run_ms={} {}"

if __name__ == "__main__":
    run_time_start = time.time()
    run_code = 0
    run_code_metric_fail = 0
    run_code_metric_success = 0
    metadata_digitemp_path = abspath(FILE_SENSORS)
    if isfile(metadata_digitemp_path):
        with open(metadata_digitemp_path, 'r') as metadata_digitemp_file:
            for metadata_digitemp_dict in json.load(metadata_digitemp_file):
                run_code_metric = 0
                temperature = None
                run_time_start_metric = time.time()
                try:
                    temperature = TemperatureSensor(UART_Adapter(FILE_SERIAL_DEVICE),
                                                    metadata_digitemp_dict["connection_mac"].replace("0x", "")).get_temperature()
                    run_code_metric_success += 1
                except Exception as error:
                    print("Error getting temperature sensor with name [{}], ID [{}] and serial device [{}]:".format(
                        metadata_digitemp_dict["unique_id"],
                        metadata_digitemp_dict["connection_mac"],
                        FILE_SERIAL_DEVICE,
                    ), end="", file=sys.stderr)
                    traceback.print_exc(limit=1)
                    run_code_metric = 1
                    run_code_metric_fail += 1
                print(FORMAT_TEMPLATE.format(
                    ",sensor_name={},sensor_rom={}".format(
                        metadata_digitemp_dict["unique_id"],
                        metadata_digitemp_dict["connection_mac"],
                    ),
                    run_code_metric,
                    "{}_celsius={},".format(metadata_digitemp_dict["unique_id"], temperature) if run_code_metric == 0 else "",
                    int((time.time() - run_time_start_metric) * 1000),
                    int(time.time() * 1000000000),
                ))
    else:
        run_code = 1
        print("Error reading sensors file at [{}]".format(metadata_digitemp_path), file=sys.stderr)
    print(FORMAT_TEMPLATE.format(
        "",
        run_code,
        "metrics_succeeded={},metrics_failed={},".format(run_code_metric_success, run_code_metric_fail),
        int((time.time() - run_time_start) * 1000),
        int(time.time() * 1000000000),
    ))
