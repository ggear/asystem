import hassapi as hass

class HelloWorld(hass.Hass):
    def initialize(self):
        self.log("Hello from AppDaemon")
        self.log("You are now ready to run Apps!")