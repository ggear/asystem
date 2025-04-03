[ "$(curl "http://${MLFLOW_SERVICE}:${MLFLOW_HTTP_PORT}/health")" == "OK" ]
# TODO: Provide implementation that reflects on models being served
