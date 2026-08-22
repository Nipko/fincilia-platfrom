# Readiness de decisiones arquitectónicas

Estado: Review pending · Tarea: FNC-ARC-006 · Datos: solo sintéticos.

## Resultado

Los contratos actuales permiten continuar con documentación, prototipos, entorno local y
spikes. No autorizan todavía el código de producto con datos reales ni permiten marcar
`S1-READY`: ADR-002 sigue Proposed, ADR-020 está bloqueada por A-02 y todos los ADR core
conservan asignación humana pendiente.

El registro autoritativo para esta revisión es `adr-readiness.json`. No reemplaza los ADR;
los inventaría, vincula evidencia y hace explícito el alcance permitido y sus bloqueos.

## Semántica

- `documented`: decisión y evidencia suficientes para presentar a aprobación humana.
- `conditional`: puede guiar contratos o scaffolding, pero sus blockers impiden promoción.
- `blocked`: no habilita implementación productiva de su alcance.

Una palabra “Accepted” dentro de un ADR no supera por sí sola un gate. Para S1-READY se
requieren owners nominales, revisión independiente, evidencia resoluble y cero ADR core
bloqueado. Los agentes nunca cambian `human_acceptance` ni `release_rule.state` a aprobado.

## Lectura ejecutiva

| Grupo | Uso permitido | Bloqueo principal |
|---|---|---|
| ADR-001/003/005/006/010/014/015/023 | Contratos, prototipos y scaffolding sintético | owners y revisión humana |
| ADR-002 | spike PostgreSQL únicamente | migraciones y wrapper transaccional |
| ADR-004 | contrato local de zonas | L-01 y A-02 cloud |
| ADR-007/008 | patrones y spikes | cola/proveedor/costo |
| ADR-009 | prohibiciones y threat model | DRG-01, evals y Fase 4 |
| ADR-020 | análisis solamente | A02-G01..G10 y decisión humana |

## Validación

```powershell
python -m tools.adr_readiness.validate
python -m unittest tools.adr_readiness.test_validate -v
```

El validador descubre los ADR dinámicamente, exige cobertura exacta, verifica rutas y
evidencia, impide aceptar gates por agente y falla si un ADR Proposed aparece como listo.
