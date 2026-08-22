# A-02 — región, transmisión y subencargados

Estado: **decisión humana pendiente** · Tarea: `FNC-ARC-003` · Evidencia revisada: 2026-08-21.

## Veredicto actual

No hay base para elegir proveedor o región todavía. El único resultado seguro es un
shortlist técnico para due diligence en Brasil y Chile y una postura `deny` para cloud,
egress y datos reales hasta completar la matriz legal, contractual y servicio por servicio.

Las fuentes oficiales revisadas muestran regiones completas candidatas en São Paulo para
AWS, Brasil/Chile para Azure y Brasil/Chile para Google Cloud. No evidencian una región
pública completa en Colombia para esos candidatos a la fecha de corte. Una ubicación edge
o Local Zone no demuestra que PostgreSQL, object storage, backups, KMS, logs y soporte
permanezcan allí.

## 1. Por qué “elegir país” no resuelve A-02

La evaluación tiene al menos cuatro capas independientes:

1. **Rol y operación:** transferencia Responsable→Responsable frente a transmisión a un
   Encargado, evaluada por actividad.
2. **Contrato:** DPA, instrucciones, confidencialidad, subencargados, auditoría, derechos,
   incidentes, devolución y borrado.
3. **Topología real:** dato en reposo, procesamiento, backup, DR, control plane, soporte,
   telemetría y llaves para cada servicio.
4. **Viabilidad:** cobertura regional, disponibilidad, latencia Bogotá, costo total, FX,
   egress, soporte y salida.

La SIC mantiene reglas e instrumentos específicos para transferencia/transmisión
internacional y cláusulas modelo. Su concepto de 2026 enfatiza roles, contrato de
transmisión y responsabilidad demostrada. Esto exige concepto jurídico firmado; el agente
no puede convertir la ubicación del proveedor en cumplimiento legal.

Fuentes: [Título V, Circular 001 de 2026](https://sedeelectronica.sic.gov.co/sites/default/files/normativa/T%C3%ADtulo%20V.%20Circular%20001%20del%209%20de%20enero%20de%202026.%20Publicada%20en%20el%20Diario%20Oficial%20No.%2053.362%20del%2009%20de%20enero%20de%202026.pdf),
[Circular 003 de 2025](https://sedeelectronica.sic.gov.co/sites/default/files/normativa/Circular%20Externa%20003%20de%202025.pdf) y
[concepto oficial SIC de 2026](https://sedeelectronica.sic.gov.co/publicaciones/boletin-juridico/concepto/alcance-de-la-circular-002-de-2025-sobre-transferencias-internacionales-de-datos).

## 2. Shortlist factual, no ranking

| Candidato | Hecho oficial verificado | Riesgo o incógnita bloqueante |
|---|---|---|
| AWS `sa-east-1` | São Paulo, Brasil, tres AZ | Disponibilidad/ubicación de cada servicio y soporte; legalidad por flujo |
| Azure `chilecentral` | Santiago, Chile, soporte de zonas, sin par publicado | Matriz servicio por servicio, contratos, soporte y DR deliberado |
| Azure `brazilsouth` | São Paulo, zonas; par documentado South Central US | Verificar que ningún servicio replique/recupere fuera sin aprobación |
| GCP `southamerica-west1` | Santiago, zonas a/b/c | Ubicación de cada servicio/global control plane y condiciones contractuales |
| GCP `southamerica-east1` | São Paulo, zonas a/b/c | Igual; además medir costo/latencia frente a Chile |

Fuentes de infraestructura: [AWS Regions](https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html),
[Azure regions](https://learn.microsoft.com/en-us/azure/reliability/regions-list),
[Azure region pairs](https://learn.microsoft.com/en-us/azure/reliability/regions-paired) y
[Google Cloud regions/zones](https://docs.cloud.google.com/compute/docs/regions-zones).

No se asignan puntos: antes de los gates legales, seguridad y localización de servicios, un
score produciría falsa precisión.

## 3. Matriz obligatoria por plano

Para PostgreSQL, cada zona de objetos, security archive/delete ledger, backups/WAL,
cola/workflow, secretos/KMS, telemetría/soporte, identidad/notificaciones, analytics e IA se
debe registrar:

- servicio exacto y versión/edición contractual;
- lugar de procesamiento y datos en reposo;
- backup, DR y control plane;
- países de soporte privilegiado y subencargados;
- propagación de revocación/borrado y restore con tombstones;
- export/portabilidad y mecanismo de salida;
- fuente contractual y prueba técnica reproducible.

Un `unknown` bloquea cloud; no se convierte en “regional” por el nombre comercial.

## 4. Topología provisional que puede evaluarse

- Una región primaria con múltiples zonas antes de multi-región.
- Nada de réplica cross-region hasta aprobación legal y técnica explícita.
- Edge solo para TLS/WAF/contenido público; nunca raw financiero.
- Security archive y delete ledger separados del restore ordinario.
- Backups regionalmente fijados; restore reaplica tombstones antes de servir.
- Archivos siguen como fallback permanente.
- IA externa continúa prohibida y tendría policy por company + AI Gateway aparte.

Esta topología es una hipótesis reversible para cotizar y probar, no autorización de despliegue.

## 5. Secuencia de decisión

1. Legal/Privacy clasifican rol y operación para cada actividad de `privacy-map`.
2. Legal/Security aprueban contrato/DPA, cláusulas, auditoría e incidentes.
3. Platform completa matriz por servicio y registro de subencargados/soporte.
4. Security verifica llaves, acceso privilegiado, egress y delete/restore.
5. Platform mide latencia y fallos desde Bogotá con workload sintético.
6. Finance compara costo a utilización completa, soporte, egress y FX.
7. Architecture prueba salida/portabilidad y presenta ADR-020 completo.
8. Owners humanos firman proveedor, región y riesgos residuales.

Hasta completar los diez gates de `region-transmission-decision.json`, A-02 permanece abierta.

