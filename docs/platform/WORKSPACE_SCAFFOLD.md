# Scaffold del workspace

La estructura separa web, API, móvil, workers, contratos, configuración y migraciones. Antes
de S1-READY solo contiene contratos y README: no se instalan frameworks ni se implementa
dominio financiero. El worker futuro devuelve manifiestos; la API es la única candidata a
publicar estado tras autorización server-side.

```text
apps/web        experiencia web
apps/api        monolito modular/control plane
apps/mobile     companion, no cierre complejo
workers/document parsing/OCR aislado
packages/contracts contratos versionados
packages/config configuración validada
db/migrations   SQL forward-only; herramienta pendiente
```

Validación: `python -m tools.workspace_contract.validate`.
