/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl -sf --max-time 5 "http://${MLFLOW_SERVICE}:${MLFLOW_HTTP_PORT}/health")" == "OK" ]
