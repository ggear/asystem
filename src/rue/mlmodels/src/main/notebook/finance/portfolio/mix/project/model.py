from math import sqrt

import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = "finance_portfolio_mix_risky_share_pct"
OUTPUT_RETURN = "finance_portfolio_mix_return_pct"
OUTPUT_VOLATILITY = "finance_portfolio_mix_volatility_pct"
RETURN_INTERCEPT = 2.0
RETURN_SLOPE = 4.0
VARIANCE_SQUARE = 220.0
VARIANCE_LINEAR = -20.0
VARIANCE_CONSTANT = 25.0


class Mix(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        weights = [share / 100.0 for share in model_input[INPUT]]
        return pd.DataFrame(
            {
                OUTPUT_RETURN: [RETURN_INTERCEPT + RETURN_SLOPE * weight for weight in weights],
                OUTPUT_VOLATILITY: [sqrt(max(VARIANCE_SQUARE * weight**2 + VARIANCE_LINEAR * weight + VARIANCE_CONSTANT, 0.0)) for weight in weights],
            }
        )


set_model(Mix())
