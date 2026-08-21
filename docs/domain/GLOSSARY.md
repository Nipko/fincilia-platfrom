# Glosario canónico v0

- Estado: Draftable
- Tarea: FNC-DAT-001

| Término | Nombre en código | Definición |
|---|---|---|
| Sujeto | subject | Persona lógica estable, independiente de credenciales |
| Identidad | user_identity | Credencial OIDC/passkey de un subject |
| Organización | organization | Contenedor administrativo de firma, BPO o PYME |
| Empresa | company | Frontera financiera permanente |
| Relación profesional | engagement | Delegación revocable organización–empresa |
| Permiso | grant | Acción explícita, vigente y condicionada |
| Principal de servicio | service_principal | Actor no humano |
| Artefacto fuente | source_artifact | Recepción lógica de un archivo/mensaje |
| Versión de artefacto | artifact_version | Binario inmutable con hash/version_id |
| Registro crudo | raw_record | Extracción fiel |
| Registro de origen | source_record | Evidencia publicada desde una fuente |
| Movimiento económico | money_movement | Evento financiero canónico |
| Vínculo de evidencia | movement_evidence_link | Relación entre evidencias y movimiento |
| Candidato de dedupe | dedupe_candidate | Sospecha; no eliminación |
| Versión de dataset | dataset_version | Resultado de extracción, receta, overlay y esquema |
| Localizador | origin_locator | Ubicación exacta en el original |
| Arista de linaje | lineage_edge | Transformación o dependencia |
| Completitud | completeness_assessment | verified, mismatch, unknown o accepted_exception |
| Estado conciliatorio | reconciliation_statement | Ecuación de saldo y partidas |
| Snapshot cerrado | closed_snapshot | Cierre reproducible e inmutable |
| Release de motor | engine_release | Código/artefacto verificable que produjo resultados |

## Términos prohibidos o ambiguos

- Tenant sin precisar organization o company.
- Movimiento para source_record y money_movement indistintamente.
- Duplicado para dedupe_candidate.
- Completo para unknown.
- Cuadrado si el statement de saldos no da cero.
- Fraude para una señal de riesgo.
- Owner sin precisar dueño administrativo, legal, de activo o de dato.

