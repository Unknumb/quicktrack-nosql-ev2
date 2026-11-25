# Pregunta estratégica QuickTrack

Esta carpeta contiene los archivos de la pregunta estratégica de la EV3.

## Pregunta

¿Cuál es la evolución anual de la demanda (órdenes), los ingresos facturados y la tasa de cancelación según el tipo de cliente (Empresa vs. Persona) y su zona geográfica, para proyectar qué segmento ofrece el mayor potencial de expansión sostenible?

## Flujo de datos

Cosmos DB for NoSQL → Azure Data Factory → Azure Blob Storage → Python (pandas) → Power BI.

ADF extrajo las colecciones `clientes`, `ordenes_entrega` y `rutas` desde Cosmos DB (`quicktrack`) y escribió los resultados JSON en `salida-etl/`. Las actividades de extracción leyeron y escribieron 100 filas por colección.

## Transformación

El script `transformar_estrategico.py` lee los 3 JSON, normaliza el identificador de clientes (`cli_N`), deriva `tipo_cliente` (Empresa / Persona), une las órdenes con rutas (`ruta_id = id`) y clientes (`cliente_id = id`), y extrae el año de envío (`anio`). Para garantizar compatibilidad regional en Power BI (`es-CL`), los montos monetarios se multiplican por 100 y se guardan como enteros `int64` (`total_centavos`, `ingreso_efectivo_centavos`, `ingreso_perdido_centavos`).

## Resultado principal

Sobre 100 órdenes y un ingreso efectivo de $8.267.595 (23,0% de cancelación global):
- **Persona:** 58 órdenes, $5.307.398 de ingreso efectivo y 19,0% de cancelación.
- **Empresa:** 42 órdenes, $2.960.197 de ingreso efectivo y 28,6% de cancelación (con un pico de 41,2% en 2023).
- **Zonas clave:** Oriente (7,7% cancelación) y Poniente (9,1% cancelación) lideran en rentabilidad y estabilidad para expansión.

## Archivos

- `adf_salida/`: JSON exportados por ADF (`clientes_planos.json`).
- `capturas/`: capturas del dashboard en Power BI.
- `evidencias/`: capturas de ejecución del pipeline en ADF Monitor.
- `out/powerbi/`: CSV generado sin decimales (`estrategico_clientes.csv`).
- `out/`: resúmenes analíticos (`resumen_estrategico.csv`) y log de limpieza (`calidad_datos.txt`).
- `consulta_adf_clientes.sql`: consulta SQL para ADF y guía técnica de configuración.
- `transformar_estrategico.py`: script ETL automatizado con pandas.
- `medidas_dax_powerbi.txt`: las 8 medidas DAX e instrucciones visuales.
- `textos_informe_estrategico.md`: textos redactados para el informe técnico Word.
- `PREGUNTA_ESTRATEGICA.md`: definición, proceso, resultados y limitaciones.
- `Pregunta_Estrategica_RICE.docx`: documento Word con la pregunta y tabla RICE formal.

## Limitación

La muestra consta de 100 órdenes históricas de 64 clientes con 3 años de registro (2024 parcial). Los resultados ofrecen una señal clara de priorización de inversión comercial y deben reevaluarse con un histórico mayor.
