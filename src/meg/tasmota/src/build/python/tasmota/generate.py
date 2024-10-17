import glob
import json
import os
import sys
from os.path import *

import pandas as pd

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
for dir_module in glob.glob(join(DIR_ROOT, "../../*/*")):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, join(dir_module, "src/build/python"))

from homeassistant.generate import load_env
from homeassistant.generate import load_entity_metadata
from homeassistant.generate import write_entity_metadata

pd.options.mode.chained_assignment = None

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    metadata_df = load_entity_metadata()

    metadata_tasmota_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Tasmota") &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["device_model"].str.len() > 0) &
        (metadata_df["device_manufacturer"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0)
        ].sort_values("connection_ip")

    write_entity_metadata("tasmota", join(DIR_ROOT, "src/main/resources/config/mqtt"), metadata_tasmota_df,
                          "homeassistant/+/tasmota/#", "tasmota/#")

    metadata_tasmota_dicts = [row.dropna().to_dict() for index, row in metadata_tasmota_df.iterrows()]
    tasmota_config_path = join(DIR_ROOT, "src/build/resources/tasmota_config.sh")
    tasmota_devices_path = join(DIR_ROOT, "src/build/resources/devices")
    os.makedirs(tasmota_devices_path, exist_ok=True)
    with open(tasmota_config_path, "wt") as tasmota_config_file:
        tasmota_config_file.write("""
#!/bin/bash
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
echo ''
        """.strip() + "\n")
        for metadata_tasmota_dict in metadata_tasmota_dicts:
            tasmota_device_path = join(tasmota_devices_path, metadata_tasmota_dict["unique_id"])
            if metadata_tasmota_dict["entity_namespace"] != "sensor":
                with open(tasmota_device_path + ".json", "wt") as tasmota_device_file:
                    metadata_tasmota_config_version = 1 if \
                        any(metadata_tasmota_dict["device_model"].startswith(metadata_tasmota_model)
                            for metadata_tasmota_model in ["POWR316D", "THR316D"]) else 0
                    metadata_tasmota_config_dict = {
                        "config_version": metadata_tasmota_config_version,
                        "templatename": "{} {}".format(
                            metadata_tasmota_dict["device_manufacturer"],
                            metadata_tasmota_dict["device_model"]
                        ),
                        "devicename": "{}".format(metadata_tasmota_dict["unique_id"]),
                        "friendlyname": [metadata_tasmota_dict["friendly_name"]],
                        "mqtt_host": "{}".format(env["VERNEMQ_SERVICE_PROD"]),
                        "mqtt_port": env["VERNEMQ_PORT"],
                        "mqtt_client": "DVES_%06X",
                        "mqtt_grptopic": "tasmotas",
                        "mqtt_topic": "{}".format(metadata_tasmota_dict["unique_id"]),
                        "mqtt_fulltopic": "tasmota/device/%topic%/%prefix%/",
                        "mqtt_prefix": ["cmnd", "stat", "tele"],
                        "mqtt_retry": 10,
                        "mqtt_keepalive": 30,
                        "mqtt_socket_timeout": 4,
                        "mqtt_user": "DVES_USER",
                        "mqtt_pwd": "DVES_PASS"
                    }
                    if metadata_tasmota_config_version == 0 and "custom_config" in metadata_tasmota_dict:
                        metadata_tasmota_config_dict["user_template"] = metadata_tasmota_dict["custom_config"]
                    tasmota_device_file.write(json.dumps(metadata_tasmota_config_dict, indent=4))
                tasmota_config_file.write("if netcat -zw 1 {} 80 2>/dev/null; then\n".format(
                    metadata_tasmota_dict["connection_ip"]),
                )
                tasmota_config_file.write(
                    "\techo 'Processing config for device [{}] at [http://{}/?] ... '\n".format(
                        metadata_tasmota_dict["unique_id"],
                        metadata_tasmota_dict["connection_ip"],
                    ))
                tasmota_config_file.write(
                    "\techo 'Current firmware ['\"$(curl -s -m 5 http://{}/cm? --data-urlencode 'cmnd=Status 2' | jq -r .StatusFWR.Version | cut -f1 -d\\()\"'] versus required [{}]'\n".format(
                        metadata_tasmota_dict["connection_ip"],
                        env["TASMOTA_FIRMWARE_VERSION"],
                    ))
                if not exists(tasmota_device_path + "-backup.json"):
                    os.system("netcat -zw 1 {} 80 2>/dev/null && decode-config.py -s {} -o {}-backup.json --json-indent 2".format(
                        metadata_tasmota_dict["connection_ip"],
                        metadata_tasmota_dict["connection_ip"],
                        tasmota_device_path,
                    ))
                tasmota_config_file.write(
                    "\tdecode-config.py -s {} -i {}.json\n".format(
                        metadata_tasmota_dict["connection_ip"],
                        tasmota_device_path,
                    ))
                if "tasmota_device_config" in metadata_tasmota_dict:
                    tasmota_config_file.write(
                        "\tsleep 1 && while ! netcat -zw 1 {} 80 2>/dev/null; do echo 'Waiting for device [{}] to come up ...' && sleep 1; done\n".format(
                            metadata_tasmota_dict["connection_ip"],
                            metadata_tasmota_dict["unique_id"],
                        ))
                    metadata_tasmota_config_dict = json.loads(metadata_tasmota_dict["tasmota_device_config"])
                    for metadata_tasmota_config in metadata_tasmota_config_dict:
                        tasmota_config_file.write(
                            "\tif [ \"$(curl -s -m 5 http://{}/cm? --data-urlencode 'cmnd={}' | grep '{}' | wc -l)\" -ne 1 ]; then\n".format(
                                metadata_tasmota_dict["connection_ip"],
                                metadata_tasmota_config,
                                json.dumps({
                                    metadata_tasmota_config: metadata_tasmota_config_dict[metadata_tasmota_config]
                                }, separators=(',', ':')),
                            ))
                        tasmota_config_file.write(
                            "\t\tprintf 'Config set [{}] to [{}] with response: ' && curl -s -m 5 http://{}/cm? --data-urlencode 'cmnd={} {}'\n".format(
                                metadata_tasmota_config,
                                metadata_tasmota_config_dict[metadata_tasmota_config],
                                metadata_tasmota_dict["connection_ip"],
                                metadata_tasmota_config,
                                metadata_tasmota_config_dict[metadata_tasmota_config],
                            ))
                        tasmota_config_file.write("\t\techo ''\n")
                        tasmota_config_file.write(
                            "\telse\n\t\techo 'Config set skipped, [{}] already set to [{}]'\n\tfi\n".format(
                                metadata_tasmota_config,
                                metadata_tasmota_config_dict[metadata_tasmota_config],
                            ))
                    tasmota_config_file.write(
                        "\tprintf 'Restarting [{}] with response: ' && curl -s -m 5 http://{}/cm? --data-urlencode 'cmnd=Restart 1'\n".format(
                            metadata_tasmota_dict["unique_id"],
                            metadata_tasmota_dict["connection_ip"],
                        ))
                    tasmota_config_file.write("\tprintf '\n'\n")
                    tasmota_config_file.write(
                        "\tprintf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && while ! netcat -zw 1 {} 80 2>/dev/null; do printf '.' && sleep 1; done\n".format(
                            metadata_tasmota_dict["connection_ip"],
                            metadata_tasmota_dict["unique_id"],
                        ))
                    tasmota_config_file.write("\tprintf ' done\n'\n")
                tasmota_config_file.write(
                    "else\n\techo 'Skipping config for device [{}] at [http://{}/?] given it is unresponsive'\n".format(
                        metadata_tasmota_dict["unique_id"],
                        metadata_tasmota_dict["connection_ip"],
                    ))
                tasmota_config_file.write("fi\necho ''\n")
    print("Build generate script [tasmota] entity metadata persisted to [{}]".format(tasmota_config_path))
