/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  curl -sf --max-time 10 "http://localhost:5000/api/2.0/mlflow/registered-models/search?max_results=1" >/dev/null &&
  curl -sf --max-time 10 "http://localhost:5000/api/2.0/mlflow/experiments/search?max_results=1" >/dev/null
