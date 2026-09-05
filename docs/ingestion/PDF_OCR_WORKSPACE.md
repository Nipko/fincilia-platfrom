# Espacio de trabajo PDF y OCR local

Fincilia acepta PDF por firma y siempre lo recibe en cuarentena. El analizador
pasivo valida final inequívoco, 25 MiB, 250 páginas, 20.000 objetos y 200.000
bloques; rechaza cifrado, JavaScript, acciones, enlaces, adjuntos, formularios
activos, firmas y estructuras ambiguas. Un PDF seguro con texto embebido sigue
el flujo `pdf_text` de pypdf 6.16.2 y conserva página, bloque, caja, confianza y
release exacta del parser.

Un PDF seguro sin texto suficiente puede procesarse con Tesseract dentro del
worker de documentos. El motor queda deshabilitado por defecto y el entorno
local lo activa con `FINCILIA_OCR_PROVIDER=local_tesseract`. No existe adaptador
de OCR externo ni salida de red asociada al flujo.

## Recorrido y frontera de confianza

1. El PDF original entra en cuarentena y se valida con el mismo analizador
   pasivo del flujo de texto embebido.
2. Solo un PDF seguro, sin texto y dentro de los límites pasa a render local.
3. PDFium rasteriza una página a la vez y Tesseract 5.5.1 produce bloques con
   página, caja y confianza.
4. Todo el texto reconocido, no solo la muestra visible, pasa el escáner de
   secretos antes de promoción.
5. Si la inspección aprueba, el manifiesto canónico se guarda en la zona
   derivada bajo su SHA-256. PostgreSQL conserva únicamente digests, conteos,
   versión, estado y vínculo exacto al artefacto y ejecución.
6. Perfil y extracción leen ese derivado verificando de nuevo su digest. Cada
   registro extraído conserva un localizador `pdf_ocr` y requiere revisión
   humana antes de mapear o publicar.

El contenido reconocido no se escribe en tablas, logs, auditoría ni resultados
de trabajos. Un fallo, truncamiento, timeout, exceso de recursos, digest
divergente o hallazgo sensible termina en cuarentena y no alimenta publicación,
conciliación, cierre ni informes certificados.

## Límites operativos

- máximo 50 páginas por documento;
- máximo 16 millones de píxeles por página y 300 millones por documento;
- máximo 20 segundos por página y 240 segundos por documento;
- máximo 8 MiB de salida TSV por página;
- temporales en `tmpfs` de 64 MiB;
- idiomas locales permitidos: español e inglés;
- releases exactas: Tesseract 5.5.1, pypdfium2 5.13.0 y Pillow 12.3.0.

La implementación recupera texto y coordenadas. La reconstrucción semántica de
tablas densas escaneadas sigue siendo una mejora posterior: hoy el usuario ve
una columna de transcripción OCR y debe limpiar/mapear de forma explícita.

## Rollback y mantenimiento

Para desactivar el productor se usa `FINCILIA_OCR_PROVIDER=disabled` y se
despliega el worker anterior. V0062 y V0063 son expansivas y pueden permanecer
sin productores. No se reescriben migraciones aplicadas. Las políticas de
retención eliminan metadatos y objetos derivados según L-01; restaurar un backup
exige reaplicar los tombstones correspondientes.
