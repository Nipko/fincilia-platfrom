# Vocabulario cross-contract v0.1

Estado: Review pending · Tarea: FNC-ARC-006A · Decisiones humanas: Proposed.

Este contrato explica diferencias intencionales entre niveles de abstracción; no cambia
los catálogos fuente ni acepta DR-ARC-001/DR-PRV-001. El modelo autoritativo para esta
propuesta es `cross-contract-vocabulary.json`.

## Stores

`module-boundaries.json` describe capacidades lógicas. El DFD describe destinos físicos o
operativos. Por eso `object_storage` se descompone en cuarentena, raw y derivados, y
`analytics_store` corresponde a `analytics_projection`. Una relación de mapping no permite
mezclar datos entre zonas ni heredar autoridad.

PostgreSQL, las tres zonas de objetos y el archivo de seguridad tienen persistencia activa
en F01–F13. Temporal, Valkey, analytics projection y vault son capacidades catalogadas sin
un flujo de persistencia activo: hasta que se agregue finalidad, clasificación, retención,
borrado, amenazas y pruebas, persistir allí está prohibido. Vault además espera una
capacidad lógica explícita en module boundaries; no se inventa esa aprobación aquí.

## Clasificación

El DFD necesita dos sentinelas de borde que no son clases válidas de una entidad financiera
canónica:

- `public`: contenido público/minimizado en límites del sistema;
- `prohibited`: contenido que no puede persistirse ni egresar.

Las cuatro clases canónicas son exactamente el subconjunto compartido:
`internal`, `confidential`, `financial_sensitive` y `secret`. Esto no implica que `public`
o `prohibited` desaparezcan; impide que una entidad canónica los use para eludir controles.

La condición de dato personal es un segundo eje. Permanece `pending_human` bajo
DR-PRV-001; `unknown` bloquea egreso cuando el propósito exige esa evaluación.

## Engine release

ADR-023 fija la decisión base. DOM-005 materializó el perfil completo, incluyendo árbol
limpio, lock digest, provenance, attestation, firma, builder y timestamp. Este contrato
comprueba que ADR y perfil no vuelvan a divergir y que la lista ejecutable coincida
exactamente con `lineage-model.json`.

## Verificación

```bash
python -m tools.cross_contract_model.validate
python -m unittest tools.cross_contract_model.test_validate -v
```

Aceptar esta propuesta exige revisión humana de Architecture, Platform, Privacy y Security.
