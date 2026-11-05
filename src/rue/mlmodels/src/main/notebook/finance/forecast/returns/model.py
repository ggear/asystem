import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = "finance_forecast_returns_scenario"
OUTPUT = "finance_forecast_returns_nominal_pct"
RETURNS = (3.55, 6.0, 8.45)


class Returns(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: [RETURNS[min(max(int(round(scenario)), 0), 2)] for scenario in model_input[INPUT]]})


set_model(Returns())
