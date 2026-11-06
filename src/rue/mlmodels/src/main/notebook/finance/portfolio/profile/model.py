from math import exp, sqrt

import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT_SHARE = 'finance_portfolio_profile_risky_share_pct'
INPUT_RATE = 'finance_portfolio_profile_withdrawal_rate_pct'
OUTPUT_RETURN = 'finance_portfolio_profile_return_pct'
OUTPUT_VOLATILITY = 'finance_portfolio_profile_volatility_pct'
OUTPUT_SHORTFALL = 'finance_portfolio_profile_shortfall_probability_pct'
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
    weight = share / 100.0
    mean = RETURN_INTERCEPT + RETURN_SLOPE * weight
    volatility = sqrt(max(VARIANCE_SQUARE * weight**2 + VARIANCE_LINEAR * weight + VARIANCE_CONSTANT, 0.0))
    shortfall = 100.0 / (1.0 + exp(min(-SLOPE * (rate - (M0 + M1 * mean - M2 * volatility)), 50.0)))
    return mean, volatility, shortfall


class Profile(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        results = [profile(share, rate) for share, rate in zip(model_input[INPUT_SHARE], model_input[INPUT_RATE], strict=True)]
        return pd.DataFrame(
            {
                OUTPUT_RETURN: [result[0] for result in results],
                OUTPUT_VOLATILITY: [result[1] for result in results],
                OUTPUT_SHORTFALL: [result[2] for result in results],
            }
        )


set_model(Profile())
