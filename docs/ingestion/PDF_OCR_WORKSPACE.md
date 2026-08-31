# Espacio de trabajo PDF y frontera OCR

Fincilia acepta PDF por firma, siempre en cuarentena. El escáner del worker
aislado valida el final inequívoco, los límites de 25 MiB, 250 páginas, 20.000
objetos y 200.000 bloques, y rechaza cifrado, JavaScript, acciones, enlaces,
adjuntos, formularios activos, firmas y estructuras que el parser estricto no
pueda resolver.

Un PDF pasivo con texto embebido se copia a `raw` y cada bloque se guarda como
`raw_record` con identidad del artefacto, página, ordinal, caja normalizada,
confianza y versión del parser. Eso es evidencia extraída, no semántica
contable: requiere revisión humana y jamás publica movimientos por sí mismo.

Un PDF pasivo sin texto suficiente queda en cuarentena con `ocr_required`. El
puerto OCR está implementado pero desactivado. Activarlo exige adjudicar al
final proveedor, región, idiomas, costo/páginas, conservación, DPA, política por
empresa y salida exclusivamente por el AI Gateway. No se envían archivos ni
texto a terceros con la configuración actual.

La biblioteca está fijada a `pypdf 6.16.2` y sus dos artefactos PyPI por hash.
El resultado registra `pypdf-6.16.2/fincilia-pdf-1`, por lo que una lectura
posterior puede demostrar exactamente qué parser produjo el workspace.
