# Imagen del worker de documentos. Base fijada por digest.
FROM python@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src:/app/packages/contracts/python:/app/packages/platform/python

WORKDIR /app

COPY workers/document/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /app/requirements.txt

COPY packages/contracts/python /app/packages/contracts/python
COPY packages/platform/python /app/packages/platform/python
COPY workers/document/src /app/src

RUN useradd --system --uid 10002 --create-home fincilia
USER 10002

CMD ["python", "-m", "fincilia_worker.main"]
