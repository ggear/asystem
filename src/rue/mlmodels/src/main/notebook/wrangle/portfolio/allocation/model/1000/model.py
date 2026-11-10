import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

EXCESS = 4.0
GAMMA = 3.0

def allocation(volatility):
    share = 100.0 if volatility <= 0.0 else min(100.0, EXCESS / GAMMA / (volatility / 100.0) ** 2)
    return share, EXCESS - 0.5 * GAMMA * (volatility / 100.0) ** 2 * 100.0


INPUTS = ['portfolio_allocation_volatility_pct']
OUTPUTS = ['portfolio_allocation_risky_pct', 'portfolio_allocation_riskadjusted_pct']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        columns = [model_input[column] if column in model_input else [None] * len(model_input) for column in INPUTS]
        results = [allocation(*values) for values in zip(*columns, strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
