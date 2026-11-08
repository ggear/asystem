from math import atan

import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = "weatherstation_console_battery_voltage"
OUTPUT = "weewx_console_battery_capacity_pct"
MEAN_INPUT = 'weatherstation_console_battery_voltage_mean20'
X_MIN = 3.002000093460083
X_MAX = 3.9649999141693115
Y_MIN = 0.0
Y_MAX = 100.0
STEP = 5
SHELF_LOW = 3.77
SHELF_HIGH = 3.83
SHELF_CENTRE = 0.5 * (SHELF_LOW + SHELF_HIGH)
K = 57.963759356712906
W = 5.0
X0 = 3.783983480797712
Y0 = 62.58092515895401


def capacity_pct(voltage, mean=None):
    smoothed = mean is not None and mean == mean
    reading = mean if smoothed else voltage
    if reading < X_MIN:
        return Y_MIN
    if reading > X_MAX:
        return Y_MAX
    if not smoothed and SHELF_LOW <= reading <= SHELF_HIGH:
        reading = SHELF_CENTRE
    capacity = K * atan(W * (reading - X0)) + Y0
    if capacity < Y_MIN:
        return Y_MIN
    if capacity > Y_MAX:
        return Y_MAX
    return float(int(capacity) // STEP * STEP)


class ConsoleBattery(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        means = model_input[MEAN_INPUT] if MEAN_INPUT in model_input.columns else [None] * len(model_input)
        return pd.DataFrame({OUTPUT: [capacity_pct(voltage, mean) for voltage, mean in zip(model_input[INPUT], means, strict=True)]})


set_model(ConsoleBattery())
