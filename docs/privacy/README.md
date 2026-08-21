# Privacidad

Contrato de privacidad, tratamiento, retención y borrado de Fincilia.

| Artefacto | Qué es |
|---|---|
| `PRIVACY_MAP.md` | Documento revisable: principios, roles, finalidades, stores, retención, borrado, portabilidad, derechos, región, IA, cliente, incidentes, DPIA y gates. |
| `privacy-map.json` | Modelo ejecutable y **autoritativo**. Si el documento y el modelo difieren, manda el modelo y la diferencia es un defecto. |
| `tools/privacy_model/validate.py` | Validador determinista, solo biblioteca estándar. |
| `tools/privacy_model/test_validate.py` | Pruebas positivas y negativas por mutación del modelo real. |

## Verificar

```bash
python -m tools.privacy_model.validate
python -m unittest tools.privacy_model.test_validate -v
```

El validador devuelve `{"errors": [...], "ok": true|false}` y termina en 0 solo si el
modelo pasa. No consulta red, reloj, entorno ni aleatoriedad: la misma entrada produce
siempre la misma salida.

## Qué NO es esto

- **No es un concepto jurídico.** `legal_validation` está en `pending_human` y ninguna base legal aparece aceptada.
- **No fija plazos.** Ninguna política declara duración numérica; L-01 es una decisión de Legal y el validador rechaza cualquier número de días, meses o años.
- **No elige región ni proveedor.** `region_decision` está en `pending_A-02` y los ocho destinatarios del registro están sin seleccionar.
- **No habilita IA externa.** `external_ai_enabled: false`, tanto global como por actividad.
- **No supera ningún gate.** Los ocho gates están en `not_met`.

## Estado

`FNC-PRV-001` — **Review pending**. Requiere Privacy y Legal como owners, y revisión de
Security, Architecture y Product. Datos autorizados: `synthetic_only`.
