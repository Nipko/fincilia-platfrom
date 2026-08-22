# Arquitectura de información de Fincilia

Estado: `Review pending` · Tarea: `FNC-UX-001` · Datos: exclusivamente sintéticos.

## 1. Principio de organización

La interfaz responde primero “¿dónde debo intervenir?” y después “¿qué evidencia sostiene
esta cifra?”. No se organiza alrededor de módulos técnicos ni promete que una coincidencia
es un hecho. La jerarquía estable es:

```text
Firma / Portafolio
  └─ Empresa autorizada
      ├─ Importación
      │   ├─ Original
      │   ├─ Extracción fiel
      │   ├─ Dataset limpio
      │   └─ Esquema canónico
      ├─ Conciliación
      ├─ Cierre
      ├─ Señales
      ├─ Informes
      └─ Administración
```

`company` sigue siendo la frontera financiera. El portafolio es una proyección de
engagements y grants vigentes; no expresa propiedad de la firma.

## 2. Navegación web

| Área | Pregunta primaria | Acción dominante | Evidencia mínima visible |
|---|---|---|---|
| Portafolio | ¿Qué empresa o ciclo requiere atención? | Abrir empresa priorizada | Estado, periodo, bloqueo, antigüedad |
| Importación | ¿Qué llegó y cómo fue interpretado? | Revisar/marcar/mapejar | Artefacto, versión, hoja/página/celda, confianza |
| Conciliación | ¿Qué explica cada movimiento y diferencia? | Confirmar/rechazar propuesta | Ecuación, componentes, referencias y origen |
| Cierre | ¿Está completo, balanceado y revisado? | Preparar o devolver | Fuentes, saldos, excepciones, SoD y snapshot |
| Señales | ¿Qué inconsistencia merece investigación? | Crear/resolver caso | Razón, baseline, exposición y confiabilidad |
| Informes | ¿Qué resultado reproducible puedo consultar? | Ver/exportar versión | Periodo, definición, release y drill-down |
| Administración | ¿Quién puede hacer qué y por qué ruta? | Gestionar delegación | company, engagement, grant, vigencia y auditoría |

## 3. Import Studio

Las cuatro vistas son estados de evidencia distintos, nunca tabs decorativos:

1. **Original:** bytes/render fiel, hash, versión y procedencia. No se edita.
2. **Extracción fiel:** tokens/celdas tal como fueron leídos, incluidos vacíos y ruido.
3. **Dataset limpio:** resultado versionado de una receta reversible con diff.
4. **Esquema canónico:** campos tipados que podrían alimentar dominio después de controles.

Al enfocar o seleccionar un valor derivado se resalta su origen exacto:

- CSV/XLSX: hoja, fila, columna y celda A1;
- PDF/imagen: página y bounding box;
- XML/OFX/MT940: registro/tag y posición;
- valor inferido: fuentes utilizadas, versión de regla y ambigüedad.

La persona puede marcar cabecera, fila, columna, celda, rango o región. Toda corrección es
un overlay; nunca modifica el original. Una fecha `03/04/26` permanece ambigua hasta que
se confirme locale o exista evidencia determinística suficiente.

## 4. Modelo de estados

| Estado | Presentación | Acción segura |
|---|---|---|
| Vacío | Explica qué falta y por qué importa | Cargar fuente o configurar expectativa |
| Error | Nombra el paso que falló sin culpar al usuario | Reintentar de forma idempotente o aportar alternativa |
| Degradado | Conserva capacidades seguras disponibles | Usar archivo/manual; no inferir éxito |
| Parcial | Muestra rango recibido, esperado e impacto | Completar fuente; bloquea certificación |
| Ambiguo | Muestra interpretaciones y evidencia | Confirmar explícitamente o mantener unknown |
| Sin permiso | Respuesta uniforme, sin revelar existencia ajena | Solicitar acceso por flujo autorizado |
| Procesando | Progreso y última transición comprobada | Salir sin perder job; no inventar porcentaje |

Icono, texto y patrón acompañan el color. `partial`, `unknown` y `unverified` no se
presentan como éxito ni alimentan cierre certificado.

## 5. Conciliación y cierre

Conciliación se organiza por cuenta y periodo. La ecuación visible separa saldo de
extracto, partidas explicadas, partidas abiertas y saldo en libros. Los candidatos muestran
razones y conflictos, no un score opaco. Las relaciones 1:1, 1:N, N:1 y parciales deben
poder recorrerse hasta cada componente.

La sala de cierre muestra, en este orden: completitud de fuentes, reconciliation statements,
excepciones, segregación, aprobaciones y snapshot. Diferencia no explicada distinta de cero
bloquea el estado balanceado. Reapertura crea otra versión.

## 6. Companion móvil

| Permitido inicialmente | Derivar a web |
|---|---|
| Ver solicitud y contexto mínimo | Mapping tabular o PDF complejo |
| Capturar/adjuntar evidencia puntual | Reglas, recetas y schema drift |
| Responder, comentar o devolver | Conciliación masiva o multifuente |
| Aprobar/rechazar propuesta simple con step-up | Materialidad, cierre final o reapertura |
| Ver estado resumido y recordatorio | Administración avanzada y exports masivos |

Las notificaciones push no incluyen montos, contrapartes ni identificadores financieros.

## 7. Accesibilidad y contenido

- Objetivo: WCAG 2.2 AA; revisión humana y pruebas con tecnologías de asistencia pendientes.
- Skip link, landmarks, orden de headings y foco visible.
- Todas las acciones se operan con teclado; no hay interacción exclusiva por hover.
- Tablas conservan headers y captions; los estados usan texto además de color.
- Regiones dinámicas anuncian cambios relevantes mediante `aria-live` sin interrumpir.
- Targets táctiles y espaciado permiten companion móvil; se respeta reducción de movimiento.
- Lenguaje: “propuesta”, “señal” o “inconsistencia”; nunca afirmar una conclusión de fraude.
- Dinero siempre incluye moneda; fecha ambigua incluye locale/interpretación.

## 8. Validación de usabilidad

Antes de aceptar esta arquitectura, ejecutar sesiones con al menos cinco contadores y cinco
personas PYME usando solo ejemplos sintéticos. Tareas: localizar empresa bloqueada, explicar
una celda limpia, resolver fecha ambigua, recorrer un neto hasta su origen, identificar por
qué no se puede cerrar y responder una solicitud móvil. Medir éxito sin ayuda, tiempo,
errores críticos, confianza y comprensión de `partial/unknown`.
