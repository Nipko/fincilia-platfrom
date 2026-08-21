# ADR-001 — Monolito modular y workers aislados

- Status: Accepted architectural shape; language choice pending FNC-PLT-001
- Date: 2026-08-21
- Owners: Architecture, UNASSIGNED
- Gate: S1-READY
- Plan refs: §20–§21

## Context

El producto requiere invariantes financieras fuertes y también procesamiento pesado/no confiable. Microservicios tempranos aumentarían contratos, operación y consistencia sin evidencia de escala.

## Decision

- Dominio y plano de control forman un monolito modular.
- Parsing, OCR y cómputo se ejecutan en workers aislados.
- Workers devuelven manifiestos; no publican directamente estado financiero.
- Los módulos no escriben tablas ajenas.
- Stack candidato: NestJS/TypeScript + workers Python, sujeto al spike A-01.

## Alternatives rejected

- Microservicios desde el inicio.
- Un único proceso con parsers no confiables.
- Kafka/Kubernetes sin umbral.

## Consequences

Menor costo operacional y transacciones locales claras; exige enforcement de límites y contratos internos. Separar un módulo futuro requerirá métricas y ADR.

## Verification

FNC-PLT-001 demuestra auth context, RLS, outbox y worker sintético antes de aceptar lenguajes/tooling.

