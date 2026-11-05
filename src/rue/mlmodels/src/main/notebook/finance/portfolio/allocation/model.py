import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = "finance_portfolio_allocation_volatility_pct"
OUTPUT = "finance_portfolio_allocation_risky_pct"
COEFFICIENT = 1.5


class Allocation(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: [min(100.0, COEFFICIENT / (volatility / 100.0) ** 2) for volatility in model_input[INPUT]]})


set_model(Allocation())
