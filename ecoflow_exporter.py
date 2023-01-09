import logging as log
import sys
import os
import random
import ssl
import time
import json
import re
import paho.mqtt.client as mqtt
from queue import Queue
from prometheus_client import start_http_server, Gauge, Counter


class EcoflowMetricException(Exception):
    pass


class EcoflowMetric:
    def __init__(self, ecoflow_payload_key, device_sn):
        self.ecoflow_payload_key = ecoflow_payload_key
        self.device_sn = device_sn
        self.name = f"ecoflow_{self.convert_ecoflow_key_to_prometheus_name()}"
        self.metric = Gauge(self.name, f"value from MQTT object key {ecoflow_payload_key}", labelnames=["device_sn"])

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
        log.debug(f"Set {self.name} = {value}")
        self.metric.labels(device_sn=self.device_sn).set(value)

    def clear(self):
        log.debug(f"Clear {self.name}")
        self.metric.clear()


class Worker:
    def __init__(self, message_queue, device_sn, collecting_interval_seconds=5):
        self.message_queue = message_queue
        self.device_sn = device_sn
        self.collecting_interval_seconds = collecting_interval_seconds
        self.metrics_collector = []
        self.online = Gauge("ecoflow_online", "1 if device is online", labelnames=["device_sn"])
        self.mqtt_messages_receive_total = Counter("ecoflow_mqtt_messages_receive_total", "total MQTT messages", labelnames=["device_sn"])

    def run_metrics_loop(self):
        time.sleep(self.collecting_interval_seconds)
        while True:
            queue_size = self.message_queue.qsize()
            if queue_size > 0:
                log.info(f"Processing {queue_size} event(s) from the message queue")
                self.online.labels(device_sn=self.device_sn).set(1)
                self.mqtt_messages_receive_total.labels(device_sn=self.device_sn).inc(queue_size)
            else:
                log.info("Message queue is empty. Assuming that the device is offline")
                self.online.labels(device_sn=self.device_sn).set(0)
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
            if isinstance(ecoflow_payload_value, list):
                log.warning(f"Skipping unsupported metric {ecoflow_payload_key}: {ecoflow_payload_value}")
                continue

            metric = self.get_metric_by_ecoflow_payload_key(ecoflow_payload_key)
            if not metric:
                try:
                    metric = EcoflowMetric(ecoflow_payload_key, self.device_sn)
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


class EcoflowMQTT():

    def __init__(self, message_queue, device_sn, username, password, broker_addr, broker_port):
        self.message_queue = message_queue
        self.broker_addr = broker_addr
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.topic = f"/app/device/property/{device_sn}"
        self.client = mqtt.Client(f'python-mqtt-{random.randint(0, 100)}')

    def connect(self):
        self.client.username_pw_set(self.username, self.password)
        self.client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
        self.client.tls_insecure_set(False)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        log.info(f"Connecting to EcoFlow MQTT Broker {self.broker_addr}:{self.broker_port}")
        self.client.connect(self.broker_addr, self.broker_port)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        match rc:
            case 0:
                log.info(f"Successfully connected to MQTT")
                self.client.subscribe(self.topic)
                log.debug(f"Subscribed to topic {self.topic}")
            case -1:
                log.error("Failed to connect to MQTT: connection timed out")
            case 1:
                log.error("Failed to connect to MQTT: incorrect protocol version")
            case 2:
                log.error("Failed to connect to MQTT: invalid client identifier")
            case 3:
                log.error("Failed to connect to MQTT: server unavailable")
            case 4:
                log.error("Failed to connect to MQTT: bad username or password")
            case 5:
                log.error("Failed to connect to MQTT: not authorised")
            case _:
                log.error(f"Failed to connect to MQTT: another error occured: {rc}")

        return client

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            log.error(f"Unexpected MQTT disconnection: {rc}. Will auto-reconnect")

    def on_message(self, client, userdata, message):
        self.message_queue.put(message.payload.decode("utf-8"))


def main():
    log_level = os.getenv("LOG_LEVEL", "INFO")

    match log_level:
        case "DEBUG":
            log_level = log.DEBUG
        case "INFO":
            log_level = log.INFO
        case "WARNING":
            log_level = log.ERROR
        case "ERROR":
            log_level = log.ERROR
        case _:
            log_level = log.INFO

    log.basicConfig(stream=sys.stdout, level=log_level, format='%(asctime)s %(levelname)-7s %(message)s')

    device_sn = os.getenv("DEVICE_SN")
    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")
    broker_addr = os.getenv("MQTT_BROKER", "mqtt.ecoflow.com")
    broker_port = int(os.getenv("MQTT_PORT", "8883"))
    exporter_port = int(os.getenv("EXPORTER_PORT", "9090"))

    if (not device_sn or not username or not password):
        log.error("Please, provide all required environment variables: DEVICE_SN, MQTT_USERNAME, MQTT_PASSWORD")
        sys.exit(1)

    message_queue = Queue()

    ecoflow_mqtt = EcoflowMQTT(message_queue, device_sn, username, password, broker_addr, broker_port)
    ecoflow_mqtt.connect()

    metrics = Worker(message_queue, device_sn)
    start_http_server(exporter_port)
    metrics.run_metrics_loop()


if __name__ == '__main__':
    main()
