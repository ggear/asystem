import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = "finance_forecast_costs_scenario"
OUTPUT = "finance_forecast_costs_growth_pct"
GROWTH = (3.24, 4.83, 6.42)


class Costs(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: [GROWTH[min(max(int(round(scenario)), 0), 2)] for scenario in model_input[INPUT]]})


set_model(Costs())
