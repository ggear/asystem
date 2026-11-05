from math import atan

import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = "weatherstation_console_battery_voltage"
OUTPUT = "weewx_console_battery_capacity_pct"
X_MIN = 3.002000093460083
X_MAX = 3.9649999141693115
Y_MIN = 0.0
Y_MAX = 100.0
STEP = 5
K = 40.68866819068917
W = 9.507014011286998
X0 = 3.7629938319692826
Y0 = 56.74132585468961


def capacity_pct(voltage):
    if voltage < X_MIN:
        return Y_MIN
    if voltage > X_MAX:
        return Y_MAX
    capacity = K * atan(W * (voltage - X0)) + Y0
    if capacity < Y_MIN:
        return Y_MIN
    if capacity > Y_MAX:
        return Y_MAX
    return float(int(capacity) // STEP * STEP)


class ConsoleBattery(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: [capacity_pct(voltage) for voltage in model_input[INPUT]]})


set_model(ConsoleBattery())
