import pandas as pd
import yaml

pd.options.mode.chained_assignment = None

from asystem import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

ZIGBEE_CONFIG_PATH = abspath(join(DIR_ROOT, "src/main/resources/data/configuration.yaml"))

with open(ZIGBEE_CONFIG_PATH) as zigbee_config_file:
    ZIGBEE_BASE_TOPIC = yaml.safe_load(zigbee_config_file)["mqtt"]["base_topic"]

if __name__ == "__main__":
    env = load_bootstrap_env(DIR_ROOT)
    metadata_df = load_bootstrap_entities()

    write_container_bootstrap()
    write_container_healthchecks()
    write_container_backup()
    write_container_restore()

    write_schema_broker(dialects.vernemq.Discover("{}/#".format(ZIGBEE_BASE_TOPIC), label="Zigbee2MQTT").document())

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
    metadata_config_path = abspath(join(DIR_ROOT, "src/main/resources/image/broker_config.sh"))
    with open(metadata_config_path, 'w') as metadata_config_file:
        metadata_config_file.write(dialects.vernemq.config_script(
            "zigbee2mqtt", "config", "apply the declared device and group configuration to the bridge",
            "{}/bridge/state".format(ZIGBEE_BASE_TOPIC), '.state == "online"', [
                "configure '{}' '{}' '{}' '{}'".format(
                    metadata_config_dict["connection_mac"],
                    metadata_config_dict["device_name"],
                    metadata_groups_dict[metadata_config_dict["zigbee_group"]]["device_name"],
                    metadata_config_dict["zigbee_device_config"].replace("'", "\"") if "zigbee_device_config" in metadata_config_dict else "",
                ) for metadata_config_dict in metadata_config_dicts] + ["configured"],
            preamble="""
FAULTS=0

retained() {{
  mosquitto_sub "${{BROKER_ARGS[@]}}" -t "$1" -C 1 -W 2 2>/dev/null || true
}}

membership() {{
  jq -nc --arg group "$1" --arg device "$2" '{{group: $group, device: $device}}'
}}

grouped() {{
  retained '{base}/bridge/groups' | jq -e --arg group "$1" --arg address "$2" \\
    'any(.[]; .friendly_name == $group and any(.members[]?; .ieee_address == $address))' >/dev/null 2>&1
}}

straying() {{
  retained '{base}/bridge/groups' | jq -r --arg group "$1" --arg address "$2" \\
    '.[] | select(.friendly_name != $group) | select(any(.members[]?; .ieee_address == $address)) | .friendly_name'
}}

configure() {{
  local address="$1" name="$2" group="$3" config="$4" attempt=0 stray
  if ! retained "{base}/${{name}}/availability" | jq -e '.state == "online"' >/dev/null 2>&1; then
    printf 'Device [%s] not available currently, skipping config\\n' "${{name}}"
    return 0
  fi
  while IFS= read -r stray; do
    [ -z "${{stray}}" ] && continue
    mosquitto_pub "${{BROKER_ARGS[@]}}" -t '{base}/bridge/request/group/members/remove' -m "$(membership "${{stray}}" "${{name}}")"
    printf 'Device [%s] removed from stray group [%s]\\n' "${{name}}" "${{stray}}"
    sleep 1
  done < <(straying "${{group}}" "${{address}}")
  while [ "${{attempt}}" -lt 3 ]; do
    if grouped "${{group}}" "${{address}}"; then
      printf 'Device [%s] group [%s] configured\\n' "${{name}}" "${{group}}"
      return 0
    fi
    if [ -n "${{config}}" ]; then
      mosquitto_pub "${{BROKER_ARGS[@]}}" -t "{base}/${{name}}/set" -m "${{config}}"
      printf 'Device [%s] config command pushed\\n' "${{name}}"
    fi
    mosquitto_pub "${{BROKER_ARGS[@]}}" -t '{base}/bridge/request/group/members/add' -m "$(membership "${{group}}" "${{name}}")"
    printf 'Device [%s] group [%s] add command pushed\\n' "${{name}}" "${{group}}"
    attempt=$((attempt + 1))
    sleep 2
  done
  FAULTS=$((FAULTS + 1))
  fail "Device [${{name}}] could not be added to group [${{group}}] after [${{attempt}}] attempts" \\
    "The bridge did not report the device as a group member, check the device is paired and responding"
  return 0
}}

configured() {{
  if [ "${{FAULTS}}" != 0 ]; then
    printf '\\nBroker config [%s] found [%s] fault(s)\\n' "zigbee2mqtt" "${{FAULTS}}" >&2
    exit 1
  fi
  printf '\\nBroker config [%s] applied to every available device\\n' "zigbee2mqtt"
}}
""".format(base=ZIGBEE_BASE_TOPIC)))
    os.chmod(metadata_config_path, 0o750)
    print("Build generate script [zigbee2mqtt] entity device config persisted to [{}]".format(metadata_config_path))

    metadata_config_clean_path = abspath(join(DIR_ROOT, "src/main/resources/image/broker_config_clean.sh"))
    with open(metadata_config_clean_path, 'w') as metadata_config_clean_file:
        metadata_config_clean_file.write(dialects.vernemq.config_script(
            "zigbee2mqtt", "clean", "remove every declared device from all of its bridge groups",
            "{}/bridge/state".format(ZIGBEE_BASE_TOPIC), '.state == "online"', [
                'mosquitto_pub "${{BROKER_ARGS[@]}}" -t \'{}\' -m \'{}\' &&\n'
                '  printf \'Device [%s] removed from all groups\\n\' \'{}\' && sleep 1'.format(
                    "{}/bridge/request/group/members/remove_all".format(ZIGBEE_BASE_TOPIC),
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
