# Imagen de la API. Base fijada por digest: una etiqueta puede reapuntarse.
FROM python:3.12-alpine3.23@sha256:f0b72408d0c2ee5cf1df64adce9b92ab4f2d3c8cfbb879ac5ab1d0ec07208555

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app:/app/src:/app/packages/contracts/python:/app/packages/platform/python

WORKDIR /app

# Las dependencias se instalan desde el lock con hashes: sin `--require-hashes`
# un mirror comprometido podria servir otra rueda con la misma version.
COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /app/requirements.txt

COPY packages/contracts/python /app/packages/contracts/python
COPY packages/platform/python /app/packages/platform/python
COPY db /app/db
COPY apps/api/src /app/src
COPY apps/api/tests /app/tests
# El codigo del worker viaja para que las pruebas de esquema puedan ejercer
# el recorrido completo -- subir, escanear, promover, perfilar -- en un solo
# proceso. **No** esta en PYTHONPATH: la API no puede importarlo por accidente,
# y solo las pruebas lo anaden a `sys.path` explicitamente.
COPY workers/document/src /app/worker_src

# El proceso no corre como root: un upload malicioso no debe encontrarse uid 0.
RUN adduser --system --uid 10001 --home /home/fincilia fincilia
USER 10001

EXPOSE 8000
CMD ["uvicorn", "fincilia_api.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
