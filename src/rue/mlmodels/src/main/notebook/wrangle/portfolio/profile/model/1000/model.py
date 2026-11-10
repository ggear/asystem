import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

RETURN_INTERCEPT = 2.0
RETURN_SLOPE = 4.0
VARIANCE_SQUARE = 220.0
VARIANCE_LINEAR = -20.0
VARIANCE_CONSTANT = 25.0
SLOPE = 1.5014
M0 = 3.3555
M1 = 0.7215
M2 = 0.1087

def profile(share, rate):
    from math import exp, sqrt

    weight = share / 100.0
    mean = RETURN_INTERCEPT + RETURN_SLOPE * weight
    volatility = sqrt(max(VARIANCE_SQUARE * weight**2 + VARIANCE_LINEAR * weight + VARIANCE_CONSTANT, 0.0))
    shortfall = 100.0 / (1.0 + exp(min(-SLOPE * (rate - (M0 + M1 * mean - M2 * volatility)), 50.0)))
    return mean, volatility, shortfall


INPUTS = ['portfolio_profile_risky_share_pct', 'portfolio_profile_withdrawal_rate_pct']
OUTPUTS = ['portfolio_profile_return_pct', 'portfolio_profile_volatility_pct', 'portfolio_profile_shortfall_probability_pct']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        results = [profile(*values) for values in zip(*(model_input[column] for column in INPUTS), strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
