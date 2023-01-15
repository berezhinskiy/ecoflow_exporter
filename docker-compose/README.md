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
$ sudo docker compose up -d
[+] Running 6/6
 ⠿ Network docker-compose_default     Created
 ⠿ Volume "docker-compose_prom_data"  Created
 ⠿ Container alertmanager             Started
 ⠿ Container grafana                  Started
 ⠿ Container prometheus               Started
 ⠿ Container ecoflow_exporter         Started

```

## Expected result

Listing containers must show two containers running and the port mapping as below:

```bash
$ sudo docker ps -a
CONTAINER ID   IMAGE                                   COMMAND                  CREATED              STATUS          PORTS                                       NAMES
6e300b56ad58   prom/prometheus                         "/bin/prometheus --c…"   About a minute ago   Up 59 seconds   0.0.0.0:9090->9090/tcp, :::9090->9090/tcp   prometheus
3a13d5b37398   prom/alertmanager                       "/bin/alertmanager -…"   About a minute ago   Up 59 seconds   0.0.0.0:9093->9093/tcp, :::9093->9093/tcp   alertmanager
de22630b4d3a   ghcr.io/berezhinskiy/ecoflow_exporter   "python /ecoflow_exp…"   About a minute ago   Up 59 seconds   0.0.0.0:9091->9091/tcp, :::9091->9091/tcp   ecoflow_exporter
1d61e570968d   grafana/grafana                         "/run.sh"                About a minute ago   Up 59 seconds   0.0.0.0:3000->3000/tcp, :::3000->3000/tcp   grafana

```

Navigate to `http://localhost:3000` in your web browser and use the login credentials specified in the compose file to access Grafana. It is already configured with prometheus as the default datasource.

Navigate to `http://localhost:9090` in your web browser to access directly the web interface of prometheus.

Stop and remove the containers. Use `-v` to remove the volumes if looking to erase all data:

```plain
$ docker compose down -v

```
