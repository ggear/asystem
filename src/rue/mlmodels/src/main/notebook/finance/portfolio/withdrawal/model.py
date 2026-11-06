import pandas as pd
from mlflow.models import set_model
from mlflow.pyfunc import PythonModel

INPUT = 'finance_portfolio_withdrawal_age_years'
OUTPUT = 'finance_portfolio_withdrawal_rate_pct'
REAL = 0.02
HORIZON = 100.0


class Withdrawal(PythonModel):
    def predict(self, context, model_input: pd.DataFrame, params=None):
        return pd.DataFrame({OUTPUT: [100.0 * REAL / (1.0 - (1.0 + REAL) ** -max(HORIZON - age, 1.0)) for age in model_input[INPUT]]})


set_model(Withdrawal())
