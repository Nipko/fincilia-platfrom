# Solicitudes de decisión derivadas de FNC-PRV-001

Estado: `Proposed` · Gate afectado: S1-READY/DRG-00 · Ninguna decisión aceptada.

Este documento enruta los cinco hallazgos del mapa de privacidad. No fija región,
retención, rol legal o topología y no autoriza datos reales.

## DR-ARC-001 — Semántica de stores y políticas del DFD

- Tareas afectadas: FNC-ARC-002, FNC-PRV-001, FNC-PRV-002.
- Owner: Architecture.
- Revisores: Privacy, Security, Platform.
- Fecha límite: antes de S1-READY.

### Incertidumbre

`L-01-AUDITABLE-DECISION` aparece en F03/F07 aunque no estaba en una lista manual del
encargo. Además `temporal`, `valkey`, `analytics_projection` y `vault` figuran en el
catálogo de stores, pero ningún `persistence[]` de F01–F13 los usa.

### Decisión requerida

1. Confirmar que las políticas de retención consumidoras se derivan dinámicamente de
   todos los `persistence[]`; no mantener una lista paralela susceptible de drift.
2. Elegir y documentar una de estas opciones por store:
   - capacidad aprobada todavía no activa, con persistencia prohibida hasta agregar flujo;
   - persistencia activa, incorporando su flujo, finalidad, clasificación, retención,
     borrado, amenazas, controles y prueba negativa.
3. El validador debe fallar si el estado declarado del store contradice los flujos.

### Evidencia de cierre

- Modelo DFD y tests negativos actualizados.
- Revisión Architecture + Privacy.
- Ninguna política L-01 inventada o aceptada por un agente.

### Evidencia técnica disponible

FNC-ARC-006A propone un mapping ejecutable en
`docs/architecture/cross-contract-vocabulary.json`: deriva stores activos desde todos los
`persistence[]`, bloquea uso de capacidades inactivas y conserva DR-ARC-001 como Proposed.
Architecture, Privacy y Platform todavía deben aceptarlo o corregirlo.

## DR-PRV-001 — Segundo eje de clasificación personal

- Tareas afectadas: FNC-ARC-002, FNC-PRV-001, FNC-PRV-002, FNC-DOM-005.
- Owners: Privacy + Architecture.
- Revisores: Security, Product, Legal.
- Fecha límite: antes de S1-READY; obligatoriedad legal antes de DRG-00.

### Incertidumbre

El eje `public/internal/confidential/financial_sensitive/secret/prohibited` describe
sensibilidad y controles operativos. No permite expresar por sí solo si un dato pertenece
a una persona natural, qué categoría de titular tiene o si es sensible bajo la ley.
`PA-20`, por ejemplo, puede ser `internal` y aun contener actividad laboral personal.

### Decisión requerida

Definir un eje ortogonal, como mínimo con:

- presencia: none/possible/confirmed;
- categoría de titular;
- categoría personal: identificación, contacto, laboral, financiera, sensible u otra
  taxonomía aprobada por Privacy/Legal;
- propósito, minimización y rights workflow aplicables;
- propagación por lineage, derivados, exports, logs, IA y borrado.

No se permite inferir que `internal` significa “no personal”, ni que hash/HMAC anonimiza.

### Evidencia de cierre

- Contrato ejecutable y pruebas de propagación/redacción.
- Privacy y Legal aprueban categorías; Architecture aprueba representación.
- PA-20 y todos los flujos F01–F13 quedan evaluados explícitamente.

### Evidencia técnica disponible

FNC-ARC-006A valida que la clasificación canónica sea el subconjunto financiero del DFD y
que `public/prohibited` permanezcan sentinelas de borde. El contenido del eje personal no
se define: sigue `pending_human`, ortogonal y con egreso fail-closed.

## DR-LEG-001 — Orden y reloj de retención

- Tareas afectadas: FNC-PRV-002, FNC-PLT-004, FNC-DAT-003, FNC-PRV-003.
- Owner: Legal.
- Co-owners de implementación: Privacy + Platform.
- Revisores: Accounting, Security, Data Engineering.
- Fecha límite: antes de DRG-00.

### Incertidumbre

El delete ledger debe seguir disponible mientras cualquier backup pueda restaurar datos
tombstoned. La retención financiera puede reactivarse por asiento, documento relacionado,
reapertura u otro evento legal/contable; `uploaded_at` no es un reloj suficiente.

### Decisión requerida

1. Fijar una relación verificable: la expiración de `L-01-DELETE-LEDGER` ocurre después de
   la última ventana restaurable relevante, reconciliación y legal hold aplicable.
2. Definir por clase el evento de inicio/reinicio/suspensión del reloj, incluyendo último
   asiento/documento relacionado, reapertura, disputa y legal hold.
3. Determinar cómo se propaga el reloj a raw, derivados, snapshots, exports y backups.
4. Prohibir lifecycle basado únicamente en `created_at`/`uploaded_at` para evidencia financiera.

### Evidencia de cierre

- Matriz L-01 aprobada por Legal/Privacy/Accounting.
- Prueba restore → reaplicar tombstones → reconciliar antes de abrir.
- Pruebas de periodo reabierto y carga tardía.
- Delete ledger fuera del restore ordinario y con retención ordenada sobre backups.

## Estado de enrutamiento

| Hallazgo | Solicitud | Owner | Estado |
|---|---|---|---|
| Política no incluida en lista manual | DR-ARC-001 | Architecture | Proposed |
| Stores declarados sin persistencia | DR-ARC-001 | Architecture | Proposed |
| Ejes de clasificación colapsados | DR-PRV-001 | Privacy + Architecture | Proposed |
| Delete ledger vs backup | DR-LEG-001 | Legal + Privacy + Platform | Proposed |
| Reloj financiero desde evento relacionado | DR-LEG-001 | Legal + Accounting | Proposed |
