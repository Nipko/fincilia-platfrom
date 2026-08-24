# Dónde retomar

| Campo | Valor |
|---|---|
| Rama | `claude/principal-dev` |
| Cierre técnico P3.6-R2 | `b481411` — push y carril manual verdes |
| Migraciones añadidas | `V0012`–`V0015` — `V0001`–`V0011` con su checksum intacto |
| Rutas nuevas | overrides de linaje (listar, crear, aprobar) y miembros asignables |
| ADR propuesta | ADR-024 — actualizada, **sigue `Proposed`** |
| Gate S1-READY | sigue `not_met`, y nada de esto lo mueve |
| Prioridad de producto | plataforma web primero; móvil queda al final |

Evidencia remota de cierre:

- push: https://github.com/Nipko/fincilia-platfrom/actions/runs/32695531220
- rendimiento al techo productivo: https://github.com/Nipko/fincilia-platfrom/actions/runs/32695925730

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
| la extracción cargaba el fichero entero | generador real y `COPY` a temporal: 100.000 filas en 94,2 s —17,1 de extracción, frente a 33,0 en P3.5— con 195,9 MiB de pico |
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

## 4. La siguiente rebanada, exacta: plataforma web

El siguiente bloque se registra como **FNC-P3.7 — endurecimiento verificable del
recorrido web P3**. La app móvil no participa en esta ruta crítica y se retoma
después de que la plataforma web complete conciliación, revisión e informes.

Orden de implementación:

1. **Confianza del recorrido actual.** El ciclo de una fuente se carga de verdad,
   se conserva al editar y el estado huérfano es alcanzable. El mapeo obliga a
   elegir visiblemente una fuente; nunca cae en `sourceRows[0]` ni pierde
   `sourceId` al navegar desde la carga.
2. **Carga contractual de 25 MiB.** Reemplazar el Server Action limitado por
   defecto a 1 MiB con un Route Handler/BFF de streaming y límite explícito.
   Mantener token y bytes fuera del navegador, logs y memoria no acotada; probar
   límite exacto y límite + 1.
3. **Estados y accesibilidad.** Separar 401, 403, 503, vacío exitoso y reintento;
   añadir `loading`, `error` y `not-found`, skip link, foco visible completo,
   captions/scope y `prefers-reduced-motion`.
4. **Navegación y volumen.** Conservar fuente, mapeo y página en query params;
   paginar o divulgar todos los topes de 25/50/100 registros.
5. **Verificación web.** Restaurar dependencias con `npm ci --ignore-scripts`,
   mantener versiones exactas, añadir pruebas de componentes y E2E/a11y en CI, y
   ejecutar build, typecheck y lint dentro de la imagen.
6. **Capacidad de negocio visible.** Después del endurecimiento: exportación de
   dataset publicado, pantalla de overrides y preparación larga en worker. Sólo
   entonces comienza el contrato P4 de completitud, candidatos deterministas,
   excepciones y `ready_to_close`.

Durante `PRE_SPRINT_1` no se habilitan auto-match, cierre, reporte certificado,
fraude por ML ni IA autoritativa. `accounting_date` sigue nula hasta su decisión
contable de P4.

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
- **Revisión de la adopción de la ruta `COPY`/temporal.** El spike midió, las
  diez comprobaciones salieron y el worker ya escribe por ahí. Lo que falta es
  que alguien de Security lea la propiedad en la que se apoya —`TEMPORARY` sobre
  la base es un privilegio que PostgreSQL concede a `PUBLIC` por defecto— y diga
  si le vale.
- **Vault o KMS** para `FINCILIA_IDENTIFIER_TOKENIZATION_KEY` fuera de local. Hoy
  el validador levanta si `env` no es `local` ni `test`, que es la trampa para el
  día que alguien añada `staging`.
- **DB-G03**: cinco funciones `SECURITY DEFINER` con `human_review_state:
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
