# Git, ramas y worktrees

## Ejecutor elegido

Para este workspace, Git se ejecuta desde Windows/PowerShell. Docker y comandos Linux se ejecutan dentro de Ubuntu/WSL.

No mezclar Git de Windows y Git de WSL sobre el mismo worktree. .gitattributes fija el comportamiento de EOL.

## Modos de colaboración

### Worktrees aislados

Después de existir un commit base:

~~~powershell
$base = git rev-parse main
git worktree add ..\knowledge-app-worktrees\FNC-DOM-001 -b docs/FNC-DOM-001-tenancy $base
~~~

Convenciones:

~~~text
feat/FNC-XXX-000-slug
fix/FNC-XXX-000-slug
docs/FNC-XXX-000-slug
spike/FNC-XXX-000-slug
security/FNC-XXX-000-slug
~~~

El checkout principal queda para Integration Steward. Cada agente recibe un worktree y rutas exclusivas.

### Agentes con filesystem compartido

- Solo el agente raíz ejecuta Git.
- Subagentes no cambian rama, index, lockfiles ni archivos centrales.
- Cada subagente edita rutas disjuntas.
- El coordinador inspecciona, valida e integra.

## Secuencia

1. Registrar tarea, owner, revisor, base SHA y rutas.
2. Crear branch/worktree.
3. Implementar y probar.
4. Entregar handoff con head SHA.
5. Integrar mediante cola.
6. Verificar main.
7. Remover worktree con git worktree remove y liberar reserva.

## Reglas

- Nunca editar main directamente salvo bootstrap inicial del Integration Steward.
- Nunca force-push o reescribir una rama entregada.
- Los conflictos semánticos los resuelven autor + owner, no el integrador a ciegas.
- Contratos/migraciones/lockfiles se serializan.
- Commits pequeños: type(scope): FNC-XXX-000 descripción.

