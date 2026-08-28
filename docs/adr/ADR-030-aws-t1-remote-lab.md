# ADR-030 — Host unico y SSM para el laboratorio remoto T1

- Estado: **Proposed, autorizado solo como laboratorio reversible**
- Fecha: 2026-08-28
- Tarea: FNC-PLT-011
- Gate: T1-SYNTHETIC-RUNTIME

## Contexto

La plataforma necesita ejercerse fuera del portatil antes de asumir el costo y la
complejidad de RDS, NAT Gateway, ALB y un dominio. El stack actual funciona como seis
contenedores y conserva datos exclusivamente sinteticos.

## Decision del laboratorio

Usar una sola `t3.small` x86_64 en la subred publica T0, con IP efimera para egress pero
sin regla de ingress. Session Manager es el unico plano de acceso. Un timer del sistema
apaga la maquina a las cuatro horas de cada boot; el shutdown detiene, no termina.

PostgreSQL, Valkey y MinIO permanecen en Docker sobre un root gp3 cifrado. Esta topologia
no es productiva ni una decision de persistencia: su objeto es demostrar deploy, recorrido,
aislamiento, backup/restore y operacion remota al costo minimo.

## Alternativas

- RDS + EC2: mejor frontera de datos, pero agrega costo permanente antes de medir carga.
- ECS/Fargate + RDS: mayor operabilidad, pero requiere red/secretos/ingress adicionales.
- ALB o CloudFront: acceso HTTPS publico, bloqueado hasta dominio y threat review.
- SSH: descartado; requeriria key pair e ingress que SSM vuelve innecesarios.

## Consecuencias

- La caida o reemplazo del host puede perder el laboratorio; solo contiene datos sinteticos.
- El EBS se conserva durante stop, no durante reemplazo/terminacion.
- Una nueva tarea debe seleccionar RDS, gestor de secretos e IdP antes de un piloto real.
- Sin revisores independientes, este ADR permanece Proposed.
