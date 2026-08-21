# Infraestructura

Este directorio se habilitará mediante FNC-PLT-002 después del spike FNC-PLT-001.

El entorno local previsto utilizará Docker Compose y servicios ligados a 127.0.0.1. Debe incluir versiones fijadas, healthchecks, volúmenes nombrados y datos exclusivamente sintéticos.

No crear todavía:

- Recursos cloud productivos.
- Egress hacia IA.
- Conectores reales.
- Puertos publicados en 0.0.0.0 sin decisión.
- Secretos en archivos versionados.

Docker Engine vive dentro de Ubuntu/WSL; Git permanece en Windows.

