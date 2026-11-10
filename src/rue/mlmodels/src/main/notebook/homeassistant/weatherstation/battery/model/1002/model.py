import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

X_MIN = 3.002
X_MAX = 3.965
Y_MIN = 0.0
Y_MAX = 100.0
POLY_A = 287.8610615789477
POLY_B = -1891.2359322558566
POLY_C = 3098.333832031696

def bounded_poly(voltage, voltage_valid):
    if voltage_valid == 0:
        return Y_MIN, 0
    if voltage < X_MIN:
        return Y_MIN, 1
    if voltage > X_MAX:
        return Y_MAX, 1
    return min(max((POLY_A * voltage + POLY_B) * voltage + POLY_C, Y_MIN), Y_MAX), 1


INPUTS = ['weatherstation_console_battery_voltage', 'weatherstation_console_battery_voltage_valid']
OUTPUTS = ['weatherstation_console_battery_capacity_pct', 'weatherstation_console_battery_capacity_pct_valid']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        columns = [model_input[column] if column in model_input else [None] * len(model_input) for column in INPUTS]
        results = [bounded_poly(*values) for values in zip(*columns, strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
