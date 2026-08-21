---
task: FNC-ARC-002
status: REVIEW_PENDING
base_sha: 7a22ada
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-ARC-002

## Entrega

- DFD explicativo con siete zonas de confianza y secuencias de ingesta/exportación.
- Catálogo JSON ejecutable con seis clasificaciones, nueve stores aprobados, 12 amenazas, 21 controles y 14 pruebas negativas nominales.
- Trece flujos F01–F13; cada uno declara actor, propósito, path, company scope, clases, protocolo, autenticación, cifrado, persistencia, retención/borrado, logs permitidos, egress, amenazas, controles, pruebas, autoridad, degradación y owner de rol.
- Invariantes específicas para quarantine, workers sin egress/autoridad canónica, completitud/linaje, SoD/dinero, exports reautorizados, AI Gateway, webhooks, auditoría, delete ledger, restore y revocación.
- Validador Python sin dependencias externas y 13 pruebas de mutación.
- CI ampliado para validar el DFD en cada push/PR.

## Verificación

```powershell
python -m tools.dfd_model.validate
python -m unittest tools.dfd_model.test_validate -v
python -m unittest discover -s tools -p "test_*.py"
python -m tools.quality_gate.cli
python -m tools.synthetic_corpus.cli verify --root tests/golden/synthetic
```

Resultado observado antes de integración:

- Modelo DFD: PASS, 0 errores.
- Pruebas DFD: 13/13 PASS.
- Suite Python combinada: 39/39 PASS.
- Kernel de autorización en Node fijado: 61/61 PASS.
- Stack spike: Compose válido; npm audit 0 vulnerabilidades; typecheck PASS; API 5/5 y worker 3/3 PASS.
- Workflow YAML y `git diff --check`: PASS.
- Quality gate: 0 hallazgos; corpus: 5/5 verificado con dos advertencias de fórmula inerte intencional.
- No se usó red, proveedor externo ni dato real para construir o validar el modelo.

## Decisiones preservadas

- Company permanece como frontera financiera estable y se resuelve server-side.
- `prohibited` no puede entrar a ningún flujo; secretos se mantienen en vault/protocolo.
- Worker aislado retorna manifiesto y no publica estado canónico.
- IA externa cruza Z5/AI Gateway, recibe información minimizada y no decide dinero, acceso, match o cierre.
- Delete ledger vive fuera del restore ordinario; restore reaplica tombstones antes de abrir servicio.
- Valkey y analytics no son autoridad financiera.
- No se eligió cloud, región, IdP, antivirus, OCR, proveedor IA, cola ni política numérica de retención.

## Riesgos y pendientes

- Architecture, Security y Privacy deben revisar y aceptar; el implementador no sustituye esa independencia.
- FNC-SEC-002 debe convertir los IDs de amenaza en riesgo inherente/residual, tratamiento, owner y fecha.
- FNC-PRV-001 debe resolver finalidad/base, región, transmisiones, subencargados, minimización y vínculo con L-01/L-02.
- L-01 todavía debe fijar plazos por clase/store/evento; los IDs actuales son referencias, no duraciones aprobadas.
- S-01 debe fijar detección de PAN antes de raw y manejo del rechazo.
- A-02 debe fijar topología/región sin relajar Z5/Z6.
- Los contratos son de arquitectura E0; no constituyen implementación productiva.

## Rollback

Restaurar `DFD.md`, retirar `dfd-flows.json`, `tools/dfd_model`, su paso CI y este handoff. No existen migraciones, despliegues ni datos reales.

Esta entrega no supera S1-READY ni autoriza DRG-00.
