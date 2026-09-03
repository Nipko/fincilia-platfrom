# Laboratorio aislado para el primer corpus real

Este es el diseño de seguridad de FNC-SEC-003, no un entorno desplegado. Un
`ok: true` sólo significa que el diseño está completo para revisión; el mismo
reporte debe decir `implemented: false`, `passed_test_count: 0` y
`real_data_authorized: false`.

## Qué existe hoy y qué cambia para datos reales

La plataforma ya resuelve roles por empresa en servidor, RLS, revocación,
sesiones cortas, contexto durable y auditoría. Esos controles se reutilizan.
El proveedor local de identidad y las contraseñas de la demo no son una
autoridad admisible para datos reales.

El laboratorio exige:

- IdP administrado con usuarios nominales; nunca cuentas compartidas.
- MFA resistente a phishing y step-up AAL3 para aprobación, export, borrado y
  break-glass.
- Invitación/enrolamiento ligado a un `subject` estable; los roles continúan en
  PostgreSQL y no se confían a claims enviados por el navegador.
- Privilegio JIT de máximo 60 minutos, doble control para emergencia y revisión
  posterior por otra persona.
- Identidades de workload cortas, sin access keys o credenciales estáticas.

Proveedor, región, IdP, KMS, secretos y endpoints permanecen nulos hasta A-02 y
`UD-PROVIDERS`. No se creó una funcionalidad especial de pruebas: el modelo es
el mismo que se espera utilizar finalmente.

## Zonas de confianza

| Zona | Propósito | Ingreso | Egreso |
|---|---|---|---|
| Z-IN | Ingreso controlado | Broker nominal | Denegado |
| Z-Q | Cuarentena no confiable | Capacidad de intake | Denegado |
| Z-P | Procesamiento aislado | Dispatcher con capacidad | Denegado |
| Z-E | Evidencia aceptada | Workload identity privada | Denegado |
| Z-C | Control plane | Broker de administración auditado | Denegado |
| Z-A | Auditoría/delete ledger | Append/reconcile acotado | Denegado |

Ninguna zona tiene IP pública. Mientras A-02 esté abierta tampoco existe
allowlist DNS/egress ni endpoint privado seleccionado.

## Camino de un archivo

```text
manifiesto aprobado
  -> broker de ingreso
  -> objeto opaco en cuarentena
  -> escaneo fail-closed (malware, activo, PAN y contenido prohibido)
  -> decisión auditada
  -> raw inmutable o rechazo/purga
  -> worker efímero sin red
  -> derivados con linaje por digest
  -> reconciliación y destrucción del scratch
```

Nada ejecuta el contenido. Una hoja, PDF o texto es entrada no confiable, nunca
una instrucción. Un timeout, error o motor ausente rechaza la promoción; no hace
fallback a OCR/IA externa.

## Cómputo y cadena de suministro

El worker usa imagen fijada, firmada y con procedencia verificada; corre como
no-root, filesystem raíz read-only, scratch cifrado efímero, sin privilegios,
host mounts, host namespaces, instalación dinámica o fallback de red. La
capacidad se emite por ejecución/empresa y se revalida antes de publicar.

La release adjudicada en FNC-GAT-005 demuestra SBOM, firma y procedencia tanto
dentro como fuera del runner. Ese resultado cierra el control automático
`G00-SUPPLY-CHAIN`, pero no admite por sí solo la release en el entorno objetivo
ni reemplaza el drill aislado o la revisión independiente.

## Stores, borrado y restore

Cada plano usa rutas y claves separadas. Raw es inmutable después de promoción;
auditoría/delete ledger está fuera del restore ordinario; región y ventana de
backup esperan A-02/L-01. Un restore reaplica tombstones y reconcilia el
inventario antes de que una sonda pueda declarar el servicio listo.

Logs y errores usan allowlist estructurada. Se prohíben payloads, montos,
cuentas, NIT, nombres de archivo, tokens y contenido documental.

## Evidencia que debe producir PLT-004/QA-001

Las 12 pruebas incluyen: ausencia de red pública, egress imposible desde
quarantine/processing, fixtures hostiles que no llegan a raw, negaciones
cross-company, revocación de sesión/job/download, rechazo de cuentas
compartidas/keys/password-only, logs limpios, restore con tombstones, destrucción
completa, rechazo de imagen no firmada y break-glass con dos personas.

Ninguna está marcada como ejecutada. El diseño falla si alguien cambia ese
estado sin materializar primero la infraestructura y evidencia.

## Prerrequisitos antes de recibir un solo artefacto real

1. FNC-LEG-001 firmado por abogado independiente.
2. L-01 adjudicada y aplicada.
3. A-02 con proveedor, región y data planes aceptados.
4. S-01 con revisión Security/Privacy/Architecture.
5. Release exacta admitida en el target usando la firma y procedencia ya
   demostradas por FNC-GAT-005.
6. FNC-PLT-004 desplegado y FNC-QA-001 repetido contra el target aislado.
7. Gate DRG-00 consolidado por sus humanos nominales.

Hasta entonces, “real pero de prueba” sigue siendo dato real y no entra.

## Verificación

```text
python -m tools.isolated_lab validate
python -m tools.isolated_lab report
python -m unittest tools.isolated_lab.test_model
```
