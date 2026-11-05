from math import exp

import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = "finance_portfolio_montecarlo_spending_rate_pct"
OUTPUT = "finance_portfolio_montecarlo_ruin_pct"
SLOPE = 1.0883
MIDPOINT = 5.1025


class Montecarlo(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: [100.0 / (1.0 + exp(-SLOPE * (rate - MIDPOINT))) for rate in model_input[INPUT]]})


set_model(Montecarlo())
