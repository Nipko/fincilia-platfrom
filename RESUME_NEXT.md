# Dónde retomar

| Campo | Valor |
|---|---|
| Rama | `claude/principal-dev` |
| Base de esta ejecución | `31e791a` |
| Migraciones añadidas | `V0009`, `V0010`, `V0011` — `V0001`–`V0008` con su checksum intacto |
| Permisos nuevos | `financial_account.manage`, `data_source.manage` |
| ADR propuesta | ADR-024 — representación lógica y física del linaje |
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

El detalle está en [el handoff](docs/implementation/handoffs/FNC-P3.5.md). En
corto, tres cosas que P3 dejó abiertas:

| Antes | Ahora |
|---|---|
| una release en borrador podía publicar | preparar y publicar exigen `approved`, con constancia de quién firmó y digest de lo firmado |
| no había alta de cuentas ni de fuentes | pantalla de onboarding con cuentas, fuentes, vínculos tipados y ciclos esperados |
| el linaje crecía por fila × campo | las seis etapas viven en un plan por columna; **24 nodos** para 100.000 filas |
| techo de 10.000 filas | 100.000 medidas en CI: 11,2 s de preparación, 50 lotes, 81,3 MiB de pico |

Y un defecto de P3 que salió revisando: una lectura truncada terminaba bien
—`truncated` es un estado, no un fallo— y la preparación no lo miraba. Un fichero
cortado por el límite de tiempo podía publicarse como completo.

---

## 3. Tres cosas que costaron una vuelta

**`COPY FROM` no funciona bajo seguridad por filas.** Era la pieza central del
diseño de escala y PostgreSQL simplemente no lo admite sobre una tabla con RLS.
Se cambió por sentencias multifila de 500. Entre perder el aislamiento y perder
velocidad, se pierde velocidad.

**Un CHECK de V0008 hacía imposible retirar una release.** Decía «sólo una
aprobada tiene referencia de aprobación», y al pasar a `superseded` la referencia
sigue ahí porque tiene que seguir. El error estaba en el enunciado, no en el
estado: `V0010` lo corrige.

**Una función nueva nace ejecutable por `PUBLIC`.** Los privilegios por defecto
de V0005 no se aplicaron al disparador de V0009, y un `proacl` nulo significa el
valor por defecto del motor. Lo delató la misma prueba que en V0005 destapó que
un `REVOKE` de quien no es dueño avisa y no hace nada.

---

## 4. La siguiente rebanada, exacta

**La extracción sigue sin ser streaming, y es el cuello que queda.** La
publicación se rediseñó por lotes; leer el fichero no. `extraction.py` construye
la lista completa de filas y `_LineFeeder` guarda dos listas más del fichero
entero. Medido en CI: 55,2 s para 100.000 filas, **a cinco segundos** del límite
declarado de 60 s. Con 150.000 filas se trunca, y truncar ahora bloquea la
publicación, que es correcto pero no es lo que uno quiere descubrir en
producción.

Lo que hay que hacer, por orden:

1. **Extracción incremental.** `extract()` debería emitir filas en vez de
   devolverlas todas, y el worker escribirlas por tandas según llegan. La
   coordenada de bytes ya se calcula por registro, así que el cambio es de forma,
   no de fondo.
2. **Preparación en el worker.** Hoy la API prepara con presupuesto de tiempo y
   devuelve `202` para que el llamante continúe. Funciona y es honesto, pero un
   trabajo de minutos pertenece a la cola, no a una petición HTTP. La cola ya
   admite un tipo nuevo sin tocar el despachador: basta añadirlo a las **tres**
   listas, y hay una prueba que comprueba que coinciden.
3. **Exportación del dataset publicado.** Un conjunto canónico que no se puede
   sacar obliga a mirarlo por pantalla.
4. **Lectura de miembros de la empresa.** El desplegable de responsables del
   ciclo lista sólo a quien tiene sesión, porque no hay endpoint que devuelva los
   miembros.
5. **Formatos que no son CSV.** Un libro de cálculo sigue quedándose en
   cuarentena con `no_scanner_for_format`, y eso es correcto.

Nada de auto-match, conciliación, fraude por ML, cierre ni IA autoritativa.

---

## 5. Lo que sigue esperando a una persona

Ninguno se ha movido y ninguno se ha marcado como aceptado.

- **Aprobación real de `engine_release`** en cualquier entorno que no sea el
  local sintético: exige `approval_ref`, `result_diff_report` y revisión
  independiente, y es de `human_platform_owner`.
- **ADR-024**, `Proposed` y registrada `blocked`. Propone separar la
  representación lógica del linaje de la física; falta ratificación de Data y
  Architecture y la enmienda del contrato ejecutable.
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

Las cinco están en la [sección 9 del handoff](docs/implementation/handoffs/FNC-P3.5.md).
La que más pesa: **seis tablas nuevas no están en `canonical-model.json`**, porque
añadirlas exige editar la lista de entidades del validador, que es la guarda
contra la deriva accidental del modelo. Hacerlo en silencio la volvería inútil, y
por eso lo propone ADR-024 en vez de darlo por hecho.
