# Entorno local Fincilia

Este Compose ejecuta la base mínima de E0: PostgreSQL autoritativo y un runner efímero de
verificación. Solo admite datos sintéticos. No es despliegue productivo ni contiene el
esquema financiero del producto.

## Requisitos

- Docker Engine y Compose dentro de Ubuntu/WSL.
- Git y edición permanecen en Windows.

## Arranque y comprobación

Desde WSL, en este directorio:

```bash
docker compose config --quiet
docker compose up -d --wait postgres
docker compose --profile test run --rm lifecycle-test initial
docker compose restart postgres
docker compose up -d --wait postgres
FINCILIA_LOCAL_LIFECYCLE_MODE=persisted docker compose --profile test run --rm lifecycle-test
docker compose stop postgres
docker compose start postgres
docker compose --profile test run --rm -e FINCILIA_LOCAL_LIFECYCLE_MODE=persisted lifecycle-test
```

La base escucha únicamente en `127.0.0.1:55430`. Los valores por defecto son credenciales
locales públicas y desechables; no deben reutilizarse fuera de este Compose.

## Parada y purga

Conservar el volumen:

```bash
docker compose down --remove-orphans
```

Eliminar exclusivamente el volumen local nombrado y volver a bootstrap limpio:

```bash
docker compose --profile test down --volumes --remove-orphans
```

La purga elimina solo `fincilia_local_pgdata`. Nunca apunta a directorios del workspace.

## Servicios diferidos

- Object storage: requiere motor, regiones y contrato de retención/versionado.
- Temporal: se agrega cuando existan esperas humanas durables reales.
- Valkey: se agrega únicamente tras una necesidad medida de cache/progreso.
- Analytics: seguirá siendo proyección reconstruible, nunca autoridad financiera.

