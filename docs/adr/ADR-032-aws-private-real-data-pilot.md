# ADR-032 — entorno AWS separado para piloto privado real

- Estado: **Proposed; bloqueado por DRG-00/DRG-01 y revisión independiente**
- Fecha: 2026-08-28
- Tareas: FNC-GAT-005 / FNC-PLT-012 / FNC-PLT-013
- Gates: DRG-00 / DRG-01

## Contexto

El Founder quiere probar Fincilia con documentos propios. El host único de
BETA-01 fue diseñado para datos inventados: comparte cómputo, PostgreSQL y
objetos sobre un volumen y no demuestra KMS, Secrets Manager, WAF, IdP real,
restore con tombstones ni aislamiento de egress. Elevar su bandera de datos
sería presentar una topología económica como una frontera de seguridad.

## Decisión propuesta

Crear un entorno `private-pilot` independiente en AWS `sa-east-1`. La única
entrada pública será un ALB HTTPS con ACM y WAF. Aplicación, worker y stores no
tendrán IP pública; PostgreSQL administrado permanecerá en subredes privadas;
objetos usarán buckets separados de cuarentena, evidencia y auditoría con claves
KMS separadas, versionado, bloqueo de acceso público y lifecycle aprobado.

Cognito será el IdP administrado con MFA y usuarios nominales. Google podrá
federarse por Cognito cuando existan dominio, client ID/secret y DRG-00; los
claims nunca otorgarán empresa ni rol. Secrets Manager contendrá credenciales
rotables. CloudTrail y logs de seguridad irán a un archivo separado. El acceso
operativo será SSM, nunca SSH.

Los workers de cuarentena/procesamiento no tendrán egress general. El tráfico
de aplicación que necesite endpoints públicos se separará de esos workers y se
reducirá a destinos justificados; una ausencia de servicio no habilita fallback
a IA, OCR o proveedor externo.

El entorno tendrá un ciclo de costo reversible. El plano persistente conserva
datos, llaves, identidad y auditoría; el plano runtime temporal contiene ALB/WAF,
NAT, endpoints Interface, Valkey y ECS. `cold` retira solo el segundo y solicita
detener RDS. `warm` lo recrea con capacidad ECS cero. Escalar tareas continúa
siendo una operación separada, posterior a gates firmados; el ciclo de costo no
autoriza datos por sí mismo.

## Consecuencias

- BETA-01 puede seguir existiendo para UX sintética, pero nunca recibe copias de
  datos reales ni comparte secretos, estado, buckets o backups con el piloto.
- El costo será mayor que el host beta y debe medirse con un plan real antes del
  apply; los créditos no se consideran un control de seguridad.
- PDF permanecerá en cuarentena hasta que exista escaneo antimalware y análisis
  de contenido completo; CSV/XLSX conservan las guardas actuales y añaden el
  escáner antimalware del entorno.
- DRG-00/01 continúan cerrados hasta evidencias, pentest y firmas humanas.

## Alternativas descartadas

- Habilitar datos reales en el host beta: radio de fallo y controles insuficientes.
- Guardar archivos reales en local: sin aislamiento, auditoría o restore operable.
- Usar una bandera manual como autorización: no prueba ninguno de los controles.

## Rollback

Deshabilitar ingreso, retirar DNS, revocar sesiones y secretos, preservar el
delete ledger, ejecutar la purga conciliada y destruir el entorno únicamente
después de verificar inventario, backups y retención aplicable.
