# Solicitud de decisión — pyme directa y perfiles operativos

- ID: FNC-PRD-002
- Fecha: 2026-11-04
- Tarea bloqueada: FNC-SMB-001..006
- Owner requerido: Product + Accounting (FOUNDER-01)
- Gate afectado: S1-READY (alcance de producto); no relaja DRG-00, DRG-01 ni GA-01
- Fecha límite: 2026-11-04

## Contradicción o incertidumbre

El PRD (FNC-PRD-001) define a la firma contable como comprador prioritario y
exige segregación de funciones (SoD) de dos personas en cada decisión. El
diagnóstico del 2026-11-04 muestra que una pyme sin personal contable necesita
más de 10 pasos, dos archivos, dos personas y una acción por CLI para conciliar
un extracto. El Founder pide servir directamente a pymes con flujos muy
sencillos sin perder un modo estricto.

## Evidencia disponible

- Inventario de código en `main` b3f5110: cruce exacto, SoD forzada por
  triggers en V0012, V0017, V0028, V0034, V0035 y V0046; sin tolerancias,
  sin reglas aprendidas, sin facturas DIAN ni plantillas bancarias.
- Investigación de mercado (2026-11-04): Bre-B multiplica microabonos; la
  conciliación en pymes suele quedar sin dueño (CTCP 0443/2024); los
  referentes (Xero, QuickBooks) se basan en reglas aprendidas, confianza
  visible y aceptar con un clic, y sus usuarios piden previsibilidad.

## Opciones

| Opción | Ventajas | Riesgos | Costo de reversión |
|---|---|---|---|
| A. Mantener solo firma + SoD estricta | Sin cambios de control | Inviable para pymes de una o dos personas | Nulo |
| B. Perfiles `simple` y `estricto` por empresa, con modo de revisión explícito y certificación posterior del contador | Flujo de una persona sin ocultar que no hubo revisión independiente | Más estados que explicar; requiere ADR y pruebas de RLS/SoD | Medio: el perfil es configuración auditada; el ledger conserva el modo |
| C. Eliminar SoD | Máxima simplicidad | Viola invariantes y pierde confianza | Alto |

## Recomendación del agente

Opción B, documentada en ADR-039.

## Decisión humana

- Estado: Accepted
- Aprobador: FOUNDER-01 (instrucción en sesión del 2026-11-04: perfiles para
  empresas pequeñas limitadas por personal y otro más estricto, sin agregar
  complejidad; «cierre del dueño + revisión del contador»)
- Fecha: 2026-11-04
- ADR o cambio requerido: ADR-039; actualización del PRD §3 y §7; tareas
  FNC-SMB-001..006. La revisión independiente sigue pendiente como en el resto
  del paquete.
