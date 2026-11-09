from math import log

import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = 'portfolio_utility_wealth'
OUTPUT = 'portfolio_utility_value'
GAMMA = 3.0


def utility(wealth):
    return log(wealth) if GAMMA == 1.0 else wealth ** (1.0 - GAMMA) / (1.0 - GAMMA)


class Utility(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: [utility(wealth) for wealth in model_input[INPUT]]})


set_model(Utility())
