"""Bucle del dispatcher durable de correo.

Con el proveedor desactivado el proceso solo mantiene su healthcheck y nunca
abre la cola. Con SES activo verifica DRG-01 antes de construir cualquier
cliente, descifra el destino solo en memoria y persiste un digest del mensaje.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from pathlib import Path
from types import FrameType

import boto3

from fincilia_platform.db import Database
from fincilia_platform.email_delivery import (
    AwsKmsDestinationProtector,
    AwsSesAdapter,
    DeliveryError,
    EncryptedDestination,
)
from fincilia_platform.gates import verify_configured_gate
from fincilia_platform.observability import configure as configure_observability
from fincilia_platform.observability import log_event
from fincilia_notification_worker import delivery
from fincilia_notification_worker.config import NotificationWorkerSettings, load_settings


HEARTBEAT_PATH = Path("/tmp/fincilia-notification-worker-alive")
HEARTBEAT_INTERVAL_SECONDS = 5
IDLE_SLEEP_SECONDS = 2
logger = logging.getLogger("fincilia.notification_worker")
_running = True


def _stop(signum: int, _frame: FrameType | None) -> None:
    global _running
    logger.info("dispatcher draining after signal %s", signum)
    _running = False


def beat() -> None:
    HEARTBEAT_PATH.write_text(str(int(time.time())), encoding="utf-8")


def build_delivery_clients(settings: NotificationWorkerSettings):
    """Construye clientes solo despues de validar configuracion y DRG-01."""
    if settings.notification_provider != "aws_ses":
        raise RuntimeError("notification provider is disabled")
    kms = boto3.client("kms", region_name=settings.notification_region)
    verify_configured_gate(settings, required_gate="DRG-01", kms_client=kms)
    ses = boto3.client("sesv2", region_name=settings.notification_region)
    return (
        AwsKmsDestinationProtector(
            kms, key_id=settings.notification_destination_kms_key_id),
        AwsSesAdapter(
            ses, from_address=settings.notification_from_address,
            reply_to=settings.notification_reply_to_address,
            configuration_set=settings.notification_configuration_set,
            public_origin=settings.notification_public_origin,
        ),
    )


def process_one(database: Database, protector: AwsKmsDestinationProtector,
                adapter: AwsSesAdapter, identity: str) -> bool:
    try:
        with database.session() as connection:
            claim = delivery.claim_next(connection, identity)
    except Exception:  # noqa: BLE001 - la base puede reiniciarse
        logger.exception("notification queue unavailable")
        return False
    if claim is None:
        return False

    try:
        recipient = protector.decrypt(EncryptedDestination(
            claim.encrypted_address, claim.address_ref, claim.kms_key_ref))
    except DeliveryError as error:
        try:
            with database.session() as connection:
                delivery.finish(
                    connection, claim, outcome=error.failure_class,
                    reason_code=error.code)
        except Exception:  # noqa: BLE001
            logger.exception("could not persist notification preflight failure")
        return True
    except Exception:  # noqa: BLE001 - aun no se contacto al proveedor
        try:
            with database.session() as connection:
                delivery.finish(
                    connection, claim, outcome="fatal",
                    reason_code="worker_preflight_failed")
        except Exception:  # noqa: BLE001
            logger.exception("could not persist notification preflight failure")
        return True

    # Desde este commit durable cualquier caida permanece uncertain. El claim
    # no se recicla y por tanto nunca puede reenviar a ciegas.
    try:
        with database.session() as connection:
            armed = delivery.arm(connection, claim)
    except Exception:  # noqa: BLE001 - SES todavia no fue invocado
        logger.exception("could not arm notification delivery")
        return True
    if armed != "armed":
        return True

    try:
        provider_ref = adapter.deliver(
            recipient=recipient, template_code=claim.template_code,
            locale=claim.locale, context=claim.render_context,
            idempotency_key=claim.idempotency_key,
        )
    except DeliveryError as error:
        outcome = error.failure_class
        provider_ref = None
        reason = error.code
    except Exception:  # noqa: BLE001 - pudo ocurrir despues de entregar a SES
        # Si no se conoce en que punto fallo el SDK, reenviar podria duplicar el
        # correo. Se manda a conciliacion manual como resultado incierto.
        outcome = "uncertain"
        provider_ref = None
        reason = "provider_outcome_unknown"
        logger.error("unexpected provider boundary failure; outcome uncertain")
    else:
        outcome = "sent"
        reason = None

    try:
        with database.session() as connection:
            state = delivery.settle(
                connection, claim, outcome=outcome,
                provider_message_ref=provider_ref, reason_code=reason)
    except Exception:  # noqa: BLE001
        # Nunca se reenvia aqui: el arm durable ya dejo la fila uncertain.
        # SES conserva la etiqueta estable para una conciliacion humana.
        logger.exception("could not persist notification outcome")
        return True
    log_event(
        logger, logging.INFO, "notification.delivery.finished",
        job_id=claim.delivery_id, outcome=state,
    )
    return True


def main() -> int:
    global _running
    settings = load_settings()
    configure_observability(settings.service_name, settings.log_level)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log_event(
        logger, logging.INFO, "notification_worker.starting",
        environment=settings.env, release_id=settings.release_id,
        outcome=settings.notification_provider,
    )

    if settings.notification_provider == "disabled":
        while _running:
            beat()
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)
        return 0

    protector, adapter = build_delivery_clients(settings)
    database = Database(settings)
    identity = f"{settings.service_name}-{os.getpid()}"
    last_beat = 0.0
    try:
        while _running:
            now = time.monotonic()
            if now - last_beat >= HEARTBEAT_INTERVAL_SECONDS:
                beat()
                last_beat = now
            if not process_one(database, protector, adapter, identity):
                time.sleep(IDLE_SLEEP_SECONDS)
    finally:
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
