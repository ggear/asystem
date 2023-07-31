import time

from digitemp.device import TemperatureSensor
from digitemp.master import UART_Adapter

FORMAT_TEMPLATE = "digitemp,metric=temperature,rom_id={},run_code={}{},run_ms={} {}"

if __name__ == "__main__":
    bus = UART_Adapter('/dev/ttyUSBTempProbe')
    sensor = TemperatureSensor(bus, rom='28FF641E870006AE')
    sensor.info()
    print(sensor.get_temperature())

    # print(FORMAT_TEMPLATE.format(
    #     "108739A80208006F",
    #     0,
    #     ",temp_cel={}".format(10),
    #     "10",
    #     int(time.time() * 1000000000),
    # ))
