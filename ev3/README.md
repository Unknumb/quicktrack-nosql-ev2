# QuickTrack · EV3 · Explotación de datos NoSQL para el análisis organizacional

**BDY0101 Base de Datos No Relacionales · Duoc UC** · Integrantes: Alvaro Uribe, Nicolas Mansilla y Genesis Montero · Docente: German Barrientos

La EV3 continúa el caso QuickTrack de la EP2. Cada integrante responde una pregunta de negocio de distinto tipo (táctica, estratégica y operacional) con su tabla RICE y su dashboard.

> **Informe técnico:** [`informe/Informe_Tecnico_EP3_QuickTrack.pdf`](informe/Informe_Tecnico_EP3_QuickTrack.pdf) (editable: `.docx`)

## Flujo de datos

```
Cosmos DB (NoSQL, Serverless) → Azure Data Factory → Blob Storage → Python (pandas) → Power BI
```

1. `cargar_cosmos.py` carga las 5 colecciones del anexo en Cosmos DB for NoSQL (copia `_id` en `id`).
2. El pipeline `PL_ETL_QuickTrack_Tactico` de Data Factory ejecuta 3 consultas SQL (proyección y aplanamiento del historial con `JOIN … IN`) y deja 3 JSON en Blob Storage (`tactico/adf_salida/`). Evidencia en `tactico/evidencias/`: 100, 100 y 302 filas.
3. `transformar_tactico.py` limpia, une las colecciones y calcula los campos derivados. Genera `out/powerbi/tactico_ordenes.csv`, sin decimales (montos en centavos), porque con configuración regional chilena Power BI leía el punto decimal como separador de miles.
4. En Power BI se carga ese CSV y se crean las 8 medidas DAX (`tactico/paquete_powerbi/medidas.dax`).

## Pregunta táctica (Alvaro Uribe)

> ¿Qué zonas de reparto y tramos de distancia concentran la mayor tasa de cancelación y el mayor ingreso perdido, y la distancia de la ruta explica esas cancelaciones?

- **Resultado:** 23,0 % de cancelación, $2.672.017 de ingreso perdido; Centro (47,1 %) y Norte (36,4 %) concentran 16 de las 23 cancelaciones y el 72 % del ingreso perdido. La distancia no explica la cancelación.
- Tabla RICE y decisiones: [`tactico/Pregunta_Tactica_RICE.docx`](tactico/Pregunta_Tactica_RICE.docx) y [`tactico/PREGUNTA_TACTICA.md`](tactico/PREGUNTA_TACTICA.md).
- Capturas del dashboard en Power BI: [`informe/figuras/`](informe/figuras/) (`fig_pbi_*.png`).
- Para reconstruir el dashboard en Power BI Desktop: [`tactico/paquete_powerbi/`](tactico/paquete_powerbi/).

## Cómo reproducirlo

Requiere Python 3 con `pandas` y `azure-cosmos`. **Las credenciales no se suben al repositorio**: se pasan por variables de entorno.

```bash
export COSMOS_ENDPOINT="https://<cuenta>.documents.azure.com:443/"
export COSMOS_KEY="<clave primaria>"
python tactico/cargar_cosmos.py --datos data          # carga las 5 colecciones
# ejecutar el pipeline en ADF y bajar los 3 JSON a tactico/adf_salida
python tactico/transformar_tactico.py --entrada tactico/adf_salida
# Power BI: Crear > Cargar un archivo > tactico/out/powerbi/tactico_ordenes.csv
```

Para probar la transformación sin Azure: `python tactico/transformar_tactico.py --desde-crudo data`.

## Preguntas de los otros integrantes

_Pendiente: Nicolas Mansilla y Genesis Montero agregan aquí su pregunta, su tabla RICE y sus evidencias._
