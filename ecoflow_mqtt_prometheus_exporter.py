import logging as log
import sys
import os
import random
import ssl
import time
import json
import paho.mqtt.client as mqtt
from queue import Queue
from prometheus_client import start_http_server, Gauge, Counter


class EcoflowMetric:
    def __init__(self, ecoflow_object_key, device_sn):
        self.ecoflow_object_key = ecoflow_object_key
        self.device_sn = device_sn
        self.name = f"ecoflow_{self.convert_ecoflow_key_to_prometheus_name()}"
        self.metric = Gauge(self.name, f"value from MQTT object key {ecoflow_object_key}", labelnames=["device_sn"])

    def convert_ecoflow_key_to_prometheus_name(self):
        # bms_bmsStatus.maxCellTemp -> bms_bms_status_max_cell_temp
        # pd.ext4p8Port -> pd_ext4p8_port
        key = self.ecoflow_object_key.replace('.', '_')
        new = key[0].lower()
        for character in key[1:]:
            if character.isupper() and not new[-1] == '_':
                new += '_'
            new += character.lower()
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
        self.metrics = []
        self.online = Gauge("online", "1 if device is online", labelnames=["device_sn"], namespace="ecoflow")
        self.mqtt_messages_receive_total = Counter("mqtt_messages_receive_total", "total MQTT messages", labelnames=["device_sn"], namespace="ecoflow")

    def run_metrics_loop(self):
        while True:
            if self.message_queue.qsize() > 0:
                log.info(f"Processing {self.message_queue.qsize()} event(s) from the message queue")
                self.online.labels(device_sn=self.device_sn).set(1)
                self.mqtt_messages_receive_total.labels(device_sn=self.device_sn).inc(self.message_queue.qsize())
            else:
                log.info("Message queue is empty. Probably, the device is offline")
                self.online.labels(device_sn=self.device_sn).set(0)
                # Clear metrics for NaN instead of last value
                for metric in self.metrics:
                    metric.clear()

            while not self.message_queue.empty():
                message = self.message_queue.get()
                if message is None:
                    continue

                try:
                    message = json.loads(message)
                    params = message['params']
                except Exception:
                    log.error(f"Cannot parse MQTT message: {message}")
                    continue
                log.debug(f"Processing payload: {params}")
                self.process_payload(params)

            time.sleep(self.collecting_interval_seconds)

    def get_metric_by_ecoflow_object_key(self, ecoflow_object_key):
        for metric in self.metrics:
            if metric.ecoflow_object_key == ecoflow_object_key:
                return metric
        return False

    def process_payload(self, params):
        for ecoflow_object_key in params.keys():
            ecoflow_object_value = params[ecoflow_object_key]
            if isinstance(ecoflow_object_value, list):
                log.warning(f"Skipping not supported metric {ecoflow_object_key}: {ecoflow_object_value}")
                continue
            metric = self.get_metric_by_ecoflow_object_key(ecoflow_object_key)
            if not metric:
                metric = EcoflowMetric(ecoflow_object_key, self.device_sn)
                log.info(f"Created new metric from object key {metric.ecoflow_object_key} -> {metric.name}")
                self.metrics.append(metric)
            metric.set(ecoflow_object_value)
            # Set AC current to zero in case of zero voltage
            if ecoflow_object_key == 'inv.acInVol' and ecoflow_object_value == 0:
                ac_voltage = self.get_metric_by_ecoflow_object_key('inv.acInAmp')
                if ac_voltage:
                    ac_voltage.set(0)


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
        if rc == 0:
            log.info(f"Successfully connected to MQTT")
            self.client.subscribe(self.topic)
            log.debug(f"Subscribed to topic {self.topic}")
        elif rc == -1:
            log.error("Failed to connect to MQTT: connection timed out")
        elif rc == 1:
            log.error("Failed to connect to MQTT: incorrect protocol version")
        elif rc == 2:
            log.error("Failed to connect to MQTT: invalid client identifier")
        elif rc == 3:
            log.error("Failed to connect to MQTT: server unavailable")
        elif rc == 4:
            log.error("Failed to connect to MQTT: bad username or password")
        elif rc == 5:
            log.error("Failed to connect to MQTT: not authorised")
        else:
            log.error(f"Failed to connect to MQTT: another error occured: {rc}")
        return client

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            log.warning(f"Unexpected MQTT disconnection: {rc}. Will auto-reconnect")

    def on_message(self, client, userdata, message):
        self.message_queue.put(message.payload.decode("utf-8"))


def main():
    log_level = str(os.getenv("LOG_LEVEL", "INFO"))
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

    device_sn = str(os.getenv("DEVICE_SN"))
    username = str(os.getenv("MQTT_USERNAME"))
    password = str(os.getenv("MQTT_PASSWORD"))
    broker_addr = str(os.getenv("MQTT_BROKER", "mqtt.ecoflow.com"))
    broker_port = int(os.getenv("MQTT_PORT", "8883"))
    exporter_port = int(os.getenv("EXPORTER_PORT", "9090"))

    message_queue = Queue()

    ecoflow_mqtt = EcoflowMQTT(message_queue, device_sn, username, password, broker_addr, broker_port)
    ecoflow_mqtt.connect()

    metrics = Worker(message_queue, device_sn)
    start_http_server(exporter_port)
    metrics.run_metrics_loop()


if __name__ == '__main__':
    main()
