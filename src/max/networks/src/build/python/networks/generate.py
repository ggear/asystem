from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    write_healthcheck()

    # Build MQTT schema
    metadata_networks_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Networks") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ].copy()
    write_entity_metadata(metadata_networks_df,
                          topic_glob_discovery="homeassistant/+/networks/+/config",
                          topic_glob_data="networks/data/#",
                          schema_state="""
{
  "timestamp": <number>,
  "ok": <true|false>,
  "status": <fit|sick|dead>,
  "score": <0-100>
}
                              """, schema_command="""
<ON|OFF>
                              """, schema_availability="""
<online|offline>
                              """)
