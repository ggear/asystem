import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

GAIN = 2.5
OFFSET = 1.0

def linear(pyfunc_in):
    return GAIN * pyfunc_in + OFFSET


INPUTS = ['pyfunc_in']
OUTPUTS = ['pyfunc_out']


class Model(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        columns = [model_input[column] if column in model_input else [None] * len(model_input) for column in INPUTS]
        results = [linear(*values) for values in zip(*columns, strict=True)]
        if len(OUTPUTS) == 1:
            results = [(result,) for result in results]
        return pd.DataFrame({column: [result[index] for result in results] for index, column in enumerate(OUTPUTS)})


set_model(Model())
