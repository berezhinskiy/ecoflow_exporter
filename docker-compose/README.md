# Quick Start

Exporter should run along with [Prometheus](http://prometheus.io) and [Grafana](https://grafana.com). If you want to recive notifications to [Telegram](https://telegram.org) it is requred to startup [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) as well.

⚠️ This article does not cover Telegram-related things such as new bot token creation process, joining to the chat and so on. Please, talk directly to [Bot Father](https://telegram.me/BotFather)

## Compose

Project structure:

```plain
.
├── alertmanager
│   ├── templates
│   │   └── telegram.tmpl
│   └── alertmanager.yml
├── grafana
│   ├── dashboards
│   │   └── ecoflow.json
│   ├── dashboard.yml
│   └── datasource.yml
├── nginx
│   ├── nginx.conf
│   └── nginx.ssl.conf.example
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
      - 127.0.0.1:9090:9090

  alertmanager:
    image: prom/alertmanager
    ...
    ports:
      - 127.0.0.1:9093:9093

  grafana:
    image: grafana/grafana
    ...
    ports:
      - 3000:3000

  ecoflow_exporter:
    build: ..
    ...
    ports:
      - 127.0.0.1:9091:9091

  nginx:
    image: nginx:alpine
    profiles: [nginx]
    ...
    ports:
      - 80:80
      - 443:443
```

The compose file defines a stack with four services plus an optional `nginx` reverse proxy (enabled via `--profile nginx`):

- `prometheus`
- `alertmanager`
- `grafana`
- `ecoflow_exporter`

Prometheus, Alertmanager and ecoflow_exporter ports are bound to `127.0.0.1` — accessible locally or via SSH tunnel only.

## Deploy with docker compose

⚠️ Make sure the port `3000` on the host is not already in use (or `80`/`443` when using nginx).

To run all the services together, do the following:

- Create `.env` file inside `docker-compose` folder:

```bash
# Serial number(s) of your device(s) shown in the mobile application
# For multiple devices, use comma-separated values
DEVICE_SN="DEVICE_SN"
# Optional: custom device name(s) for Prometheus labels (comma-separated, same order as DEVICE_SN)
DEVICE_NAME="DEVICE_NAME"
# Email entered in the mobile application
ECOFLOW_USERNAME="ECOFLOW_USERNAME"
# Password entered in the mobile application
ECOFLOW_PASSWORD="ECOFLOW_PASSWORD"
# Username for Grafana Web interface
GRAFANA_USERNAME="admin"
# Password for Grafana Web interface
GRAFANA_PASSWORD="grafana"
# Telegram bot token and chat ID for Alertmanager notifications
TELEGRAM_BOT_TOKEN="TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID="TELEGRAM_CHAT_ID"

# Example for multiple devices:
# DEVICE_SN="DAEBX1234567,DELTA2ABCDEF"
# DEVICE_NAME="delta-pro,delta-2-max"
```

- Generate `alertmanager.yml` from the template (uses values from `.env`):

```bash
export $(grep -v '^#' .env | xargs) && envsubst < alertmanager/alertmanager.yml.example > alertmanager/alertmanager.yml
```

> If you don't want to receive notifications to Telegram, comment out the `alertmanager` section in [compose.yaml](compose.yaml) and the `alerting` section in [prometheus.yml](prometheus/prometheus.yml)

- Change directory to `docker-compose`, then create and start the containers:

```plain
$ cd docker-compose
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
CONTAINER ID   IMAGE                    COMMAND                  CREATED         STATUS         PORTS                          NAMES
6e300b56ad58   prom/prometheus          "/bin/prometheus --c…"   1 minute ago    Up 59 seconds  127.0.0.1:9090->9090/tcp       prometheus
3a13d5b37398   prom/alertmanager        "/bin/alertmanager -…"   1 minute ago    Up 59 seconds  127.0.0.1:9093->9093/tcp       alertmanager
de22630b4d3a   docker-compose-ecoflow…  "python /ecoflow_exp…"   1 minute ago    Up 59 seconds  127.0.0.1:9091->9091/tcp       ecoflow_exporter
1d61e570968d   grafana/grafana          "/run.sh"                1 minute ago    Up 59 seconds  0.0.0.0:3000->3000/tcp         grafana

```

## Grafana dashboard

The EcoFlow dashboard is provisioned automatically — navigate to [http://localhost:3000](http://localhost:3000) and use `GRAFANA_USERNAME` / `GRAFANA_PASSWORD` credentials from `.env` file to access Grafana.

## Production deployment

> ⚠️ In production, Prometheus (9090), Alertmanager (9093) and ecoflow_exporter (9091) are only accessible from `127.0.0.1` (SSH tunnel). Only Grafana and nginx are exposed publicly.

### Option 1: Direct IP access (no domain)

Open port 3000 in your firewall and access Grafana at `http://<server-ip>:3000`.

No extra configuration needed.

### Option 2: Domain with Cloudflare

Cloudflare handles SSL — nginx serves plain HTTP on port 80.

Add to `.env`:
```bash
GRAFANA_ROOT_URL=https://grafana.yourdomain.com
```

Start with nginx profile:
```bash
docker compose --profile nginx up -d
```

In Cloudflare: create an A record pointing to your server IP, enable the orange cloud (proxy).

### Option 3: Domain with Let's Encrypt

1. Obtain a certificate (run once, before starting nginx):
```bash
docker run --rm -p 80:80 \
  -v $(pwd)/nginx/certs:/etc/letsencrypt \
  certbot/certbot certonly --standalone -d grafana.yourdomain.com
# Certs will be at nginx/certs/live/grafana.yourdomain.com/
```

2. Copy the SSL config and update paths:
```bash
cp nginx/nginx.ssl.conf.example nginx/nginx.conf
# Edit nginx.conf: replace your.domain.com with your actual domain
# Update ssl_certificate paths to /etc/nginx/certs/live/grafana.yourdomain.com/fullchain.pem
```

3. Add to `.env`:
```bash
GRAFANA_ROOT_URL=https://grafana.yourdomain.com
```

4. Start with nginx profile:
```bash
docker compose --profile nginx up -d
```

## Troubleshooting

Check the logs:

```plain
$ docker compose logs
```

Get raw data from `ecoflow_exporter`:

```plain
$ curl http://127.0.0.1:9091
```

Navigate to [http://localhost:9090](http://localhost:9090) in your web browser to access directly the web interface of Prometheus. Check `Status` → `Targets`. The state of `ecoflow_exporter` should be `UP`. Otherwise, see the `Error` column.

Navigate to [http://localhost:9093](http://localhost:9093) in your web browser to directly access the web interface of Alertmanager.

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
