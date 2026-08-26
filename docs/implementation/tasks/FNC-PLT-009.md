---
id: FNC-PLT-009
title: Runtime local persistente de Docker Engine en Windows y WSL
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 63484e4
implementation_sha: 2ef810f
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Platform/SRE, Security, Developer Experience]
---

# Resultado

Permitir que el stack local permanezca activo despues de que termine el comando
de arranque en Windows. El wrapper mantiene una unica sesion WSL oculta y
reversible, opera solo `fincilia-local` y conserva volumenes al apagar.

# Alcance reservado

- Wrapper PowerShell de Windows para `doctor`, `up`, `status` y `down`.
- Contrato/validador del puente WSL y pruebas de invariantes destructivas.
- Actualizacion de la decision `UD-PLT-CLI-WSL`, documentacion local y handoff.

# Criterios

- El keepalive se inicia sin ventana y se identifica por PID y linea de comando.
- No se usa `wsl --shutdown`, `wsl --terminate`, `docker system prune`,
  `--volumes` ni `--remove-orphans`.
- `up` espera Docker, ejecuta el lifecycle existente y demuestra persistencia
  despues de cerrar el proceso invocador.
- `down` afecta solo el proyecto/compose allowlisted, conserva datos y detiene
  unicamente el keepalive que creo Fincilia.
- Estado local fuera del repo contiene solo PID, distribucion e instante; nunca
  credenciales, variables de entorno o datos financieros.

# Limites

No instala ni actualiza WSL/Docker, no modifica `.wslconfig`, no abre ventanas,
no toca otras distribuciones y no autoriza datos reales.

# Verificacion requerida

- Platform/SRE: lifecycle, recuperacion, WSL/systemd y limites de proceso.
- Security: argv, PID reciclado, estado minimo y ausencia de operaciones globales.
- Developer Experience: comandos, diagnostico y salida estructurada.
