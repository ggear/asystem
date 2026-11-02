for model in $(echo "${MLSERVER_MODELS}" | tr ',' ' '); do
  model_dir="${MLFLOW_MODEL_DIR}/${model}"
  rm -rf "${model_dir}.new"
  if timeout 120 mlflow artifacts download --artifact-uri "models:/${model}@release" --dst-path "${model_dir}.new"; then
    rm -rf "${model_dir}" && mv "${model_dir}.new" "${model_dir}"
    echo "Pulled model [${model}] alias [release]"
  else
    rm -rf "${model_dir}.new"
    echo "WARN Pull failed model [${model}] alias [release], keeping any cached copy"
  fi
done
