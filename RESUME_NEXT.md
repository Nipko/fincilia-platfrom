# Dónde retomar

| Campo | Valor |
|---|---|
| Rama | `claude/principal-dev` |
| Base de esta ejecución | `5aa8c53` |
| Migraciones añadidas | `V0012` — `V0001`–`V0011` con su checksum intacto |
| Rutas nuevas | overrides de linaje (listar, crear, aprobar) y miembros asignables |
| ADR propuesta | ADR-024 — actualizada, **sigue `Proposed`** |
| Gate S1-READY | sigue `not_met`, y nada de esto lo mueve |

---

## 1. Levantar el stack

```bash
sh infra/local/up.sh
```

> **Si tu volumen local es anterior a `V0005`**, recréalo primero con
> `docker compose -f infra/local/compose.yaml -p fincilia-local down --volumes`.
> Los roles nuevos los crea el bootstrap, que sólo corre sobre un volumen vacío.

Y una cosa que **hay que hacer una vez** antes de poder publicar:

```bash
docker compose -f infra/local/compose.yaml -p fincilia-local --profile migrate run --rm migrate python -m db.admin.releases approve --release fnc-p3-mapping-0.1.0 --actor "tu.nombre" --ref "ACTA-LOCAL" --rationale "entorno sintetico local"
```

No es burocracia de demo. Publicar afirma que algo se puede reproducir, y esa
afirmación se apoya en una versión del motor que alguien miró. La semilla la deja
en `draft` a propósito: aprobar es una decisión humana, y ni el agente ni el
sembrador la toman por ti. Antes de firmar, `show --release ...` enseña qué
componentes y qué digests estás aprobando.

---

## 2. Qué hay ahora

El detalle está en [el handoff](docs/implementation/handoffs/FNC-P3.6.md). En
corto, cuatro de las cinco divergencias que P3.5 dejó declaradas:

| Antes | Ahora |
|---|---|
| seis tablas sin contrato que dijera de quién eran | cada una bajo su autoridad, y `DOM-FOREIGN-AUTHORITY` impide meterlas en el modelo financiero por comodidad |
| ADR-024 no contestaba qué pasa con la fila que no sigue el plan | `lineage_row_override`: siete clases, huellas sin valores, autor ≠ aprobador, intercalado en su posición lógica |
| la extracción cargaba el fichero entero | generador real: 100.000 filas en 110,9 s, 193,7 MiB de pico y **52,0 de crecimiento** |
| el desplegable de responsables listaba sólo a quien tenía sesión | endpoint de miembros elegibles con las tres condiciones del autorizador |

Y `accounting_date` sigue nula **a propósito**, ahora con nueve pruebas que
impiden inferirla de `occurrence_date` o `posting_date`.

---

## 3. Dos cosas que costaron una vuelta

**Un permiso que no existe no deniega selectivamente: deniega todo.** La ruta de
overrides pedía `dataset.prepare`, que no es un permiso de este sistema —quien
prepara tiene `dataset.map`—. Doce pruebas contra PostgreSQL real recibieron 403
donde esperaban 201, y que las doce fallaran a la vez por lo mismo fue la señal
útil.

**Un contrato puede describir un sistema que no existe.** `lineage-model.json`
nombra tablas físicas y ningún validador lo cruzaba: el de linaje mira la forma
del contrato y el de migraciones mira el SQL. Ahora `cross-contract` los cruza.

---

## 4. La siguiente rebanada, exacta

1. **Preparación en el worker.** Hoy la API prepara con presupuesto de tiempo y
   devuelve `202` para que el llamante continúe. Funciona y es honesto, pero un
   trabajo de minutos pertenece a la cola, no a una petición HTTP. La cola admite
   un tipo nuevo sin tocar el despachador: basta añadirlo a las **tres** listas, y
   hay una prueba que comprueba que coinciden.
2. **`accounting_date` en P4.** Periodo contable, reglas y revisión humana. Está
   blindada para que nadie la invente antes.
3. **Exportación del dataset publicado.** Un conjunto canónico que no se puede
   sacar obliga a mirarlo por pantalla.
4. **Pantalla de overrides.** La API los crea, aprueba y lista, y el drill-down
   los enseña; no hay interfaz para escribirlos.
5. **Formatos que no son CSV.** Un libro de cálculo sigue quedándose en
   cuarentena con `no_scanner_for_format`, y eso es correcto.

Nada de auto-match, conciliación, fraude por ML, cierre ni IA autoritativa.

---

## 5. Lo que sigue esperando a una persona

Ninguno se ha movido y ninguno se ha marcado como aceptado.

- **Aprobación real de `engine_release`** en cualquier entorno que no sea el
  local sintético: exige `approval_ref`, `result_diff_report` y revisión
  independiente, y es de `human_platform_owner`.
- **ADR-024**, `Proposed` y registrada `blocked`. Falta ratificación de Data y
  Architecture.
- **Re-adjudicación del registro dorado y del de mutaciones.** Los digests de
  entrada se re-anotaron porque los ficheros cambiaron de verdad —paso 2 del
  procedimiento—; el **paso 3**, revisión independiente por quien no tocó el
  contrato, sigue pendiente. Ninguna expectativa se movió.
- **Adopción o descarte formal de la ruta `COPY`/temporal.** El spike mide y
  comprueba; adoptar es una decisión que se toma leyendo los números.
- **Vault o KMS** para `FINCILIA_IDENTIFIER_TOKENIZATION_KEY` fuera de local. Hoy
  el validador levanta si `env` no es `local` ni `test`, que es la trampa para el
  día que alguien añada `staging`.
- **DB-G03**: cuatro funciones `SECURITY DEFINER` con `human_review_state:
  pending`.
- **DRG-01**: la excepción de RLS de `dispatch_pointer` sigue ampliada.
- **S-01 / TM-005**: detección de PAN antes de `raw`. Sin resolver.
- **ADR-002**: sigue `proposed`, sin herramienta seleccionada.
- **`retry_policy_contract`**: trece campos declarados, incluidos `owner` y
  `reviewer` independientes, que no se han inventado.
- Cuatro huecos de cadena de suministro (SBOM, firma, attestation, procedencia) y
  seis alcances OCI sin monitor, como estaban.

---

## 6. Divergencias declaradas

Las cinco están en la [sección 9 del handoff](docs/implementation/handoffs/FNC-P3.6.md).
La que más pesa: **el modelo canónico dice `uuid_v7` y las migraciones usan
`gen_random_uuid()`** en las veintidós entidades. Es anterior a P3.6 y ningún
validador lo cruza, así que hoy nadie se enteraría de que divergen.
