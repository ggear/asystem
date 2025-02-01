import hassapi as hass
import json

class HelloWorld(hass.Hass):
    def initialize(self):
        self.register_endpoint(self.my_callback, "hello")
        self.log("Hello from AppDaemon")
        self.log("You are now ready to run Apps!")

    def my_callback(self, json_obj, cb_args):
        self.log(json_obj)
        response = {"message": "Received: {}".format(json_obj)}
        return response, 200
