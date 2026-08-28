# ADR-031 — Beta cerrada sintética antes de DRG-01

- Estado: **Proposed; despliegue sintético condicionado a BETA-01**
- Fecha: 2026-08-28
- Gates: BETA-01 / DRG-00 / DRG-01

## Contexto

El equipo necesita observar onboarding y comportamiento multiusuario en Internet,
pero DRG-01 autoriza un piloto con datos financieros reales y todavía depende de
DRG-00, DPA, región, restore, PCI, pentest y revisiones humanas. Usar DRG-01 como
sinónimo de beta de usabilidad borraría una frontera de datos importante.

## Decisión

Se crea `BETA-01`, un gate operativo anterior que solo autoriza una beta cerrada
con identidades y documentos inventados. El ambiente es público por HTTPS pero no
es producción: registro muestra el límite, cada invitado lo acepta y el backend
mantiene `real_data_enabled=false`.

La primera forma de bajo costo es un runtime AWS dedicado de host único, separado
de T1, administrado por SSM y publicado solo detrás de un reverse proxy TLS. Es
reversible y se reemplaza antes de admitir datos reales. PostgreSQL, Valkey,
objetos, API y administración permanecen en red no pública.

El inicio con Google puede construirse y probarse con dobles, pero no activarse en
BETA-01 mientras DRG-00 esté cerrado: nombre y correo de una persona ya son datos
personales aunque sus documentos sean sintéticos.

## Consecuencias

- Se puede aprender de UX, concurrencia y estabilidad sin ampliar el techo de datos.
- BETA-01 no mueve S1-READY, DRG-00, DRG-01 ni GA-01.
- Un host único acepta indisponibilidad y RPO de beta; no es arquitectura final.
- Security, Platform, Privacy y QA continúan siendo revisores independientes.

## Rollback

Desactivar registro, retirar DNS y detener el runtime. Backups y recursos se
conservan según la ventana sintética aprobada; no se reutilizan secretos ni digests.
