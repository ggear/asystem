import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

Y_MIN = 0.0
Y_MAX = 100.0
HASS_A = -618.142568664181
HASS_B = 7028.993872449034
HASS_C = -26390.330608127693
HASS_D = 32767.377957563203

def hass_poly(voltage, voltage_valid):
    if voltage_valid == 0:
        return Y_MIN, 0
    capacity = ((HASS_A * voltage + HASS_B) * voltage + HASS_C) * voltage + HASS_D
    return float(round(min(max(capacity, Y_MIN), Y_MAX))), 1


INPUTS = ['weatherstation_console_battery_voltage', 'weatherstation_console_battery_voltage_valid']
OUTPUTS = ['weatherstation_console_battery_capacity_pct', 'weatherstation_console_battery_capacity_pct_valid']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        columns = [model_input[column] if column in model_input else [None] * len(model_input) for column in INPUTS]
        results = [hass_poly(*values) for values in zip(*columns, strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
