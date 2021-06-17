FROM python:3.9 as builder

WORKDIR /eth/

COPY requirements.txt   /eth/requirements.txt
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install -r requirements.txt


FROM python:3.9-slim as runner
WORKDIR /eth/
COPY --from=builder /opt/venv /opt/venv
COPY plugin       /eth/plugin
ENTRYPOINT ["/opt/venv/bin/python3", "-m", "plugin"]