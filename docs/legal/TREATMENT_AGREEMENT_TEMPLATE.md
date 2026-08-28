# Plantilla de tratamiento previa a datos reales

Esta es una lista de revisión, no un contrato firmado ni asesoría jurídica. Su
única salida técnica válida es **lista para revisión por abogado independiente**.
No autoriza corpus real, piloto, proveedor, región, plazo de retención ni rol de
Fincilia. Mientras los campos humanos sigan pendientes, rige `synthetic_only`.

El contrato ejecutable está en `treatment-agreement-template.json` y se valida
contra las actividades de `docs/privacy/privacy-map.json`; por tanto, una nueva
actividad dirigida a `DRG-00` o `DRG-01` no puede quedar invisible.

## Decisiones que debe producir la revisión humana

El abogado nominal debe resolver por actividad, con fundamento y evidencia:

1. Partes, capacidad, finalidad y operaciones autorizadas.
2. Rol de Fincilia y de cada empresa: no se presume Responsable o Encargado.
3. Categorías de titulares y datos; minimización y contenido prohibido.
4. Aplicabilidad del contrato de transmisión/tratamiento por actividad.
5. Región, proveedor, receptores, subencargados y circulación internacional.
6. Base jurídica, instrucciones, derechos, consultas y reclamos.
7. Retención desde el evento correcto, legal hold, devolución y supresión.
8. Backups, restore, `delete ledger`, portabilidad y terminación.
9. Medidas técnicas, incidentes, confidencialidad y auditoría.

No deben escribirse nombres civiles, documentos, firmas, credenciales, PII ni
evidencia contractual sensible en Git. El repositorio sólo conservará alias
estables, estados y referencias no secretas a evidencia custodiada externamente.

## Cobertura dinámica vigente

| Gate | Actividades descubiertas en el mapa de privacidad |
|---|---|
| DRG-00 | PA-04, PA-05, PA-15, PA-22, PA-23 |
| DRG-01 | PA-03, PA-08, PA-10, PA-13, PA-16, PA-17 |

Cada fila permanece con `contract_applicability: pending_legal` y
`fincilia_role: not_determined_pending_legal` hasta adjudicación nominal.

## Fuentes oficiales consultadas

- SUIN, Ley 1581 de 2012: definiciones, principios y deberes a interpretar por
  el abogado.
- SIC, política de tratamiento: referencia oficial sobre contenido y medidas.
- SIC, diferencia entre transferencia y transmisión: pregunta de calificación
  para cada actividad.
- SIC, concepto sobre Circular 002 de 2025: transmisión internacional y
  responsabilidad demostrada.

Las URL completas, su fecha de consulta y el uso acotado están versionados en el
JSON. El artefacto no reproduce textos extensos ni extrae conclusiones legales.

## Salida y segregación

Se requieren tres vistos buenos: Legal, Privacy y Security. `FOUNDER-01` puede
ser accountable provisional, pero no cuenta como abogado o revisor
independiente de una decisión propia. La revisión debe registrar alias del
profesional, fundamento profesional, fecha y referencia externa de evidencia.

Incluso con el concepto jurídico, A-02 y L-01 se adjudican en sus propios
contratos; Security debe demostrar aislamiento y egress; QA debe demostrar el
gate. Esta plantilla, aislada, nunca cambia `DRG-00` ni `DRG-01`.

## Verificación local

```text
python -m tools.legal_treatment validate
python -m tools.legal_treatment report
python -m unittest tools.legal_treatment.test_model
```

Un `ok: true` significa que el paquete está estructuralmente listo para el
abogado. Siempre debe coexistir con `real_data_authorized: false`.
