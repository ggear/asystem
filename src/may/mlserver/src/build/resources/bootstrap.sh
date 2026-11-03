for model in $(echo "${MLSERVER_MODELS}" | tr ',' ' '); do
  model_dir="${MLFLOW_MODEL_DIR}/${model}"
  rm -rf "${model_dir}"
  timeout 120 mlflow artifacts download --artifact-uri "models:/${model}@release" --dst-path "${model_dir}" || {
    echo "ERROR Pull failed model [${model}] alias [release]" >&2
    exit 1
  }
  echo "Pulled model [${model}] alias [release]"
done
