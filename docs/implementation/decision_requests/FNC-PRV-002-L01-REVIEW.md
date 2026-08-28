# Solicitud de adjudicación humana L-01 — FNC-PRV-002

## Decisión solicitada

Completar las 19 filas de `retention-deletion-matrix.json` con plazos en días
calendario, fundamento, contrato, excepciones, vigencia y evidencia. No editar
el privacy-map para acomodar una conclusión: un cambio de hechos técnicos exige
su propia revisión de contrato y digest.

Esta solicitud no permite cargar datos reales. Aun una L-01 válida deja
DRG-00/DRG-01 cerrados hasta completar todos sus demás controles.

## Responsables nominales requeridos

- Legal: abogado colombiano distinto de `FOUNDER-01`; decide fundamento y plazo.
- Privacy: finalidades, derechos, minimización, supresión y derivados.
- Security: hold, tombstones, archivo, backups, restore y evidencia.
- Accounting: eventos de inicio de evidencia financiera y cierres.

Los cuatro aliases deben corresponder a personas distintas. El Founder conserva
accountability provisional, pero no cuenta como revisor independiente.

## Preguntas por fila

1. ¿Qué evento inicia el reloj y qué evento lo reinicia o suspende?
2. ¿Qué plazo exacto en días debe configurar la plataforma?
3. ¿Qué norma, obligación, política o contrato sustenta el plazo?
4. ¿Qué excepción y qué legal hold aplican, con quién puede activarse?
5. ¿Qué derivados, exports, cachés, dispositivos y terceros deben purgarse?
6. ¿Qué evidencia demuestra purga y quién reconcilia el inventario?
7. ¿Qué ocurre en backup y qué debe verificarse antes de un restore?

## Condiciones especiales

- Confirmar el inicio de `L-01-FINANCIAL` en el último asiento/documento
  relacionado, no en la fecha de upload.
- El plazo de `L-01-DELETE-LEDGER` debe ser estrictamente mayor al de
  `L-01-BACKUP`.
- Adjudicar expresamente las cinco políticas hoy `pending_contract` y la política
  L-02-AI-CALL, sin que ello habilite IA externa.
- No declarar supresión completa si queda una copia activa no justificada.

## Evidencia de salida

- Alias y competencia del abogado; fecha y referencia externa del concepto.
- Una decisión y evidencia por cada una de las 19 políticas.
- Vistos buenos distintos de Legal, Privacy, Security y Accounting.
- Registro de discrepancias y condiciones de implementación.
- Confirmación separada de que DRG-00/DRG-01 continúan cerrados.

No introducir PII, firmas, contratos, documentos financieros, URLs con tokens o
credenciales en el repositorio. El Integration Steward trasladará únicamente
metadatos no secretos después de verificar la evidencia externa.
