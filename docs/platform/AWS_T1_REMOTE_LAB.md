# AWS T1 — laboratorio remoto sintetico

T1 ejecuta el mismo recorrido local de Fincilia en una instancia temporal sin exponer
puertos a Internet. Es una prueba operativa real de despliegue, no un entorno productivo
y no admite documentos financieros reales.

## Acceso

La instancia no tiene SSH ni ingress. Con AWS CLI y Session Manager Plugin:

```bash
aws ssm start-session \
  --profile fincilia-sandbox \
  --target '<INSTANCE_ID>' \
  --document-name AWS-StartPortForwardingSession \
  --parameters 'portNumber=53000,localPortNumber=53000'
```

Mientras la sesion esta abierta, la web se visita en <http://127.0.0.1:53000>. La API
puede tunelizarse por separado desde el puerto remoto 58080.

La sesion termina con `Ctrl+C`; cerrar el tunel no detiene la instancia. El host se
detiene por sus dos guardas de cuatro horas o mediante una operacion AWS explicita.

## Estado verificado — 2026-08-28

El release `a710c9e421852a54e35613de81f025fe3c533efc` se desplego por digest y completo
`cloud-init`. PostgreSQL, Valkey, MinIO, API, worker y web quedaron saludables; el
esquema alcanzo `V0038` y la API devolvio `ready`.

Con datos exclusivamente sinteticos se demostraron:

- autenticacion de dos identidades y portafolios de dos y una empresas;
- denegacion `403` al intentar cruzar la frontera de empresa;
- resolucion de fuente, carga, cuarentena y promocion del documento;
- backup y restore en una base independiente con conteos equivalentes;
- web HTTP 200 por un tunel SSM ligado a loopback;
- plan posterior `No changes`, sin key pair y con cero reglas de ingress.

Estas evidencias habilitan pruebas humanas sinteticas del laboratorio, no DRG-00 ni
DRG-01. ADR-030 y las revisiones independientes permanecen pendientes.

## Limites operativos

- El primer boot programa `shutdown --poweroff +240` antes de tocar red, S3 o Docker.
- Un timer persistente vuelve a programar `poweroff` a las cuatro horas de cada boot;
  EC2 interpreta ambos shutdown como stop.
- No existe Elastic IP: el egress usa una IP publica efimera y no hay inbound.
- El root EBS cifrado persiste al detener, pero se elimina al terminar la instancia.
- Los secretos sinteticos se generan en `/opt/fincilia/runtime.env` modo 0600.
- Solo el seed sintetico `demo.local` esta permitido.

## Camino hacia un piloto real

1. demostrar deploy y dos reinicios sin drift;
2. ejecutar smoke, E2E, a11y y aislamiento cross-company;
3. demostrar backup/restore en un host reemplazable;
4. escanear imagenes y resolver hallazgos criticos/altos;
5. decidir RDS, secretos, IdP, dominio, TLS, observabilidad y retencion;
6. obtener revisiones independientes Security/Privacy/Legal/Accounting;
7. cerrar DRG-00 para corpus real y DRG-01 para un piloto limitado.
