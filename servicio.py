"""
Lógica de negocio de QuickTrack (validaciones + operaciones CRUD).
La usan tanto el script 03_crud.py como la API REST (app.py), así ambos
aplican exactamente las mismas reglas.
"""
import re
from datetime import datetime

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from db import get_logger

log = get_logger("servicio")

ESTADOS = ["En preparación", "Despachado", "En tránsito", "Entregado", "Cancelado"]
MEDIOS_PAGO = ["Tarjeta", "Efectivo", "Transferencia"]
ZONAS = ["Norte", "Centro", "Sur", "Oriente", "Poniente"]
# Flujo permitido de estados: evita retrocesos (p.ej. Entregado -> En preparación)
TRANSICIONES = {
    "En preparación": ["Despachado", "Cancelado"],
    "Despachado": ["En tránsito", "Cancelado"],
    "En tránsito": ["Entregado"],
    "Entregado": [],
    "Cancelado": [],
}
RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErrorNegocio(Exception):
    status = 400


class ErrorValidacion(ErrorNegocio):
    status = 400


class NoEncontrado(ErrorNegocio):
    status = 404


class Conflicto(ErrorNegocio):
    status = 409


# ---------------------------------------------------------------- helpers
def _es_numero(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _texto(data, campo, minimo=1, maximo=200, obligatorio=True):
    valor = data.get(campo)
    if valor is None and not obligatorio:
        return None
    if not isinstance(valor, str) or not (minimo <= len(valor.strip()) <= maximo):
        raise ErrorValidacion(f"'{campo}' debe ser texto de {minimo} a {maximo} caracteres")
    return valor.strip()


def _cuerpo(data):
    if not isinstance(data, dict):
        raise ErrorValidacion("El cuerpo debe ser un objeto JSON")
    return data


def siguiente_id(db, prefijo):
    """Secuencia atómica (patrón 'counters' de MongoDB) -> 'orden_101', 'cli_101'..."""
    doc = db.contadores.find_one_and_update(
        {"_id": prefijo}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return f"{prefijo}_{doc['seq']}"


def en_transaccion(client, operacion):
    """Ejecuta varias escrituras como una unidad atómica (todo o nada)."""
    with client.start_session() as sesion:
        return sesion.with_transaction(lambda s: operacion(s))


# ---------------------------------------------------------------- clientes
def crear_cliente(db, data):
    data = _cuerpo(data)
    nombre = _texto(data, "nombre", 2, 120)
    correo = _texto(data, "correo", 5, 120).lower()
    if not RE_CORREO.match(correo):
        raise ErrorValidacion("'correo' no tiene formato válido")
    pais = _texto(data, "pais", 2, 80, obligatorio=False)
    if db.clientes.find_one({"correo": correo}, {"_id": 1}):
        raise Conflicto(f"Ya existe un cliente con el correo {correo}")
    doc = {"_id": data.get("_id") or siguiente_id(db, "cli"), "nombre": nombre, "correo": correo,
           "fecha_registro": datetime.now()}
    if pais:
        doc["pais"] = pais
    try:
        db.clientes.insert_one(doc)
    except DuplicateKeyError as e:  # carrera entre el find_one y el insert, o _id repetido
        raise Conflicto(f"Cliente duplicado: {e.details.get('keyValue')}")
    log.info("Cliente creado %s", doc["_id"])
    return doc


# ---------------------------------------------------------------- órdenes
def crear_orden(client, db, data):
    """Crea la orden y su documento de seguimiento en una sola transacción."""
    data = _cuerpo(data)
    cliente_id = _texto(data, "cliente_id", 4, 30)
    ruta_id = _texto(data, "ruta_id", 6, 30)
    total = data.get("total")
    if not _es_numero(total) or total <= 0:
        raise ErrorValidacion("'total' debe ser un número mayor a 0")
    medio_pago = data.get("medio_pago")
    if medio_pago not in MEDIOS_PAGO:
        raise ErrorValidacion(f"'medio_pago' debe ser uno de {MEDIOS_PAGO}")
    # Integridad referencial (MongoDB no tiene FK: se valida en la aplicación)
    if not db.clientes.find_one({"_id": cliente_id}, {"_id": 1}):
        raise NoEncontrado(f"El cliente {cliente_id} no existe")
    ruta = db.rutas.find_one({"_id": ruta_id}, {"zona": 1})
    if not ruta:
        raise NoEncontrado(f"La ruta {ruta_id} no existe")

    ahora = datetime.now()
    orden_id = data.get("_id") or siguiente_id(db, "orden")
    orden = {"_id": orden_id, "cliente_id": cliente_id, "ruta_id": ruta_id, "zona": ruta["zona"],
             "fecha_envio": ahora, "estado": "En preparación", "medio_pago": medio_pago, "total": float(total)}
    seguimiento = {"_id": orden_id.replace("orden", "seg"), "orden_id": orden_id, "estado_actual": "En preparación",
                   "historial": [{"estado": "En preparación", "fecha": ahora}]}

    def escribir(s):
        db.ordenes_entrega.insert_one(orden, session=s)
        db.seguimiento.insert_one(seguimiento, session=s)

    try:
        en_transaccion(client, escribir)
    except DuplicateKeyError as e:
        raise Conflicto(f"Orden duplicada: {e.details.get('keyValue')}")
    log.info("Orden creada %s (cliente %s, ruta %s)", orden_id, cliente_id, ruta_id)
    return orden


def obtener_orden(db, orden_id):
    res = list(db.ordenes_entrega.aggregate([
        {"$match": {"_id": orden_id}},
        {"$lookup": {"from": "clientes", "localField": "cliente_id", "foreignField": "_id", "as": "cliente"}},
        {"$lookup": {"from": "rutas", "localField": "ruta_id", "foreignField": "_id", "as": "ruta"}},
        {"$lookup": {"from": "seguimiento", "localField": "_id", "foreignField": "orden_id", "as": "seguimiento"}},
        {"$lookup": {"from": "valoraciones", "localField": "_id", "foreignField": "orden_id", "as": "valoracion"}},
        {"$set": {"cliente": {"$first": "$cliente"}, "ruta": {"$first": "$ruta"},
                  "seguimiento": {"$first": "$seguimiento"}, "valoracion": {"$first": "$valoracion"}}},
    ]))
    if not res:
        raise NoEncontrado(f"La orden {orden_id} no existe")
    return res[0]


def listar_ordenes(db, zona=None, estado=None, min_total=None, limite=20, salto=0):
    filtro = {}
    if zona:
        if zona not in ZONAS:
            raise ErrorValidacion(f"'zona' debe ser una de {ZONAS}")
        filtro["zona"] = zona
    if estado:
        if estado not in ESTADOS:
            raise ErrorValidacion(f"'estado' debe ser uno de {ESTADOS}")
        filtro["estado"] = estado
    if min_total is not None:
        filtro["total"] = {"$gte": min_total}
    if not (1 <= limite <= 100) or salto < 0:
        raise ErrorValidacion("'limite' debe estar entre 1 y 100 y 'salto' >= 0")
    cursor = (db.ordenes_entrega.find(filtro, {"cliente_id": 1, "zona": 1, "estado": 1, "fecha_envio": 1, "total": 1})
              .sort([("fecha_envio", -1), ("_id", 1)]).skip(salto).limit(limite))
    return {"total_coincidencias": db.ordenes_entrega.count_documents(filtro), "datos": list(cursor)}


def cambiar_estado(client, db, orden_id, nuevo_estado):
    """Actualiza orden + seguimiento de forma atómica respetando el flujo de estados."""
    if nuevo_estado not in ESTADOS:
        raise ErrorValidacion(f"'estado' debe ser uno de {ESTADOS}")
    orden = db.ordenes_entrega.find_one({"_id": orden_id}, {"estado": 1})
    if not orden:
        raise NoEncontrado(f"La orden {orden_id} no existe")
    actual = orden["estado"]
    if nuevo_estado not in TRANSICIONES[actual]:
        raise Conflicto(f"Transición no permitida: '{actual}' -> '{nuevo_estado}'. Permitidas: {TRANSICIONES[actual]}")
    ahora = datetime.now()

    def escribir(s):
        # El filtro incluye el estado leído: si otro proceso lo cambió entretanto, no se pisa (control optimista)
        r = db.ordenes_entrega.update_one({"_id": orden_id, "estado": actual}, {"$set": {"estado": nuevo_estado}}, session=s)
        if r.modified_count != 1:
            raise Conflicto("La orden fue modificada por otro proceso, reintente")
        db.seguimiento.update_one(
            {"orden_id": orden_id},
            {"$set": {"estado_actual": nuevo_estado}, "$push": {"historial": {"estado": nuevo_estado, "fecha": ahora}}},
            upsert=False, session=s,
        )

    en_transaccion(client, escribir)
    log.info("Orden %s: %s -> %s", orden_id, actual, nuevo_estado)
    return {"orden_id": orden_id, "estado_anterior": actual, "estado_nuevo": nuevo_estado, "fecha": ahora}


def eliminar_orden(client, db, orden_id):
    """Borrado en cascada: orden + seguimiento + valoración (evita documentos huérfanos)."""
    if not db.ordenes_entrega.find_one({"_id": orden_id}, {"_id": 1}):
        raise NoEncontrado(f"La orden {orden_id} no existe")

    def borrar(s):
        return {
            "ordenes_entrega": db.ordenes_entrega.delete_one({"_id": orden_id}, session=s).deleted_count,
            "seguimiento": db.seguimiento.delete_many({"orden_id": orden_id}, session=s).deleted_count,
            "valoraciones": db.valoraciones.delete_many({"orden_id": orden_id}, session=s).deleted_count,
        }

    eliminados = en_transaccion(client, borrar)
    log.info("Orden %s eliminada en cascada: %s", orden_id, eliminados)
    return {"orden_id": orden_id, "eliminados": eliminados}


# ---------------------------------------------------------------- valoraciones
def crear_valoracion(db, data):
    data = _cuerpo(data)
    orden_id = _texto(data, "orden_id", 3, 30)
    puntaje = data.get("puntaje")
    if not isinstance(puntaje, int) or isinstance(puntaje, bool) or not 1 <= puntaje <= 5:
        raise ErrorValidacion("'puntaje' debe ser un entero entre 1 y 5")
    comentario = _texto(data, "comentario", 0, 500, obligatorio=False) or ""
    orden = db.ordenes_entrega.find_one({"_id": orden_id}, {"estado": 1})
    if not orden:
        raise NoEncontrado(f"La orden {orden_id} no existe")
    if orden["estado"] != "Entregado":
        raise Conflicto(f"Solo se pueden valorar órdenes entregadas (estado actual: {orden['estado']})")
    doc = {"_id": orden_id.replace("orden", "val"), "orden_id": orden_id, "puntaje": puntaje,
           "comentario": comentario, "recomienda": puntaje >= 4}
    try:
        db.valoraciones.insert_one(doc)
    except DuplicateKeyError:
        raise Conflicto(f"La orden {orden_id} ya tiene una valoración")
    log.info("Valoración creada para %s (puntaje %d)", orden_id, puntaje)
    return doc


# ---------------------------------------------------------------- KPIs
def kpis_zonas(db):
    return list(db.ordenes_entrega.aggregate([
        {"$lookup": {"from": "valoraciones", "localField": "_id", "foreignField": "orden_id", "as": "v"}},
        {"$group": {"_id": "$zona", "ordenes": {"$sum": 1},
                    "canceladas": {"$sum": {"$cond": [{"$eq": ["$estado", "Cancelado"]}, 1, 0]}},
                    "puntaje_prom": {"$avg": {"$first": "$v.puntaje"}}}},
        {"$project": {"_id": 0, "zona": "$_id", "ordenes": 1,
                      "pct_canceladas": {"$round": [{"$multiply": [{"$divide": ["$canceladas", "$ordenes"]}, 100]}, 1]},
                      "puntaje_prom": {"$round": ["$puntaje_prom", 2]}}},
        {"$sort": {"zona": 1}},
    ]))
