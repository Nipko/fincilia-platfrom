-- --------------------------------------------------------------------------- --
-- V0011 — La funcion del disparador no la ejecuta PUBLIC (FNC-P3.5)
--
-- V0005 registro privilegios por defecto que quitan `EXECUTE` a `PUBLIC` sobre
-- las funciones que cree el migrador. La funcion de V0009 nacio igualmente con
-- `proacl` nulo, y un ACL nulo significa el valor por defecto del motor, que
-- para una funcion es **ejecutable por PUBLIC**.
--
-- Lo delato la prueba que consulta el ACL real en vez de fiarse de la intencion
-- de la migracion. Es la misma prueba que en V0005 destapo que un `REVOKE` de
-- quien no es dueno avisa y no hace nada.
--
-- Que sea un disparador no lo hace inofensivo: `PUBLIC` incluye a cualquier rol
-- futuro, y un privilegio heredado es justo el que nadie revisa.
-- --------------------------------------------------------------------------- --

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.engine_release_is_frozen() FROM PUBLIC;
