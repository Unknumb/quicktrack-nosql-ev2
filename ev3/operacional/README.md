# Pregunta operacional QuickTrack

Esta carpeta contiene los archivos de la pregunta operacional de la EV3.

## Pregunta

¿Qué órdenes requieren revisión según el puntaje y el comentario de la valoración, y en qué zona y estado se encuentran?

## Flujo de datos

Cosmos DB for NoSQL → Azure Data Factory → Azure Blob Storage → Power Query → Power BI Desktop.

ADF extrajo las colecciones `valoraciones`, `ordenes_entrega` y `rutas` desde `quicktrack_shared` y escribió los resultados en `salida-etl/operacional`. Las actividades leyeron y escribieron 100 filas por colección.

## Transformación

En Power Query se unieron las valoraciones con las órdenes por `orden_id = id`, y luego con las rutas por `ruta_id = id`. Se creó `prioridad_operacional`, que marca como prioritarias las órdenes con puntaje ≤ 2 o con comentarios que mencionan retraso o producto en mal estado.

## Resultado principal

Se marcaron 49 de 100 órdenes como prioritarias. El puntaje promedio fue 3,07/5. Los casos prioritarios por zona fueron: Centro 9, Norte 10, Oriente 11, Poniente 11 y Sur 8.

## Archivos

- `adf_salida/`: JSON exportados por ADF.
- `evidencias/`: capturas del pipeline, ejecuciones y dashboard.
- `paquete_powerbi/`: archivo `.pbix`.
- `PREGUNTA_OPERACIONAL.md`: definición, proceso y resultados.
- `Pregunta_Operacional_RICE.docx`: pregunta y tabla RICE.

## Limitación

Los datos son históricos y fijos. La clasificación es una regla para orientar la revisión de casos; no constituye una alerta en tiempo real ni confirma la causa de una valoración.