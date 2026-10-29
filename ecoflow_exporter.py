import logging as log
import sys
import os
import signal
import ssl
import time
import json
import re
import base64
import uuid
import random
from queue import Queue
from threading import Timer
import requests
import paho.mqtt.client as mqtt
from prometheus_client import start_http_server, REGISTRY, Gauge, Counter


# Arrays of bytes that are actually strings, e.g. bmsMaster.packSn: [48, 48, ...] or bmsMaster.hwEdition: [86, 48, 46, 48]
NON_NUMERIC_ARRAY_KEYS = re.compile(r"(Sn|Edition)$")


class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


class EcoflowMetricException(Exception):
    pass


class EcoflowAuthentication:
    def __init__(self, ecoflow_username, ecoflow_password, ecoflow_api_host, device_sn):
        self.ecoflow_username = ecoflow_username
        self.ecoflow_password = ecoflow_password
        self.ecoflow_api_host = ecoflow_api_host
        self.device_sn = device_sn
        self.mqtt_url = "mqtt.ecoflow.com"
        self.mqtt_port = 8883
        self.mqtt_username = None
        self.mqtt_password = None
        self.mqtt_client_id = None
        self.user_id = None
        self.authorize()

    def authorize(self):
        url = f"https://{self.ecoflow_api_host}/auth/login"
        headers = {"lang": "en_US", "content-type": "application/json"}
        data = {"email": self.ecoflow_username,
                "password": base64.b64encode(self.ecoflow_password.encode()).decode(),
                "scene": "IOT_APP",
                "userType": "ECOFLOW"}

        log.info(f"Login to EcoFlow API {url}")
        request = requests.post(url, json=data, headers=headers, timeout=30)
        response = self.get_json_response(request)

        try:
            token = response["data"]["token"]
            user_id = response["data"]["user"]["userId"]
            user_name = response["data"]["user"]["name"]
        except KeyError as key:
            raise Exception(f"Failed to extract key {key} from response: {response}")

        log.info(f"Successfully logged in: {user_name}")

        url = f"https://{self.ecoflow_api_host}/iot-auth/app/certification"
        headers = {"lang": "en_US", "authorization": f"Bearer {token}"}
        data = {"userId": user_id}

        log.info(f"Requesting IoT MQTT credentials {url}")
        request = requests.get(url, data=data, headers=headers, timeout=30)
        response = self.get_json_response(request)

        try:
            self.mqtt_url = response["data"]["url"]
            self.mqtt_port = int(response["data"]["port"])
            self.mqtt_username = response["data"]["certificateAccount"]
            self.mqtt_password = response["data"]["certificatePassword"]
            # EcoFlow limits the number of distinct client ids per account per day, so keep it stable across restarts.
            # The device serial number makes it unique for every exporter instance of the same account
            client_uuid = uuid.uuid5(uuid.NAMESPACE_OID, f"{user_id}_{self.device_sn}")
            self.mqtt_client_id = f"ANDROID_{str(client_uuid).upper()}_{user_id}"
            self.user_id = user_id
        except KeyError as key:
            raise Exception(f"Failed to extract key {key} from {response}")

        log.info(f"Successfully extracted account: {self.mqtt_username}")

    def get_json_response(self, request):
        if request.status_code != 200:
            raise Exception(f"Got HTTP status code {request.status_code}: {request.text}")

        try:
            response = json.loads(request.text)
            response_message = response["message"]
        except KeyError as key:
            raise Exception(f"Failed to extract key {key} from {response}")
        except Exception as error:
            raise Exception(f"Failed to parse response: {request.text} Error: {error}")

        if response_message.lower() != "success":
            raise Exception(f"{response_message}")

        return response


class EcoflowMQTT():

    def __init__(self, message_queue, device_sn, user_id, username, password, addr, port, client_id, timeout_seconds,
                 handshake_interval_seconds):
        self.message_queue = message_queue
        self.addr = addr
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.topic = f"/app/device/property/{device_sn}"
        # The mobile app requests the latest quotas of the device through these topics. Such a request "wakes up" the
        # device, so it starts (and keeps) streaming telemetry to self.topic
        self.get_topic = f"/app/{user_id}/{device_sn}/thing/property/get"
        self.get_reply_topic = f"/app/{user_id}/{device_sn}/thing/property/get_reply"
        self.timeout_seconds = timeout_seconds
        self.handshake_interval_seconds = handshake_interval_seconds
        self.last_message_time = None
        self.client = None

        self.connect()

        self.idle_timer = RepeatTimer(10, self.idle_reconnect)
        self.idle_timer.daemon = True
        self.idle_timer.start()

        if self.handshake_interval_seconds > 0:
            self.handshake_timer = RepeatTimer(self.handshake_interval_seconds, self.handshake)
            self.handshake_timer.daemon = True
            self.handshake_timer.start()

    def connect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, self.client_id)
        self.client.username_pw_set(self.username, self.password)
        self.client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
        self.client.tls_insecure_set(False)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        log.info(f"Connecting to MQTT Broker {self.addr}:{self.port} using client id {self.client_id}")
        self.client.connect(self.addr, self.port)
        self.client.loop_start()

    def idle_reconnect(self):
        if self.last_message_time and time.time() - self.last_message_time > self.timeout_seconds:
            log.error(f"No messages received for {self.timeout_seconds} seconds. Reconnecting to MQTT")
            try:
                self.connect()
            except Exception as error:
                # Keep last_message_time as is, so the next idle_reconnect call retries the connection
                log.error(f"Reconnection failed: {error}. Will retry")
                return
            log.info("Reconnection successful, continuing")
            # Give the new connection a full timeout before the next reconnection attempt
            self.last_message_time = time.time()

    def handshake(self):
        # Mimic the mobile app opening the device page: request all latest quotas. The device replies with a full
        # snapshot to get_reply_topic and starts pushing telemetry to self.topic
        if not self.client or not self.client.is_connected():
            log.debug("MQTT client is not connected. Skipping handshake")
            return
        payload = {
            "id": random.randint(100000000, 999999999),
            "version": "1.1",
            "from": "Android",
            "moduleType": 0,
            "operateType": "latestQuotas",
            "params": {}
        }
        log.debug(f"Sending handshake to {self.get_topic}: {payload}")
        result = self.client.publish(self.get_topic, json.dumps(payload), qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            log.error(f"Failed to publish handshake to {self.get_topic}: {mqtt.error_string(result.rc)}")

    def on_connect(self, client, userdata, flags, reason_code, properties):
        # Initialize the time of last message at least once upon connection so that other things that rely on that to be
        # set (like idle_reconnect) work
        self.last_message_time = time.time()
        match reason_code:
            case "Success":
                self.client.subscribe([(self.topic, 1), (self.get_reply_topic, 1)])
                log.info(f"Subscribed to MQTT topics {self.topic}, {self.get_reply_topic}")
                self.handshake()
            case "Keep alive timeout":
                log.error("Failed to connect to MQTT: connection timed out")
            case "Unsupported protocol version":
                log.error("Failed to connect to MQTT: unsupported protocol version")
            case "Client identifier not valid":
                log.error("Failed to connect to MQTT: invalid client identifier")
            case "Server unavailable":
                log.error("Failed to connect to MQTT: server unavailable")
            case "Bad user name or password":
                log.error("Failed to connect to MQTT: bad username or password")
            case "Not authorized":
                log.error("Failed to connect to MQTT: not authorised")
            case _:
                log.error(f"Failed to connect to MQTT: another error occured: {reason_code}")

        return client

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code > 0:
            log.error(f"Unexpected MQTT disconnection: {reason_code}. Will auto-reconnect")
            time.sleep(5)

    def on_message(self, client, userdata, message):
        self.last_message_time = time.time()
        try:
            payload = message.payload.decode("utf-8")
        except UnicodeDecodeError:
            # Newer devices send binary (protobuf) payloads which are not supported yet
            log.debug(f"Skipping non UTF-8 MQTT payload from {message.topic}: {message.payload.hex()}")
            return
        self.message_queue.put(payload)


class EcoflowMetric:
    def __init__(self, ecoflow_payload_key, device_name, indexed=False):
        self.ecoflow_payload_key = ecoflow_payload_key
        self.device_name = device_name
        # Indexed metrics are built from arrays (e.g. voltage of every battery cell) and have an extra label "index"
        self.indexed = indexed
        self.name = f"ecoflow_{self.convert_ecoflow_key_to_prometheus_name()}"
        labelnames = ["device", "index"] if indexed else ["device"]
        try:
            self.metric = Gauge(self.name, f"value from MQTT object key {ecoflow_payload_key}", labelnames=labelnames)
        except ValueError as error:
            # E.g. two different payload keys are converted to the same metric name
            raise EcoflowMetricException(f"Cannot create metric {self.name} from payload key {ecoflow_payload_key}: {error}")

    def convert_ecoflow_key_to_prometheus_name(self):
        # bms_bmsStatus.maxCellTemp -> bms_bms_status_max_cell_temp
        # pd.ext4p8Port -> pd_ext4p8_port
        key = self.ecoflow_payload_key.replace('.', '_')
        new = key[0].lower()
        for character in key[1:]:
            if character.isupper() and new[-1] != '_':
                new += '_'
            new += character.lower()
        # Check that metric name complies with the data model for valid characters
        # https://prometheus.io/docs/concepts/data_model/#metric-names-and-labels
        if not re.fullmatch("[a-zA-Z_:][a-zA-Z0-9_:]*", new):
            raise EcoflowMetricException(f"Cannot convert payload key {self.ecoflow_payload_key} to comply with the Prometheus data model. Please, raise an issue!")
        return new

    def set(self, value, index=None):
        # According to best practices for naming metrics and labels, the voltage should be in volts and the current in amperes
        # WARNING! This will ruin all Prometheus historical data and backward compatibility of Grafana dashboard
        # value = value / 1000 if value.endswith("_vol") or value.endswith("_amp") else value
        if self.indexed:
            log.debug(f"Set {self.name}[{index}] = {value}")
            self.metric.labels(device=self.device_name, index=index).set(value)
        else:
            log.debug(f"Set {self.name} = {value}")
            self.metric.labels(device=self.device_name).set(value)

    def clear(self):
        log.debug(f"Clear {self.name}")
        self.metric.clear()


class Worker:
    def __init__(self, message_queue, device_name, collecting_interval_seconds=10):
        self.message_queue = message_queue
        self.device_name = device_name
        self.collecting_interval_seconds = collecting_interval_seconds
        self.metrics_collector = {}
        # Payload keys that cannot be exported. They are logged only once, as they come with every message
        self.unsupported_keys = set()
        self.online = Gauge("ecoflow_online", "1 if device is online", labelnames=["device"])
        self.mqtt_messages_receive_total = Counter("ecoflow_mqtt_messages_receive_total", "total MQTT messages", labelnames=["device"])

    def loop(self):
        time.sleep(self.collecting_interval_seconds)
        while True:
            queue_size = self.message_queue.qsize()
            if queue_size > 0:
                log.info(f"Processing {queue_size} event(s) from the message queue")
                self.online.labels(device=self.device_name).set(1)
                self.mqtt_messages_receive_total.labels(device=self.device_name).inc(queue_size)
            else:
                log.info("Message queue is empty. Assuming that the device is offline")
                self.online.labels(device=self.device_name).set(0)
                # Clear metrics for NaN (No data) instead of last value
                for metric in self.metrics_collector.values():
                    metric.clear()

            while not self.message_queue.empty():
                payload = self.message_queue.get()
                log.debug(f"Recived payload: {payload}")
                if payload is None:
                    continue

                try:
                    payload = json.loads(payload)
                    if 'params' in payload:
                        params = payload['params']
                    else:
                        params = payload['data']['quotaMap']
                except (KeyError, TypeError) as key:
                    log.error(f"Failed to extract key {key} from payload: {payload}")
                    continue
                except Exception as error:
                    log.error(f"Failed to parse MQTT payload: {payload} Error: {error}")
                    continue
                self.process_payload(params)

            time.sleep(self.collecting_interval_seconds)

    def get_metric_by_ecoflow_payload_key(self, ecoflow_payload_key):
        return self.metrics_collector.get(ecoflow_payload_key)

    def skip_unsupported_key(self, ecoflow_payload_key, reason):
        if ecoflow_payload_key not in self.unsupported_keys:
            self.unsupported_keys.add(ecoflow_payload_key)
            log.warning(f"Skipping unsupported metric {ecoflow_payload_key}: {reason}")

    @staticmethod
    def flatten_payload_value(ecoflow_payload_key, ecoflow_payload_value):
        # Yields (key, index, value) for every numeric value. Arrays are exported with the "index" label:
        # bmsMaster.cellVol: [3883, 3851] -> (bmsMaster.cellVol, 0, 3883), (bmsMaster.cellVol, 1, 3851)
        # kit.productInfoDetails: [{"soc": 50}] -> (kit.productInfoDetails.soc, 0, 50)
        if isinstance(ecoflow_payload_value, (int, float)):
            yield ecoflow_payload_key, None, ecoflow_payload_value
        elif isinstance(ecoflow_payload_value, list) and not NON_NUMERIC_ARRAY_KEYS.search(ecoflow_payload_key):
            for index, item in enumerate(ecoflow_payload_value):
                if isinstance(item, (int, float)):
                    yield ecoflow_payload_key, str(index), item
                elif isinstance(item, dict):
                    for field, value in item.items():
                        if isinstance(value, (int, float)):
                            yield f"{ecoflow_payload_key}.{field}", str(index), value

    def process_payload(self, params):
        log.debug(f"Processing params: {params}")
        for ecoflow_payload_key, ecoflow_payload_value in params.items():
            if ecoflow_payload_key in self.unsupported_keys:
                continue

            values = list(self.flatten_payload_value(ecoflow_payload_key, ecoflow_payload_value))
            if not values:
                # Empty arrays and known non-numeric arrays are skipped silently
                if ecoflow_payload_value and not NON_NUMERIC_ARRAY_KEYS.search(ecoflow_payload_key):
                    self.skip_unsupported_key(ecoflow_payload_key, ecoflow_payload_value)
                continue

            for key, index, value in values:
                self.set_metric(key, index, value)

    def set_metric(self, ecoflow_payload_key, index, value):
        if ecoflow_payload_key in self.unsupported_keys:
            return

        metric = self.get_metric_by_ecoflow_payload_key(ecoflow_payload_key)
        if not metric:
            try:
                metric = EcoflowMetric(ecoflow_payload_key, self.device_name, indexed=index is not None)
            except EcoflowMetricException as error:
                self.skip_unsupported_key(ecoflow_payload_key, error)
                return
            log.info(f"Created new metric from payload key {metric.ecoflow_payload_key} -> {metric.name}")
            self.metrics_collector[ecoflow_payload_key] = metric

        if metric.indexed != (index is not None):
            self.skip_unsupported_key(ecoflow_payload_key, "the value changed between a number and an array")
            return

        metric.set(value, index)

        if ecoflow_payload_key == 'inv.acInVol' and value == 0:
            ac_in_current = self.get_metric_by_ecoflow_payload_key('inv.acInAmp')
            if ac_in_current:
                log.debug("Set AC inverter input current to zero because of zero inverter voltage")
                ac_in_current.set(0)


def signal_handler(signum, frame):
    log.info(f"Received signal {signum}. Exiting...")
    sys.exit(0)


def main():
    # Register the signal handler for SIGTERM
    signal.signal(signal.SIGTERM, signal_handler)

    # Disable Process and Platform collectors
    for coll in list(REGISTRY._collector_to_names.keys()):
        REGISTRY.unregister(coll)

    log_level = os.getenv("LOG_LEVEL", "INFO")

    match log_level:
        case "DEBUG":
            log_level = log.DEBUG
        case "INFO":
            log_level = log.INFO
        case "WARNING":
            log_level = log.WARNING
        case "ERROR":
            log_level = log.ERROR
        case _:
            log_level = log.INFO

    log.basicConfig(stream=sys.stdout, level=log_level, format='%(asctime)s %(levelname)-7s %(message)s')

    device_sn = os.getenv("DEVICE_SN")
    device_name = os.getenv("DEVICE_NAME") or device_sn
    ecoflow_username = os.getenv("ECOFLOW_USERNAME")
    ecoflow_password = os.getenv("ECOFLOW_PASSWORD")
    ecoflow_api_host = os.getenv("ECOFLOW_API_HOST", "api.ecoflow.com")
    exporter_port = int(os.getenv("EXPORTER_PORT", "9090"))
    collecting_interval_seconds = int(os.getenv("COLLECTING_INTERVAL", "10"))
    timeout_seconds = int(os.getenv("MQTT_TIMEOUT", "60"))
    handshake_interval_seconds = int(os.getenv("MQTT_HANDSHAKE_INTERVAL", "30"))

    if (not device_sn or not ecoflow_username or not ecoflow_password):
        log.error("Please, provide all required environment variables: DEVICE_SN, ECOFLOW_USERNAME, ECOFLOW_PASSWORD")
        sys.exit(1)

    try:
        auth = EcoflowAuthentication(ecoflow_username, ecoflow_password, ecoflow_api_host, device_sn)
    except Exception as error:
        log.error(error)
        sys.exit(1)

    message_queue = Queue()

    EcoflowMQTT(message_queue, device_sn, auth.user_id, auth.mqtt_username, auth.mqtt_password, auth.mqtt_url, auth.mqtt_port,
                auth.mqtt_client_id, timeout_seconds, handshake_interval_seconds)

    metrics = Worker(message_queue, device_name, collecting_interval_seconds)

    start_http_server(exporter_port)

    try:
        metrics.loop()

    except KeyboardInterrupt:
        log.info("Received KeyboardInterrupt. Exiting...")
        sys.exit(0)


if __name__ == '__main__':
    main()
