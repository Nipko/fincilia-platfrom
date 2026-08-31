---
id: FNC-PRV-004
status: REVIEW_PENDING
base_sha: 5956b063e676204d43921f3916fae285cf04e34f
data_ceiling: synthetic_only_until_DRG-01
---

# Corrección R2 — persistencia DRG reproducible en Windows y Linux

## Hallazgo ejecutado

El agregador DRG-01 pasaba en Linux/CI, pero fallaba con Python nativo en
Windows. Los descriptores abiertos con `os.open` heredaban modo texto: el
contenido se identificaba por SHA-256 antes de persistir y Windows podía
convertir `LF` a `CRLF` durante `os.write`. Tras corregirlo, la purga reveló un
segundo defecto: un respaldo correctamente marcado read-only no podía
eliminarse en Windows.

## Corrección

- Artefactos, auditoría, inventario y delete ledger añaden `O_BINARY` cuando la
  plataforma lo ofrece.
- La purga conserva los objetos read-only durante su vida. Ante
  `PermissionError`, habilita únicamente el bit de escritura del propietario y
  reintenta el borrado inmediato.
- La evidencia `FNC-PRV-004.json` se renovó con los digests canónicos de las
  fuentes; sus doce resultados semánticos no cambiaron.
- Una regresión comprueba bytes exactos en cuarentena y ausencia de CRLF en los
  tres ledgers durables.

## Evidencia

- 36 pruebas focales en Python Windows: OK.
- Las mismas 36 pruebas en Python Linux/WSL: OK.
- `tools.drg01_readiness.validate` en ambos runtimes: modelo válido, cero
  findings, 14 blockers y `real_data_authorized=false`.

## Límites

No se usaron datos reales ni se aceptó un gate. Legal, Security, Platform y QA
continúan pendientes según el paquete nominal. Este handoff complementa R1 y
no lo modifica.
