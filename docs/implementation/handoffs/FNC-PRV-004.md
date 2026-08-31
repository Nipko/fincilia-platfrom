---
id: FNC-PRV-004
status: REVIEW_PENDING
base_sha: 4d84858
data_ceiling: synthetic_only_until_DRG-01
---

# Entrega

El recorrido `RW-DELETE`/`RW-COMPLAINT` quedó ligado al mapa de privacidad y
ejercitado con doce controles completamente sintéticos. La evidencia solo lleva
referencias opacas y SHA-256; no contiene nombres, correos, montos ni contenido.

# Resultados

- Solicitud, identidad, autoridad y empresa resueltas antes de actuar.
- Incidente conserva `detected_at`, `aware_at` y `confirmed_at` por separado.
- Evidencia preservada antes de revocar/remediar; acceso stale denegado.
- Tombstone antes de purge; repetición idempotente e inventario reconciliado.
- Restore no queda ready hasta reaplicar tombstones.
- Cierre exige respondedor, aprobador y post-revisor distintos en el fixture.
- `notification_decision=pending_legal`; datos reales siguen deshabilitados.

# Verificación

```text
PYTHONPATH=packages/contracts/python python -m unittest tools.rights_incident_drill.test_drill -v
PYTHONPATH=packages/contracts/python python -m tools.rights_incident_drill.cli
python -m tools.drg01_readiness.validate
```

# Pendientes no ocultos

Repetir el drill en el entorno AWS protegido, aceptar L-01, fijar plazos y
excepciones por jurisdicción y obtener revisión independiente Privacy/Legal,
Security y QA. Ninguna de esas decisiones fue simulada.
