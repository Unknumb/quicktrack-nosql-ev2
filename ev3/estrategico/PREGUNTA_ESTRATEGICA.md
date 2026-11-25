# Pregunta estratégica

**Responsable:** Genesis Montero

## Pregunta de negocio

¿Cuál es la evolución anual de la demanda (órdenes), los ingresos facturados y la tasa de cancelación según el tipo de cliente (Empresa vs. Persona) y su zona geográfica, para proyectar qué segmento ofrece el mayor potencial de expansión sostenible?

## Decisión que respalda

Priorizar en qué segmento de clientes (Empresa vs. Persona) y en qué zonas geográficas enfocar los recursos comerciales y de inversión logística a mediano y largo plazo (horizonte de 1 a 3 años), mitigando el riesgo financiero derivado de la tasa de cancelación.

## Datos utilizados

- `clientes`: `id` (formato `cli_N`), `tipo_cliente` (Empresa / Persona), `pais`, `fecha_registro`.
- `ordenes_entrega`: `id`, `cliente_id`, `ruta_id`, `fecha_envio` (año), `estado`, `total`.
- `rutas`: `id`, `zona` (Centro, Norte, Oriente, Poniente, Sur).

## Regla estratégica

1. **Derivación de tipo de cliente:** Si el campo `tipo_cliente` no está presente en Cosmos DB, se deriva deterministamente mediante regla de negocio documentada (`_id` divisible por 3 ó 5 → **Empresa** [47%], resto → **Persona** [53%]) para garantizar reproducibilidad analítica.
2. **Dimensión temporal:** Extracción del año (`anio`) a partir de `fecha_envio` (2022, 2023, 2024).
3. **Métricas aditivas y regla regional Power BI (es-CL):** Cálculo de `cancelada` (0/1), `ingreso_efectivo_centavos` (total × 100 si no cancelada) e `ingreso_perdido_centavos` (total × 100 si cancelada) almacenados como enteros `int64` sin decimales para prevenir errores de interpretación regional. En Power BI las medidas DAX dividen entre 100.

## Resultado

De 100 órdenes analizadas ($10.939.613 de ingreso bruto total):
- **Demanda y Facturación:** 100 órdenes generaron un ingreso efectivo de **$8.267.595**, mientras que **$2.672.017** se perdieron por cancelación (23,0% de tasa global).
- **Por Segmento:** **Persona** concentra el 58% de las órdenes (58) y el 64,2% del ingreso efectivo ($5.307.398), con una tasa de cancelación del **19,0%**. En contraste, **Empresa** generó 42 órdenes ($2.960.197) con una tasa de cancelación superior del **28,6%** (alcanzando un crítico 41,2% en 2023).
- **Por Zona:** Oriente (7,7% cancelación, $2.316.760 efectivo) y Poniente (9,1% cancelación, $2.519.359 efectivo) son las zonas más estables. Centro (47,1%) y Norte (36,4%) concentran el mayor riesgo y pérdida económica.
- **Conclusión Estratégica:** Se proyecta priorizar la expansión en el segmento **Persona** en zonas **Oriente y Poniente**, suspendiendo la inversión masiva en B2B Empresa hasta diagnosticar operativamente las causas de cancelación en Centro y Norte.

## Proceso

Azure Data Factory extrajo las 3 colecciones de Cosmos DB for NoSQL mediante proyecciones SQL (`Copiar_Clientes`, `Copiar_Ordenes`, `Copiar_Rutas`) hacia Azure Blob Storage (`salida-etl/`). El script Python (`transformar_estrategico.py`) unió las tres colecciones, normalizó identificadores (`_id` → `cli_N`), derivó los campos aditivos en centavos enteros y generó `estrategico_clientes.csv`. Power BI Desktop / Service consume el CSV mediante un modelo plano con 8 medidas DAX, visualizando 4 tarjetas KPI, 2 gráficos interactivos (evolución anual por segmento y tendencia de cancelación) y 3 segmentadores interactivos.

## Limitaciones

La muestra es de 100 órdenes (muestra histórica cerrada) y 64 clientes únicos. Los datos anuales incluyen solo 3 años (2022 a 2024, con 2024 parcial de 17 órdenes). La zona geográfica proviene de la ruta de entrega asociada y `tipo_cliente` se basa en regla determinista si no viene en el origen NoSQL.
