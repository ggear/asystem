import json
from os.path import *

import pandas as pd

from homeassistant.generate import load_entity_metadata

pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    metadata_kasa_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "TPLink") &
        (metadata_df["entity_namespace"] == "switch") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["connection_ip"].str.len() > 0)
        ].sort_values("connection_ip")
    metadata_kasa_dicts = [row.dropna().to_dict() for index, row in metadata_kasa_df.iterrows()]
    kasa_config_path = join(DIR_ROOT, "src/build/resources/kasa_config.sh")
    with open(kasa_config_path, "wt") as kasa_config_file:
        kasa_config_file.write("""
#!/bin/bash
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
        """.strip() + "\n")
        for metadata_kasa_dict in metadata_kasa_dicts:
            kasa_config_file.write("if netcat -zw 1 {} 9999 2>/dev/null; then\n".format(
                metadata_kasa_dict["connection_ip"]),
            )
            kasa_config_file.write(
                "\techo '' && echo 'Processing config for device [{}] at [{}] ... '\n".format(
                    metadata_kasa_dict["unique_id"],
                    metadata_kasa_dict["connection_ip"],
                ))
            kasa_config_file.write(
                "\tkasa --host {} --type plug alias '{}'\n".format(
                    metadata_kasa_dict["connection_ip"],
                    metadata_kasa_dict["unique_id"].replace("_", " ").title(),
                ))
            if "custom_config" in metadata_kasa_dict:
                metadata_kasa_config_dict = json.loads(metadata_kasa_dict["custom_config"])
                if "led" in metadata_kasa_config_dict:
                    kasa_config_file.write(
                        "\tkasa --host {} --type plug led '{}'\n".format(
                            metadata_kasa_dict["connection_ip"],
                            metadata_kasa_config_dict["led"],
                        ))
            kasa_config_file.write(
                "else\n\techo '' && echo 'Skipping config for device [{}] at [http://{}/?] given it is unresponsive'\n".format(
                    metadata_kasa_dict["unique_id"],
                    metadata_kasa_dict["connection_ip"],
                ))
            kasa_config_file.write("fi\n")
        kasa_config_file.write("echo ''")
        print("Build generate script [kasa] entity metadata persisted to [{}]".format(kasa_config_path))
