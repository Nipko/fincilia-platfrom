# Evidencia FNC-PLT-001

- Fecha: 2026-08-21
- Base: `f621236`
- Clasificación de datos: exclusivamente sintética
- Artefacto: `spikes/FNC-PLT-001/`
- Resultado técnico: PASS
- Decisión humana: pendiente

## Resultado

El spike confirma que NestJS/TypeScript, `pg`, PostgreSQL con RLS y workers Python pueden cubrir el patrón mínimo sin compartir la fuente de verdad ni relajar aislamiento. No convierte el spike en producto ni supera S1-READY.

| Prueba | Resultado | Evidencia |
|---|---:|---|
| TypeScript estricto | PASS | `npm run typecheck` en Node 22.20.0 Linux |
| TST-RLS-001 grant verificado | PASS | Solicitud autorizada crea registro en company 1 |
| TST-RLS-002 acceso cruzado | PASS | Subject 1 recibe 403 al solicitar company 2 |
| TST-RLS-002 fuga de pool | PASS | Consulta posterior sin contexto ve 0 registros |
| TST-OUT-001 commit atómico | PASS | Registro y outbox aparecen juntos |
| TST-OUT-001 rollback atómico | PASS | Falla posterior al outbox deja 0 + 0 filas |
| Worker idempotente | PASS | Segundo intento conserva manifiesto y un solo output |
| Colisión de clave | PASS | Misma clave con contenido diferente se rechaza |
| Techo de datos | PASS | Job no sintético se rechaza |
| Compose | PASS | `docker compose config --quiet` |
| Dependencias JS | PASS | `npm audit`: 0 vulnerabilidades reportadas |

Vitest ejecutó 5/5 pruebas en 514 ms dentro del contenedor. `unittest` ejecutó 3/3 pruebas Python en 16 ms. Los tiempos son evidencia funcional local, no benchmark de capacidad.

## Controles observados

PostgreSQL reportó para `fincilia_app`: `rolsuper=false`, `rolcreaterole=false`, `rolcreatedb=false` y `rolbypassrls=false`.

`control.company_grant`, `demo.reconciliation_probe` y `platform.outbox_event` reportaron `relrowsecurity=true` y `relforcerowsecurity=true`. Las tablas de catálogo sintético no son company-scoped y no activan RLS en este spike.

El contexto usa `set_config(..., true)`, equivalente transaccional de `SET LOCAL`, después de `BEGIN`. El acceso se valida consultando un grant filtrado por RLS antes de ejecutar la operación. `COMMIT` o `ROLLBACK` preceden siempre a `release()`.

## Contraste del stack

| Arista | NestJS/TypeScript | Python worker | Conclusión |
|---|---|---|---|
| Dominio/API | Tipos, DI, módulos y contrato HTTP coherentes | Menos alineado con el frontend y contratos TS | TS para control y dominio |
| Transacción/RLS | Wrapper pequeño y verificable sobre `pg` | Posible, pero duplicaría convenciones | La API posee transacciones financieras |
| Parsing/OCR/dataframes | Ecosistema suficiente, no dominante | Ecosistema maduro para documentos y datos | Python para cómputo aislado |
| Idempotencia | Adecuado para comandos/outbox | Adecuado para jobs y manifiestos | Contrato explícito en ambos lados |
| Testing | Vitest + Nest testing fueron directos | `unittest` sin dependencias fue suficiente | Ambos son operables |
| Operación | Dos runtimes aumentan SBOM, imágenes y observabilidad | Requiere límites y despliegue separado | Costo aceptable solo por el aislamiento útil |

## Recomendación

1. Mantener el monolito modular NestJS/TypeScript para dominio y plano de control.
2. Mantener workers Python aislados que reciben jobs versionados y devuelven manifiestos; nunca publican directamente estado financiero.
3. Adoptar PostgreSQL 17 soportado, con runtime no-owner y `FORCE RLS`; fijar el patch exacto por engine release.
4. Encapsular toda operación company-scoped en un wrapper transaccional que establezca subject/company y verifique la delegación.
5. Evaluar en una tarea separada la herramienta de migraciones y la capa de consultas. El SQL manual de este spike no es una estrategia de producción.

## Límites y riesgos abiertos

- `x-subject-id` es un mecanismo sintético de prueba, no autenticación.
- Las contraseñas locales son marcadores reproducibles, no secretos de entorno.
- No se probaron migraciones forward-only, restore, rotación, observabilidad ni carga.
- Las variables de sesión solo son seguras si el rol runtime no se expone al cliente y todo acceso pasa por autorización server-side.
- Las políticas todavía deben recibir revisión independiente de Architecture y Security.
- PostgreSQL y Node están fijados por digest en el spike; la política general de engine release sigue pendiente.
