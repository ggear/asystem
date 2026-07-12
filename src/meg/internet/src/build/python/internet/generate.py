from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    write_healthcheck()

    # Build MQTT schema
    metadata_publish_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Internet") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0)
        ]
    write_entity_metadata(metadata_publish_df,
                          topic_glob_discovery="homeassistant/+/internet/#",
                          topic_glob_data="telegraf/+/internet/#",
                          schema_state="""
{
  "metrics": [
    {
      "name": "<text>",
      "tags": {
        "metric": "<ping|download|upload>"
      },
      "fields": {
        "<text>": <number>
      },
      "timestamp": <number>
    }
  ]
}
                          """)
