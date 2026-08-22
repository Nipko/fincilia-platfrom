# RFQ — conectividad read-only para conciliación

Usar una copia por proveedor. No enviar hasta autorización humana. Todas las respuestas
deben identificar fecha, versión del producto y vigencia comercial.

## 1. Cobertura nominal

- Bancos colombianos exactos y estado producción/beta.
- Persona jurídica vs natural; cuenta corriente, ahorros, tarjetas y depósitos.
- Canal API oficial, open finance, bilateral, host-to-host o credenciales por institución.
- Recursos: cuentas, owners, saldos, movimientos, pending/posted y documentos.
- Historia inicial, incremental, refresh, webhook, paginación y rate limit.

## 2. Calidad y operación

- Estabilidad/unicidad de transaction ID y tratamiento de correcciones/reversos.
- Completitud, timestamps/timezone, currency, descripciones y contraparte.
- SLA mensual, exclusiones, service credits, soporte y escalamiento.
- Status page e historial de incidentes de 12 meses.
- RTO/RPO, mantenimiento y notificación de breaking changes/deprecations.

## 3. Seguridad y privacidad

- Flujo de consentimiento/revocación y quién recibe credenciales/OTP.
- Confirmación escrita de que Fincilia no recibe credenciales bancarias.
- ISO 27001/SOC 2 u otra evidencia; pentest y gestión de vulnerabilidades.
- Cifrado, residencia, backups, soporte, subencargados y transferencias.
- DPA, retención/borrado, evidencia de eliminación y respuesta a incidentes.
- Logs/auditoría, segregación de tenants, acceso privilegiado y continuidad.

## 4. Comercial

- Setup/homologación, mínimo mensual, cuenta/conexión/refresh/request/movimiento.
- Sandbox/trial, soporte, exceso, reconexión y almacenamiento.
- Moneda, impuestos, indexación, FX y compromiso mínimo.
- Precios a 10, 50, 100, 250 y 500 cuentas activas; 5k/25k/100k movimientos.
- Terminación, exportación, asistencia de salida, borrado e indemnidades.

## 5. Escenarios comparables

Cotizar en COP o separar TRM asumida:

| Escenario | Empresas | Cuentas | Movimientos/mes | Refresh |
|---|---:|---:|---:|---|
| Piloto | 15 | 30 | 75.000 | diario |
| Firma inicial | 50 | 100 | 250.000 | diario |
| Escala | 250 | 500 | 1.250.000 | 4/día |

Separar impuestos y mostrar sensibilidad FX. No mezclar iniciación de pagos: Fincilia pide
solo lectura para esta evaluación.

## 6. Evidencia exigida

- Matriz de cobertura firmada/fechada.
- Arquitectura y flujo de credenciales/consentimiento.
- SLA/DPA/subencargados/retención.
- Cotización con vigencia y supuestos.
- Contrato modelo y exit terms.
