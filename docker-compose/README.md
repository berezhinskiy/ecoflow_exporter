# Quick Start

## Compose

Exporter should run along with [Prometheus](http://prometheus.io) and [Grafana](https://grafana.com). If you want to recive notifications to [Telegram](https://telegram.org) is requred to startup [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) as well.

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

## Deploy with docker compose

⚠️ Make sure the ports `9090`, `9091`, `9093` and `3000` on the host are not already in use.

To run them all together, do the following:

- Create `.env` file inside `docker-compose` folder with the following:

```bash
# Serial number of your device shown in the mobile application
DEVICE_SN=<DEVICE_SN>
# Email entered in the mobile application
ECOFLOW_USERNAME=<ECOFLOW_USERNAME>
# Password entereed in the mobile application
ECOFLOW_PASSWORD=<ECOFLOW_PASSWORD>
```

- If you don't want to receive notifications to Telegram, comment out `alertmanager` section in [compose.yaml](compose.yaml#L14-L23). Otherwise, replace `<TELEGRAM_BOT_TOKEN>` and `<TELEGRAM_CHAT_ID>` with your values in [alertmanager.yaml](alertmanager/alertmanager.yml)

> ⚠️ This article not covers Telegram-related things. Such as new bot token creation process, joining to the chat and so on. Please, talk directly to [Bot Father](https://telegram.me/BotFather)

- Create and start containers:

```plain
$ docker compose up -d
[+] Running 6/6
 ⠿ Network docker-compose_default     Created
 ⠿ Volume "docker-compose_prom_data"  Created
 ⠿ Container alertmanager             Started
 ⠿ Container grafana                  Started
 ⠿ Container prometheus               Started
 ⠿ Container ecoflow_exporter         Started

```

## Expected result

Listing containers must show four containers running and the port mapping as below:

```bash
$ docker ps -a
CONTAINER ID   IMAGE                                   COMMAND                  CREATED              STATUS          PORTS                                       NAMES
6e300b56ad58   prom/prometheus                         "/bin/prometheus --c…"   About a minute ago   Up 59 seconds   0.0.0.0:9090->9090/tcp, :::9090->9090/tcp   prometheus
3a13d5b37398   prom/alertmanager                       "/bin/alertmanager -…"   About a minute ago   Up 59 seconds   0.0.0.0:9093->9093/tcp, :::9093->9093/tcp   alertmanager
de22630b4d3a   ghcr.io/berezhinskiy/ecoflow_exporter   "python /ecoflow_exp…"   About a minute ago   Up 59 seconds   0.0.0.0:9091->9091/tcp, :::9091->9091/tcp   ecoflow_exporter
1d61e570968d   grafana/grafana                         "/run.sh"                About a minute ago   Up 59 seconds   0.0.0.0:3000->3000/tcp, :::3000->3000/tcp   grafana

```

## Import Grafana dasboard

Navigate to [http://localhost:3000](http://localhost:3000) in your web browser and use the login credentials `admin/grafana` to access Grafana. It is already configured with prometheus as the default datasource.

Navigate to Dashboards → Import dashboard, import ID `17812` via grafana.com, select the only existing Prometheus dataset.

## Troubleshooting

```plain
$ docker compose logs
...
```

## Destroy

Stop and remove the containers. Use `-v` to remove the volumes if looking to erase all data:

```plain
$ docker compose down -v
[+] Running 6/6
 ⠿ Container ecoflow_exporter       Removed
 ⠿ Container alertmanager           Removed
 ⠿ Container grafana                Removed
 ⠿ Container prometheus             Removed
 ⠿ Volume docker-compose_prom_data  Removed
 ⠿ Network docker-compose_default   Removed
```
