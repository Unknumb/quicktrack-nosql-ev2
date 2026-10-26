# QuickTrack – EP2 BDY0101 (Forma B)

**Integrantes:** Alvaro Uribe, Nicolas Mansilla y Genesis Montero

Implementación de una base de datos NoSQL (MongoDB Atlas) para la empresa de logística QuickTrack:
creación de colecciones con validación, carga de datos, consultas de negocio, CRUD completo,
evaluación de rendimiento e integración con una API REST (Flask).

## Estructura

| Archivo | Qué hace | Indicadores |
|---|---|---|
| `db.py` | Conexión a Atlas (ping, timeouts, `w=majority`) y logging en `logs/quicktrack.log` | IE2, IE3, IE11 |
| `01_setup_y_carga.py` | Crea 5 colecciones con `$jsonSchema` + índices, transforma e inserta los JSON del anexo, verifica conteos | IE1, IE2, IE7 |
| `02_consultas.py` | 8 consultas de negocio (filtros, proyecciones, `$or`/`$in`, rangos, orden, agregaciones con `$lookup`) → `resultados/*.csv` | IE4, IE5 |
| `03_crud.py` | Caso de negocio completo: crear cliente/orden, leer, avanzar estados, valorar, errores controlados, corrección de inconsistencias, borrado en cascada | IE7, IE8 |
| `04_rendimiento.py` | `explain()` con y sin índice, bytes con y sin proyección, prueba de volumen con 20.000 docs | IE6 |
| `servicio.py` | Reglas de negocio y validaciones (compartidas por el script CRUD y la API) | IE8, IE10 |
| `app.py` | API REST Flask + PyMongo con `X-Request-ID`, logs y manejo de errores 400/404/409/500/503 | IE9, IE10, IE11 |
| `05_prueba_api.py` | Prueba end-to-end de la API (escritura y lectura inmediata) | IE9 |
| `postman/QuickTrack.postman_collection.json` | Colección Postman con tests automáticos | IE3, IE9 |
| `data/` | Datos del anexo Forma B | |

## Cómo ejecutarlo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # pega aquí tu URI de MongoDB Atlas

python 01_setup_y_carga.py  # crea colecciones e inserta datos
python 02_consultas.py      # consultas de negocio
python 03_crud.py           # CRUD + validaciones
python 04_rendimiento.py    # eficiencia de consultas

python app.py               # API en http://localhost:5050 (dejar corriendo)
python 05_prueba_api.py     # en otra terminal
```

La API usa el puerto **5050** porque en macOS el 5000 está ocupado por AirPlay Receiver.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Ping a la base y conteo de documentos |
| GET | `/ordenes?zona=&estado=&min_total=&limite=&salto=` | Listado filtrado y paginado |
| GET | `/ordenes/{id}` | Orden con cliente, ruta, seguimiento y valoración (`$lookup`) |
| POST | `/ordenes` | Crea la orden y su seguimiento (transacción) |
| PATCH | `/ordenes/{id}/estado` | Avanza el estado (valida el flujo y agrega el evento al historial) |
| DELETE | `/ordenes/{id}` | Borrado en cascada (orden, seguimiento y valoración) |
| POST | `/clientes` | Crea un cliente (correo único y validado) |
| POST | `/valoraciones` | Valoración de 1 a 5, solo para órdenes entregadas |
| GET | `/kpis/zonas` | KPIs por zona |
