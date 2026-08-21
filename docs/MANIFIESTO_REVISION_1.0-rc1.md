# Manifiesto del paquete de revisión 1.0-rc1

**Fecha de congelación:** 21 de agosto de 2026  
**Estado:** candidato para revisión externa; todavía no aprobado para construcción, datos reales ni GA

| Archivo | SHA-256 |
|---|---|
| `PLAN_MAESTRO_PLATAFORMA_CONCILIACION.md` | `EE283D1E951D6739005A92B8BBB3CE05B41A128BA2FAB8A9B698BF9A74B53FC8` |
| `PROMPT_REVISION_CLAUDE.md` | `D846487F91D8355BBD6A22406CC806DDCD58D8C2EFF8C9BC3B79F897D6BDF107` |

El revisor debe registrar estos hashes en su respuesta. Si un hash no coincide, debe detenerse, identificar la versión recibida y no presentar el resultado como revisión de `1.0-rc1`.

Verificación en PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath .\PLAN_MAESTRO_PLATAFORMA_CONCILIACION.md
Get-FileHash -Algorithm SHA256 -LiteralPath .\PROMPT_REVISION_CLAUDE.md
```

Validaciones mecánicas antes de congelar:

- 2.186 líneas en el plan y 200 en el prompt.
- Bloques de código balanceados.
- Tablas Markdown con número consistente de columnas.
- Secciones numeradas 0–50 y partes I–X presentes.
- Sin redacción heredada de anualidad a diez meses, feeds 1/3/10, alertas 80/100 ni Temporal condicionado.

Este manifiesto prueba identidad de archivos, no corrección de las decisiones. Claude debe emitir tres veredictos independientes: construcción significativa, piloto con datos reales y GA.
