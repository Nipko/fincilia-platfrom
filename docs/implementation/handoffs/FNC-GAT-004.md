# Handoff — FNC-GAT-004: relevancia explícita de contradicciones en el agregador S1

| Campo | Valor |
|---|---|
| Tarea | FNC-GAT-004 |
| Estado | **`REVIEW_PENDING`** |
| Base | `81f7dd9` (`main`), rama `claude/principal-dev` |
| Owner | Integration Steward |
| Revisores independientes | Architecture, Security, QA |
| Gate | S1-READY — sigue `not_met` |

---

## 1. Hallazgo que motiva la tarea

En `81f7dd9`, la función `no_contradiction` del agregador calculaba así el conjunto de
gates cuya contradicción bloquea:

```python
relevant_gates = {target_gate}
relevant_gates.update(r["ref"] for r in requirements if r["kind"] == "gate")
```

La integración de la Ola A/B retiró **todos** los requisitos de tipo `gate`. Comprobado
sobre el árbol real:

```
requisitos kind=gate: 0
relevant_gates efectivo: ['S1-READY']
contradicciones detectadas: 2  (DRG-00 owner_role Legal/Security, DRG-01 idem)
REQ-NO-CONTRADICTION -> machine_pass
```

Es decir: el agregador reportaba dos contradicciones reales y **no bloqueaba por ninguna**,
no porque alguien decidiera que los gates de datos no condicionan S1, sino porque el
conjunto de relevancia quedó vacío como efecto colateral de retirar unos requisitos.

Que `DRG-00` y `DRG-01` no bloqueen S1-READY es defendible —son gates posteriores—. Que eso
ocurra sin que nadie lo haya declarado, no.

## 2. Qué cambia

1. **La relevancia se declara**, no se deduce. Nuevo bloque `contradiction_relevance` con
   `gates`, `owner_slots_from_requirements` y `rationale` obligatorio.
2. **El silencio deja de ser una resolución.** Una contradicción que no es relevante para
   S1-READY solo sale de los blockers si está **enrutada**: con `owner_role`, `gate`,
   `reason` y `blocks_gate: true`. Si nadie la enruta, bloquea.
3. **Enrutar no resuelve.** El validador rechaza `blocks_gate: false` y rechaza que una
   ruta apunte al propio gate objetivo. Una contradicción enrutada sigue bloqueando *su*
   gate y conserva quién debe adjudicarla.
4. **El informe expone el triaje**: `contradiction_triage` con `blocking`, `acknowledged`
   y `unrouted`, y `explain` lo arrastra.

Las dos contradicciones observadas quedan enrutadas a **Integration Steward**, con
revisores **Legal** y **Security**, bloqueando `DRG-00` y `DRG-01` respectivamente.

## 3. Rutas modificadas

| Ruta | Cambio |
|---|---|
| `tools/s1_readiness/evaluate.py` | `triage_contradictions()` con relevancia declarada; `contradiction_triage` en el informe |
| `tools/s1_readiness/model.py` | reglas `S1R-CONTRADICTION-RELEVANCE` y `S1R-CONTRADICTION-ROUTE` |
| `docs/implementation/s1-readiness.json` | `contradiction_relevance`, `acknowledged_contradictions`, nueva anti-promesa |
| `tools/s1_readiness/test_validate.py` | 10 pruebas nuevas; una existente extendida |
| `docs/implementation/S1_READINESS_REPORT.md` | sección de triaje |
| `docs/implementation/BACKLOG_PHASE_0.md` | fila FNC-GAT-004 |
| `docs/implementation/tasks/FNC-GAT-004.md` | ficha |

## 4. Prueba existente modificada — y por qué

`test_neg_09d_a_later_gate_contradiction_is_reported_but_not_an_s1_blocker`, añadida
durante la integración, afirmaba que una contradicción de gate posterior queda
`machine_pass`. Bajo la regla nueva eso solo es cierto **si está enrutada**.

La prueba se extendió para cubrir ambos lados en vez de relajarse: sin enrutar →
`contradiction` y aparece en `unrouted`; enrutada → `machine_pass`, con `routed_to_owner` y
`blocks_gate` verificados. No se borró ninguna aserción; se añadió la que faltaba.

## 5. Verificación

| Comando | Exit | Resultado |
|---|---:|---|
| `python -m unittest tools.s1_readiness.test_validate` | 0 | **98 pruebas, OK** (antes 88) |
| `python -m tools.s1_readiness.cli validate` | 0 | contrato válido |
| `python -m tools.s1_readiness.cli evaluate` | 10 | gate `not_met`, 10 blockers, triaje 0/2/0 |
| `python -m tools.quality_gate.cli` | 0 | política de repositorio |
| `python -m tools.work_graph.validate` | 0 | 58 tareas, sin huérfanos |
| `python -m tools.test_catalog.cli validate` | 0 | sin drift bloqueante |
| `python -m tools.golden_harness.cli verify` | 0 | registro golden íntegro |
| `python -m tools.mutation_harness.cli verify` | 0 | registro de mutaciones íntegro |

Pruebas negativas que muerden: relevancia ausente, conjunto vacío, gate objetivo ausente
de su propia relevancia, rationale vacío, ruta sin owner/gate/reason/subject/field,
`blocks_gate: false`, ruta apuntando al gate objetivo, y una prueba que demuestra que
retirar requisitos ya **no** cambia qué contradicción bloquea.

## 6. Lo que no cambia

- S1-READY sigue `not_met` con 10 blockers y aceptación `pending_human`.
- Las dos contradicciones **siguen sin resolverse**: ahora tienen owner y gate, que es
  distinto de estar resueltas.
- Ningún gate humano se marca `met`; ningún ADR se acepta.

## 7. Decisión que corresponde a un humano

`DRG-00` y `DRG-01` tienen owner divergente entre `docs/privacy/privacy-map.json` (Legal) y
`docs/domain/lineage-model.json` (Security). **Integration Steward**, con Legal y Security,
debe adjudicar cuál fuente queda como autoritativa y corregir la otra. Hasta entonces no
está definido quién puede aprobar esos dos gates de datos.
