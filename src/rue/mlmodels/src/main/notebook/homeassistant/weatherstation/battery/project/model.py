import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

X_MIN = 3.002
X_MAX = 3.965
Y_MIN = 0.0
Y_MAX = 100.0
K = 64.05025793850861
X0 = 3.802862056721742
Y0 = 70.75003479926724
W = 5.0
SHELF_LOW = 3.77
SHELF_HIGH = 3.83
SHELF_CENTRE = 3.8

def arctan_shelf(voltage):
    from math import atan

    if voltage < X_MIN:
        return Y_MIN
    if voltage > X_MAX:
        return Y_MAX
    reading = SHELF_CENTRE if SHELF_LOW <= voltage <= SHELF_HIGH else voltage
    capacity = K * atan(W * (reading - X0)) + Y0
    if capacity < Y_MIN:
        return Y_MIN
    if capacity > Y_MAX:
        return Y_MAX
    return float(int(capacity) // 5 * 5)


INPUTS = ['weatherstation_console_battery_voltage']
OUTPUTS = ['weatherstation_console_battery_capacity_pct']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        results = [arctan_shelf(*values) for values in zip(*(model_input[column] for column in INPUTS), strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
