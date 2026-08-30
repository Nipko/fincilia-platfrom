---
id: FNC-BET-001
title: Beta cerrada sintetica con dominio propio
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 93dac84
gate: BETA-01
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Security, Platform/SRE, Privacy/Legal, QA]
---

# Resultado

Fincilia puede ser usada por un grupo invitado desde un dominio HTTPS propio
para evaluar onboarding, usabilidad, aislamiento y comportamiento, sin datos
personales o financieros reales y sin presentar el entorno como producción.

# Alcance

- Entorno AWS separado del laboratorio T1 y de cualquier futuro entorno real.
- Único ingreso público por HTTPS; base, cache, objetos y API no se publican.
- Administración por SSM, sin SSH, y secretos generados fuera de Git.
- Registro sintético, aviso persistente y aceptación expresa de uso de datos
  inventados antes de crear una cuenta.
- Backups, restore ensayado, monitoreo mínimo, presupuesto y rollback.
- Despliegue por digest y migraciones separadas del arranque de aplicaciones.

# Criterios de aceptación

1. Dominio y certificado válidos, redirección HTTP→HTTPS y cookies `secure`.
2. Solo 80/443 públicos; SSH, PostgreSQL, Valkey, objetos y API no son públicos.
3. Alta, login, empresa inicial, carga sintética y cierre de sesión funcionan E2E.
4. La UI y los términos dicen claramente `beta cerrada · solo datos sintéticos`.
5. Rate limiting, límites de carga, logs redactados y health checks están activos.
6. Backups y restauración sintética tienen evidencia reproducible.
7. Alarmas de disponibilidad/costo y runbooks de incidente/rollback existen.
8. No se habilitan Google real, documentos reales, conectores o IA externa.
9. Security/Platform/Privacy/QA revisan antes de invitar a terceros.

# Fuera de alcance

DRG-00, DRG-01, datos reales, producción, GA, billing, SLA, conectores, OCR/IA
externa o aprobación jurídica definitiva.

# Punto de control 2026-08-28

- El registro cerrado usa invitaciones criptográficas de un solo uso; PostgreSQL
  conserva solo el digest y la consume atómicamente con el alta.
- `infra/aws/beta` materializa un entorno separado con EIP, 80/443, Caddy,
  Nginx, SSM sin SSH, redes Docker privadas y secretos generados en el host.
- La semilla de beta no crea personas, credenciales, firmas ni empresas.
- Backup diario y restore-check semanal publican métricas sin guardar un correo
  personal en IaC, S3 o estado antes de DRG-00.
- Contrato, mutaciones, OpenTofu, Compose, proxies y bootstrap PostgreSQL están
  verificados localmente. No se ha ejecutado `plan` ni `apply` del entorno beta.

# Pendiente para aplicar

Dominio exacto, control del DNS, release por digest de estos commits, plan
adjudicado, apply, registro A, evidencia HTTPS/E2E/backup/restore y las cuatro
revisiones independientes. BETA-01 y DRG-01 permanecen `not_met`.

# Punto de control 2026-08-30

- `fincilia.com` fue adjudicado como dominio raíz y el release de aplicación
  `4344a4405fb5ec26f8dc001553612f07db515fbc` fue publicado en ECR con las tres
  imágenes fijadas por digest después de CI verde y pruebas dentro del contenedor.
- OpenTofu aplicó los 27 recursos previstos en la cuenta autorizada
  `632144225293`, región `sa-east-1`, sin cambios ni eliminaciones. La instancia
  es `i-03115c49eef006553` y su EIP estable es `54.94.132.123`.
- La ejecución real detectó dos defectos previos a exposición: CloudWatch rechaza
  ventanas mayores a siete días y el bootstrap no creaba las cuatro zonas de
  objetos antes del worker. `c4c783b` y `72c529e` los corrigen con mutantes que
  muerden; los deltas aplicados fueron uno de alta y dos actualizaciones in-place,
  sin reemplazar instancia, IP o volumen.
- EC2 pasa status checks, SSM está `Online`, el bundle local verifica por SHA-256,
  `fincilia-beta.service` está activo y el acceso externo por IP con `Host:
  fincilia.com` devuelve redirección permanente a HTTPS.
- El registro DNS A y el certificado ya están operativos; el E2E público,
  restore verificado y las revisiones independientes siguen pendientes.
  `BETA-01`, `DRG-00`, `DRG-01` y `GA-01` permanecen `not_met`; solo se permiten
  datos completamente sintéticos.

# Punto de control 2026-08-30 — dominio y operación

- `fincilia.com` resuelve a la EIP, redirige HTTP a HTTPS y sirve un certificado
  Let's Encrypt válido. Los puertos 22, 3000, 5432, 6379 y 9000 permanecen
  cerrados desde Internet.
- El primer backup sintético se escribió en S3 y sus tres artefactos pasaron
  checksum. El restore desechable descubrió una carrera: `pg_isready` observaba
  el PostgreSQL temporal del entrypoint antes de que terminara el reinicio. La
  espera ahora exige `SELECT 1` sobre la base final exacta. La primera repetición
  descubrió además que las políticas RLS referencian roles que un dump sin
  owners/ACL no recrea; el laboratorio crea placeholders `NOLOGIN`, nunca copia
  roles ni credenciales del entorno activo.
- El primer plan de actualización pretendía reemplazar EC2, su asociación EIP y
  el volumen por un cambio solo web. El release ahora se despliega in-place por
  SSM, bajo lock, con bundle verificado, preservación de volúmenes y rollback
  local al release anterior. El user-data queda reservado al alta de hosts.
- La superficie pública deja de mostrar usuarios conocidos del laboratorio y
  publica canales separados `support`, `privacy`, `legal` y `security` bajo
  `fincilia.com`. El código y las imágenes fueron verificados; falta aplicar el
  bundle final, repetir restore y completar el E2E de una cuenta invitada.

# Punto de control final 2026-08-30

- El release `90110e70d51c069afa0c5b91e32d86572b585eee` está activo sobre la
  instancia y EIP originales. Los planes de los tres incrementos dejaron
  `aws_instance.beta`, `aws_eip.beta` y `aws_eip_association.beta` en `no-op`.
- El restore desechable terminó con exit 0 y publicó evidencia en
  `restore-checks/beta/20260830T060535Z.json`; los timers diarios/semanales
  quedaron habilitados.
- El recorrido operacional en AWS creó una identidad y firma completamente
  sintéticas, autenticó, aprovisionó empresa/cuenta/fuente/ciclo, cargó un CSV
  inventado y observó `scan`, `profile` y `extract` en `succeeded`. Invitación,
  contraseña y token nunca aparecieron en salida, Git, S3 o Parameter Store.
- La ejecución encontró y cerró tres defectos antes de invitar personas: permiso
  inicial del nuevo script, multipart con escapes literales y rate limiting de
  Nginx sobre GET que se presentaba como 503. El límite ahora aplica a POST y
  responde 429; `/registro` soportó cinco recargas consecutivas por HTTPS.
- La portada describe el modo realmente activo: invitación, beta cerrada y datos
  sintéticos. Google continúa deshabilitado hasta DRG-00.
- La implementación pasa a `review_pending`. Security, Platform/SRE,
  Privacy/Legal y QA deben revisar de forma independiente antes de invitar a
  terceros; `BETA-01`, `DRG-00`, `DRG-01` y `GA-01` siguen `not_met`.
