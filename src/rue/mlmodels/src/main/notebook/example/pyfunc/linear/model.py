import pandas as pd
import polars as pl
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = "pyfunc_in"
OUTPUT = "pyfunc_out"
GAIN = 2.5
OFFSET = 1.0


class Linear(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: (pl.Series(model_input[INPUT].to_list()) * GAIN + OFFSET).to_list()})


set_model(Linear())
