import json
import os
from os.path import *

import pandas as pd

from asystem import load_bootstrap_entities
from asystem import load_bootstrap_env
from asystem import write_container_healthchecks
from asystem import write_schema_broker

pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    env = load_bootstrap_env(DIR_ROOT)
    write_container_healthchecks()
    metadata_df = load_bootstrap_entities()

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

    write_schema_broker(metadata_tasmota_df,
                        topic_glob_discovery="homeassistant/+/tasmota/#",
                        topic_glob_data="tasmota/#",
                        schema_state={
                              "*/stat/POWER": """
<ON|OFF>
                              """,
                              "*/tele/SENSOR": """
{
  "Time": "<text>",
  "SI7021": {
    "Temperature": <number>,
    "Humidity": <number>
  },
  "DS18B20": {
    "Temperature": <number>
  },
  "ENERGY": {
    "Power": <number>,
    "Total": <number>
  }
}
                              """,
                          }, schema_command="""
<ON|OFF|TOGGLE>
                          """, schema_availability="""
<Online|Offline>
                          """)

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
                        "mqtt_port": env["VERNEMQ_API_PORT"],
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
                    os.system(
                        "netcat -zw 1 {} 80 2>/dev/null && decode-config.py -s {} -o {}-backup.json --json-indent 2".format(
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
                    tasmota_config_file.write("\tprintf '\\n'\n")
                    tasmota_config_file.write(
                        "\tTIMEOUT=30; ELAPSED=0; printf 'Waiting for device to come up .' && sleep 1 && printf '.' && sleep 1 && printf '.' && "
                        "while ! (echo >/dev/tcp/{}/80) 2>/dev/null; do printf '.' && sleep 1 && ELAPSED=$((ELAPSED + 1)) && "
                        "if [ \"$ELAPSED\" -ge \"$TIMEOUT\" ]; then printf ' abort\\n' && exit 1; fi; done && printf ' done\\n'\n".format(
                            metadata_tasmota_dict["connection_ip"],
                        )
                    )
                tasmota_config_file.write(
                    "else\n\techo 'Skipping config for device [{}] at [http://{}/?] given it is unresponsive'\n".format(
                        metadata_tasmota_dict["unique_id"],
                        metadata_tasmota_dict["connection_ip"],
                    ))
                tasmota_config_file.write("fi\necho ''\n")
    print("Build generate script [tasmota] entity metadata persisted to [{}]".format(tasmota_config_path))

    tasmota_devices = {}
    for metadata_tasmota_dict in metadata_tasmota_dicts:
        if metadata_tasmota_dict["entity_namespace"] != "sensor" and "connection_ip" in metadata_tasmota_dict:
            tasmota_devices[metadata_tasmota_dict["unique_id"]] = (
                metadata_tasmota_dict["device_name"], metadata_tasmota_dict["connection_ip"])
    tasmota_html_path = join(DIR_ROOT, "src/main/resources/image/html/index.html")
    os.makedirs(dirname(tasmota_html_path), exist_ok=True)
    with open(tasmota_html_path, "wt") as tasmota_html_file:
        tasmota_html_file.write("""
<!doctype html>
<html lang="en" data-theme="ares">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tasmota</title>
<link rel="stylesheet" href="ares.css">
<style>
:root { --background: oklch(0.14 0.02 250); --foreground: oklch(0.94 0.01 250); }
body { background: var(--background); color: var(--foreground); margin: 0; padding: 2rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.95rem; }
h1 { margin: 0 0 1.5rem; font-size: 1.1rem; font-weight: 500; letter-spacing: 0.35em;
  text-transform: uppercase; color: var(--primary); text-shadow: 0 0 12px var(--glow-muted); }
ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.5rem;
  grid-template-columns: repeat(auto-fill, minmax(22rem, 1fr)); }
li { display: flex; align-items: center; gap: 0.75rem; padding: 0.7rem 0.9rem;
  background: var(--input); border: 1px solid var(--border); border-radius: 2px; }
a { color: var(--foreground); text-decoration: none; flex: 1; }
a:hover { color: var(--primary); text-shadow: 0 0 10px var(--glow-muted); }
.ip { color: var(--muted-foreground); font-size: 0.8rem; }
.status { color: var(--muted-foreground); font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; }
.status[data-state="online"] { color: var(--primary); text-shadow: 0 0 10px var(--glow); }
.status[data-state="offline"] { color: var(--secondary); }
</style>
</head>
<body>
<h1>Tasmota</h1>
<ul>
        """.strip() + "\n")
        for tasmota_device_id in sorted(tasmota_devices, key=lambda id: tasmota_devices[id][0]):
            tasmota_device_name, tasmota_device_ip = tasmota_devices[tasmota_device_id]
            tasmota_html_file.write('<li><span class="status" id="{}">unknown</span>'
                                    '<a href="http://{}/">{}</a><span class="ip">{}</span></li>\n'.format(
                tasmota_device_id, tasmota_device_ip, tasmota_device_name, tasmota_device_ip))
        tasmota_html_file.write("""
</ul>
<script src="mqtt.min.js"></script>
<script>
const client = mqtt.connect((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/mqtt");
client.on("connect", () => client.subscribe("tasmota/device/+/tele/LWT"));
client.on("message", (topic, payload) => {
  const status = document.getElementById(topic.split("/")[2]);
  if (!status) return;
  status.textContent = payload.toString().toLowerCase();
  status.dataset.state = payload.toString().toLowerCase();
});
client.on("error", () => document.querySelectorAll(".status").forEach((status) => {
  status.textContent = "unknown";
  delete status.dataset.state;
}));
</script>
</body>
</html>
        """.strip() + "\n")
    print("Build generate script [tasmota] device index persisted to [{}]".format(tasmota_html_path))
