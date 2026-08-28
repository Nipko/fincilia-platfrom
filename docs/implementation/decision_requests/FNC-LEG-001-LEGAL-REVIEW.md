# Solicitud de revisión jurídica independiente — FNC-LEG-001

## Decisión solicitada

Revisar y completar fuera de Git el acuerdo aplicable al corpus de
investigación y al futuro piloto. Registrar en el contrato versionado sólo los
alias, estados, conclusiones acotadas y referencias externas no secretas.

Esta solicitud **no autoriza datos reales**. Hasta que todos los controles del
gate correspondiente se satisfagan, sólo se usan fixtures completamente
sintéticos.

## Revisor requerido

- Abogado colombiano distinto de `FOUNDER-01`, con competencia verificable en
  protección de datos y contratación tecnológica.
- Privacy revisa finalidades, categorías, derechos, retención y supresión.
- Security revisa medidas, incidentes, subencargados, restore y auditoría.

El Founder es accountable provisional, pero no puede ser la revisión
independiente de su propia postura.

## Material de entrada

- `docs/legal/TREATMENT_AGREEMENT_TEMPLATE.md`
- `docs/legal/treatment-agreement-template.json`
- `docs/privacy/privacy-map.json`
- `docs/architecture/REGION_TRANSMISSION_DECISION.md`
- `docs/security/THREAT_MODEL.md`

No adjuntar extractos, nombres de clientes, PII, credenciales ni documentos
financieros al issue, PR, commit o prompt de revisión.

## Preguntas obligatorias

1. ¿Qué rol y base corresponden a Fincilia en cada actividad PA cubierta?
2. ¿Qué documento contractual aplica al corpus DRG-00 y al piloto DRG-01?
3. ¿Qué partes instruyen, reciben solicitudes de titulares y responden?
4. ¿Qué región, transmisión, transferencia y subencargados son admisibles?
5. ¿Qué evento inicia cada plazo y qué ocurre con derivados y backups?
6. ¿Qué medidas, evidencia, incidentes y derechos deben pactarse?
7. ¿Qué excepciones, cambios y terminación requieren nueva aprobación?

## Evidencia de salida

- Alias nominal del abogado independiente y fundamento profesional.
- Fecha, versión y referencia externa inmutable del concepto.
- Matriz por actividad con rol y aplicabilidad.
- Adjudicación o remisión explícita de `UD-A-02`, `UD-L-01`, `UD-ROLE` y
  `UD-PROVIDERS`.
- Vistos buenos nominales de Legal, Privacy y Security.
- Lista de condiciones todavía bloqueantes para DRG-00 y DRG-01.

La respuesta no debe marcar gates como superados. El Integration Steward
consolida la evidencia en una tarea posterior y el owner nominal del gate toma
la decisión final.
