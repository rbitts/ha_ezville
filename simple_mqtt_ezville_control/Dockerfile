FROM python:3.8-slim-buster
  
ENV LANG C.UTF-8
ENV TZ=Asia/Seoul

# Install requirements for add-on
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir paho-mqtt
#RUN pip install --no-cache-dir telnetlib

# Copy data for add-on
COPY run.sh /

# 리팩토링된 모듈 파일들
COPY constants.py /
COPY utils.py /
COPY device_manager.py /
COPY mqtt_client.py /
COPY ew11_client.py /
COPY packet_processor.py /
COPY command_handler.py /
COPY application.py /
COPY ezville_refactored.py /

# 기존 파일 (백업용)
COPY ezville.py /

WORKDIR /share

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
