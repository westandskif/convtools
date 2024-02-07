ARG PY_VERSION="3.6"
FROM python:$PY_VERSION
ARG PY_VERSION="3.6"

RUN pip install -U pip

RUN mkdir -p /mnt/convtools
COPY requirements$PY_VERSION.out /mnt/convtools/
RUN pip install -r "/mnt/convtools/requirements$PY_VERSION.out"

WORKDIR /mnt/convtools
