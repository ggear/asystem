import hassapi as hass


class HelloWorld(hass.Hass):
    def initialize(self):
        self.register_endpoint(self.my_callback, "hello")
        self.log("Hello from AppDaemon")
        self.log("You are now ready to run Apps!")

    def my_callback(self, json_obj, cb_args):
        self.log(json_obj)
        response = {"message": "Hello World"}
        return response, 200
