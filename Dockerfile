FROM python:3.10.5-buster

RUN apt update -y && apt upgrade -y

RUN /usr/local/bin/python -m pip install --upgrade pip
ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

ADD ecoflow_exporter.py /ecoflow_exporter.py

CMD [ "python", "/ecoflow_exporter.py" ]
