import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

MODEL_VERSION = "1000-SNAPSHOT"
INPUT = "example_pyfunc_in"
OUTPUT = "example_pyfunc_out"
GAIN = 2.5
OFFSET = 1.0


class Linear(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: [GAIN * x + OFFSET for x in model_input[INPUT]]})


set_model(Linear())
