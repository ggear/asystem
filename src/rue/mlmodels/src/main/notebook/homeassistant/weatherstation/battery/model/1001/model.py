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

def refitted_poly(voltage):
    if voltage < X_MIN:
        return Y_MIN
    if voltage > X_MAX:
        return Y_MAX
    return (POLY_A * voltage + POLY_B) * voltage + POLY_C


INPUTS = ['weatherstation_console_battery_voltage']
OUTPUTS = ['weatherstation_console_battery_capacity_pct']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        results = [refitted_poly(*values) for values in zip(*(model_input[column] for column in INPUTS), strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
