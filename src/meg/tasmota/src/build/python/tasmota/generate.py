import glob
import os
import sys

import pandas as pd

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_env
from homeassistant.generate import load_entity_metadata

pd.options.mode.chained_assignment = None

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    metadata_df = load_entity_metadata()

    metadata_tasmota_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Tasmota") &
        (metadata_df["entity_namespace"] == "switch") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["device_model"].str.len() > 0) &
        (metadata_df["device_manufacturer"].str.len() > 0) &
        (metadata_df["custom_config"].str.len() > 0) &
        (metadata_df["connection_ip"].str.len() > 0)
        ].sort_values("connection_ip")
    metadata_tasmota_dicts = [row.dropna().to_dict() for index, row in metadata_tasmota_df.iterrows()]
    tasmota_config_path = os.path.join(DIR_ROOT, "src/build/resources/tasmota_config.sh")
    with open(tasmota_config_path, "wt") as tasmota_config_file:
        tasmota_config_file.write("""
#!/bin/sh
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
        """.strip() + "\n")
        for metadata_tasmota_dict in metadata_tasmota_dicts:
            tasmota_device_path = os.path.join(DIR_ROOT, "src/build/resources/devices/", metadata_tasmota_dict["unique_id"])
            with open(tasmota_device_path + ".json", "wt") as tasmota_device_file:
                tasmota_device_file.write("""
{{
  "templatename": "{} {}",
  "user_template": {},
  "devicename": "{}",
  "friendlyname": [ "{}" ],
  "mqtt_host": "{}",
  "mqtt_port": {},
  "mqtt_client": "DVES_%06X",
  "mqtt_grptopic": "tasmotas",
  "mqtt_topic": "{}",
  "mqtt_fulltopic": "tasmota/device/%topic%/%prefix%/",
  "mqtt_prefix": [ "cmnd", "stat", "tele" ],
  "mqtt_retry": 10,
  "mqtt_keepalive": 30,
  "mqtt_socket_timeout": 4,
  "mqtt_user": "DVES_USER",
  "mqtt_pwd": "DVES_PASS"
}}
                """.format(
                    metadata_tasmota_dict["device_manufacturer"],
                    metadata_tasmota_dict["device_model"],
                    metadata_tasmota_dict["custom_config"],
                    metadata_tasmota_dict["unique_id"],
                    metadata_tasmota_dict["friendly_name"],
                    env["VERNEMQ_IP_PROD"],
                    env["VERNEMQ_PORT"],
                    metadata_tasmota_dict["unique_id"],
                ).strip() + "\n\n")
            tasmota_config_file.write(
                "echo '' && echo 'Processing config for device [{}] at [http://{}/cn] ... '\n".format(
                    metadata_tasmota_dict["unique_id"],
                    metadata_tasmota_dict["connection_ip"],
                ))
            if not os.path.exists(tasmota_device_path + "-backup.json"):
                os.system("decode-config.py -s {} -o {}-backup.json --json-indent 2".format(
                    metadata_tasmota_dict["connection_ip"],
                    tasmota_device_path,
                ))
            tasmota_config_file.write(
                "decode-config.py -s {} -i {}.json || true\n".format(
                    metadata_tasmota_dict["connection_ip"],
                    tasmota_device_path,
                ))
        tasmota_config_file.write("echo ''")
    print("Build generate script [tasmota] entity metadata persisted to [{}]".format(tasmota_config_path))
