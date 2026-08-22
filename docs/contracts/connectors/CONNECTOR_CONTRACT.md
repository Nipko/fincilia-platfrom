# Contrato de conectores v0

Estado: `Review pending` · Tarea: `FNC-ARC-005` · Datos: solo sintéticos.

Un conector es un adaptador read-only hacia una fuente autorizada. No es prueba de
completitud, no es fuente de autorización y no reemplaza el canal de archivos. Ningún
conector recibe estado `certified` hasta aprobar cobertura nominal, seguridad, legal,
costo, completitud y fallback con revisores humanos.

Todo conector declara:

1. País, institución, fuente y tipos de cuenta.
2. Autorización, scopes, revocación y secret references.
3. Backfill, incremental, cursor y ventana histórica.
4. IDs estables, pending/posted y correcciones.
5. Paginación, rate limits y frescura.
6. Webhook, firma, timestamp, nonce y replay.
7. Totales y completitud por periodo.
8. Taxonomía de errores; sin retries internos.
9. SLA, status y modo degradado.
10. Región, subencargados, DPA y retención.
11. Unidad de costo, moneda y mínimos.
12. Fallback por archivo.
13. Sandbox, fixtures sintéticos y golden tests.
14. Owner, versión y política de retiro.

## Invariantes

- Company/account/source se resuelven server-side; nunca desde el payload sin verificar.
- La plataforma no recibe, persiste ni registra usuario, contraseña, OTP, certificado
  privado o secreto bancario. OAuth/consent usa redirect/widget alojado o secret reference.
- El alcance inicial es read-only; pagos, write-back y fondos están deshabilitados.
- Un ID de proveedor es candidato hasta que su contrato de identidad esté `verified`.
- Backfill e incremental comparten identidad, corrections y completeness; no publican dos veces.
- Pending no se publica como posted. Corrección/reverso crea versión/evento, no overwrite.
- Cada página/cursor tiene evidencia; cursor agotado no prueba completitud sin controles.
- Adapter clasifica errores y falla rápido. Queue/workflow padre posee retries.
- Frescura desconocida, gap o provider down se muestran; nunca se interpreta como saldo cero.
- Archivo es fallback permanente, utiliza el mismo modelo canónico y conserva evidencia.
- Logs/metrics no contienen payload, credenciales, cuentas, NIT, referencias ni montos.
- Región, subencargados, DPA, retención, SLA y costo permanecen pendientes hasta evidencia.

## Estados

`draft → review_pending → certified → suspended → retired`. Suspender identidad, auth,
schema o completitud bloquea publicación automática y activa fallback. Retired conserva
versiones históricas necesarias para explicar resultados, sujetas a L-01.

## Completitud y modo degradado

Cada run produce controles disponibles por source/account/period. Falta de un control
requerido produce `unknown`; no se infiere `verified`. Un feed degradado conserva última
frescura conocida, gaps, cursor y motivo. El archivo subido se concilia contra el feed como
otra evidencia; similitud no borra registros ni crea unicidad económica.

## Seguridad y egress

Hosts, métodos y paths usan allowlist versionada; DNS/private ranges/redirects se validan
contra SSRF. Webhooks verifican firma, timestamp, nonce y replay antes del inbox. Secretos
solo se obtienen por referencia de vault y capabilities cortas. Revocar consentimiento
bloquea jobs, webhooks y publicación pendientes mediante `authorization_version`.

## Gate de certificación

- Contract tests.
- Replay/duplicados.
- Cursor y paginación.
- Pending→posted/correcciones.
- Rate limit y expiración.
- Completitud/control totals.
- Revocación/borrado.
- Aislamiento cross-company.
- Fallback y modo degradado.
- Legal, SLA y costo aprobados.

Todos los gates quedan `pending_human` en E0. Un test técnico no acepta contrato, DPA,
región, SLA o margen. La falla de cualquier gate suspende el conector sin bloquear el
fallback por archivo.

Archivos permanecen fallback contractual aunque exista API.
