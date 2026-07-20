from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    write_healthcheck()

    # Build MQTT schema
    metadata_tempstat_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "TempStat") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ].copy()
    metadata_tempstat_df["availability_topic"] = "tempstat/macmini-may/status"
    write_entity_metadata(metadata_tempstat_df,
                          topics_path="tempstat",
                          topic_glob_discovery="homeassistant/+/tempstat/+/config",
                          topic_glob_data="tempstat/+/data",
                          schema_state="""
{
  "timestamp": "<text>",
  "period_ms": <number>,
  "samples": {
    "utility_temperature_celsius": <number>,
    "rack_top_temperature_celsius": <number>,
    "rack_bottom_temperature_celsius": <number>
  }
}
                          """, schema_command="""
<start|stop|restart>
                          """, schema_availability="""
<online|offline>
                          """)
