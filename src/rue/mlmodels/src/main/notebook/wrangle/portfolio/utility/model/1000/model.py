import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

GAMMA = 3.0

def utility_model(wealth):
    from math import log

    return log(wealth) if GAMMA == 1.0 else wealth ** (1.0 - GAMMA) / (1.0 - GAMMA)


INPUTS = ['portfolio_utility_wealth']
OUTPUTS = ['portfolio_utility_value']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        columns = [model_input[column] if column in model_input else [None] * len(model_input) for column in INPUTS]
        results = [utility_model(*values) for values in zip(*columns, strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
