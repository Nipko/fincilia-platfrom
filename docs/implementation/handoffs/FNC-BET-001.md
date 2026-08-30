---
task_id: FNC-BET-001
status: REVIEW_PENDING
base_sha: 93dac84
implementation_sha: 90110e70d51c069afa0c5b91e32d86572b585eee
tested_head_sha: 90110e70d51c069afa0c5b91e32d86572b585eee
data_ceiling: synthetic_only
gate_effect: evidence_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Platform/SRE, Privacy/Legal, QA]
---

# Handoff FNC-BET-001 — beta cerrada sintética

## Resultado

`https://fincilia.com` sirve Fincilia sobre HTTPS en `sa-east-1`, con entrada
pública únicamente por 80/443, administración SSM sin SSH, servicios de datos
privados, registro por invitación de un uso y avisos persistentes de uso
exclusivamente sintético.

El release activo es `90110e70d51c069afa0c5b91e32d86572b585eee` en la
instancia `i-03115c49eef006553` y EIP `54.94.132.123`. Los despliegues de release
son in-place, verifican el manifiesto SHA-256, se niegan durante backup/restore y
restauran el release anterior si el servicio no arranca. EC2, EIP y volumen no
se reemplazaron en ninguno de los planes adjudicados.

## Evidencia operacional

| Control | Evidencia |
|---|---|
| HTTPS y contenido | Portada y `/registro` renderizados desde `fincilia.com`; cinco recargas consecutivas sin 503 |
| Mensaje honesto | La portada anuncia invitación, beta cerrada y datos completamente sintéticos; Google apagado |
| Recorrido de producto | SSM `b00d8186-72c7-491b-988c-86345682fb8d`: registro, autenticación, empresa y carga pasaron |
| Procesamiento | `scan`, `profile` y `extract` terminaron `succeeded` para el artefacto sintético |
| Release final | SSM `54f5c500-2cac-441f-8a69-fe0540b36679`: manifest completo OK y release activo |
| Backup | `backups/beta/2026/08/30/20260830T054727Z/`, cuatro objetos con checksums OK |
| Restore | SSM `67330d32-df47-4081-a1b3-531d7931197a`, exit 0; evidencia `restore-checks/beta/20260830T060535Z.json` |
| Contrato AWS | 17 pruebas y `tools.aws_beta.validate`, OK |
| Web | 45 archivos / 263 pruebas unitarias, typecheck, ESLint y build de producción, OK |
| Quality gate | Sin findings sobre el índice integrado |

El recorrido genera credenciales e invitación en memoria, las entrega por stdin
al proceso de API y solo imprime identificadores opacos y estados. Una ejecución
intermedia dejó una segunda identidad/empresa sintética sin documento al descubrir
el multipart inválido; no es accesible porque su secreto no se conserva. No hay
PII ni información financiera real.

## Defectos encontrados ejecutando

1. Un cambio solo web provocaba reemplazo de EC2/EIP/volumen por `user_data`.
   `user_data` queda reservado al alta y el release se despliega por SSM.
2. El restore confundía el PostgreSQL temporal del entrypoint con la base final y
   luego fallaba por roles RLS ausentes en un dump sin owners/ACL. Ahora espera la
   base exacta y crea placeholders `NOLOGIN` desechables.
3. El primer script nuevo no recibió modo ejecutable porque lo instaló el
   desplegador anterior. La invocación explícita no ejecutó producto y el
   desplegador ya activo conoce el nuevo artefacto.
4. El multipart de la sonda codificaba CRLF como texto. La API lo rechazó con 400;
   la representación se corrigió y quedó guardada por el validador.
5. Nginx limitaba también los GET de `/registro` y devolvía 503. El límite de
   autenticación ahora usa una clave solo para POST y responde 429.

## Límites y revisión pendiente

Esta entrega no es producción, no autoriza datos reales, Google, IA externa,
conectores, precios, billing ni SLA. `BETA-01` permanece `not_met` hasta obtener
revisión independiente de Security, Platform/SRE, Privacy/Legal y QA. El Founder
y el implementador no cuentan como segunda mirada.

Para DRG-00/DRG-01 siguen siendo necesarios, entre otros, adjudicación legal y
de retención, región/subencargados, procedencia independiente de supply chain,
secreto/tokenización administrados, controles S-01 y revisión/pentest externos.

## Rollback

Ejecutar por SSM el `deploy-release.sh` del bundle anterior o restaurar el
directorio indicado por la salida `rollback=/opt/fincilia-rollback-*`. El
procedimiento no recrea la instancia ni toca los volúmenes de PostgreSQL, MinIO
o Caddy. Las rutas quedan liberadas para revisión.
