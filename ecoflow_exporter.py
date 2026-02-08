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
import threading
from queue import Queue
from threading import Timer

import requests
import paho.mqtt.client as mqtt
from prometheus_client import start_http_server, REGISTRY, Gauge, Counter

# Shared Prometheus metric registries (thread-safe)
_gauge_registry = {}
_gauge_registry_lock = threading.Lock()

_online_gauge = None
_mqtt_counter = None
_worker_metrics_lock = threading.Lock()


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

    def __init__(self, message_queue, device_sn, username, password, addr, port, user_id, timeout_seconds):
        self.message_queue = message_queue
        self.addr = addr
        self.port = port
        self.username = username
        self.password = password
        self.client_id = f"ANDROID_{str(uuid.uuid4()).upper()}_{user_id}"
        self.device_sn = device_sn
        self.topic = f"/app/device/property/{device_sn}"
        self.topic_get = f"/app/{user_id}/{device_sn}/thing/property/get"
        self.timeout_seconds = timeout_seconds
        self.last_message_time = None
        self.client = None

        self.connect()

        self.idle_timer = RepeatTimer(10, self.idle_reconnect)
        self.idle_timer.daemon = True
        self.idle_timer.start()

        self.quota_timer = RepeatTimer(15, self.request_data)
        self.quota_timer.daemon = True
        self.quota_timer.start()

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
            log.error(f"[{self.device_sn}] No messages received for {self.timeout_seconds} seconds. Reconnecting to MQTT")
            while True:
                connect_thread = threading.Thread(target=self.connect, daemon=True)
                connect_thread.start()
                connect_thread.join(timeout=60)
                if not connect_thread.is_alive():
                    log.info(f"[{self.device_sn}] Reconnection successful, continuing")
                    self.last_message_time = None
                    break
                else:
                    log.error(f"[{self.device_sn}] Reconnection timed out, retrying...")

    def request_data(self):
        if self.client and self.client.is_connected():
            payload = json.dumps({
                "from": "Android",
                "id": str(int(time.time() * 1000)),
                "moduleType": 0,
                "operateType": "latestQuotas",
                "params": {},
                "version": "1.0"
            })
            log.debug(f"[{self.device_sn}] Requesting data via {self.topic_get}")
            self.client.publish(self.topic_get, payload)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        # Initialize the time of last message at least once upon connection so that other things that rely on that to be
        # set (like idle_reconnect) work
        self.last_message_time = time.time()
        match reason_code:
            case "Success":
                self.client.subscribe(self.topic)
                log.info(f"Subscribed to MQTT topic {self.topic}")
                self.request_data()
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
    def __init__(self, ecoflow_payload_key, device_name):
        self.ecoflow_payload_key = ecoflow_payload_key
        self.device_name = device_name
        self.name = f"ecoflow_{self.convert_ecoflow_key_to_prometheus_name()}"
        with _gauge_registry_lock:
            if self.name in _gauge_registry:
                self.metric = _gauge_registry[self.name]
            else:
                self.metric = Gauge(self.name, f"value from MQTT object key {ecoflow_payload_key}", labelnames=["device"])
                _gauge_registry[self.name] = self.metric

    def convert_ecoflow_key_to_prometheus_name(self):
        # bms_bmsStatus.maxCellTemp -> bms_bms_status_max_cell_temp
        # pd.ext4p8Port -> pd_ext4p8_port
        key = self.ecoflow_payload_key.replace('.', '_')
        new = key[0].lower()
        for character in key[1:]:
            if character.isupper() and not new[-1] == '_':
                new += '_'
            new += character.lower()
        # Check that metric name complies with the data model for valid characters
        # https://prometheus.io/docs/concepts/data_model/#metric-names-and-labels
        if not re.match("[a-zA-Z_:][a-zA-Z0-9_:]*", new):
            raise EcoflowMetricException(f"Cannot convert payload key {self.ecoflow_payload_key} to comply with the Prometheus data model. Please, raise an issue!")
        return new

    def set(self, value):
        # According to best practices for naming metrics and labels, the voltage should be in volts and the current in amperes
        # WARNING! This will ruin all Prometheus historical data and backward compatibility of Grafana dashboard
        # value = value / 1000 if value.endswith("_vol") or value.endswith("_amp") else value
        log.debug(f"Set {self.name} = {value}")
        self.metric.labels(device=self.device_name).set(value)

    def clear(self):
        log.debug(f"Clear {self.name} for device {self.device_name}")
        self.metric.remove(self.device_name)


class Worker:
    def __init__(self, message_queue, device_name, collecting_interval_seconds=10):
        global _online_gauge, _mqtt_counter
        self.message_queue = message_queue
        self.device_name = device_name
        self.collecting_interval_seconds = collecting_interval_seconds
        self.metrics_collector = []
        with _worker_metrics_lock:
            if _online_gauge is None:
                _online_gauge = Gauge("ecoflow_online", "1 if device is online", labelnames=["device"])
            if _mqtt_counter is None:
                _mqtt_counter = Counter("ecoflow_mqtt_messages_receive_total", "total MQTT messages", labelnames=["device"])
        self.online = _online_gauge
        self.mqtt_messages_receive_total = _mqtt_counter

    def loop(self):
        time.sleep(self.collecting_interval_seconds)
        while True:
            queue_size = self.message_queue.qsize()
            if queue_size > 0:
                log.info(f"[{self.device_name}] Processing {queue_size} event(s) from the message queue")
                self.online.labels(device=self.device_name).set(1)
                self.mqtt_messages_receive_total.labels(device=self.device_name).inc(queue_size)
            else:
                log.info(f"[{self.device_name}] Message queue is empty. Assuming that the device is offline")
                self.online.labels(device=self.device_name).set(0)
                # Clear metrics for NaN (No data) instead of last value
                for metric in self.metrics_collector:
                    metric.clear()

            while not self.message_queue.empty():
                payload = self.message_queue.get()
                log.debug(f"Recived payload: {payload}")
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

            time.sleep(self.collecting_interval_seconds)

    def get_metric_by_ecoflow_payload_key(self, ecoflow_payload_key):
        for metric in self.metrics_collector:
            if metric.ecoflow_payload_key == ecoflow_payload_key:
                log.debug(f"Found metric {metric.name} linked to {ecoflow_payload_key}")
                return metric
        log.debug(f"Cannot find metric linked to {ecoflow_payload_key}")
        return False

    def process_payload(self, params):
        log.debug(f"Processing params: {params}")
        for ecoflow_payload_key in params.keys():
            ecoflow_payload_value = params[ecoflow_payload_key]
            if not isinstance(ecoflow_payload_value, (int, float)):
                log.warning(f"Skipping unsupported metric {ecoflow_payload_key}: {ecoflow_payload_value}")
                continue

            metric = self.get_metric_by_ecoflow_payload_key(ecoflow_payload_key)
            if not metric:
                try:
                    metric = EcoflowMetric(ecoflow_payload_key, self.device_name)
                except EcoflowMetricException as error:
                    log.error(error)
                    continue
                log.info(f"Created new metric from payload key {metric.ecoflow_payload_key} -> {metric.name}")
                self.metrics_collector.append(metric)

            metric.set(ecoflow_payload_value)

            if ecoflow_payload_key == 'inv.acInVol' and ecoflow_payload_value == 0:
                ac_in_current = self.get_metric_by_ecoflow_payload_key('inv.acInAmp')
                if ac_in_current:
                    log.debug("Set AC inverter input current to zero because of zero inverter voltage")
                    ac_in_current.set(0)


def signal_handler(signum, frame):
    log.info(f"Received signal {signum}. Exiting...")
    sys.exit(0)


def parse_device_list():
    device_sn_raw = os.getenv("DEVICE_SN", "")
    device_name_raw = os.getenv("DEVICE_NAME", "")

    sns = [s.strip() for s in device_sn_raw.split(",") if s.strip()]
    names = [s.strip() for s in device_name_raw.split(",")] if device_name_raw else []

    if not sns:
        log.error("Please, provide DEVICE_SN environment variable")
        sys.exit(1)

    devices = []
    for i, sn in enumerate(sns):
        name = names[i] if i < len(names) and names[i] else sn
        devices.append({"sn": sn, "name": name})

    return devices


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

    devices = parse_device_list()
    ecoflow_username = os.getenv("ECOFLOW_USERNAME")
    ecoflow_password = os.getenv("ECOFLOW_PASSWORD")
    ecoflow_api_host = os.getenv("ECOFLOW_API_HOST", "api.ecoflow.com")
    exporter_port = int(os.getenv("EXPORTER_PORT", "9090"))
    collecting_interval_seconds = int(os.getenv("COLLECTING_INTERVAL", "10"))
    timeout_seconds = int(os.getenv("MQTT_TIMEOUT", "60"))

    if not ecoflow_username or not ecoflow_password:
        log.error("Please, provide all required environment variables: DEVICE_SN, ECOFLOW_USERNAME, ECOFLOW_PASSWORD")
        sys.exit(1)

    try:
        auth = EcoflowAuthentication(ecoflow_username, ecoflow_password, ecoflow_api_host)
    except Exception as error:
        log.error(error)
        sys.exit(1)

    start_http_server(exporter_port)

    worker_threads = []
    for device in devices:
        sn = device["sn"]
        name = device["name"]
        log.info(f"Setting up device: {name} (SN: {sn})")

        message_queue = Queue()

        EcoflowMQTT(message_queue, sn, auth.mqtt_username, auth.mqtt_password, auth.mqtt_url, auth.mqtt_port, auth.user_id, timeout_seconds)

        worker = Worker(message_queue, name, collecting_interval_seconds)

        t = threading.Thread(target=worker.loop, name=f"worker-{name}", daemon=True)
        t.start()
        worker_threads.append(t)

    log.info(f"Started monitoring {len(devices)} device(s)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Received KeyboardInterrupt. Exiting...")
        sys.exit(0)


if __name__ == '__main__':
    main()
