[ "$(jq -er .model_version /train/en_US-rhasspy/training_info.json 2>/dev/null)" == "1.0" ]
