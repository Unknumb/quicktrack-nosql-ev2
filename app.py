"""
API REST de QuickTrack (Flask + PyMongo) conectada a MongoDB Atlas.

Uso:  python app.py   ->  http://localhost:5050
Cada respuesta incluye el header X-Request-ID; cada request queda registrado
en logs/quicktrack.log (método, ruta, status, duración).
"""
import time
import uuid
from datetime import datetime

from flask import Flask, g, jsonify, request
from flask.json.provider import DefaultJSONProvider
from pymongo.errors import ConnectionFailure, PyMongoError
from werkzeug.exceptions import HTTPException

import servicio as svc
from db import get_db, get_logger

log = get_logger("api")
client, db = get_db()


class JSONMongo(DefaultJSONProvider):
    ensure_ascii = False

    @staticmethod
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = JSONMongo(app)


# ---------------------------------------------------------------- trazabilidad
@app.before_request
def inicio_request():
    g.rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]
    g.t0 = time.perf_counter()


@app.after_request
def fin_request(resp):
    ms = (time.perf_counter() - g.t0) * 1000
    resp.headers["X-Request-ID"] = g.rid
    log.info("[%s] %s %s -> %d (%.1f ms)", g.rid, request.method, request.full_path.rstrip("?"), resp.status_code, ms)
    return resp


def error(status, mensaje):
    return jsonify({"error": mensaje, "status": status, "request_id": g.get("rid")}), status


@app.errorhandler(svc.ErrorNegocio)
def manejar_negocio(e):
    log.warning("[%s] %s: %s", g.rid, type(e).__name__, e)
    return error(e.status, str(e))


@app.errorhandler(ConnectionFailure)
def manejar_conexion(e):
    log.error("[%s] Sin conexión a MongoDB: %s", g.rid, e)
    return error(503, "Base de datos no disponible, intente más tarde")


@app.errorhandler(PyMongoError)
def manejar_mongo(e):
    log.exception("[%s] Error de MongoDB", g.rid)
    return error(500, f"Error de base de datos: {type(e).__name__}")


@app.errorhandler(HTTPException)
def manejar_http(e):
    return error(e.code, e.description)


def cuerpo_json():
    data = request.get_json(silent=True)
    if data is None:
        raise svc.ErrorValidacion("Se esperaba un cuerpo JSON válido (Content-Type: application/json)")
    return data


def entero(param, defecto):
    valor = request.args.get(param, defecto)
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise svc.ErrorValidacion(f"'{param}' debe ser un entero")


# ---------------------------------------------------------------- endpoints
@app.get("/health")
def health():
    t0 = time.perf_counter()
    client.admin.command("ping")
    return jsonify({"status": "ok", "base": db.name, "ping_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "documentos": {c: db[c].estimated_document_count()
                                   for c in ["clientes", "ordenes_entrega", "rutas", "seguimiento", "valoraciones"]}})


@app.get("/ordenes")
def listar_ordenes():
    min_total = request.args.get("min_total")
    try:
        min_total = float(min_total) if min_total is not None else None
    except ValueError:
        raise svc.ErrorValidacion("'min_total' debe ser numérico")
    return jsonify(svc.listar_ordenes(db, request.args.get("zona"), request.args.get("estado"), min_total,
                                      entero("limite", 20), entero("salto", 0)))


@app.get("/ordenes/<orden_id>")
def obtener_orden(orden_id):
    return jsonify(svc.obtener_orden(db, orden_id))


@app.post("/ordenes")
def crear_orden():
    return jsonify(svc.crear_orden(client, db, cuerpo_json())), 201


@app.patch("/ordenes/<orden_id>/estado")
def cambiar_estado(orden_id):
    return jsonify(svc.cambiar_estado(client, db, orden_id, cuerpo_json().get("estado")))


@app.delete("/ordenes/<orden_id>")
def eliminar_orden(orden_id):
    return jsonify(svc.eliminar_orden(client, db, orden_id))


@app.post("/clientes")
def crear_cliente():
    return jsonify(svc.crear_cliente(db, cuerpo_json())), 201


@app.post("/valoraciones")
def crear_valoracion():
    return jsonify(svc.crear_valoracion(db, cuerpo_json())), 201


@app.get("/kpis/zonas")
def kpis_zonas():
    return jsonify(svc.kpis_zonas(db))


if __name__ == "__main__":
    app.run(port=5050, debug=False)  # el 5000 lo ocupa AirPlay en macOS
