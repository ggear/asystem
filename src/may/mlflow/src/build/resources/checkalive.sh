curl -sf --max-time 5 "http://${MLFLOW_SERVICE}:${MLFLOW_HTTP_PORT}/health" >/dev/null
