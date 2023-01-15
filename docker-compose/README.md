# Compose sample

## Prometheus, Grafana, Alertmanager, EcoFlow exporter

Project structure:

```plain
.
├── alertmanager
│   ├── templates
│   │   └── telegram.tmpl
│   └── alertmanager.yml
├── grafana
│   └── datasource.yml
├── prometheus
│   ├── alerts
│   │   └── ecoflow.yml
│   ├── config
│   └── prometheus.yml
├── README.md
└── compose.yaml
```

[_compose.yaml_](compose.yaml)

```yaml
services:
  prometheus:
    image: prom/prometheus
    ...
    ports:
      - 9090:9090
  alertmanager:
    image: prom/alertmanager
    ...
    ports:
      - 9093:9093
  grafana:
    image: grafana/grafana
    ...
    ports:
      - 3000:3000
  ecoflow_exporter:
    image: ghcr.io/berezhinskiy/ecoflow_exporter
    ...
    ports:
      - 9091:9091
```

The compose file defines a stack with four services:

- `prometheus`
- `alertmanager`
- `grafana`
- `ecoflow_exporter`

When deploying the stack, docker compose maps port the default ports for each service to the equivalent ports on the host in order to inspect easier the web interface of each service.

⚠️ Make sure the ports `9090`, `9091`, `9093` and `3000` on the host are not already in use.

## Deploy with docker compose

```plain
$ docker compose up -d
Creating network "prometheus-grafana_default" with the default driver
Creating volume "prometheus-grafana_prom_data" with default driver
...
Creating grafana    ... done
Creating prometheus ... done
Attaching to prometheus, grafana

```

## Expected result

Listing containers must show two containers running and the port mapping as below:

```plain
$ docker ps

```

Navigate to `http://localhost:3000` in your web browser and use the login credentials specified in the compose file to access Grafana. It is already configured with prometheus as the default datasource.

Navigate to `http://localhost:9090` in your web browser to access directly the web interface of prometheus.

Stop and remove the containers. Use `-v` to remove the volumes if looking to erase all data:

```plain
$ docker compose down -v

```
