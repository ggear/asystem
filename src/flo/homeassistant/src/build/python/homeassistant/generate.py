import datetime
import glob
import json
import sys
import time
from collections import OrderedDict
from os.path import *

import pandas as pd
from pathlib2 import Path
from requests import get

DIR_ROOT = abspath("{}/../../../..".format(dirname(realpath(__file__))))


def load_env(root_dir=None):
    env = {}
    env_path = abspath(join(DIR_ROOT if root_dir is None else root_dir, ".env"))
    if not isfile(env_path):
        env_path = abspath(join(DIR_ROOT if root_dir is None else root_dir, "target/release/.env"))
    if not isfile(env_path):
        raise Exception("Could not find dev or prod .env file!")
    with open(env_path, 'r') as env_file:
        for env_line in env_file:
            env_line = env_line.replace("export ", "").rstrip()
            if "=" not in env_line:
                continue
            if env_line.startswith("#"):
                continue
            env_key, env_value = env_line.split("=", 1)
            env[env_key] = env_value
    print("Build generate script environment loaded from [{}]".format(env_path))
    sys.stdout.flush()
    return env


def load_modules():
    modules = {}
    host_labels_names = {line.split("=")[0]: line.split("=")[-1].split(",")
                         for line in Path(join(dirname(abspath(join(DIR_ROOT, "../.."))), ".hosts")).read_text().strip().split("\n")}
    for module in glob.glob(abspath(join(DIR_ROOT, "../../*/*"))):
        env = load_env(module)
        name = basename(module)
        hosts = ["{}-{}".format(host_labels_names[host_label][0], host_label) for host_label in basename(dirname(module)).split("_")]
        modules[name] = [hosts, env]
    return modules


def load_entity_metadata():
    metadata_path = abspath(join(DIR_ROOT, "src/build/resources/entity_metadata.xlsx"))
    metadata_df = pd.read_excel(metadata_path, header=2, dtype=str)
    metadata_df["index"] = metadata_df["index"].astype(int)
    metadata_df = metadata_df.set_index(metadata_df["index"]).sort_index()
    print("Build generate script entity metadata loaded from [{}]".format(metadata_path))
    sys.stdout.flush()
    return metadata_df


if __name__ == "__main__":
    env = load_env()
    metadata_df = load_entity_metadata()

    # Verify entity IDs
    metadata_verify_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] != "_") &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0)
        ]
    metadata_verify_dicts = [row.dropna().to_dict() for index, row in metadata_verify_df.iterrows()]
    for metadata_verify_dict in metadata_verify_dicts:
        try:
            state_response = get(
                "http://{}:{}/api/states/{}.{}".format(
                    env["HOMEASSISTANT_IP_PROD"],
                    env["HOMEASSISTANT_HTTP_PORT"],
                    metadata_verify_dict["entity_namespace"],
                    metadata_verify_dict["unique_id"]
                ), headers={
                    "Authorization": "Bearer {}".format(env["HOMEASSISTANT_API_TOKEN"]),
                    "content-type": "application/json",
                })
            if state_response.status_code == 200:
                hours_since_update = (time.time() - (time.mktime(datetime.datetime.strptime(
                    state_response.json()["last_updated"].split('+')[0], '%Y-%m-%dT%H:%M:%S.%f').timetuple()) + 8 * 60 * 60)) / (60 * 60)
                if hours_since_update > 6:
                    print("Build generate script [homeassistant] entity metadata [{}.{}] not recently updated, [{:.1f}] hours"
                          .format(metadata_verify_dict["entity_namespace"], metadata_verify_dict["unique_id"], hours_since_update),
                          file=sys.stderr if \
                              "haas_display_mode" in metadata_verify_dict and \
                              metadata_verify_dict["entity_namespace"] == "sensor"
                          else sys.stdout)
                else:
                    print("Build generate script [homeassistant] entity metadata [{}.{}] verified"
                          .format(metadata_verify_dict["entity_namespace"], metadata_verify_dict["unique_id"]))
            else:
                print("Build generate script [homeassistant] entity metadata [{}.{}] not found"
                      .format(metadata_verify_dict["entity_namespace"], metadata_verify_dict["unique_id"]), file=sys.stderr)
        except Exception as exception:
            print("Build generate script [homeassistant] could not connect to HAAS with error [{}]".format(exception))

    # Build customise YAML
    metadata_customise_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] != "_") &
        (metadata_df["device_via_device"] != "Action") &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["friendly_name"].str.len() > 0) &
        (metadata_df["entity_domain"].str.len() > 0)
        ]
    metadata_customise_dicts = [row.dropna().to_dict() for index, row in metadata_customise_df.iterrows()]
    metadata_customise_path = abspath(join(DIR_ROOT, "src/main/resources/config/customise.yaml"))
    with open(metadata_customise_path, 'w') as metadata_customise_file:
        metadata_customise_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
        """.strip() + "\n")
        for metadata_customise_dict in metadata_customise_dicts:
            metadata_customise_file.write("""
{}.{}:
  friendly_name: '{}'
            """.format(
                metadata_customise_dict["entity_namespace"],
                metadata_customise_dict["unique_id"],
                metadata_customise_dict["friendly_name"],
            ).strip() + "\n")
            if "icon" in metadata_customise_dict:
                metadata_customise_file.write("  " + """
  icon: '{}'
                """.format(
                    metadata_customise_dict["icon"],
                ).strip() + "\n")
            if "unit_of_measurement" in metadata_customise_dict:
                metadata_customise_file.write("  " + """
  unit_of_measurement: '{}'
                """.format(
                    metadata_customise_dict["unit_of_measurement"],
                ).strip() + "\n")
        print("Build generate script [homeassistant] entity metadata persisted to [{}]".format(metadata_customise_path))

    # Build compensation YAML
    metadata_compensation_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["compensation_curve"].str.len() > 0)
        ]
    metadata_compensation_dicts = [row.dropna().to_dict() for index, row in metadata_compensation_df.iterrows()]
    metadata_compensation_path = abspath(join(DIR_ROOT, "src/main/resources/config/custom_packages/compensation.yaml"))
    with open(metadata_compensation_path, 'w') as metadata_compensation_file:
        metadata_compensation_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
compensation:
        """.strip() + "\n")
        for metadata_compensation_dict in metadata_compensation_dicts:
            metadata_compensation_file.write("  " + """
  #####################################################################################
  {}:
    unique_id: {}
    source: sensor.{}
    precision: 1
    data_points: {}
            """.format(
                metadata_compensation_dict["unique_id"],
                metadata_compensation_dict["unique_id"],
                metadata_compensation_dict["unique_id"].replace("compensation_sensor_", ""),
                "\n      - " + metadata_compensation_dict["compensation_curve"].replace("],[", "]\n      - ["),
            ).strip() + "\n")
        metadata_compensation_file.write("  " + """
  #####################################################################################
        """.strip() + "\n")
        print("Build generate script [homeassistant] entity compensation persisted to [{}]".format(metadata_compensation_path))

    # Build control YAML
    metadata_control_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "TPLink") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["connection_ip"].str.len() > 0)
        ]
    metadata_control_dicts = [row.dropna().to_dict() for index, row in metadata_control_df.iterrows()]
    metadata_control_dicts = sorted(metadata_control_dicts, key=lambda metadata_control_dict: metadata_control_dict['connection_ip'])
    metadata_control_path = abspath(join(DIR_ROOT, "src/main/resources/config/custom_packages/control.yaml"))
    with open(metadata_control_path, 'w') as metadata_control_file:
        metadata_control_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
fan:
  - platform: group
    name: Deck Fan
    unique_id: deck_fan
    entities:
      - fan.deck_east_fan
      - fan.deck_west_fan
#######################################################################################
tplink:
  discovery: false
  switch:
        """.strip() + "\n")
        for metadata_control_dict in metadata_control_dicts:
            metadata_control_file.write("    " + """
    - host: {}
            """.format(
                metadata_control_dict["connection_ip"]
            ).strip() + "\n")
        metadata_control_file.write("""
#######################################################################################
automation:
  - alias: "Electricity: Turn off Smart Plug LED"
    mode: single
    trigger:
      - platform: time
        at: "02:00:00"
    condition: [ ]
    action:
      - service: homeassistant.turn_off
        entity_id:
        """.strip() + "\n")
        for metadata_control_dict in metadata_control_dicts:
            metadata_control_file.write("          " + """
          - switch.{}_led
                """.format(
                metadata_control_dict["unique_id"]
            ).strip() + "\n")
        metadata_control_file.write("""
#######################################################################################
            """.strip() + "\n")

        # Build HAAS integration YAML
        metadata_haas_df = metadata_df[
            (metadata_df["index"] > 0) &
            (metadata_df["entity_status"] == "Enabled") &
            (metadata_df["entity_namespace"].str.len() > 0) &
            (metadata_df["unique_id"].str.len() > 0) &
            (metadata_df["entity_namespace"].str.len() > 0) &
            (metadata_df["google_aliases"].str.len() > 0) &
            (metadata_df["device_suggested_area"].str.len() > 0)
            ]
        metadata_haas_dicts = [row.dropna().to_dict() for index, row in metadata_haas_df.iterrows()]
        metadata_haas_path = abspath(join(DIR_ROOT, "src/main/resources/config/haas-entities.yaml"))
        with open(metadata_haas_path, 'w') as metadata_haas_file:
            metadata_haas_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
            """.strip() + "\n")
            for metadata_haas_dict in metadata_haas_dicts:
                metadata_haas_aliases = ["{}{}{}".format(metadata_haas_dict["device_suggested_area"],
                                                         "" if alias.startswith("s ") else " ", alias)
                                         for alias in metadata_haas_dict["google_aliases"].split(',')]
                metadata_haas_name = metadata_haas_aliases.pop(0)
                metadata_haas_room = metadata_haas_dict["device_suggested_area_override"] \
                    if "device_suggested_area_override" in metadata_haas_dict else metadata_haas_dict["device_suggested_area"]
                metadata_haas_file.write("""
{}.{}:
  name: {}
  aliases: {}
  room: {}
                    """.format(
                    metadata_haas_dict["entity_namespace"],
                    metadata_haas_dict["unique_id"],
                    metadata_haas_name,
                    metadata_haas_aliases,
                    metadata_haas_room,
                ).strip() + "\n")
            metadata_haas_file.write("""
#######################################################################################
                """.strip() + "\n")

    # Build media YAML
    metadata_media_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        ((metadata_df["device_via_device"] == "Google") | (metadata_df["device_via_device"] == "Sonos")) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["connection_ip"].str.len() > 0)
        ]
    metadata_media_google_dicts = [row.dropna().to_dict()
                                   for index, row in metadata_media_df.query("device_via_device == 'Google'").iterrows()]
    metadata_media_sonos_dicts = [row.dropna().to_dict()
                                  for index, row in metadata_media_df.query("device_via_device == 'Sonos'").iterrows()]
    metadata_media_path = abspath(join(DIR_ROOT, "src/main/resources/config/custom_packages/media.yaml"))
    with open(metadata_media_path, 'w') as metadata_media_file:
        metadata_media_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
        """.strip() + "\n")
        metadata_media_file.write("""
# NOTE: Use for populating the Google Cast UI integration 'known_hosts' field 
# cast:
#  known_hosts: {}
        """.format(
            ','.join(sorted(map(str, [metadata_media_dict['connection_ip'] for metadata_media_dict in metadata_media_google_dicts])))
        ).strip() + "\n")
        metadata_media_file.write("""
#######################################################################################
wake_on_lan:
# webostv:
#   host: 10.0.4.49
#   name: Lounge TV
#   customize:
#     sources:
#       - livetv
#       - youtube
#       - netflix
#       - hdmi1
automation:
  - id: media_lounge_tv_on
    alias: "Media: Turn on lounge TV"
    trigger:
      - platform: webostv.turn_on
        entity_id: media_player.lg_webos_smart_tv
    action:
      # wakeonlan -i 10.0.4.255 -p 9 4c:ba:d7:bf:94:d0 works!
      - service: wake_on_lan.send_magic_packet
        data:
          mac: 4c:ba:d7:bf:94:d0
          broadcast_address: 10.0.4.255
          broadcast_port: 9
sonos:
  media_player:
    hosts:
        """.strip() + "\n")
        for metadata_media_sonos_dict in \
                sorted(metadata_media_sonos_dicts, key=lambda metadata_media_sonos_dicts: metadata_media_sonos_dicts['connection_ip']):
            metadata_media_file.write("      " + """
      - {}
            """.format(
                metadata_media_sonos_dict['connection_ip']
            ).strip() + "\n")
        metadata_media_file.write("""      
#######################################################################################
            """.strip() + "\n")

        # Build security YAML
        metadata_lock_df = metadata_df[
            (metadata_df["index"] > 0) &
            (metadata_df["entity_status"] == "Enabled") &
            (metadata_df["entity_namespace"] == "lock") &
            (metadata_df["unique_id"].str.len() > 0)
            ]
        metadata_lock_dicts = [row.dropna().to_dict() for index, row in metadata_lock_df.iterrows()]
        metadata_contact_df = metadata_df[
            (metadata_df["index"] > 0) &
            (metadata_df["entity_status"] == "Enabled") &
            (metadata_df["device_model"] == "Contact Sensor") &
            (metadata_df["unique_id"].str.len() > 0)
            ]
        metadata_contact_dicts = [row.dropna().to_dict() for index, row in metadata_contact_df.iterrows()]
        metadata_locks_all_locked_template = " and ".join([
            "states('lock.{}') == 'locked'".format(metadata_lock_dict["unique_id"])
            for metadata_lock_dict in metadata_lock_dicts
        ])
        metadata_locks_some_locked_template = " or ".join([
            "states('lock.{}') == 'locked'".format(metadata_lock_dict["unique_id"])
            for metadata_lock_dict in metadata_lock_dicts
        ])
        metadata_locks_some_unlocked_template = " or ".join([
            "states('lock.{}') == 'unlocked'".format(metadata_lock_dict["unique_id"])
            for metadata_lock_dict in metadata_lock_dicts
        ])
        metadata_state_all_on_template = " and ".join([
            "states('binary_sensor.template_{}') == 'on'".format(metadata_lock_dict["unique_id"].replace("_lock", "_state"))
            for metadata_lock_dict in metadata_lock_dicts
        ])
        metadata_security_path = abspath(join(DIR_ROOT, "src/main/resources/config/custom_packages/security.yaml"))
        with open(metadata_security_path, 'w') as metadata_security_file:
            metadata_security_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
stream:
#######################################################################################
input_boolean:
  #####################################################################################
  home_security:
    name: Security
  home_security_triggered:
    name: Security triggered flag
    initial: false
            """.strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  {}:
    name: {} Security
               """.format(
                    metadata_lock_dict["unique_id"] + "_security",
                    metadata_lock_dict["unique_id"].replace("_", " ").title(),
                ).strip() + "\n")
            metadata_security_file.write("""
#######################################################################################
template:
  #####################################################################################
  - binary_sensor:
            """.strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_lock = metadata_lock_dict["unique_id"]
                metadata_contact = "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_sensor_contact_last")
                metadata_security_file.write("      " + """
      #################################################################################
      - unique_id: {}
        icon: >-
          {{% if states('binary_sensor.{}') == 'off' and states('lock.{}') == 'locked' %}}
            mdi:shield-lock
          {{% else %}}
            mdi:shield-lock-open
          {{% endif %}}
        state: >-
          {{% if states('binary_sensor.{}') == 'off' and states('lock.{}') == 'locked' %}}
            on
          {{% else %}}
            off
          {{% endif %}}
               """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_contact,
                    metadata_lock,
                    metadata_contact,
                    metadata_lock,
                ).strip() + "\n")
            for metadata_contact_dict in metadata_contact_dicts:
                metadata_security_file.write("      " + """
      #################################################################################
      - unique_id: {}
        device_class: door
        state: >-
          {{% if states('binary_sensor.{}') not in ['unavailable', 'unknown', 'none', 'n/a'] %}}
            {{{{ states('binary_sensor.{}') }}}}
          {{% else %}}
            {{{{ states('binary_sensor.{}') }}}}
          {{% endif %}}
                """.format(
                    metadata_contact_dict["unique_id"].replace("template_", ""),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_last", "").lower(),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_last", "").lower(),
                    metadata_contact_dict["unique_id"],
                ).strip() + "\n")
            metadata_security_file.write("  " + """
  #####################################################################################
  - sensor:
            """.strip() + "\n")
            for metadata_contact_dict in metadata_contact_dicts:
                metadata_security_file.write("      " + """
      #################################################################################
      - unique_id: {}
        device_class: battery
        state_class: measurement
        unit_of_measurement: "%"
        state: >-
          {{% if states('sensor.{}') not in ['unavailable', 'unknown', 'none', 'n/a'] %}}
            {{{{ states('sensor.{}') }}}}
          {{% else %}}
            {{{{ states('sensor.{}') }}}}
          {{% endif %}}
                """.format(
                    metadata_contact_dict["unique_id"].replace("contact", "battery").replace("template_", ""),
                    metadata_contact_dict["unique_id"].replace("contact", "battery").replace("template_", "").replace("_last", "").lower(),
                    metadata_contact_dict["unique_id"].replace("contact", "battery").replace("template_", "").replace("_last", "").lower(),
                    metadata_contact_dict["unique_id"].replace("contact", "battery"),
                ).strip() + "\n")
            metadata_security_file.write("""
#######################################################################################
automation:
  #####################################################################################
  - id: routine_home_security_check_on
    alias: "Routine: Attempt to put Home into Secure mode at regular intervals"
    mode: queued
    trigger:
      - platform: time_pattern
        minutes: "/15"
    condition: [ ]
    action:
      - if:
          - condition: template
            value_template: >-
              {{{{ states('input_boolean.home_security') == 'off' }}}}
        then:
          - service: input_boolean.turn_on
            entity_id: input_boolean.home_security
  #####################################################################################
  - id: routine_home_security_on
    alias: "Routine: Put Home into Secure mode"
    mode: queued
    trigger:
      - platform: state
        entity_id: input_boolean.home_security
        to: 'on'
    condition: [ ]
    action:
      - if:
          - condition: template
            value_template: >-
              {{{{ {} }}}}
        then:
          - service: input_boolean.turn_on
            entity_id: input_boolean.home_security_triggered
          - delay: '00:00:01'
          - service: input_boolean.turn_off
            entity_id: input_boolean.home_security
        else:
          - service: input_boolean.turn_off
            entity_id: input_boolean.home_security_triggered
      - service: input_boolean.turn_on
        entity_id:
            """.format(
                metadata_locks_some_unlocked_template
            ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("          " + """
          - input_boolean.{}                
                """.format(
                    metadata_lock_dict["unique_id"] + "_security",
                ).strip() + "\n")
            metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_home_security_off
    alias: "Routine: Take Home out of Secure mode"
    mode: queued
    trigger:
      - platform: state
        entity_id: input_boolean.home_security
        to: 'off'
    condition: [ ]
    action:
      - if:
          - condition: template
            value_template: >-
              {{{{ states('input_boolean.home_security_triggered') == 'on' }}}}
        then:
          - service: input_boolean.turn_off
            entity_id: input_boolean.home_security_triggered
        else:
          - service: input_boolean.turn_off
            entity_id:
            """.format(
                metadata_locks_some_locked_template,
            ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("              " + """
              - input_boolean.{}
                """.format(
                    metadata_lock_dict["unique_id"] + "_security",
                ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_all_on
    alias: "Routine: {} all on"
    mode: queued
    trigger:
      - platform: state
        entity_id: binary_sensor.{}
        to: 'on'
    condition: [ ]
    action:
      - if:
          - condition: template
            value_template: >-
              {{{{ {} }}}}
        then:
          - service: input_boolean.turn_on
            entity_id: input_boolean.home_security
                """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"].replace("_lock", "_state").replace("_", " ").title(),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_state_all_on_template
                ).strip() + "\n")
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_all_off
    alias: "Routine: {} all off"
    mode: queued
    trigger:
      - platform: state
        entity_id: binary_sensor.{}
        to: 'off'
    condition: [ ]
    action:
      - service: input_boolean.turn_on
        entity_id: input_boolean.home_security_triggered
      - service: input_boolean.turn_off
        entity_id: input_boolean.home_security
                """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"].replace("_lock", "_state").replace("_", " ").title(),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_security_on
    alias: "Routine: Put {} into Secure mode"
    mode: queued
    trigger:
      - platform: state
        entity_id: input_boolean.{}_security
        to: 'on'
    condition: [ ]
    action:
      - if:
          - condition: template
            value_template: >-
              {{{{ states('lock.{}') == 'unlocked' }}}}
        then:
          - delay: '00:00:01'
          - service: input_boolean.turn_off
            entity_id: input_boolean.{}_security
      - if:
          - condition: template
            value_template: >-
              {{{{ states('binary_sensor.{}') == 'off' and states('lock.{}') == 'unlocked' }}}}
        then:
          - service: lock.lock
            entity_id: lock.{}
                """.format(
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"].replace("_", " ").title(),
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_sensor_contact_last"),
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_security_off
    alias: "Routine: Take {} out of Secure mode"
    mode: queued
    trigger:
      - platform: state
        entity_id: input_boolean.{}_security
        to: 'off'
    condition: [ ]
    action:
      - if:
          - condition: template
            value_template: >-
              {{{{ states('lock.{}') == 'locked' }}}}
        then:
          - service: lock.unlock
            entity_id: lock.{}
                """.format(
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"].replace("_", " ").title(),
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                    metadata_lock_dict["unique_id"],
                ).strip() + "\n")
            for metadata_contact_dict in metadata_contact_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_on
    alias: "Routine: {} on"
    mode: queued
    trigger:
      - platform: state
        entity_id: binary_sensor.{}
        to: 'off'
    condition: [ ]
    action:
      - delay: '00:00:01'
      - if:
          - condition: template
            value_template: >-
              {{{{ states('binary_sensor.{}') == 'off' and states('lock.{}') == 'unlocked' }}}}
        then:
          - service: lock.lock
            entity_id: lock.{}
      - delay: '00:00:01'
      - if:
          - condition: template
            value_template: >-
              {{{{ states('binary_sensor.{}') == 'off' and states('lock.{}') == 'unlocked' }}}}
        then:
          - service: lock.lock
            entity_id: lock.{}
      - delay: '00:00:01'
      - if:
          - condition: template
            value_template: >-
              {{{{ states('binary_sensor.{}') == 'off' and states('lock.{}') == 'unlocked' }}}}
        then:
          - service: lock.lock
            entity_id: lock.{}
                """.format(
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"].replace("_", " ").title(),
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last", "_lock"),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last", "_lock"),
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last", "_lock"),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last", "_lock"),
                    metadata_contact_dict["unique_id"],
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last", "_lock"),
                    metadata_contact_dict["unique_id"].replace("template_", "").replace("_sensor_contact_last", "_lock"),
                ).strip() + "\n")
            for metadata_lock_dict in metadata_lock_dicts:
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_on
    alias: "Routine: {} on"
    mode: queued
    trigger:
      - platform: state
        entity_id: binary_sensor.{}
        to: 'on'
    condition: [ ]
    action:
      - service: input_boolean.turn_on
        entity_id: input_boolean.{}
                """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"].replace("_lock", "_state").replace("_", " ").title(),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"] + "_security",
                ).strip() + "\n")
                metadata_security_file.write("  " + """
  #####################################################################################
  - id: routine_{}_off
    alias: "Routine: {} off"
    mode: queued
    trigger:
      - platform: state
        entity_id: binary_sensor.{}
        to: 'off'
    condition: [ ]
    action:
      - service: input_boolean.turn_off
        entity_id: input_boolean.{}
                """.format(
                    metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"].replace("_lock", "_state").replace("_", " ").title(),
                    "template_" + metadata_lock_dict["unique_id"].replace("_lock", "_state"),
                    metadata_lock_dict["unique_id"] + "_security",
                ).strip() + "\n")
            metadata_security_file.write("""      
#######################################################################################
                """.strip() + "\n")

    # Build lighting YAML
    metadata_lighting_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        ((metadata_df["device_via_device"] == "Hue") | (metadata_df["device_via_device"] == "Phillips")) &
        ((metadata_df["entity_namespace"].str.len() > 0) & (metadata_df["entity_namespace"] == "light")) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["friendly_name"].str.len() > 0)
        ]
    metadata_lighting_dicts = [row.dropna().to_dict() for index, row in metadata_lighting_df.iterrows()]
    metadata_lighting_automations_dicts = {}
    for metadata_lighting_dict in metadata_lighting_dicts:
        if "linked_entity" in metadata_lighting_dict:
            if metadata_lighting_dict["linked_entity"] not in metadata_lighting_automations_dicts:
                metadata_lighting_automations_dicts[metadata_lighting_dict["linked_entity"]] = []
            metadata_lighting_automations_dicts[metadata_lighting_dict["linked_entity"]].append(metadata_lighting_dict)
    metadata_lighting_path = abspath(join(DIR_ROOT, "src/main/resources/config/custom_packages/lighting.yaml"))
    with open(metadata_lighting_path, 'w') as metadata_lighting_file:
        metadata_lighting_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
adaptive_lighting:
        """.strip() + "\n")
        for automation_name in metadata_lighting_automations_dicts:
            metadata_lighting_file.write("  " + """
  #####################################################################################
  - name: {}
    interval: 30
    min_brightness: {}
    max_brightness: 100
    min_color_temp: 2500
    max_color_temp: 5500
    only_once: false
    take_over_control: true
    detect_non_ha_changes: true
    lights:
        """.format(
                automation_name.replace("switch.adaptive_lighting_", ""),
                "100" if automation_name == "switch.adaptive_lighting_default" else "1"
            ).strip() + "\n")
            for metadata_lighting_group_dict in metadata_lighting_automations_dicts[automation_name]:
                metadata_lighting_file.write("      " + """
        - light.{}
                  """.format(
                    metadata_lighting_group_dict["unique_id"],
                ).strip() + "\n")
        metadata_lighting_file.write("  " + """
  #####################################################################################
input_boolean:
        """.strip() + "\n")
        for metadata_lighting_dict in metadata_lighting_dicts:
            metadata_lighting_file.write("  " + """
  #####################################################################################
  lighting_reset_adaptive_lighting_{}:
    name: {}
    initial: false
              """.format(
                metadata_lighting_dict["unique_id"],
                metadata_lighting_dict["friendly_name"],
            ).strip() + "\n")
        metadata_lighting_file.write("  " + """
  #####################################################################################
automation:
  #####################################################################################
  - id: lighting_sleep_adaptive_lighting
    alias: "Lighting: Sleep Adaptive Lighting"
    mode: single
    trigger:
      - platform: time
        at: "01:00:00"
    condition: [ ]
    action:
      ################################################################################
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_default
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_sleep_mode_default
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_color_default
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_brightness_default
      - service: adaptive_lighting.set_manual_control
        data:
          entity_id: switch.adaptive_lighting_default
          manual_control: false
      ################################################################################
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_bedroom
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_sleep_mode_bedroom
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_color_bedroom
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_brightness_bedroom
      - service: adaptive_lighting.set_manual_control
        data:
          entity_id: switch.adaptive_lighting_bedroom
          manual_control: false
      ################################################################################
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_night_light
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_sleep_mode_night_light
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_color_night_light
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_brightness_night_light
      - service: adaptive_lighting.set_manual_control
        data:
          entity_id: switch.adaptive_lighting_night_light
          manual_control: false
      ################################################################################
  - id: lighting_reset_adaptive_lighting
    alias: "Lighting: Reset Adaptive Lighting"
    mode: single
    trigger:
      - platform: time
        at: "05:00:00"
    condition: [ ]
    action:
      ################################################################################
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_default
      - service: switch.turn_off
        target:
          entity_id: switch.adaptive_lighting_sleep_mode_default
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_color_default
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_brightness_default
      - service: adaptive_lighting.set_manual_control
        data:
          entity_id: switch.adaptive_lighting_default
          manual_control: false
      ################################################################################
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_bedroom
      - service: switch.turn_off
        target:
          entity_id: switch.adaptive_lighting_sleep_mode_bedroom
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_color_bedroom
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_brightness_bedroom
      - service: adaptive_lighting.set_manual_control
        data:
          entity_id: switch.adaptive_lighting_bedroom
          manual_control: false
      ################################################################################
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_night_light
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_sleep_mode_night_light
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_color_night_light
      - service: switch.turn_on
        target:
          entity_id: switch.adaptive_lighting_adapt_brightness_night_light
      - service: adaptive_lighting.set_manual_control
        data:
          entity_id: switch.adaptive_lighting_night_light
          manual_control: false
      ################################################################################
        """.strip() + "\n")
        metadata_lighting_file.write("  " + """
  - id: lighting_reset_adaptive_lighting_announce
    alias: 'Lighting: Reset Adaptive Lighting on bulb announce'
    mode: single
    trigger:
      - platform: mqtt
        topic: zigbee/bridge/event
    condition:
      - condition: template
        value_template: '{{ trigger.payload_json.data.friendly_name | regex_search(" Bulb 1$") }}'
    action:
      ################################################################################
      - variables:
          light: '{{ "light." + (trigger.payload_json.data.friendly_name | regex_replace(" Bulb 1$") | replace(" ", "_") | lower) }}'
          light_reset: '{{ "input_boolean.lighting_reset_adaptive_lighting_" + (light | replace("light.", "")) }}'
      ################################################################################
      - if:
          - condition: template
            value_template: '{{ is_state(light_reset, "off") }}'
        then:
          - service: input_boolean.turn_on
            data_template:
              entity_id: '{{ light_reset }}'
        else:
          - service: light.turn_on
            data_template:
              color_temp: 366
              brightness_pct: 100
              entity_id: '{{ light }}'
        """.strip() + "\n")
        for metadata_lighting_dict in metadata_lighting_dicts:
            metadata_lighting_file.write("  " + """
  #####################################################################################
  - id: lighting_reset_adaptive_lighting_{}
    alias: "Lighting: Reset Adaptive Lighting on request of {}"
    trigger:
      - platform: state
        entity_id: input_boolean.lighting_reset_adaptive_lighting_{}
        from: 'off'
        to: 'on'
            """.format(
                metadata_lighting_dict["unique_id"],
                metadata_lighting_dict["friendly_name"],
                metadata_lighting_dict["unique_id"],
            ).strip() + "\n")
            reset_double_trigger_timeout = "'00:00:10'"
            if "linked_entity" in metadata_lighting_dict:
                metadata_lighting_file.write("    " + """
    action:
      - service: adaptive_lighting.set_manual_control
        data:
          entity_id: {}
          lights: light.{}
          manual_control: false
      - delay: {}
      - service: input_boolean.turn_off
        entity_id: input_boolean.lighting_reset_adaptive_lighting_{}
                """.format(
                    metadata_lighting_dict["linked_entity"],
                    metadata_lighting_dict["unique_id"],
                    reset_double_trigger_timeout,
                    metadata_lighting_dict["unique_id"],
                ).strip() + "\n")
            else:
                device_config = json.loads(metadata_lighting_dict["zigbee_device_config"])
                metadata_lighting_file.write("    " + """
    action:
      - service: light.turn_on
        data_template:
          color_temp: {}
          brightness_pct: {}
          entity_id: light.{}
      - delay: {}
      - service: input_boolean.turn_off
        entity_id: input_boolean.lighting_reset_adaptive_lighting_{}
                """.format(
                    device_config["color_temp_startup"] if "color_temp_startup" in device_config else 366,
                    int(device_config["hue_power_on_brightness"] / 254 * 100) if "hue_power_on_brightness" in device_config else 100,
                    metadata_lighting_dict["unique_id"],
                    reset_double_trigger_timeout,
                    metadata_lighting_dict["unique_id"],
                ).strip() + "\n")
        metadata_lighting_file.write("  " + """
  #####################################################################################
        """.strip() + "\n")
    print("Build generate script [homeassistant] entity lighting persisted to [{}]".format(metadata_lighting_path))

    # Diagnostics YAML
    metadata_diagnostic_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["unique_id"].str.contains("linkquality")) &
        (metadata_df["entity_group"] == "Diagnostics")
        ]
    metadata_diagnostic_dicts = [row.dropna().to_dict() for index, row in metadata_diagnostic_df.iterrows()]
    metadata_diagnostic_path = abspath(join(DIR_ROOT, "src/main/resources/config/custom_packages/diagnostics.yaml"))
    with open(metadata_diagnostic_path, 'w') as metadata_diagnostic_file:
        metadata_diagnostic_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
compensation:
  #####################################################################################
  weatherstation_console_battery_percent:
    unique_id: weatherstation_console_battery_percent
    source: sensor.weatherstation_console_battery_voltage
    precision: 1
    unit_of_measurement: "%"
    data_points:
      - [ 4.5, 100 ]
      - [ 3.0, 0 ]
#######################################################################################
template:
  #####################################################################################
  - sensor:
      #################################################################################
      - unique_id: weatherstation_console_battery_percent_int
        device_class: battery
        state_class: measurement
        unit_of_measurement: "%"
        state: >-
          {{ states('sensor.compensation_sensor_weatherstation_console_battery_voltage') | float(0) | int }}
      #################################################################################
      - unique_id: weatherstation_coms_signal_quality_percentage
        device_class: signal_strength
        state_class: measurement
        unit_of_measurement: "%"
        state: >-
          {{ states('sensor.weatherstation_coms_signal_quality') | int(0) }}
        """.strip() + "\n")
        for metadata_diagnostic_dict in metadata_diagnostic_dicts:
            metadata_diagnostic_file.write("      " + """
      #################################################################################
      - unique_id: {}
        device_class: signal_strength
        state_class: measurement
        unit_of_measurement: "%"
        state: >-
          {{{{ ((states('sensor.{}') | float(0)) / 255 * 100) | int(0) }}}}
              """.format(
                metadata_diagnostic_dict["unique_id"].replace("template_", ""),
                metadata_diagnostic_dict["unique_id"].replace("template_", "").replace("_percentage", ""),
            ).strip() + "\n")

        metadata_diagnostic_file.write("""
#######################################################################################
input_boolean:
  #####################################################################################
  network_refresh_zigbee_router_lqi:
    name: Refresh state
    initial: false
#######################################################################################
automation:
  #####################################################################################
  - id: network_refresh_zigbee_router_lqi_action_scheduled
    alias: "Network: Refresh Zigbee router network link qualities on schedule"
    trigger:
      - platform: time_pattern
        hours: "/1"
    action:
      - service: input_boolean.turn_on
        entity_id: input_boolean.network_refresh_zigbee_router_lqi
  #####################################################################################
  - id: network_refresh_zigbee_router_lqi_action
    alias: "Network: Refresh Zigbee router network link qualities"
    trigger:
      - platform: state
        entity_id: input_boolean.network_refresh_zigbee_router_lqi
        from: 'off'
        to: 'on'
    action:
        """.strip() + "\n")
        for metadata_diagnostic_dict in metadata_diagnostic_dicts:
            metadata_diagnostic_file.write("      " + """
      - service: mqtt.publish
        data:
          topic: "zigbee/{}/{}/set"
          payload: '{{"read":{{"attributes":["dateCode","modelId"],"cluster":"genBasic","options":{{}}}}}}'
      - delay: '00:00:01'
            """.format(
                metadata_diagnostic_dict["friendly_name"],
                "11" if "outlet" in metadata_diagnostic_dict["unique_id"] else "1",
            ).strip() + "\n")
        for metadata_diagnostic_dict in metadata_diagnostic_dicts:
            metadata_diagnostic_file.write("      " + """
      - delay: '00:00:01'
      - if:
          - condition: template
            value_template: >-
              {{{{ ((states('sensor.{}') | lower) in ['unavailable', 'unknown', 'none', 'n/a']) or
                    ((as_timestamp(now()) - as_timestamp(states('sensor.{}'))) > {}) }}}}
        then:
          - service: mqtt.publish
            data:
              topic: "zigbee/{}"
              payload: '{{"linkquality":0,"update":{{"update_available":false}}}}'
            """.format(
                metadata_diagnostic_dict["unique_id"].replace("template_", "").replace("linkquality_percentage", "last_seen"),
                metadata_diagnostic_dict["unique_id"].replace("template_", "").replace("linkquality_percentage", "last_seen"),
                len(metadata_diagnostic_dicts) + 5,
                metadata_diagnostic_dict["friendly_name"],
            ).strip() + "\n")
        metadata_diagnostic_file.write("      " + """
      - service: input_boolean.turn_off
        entity_id: input_boolean.network_refresh_zigbee_router_lqi
#######################################################################################
        """.strip() + "\n")

    # Build action YAML
    metadata_action_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Action") &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["friendly_name"].str.len() > 0) &
        (metadata_df["linked_entity"].str.len() > 0) &
        (metadata_df["linked_service"].str.len() > 0) &
        (metadata_df["icon"].str.len() > 0)
        ]
    metadata_action_dicts = [row.dropna().to_dict() for index, row in metadata_action_df.iterrows()]
    metadata_action_path = abspath(join(DIR_ROOT, "src/main/resources/config/custom_packages/actions.yaml"))
    with open(metadata_action_path, 'w') as metadata_action_file:
        metadata_action_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
ios:
  #####################################################################################
  actions:
        """.strip() + "\n")
        for metadata_action_dict in metadata_action_dicts:
            metadata_action_file.write("    " + """
    ###################################################################################
    - name: {}
      label:
        text: "{}"
      icon:
        icon: {}
              """.format(
                metadata_action_dict["unique_id"],
                metadata_action_dict["friendly_name"],
                metadata_action_dict["icon"],
            ).strip() + "\n")
        metadata_action_file.write("""
automation:
        """.strip() + "\n")
        for metadata_action_dict in metadata_action_dicts:
            metadata_action_file.write("  " + """
  #####################################################################################
  - alias: "Action: {}"
    trigger:
      - platform: event
        event_type: ios.action_fired
        event_data:
          actionName: "{}"
    action:
      - service: {}
        entity_id: {}
              """.format(
                metadata_action_dict["friendly_name"],
                metadata_action_dict["unique_id"],
                metadata_action_dict["linked_service"],
                metadata_action_dict["linked_entity"],
            ).strip() + "\n")
        metadata_action_file.write("""
#######################################################################################
            """.strip() + "\n")

    # Build lovelace YAML
    metadata_lovelace_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["friendly_name"].str.len() > 0) &
        (metadata_df["entity_domain"].str.len() > 0) &
        (metadata_df["entity_group"].str.len() > 0) &
        (metadata_df["haas_display_mode"].str.len() > 0)
        ]
    metadata_lovelace_dicts = [row.dropna().to_dict() for index, row in metadata_lovelace_df.iterrows()]
    metadata_lovelace_group_domain_dicts = OrderedDict()
    for metadata_lovelace_dict in metadata_lovelace_dicts:
        group = metadata_lovelace_dict["entity_group"]
        domain = metadata_lovelace_dict["entity_domain"]
        if group not in metadata_lovelace_group_domain_dicts:
            metadata_lovelace_group_domain_dicts[group] = OrderedDict()
        if domain not in metadata_lovelace_group_domain_dicts[group]:
            metadata_lovelace_group_domain_dicts[group][domain] = []
        metadata_lovelace_group_domain_dicts[group][domain].append(metadata_lovelace_dict)
    for group in metadata_lovelace_group_domain_dicts:
        metadata_lovelace_path = abspath(join(DIR_ROOT, "src/main/resources/config/ui-lovelace", group.lower() + ".yaml"))
        with open(metadata_lovelace_path, 'w') as metadata_lovelace_file:
            metadata_lovelace_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
            """.strip() + "\n")
            for domain in metadata_lovelace_group_domain_dicts[group]:
                metadata_lovelace_graph_dicts = []
                for metadata_lovelace_dict in metadata_lovelace_group_domain_dicts[group][domain]:
                    if metadata_lovelace_dict["haas_display_mode"] == "Graph":
                        metadata_lovelace_graph_dicts.append(metadata_lovelace_dict)
                if metadata_lovelace_graph_dicts:
                    metadata_lovelace_file.write("""
################################################################################
- type: custom:mini-graph-card
  name: {}{}
  font_size_header: 19
  aggregate_func: max
  hours_to_show: 24
  points_per_hour: 6
  line_width: 2
  tap_action: none
  show_state: true
  show_indicator: true
  show:
    extrema: true
    fill: false
  entities:
                    """.format(
                        domain,
                        ("\n  icon: " + metadata_lovelace_graph_dicts[0]["icon"]) if "icon" in metadata_lovelace_graph_dicts[0] else ""
                    ).strip() + "\n")
                    for metadata_lovelace_graph_dict in metadata_lovelace_graph_dicts:
                        metadata_lovelace_file.write("    " + ("""
    - entity: {}.{}
      name: {}
                        """.format(
                            metadata_lovelace_graph_dict["entity_namespace"],
                            metadata_lovelace_graph_dict["unique_id"],
                            metadata_lovelace_graph_dict["friendly_name"],
                        )).strip() + "\n")
                if metadata_lovelace_group_domain_dicts[group][domain]:
                    metadata_lovelace_first_display_mode = None
                    for metadata_lovelace_dict in metadata_lovelace_group_domain_dicts[group][domain]:
                        metadata_lovelace_current_display_mode = metadata_lovelace_dict["haas_display_mode"].split("_")[0]
                        if metadata_lovelace_current_display_mode != metadata_lovelace_first_display_mode:
                            metadata_lovelace_first_display_mode = metadata_lovelace_current_display_mode
                            metadata_lovelace_first_dict = metadata_lovelace_dict
                            metadata_lovelace_first_display_type = metadata_lovelace_first_dict["haas_display_type"] \
                                if "haas_display_type" in metadata_lovelace_first_dict else "entities"
                            if metadata_lovelace_first_display_type == "entities":
                                metadata_lovelace_file.write("""
################################################################################
- type: entities
                                """.strip() + "\n")
                                if not metadata_lovelace_graph_dicts:
                                    metadata_lovelace_file.write("  " + """
  title: {}
                                    """.format(
                                        domain
                                    ).strip() + "\n")
                                    if "NoToggle" in metadata_lovelace_first_dict["haas_display_mode"]:
                                        metadata_lovelace_file.write("  " + """
  show_header_toggle: false
                                        """.format(
                                            domain
                                        ).strip() + "\n")
                                metadata_lovelace_file.write("  " + """
  entities:
                                """.strip() + "\n")
                        if "haas_display_type" not in metadata_lovelace_dict or metadata_lovelace_dict["haas_display_type"] == "entities":
                            metadata_lovelace_file.write("    " + ("""
    - entity: {}.{}
      name: {}
                            """.format(
                                metadata_lovelace_dict["entity_namespace"],
                                metadata_lovelace_dict["unique_id"],
                                metadata_lovelace_dict["friendly_name"],
                            )).strip() + "\n")
                            if "icon" in metadata_lovelace_dict:
                                metadata_lovelace_file.write("      " + """
      icon: {}
                                """.format(
                                    metadata_lovelace_dict["icon"],
                                ).strip() + "\n")
                        elif metadata_lovelace_dict["haas_display_mode"] != "Break":
                            metadata_lovelace_file.write("""
################################################################################
- type: {}
  entity: {}.{}
                            """.format(
                                metadata_lovelace_first_display_type,
                                metadata_lovelace_dict["entity_namespace"],
                                metadata_lovelace_dict["unique_id"],
                            ).strip() + "\n")
                            if metadata_lovelace_first_display_type == "picture-entity":
                                metadata_lovelace_file.write("  " + """
  show_name: false
  show_state: false
  camera_view: live
                                """.strip() + "\n")
                        else:
                            metadata_lovelace_file.write("""
################################################################################
- type: {}
                            """.format(
                                metadata_lovelace_first_display_type,
                            ).strip() + "\n")
            metadata_lovelace_file.write("""
################################################################################
            """.strip() + "\n")
            print("Build generate script [homeassistant] entity group [{}] persisted to lovelace [{}]"
                  .format(group.lower(), metadata_lovelace_path))