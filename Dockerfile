FROM python:3.9-slim

RUN mkdir -p /mnt/convtools
COPY ci-requirements/py3.9-lint-doc-build/requirements.txt /mnt/convtools/requirements.txt
RUN pip install -U pip \
    && pip install -r /mnt/convtools/requirements.txt
RUN pip install ipython ruff

WORKDIR /mnt/convtools
