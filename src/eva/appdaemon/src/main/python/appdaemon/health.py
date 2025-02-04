import hassapi as hass


class Health(hass.Hass):

    def initialize(self):
        self.home_started = self.get_ad_api().get_entity("input_boolean.home_started", namespace="hass")
        self.register_endpoint(self.health, "health")
        self.log("Initialised")

    def health(self, body_json, url_args):
        return {"health": "OK" if self.home_started.is_state("on") else "Bad"}, 200
