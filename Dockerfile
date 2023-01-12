FROM python:3.11-alpine

LABEL maintainer="Yaroslav Berezhinskiy <yaroslav@berezhinskiy.name>"
LABEL description="An implementation of a Prometheus exporter for EcoFlow portable power stations"

RUN apt update -y && apt upgrade -y

RUN /usr/local/bin/python -m pip install --upgrade pip
ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

ADD ecoflow_exporter.py /ecoflow_exporter.py

CMD [ "python", "/ecoflow_exporter.py" ]
