import glob
import os
import sys

import pandas as pd

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_entity_metadata

pd.options.mode.chained_assignment = None

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    metadata_tasmota_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Tasmota") &
        (metadata_df["entity_namespace"] == "switch") &
        (metadata_df["unique_id"].str.len() > 0) &
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
        """.strip() + "\n\n")
        for metadata_tasmota_dict in metadata_tasmota_dicts:
            tasmota_device_path = os.path.join(DIR_ROOT, "src/build/resources/devices/", metadata_tasmota_dict["unique_id"] + ".json")
            if not os.path.exists(tasmota_device_path):
                os.system("decode-config.py -s {} -o {} --json-indent 2".format(
                    metadata_tasmota_dict["connection_ip"],
                    tasmota_device_path,
                ))
            tasmota_config_file.write(
                "echo 'Processing config for device [{}] at [http://{}/cn] ... ' && decode-config.py -s {} -i {}\n".format(
                    metadata_tasmota_dict["unique_id"],
                    metadata_tasmota_dict["connection_ip"],
                    metadata_tasmota_dict["connection_ip"],
                    tasmota_device_path,
                ))
    print("Build generate script [tasmota] entity metadata persisted to [{}]".format(tasmota_config_path))
