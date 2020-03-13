from __future__ import print_function

import logging
import logging.config
import shutil
import sys
import time
import urlparse
from optparse import OptionParser

import yaml
from autobahn.twisted.resource import WebSocketResource
from autobahn.twisted.websocket import WebSocketServerFactory, WebSocketServerProtocol
from klein import Klein
from klein.resource import KleinResource
from mqtt.client import publisher
from mqtt.client.base import MQTTBaseProtocol
from mqtt.client.factory import MQTTFactory
from mqtt.error import MQTTStateError
from twisted.application.internet import ClientService, backoffPolicy
from twisted.internet import reactor
from twisted.internet import threads
from twisted.internet.defer import fail
from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import returnValue
from twisted.internet.defer import succeed
from twisted.internet.endpoints import clientFromString
from twisted.internet.task import LoopingCall
from twisted.web import client
from twisted.web.client import HTTPConnectionPool
from twisted.web.server import Site
from twisted.web.static import File

from application import *
from plugin import DATUM_QUEUE_LAST
from plugin import ModelPull
from plugin import Plugin

LOG_FORMAT = "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"

KEEPALIVE_DEFAULT_SECONDS = 3613

S3_REGION = "ap-southeast-2"
S3_BUCKET = "asystem-amodel"


# noinspection PyUnboundLocalVariable
class ANode:

    def __init__(self, core_reactor, options, config):
        log_timer = Log(logging.DEBUG).start()
        Log(logging.INFO).log("Service", "state", lambda: "[anode] initialising")
        self.core_reactor = core_reactor
        self.options = options
        self.config = config
        self.plugins = {}
        self.web_ws = WebWsFactory(u"ws://" + self.config["host"] + ":" + str(self.config["port"]), self)
        self.web_ws.protocol = WebWs
        self.web_rest = WebRest(self)
        self.web_pool = HTTPConnectionPool(reactor, persistent=True)
        self.publish_service = None
        self.publish = "publish_host" in self.config and len(self.config["publish_host"]) > 0 and \
                       "publish_port" in self.config and self.config["publish_port"] > 0
        if self.publish:
            access_key = os.environ["MQTT_ACCESS_KEY"] if "MQTT_ACCESS_KEY" in os.environ else None
            secret_key = os.environ["MQTT_SECRET_KEY"] if "MQTT_SECRET_KEY" in os.environ else None
            mqtt_client_string = clientFromString(reactor, "tcp:" + self.config["publish_host"] + ":" + str(self.config["publish_port"]))

            # TODO: Fix keepalive
            self.publish_service = MqttPublishService(mqtt_client_string, MQTTFactory(profile=MQTTFactory.PUBLISHER),
                                                      (self.config["publish_batch_seconds"] * 2) if (
                                                              "publish_batch_seconds" in self.config and self.config[
                                                          "publish_batch_seconds"] > 0) else
                                                      KEEPALIVE_DEFAULT_SECONDS, access_key, secret_key)
            self.publish_service.startService()

        def looping_call(loop_function, loop_seconds):
            loop_call = LoopingCall(loop_function)
            loop_call.clock = self.core_reactor
            loop_call.start(loop_seconds)

        if "model_pull_seconds" in self.config and self.config["model_pull_seconds"] > 0:
            model_pull = ModelPull(self, "pullmodel", {
                "pool": self.web_pool, "db_dir": self.options.db_dir,
                "model_pull_region": self.config["model_pull_region"] if "model_pull_region" in self.config else S3_REGION,
                "model_pull_bucket": (self.config["model_pull_bucket"] if "model_pull_bucket" in self.config else S3_BUCKET) + (
                    self.config["model_pull_bucket_snapshot"] if ("model_pull_bucket_snapshot" in self.config and
                                                                  APP_VERSION.endswith("-SNAPSHOT")) else "")}, self.core_reactor)
            looping_call(model_pull.poll, self.config["model_pull_seconds"])
        for plugin_name in self.config["plugin"]:
            self.config["plugin"][plugin_name]["pool"] = self.web_pool
            self.config["plugin"][plugin_name]["db_dir"] = self.options.db_dir
            if self.publish_service is not None:
                self.config["plugin"][plugin_name]["publish_service"] = self.publish_service
            if "publish_status_topic" in self.config:
                self.config["plugin"][plugin_name]["publish_status_topic"] = self.config["publish_status_topic"]
            if "publish_push_data_topic" in self.config:
                self.config["plugin"][plugin_name]["publish_push_data_topic"] = self.config["publish_push_data_topic"]
            if "publish_push_metadata_topic" in self.config:
                self.config["plugin"][plugin_name]["publish_push_metadata_topic"] = self.config["publish_push_metadata_topic"]
            if "publish_batch_datum_topic" in self.config:
                self.config["plugin"][plugin_name]["publish_batch_datum_topic"] = self.config["publish_batch_datum_topic"]
            self.plugins[plugin_name] = Plugin.get(self, plugin_name, self.config["plugin"][plugin_name], self.core_reactor)
            if "poll_seconds" in self.config["plugin"][plugin_name] and self.config["plugin"][plugin_name]["poll_seconds"] > 0:
                looping_call(self.plugins[plugin_name].poll, self.config["plugin"][plugin_name]["poll_seconds"])
            if "repeat_seconds" in self.config["plugin"][plugin_name] and self.config["plugin"][plugin_name]["repeat_seconds"] > 0:
                looping_call(self.plugins[plugin_name].repeat, self.config["plugin"][plugin_name]["repeat_seconds"])
        for plugin in self.plugins.itervalues():
            if "history_partition_seconds" in self.config["plugin"][plugin.name] and \
                    self.config["plugin"][plugin.name]["history_partition_seconds"] > 0 and \
                    "repeat_seconds" in self.config["plugin"][plugin_name] and \
                    self.config["plugin"][plugin_name]["repeat_seconds"] >= 0:
                time_current = plugin.get_time()
                time_partition = self.config["plugin"][plugin.name]["history_partition_seconds"]
                time_partition_next = time_partition - (time_current - plugin.get_time_period(time_current, time_partition))
                plugin_partitioncall = LoopingCall(self.plugins[plugin.name].repeat, force=True)
                plugin_partitioncall.clock = self.core_reactor
                self.core_reactor.callLater(time_partition_next,
                                            lambda _plugin_partitioncall, _time_partition: _plugin_partitioncall.start(_time_partition),
                                            plugin_partitioncall, time_partition)
        if self.publish and "publish_batch_seconds" in self.config and self.config["publish_batch_seconds"] > 0:
            looping_call(self.publish_datums, self.config["publish_batch_seconds"])
        if "save_seconds" in self.config and self.config["save_seconds"] > 0:
            looping_call(self.store_state, self.config["save_seconds"])
        log_timer.log("Service", "timer", lambda: "[anode] initialised", context=self.__init__)

    def get_plugin(self, plugin):
        return self.plugins[plugin] if plugin in self.plugins else None

    def get_datums(self, datum_filter, datums=None):
        datums_filtered = {}
        if datums is None:
            for plugin_name, plugin in self.plugins.items():
                plugin.datums_filter_get(datums_filtered, datum_filter)
        else:
            Plugin.datums_filter(datums_filtered, datum_filter, datums)
        return datums_filtered

    def put_datums(self, datum_filter, data):
        if "sources" in datum_filter:
            for source in datum_filter["sources"]:
                if source in self.plugins:
                    self.plugins[source].push(data, datum_filter["targets"] if "targets" in datum_filter else None)

    def push_datums(self, datums):
        self.web_ws.push(datums)

    def publish_datums(self):
        for plugin in self.plugins.values():
            plugin.publish()

    def store_state(self):
        state_dir = os.path.join(self.options.db_dir, "anode")
        state_last_dir = os.path.join(self.options.db_dir, "anode.last")
        if os.path.exists(state_dir):
            if os.path.exists(state_last_dir):
                shutil.rmtree(state_last_dir)
            os.rename(state_dir, state_last_dir)
        for plugin in self.plugins.values():
            plugin.datums_store()

    def load_state(self):
        for plugin in self.plugins.values():
            plugin.datums_load()

    def start_server(self):
        log_timer = Log(logging.DEBUG).start()
        Log(logging.INFO).log("Service", "state", lambda: "[anode] starting")
        web_root = File(os.path.dirname(__file__) + "/web")
        web_root.putChild(b"ws", WebSocketResource(self.web_ws))
        web_root.putChild(u"rest", KleinResource(self.web_rest.server))
        web = Site(web_root, logPath="/dev/null")
        web.noisy = False
        self.core_reactor.addSystemEventTrigger("after", "shutdown", self.stop_server)
        self.core_reactor.listenTCP(self.config["port"], web)
        log_timer.log("Service", "timer", lambda: "[anode] started", context=self.start_server)
        self.core_reactor.run()

    def stop_server(self):
        log_timer = Log(logging.DEBUG).start()
        Log(logging.INFO).log("Service", "state", lambda: "[anode] stopping")
        if "save_on_exit" in self.config: self.store_state()
        log_timer.log("Service", "timer", lambda: "[anode] stopped", context=self.stop_server)
        return succeed(None)


# noinspection PyPep8Naming
class MqttPublishService(ClientService):
    def __init__(self, endpoint, factory, keepalive, access_key=None, secret_key=None):
        self.keepalive = keepalive
        self.protocol = None
        self.access_key = access_key
        self.secret_key = secret_key
        ClientService.__init__(self, endpoint, factory, retryPolicy=backoffPolicy(maxDelay=keepalive))

    def startService(self):
        self.whenConnected().addCallback(self.makeConnection)
        ClientService.startService(self)

    @inlineCallbacks
    def makeConnection(self, protocol):
        self.protocol = protocol
        self.protocol.onDisconnection = self.onDisconnection
        self.protocol.setWindowSize(1)
        self.protocol.setTimeout(MQTTBaseProtocol.TIMEOUT_MAX_INITIAL)
        try:
            yield self.protocol.connect("TwistedMQTT", username=self.access_key, password=self.secret_key,
                                        keepalive=self.keepalive, cleanStart=True)
        except Exception as exception:
            Log(logging.ERROR).log("Interface", "state", lambda: "[mqtt] connection error [{}]:\n".format(exception), exception)
        else:
            Log(logging.DEBUG).log("Interface", "state", lambda: "[mqtt] connection opened")

    def onDisconnection(self, reason):
        Log(logging.WARN).log("Interface", "state", lambda: "[mqtt] connection lost [{}]".format(reason))
        self.whenConnected().addCallback(self.makeConnection)

    def isConnected(self):
        return self.protocol is not None and isinstance(self.protocol.state, publisher.ConnectedState)

    def publishMessage(self, topic, message, queue, qos, retain, on_failure):
        Log(logging.DEBUG).log("Interface", "publish", lambda: "[mqtt] message of size [{}]".format(len(message)))
        if self.isConnected():
            deferred = self.protocol.publish(topic, bytearray(message), qos, retain)
            deferred.addErrback(on_failure, message, queue)
            return deferred
        else:
            on_failure(MQTTStateError("Attempt to execute publish() operation while not connected",
                                      self.protocol.state if self.protocol is not None else None), message, queue)
            return fail(None)


class WebWsFactory(WebSocketServerFactory):
    def __init__(self, url, anode):
        super(WebWsFactory, self).__init__(url)
        self.anode = anode
        self.ws_clients = []

    # noinspection PyShadowingNames
    def register(self, client):
        if client not in self.ws_clients:
            self.ws_clients.append(client)
            Log(logging.DEBUG).log("Interface", "state", lambda: "[ws] client registered [{}]".format(client.peer))

    def push(self, datums=None):
        for ws_client in self.ws_clients:
            ws_client.push(datums)

    def deregister(self, ws_client):
        if ws_client in self.ws_clients:
            self.ws_clients.remove(ws_client)
            Log(logging.DEBUG).log("Interface", "state", lambda: "[ws] client deregistered [{}]".format(ws_client.peer))


# noinspection PyPep8Naming
class WebWs(WebSocketServerProtocol):
    def __init__(self):
        super(WebWs, self).__init__()
        self.datum_filter = None

    def onConnect(self, request):
        self.datum_filter = WebUtil.parse_query(request.params, "latin-1")
        self.datum_filter["scope"] = [DATUM_QUEUE_LAST]
        Log(logging.DEBUG).log("Interface", "state", lambda: "[ws] connection request")

    def onOpen(self):
        Log(logging.DEBUG).log("Interface", "state", lambda: "[ws] connection opened")
        self.factory.register(self)
        self.push()

    def push(self, datums=None):
        log_timer = Log(logging.DEBUG).start()
        datums = self.factory.anode.get_datums(self.datum_filter, datums)
        Log(logging.DEBUG).log("Interface", "request", lambda: "[ws] push with filter [{}] and [{}] datums".format(
            self.datum_filter, 0 if datums is None else sum(len(datums_values) for datums_values in datums.values())))
        for datum in Plugin.datum_to_format(datums, "json")["json"]:
            self.sendMessage(datum, False)
        log_timer.log("Interface", "timer", lambda: "[ws]", context=self.push)

    def onClose(self, wasClean, code, reason):
        Log(logging.DEBUG).log("Interface", "state", lambda: "[ws] connection lost")
        self.factory.deregister(self)


# noinspection PyPep8Naming
class WebRest:
    server = Klein()

    def __init__(self, anode):
        self.anode = anode

    @server.route("/", methods=["POST"])
    def post(self, request):
        log_timer = Log(logging.DEBUG).start()
        datum_filter = WebUtil.parse_query(urlparse.parse_qs(urlparse.urlparse(request.uri).query))
        Log(logging.DEBUG).log("Interface", "request", lambda: "[rest] post with filter [{}]".format(datum_filter))
        self.anode.put_datums(datum_filter, request.content.read())
        log_timer.log("Interface", "timer", lambda: "[rest]", context=self.post)
        return succeed(None)

    @server.route("/")
    @inlineCallbacks
    def get(self, request):
        log_timer = Log(logging.DEBUG).start()
        datum_filter = WebUtil.parse_query(urlparse.parse_qs(urlparse.urlparse(request.uri).query))
        datums = self.anode.get_datums(datum_filter)
        Log(logging.DEBUG).log("Interface", "request", lambda: "[rest] get with filter [{}] and [{}] datums"
                               .format(datum_filter, sum(len(datums_values) for datums_values in datums.values())))
        datum_format = "json" if "format" not in datum_filter else datum_filter["format"][0]
        datums_formatted = yield threads.deferToThread(Plugin.datums_to_format, datums, datum_format, datum_filter, True)
        request.setHeader("Content-Disposition", "attachment; filename=anode." + datum_format)
        request.setHeader("Content-Type",
                          "text/csv" if datum_format == "csv" else (
                              "application/json" if datum_format == "json" else ("image/svg+xml" if datum_format == "svg" else (
                                      "application" + datum_format))))
        log_timer.log("Interface", "timer", lambda: "[rest]", context=self.get)
        returnValue(datums_formatted)


class WebUtil:
    def __init__(self):
        pass

    @staticmethod
    def parse_query(query_dict, encoding=None):
        query_dict_parsed = {}
        for query_key in query_dict:
            query_key_values = []
            for query_key_value in query_dict[query_key]:
                query_key_values.append(query_key_value.encode(encoding) if encoding is not None else query_key_value)
            query_dict_parsed[query_key] = query_key_values
        return query_dict_parsed


class Log:
    def __init__(self, level=logging.INFO):
        self.level = level
        self.time_tracked = False
        self.time_real = 0
        self.time_user = 0
        self.time_real_start = None
        self.time_user_start = None

    # noinspection PyArgumentList, PyProtectedMember
    @staticmethod
    def configure(verbose, quiet, shutup):
        client._HTTP11ClientFactory.noisy = False
        if not logging.getLogger().handlers:
            logging_handler = logging.StreamHandler(sys.stdout)
            logging_handler.setFormatter(logging.Formatter(LOG_FORMAT))
            logging.getLogger().addHandler(logging_handler)
            if verbose:
                from twisted.logger import (
                    LogLevel, globalLogBeginner, textFileLogObserver,
                    FilteringLogObserver, LogLevelFilterPredicate)
                twisted_log_fitler = LogLevelFilterPredicate(defaultLogLevel=LogLevel.warn)
                twisted_log_fitler.setLogLevelForNamespace(namespace="stdout", level=LogLevel.critical)
                twisted_log_fitler.setLogLevelForNamespace(namespace="twisted", level=LogLevel.warn)
                twisted_log_fitler.setLogLevelForNamespace(namespace="mqtt", level=LogLevel.warn)
                globalLogBeginner.beginLoggingTo([FilteringLogObserver(observer=textFileLogObserver(sys.stdout),
                                                                       predicates=[twisted_log_fitler])], redirectStandardIO=False)
        logging.getLogger().setLevel(logging.FATAL if shutup else logging.ERROR if quiet else logging.DEBUG if verbose else logging.INFO)

    def start(self):
        if logging.getLogger().isEnabledFor(self.level):
            if self.time_user_start is not None:
                raise Exception("Log already started, cannot start")
            self.time_user_start = time.time()
            if self.time_real_start is None:
                self.time_real_start = self.time_user_start
        return self

    # noinspection PyUnboundLocalVariable
    def pause(self, stop=False):
        if logging.getLogger().isEnabledFor(self.level):
            if self.time_user_start is None:
                raise Exception("Log not started, cannot pause")
            time_now = time.time()
            self.time_user += int((time_now - self.time_user_start) * 1000)
            if stop:
                self.time_real = int((time_now - self.time_real_start) * 1000)
            self.time_tracked = True
            self.time_user_start = None
        return self

    def stop(self):
        if logging.getLogger().isEnabledFor(self.level):
            if self.time_user_start is not None:
                self.pause(True)
        return self

    def log(self, source, intonation, message, exception=None, context=None, off_thread=False):
        if logging.getLogger().isEnabledFor(self.level):
            self.stop()
            if self.level == logging.DEBUG:
                logger = logging.getLogger().debug
            elif self.level == logging.INFO:
                logger = logging.getLogger().info
            elif self.level == logging.WARN:
                logger = logging.getLogger().warning
            elif self.level == logging.ERROR:
                logger = logging.getLogger().error
            else:
                raise Exception("Unknown logging level [{}]".format(self.level))
            if not hasattr(message, '__call__'):
                raise Exception("Non callable object [{}] passed as message".format(message))
            logger(" ".join(filter(None, [".".join([source, intonation]), message(),
                                          "" if context is None else "in [{}]".format(context.__name__),
                                          "" if not self.time_tracked else ("off-thread" if off_thread else "on-thread"),
                                          "" if not self.time_tracked else "real [{}] ms".format(self.time_real),
                                          "" if not self.time_tracked else "user [{}] ms".format(self.time_user)])))
            if exception is not None:
                logging.exception(exception)


def main(core_reactor=reactor):
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="config", default="/etc/anode/anode.yaml", help="config FILE", metavar="FILE")
    parser.add_option("-d", "--db-dir", dest="db_dir", default="/etc/anode/", help="config FILE", metavar="FILE")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="noisy output to stdout")
    parser.add_option("-q", "--quiet", action="store_true", dest="quiet", default=False, help="suppress most output to stdout")
    parser.add_option("-s", "--shutup", action="store_true", dest="shutup", default=False, help="suppress all output to stdout")
    (options, args) = parser.parse_args()
    Log.configure(options.verbose, options.quiet, options.shutup)
    with open(options.config, "r") as stream:
        config = yaml.load(stream)
    if not os.path.isdir(options.db_dir):
        raise IOError("No such directory: {}".format(options.db_dir))
    anode = ANode(core_reactor, options, config)
    if core_reactor == reactor:
        anode.start_server()
    return anode
