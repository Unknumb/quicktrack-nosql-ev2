# QuickTrack · EP3 · Pregunta TÁCTICA (RICE + ETL + Dashboard)

Base conceptual: PPT *3.1.1 Diseño de procesos ETL para datos NoSQL* (tipos de requerimiento, RICE, tipos de transformación, ETL vs ELT) y *LAB 3.1.2* (ADF + Cosmos DB). Las cifras de este documento fueron **medidas** con `transformar_tactico.py` sobre los datos del anexo Forma B. Impact y Confidence son criterio razonado, justificado con esa evidencia (igual que en el documento de Ejercicios RICE del equipo).

---

## 1. Tipo de requerimiento y pregunta

El PPT define **táctico** como "orientado a procesos internos, seguimiento de indicadores, productividad". Es el nivel del jefe de operaciones que decide **qué rutas/zonas revisar este trimestre**, no el de la tendencia a largo plazo (estratégico) ni el de la alerta del día (operacional).

> **Pregunta táctica:** ¿Qué zonas de reparto y tramos de distancia concentran la mayor tasa de cancelación y el mayor ingreso perdido, y la distancia de la ruta explica esas cancelaciones, para decidir en qué rutas intervenir primero?

Se alinea con el objetivo del caso: *identificar zonas críticas de reparto* y *optimizar rutas de entrega*.

**Hipótesis que el dashboard pone a prueba:** "las rutas largas cancelan más". Con estos datos **no se sostiene** (ver §6): lo que separa a las zonas es la zona, no la distancia.

**Análisis de requerimientos** (las tres preguntas guía del PPT 3.1.1, antes de extraer o transformar):

| Pregunta guía | Respuesta |
|---|---|
| ¿Qué decisión hay que respaldar? | En qué zonas y rutas intervenir primero para reducir cancelaciones y pérdida de ingresos (horizonte de semanas o meses). |
| ¿Qué datos tenemos hoy? | 5 colecciones en Cosmos DB; esta pregunta usa 3: `ordenes_entrega` (estado, total, ruta), `rutas` (zona, distancia) y `seguimiento` (historial, solo para perfilar su calidad). |
| ¿Qué patrón buscamos? | Zonas y tramos donde se concentran la cancelación y el ingreso perdido, y si la cancelación crece con la distancia. |

**Resultados medidos (100 órdenes, 23 canceladas, $2.672.017 perdidos):**

| Zona | Órdenes | % cancelación | Ingreso perdido | ¿Crítica? (> 23,0 % global) |
|---|---|---|---|---|
| Centro | 17 | 47,1 % | $1.111.187 | Sí |
| Norte | 22 | 36,4 % | $810.247 | Sí |
| Sur | 13 | 23,1 % | $314.579 | Marginal (23,08 vs 23,0) |
| Poniente | 22 | 9,1 % | $231.836 | No |
| Oriente | 26 | 7,7 % | $204.169 | No |

Centro + Norte = 16 de las 23 cancelaciones (70 %) y 72 % del ingreso perdido.
Por tramo: <500 km 28,6 % · 500-999 km 17,6 % · 1.000-1.499 km 31,0 % · ≥1.500 km 15,2 % (sin patrón creciente).

---

## 2. Tabla RICE (pregunta táctica)

`Puntaje = (R × I × C) ÷ E` · Regla: ≥ 1 conservar · 0,5-1 evaluar · < 0,5 descartar.

| Atributo | R | I | C | E | Puntaje | Decisión | Evidencia medida y justificación |
|---|---|---|---|---|---|---|---|
| `ordenes.total` | 1,0 | 3 | 1,0 | 1 | **3,00** | Conservar | 100/100, numérico, sin nulos. Es la base del ingreso perdido. |
| `ordenes.ruta_id` | 1,0 | 2 | 1,0 | 1 | **2,00** | Conservar | 100/100 órdenes apuntan a una ruta válida (0 huérfanas). Clave para cruzar con `rutas`. |
| `ruta.zona` | 1,0 | 3 | 0,8 | 1 | **2,40** | Conservar | 5 valores limpios. C = 0,8 porque la zona no coincide con la geografía origen→destino (ver ciudades). |
| `ordenes.estado` (cancelación) | 1,0 | 3 | 0,7 | 1 | **2,10** | Conservar | 100/100, 4 valores, sin nulos. C = 0,7: solo coincide con el último evento del historial en 19/100 órdenes. Se toma el estado de la orden como fuente de verdad. |
| `ruta.distancia_km` | 1,0 | 2 | 0,4 | 1 | **0,80** | Evaluar | Se conserva **solo agrupada en tramos** (no valor exacto). El mismo par origen→destino aparece con distancias de 114 a 1.946 km. |
| `seguimiento.historial[].fecha` (tiempo de ciclo) | 1,0 | 3 | 0,3 | 3 | **0,30** | Descartar | Brecha entre eventos = **2 días en 202/202 pares**. Toda orden que llega a "Entregado" tarda exactamente 6 días: la métrica no discrimina entre zonas. Effort 3 (JOIN + fechas). |
| `seguimiento.historial[].estado` (último evento) | 1,0 | 2 | 0,3 | 2 | **0,30** | Descartar | 8 órdenes "Cancelado" tienen un evento "Entregado". Contradice a `ordenes.estado` en 81/100. |
| `ruta.ciudad_origen` / `ciudad_destino` | 1,0 | 1 | 0,4 | 1 | **0,40** | Descartar | 24 pares únicos en 100 rutas; 23 de ellos aparecen en más de una zona. No sirve como etiqueta de ruta. |
| `ordenes.fecha_envio` | 1,0 | 0,5 | 0,5 | 1 | **0,25** | Descartar | No es dimensión de esta pregunta; además 88/100 envíos son anteriores al registro del cliente (ver Ejercicio 1 del equipo). Lo usa la pregunta estratégica. |
| `ordenes.medio_pago` | 1,0 | 0,25 | 1,0 | 1 | **0,25** | Descartar | Dato limpio, pero no responde esta pregunta (lo usa la de satisfacción por medio de pago). |

> El `id` se conserva siempre como clave y no se evalúa con RICE (aquí `orden_id` y `ruta_id`), según el PPT.

**Consecuencia para el equipo:** el Ejercicio 6 del documento "Ejercicios RICE" dio `historial[].fecha` = 0,7 (*evaluar*) con C = 0,7. La brecha constante de 2 días (medida después) baja esa C a ~0,3. Conviene corregirlo o citarlo como evidencia nueva.

---

## 3. Transformaciones (tipos del PPT)

| # | Tipo (PPT) | Qué se hace | Dónde |
|---|---|---|---|
| 1 | **Aplanamiento** | `seguimiento.historial[]` → una fila por evento (`JOIN h IN s.historial`). Se usa solo para profiling de calidad. | ADF (consulta Cosmos SQL) |
| 2 | **Proyección / selección** | Solo los campos que RICE conserva; se omite `_rid`, `_etag`, `_ts`, `correo`, etc. | ADF (SELECT) |
| 3 | **Conversión de tipo** | `total`, `distancia_km` → numérico; fechas → datetime | `transformar_tactico.py` |
| 4 | **Normalización de texto** | `strip()` + `title()` en zona/ciudades y estado | `transformar_tactico.py` |
| 5 | **Limpieza** | Duplicados por `id`, nulos, integridad referencial (0 huérfanas) | `transformar_tactico.py` |
| 6 | **Campos derivados** | `cancelada` (0/1), `ingreso_perdido`, `tramo_distancia` (4 tramos) | `transformar_tactico.py` |
| 7 | **Consolidación** | `ordenes` ⟕ `rutas` → una tabla de hechos plana (1 fila por orden) | `transformar_tactico.py` |

**ETL vs ELT:** en ETL se transforma **fuera del motor**, antes de cargar; en ELT, **dentro del motor** o con herramientas sobre él. Este flujo es **mixto**, con predominio de ETL:

| Etapa | Dónde se transforma | Estilo | Qué se hace |
|---|---|---|---|
| Extracción con ADF | Dentro de Cosmos DB (consultas SQL) | ELT | Proyección y aplanamiento del historial (`JOIN … IN`). El PPT lo describe así: "se transforman con consultas SQL de Cosmos". |
| Transformación en Python | Fuera del motor (pandas) | ETL | Limpieza, tipos, unión de colecciones y campos derivados. Es el ejemplo ETL del PPT: un script Python con pandas que limpia y luego carga. |

---

## 4. Azure: de `TiendaDB/clientes` a `quicktrack`

La configuración del LAB (Data Factory, Linked Service a Cosmos, Linked Service a Blob, contenedor `salida-etl`) **se reutiliza**. Cambian base, colecciones y consultas.

### 4.1 Cargar QuickTrack en Cosmos DB (una sola persona del equipo)

```bash
pip install azure-cosmos
export COSMOS_ENDPOINT="https://<cuenta>.documents.azure.com:443/"
export COSMOS_KEY="<clave primaria>"          # no la subas al repositorio
python cargar_cosmos.py --datos "../../data" --dry-run   # valida
python cargar_cosmos.py --datos "../../data"             # carga
```

Por qué un script y no "New Item": son 500 documentos. Además Cosmos DB for NoSQL exige un campo `id` y los datos traen `_id` (MongoDB); el script copia `_id` → `id`. Crea la base `quicktrack` y 5 contenedores (`clientes` /pais, `rutas` /zona, `ordenes_entrega` /ruta_id, `seguimiento` /orden_id, `valoraciones` /orden_id).

### 4.2 Linked Service y Datasets

| Recurso | Nombre sugerido | Configuración |
|---|---|---|
| Linked Service origen | `LS_CosmosDB_QuickTrack` | Cosmos DB for NoSQL, base `quicktrack` → *Test connection* |
| Linked Service destino | `LS_Storage_Analitica` | el mismo del LAB |
| Dataset origen ×3 | `DS_Cosmos_Ordenes`, `DS_Cosmos_Rutas`, `DS_Cosmos_Seguimiento` | colecciones `ordenes_entrega`, `rutas`, `seguimiento` |
| Dataset destino ×3 | `DS_Blob_OrdenesPlanas`, `DS_Blob_Rutas`, `DS_Blob_SeguimientoEventos` | JSON en `salida-etl`: `ordenes_planas.json`, `rutas.json`, `seguimiento_eventos.json` |

### 4.3 Pipeline `PL_ETL_QuickTrack_Tactico` (3 actividades *Copy data* en paralelo)

Source → *Use query = Query*:

```sql
-- Copiar_Ordenes  (100 filas esperadas)
SELECT c.id, c.cliente_id, c.ruta_id, c.fecha_envio, c.estado, c.medio_pago, c.total
FROM c

-- Copiar_Rutas  (100 filas esperadas)
SELECT c.id, c.zona, c.ciudad_origen, c.ciudad_destino, c.distancia_km
FROM c

-- Copiar_Seguimiento_Eventos  (302 filas esperadas: aplana el arreglo historial)
SELECT s.orden_id, h.estado AS estado_evento, h.fecha AS fecha_evento
FROM s
JOIN h IN s.historial
```

Sink → *Set of objects*. Mapping → *Import schemas* (sin renombres necesarios).

Validación (Paso 5 del LAB): *Validate* → *Publish all* → *Trigger now* → Monitor. Debe decir **Rows read / written = 100, 100 y 302**. Si no coincide, hay documentos sin cargar. Descarga los 3 JSON del contenedor `salida-etl` a `./adf_salida/`.

> Las 3 consultas se **probaron contra la cuenta real** (`evaluacion3`, base `quicktrack`, modo Serverless) con el SDK de Python y devolvieron 100, 100 y 302 filas. En ADF deben salir los mismos conteos en Monitor. El script `transformar_tactico.py --desde-crudo` reproduce localmente el mismo aplanado.
> Cuenta Serverless: no usar `--throughput` en `cargar_cosmos.py` (Azure lo rechaza).

---

## 5. Transformar y generar el modelo de Power BI

```bash
pip install pandas
python transformar_tactico.py --entrada ./adf_salida        # datos reales salidos de ADF
python transformar_tactico.py --desde-crudo ../../data   # prueba local
```

Genera en `out/`:
- `tactico_ordenes.csv`: tabla de hechos (1 fila/orden) con decimales: `orden_id, estado, cancelada, total, ingreso_perdido, ruta_id, zona, distancia_km, tramo_distancia`.
- `powerbi/tactico_ordenes.csv`: **el que se carga en Power BI**. Sin decimales: `total_centavos` e `ingreso_perdido_centavos` (enteros) y `distancia_km` entera. Con la configuración regional es-CL, Power BI leía `134152.77` como 13.415.277 y el ingreso perdido sumaba 236.146.506 en vez de 2.672.017.
- `tactico_zona_tramo.csv`: resumen para validar contra los visuales.
- `calidad_datos.txt`: evidencia de limpieza para el informe.

**Modelo de datos (IE5):** una sola tabla plana `tactico_ordenes`. Se aplanó antes de cargar para que Power BI no tenga que resolver relaciones ni listas anidadas. Todo KPI sale de dos columnas aditivas (`cancelada`, `ingreso_perdido`).

### Medidas DAX finales (8 medidas)

Se crean en este orden (cada una usa a las anteriores). El archivo `paquete_powerbi/medidas.dax` las trae todas juntas.

```DAX
Ordenes = COUNTROWS ( tactico_ordenes )
Canceladas = SUM ( tactico_ordenes[cancelada] )
Pct Cancelacion = DIVIDE ( [Canceladas], [Ordenes] )
Ingreso Perdido = SUM ( tactico_ordenes[ingreso_perdido_centavos] ) / 100
Pct Cancelacion Global = CALCULATE ( [Pct Cancelacion], ALL ( tactico_ordenes ) )
Zona Critica = IF ( [Pct Cancelacion] > [Pct Cancelacion Global], 1, 0 )
Zonas Criticas = SUMX ( VALUES ( tactico_ordenes[zona] ), [Zona Critica] )
Pct Ingreso Perdido Zonas Criticas =
    DIVIDE (
        CALCULATE ( [Ingreso Perdido], FILTER ( VALUES ( tactico_ordenes[zona] ), [Zona Critica] = 1 ) ),
        CALCULATE ( [Ingreso Perdido], ALL ( tactico_ordenes ) )
    )
```

Valores sin filtros: **23,0 % · $2.672.017 · 3 zonas críticas · 83,7 %**. El último KPI divide por el ingreso perdido **total** (`ALL`), no por el de la selección: con la zona Centro filtrada muestra 41,6 % ($1.111.187 de $2.672.017).

Carga en Power BI Service (navegador): *Crear → Cargar un archivo → `out/powerbi/tactico_ordenes.csv`*; luego crear las medidas en la vista de modelo o en la vista de consultas DAX.

---

## 6. Dashboard (boceto, IE6/IE7/IE10)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ QuickTrack · Zonas críticas de reparto            [Segmentador: Zona] [Tramo]│
├───────────────┬───────────────┬───────────────┬──────────────────────────────┤
│ % Cancelación │ Ingreso       │ Zonas         │ % Ingreso perdido            │
│    23,0 %     │ perdido       │ críticas      │ en zonas críticas            │
│               │ $2.672.017    │     3         │      ~84 %                   │
├───────────────┴───────────────┴──────┬────────┴──────────────────────────────┤
│ ① Barras: % cancelación por zona     │ ② Matriz zona × tramo de distancia    │
│   + línea del promedio global (23 %) │   (% cancelación, mapa de calor,      │
│   Centro 47 · Norte 36 · Sur 23 ·    │   con n en tooltip)                   │
│   Poniente 9 · Oriente 8             │                                       │
├──────────────────────────────────────┼───────────────────────────────────────┤
│ ③ Columnas: ingreso perdido por zona │ ④ Columnas: % cancelación por tramo   │
│                                      │   (prueba de la hipótesis "rutas      │
│                                      │    largas cancelan más")              │
└──────────────────────────────────────┴───────────────────────────────────────┘
```

| Visual | Por qué ese gráfico | Responde |
|---|---|---|
| Tarjetas KPI ×4 | Lectura de un vistazo para el jefe de operaciones | ¿Cuán grave es el problema? |
| ① Barras + línea de promedio | Comparar categorías contra un umbral | ¿Qué zonas superan el promedio? |
| ② Matriz de calor zona × tramo | Dos dimensiones categóricas a la vez | ¿Dónde se concentra el problema? |
| ③ Columnas de ingreso perdido | Pasar de % a dinero | ¿Dónde duele más? |
| ④ Columnas por tramo | Contrastar la hipótesis de distancia | ¿La distancia explica la cancelación? |

Interactividad: los segmentadores de zona/tramo filtran todos los visuales (referencia cruzada).

**Limitaciones que hay que declarar en el informe:** (1) muestra de 100 órdenes: la matriz zona × tramo tiene celdas con n = 1-4, por eso se muestra n en el tooltip; (2) `distancia_km` tiene baja Confidence; (3) Sur supera el promedio por solo 0,08 puntos; (4) tiempo de ciclo y retraso se descartaron por datos sintéticos con brecha constante: el informe debe decir que **no se puede medir retraso** con estos datos.

---

## 7. Arquitectura del flujo (IE4/IE5)

```
 Cosmos DB (NoSQL)          Azure Data Factory              Blob Storage         Python              Power BI
 ┌───────────────┐   SQL    ┌─────────────────────┐  JSON  ┌────────────┐ pandas ┌───────────┐ CSV ┌──────────┐
 │ ordenes_entr. │ ───────▶ │ Copy: ordenes       │ ─────▶ │ salida-etl │ ─────▶ │ transformar│ ──▶ │ modelo   │
 │ rutas         │ ───────▶ │ Copy: rutas         │ ─────▶ │ *.json     │        │ _tactico  │     │ + DAX    │
 │ seguimiento   │ ───────▶ │ Copy: eventos (JOIN)│ ─────▶ │            │        │ .py       │     │ dashboard│
 └───────────────┘          └─────────────────────┘        └────────────┘        └───────────┘     └──────────┘
   Extract                       Extract + proyección           (intermedio)        Transform            Load
```
Automatización (IE8): *Add trigger → New/Edit → Schedule* diario en ADF; el script se agenda (o se ejecuta tras el pipeline); en Power BI Service, *Actualización programada*.

---

## 8. Cobertura de la rúbrica EP3 (solo mi pregunta)

| Indicador | Cubierto por |
|---|---|
| IE1 consultas complejas (15 %) | §4.3: proyección, `JOIN … IN` sobre arreglo anidado, 3 colecciones |
| IE2 documentación de transformaciones (15 %) | §3 + `out/calidad_datos.txt` |
| IE3 elección de la herramienta (5 %) | Informe §5.1: Power BI justificado con 4 características técnicas |
| IE4 conexión NoSQL → BI (5 %) | §4 + §5 (ADF → Blob → CSV → Power BI), 100 % de los datos |
| IE5 modelado y KPI (10 %) | §5: 4 KPI |
| IE6/IE7 dashboard y justificación (20 % + 10 %) | §6 |
| IE8 reportes automatizados (20 %) | §7 (trigger + refresco). Hay que montarlo y capturarlo. |

Nota IE3: las 4 características usadas en el informe son: modelo semántico y medidas DAX con contexto de filtro, interactividad entre visuales, formato condicional por regla y validación de las medidas en la vista de consultas DAX.

El encargo también pide el script de conexión con MongoDB (Python/PyMongo) y el repositorio con evidencias; el informe PDF lo arma el equipo uniendo las tres preguntas.

---

## 9. Dashboard final en Power BI

Informe `dashboard_quicktrack_tactico` en Power BI Service (cuenta Duoc UC), de 1 página: título y pregunta, línea de lectura, 2 segmentaciones (zona y tramo), 4 tarjetas KPI, ① columnas + línea de promedio (azul = zona crítica, gris = resto, color por regla sobre `Zona Critica`), ② matriz zona × tramo con degradado, ③ barras de ingreso perdido por zona y ④ columnas por tramo en orden de distancia.

Capturas de evidencia (carpeta `informe/`): `1_dashboard_completo.png`, `2_dashboard_filtro_Centro.png`, `3_vista_modelo_8_medidas.png` y `4_consulta_DAX_resultado.png`.

Verificado: sin filtros 23,0 % · $2.672.017 · 3 · 83,7 %; con Centro, 47,1 % · $1.111.187; celda Centro × Larga = 57,1 %; la consulta DAX por zona reproduce la tabla de §1.

Para IE3: ver la nota de §8 (4 características de la herramienta final).

---

## 10. Resumen del proceso de punta a punta (caso integrador)

Formato de la penúltima diapositiva del PPT 3.1.1, aplicado a esta pregunta:

| 1. Requerimiento | 2. Selección (RICE) | 3. Transformación | 4. Limpieza | 5. Carga |
|---|---|---|---|---|
| **Táctico:** ¿qué zonas y tramos de distancia concentran la cancelación y el ingreso perdido, y la distancia lo explica? | **Conserva:** `total`, `ruta_id`, `zona`, `estado`, `distancia_km` (solo por tramos). **Descarta:** tiempo de ciclo, último evento del historial, ciudades, `fecha_envio`, `medio_pago`. | Aplana `historial` con `JOIN … IN` (100 → 302 filas). Deriva `cancelada`, `ingreso_perdido`, `tramo_distancia`. | 0 duplicados, 0 nulos, 0 órdenes huérfanas. Normaliza el texto de zona y estado. | Transformación en Python → CSV intermedio → modelo semántico y dashboard en Power BI. |

**Resultado:** Centro y Norte concentran 16 de las 23 cancelaciones y el 72 % del ingreso perdido, y la distancia no explica la cancelación. Con eso, la jefatura de operaciones decide en qué zonas revisar primero la operación.
