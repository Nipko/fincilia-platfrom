---
task_id: FNC-LEG-001
status: REVIEW_PENDING
base_sha: e446d1ddc77102ba1464615cfbbb2f0e5dec5d7e
reservation_sha: cbdf5a1
implementation_sha: c0c5cb8
tested_head_sha: c0c5cb8d530e8c1547991fcbb956eae5440fe9dd
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [abogado colombiano nominal, Privacy, Security]
---

# Handoff FNC-LEG-001 — plantilla ejecutable de tratamiento

## Resultado

Quedó estructurado el paquete que debe recibir un abogado colombiano distinto
de `FOUNDER-01` antes del primer corpus real. El modelo descubre directamente
del mapa de privacidad las 11 actividades dirigidas a DRG-00 o DRG-01, exige
16 secciones y conserva abiertas A-02, L-01, `UD-ROLE` y `UD-PROVIDERS`.

El reporte válido significa `ready_for_lawyer_review: true`; nunca significa
aprobación. En la misma salida se fijan `real_data_authorized: false`,
`human_approval: false` y `aggregate_score: null`. No se recibió, generó ni
versionó información personal o financiera real.

## Artefactos

- `docs/legal/treatment-agreement-template.json`: contrato fail-closed.
- `docs/legal/TREATMENT_AGREEMENT_TEMPLATE.md`: guía legible de revisión.
- `tools/legal_treatment`: validador, reporte y 26 pruebas adversariales.
- `docs/implementation/decision_requests/FNC-LEG-001-LEGAL-REVIEW.md`:
  solicitud y evidencia mínima para los revisores nominales.

La extracción dinámica cubre PA-04/05/15/22/23 para DRG-00 y
PA-03/08/10/13/16/17 para DRG-01. Añadir otra actividad real al privacy-map sin
añadir su tratamiento hace fallar el modelo.

## Hallazgo adversarial corregido

La primera validación de fuentes usaba un sufijo de hostname. Un dominio como
`evilsic.gov.co` habría parecido oficial. La allowlist ahora compara hosts
exactos, rechaza credenciales/puertos en la URL y fija el esquema permitido;
una prueba específica mata la suplantación.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| `python3 -B -m unittest tools.legal_treatment.test_model` | 26/26 OK |
| `python3 -B -m tools.legal_treatment validate` | exit 0, 0 findings |
| `python3 -B -m tools.legal_treatment report` | 11 actividades, 16 secciones, no autorización |
| `python3 -B -m tools.quality_gate.cli` sobre índice | OK, 0 findings |
| `git diff --cached --check` | OK |

Las mutaciones cubren aprobación prematura, elevación de datos, asesoría
autoatribuida, fuente impostora, texto copiado, sección omitida, actividad
omitida o reclasificada, deriva dinámica, rol, región, proveedor, retención,
decisión, firma humana y gate adulterados.

## Fuentes y límite jurídico

Se versionaron referencias a SUIN y SIC consultadas el 2026-08-28 para que el
abogado evalúe Ley 1581, tratamiento, transferencia/transmisión y circulación
internacional. No se copió texto extenso ni se produjo una conclusión jurídica.
Los documentos son insumos; no sustituyen asesoría ni firma profesional.

## Revisión obligatoria y bloqueos

1. Abogado colombiano independiente: rol y aplicabilidad por actividad, partes,
   base, instrucciones, derechos, contrato y fundamento nominal.
2. Privacy: categorías, minimización, derechos, retención, derivados, backups y
   supresión.
3. Security: controles, incidentes, subencargados, restore y auditoría.
4. Integration Steward: después de esas revisiones, trasladar conclusiones a
   A-02 y L-01 sin modificar silenciosamente sus contratos.

`FOUNDER-01` continúa como accountable provisional, pero no satisface la
independencia. DRG-00 y DRG-01 permanecen `not_met`; por tanto aún no debe
cargarse ningún dato real en la plataforma ni en el repositorio.

## Rollback

La entrega sólo agrega documentación y una herramienta offline sin
dependencias. Revertir `c0c5cb8` elimina el paquete y `cbdf5a1` elimina su
reserva; no existen migraciones, estado productivo, flags ni datos que restaurar.
