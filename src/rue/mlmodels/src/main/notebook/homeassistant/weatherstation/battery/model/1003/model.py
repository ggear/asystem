import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

X_MIN = 3.002
X_MAX = 3.965
Y_MIN = 0.0
Y_MAX = 100.0
K = 39.87174356834223
W = 10.941069143382725
X0 = 3.767393235439091
Y0 = 59.80309909889081

def free_width_arctan(voltage):
    from math import atan

    if voltage < X_MIN:
        return Y_MIN
    if voltage > X_MAX:
        return Y_MAX
    capacity = K * atan(W * (voltage - X0)) + Y0
    if capacity < Y_MIN:
        return Y_MIN
    if capacity > Y_MAX:
        return Y_MAX
    return float(int(capacity) // 5 * 5)


INPUTS = ['weatherstation_console_battery_voltage']
OUTPUTS = ['weatherstation_console_battery_capacity_pct']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        results = [free_width_arctan(*values) for values in zip(*(model_input[column] for column in INPUTS), strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
