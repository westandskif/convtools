FROM python:3.6-slim

RUN mkdir -p /mnt/convtools
COPY requirements.txt /mnt/convtools/requirements.txt
RUN pip install -U pip \
    && pip install -r /mnt/convtools/requirements.txt
RUN pip install ipython

WORKDIR /mnt/convtools
