/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl "http://${MLFLOW_SERVICE}:${MLFLOW_HTTP_PORT}/health")" == "OK" ]
