"""
WARNING: This file is written by the build process, any manual edits will be lost!
"""

import hassapi as hass


class Health(hass.Hass):
    def initialize(self):
        self.register_endpoint(self.health, "health")
        self.log("Initialised")

    def health(self):
        return {"health": "OK"}, 200
