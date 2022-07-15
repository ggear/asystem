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

    metadata_zigbee2mqtt_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_name"].str.len() > 0) &
        (metadata_df["zigbee2mqtt_config"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    metadata_zigbee2mqtt_dicts = [row.dropna().to_dict() for index, row in metadata_zigbee2mqtt_df.iterrows()]
    metadata_zigbee2mqtt_devices_path = os.path.abspath(os.path.join(DIR_ROOT, "src/main/resources/config/devices.yaml"))
    with open(metadata_zigbee2mqtt_devices_path, 'w') as metadata_zigbee2mqtt_devices_file:
        metadata_zigbee2mqtt_devices_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
            """.strip() + "\n")
        for metadata_zigbee2mqtt_dict in metadata_zigbee2mqtt_dicts:
            metadata_zigbee2mqtt_devices_file.write("""
'{}':
  friendly_name: '{}'
  retain: true
  qos: 1
{}
                """.format(
                metadata_zigbee2mqtt_dict["connection_mac"],
                metadata_zigbee2mqtt_dict["device_name"],
                metadata_zigbee2mqtt_dict["zigbee2mqtt_config"],
            ).strip() + "\n")
        print("Build generate script [zigbee2mqtt] entity metadata persisted to [{}]".format(metadata_zigbee2mqtt_devices_path))
