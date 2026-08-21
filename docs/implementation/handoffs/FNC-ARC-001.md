---
task: FNC-ARC-001
status: REVIEW_PENDING
base_sha: c7fe2eb
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-ARC-001

## Entrega

- C4 nivel 1 y 2 con actores, externos, contenedores y trust boundaries.
- Cinco planos: control, financiero, evidencia, analítico y seguridad.
- Secuencias company-scoped y artefacto→worker→publicación.
- Fuentes autoritativas y comportamiento degradado por store.
- Ownership y dependencias de módulos documentados.
- Modelo JSON ejecutable: 16 módulos, 73 entidades conceptuales, 6 stores y 6 invariantes.
- Validador Python sin dependencias y siete pruebas negativas/positivas.
- CI ampliado para validar modelo y tests de arquitectura.

## Verificación

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app' && python3 -m tools.architecture_model.validate"
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/USER/Desktop/Projects/knowledge-app' && python3 -m unittest tools.architecture_model.test_validate -v"
```

Resultado observado:

- Modelo: PASS, 0 errores.
- Tests: 7/7 PASS.
- Rechazos probados: multi-owner, dependencia desconocida, ciclo, autoridad financiera analítica, cache autoritativa e invariante ausente.

## Decisiones preservadas

- Company es frontera financiera independiente de firma.
- Solo Finance, Reconciliation y Close poseen estado financiero autoritativo.
- PostgreSQL, object storage y Temporal tienen ámbitos de autoridad distintos.
- Valkey y analytics no son fuente de verdad.
- Worker retorna manifiesto; monolito publica.
- AI Gateway es egress único y no decide dinero/acceso/cierre.
- A-02 sigue abierta; no se eligió cloud, región, IdP, cola o Temporal provider.

## Pendientes

- Architecture, Security y Platform deben revisar y aceptar.
- FNC-SEC-001 debe contrastar el authorization context y SoD.
- FNC-ARC-002 debe completar DFD por flujo/clasificación.
- FNC-DOM-002..005 pueden cambiar nombres de entidades; cualquier cambio debe actualizar JSON, docs y tests juntos.
- Los límites todavía no se materializan como imports de un monorepo productivo.

## Rollback

Restaurar C4/MODULE_BOUNDARIES anteriores y retirar modelo, tooling, tests y paso CI. No existen migraciones, despliegues ni datos reales.

Esta entrega no supera S1-READY ni autoriza DRG-00.
