import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = "finance_portfolio_excess_volatility_pct"
OUTPUT = "finance_portfolio_excess_risk_adjusted_pct"
EXCESS = 4.0
GAMMA = 3.0


class Excess(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: [EXCESS - 0.5 * GAMMA * (volatility / 100.0) ** 2 * 100.0 for volatility in model_input[INPUT]]})


set_model(Excess())
