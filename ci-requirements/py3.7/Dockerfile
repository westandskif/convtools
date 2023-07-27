FROM --platform=linux/amd64 python:3.7-alpine

RUN mkdir -p /mnt/convtools
COPY requirements.txt /mnt/convtools/requirements.txt
RUN pip install -U pip \
    && pip install -r /mnt/convtools/requirements.txt
RUN pip install ipython

WORKDIR /mnt/convtools
