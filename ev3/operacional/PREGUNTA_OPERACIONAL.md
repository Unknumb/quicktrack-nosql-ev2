# Pregunta operacional

**Responsable:** Nicolas Mansilla

## Pregunta de negocio

¿Qué órdenes requieren revisión según el puntaje y el comentario de la valoración, y en qué zona y estado se encuentran?

## Decisión que respalda

Priorizar qué órdenes registradas revisar desde atención al cliente y operaciones, utilizando el puntaje y el comentario, y consultar la zona y el estado de cada orden.

## Datos utilizados

- `valoraciones`: `orden_id`, `puntaje`, `comentario`.
- `ordenes_entrega`: `id`, `estado`, `ruta_id`.
- `rutas`: `id`, `zona`.

## Regla operacional

Una orden se marca como **Prioritaria** si su puntaje es menor o igual a 2, o si el comentario contiene “retraso” o “mal estado”. Las demás órdenes quedan como **Normal**.

## Resultado

De 100 órdenes, 49 se clasificaron como prioritarias. El puntaje promedio de las valoraciones fue 3,07/5. Por zona, los casos prioritarios fueron: Centro 9, Norte 10, Oriente 11, Poniente 11 y Sur 8.

## Proceso

ADF extrajo las tres colecciones de Cosmos DB y escribió un archivo JSON por colección en Blob Storage. Power Query unió las tablas por sus identificadores y derivó la prioridad. Power BI presenta tarjetas KPI, una segmentación por prioridad, una tabla de casos y un gráfico por zona.

## Limitaciones

La muestra es histórica y no se actualiza en tiempo real. La regla identifica registros para revisión, pero no demuestra que haya ocurrido un retraso ni establece la causa de la valoración.