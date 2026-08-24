-- --------------------------------------------------------------------------- --
-- V0010 — Una version sustituida conserva su firma (FNC-P3.5)
--
-- `ck_release_approval` de V0008 decia «solo una version aprobada tiene
-- referencia de aprobacion». Suena razonable y hace imposible sustituirla: al
-- pasar a `superseded` la referencia sigue ahi —tiene que seguir— y la
-- restriccion la rechaza.
--
-- El error estaba en el enunciado, no en el estado. Lo que hay que impedir es
-- que un **borrador** tenga firma, no que la conserve algo que se aprobo y luego
-- se retiro. Retirar una version no borra que alguien la aprobo, y borrar ese
-- rastro dejaria sin explicacion cuanto produjo mientras estuvo viva.
--
-- Lo detecto una prueba: superseder una release aprobada fallaba con violacion
-- de CHECK, que es exactamente lo que una prueba contra el motor real sirve para
-- encontrar.
-- --------------------------------------------------------------------------- --

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

ALTER TABLE fincilia.engine_release DROP CONSTRAINT ck_release_approval;

-- Aprobada o sustituida: hay firma. Borrador: no la hay. Un borrador con
-- referencia de aprobacion seria una firma sin nada firmado.
ALTER TABLE fincilia.engine_release
  ADD CONSTRAINT ck_release_approval CHECK (
    (state IN ('approved', 'superseded')) = (approval_ref IS NOT NULL));
