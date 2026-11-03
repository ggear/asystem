import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel


class Demo(PythonModel):
    def predict(self, context, model_input, params=None):
        return pd.DataFrame({"demo_out_seconds": model_input["demo_in_seconds"] * 2})


set_model(Demo())
