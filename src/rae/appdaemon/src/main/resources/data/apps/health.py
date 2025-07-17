"""
WARNING: This file is written by the build process, any manual edits will be lost!
"""

import hassapi as hass


class Health(hass.Hass):

    def initialize(self):
        self.register_endpoint(self.health, "health")
        self.log("Initialised")

    def health(self, body_json, url_args):
        return {"health": ("OK" if self.get_state("input_boolean.home_started") == "on" else "Bad")}, 200
