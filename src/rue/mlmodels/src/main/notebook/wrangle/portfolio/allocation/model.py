import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = 'portfolio_allocation_volatility_pct'
OUTPUT_RISKY = 'portfolio_allocation_risky_pct'
OUTPUT_ADJUSTED = 'portfolio_allocation_riskadjusted_pct'
EXCESS = 4.0
GAMMA = 3.0


def risky_share(volatility):
    return 100.0 if volatility <= 0.0 else min(100.0, EXCESS / GAMMA / (volatility / 100.0) ** 2)


class Allocation(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        volatilities = list(model_input[INPUT])
        return pd.DataFrame(
            {
                OUTPUT_RISKY: [risky_share(volatility) for volatility in volatilities],
                OUTPUT_ADJUSTED: [EXCESS - 0.5 * GAMMA * (volatility / 100.0) ** 2 * 100.0 for volatility in volatilities],
            }
        )


set_model(Allocation())
