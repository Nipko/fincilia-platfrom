# Infraestructura

Este directorio fue habilitado por FNC-PLT-002 después del spike FNC-PLT-001. El entorno
mínimo vive en `infra/local`; servicios diferidos no deben agregarse por conveniencia.

El entorno local previsto utilizará Docker Compose y servicios ligados a 127.0.0.1. Debe incluir versiones fijadas, healthchecks, volúmenes nombrados y datos exclusivamente sintéticos.

No crear todavía:

- Recursos cloud productivos. El unico cloud permitido es el spike sintetico T0 de
  `infra/aws`, gobernado por FNC-PLT-010 y sin runtime en su primer apply.
- Egress hacia IA.
- Conectores reales.
- Puertos publicados en 0.0.0.0 sin decisión.
- Secretos en archivos versionados.

Docker Engine vive dentro de Ubuntu/WSL; Git permanece en Windows.
