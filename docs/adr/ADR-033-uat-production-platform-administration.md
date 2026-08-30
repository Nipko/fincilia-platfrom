# ADR-033: UAT separado, promoción a producción y administración de plataforma

- Estado: Proposed; dirección del Founder registrada, revisión independiente pendiente
- Fecha: 2026-08-30
- Decisor accountable: FOUNDER-01
- Revisores requeridos: Security, Privacy/Legal, Architecture/Database, SRE y QA
- Supersede al destino operativo de ADR-031 y ADR-032; no borra su evidencia histórica

## Contexto

Fincilia necesita validar el producto completo con varias personas antes de operar
producción. Ese entorno no debe llamarse beta ni convertirse en producción por un
cambio de etiqueta: contendrá cuentas y datos de prueba que deben poder
sanitizarse. También hace falta una autoridad de plataforma distinta de los roles
de firma y empresa.

## Decisión

1. `UAT` es el entorno previo a producción. Usa identidad nominal, datos
   autorizados para prueba y controles equivalentes a producción cuando sean
   aplicables, pero sus datos son reiniciables.
2. Producción nace como entorno separado: almacenes, base, secretos, claves,
   buckets, backups, auditoría y configuración no se comparten con UAT.
3. Se promueve el mismo artefacto inmutable que superó UAT. No se copia la base
   de UAT a producción ni se promueven cuentas de prueba.
4. La limpieza de UAT es una operación explícita con previsualización, respaldo,
   token de confirmación, allowlist de entorno y evidencia de ejecución. Nunca se
   ejecuta desde la consola web ordinaria.
5. `platform_superadmin` es un rol del plano de control, no un rol financiero.
   Puede administrar servicio, identidades, organizaciones, releases,
   configuración, salud, trabajos y auditoría de plataforma. No obtiene acceso
   implícito a documentos, movimientos, saldos o decisiones de una empresa.
6. El primer superadmin se reclama una sola vez contra una referencia HMAC de un
   correo Google verificado configurada fuera del código. La API no acepta un
   correo ni un rol enviados por el navegador.
7. El acceso excepcional a datos de una empresa, si se implementa, será un
   flujo `break-glass` separado: motivo, empresa y alcance explícitos, AAL3,
   segundo aprobador distinto, expiración automática y revisión posterior. No
   forma parte del bootstrap ni del permiso normal de superadmin.

## Consecuencias

- Los nombres físicos heredados de infraestructura pueden permanecer hasta una
  migración de estado segura, pero la experiencia y los nuevos contratos dicen
  UAT.
- Una sola persona puede probar varios roles contables en UAT, pero no satisface
  separación de funciones para aprobaciones reales ni break-glass.
- El superadmin inicial no se crea con un password local ni se versiona su email.
- Una restauración debe conservar o reconfigurar de forma controlada el
  bootstrap; nunca puede abrir una segunda reclamación accidental.

## Alternativas descartadas

- **Un owner de empresa como superadmin:** mezcla tenancy con control del SaaS.
- **Un claim de Cognito como autoridad final:** permite que el IdP conceda
  permisos financieros y contradice la autorización server-side.
- **Convertir UAT en producción:** arrastra cuentas, secretos y evidencia de
  prueba, e impide demostrar una frontera limpia.
- **Acceso total permanente para soporte:** crea una puerta trasera transversal.

## Evidencia de salida

- Migración y pruebas PostgreSQL del bootstrap único y privilegios negativos.
- API y consola de administración sin payload financiero.
- Runbook UAT, promoción y sanitización con ejecución ensayada.
- Revisión independiente de Security/Privacy/Architecture/SRE/QA antes de GA.
