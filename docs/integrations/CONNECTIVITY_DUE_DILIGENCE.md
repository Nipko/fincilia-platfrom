# Due diligence de conectividad financiera

Estado: Review pending · Corte de evidencia: 2026-08-21 · Tarea: FNC-INT-001.

## Decisión provisional

Fincilia inicia file-first. CSV/XLSX/OFX/XML y formatos priorizados por corpus son un canal
permanente, no una contingencia temporal. Ninguna conexión viva está seleccionada y ningún
precio, SLA o banco empresarial se considera demostrado hasta recibir evidencia escrita.

La primera conexión candidata es Bancolombia directa o Prometeo, pero solo después de
comparar cobertura nominal por institución/cuenta, método de acceso, calidad, seguridad,
contrato y COGS. Belvo permanece como benchmark: su documentación pública actual no ofrece
evidencia suficiente de banking colombiano.

## Lectura por opción

| Opción | Evidencia pública | Uso permitido ahora | Bloqueo |
|---|---|---|---|
| Archivos | Contrato interno ejecutable | fixtures y desarrollo sintético | corpus real requiere DRG-00 |
| Bancolombia directo | sandbox, proceso productivo y consentimiento documentados | investigar/sandbox sintético autorizado | producto exacto, acuerdo, cobertura y precio |
| Prometeo | movimientos y sandbox ficticio documentados | investigación y sandbox sintético | matriz nominal, método por banco, SLA, DPA y precio |
| Belvo | productos públicos centrados en otros mercados | benchmark/RFQ condicionado | cobertura banking Colombia no demostrada |

## Reglas no negociables

1. Fincilia nunca recibe, persiste o registra usuario, contraseña u OTP bancarios.
2. Un agregador que use credenciales debe alojar completamente widget/redirect y asumir su custodia.
3. “Colombia” en una lista genérica no demuestra bancos, cuentas empresariales ni recursos.
4. Sandbox no demuestra producción, completitud, SLA, estabilidad de IDs o capacidad histórica.
5. Un feed degradado nunca se interpreta como cero movimientos.
6. Archivos permanecen disponibles aun si existe conexión viva.
7. El costo se modela a utilización completa, impuestos separados y FX ±10%/±25%.
8. No se publica conector ni se incluye en un plan comercial antes de INT-G02..G07.

## Evidencia requerida en sandbox

- cuentas empresariales nominales y recursos exactos;
- movimientos posted/pending, saldos y paginación;
- profundidad histórica y solapamientos;
- IDs estables, correcciones y reversos;
- refresh, webhooks, rate limits y ventanas de mantenimiento;
- consentimiento, revocación y borrado;
- errores, latencia, degradación y reconciliación tras timeout;
- exportación/portabilidad y continuidad por archivos.

Las pruebas usan únicamente datos ficticios hasta los gates legales y de privacidad.

## Fuentes primarias

- [Paso a producción Bancolombia](https://soportedevs.bancolombia.com/hc/es-419/articles/22036835683860--C%C3%B3mo-solicitar-el-paso-a-producci%C3%B3n-con-los-productos-de-APIs)
- [Open Banking Bancolombia](https://soportedevs.bancolombia.com/hc/es-419/sections/29354404515476--C%C3%B3mo-consumir-los-productos-API-de-Open-Banking)
- [Política de terceros receptores Bancolombia](https://www.bancolombia.com/wcm/connect/22a8e090-05a5-47e7-8a26-c2b98cfa756e/Politica_vinculacion_Terceros_Receptores_de_Datos_Bancolombia_V1.pdf?MOD=AJPERES)
- [Movimientos Prometeo](https://docs.prometeoapi.com/reference/getmovements)
- [Sandbox Prometeo](https://docs.prometeoapi.com/docs/comienza-la-integraci%C3%B3n-en-sandbox)
- [Productos públicos Belvo](https://developers.belvo.com/es/apis/belvoopenapispec/section/introduccion/informacion-disponible-y-metodos-de-pago)

## Validación

```powershell
python -m tools.provider_evaluation.validate
python -m unittest tools.provider_evaluation.test_validate -v
```
