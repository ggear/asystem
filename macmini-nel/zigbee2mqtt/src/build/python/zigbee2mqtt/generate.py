import glob
import os
import sys

import pandas as pd
import urllib3

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_env
from homeassistant.generate import load_entity_metadata

DNSMASQ_CONF_PREFIX = "dhcp.dhcpServers"
UNIFI_CONTROLLER_URL = "https://unifi.janeandgraham.com:443"

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    metadata_df = load_entity_metadata()

    metadata_devices_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_name"].str.len() > 0) &
        (metadata_df["zigbee2mqtt_type"] == "Device") &
        (metadata_df["zigbee2mqtt_config"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    metadata_devices_dicts = [row.dropna().to_dict() for index, row in metadata_devices_df.iterrows()]
    metadata_devices_path = os.path.abspath(os.path.join(DIR_ROOT, "src/main/resources/config/devices.yaml"))
    with open(metadata_devices_path, 'w') as metadata_devices_file:
        metadata_devices_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
            """.strip() + "\n")
        for metadata_devices_dict in metadata_devices_dicts:
            metadata_devices_file.write("""
'{}':
  friendly_name: '{}'
  retain: true
  qos: 1
{}
                """.format(
                metadata_devices_dict["connection_mac"],
                metadata_devices_dict["device_name"].replace("-", " ").title(),
                metadata_devices_dict["zigbee2mqtt_config"],
            ).strip() + "\n")
        print("Build generate script [zigbee2mqtt] entity device metadata persisted to [{}]".format(metadata_devices_path))

    metadata_groups_devices_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_name"].str.len() > 0) &
        (metadata_df["zigbee2mqtt_type"].str.len() > 0) &
        (metadata_df["zigbee2mqtt_group"].str.len() > 0) &
        (metadata_df["zigbee2mqtt_config"].str.len() > 0)
        ]
    metadata_groups_devices_dicts = [row.dropna().to_dict() for index, row in metadata_groups_devices_df.iterrows()]
    metadata_groups_dict = {}
    metadata_grouped_devices_dict = {}
    for metadata_groups_devices_dict in metadata_groups_devices_dicts:
        if metadata_groups_devices_dict["zigbee2mqtt_type"] == "Group":
            metadata_groups_dict[metadata_groups_devices_dict["zigbee2mqtt_group"]] = metadata_groups_devices_dict
            metadata_grouped_devices_dict[metadata_groups_devices_dict["zigbee2mqtt_group"]] = []
    for metadata_groups_devices_dict in metadata_groups_devices_dicts:
        if metadata_groups_devices_dict["zigbee2mqtt_type"] == "Device" and \
                metadata_groups_devices_dict["zigbee2mqtt_group"] in metadata_grouped_devices_dict:
            metadata_grouped_devices_dict[metadata_groups_devices_dict["zigbee2mqtt_group"]].append(metadata_groups_devices_dict)
    metadata_groups_path = os.path.abspath(os.path.join(DIR_ROOT, "src/main/resources/config/groups.yaml"))
    with open(metadata_groups_path, 'w') as metadata_groups_file:
        metadata_groups_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
            """.strip() + "\n")
        for metadata_groups_id in metadata_groups_dict:
            metadata_groups_file.write("""
'{}':
  friendly_name: '{}'
  retain: true
{}
  devices:
            """.format(
                metadata_groups_id,
                metadata_groups_dict[metadata_groups_id]["device_name"].replace("-", " ").title(),
                metadata_groups_dict[metadata_groups_id]["zigbee2mqtt_config"],
            ).strip() + "\n")
            for metadata_device_dict in metadata_grouped_devices_dict[metadata_groups_id]:
                metadata_groups_file.write("    " + """
    - '{}'
                """.format(
                    metadata_device_dict["connection_mac"]
                ).strip() + "\n")
        print("Build generate script [zigbee2mqtt] entity group metadata persisted to [{}]".format(metadata_groups_path))
