# Evidencia FNC-PLT-002

La evidencia reproducible es el lifecycle `TST-LOCAL-001`, no una captura manual.

Secuencia:

1. `docker compose config --quiet` valida interpolación y estructura.
2. `down --volumes` garantiza arranque desde cero sobre el volumen exacto del proyecto.
3. `up --wait postgres` exige healthcheck verde.
4. El runner comprueba marcador sintético, rol sin privilegios y aislamiento de `public`.
5. Inserta un probe sintético, reinicia el contenedor y comprueba persistencia.
6. Ejecuta stop/start y vuelve a comprobar el mismo probe.
7. La limpieza final elimina contenedores, red y el volumen nombrado.

La revisión humana de Platform/Security/Architecture permanece pendiente. Esta evidencia no
aprueba una migración de producto ni un motor de object storage.

Corrida local observada el 2026-08-21: bootstrap limpio `PASS`, persistencia tras `restart`
`PASS`, persistencia tras `stop/start` `PASS` y purga final del volumen exacto `PASS`.
