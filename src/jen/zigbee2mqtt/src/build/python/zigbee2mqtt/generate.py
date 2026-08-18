import pandas as pd
import urllib3

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

from asystem import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

DNSMASQ_CONF_PREFIX = "dhcp.dhcpServers"
UNIFI_CONTROLLER_URL = "https://unifi.janeandgraham.com:443"
ZIGBEE_TOPIC_GLOB = "zigbee/#"
ZIGBEE_HEALTH_TOPIC = "zigbee/bridge/health"
ZIGBEE_HEALTH_FILTER = ".process.uptime_sec > 0"
ZIGBEE_GROUP_REMOVE_TOPIC = "zigbee/bridge/request/group/members/remove_all"

if __name__ == "__main__":
    env = load_bootstrap_env(DIR_ROOT)
    metadata_df = load_bootstrap_entities()

    write_container_bootstrap()
    write_container_healthchecks()
    write_container_backup()

    write_schema_broker(dialects.vernemq.Discover(ZIGBEE_TOPIC_GLOB, label="Zigbee2MQTT").document())

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
    metadata_config_path = abspath(join(DIR_ROOT, "src/main/resources/image/vernemq/broker_config.sh"))
    with open(metadata_config_path, 'w') as metadata_config_file:
        metadata_config_file.write(dialects.vernemq.config_script(
            "zigbee2mqtt", "config", "apply the declared device and group configuration to the bridge",
            ZIGBEE_HEALTH_TOPIC, ZIGBEE_HEALTH_FILTER, [
                '"${{ROOT_DIR}}/broker_config.py" \'{}\' \'{}\' \'{}\' \'{}\''.format(
                    metadata_config_dict["connection_mac"],
                    metadata_config_dict["device_name"],
                    metadata_groups_dict[metadata_config_dict["zigbee_group"]]["device_name"],
                    metadata_config_dict["zigbee_device_config"].replace("'", "\"") if "zigbee_device_config" in metadata_config_dict else "",
                ) for metadata_config_dict in metadata_config_dicts]))
    os.chmod(metadata_config_path, 0o750)
    print("Build generate script [zigbee2mqtt] entity device config persisted to [{}]".format(metadata_config_path))

    metadata_config_clean_path = abspath(join(DIR_ROOT, "src/main/resources/image/vernemq/broker_config_clean.sh"))
    with open(metadata_config_clean_path, 'w') as metadata_config_clean_file:
        metadata_config_clean_file.write(dialects.vernemq.config_script(
            "zigbee2mqtt", "clean", "remove every declared device from all of its bridge groups",
            ZIGBEE_HEALTH_TOPIC, ZIGBEE_HEALTH_FILTER, [
                'mosquitto_pub "${{BROKER_ARGS[@]}}" -t \'{}\' -m \'{}\' &&\n'
                '  printf \'Device [%s] removed from all groups\\n\' \'{}\' && sleep 1'.format(
                    ZIGBEE_GROUP_REMOVE_TOPIC,
                    '{{ "device": "{}" }}'.format(metadata_config_clean_dict["device_name"]),
                    metadata_config_clean_dict["device_name"],
                ) for metadata_config_clean_dict in metadata_config_dicts]))
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
