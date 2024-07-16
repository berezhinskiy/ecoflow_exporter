FROM python:3.12-alpine

LABEL org.opencontainers.image.authors="Yaroslav Berezhinskiy <yaroslav@berezhinskiy.name>"
LABEL org.opencontainers.image.description="An implementation of a Prometheus exporter for EcoFlow portable power stations"
LABEL org.opencontainers.image.source=https://github.com/berezhinskiy/ecoflow_exporter
LABEL org.opencontainers.image.licenses=GPL-3.0

RUN apk update && apk add py3-pip

ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

ADD ecoflow_exporter.py /ecoflow_exporter.py

CMD [ "python", "/ecoflow_exporter.py" ]
