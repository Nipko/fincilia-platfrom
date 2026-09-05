# Dispatcher de correo: imagen propia, dependencias y usuario propios.
FROM python:3.12-alpine3.23@sha256:f0b72408d0c2ee5cf1df64adce9b92ab4f2d3c8cfbb879ac5ab1d0ec07208555

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src:/app/packages/platform/python

WORKDIR /app

COPY workers/notification/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /app/requirements.txt

COPY packages/platform/python /app/packages/platform/python
COPY workers/notification/src /app/src
COPY workers/notification/tests /app/tests

RUN adduser --system --uid 10003 --home /home/fincilia fincilia
USER 10003

CMD ["python", "-m", "fincilia_notification_worker.main"]
