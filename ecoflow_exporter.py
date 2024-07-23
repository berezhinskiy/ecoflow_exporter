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
from queue import Queue
from threading import Timer
from multiprocessing import Process
import requests
import paho.mqtt.client as mqtt
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
from prometheus_client import start_http_server, REGISTRY


class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


class EcoflowMetricException(Exception):
    pass


class EcoflowAuthentication:
    def __init__(self, ecoflow_username, ecoflow_password, ecoflow_api_host):
        self.ecoflow_username = ecoflow_username
        self.ecoflow_password = ecoflow_password
        self.ecoflow_api_host = ecoflow_api_host
        self.mqtt_url = "mqtt.ecoflow.com"
        self.mqtt_port = 8883
        self.mqtt_username = None
        self.mqtt_password = None
        self.mqtt_client_id = None
        self.authorize()

    def authorize(self):
        url = f"https://{self.ecoflow_api_host}/auth/login"
        headers = {"lang": "en_US", "content-type": "application/json"}
        data = {"email": self.ecoflow_username,
                "password": base64.b64encode(self.ecoflow_password.encode()).decode(),
                "scene": "IOT_APP",
                "userType": "ECOFLOW"}

        log.info(f"Login to EcoFlow API {url}")
        request = requests.post(url, json=data, headers=headers)
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
        request = requests.get(url, data=data, headers=headers)
        response = self.get_json_response(request)

        try:
            self.mqtt_url = response["data"]["url"]
            self.mqtt_port = int(response["data"]["port"])
            self.mqtt_username = response["data"]["certificateAccount"]
            self.mqtt_password = response["data"]["certificatePassword"]
            self.mqtt_client_id = f"ANDROID_{str(uuid.uuid4()).upper()}_{user_id}"
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

    def __init__(self, message_queue, device_sn, username, password, addr, port, client_id, timeout_seconds):
        self.message_queue = message_queue
        self.addr = addr
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.topic = f"/app/device/property/{device_sn}"
        self.timeout_seconds = timeout_seconds
        self.last_message_time = None
        self.client = None

        self.connect()

        self.idle_timer = RepeatTimer(10, self.idle_reconnect)
        self.idle_timer.daemon = True
        self.idle_timer.start()

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
            # We pull the following into a separate process because there are actually quite a few things that can go
            # wrong inside the connection code, including it just timing out and never returning. So this gives us a
            # measure of safety around reconnection
            while True:
                connect_process = Process(target=self.connect)
                connect_process.start()
                connect_process.join(timeout=60)
                connect_process.terminate()
                if connect_process.exitcode == 0:
                    log.info("Reconnection successful, continuing")
                    # Reset last_message_time here to avoid a race condition between idle_reconnect getting called again
                    # before on_connect() or on_message() are called
                    self.last_message_time = None
                    break
                else:
                    log.error("Reconnection errored out, or timed out, attempted to reconnect...")

    def on_connect(self, client, userdata, flags, reason_code, properties):
        # Initialize the time of last message at least once upon connection so that other things that rely on that to be
        # set (like idle_reconnect) work
        self.last_message_time = time.time()
        match reason_code:
            case "Success":
                self.client.subscribe(self.topic)
                log.info(f"Subscribed to MQTT topic {self.topic}")
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
        self.message_queue.put(message.payload.decode("utf-8"))
        self.last_message_time = time.time()


class EcoflowMetric:
    def __init__(self, name, value, labels):
        self.original_name = name
        self.name = "ecoflow_" + self.transform_key(name)
        self.value = value
        self.labels = labels
        self.timestamp = time.time()
        self.label_names = list(labels.keys())

    def is_stale(self, current_time, timeout_seconds):
        return current_time - self.timestamp > timeout_seconds

    def transform_key(self, original_key):
        # bms_bmsStatus.maxCellTemp -> bms_bms_status_max_cell_temp
        # pd.ext4p8Port -> pd_ext4p8_port
        key = original_key.replace('.', '_')
        new = key[0].lower()
        for character in key[1:]:
            if character.isupper() and not new[-1] == '_':
                new += '_'
            new += character.lower()
        # Check that metric name complies with the data model for valid characters
        # https://prometheus.io/docs/concepts/data_model/#metric-names-and-labels
        if not re.match("[a-zA-Z_:][a-zA-Z0-9_:]*", new):
            raise EcoflowMetricException(f"Cannot convert payload key {original_key} to comply with the Prometheus data model. Please, raise an issue!")
        return new

    def set(self, value):
        self.timestamp = time.time()
        self.value = value

    def to_metric_family(self):
        label_names = list(self.labels.keys())
        label_values = list(self.labels.values())
        metric_family = GaugeMetricFamily(self.name, f'value from MQTT object key {self.original_name}', labels=label_names)
        metric_family.add_metric(label_values, self.value, timestamp=self.timestamp)
        return metric_family


class EcoflowCollector:
    def __init__(self, device_timeout, metric_timeout):
        self.metrics = {}
        self.device_timeout = device_timeout
        self.metric_timeout = metric_timeout
        self.device_last_seen = {}
        self.ecoflow_mqtt_messages_receive_total = {}

    def generate_ecoflow_online_metric(self):
        metric = GaugeMetricFamily('ecoflow_online', '1 if device is online', labels=['device'])
        now = time.time()
        for device, last_seen in self.device_last_seen.items():
            online = 1 if now - last_seen < self.device_timeout else 0
            metric.add_metric([device], online)
        return metric

    def generate_ecoflow_mqtt_messages_receive_total_metric(self):
        metric = CounterMetricFamily('ecoflow_mqtt_messages_receive_total', 'total MQTT messages', labels=['device'])
        for device, counter in self.ecoflow_mqtt_messages_receive_total.items():
            metric.add_metric([device], counter)
        return metric

    def collect(self):
        log.debug(f"Serving metrics")

        # Add synthetic metrics
        yield self.generate_ecoflow_online_metric()
        yield self.generate_ecoflow_mqtt_messages_receive_total_metric()

        # Iterate over device metrics
        now = time.time()
        for metric_name, metric_data in list(self.metrics.items()):
            if metric_data.is_stale(now, self.metric_timeout):
                log.info(f"Expiring metric {metric_name}")
                del self.metrics[metric_name]
                continue

            yield metric_data.to_metric_family()

    def set(self, name, value, device):
        # According to best practices for naming metrics and labels, the voltage should be in volts and the current in amperes
        # WARNING! This will ruin all Prometheus historical data and backward compatibility of Grafana dashboard
        # value = value / 1000 if key.endswith("Vol") or key.endswith("Amp") else value

        log.debug(f"Set {name} = {value}")

        key = (name, device)
        if key not in self.metrics:
            log.info(f"Created new metric {name}")

        self.metrics[key] = EcoflowMetric(name, value, {"device": device})

        if name == 'inv.acInVol' and value == 0:
            ac_in_current_key = ('inv.acInAmp', device)
            ac_in_current = self.metrics[ac_in_current_key]
            if ac_in_current:
                log.debug("Set AC inverter input current to zero because of zero inverter voltage")
                ac_in_current.set(0)

    def update_device_last_seen(self, device):
        self.device_last_seen[device] = time.time()

    def increment_mqtt_messages_receive_total(self, device):
        if device not in self.ecoflow_mqtt_messages_receive_total:
            self.ecoflow_mqtt_messages_receive_total[device] = 0
        self.ecoflow_mqtt_messages_receive_total[device] += 1


class Worker:
    def __init__(self, message_queue, device_name, collector):
        self.message_queue = message_queue
        self.device_name = device_name
        self.collector = collector

    def loop(self):
        while True:
            payload = self.message_queue.get()
            log.debug(f"Received payload: {payload}")
            self.collector.increment_mqtt_messages_receive_total(self.device_name)
            if payload is None:
                continue

            try:
                payload = json.loads(payload)
                params = payload['params']
            except KeyError as key:
                log.error(f"Failed to extract key {key} from payload: {payload}")
            except Exception as error:
                log.error(f"Failed to parse MQTT payload: {payload} Error: {error}")
                continue

            self.process_payload(params)

    def process_payload(self, params):
        log.debug(f"Processing params: {params}")
        for key, value in params.items():
            self.collector.update_device_last_seen(self.device_name)

            if not isinstance(value, (int, float)):
                log.warning(f"Skipping unsupported metric {key}: {value}")
                continue

            self.collector.set(key, value, self.device_name)


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
    device_timeout = int(os.getenv("DEVICE_TIMEOUT", "30"))
    metric_timeout = int(os.getenv("METRIC_TIMEOUT", "60"))
    mqtt_timeout = int(os.getenv("MQTT_TIMEOUT", "60"))

    if (not device_sn or not ecoflow_username or not ecoflow_password):
        log.error("Please, provide all required environment variables: DEVICE_SN, ECOFLOW_USERNAME, ECOFLOW_PASSWORD")
        sys.exit(1)

    try:
        auth = EcoflowAuthentication(ecoflow_username, ecoflow_password, ecoflow_api_host)
    except Exception as error:
        log.error(error)
        sys.exit(1)

    message_queue = Queue()

    EcoflowMQTT(message_queue, device_sn, auth.mqtt_username, auth.mqtt_password, auth.mqtt_url, auth.mqtt_port, auth.mqtt_client_id, mqtt_timeout)

    collector = EcoflowCollector(device_timeout, metric_timeout)
    REGISTRY.register(collector)

    worker = Worker(message_queue, device_name, collector)

    start_http_server(exporter_port)

    try:
        worker.loop()

    except KeyboardInterrupt:
        log.info("Received KeyboardInterrupt. Exiting...")
        sys.exit(0)


if __name__ == '__main__':
    main()
