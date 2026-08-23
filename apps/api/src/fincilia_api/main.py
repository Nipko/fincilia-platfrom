"""Aplicacion FastAPI de Fincilia.

`/health/live` responde si el proceso esta vivo y **no** toca dependencias: si
consultara la base, un fallo de red reiniciaria el contenedor sin motivo.
`/health/ready` si las consulta, porque responde a otra pregunta: si este proceso
puede atender trafico ahora.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import valkey

from fincilia_platform.db import Database
from fincilia_platform.identity import Credential, LocalIdentityProvider
from fincilia_platform.objects import S3ObjectStore
from fincilia_platform.settings import ApiSettings, get_api_settings
from fincilia_platform.probes import Probe, build_probes, ensure_buckets
from fincilia_contracts.errors import ProblemDetail, problem

from . import repository
from .routes import router
from .security import ProblemError
from .throttle import AttemptThrottle

API_VERSION = "0.1.0"
PROBLEM_MEDIA_TYPE = "application/problem+json"

logger = logging.getLogger("fincilia.api")


def _problem_response(detail: ProblemDetail) -> JSONResponse:
    return JSONResponse(status_code=detail.status, content=detail.as_dict(),
                        media_type=PROBLEM_MEDIA_TYPE)


def expected_schema_head() -> str | None:
    """Cabeza que espera **esta imagen**, leida de las migraciones que lleva dentro.

    Comparar la base contra una constante escrita a mano se desincroniza el dia
    que alguien anade una migracion y no toca la constante. Comparar contra los
    ficheros que viajan en la imagen no puede desincronizarse.
    """
    try:
        from db.migrate.apply import discover
    except ImportError:
        return None
    try:
        plan = discover()
    except Exception:  # noqa: BLE001 - un plan ilegible no tumba el arranque
        logger.warning("migration plan unreadable; the schema probe will not pin a head")
        return None
    return plan[-1].version if plan else None


def build_identity_provider(settings: ApiSettings, database: Database):
    """Proveedor local tras la interfaz. Sustituirlo no toca dominio ni rutas."""
    def lookup(username: str) -> Credential | None:
        with database.session() as connection:
            return repository.find_credential(connection, username)
    return LocalIdentityProvider(lookup, real_data_enabled=settings.real_data_enabled)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: ApiSettings = app.state.settings
    logging.basicConfig(level=settings.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info("starting %s in %s", settings.service_name, settings.env)
    database = Database(settings)
    app.state.database = database
    app.state.identity_provider = build_identity_provider(settings, database)
    app.state.throttle = AttemptThrottle(
        valkey.Valkey.from_url(settings.cache_url, socket_connect_timeout=2,
                               socket_timeout=2))
    app.state.object_store = S3ObjectStore(settings)
    app.state.probes = build_probes(settings, expected_head=expected_schema_head())
    if settings.env == "local":
        # Solo en local. En cualquier otro entorno las zonas de evidencia las crea
        # la infraestructura y el servicio no tiene permiso para hacerlo.
        created = ensure_buckets(settings)
        logger.info("object storage ready; created=%s", created or "none")
    try:
        yield
    finally:
        database.close()
        logger.info("stopping %s", settings.service_name)


def create_app(settings: ApiSettings | None = None,
               probes: tuple[Probe, ...] | None = None) -> FastAPI:
    """Fabrica inyectable: las pruebas pasan settings y sondas propias."""
    resolved = settings or get_api_settings()
    app = FastAPI(
        title="Fincilia API",
        version=API_VERSION,
        summary="Plataforma local de conciliacion y cierre. Datos sinteticos.",
        lifespan=lifespan,
        docs_url="/docs" if resolved.env == "local" else None,
        redoc_url=None,
    )
    app.state.settings = resolved
    if probes is not None:
        app.state.probes = probes

    @app.exception_handler(ProblemError)
    async def _problem_error(_request: Request, error: ProblemError) -> JSONResponse:
        return _problem_response(error.problem)

    @app.exception_handler(ValueError)
    async def _value_error(_request: Request, error: ValueError) -> JSONResponse:
        # Un ValueError del dominio es del cliente, no del servidor. El mensaje
        # es el del dominio, que ya esta escrito para no filtrar datos.
        return _problem_response(problem(
            "invalid-request", "Invalid request", 422, str(error)))

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, Any]:
        return {"status": "alive", "service": resolved.service_name,
                "version": API_VERSION, "environment": resolved.env}

    # `def`, no `async def`: las sondas son bloqueantes y en el bucle de eventos
    # dejarian sin atender al resto mientras esperan.
    @app.get("/health/ready", tags=["health"])
    def ready() -> JSONResponse:
        results = [probe.probe() for probe in app.state.probes]
        healthy = all(result.healthy for result in results)
        payload = {
            "status": "ready" if healthy else "degraded",
            "service": resolved.service_name,
            "version": API_VERSION,
            "dependencies": [result.as_dict() for result in results],
        }
        return JSONResponse(status_code=200 if healthy else 503, content=payload)

    @app.get("/health/config", tags=["health"])
    async def config_diagnosis() -> dict[str, Any]:
        """Diagnostico de configuracion **sin secretos**.

        Se publica que capacidades estan apagadas, no con que credenciales se
        conecta: un endpoint de diagnostico que filtra un DSN es una brecha.
        """
        return {
            "environment": resolved.env,
            "data_ceiling": "synthetic_only",
            "capabilities": {
                "real_data_enabled": resolved.real_data_enabled,
                "ai_gateway_enabled": resolved.ai_gateway_enabled,
                "payments_enabled": resolved.payments_enabled,
            },
            "buckets": list(resolved.buckets),
            "auth_issuer": resolved.auth_issuer,
            "auth_token_ttl_seconds": resolved.auth_token_ttl_seconds,
        }

    app.include_router(router)
    return app


app = create_app  # se instancia en el arranque real, ver `asgi.py`
