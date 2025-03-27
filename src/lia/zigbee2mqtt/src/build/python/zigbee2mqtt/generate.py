from os.path import *
import os
import pandas as pd
import urllib3

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

from homeassistant.generate import load_env
from homeassistant.generate import load_entity_metadata

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

DNSMASQ_CONF_PREFIX = "dhcp.dhcpServers"
UNIFI_CONTROLLER_URL = "https://unifi.janeandgraham.com:443"

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    metadata_df = load_entity_metadata()

    metadata_groups_devices_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_name"].str.len() > 0) &
        (metadata_df["zigbee_type"].str.len() > 0) &
        (metadata_df["zigbee_group"].str.len() > 0) &
        (metadata_df["zigbee_config"].str.len() > 0)
        ]
    metadata_groups_devices_dicts = [row.dropna().to_dict() for index, row in metadata_groups_devices_df.iterrows()]
    metadata_groups_dict = {}
    metadata_grouped_devices_dict = {}
    for metadata_groups_devices_dict in metadata_groups_devices_dicts:
        if metadata_groups_devices_dict["zigbee_type"] == "Group":
            metadata_groups_dict[metadata_groups_devices_dict["zigbee_group"]] = metadata_groups_devices_dict
            metadata_grouped_devices_dict[metadata_groups_devices_dict["zigbee_group"]] = []
    for metadata_groups_devices_dict in metadata_groups_devices_dicts:
        if metadata_groups_devices_dict["zigbee_type"] == "Device" and \
                metadata_groups_devices_dict["zigbee_group"] in metadata_grouped_devices_dict:
            metadata_grouped_devices_dict[metadata_groups_devices_dict["zigbee_group"]].append(metadata_groups_devices_dict)
    metadata_groups_path = abspath(join(DIR_ROOT, "src/main/resources/data/groups.yaml"))
    with open(metadata_groups_path, 'w') as metadata_groups_file:
        metadata_groups_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
        """.strip() + "\n")
        for metadata_groups_id in sorted(metadata_groups_dict.keys()):
            if sum(1 for k in metadata_grouped_devices_dict[metadata_groups_id] if k.get('connection_mac')) > 0:
                metadata_groups_file.write("""
'{}':
  friendly_name: '{}'
  retain: true
  {}
  devices:
                """.format(
                    metadata_groups_id,
                    metadata_groups_dict[metadata_groups_id]["device_name"],
                    metadata_groups_dict[metadata_groups_id]["zigbee_config"].replace("\n", "\n  "),
                ).strip() + "\n")
                for metadata_device_dict in metadata_grouped_devices_dict[metadata_groups_id]:
                    if "connection_mac" in metadata_device_dict:
                        metadata_groups_file.write("    " + """
    - '{}'
                        """.format(
                            metadata_device_dict["connection_mac"]
                        ).strip() + "\n")
        print("Build generate script [zigbee2mqtt] entity group metadata persisted to [{}]".format(metadata_groups_path))

    metadata_config_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_name"].str.len() > 0) &
        (metadata_df["zigbee_type"] == "Device") &
        (metadata_df["zigbee_group"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    metadata_config_dicts = [row.dropna().to_dict() for index, row in metadata_config_df.iterrows()]
    metadata_config_path = abspath(join(DIR_ROOT, "src/main/resources/image/mqtt/mqtt_config.sh"))
    with open(metadata_config_path, 'w') as metadata_config_file:
        metadata_config_file.write("""
#!/bin/bash
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
ROOT_DIR="$(dirname "$(readlink -f "$0")")"
while [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null | grep online | wc -l) -ne 1 ]; do :; done
        """.strip() + "\n")
        for metadata_config_dict in metadata_config_dicts:
            metadata_config_file.write("""
${{ROOT_DIR}}/mqtt_config.py '{}' '{}' '{}' '{}'
            """.format(
                metadata_config_dict["connection_mac"],
                metadata_config_dict["device_name"],
                metadata_groups_dict[metadata_config_dict["zigbee_group"]]["device_name"],
                metadata_config_dict["zigbee_device_config"].replace("'", "\"") if "zigbee_device_config" in metadata_config_dict else "",
            ).strip() + "\n")
    os.chmod(metadata_config_path, 0o750)
    print("Build generate script [zigbee2mqtt] entity device config persisted to [{}]".format(metadata_config_path))

    metadata_config_clean_path = abspath(join(DIR_ROOT, "src/main/resources/image/mqtt/mqtt_config_clean.sh"))
    with open(metadata_config_clean_path, 'w') as metadata_config_clean_file:
        metadata_config_clean_file.write("""
#!/bin/bash
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
ROOT_DIR="$(dirname "$(readlink -f "$0")")"
while [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null | grep online | wc -l) -ne 1 ]; do :; done
        """.strip() + "\n")
        for metadata_config_clean_dict in metadata_config_dicts:
            metadata_name = metadata_config_clean_dict["device_name"]
            metadata_config_clean_file.write("""
        mosquitto_pub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -t 'zigbee/bridge/request/group/members/remove_all' -m '{}' && echo '[INFO] Device [{}] removed from all groups' && sleep 1
                    """.format(
                '{{ "device": "{}" }}'.format(metadata_name),
                metadata_name,
            ).strip() + "\n")
    os.chmod(metadata_config_clean_path, 0o750)
    print("Build generate script [zigbee2mqtt] entity device clean persisted to [{}]".format(metadata_config_clean_path))

    metadata_devices_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_name"].str.len() > 0) &
        (metadata_df["zigbee_type"] == "Device") &
        (metadata_df["zigbee_config"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    metadata_devices_dicts = [row.dropna().to_dict() for index, row in metadata_devices_df.iterrows()]
    metadata_devices_path = abspath(join(DIR_ROOT, "src/main/resources/data/devices.yaml"))
    with open(metadata_devices_path, 'w') as metadata_devices_file:
        metadata_devices_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
            """.strip() + "\n")
        for metadata_devices_dict in metadata_devices_dicts:
            metadata_devices_file.write("""
'{}':
  friendly_name: '{}'
  {}
                """.format(
                metadata_devices_dict["connection_mac"],
                metadata_devices_dict["device_name"],
                metadata_devices_dict["zigbee_config"].replace("\n", "\n  "),
            ).strip() + "\n")
        print("Build generate script [zigbee2mqtt] entity device metadata persisted to [{}]".format(metadata_devices_path))
