for model in $(echo "${MLSERVER_MODELS}" | tr ',' ' '); do
  model_dir="${MLFLOW_MODEL_DIR}/${model}"
  rm -rf "${model_dir}"
  timeout 120 mlflow artifacts download --artifact-uri "models:/${model}@release" --dst-path "${model_dir}" || {
    echo "ERROR Pull failed model [${model}] alias [release]" >&2
    exit 1
  }
  evaluation="$(find "${model_dir}" -name evaluation.json | head -n 1)"
  if [[ -z "${evaluation}" ]] || ! python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["passed"] is True else 1)' "${evaluation}"; then
    rm -rf "${model_dir}"
    echo "ERROR Acceptance not passed model [${model}] alias [release]" >&2
    exit 1
  fi
  echo "Pulled model [${model}] alias [release]"
done
