FROM python:3.7
COPY . /tmp/debian_local_mirror
RUN cd /tmp/debian_local_mirror && \
    python -m pip install --upgrade pip && \
    python -m pip install --upgrade setuptools wheel && \
    python -m pip install .
ENTRYPOINT ["python", "-m", "debian_local_mirror"]
