# Handoff FNC-DAT-001

- Estado: PARTIAL — borrador completo; no puede pasar a Accepted sin dependencia y revisiones humanas.
- Agente: `/root/impl_arch_data` (lane A5 DataQA)
- Accountable owner: UNASSIGNED
- Revisores requeridos: Privacy y Accounting; Security para controles de hallazgo/archivos hostiles.
- Base SHA: No consultado por instrucción expresa de no usar Git; debe completarlo Integration Steward.
- Head SHA: No consultado por instrucción expresa de no usar Git; debe completarlo Integration Steward.
- Rama/worktree: Filesystem compartido; subagente sin operaciones Git.
- Objetivo y resultado: Taxonomía de fuentes/documentos/formatos/campos y política de datos por gate redactadas. Se definió un manifiesto reproducible para fixtures completamente sintéticos y un diseño, no autorización, de sanitización posterior a DRG-00.
- Paths modificados: `docs/domain/GLOSSARY.md`; `docs/testing/SYNTHETIC_DATA_POLICY.md`; este handoff.
- Paths reservados que se liberan: `docs/domain/GLOSSARY.md`; `docs/testing/SYNTHETIC_DATA_POLICY.md`; `docs/implementation/handoffs/FNC-DAT-001.md`.
- ADR/contratos afectados: No se modificó ningún ADR/contrato compartido. El vocabulario propuesto debe alimentar FNC-DOM-002..005 y FNC-ARC-002/005.
- Migraciones/eventos/flags: Ninguno.
- Decisiones y supuestos: Fuente, canal, familia documental, formato y template son dimensiones independientes. `source_record` es evidencia y `money_movement` el evento económico canónico. Anonimizado/saneado continúa siendo real derivado. Repo/local/dev/CI siguen sintéticos aun después de gates posteriores. La lista de formatos es taxonomía, no promesa de soporte.
- Riesgos de seguridad/privacidad/datos: El manifiesto no prueba por sí solo ausencia de datos reales; requiere generación reproducible, inventario de inputs, escaneo y revisor distinto. Identificadores numéricos generados podrían coincidir accidentalmente con terceros, por lo que no se consultan ni transmiten externamente. La sanitización descrita no está autorizada antes de DRG-00.
- Compatibilidad y consumidores: FNC-PRD-001 decide el wedge; FNC-DOM-002..005 consumen términos/tipos; FNC-ARC-002 consume clasificación y flujos; FNC-DAT-002/FNC-QA-003 implementan corpus, manifiestos y validación.
- Rollback: Restaurar las versiones anteriores de los dos borradores y retirar este handoff mediante Integration Steward. No hay datos, schema, migración ni estado persistente que revertir.
- Comandos ejecutados: `Get-Content` sobre reglas, fase, ownership, tarea, plan y documentos relacionados; `rg` para referencias/IDs; validadores PowerShell de fences/tablas/términos/hashes; `apply_patch` solo en rutas autorizadas. No se ejecutó Git.
- Resultado exacto de pruebas: `GLOSSARY.md`: 241 líneas, 18.569 bytes, 2 fences, 0 inconsistencias de tablas, SHA-256 `d1f80a66230915530ac45a0a2413efb6ff84853110a846b97c6fce8e5514c8fb`. `SYNTHETIC_DATA_POLICY.md`: 358 líneas, 16.781 bytes, 2 fences, 0 inconsistencias de tablas, SHA-256 `ded4699a7c2cc7ace753357627ff0f9a75e6470a6e6a2c74e49b57cfc3643be1`. Lista de 16 términos obligatorios: 0 ausentes. Marcadores `TODO`/`TBD`: 0.
- Evidencia: Glosario §§1 y 3–10; política §§2, 6–10 y 12–13; manifiesto ilustrativo en política §8.
- Fallos conocidos: No existe schema ejecutable ni linter de manifiestos; no se crearon fixtures; no hubo revisión humana independiente; la dependencia FNC-PRD-001 sigue Draftable.
- Trabajo pendiente con IDs: FNC-PRD-001 confirma el wedge; FNC-DAT-002 crea corpus/manifiestos sintéticos; FNC-DOM-002..005 consolidan el modelo; FNC-QA-003 implementa harness/linter determinista; FNC-ARC-002 incorpora clasificación al DFD.
- Bloqueos, owner y condición de desbloqueo: FNC-GOV-001 debe asignar Product, Accounting, Privacy y Security; FNC-PRD-001 debe fijar alcance provisional; Accounting y Privacy deben aprobar semántica y política. Hasta entonces FNC-DAT-001 permanece Draftable/PARTIAL.

## Declaración de alcance

No se crearon ni recibieron fixtures, documentos financieros, uploads, archivos
raw, datos de clientes o ejemplos derivados de datos reales. El ejemplo YAML es
solo una especificación documental y contiene placeholders que fallarían la futura
validación de un manifiesto real.
