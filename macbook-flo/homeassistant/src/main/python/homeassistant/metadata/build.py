import glob
import os
import sys

DIR_MODULE_ROOT = os.path.abspath("{}/../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/*/*/".format("{}/../../../../../../..".format(os.path.dirname(os.path.realpath(__file__))))):
    if dir_module.split("/")[-2] == "anode":
        sys.path.insert(0, "{}/src/main/python".format(dir_module))
sys.path.insert(0, DIR_MODULE_ROOT)

from anode.metadata.build import load

if __name__ == "__main__":
    sensors = load(os.path.join(DIR_MODULE_ROOT, "../../../.env"))
    with open(DIR_MODULE_ROOT + "/../../main/resources/config/customize.yaml", "w") as file:
        for group in sensors:
            for domain in sensors[group]:
                for sensor in sensors[group][domain]:
                    file.write("""
sensor.{}:
  friendly_name: {}
            """.format(sensor[2], sensor[5]).strip() + "\n")
    print("Metadata script [homeassistant] customize saved")

    for group in sensors:
        with open(DIR_MODULE_ROOT + "/../../main/resources/config/ui-lovelace/{}.yaml".format(group), "w") as file:
            for domain in sensors[group]:
                file.write("""
- type: custom:mini-graph-card
  name: {}
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
                """.format(domain).strip() + "\n")
                for sensor in sensors[group][domain]:
                    file.write("    " + """
    - sensor.{}
                """.format(sensor[2]).strip() + "\n")
                file.write("""
- type: entities
  show_header_toggle: false
  entities:
            """.strip() + "\n")
                for sensor in sensors[group][domain]:
                    file.write("    " + """
    - entity: sensor.{}
                """.format(sensor[2]).strip() + "\n")
    print("Metadata script [homeassistant] lovelace saved")
