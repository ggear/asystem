#!/bin/bash

set -o nounset
set -o errexit
set -o pipefail

mlflow doctor
mlflow db upgrade "$MLFLOW_BACKEND_STORE_URI"
exec mlflow server --host 0.0.0.0 --port 5000 --serve-artifacts --artifacts-destination "$MLFLOW_ARTIFACTS_DESTINATION" --default-artifact-root "$MLFLOW_DEFAULT_ARTIFACT_ROOT" --allowed-hosts "$MLFLOW_ALLOWED_HOSTS" --cors-allowed-origins "$MLFLOW_CORS_ALLOWED_ORIGINS" --workers 1
