#!/bin/sh

set -o nounset
set -o errexit

mlflow doctor
mlflow db upgrade "$MLFLOW_BACKEND_STORE_URI" 2> /dev/null || true
mlflow server --host 0.0.0.0 --port 5000 --serve-artifacts
