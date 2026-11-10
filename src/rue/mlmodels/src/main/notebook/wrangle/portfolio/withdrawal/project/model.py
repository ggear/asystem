import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

REAL = 0.02
HORIZON = 100.0

def withdrawal(age):
    return 100.0 * REAL / (1.0 - (1.0 + REAL) ** -max(HORIZON - age, 1.0))


INPUTS = ['portfolio_withdrawal_age_years']
OUTPUTS = ['portfolio_withdrawal_rate_pct']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        columns = [model_input[column] if column in model_input else [None] * len(model_input) for column in INPUTS]
        results = [withdrawal(*values) for values in zip(*columns, strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
