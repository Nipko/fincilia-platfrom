---
task: FNC-ARC-006A
status: REVIEW_PENDING
base_sha: 2eb5a31
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-ARC-006A

## Entrega

- Contrato narrativo y JSON autoritativo para stores, clasificaciones y release profile.
- Validador offline con referencias dinámicas a boundaries, DFD, canónico y linaje.
- 28 pruebas positivas/negativas.
- Perfil de implementación de ADR-023 ampliado sin cambiar la decisión core.
- CI, catálogo, fase y trazabilidad integrados.

## Decisiones preservadas

- DR-ARC-001 y DR-PRV-001 siguen Proposed.
- `vault` no recibe una capacidad lógica inventada: queda `pending_human` y sin persistencia.
- Temporal, Valkey y analytics projection siguen inactivos mientras ningún flujo declare
  finalidad, retención, borrado, amenazas y pruebas.
- Un mapping a object storage no colapsa cuarentena/raw/derived.
- `public` y `prohibited` no clasifican entidades financieras canónicas.
- Un agente no define la taxonomía personal ni aprueba una engine release.

## Comandos

```powershell
python -m tools.cross_contract_model.validate
python -m unittest tools.cross_contract_model.test_validate -v
```

Resultado observado: 28/28 PASS; suite integrada 367/367 PASS; quality gate sin hallazgos.

## Revisión requerida

- Architecture: mappings lógico/físico y estado de vault.
- Platform: Temporal/Valkey/analytics y perfil de build/release.
- Privacy + Legal: semántica del segundo eje, que continúa pendiente.
- Security: zonas de objetos, vault, provenance, firma y efecto fail-closed.

## Trabajo diferido

1. Aceptación humana o ajuste de DR-ARC-001.
2. Taxonomía personal aprobada para DR-PRV-001.
3. Añadir capacidad lógica de vault solo si Architecture la aprueba.
4. Activar stores hoy inactivos únicamente con flujos DFD completos.
5. Implementar pipeline real de engine release, SBOM, provenance, firma y revocación.

## Rollback

Retirar contrato, herramienta, integración CI y aclaración de ADR-023. No existen
migraciones, datos reales ni estado productivo que purgar.
