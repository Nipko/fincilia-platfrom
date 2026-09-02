# DRG-01 — piloto privado con datos reales

Este paquete convierte la intención “probar con mis propios datos” en una lista
cerrada de obligaciones. No autoriza una carga: el reporte permanece bloqueado
mientras falte una sola evidencia o revisión requerida.

## Alcance más pequeño útil

El primer piloto real empieza con una empresa del Founder y usuarios nominales.
Admite únicamente extractos, auxiliares y facturas propios en CSV, XLSX o PDF.
No admite tarjetas, nómina, documentos de identidad, salud, secretos, conectores,
correo, SFTP, webhooks, IA externa ni cierre automático.

Esta reducción limita el daño posible, pero no convierte los datos en sintéticos:
siguen sujetos a privacidad, seguridad, transmisión internacional, retención y
borrado.

## Secuencia obligatoria

1. Cerrar DRG-00: tratamiento, L-01, A-02, ambiente aislado, inventario,
   borrado, ensayo y revisión independiente.
2. Desplegar el entorno de piloto separado del host beta: HTTPS/WAF como única
   entrada, stores privados, KMS, Secrets Manager, CloudTrail y SSM sin SSH.
3. Activar IdP administrado, usuarios nominales, MFA y revocación; PostgreSQL
   continúa siendo la autoridad de empresa y rol.
4. Demostrar cuarentena, inspección, canales no usados deshabilitados, RLS y
   negaciones cross-tenant.
5. Ejercitar backup/restore con tombstones, derechos, incidente y rollback.
6. Obtener concepto PCI, DPA/subencargados, pentest e independientes nominales.
7. Solo entonces el gate puede derivar `real_data_authorized=true`.

## Verificación

```text
python -m tools.drg01_readiness.validate
python -m unittest tools.drg01_readiness.test_validate
```

El resultado válido hoy es `ok: true`, `DRG-01: not_met` y una lista explícita
de blockers. `ok` significa que el modelo no se contradice; no que el piloto
esté autorizado.

## Evidencia técnica DRG-00 — 2026-08-29

FNC-PLT-004, FNC-DAT-003, FNC-PRV-003 y FNC-QA-001 materializaron y ejercitaron
el laboratorio con fixtures completamente sintéticos. Los doce casos
`LAB-T01..T12` pasaron y el agregador verifica el digest y el mapeo antes de
contar inventario, borrado y drill. El aislamiento productivo permanece pendiente
hasta admitir una release firmada/provenanced y un IdP administrado.

G00-SUPPLY-CHAIN quedó adjudicado con un candidato sintético reproducible,
SBOM SPDX y procedencia SLSA firmados por OIDC, verificados dentro y fuera del
runner y ligados a los inputs actuales. DRG-00 permanece `not_met`: además de
los cuatro controles humanos sigue pendiente `G00-ISOLATED-ENV`. Por tanto el
techo continúa sintético y ninguna release está admitida para documentos reales.

## Evidencia técnica DRG-01 acotada — 2026-08-31

FNC-GAT-006 repitió 90 pruebas contra PostgreSQL 17 y MinIO y ligó por SHA-256
los selectores y fuentes que demuestran tres controles sin ampliar el techo de
datos:

- `D01-XTENANT`: RLS, empresa resuelta por servidor, revocación y contexto de
  autorización fallan cerrados.
- `D01-INGRESS`: todo aterriza en cuarentena; PAN, credenciales, contenido activo
  y formatos sin inspección completa no llegan a `raw`.
- `D01-CHANNELS`: email ingest, SFTP, conectores y webhooks no tienen rutas; IA,
  pagos y datos reales siguen deshabilitados en el runtime protegido.

FNC-PRV-004 añade un ensayo sintético de 12 pasos para derechos e incidente:
referencias opacas, verificación AAL, inventario, preservación digest-only,
revocación, tombstone, purga, restore cerrado y post-revisión separada. El flujo
mantiene notificabilidad, plazos, aplicabilidad y excepciones en `pending_legal`.

El gate permanece `not_met` con 13 blockers. Identidad en runtime protegido,
cloud, restore del entorno objetivo y las aprobaciones humanas no se infieren
de esta evidencia.
