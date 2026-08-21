---
id: FNC-DAT-002
title: Generador, corpus y linter sintéticos
epic: FNC-EP-006
phase: F0
iteration: E0
type: data-quality
status: claimed
priority: P0
accountable_owner: UNASSIGNED
implementer: Integration Steward
base_sha: 85c29d9
agent_lane: A5
independent_reviewer: Privacy and Accounting
plan_refs: [§7, §15, §31, §48]
dependencies: [FNC-DAT-001]
gate: S1-READY
allowed_data: synthetic
file_scope: [tools/synthetic_corpus, tests/golden/synthetic, docs/testing/SYNTHETIC_CORPUS.md, docs/implementation/handoffs/FNC-DAT-002.md]
forbidden_scope: [data, uploads, raw, customer-files, application-auth, db/migrations, lockfiles, compose]
---

# Resultado esperado

Implementar un generador determinista y un linter fail-closed para demostrar la procedencia completamente sintética del corpus golden inicial.

# Criterios de aceptación

- Usa Python 3.12 y biblioteca estándar; no introduce lockfile ni dependencia.
- Mismo seed y versión producen bytes y hashes idénticos.
- Cada fixture tiene manifiesto con clasificación, generador, seed, locale, encoding, esquema y SHA-256.
- Cubre `es-CO`, `en-US` y otro locale latinoamericano, COP/USD, fechas ambiguas, signos, saldos y duplicados económicos legítimos.
- Incluye casos hostiles inocuos: fórmula CSV, delimitador/encoding ambiguos, columnas desconocidas y archivo parcial; no crea malware ni bombas reales.
- El linter rechaza manifiesto ausente, hash distinto, procedencia no sintética, dominio no reservado y clasificación real/derivada.
- Tests reproducibles y documentación de regeneración/limpieza.

# Restricción de fase

Es scaffolding de calidad para S1-READY. No autoriza corpus real ni ingesta de clientes.
