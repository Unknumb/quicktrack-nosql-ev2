"""
01 - Creación de colecciones (con validación de esquema e índices) e inserción
de los datos de prueba de QuickTrack (Forma B).

Uso:  python 01_setup_y_carga.py
El script es idempotente: borra y vuelve a crear las colecciones cada vez.
"""
import json
from datetime import datetime

from pymongo.errors import BulkWriteError, CollectionInvalid

from db import BASE_DIR, get_db, get_logger

log = get_logger("setup")
DATA = BASE_DIR / "data"

ESTADOS = ["En preparación", "Despachado", "En tránsito", "Entregado", "Cancelado"]
ZONAS = ["Norte", "Centro", "Sur", "Oriente", "Poniente"]

# ---------------------------------------------------------------- esquemas
VALIDADORES = {
    "clientes": {
        "bsonType": "object",
        "required": ["_id", "nombre", "correo", "fecha_registro"],
        "properties": {
            "_id": {"bsonType": "string", "pattern": "^cli_[0-9]+$"},
            "nombre": {"bsonType": "string", "minLength": 2},
            "correo": {"bsonType": "string", "pattern": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"},
            "pais": {"bsonType": "string"},
            "fecha_registro": {"bsonType": "date"},
        },
    },
    "rutas": {
        "bsonType": "object",
        "required": ["_id", "zona", "ciudad_origen", "ciudad_destino", "distancia_km"],
        "properties": {
            "zona": {"enum": ZONAS},
            "ciudad_origen": {"bsonType": "string"},
            "ciudad_destino": {"bsonType": "string"},
            "distancia_km": {"bsonType": ["double", "int"], "minimum": 0},
        },
    },
    "ordenes_entrega": {
        "bsonType": "object",
        "required": ["_id", "cliente_id", "ruta_id", "fecha_envio", "estado", "total"],
        "properties": {
            "cliente_id": {"bsonType": "string", "pattern": "^cli_[0-9]+$"},
            "ruta_id": {"bsonType": "string", "pattern": "^ruta_[0-9]+$"},
            "zona": {"enum": ZONAS},
            "fecha_envio": {"bsonType": "date"},
            "estado": {"enum": ESTADOS},
            "medio_pago": {"enum": ["Tarjeta", "Efectivo", "Transferencia"]},
            "total": {"bsonType": ["double", "int"], "minimum": 0},
        },
    },
    "seguimiento": {
        "bsonType": "object",
        "required": ["_id", "orden_id", "estado_actual", "historial"],
        "properties": {
            "orden_id": {"bsonType": "string"},
            "estado_actual": {"enum": ESTADOS},
            "historial": {
                "bsonType": "array",
                "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": ["estado", "fecha"],
                    "properties": {"estado": {"enum": ESTADOS}, "fecha": {"bsonType": "date"}},
                },
            },
        },
    },
    "valoraciones": {
        "bsonType": "object",
        "required": ["_id", "orden_id", "puntaje"],
        "properties": {
            "orden_id": {"bsonType": "string"},
            "puntaje": {"bsonType": "int", "minimum": 1, "maximum": 5},
            "comentario": {"bsonType": "string", "maxLength": 500},
            "recomienda": {"bsonType": "bool"},
        },
    },
}

# ---------------------------------------------------------------- índices
INDICES = {
    "clientes": [([("correo", 1)], {"unique": True, "name": "ux_correo"})],
    "rutas": [([("zona", 1), ("distancia_km", -1)], {"name": "ix_zona_distancia"})],
    "ordenes_entrega": [
        ([("zona", 1), ("estado", 1), ("total", -1)], {"name": "ix_zona_estado_total"}),
        ([("cliente_id", 1)], {"name": "ix_cliente"}),
        ([("fecha_envio", 1)], {"name": "ix_fecha_envio"}),
    ],
    "seguimiento": [([("orden_id", 1)], {"unique": True, "name": "ux_orden"})],
    "valoraciones": [
        ([("orden_id", 1)], {"unique": True, "name": "ux_orden"}),
        ([("puntaje", 1)], {"name": "ix_puntaje"}),
    ],
}


# ---------------------------------------------------------------- lectura y transformación
def leer_json(nombre):
    """Soporta los dos formatos del anexo: arreglo JSON (clientes) y JSON Lines (resto)."""
    texto = (DATA / f"{nombre}.json").read_text(encoding="utf-8").strip()
    if texto.startswith("["):
        return json.loads(texto)
    return [json.loads(linea) for linea in texto.splitlines() if linea.strip()]


def fecha(s):
    return datetime.fromisoformat(s)


def transformar(datos):
    """Normalizaciones necesarias detectadas al revisar el anexo (ver informe, sección 3)."""
    rutas = datos["rutas"]
    zona_por_ruta = {r["_id"]: r["zona"] for r in rutas}

    # Problema 1: clientes._id viene como entero (1, 2...) pero ordenes.cliente_id usa "cli_1".
    clientes = [{**c, "_id": f"cli_{c['_id']}", "fecha_registro": fecha(c["fecha_registro"])} for c in datos["clientes"]]

    # Problema 2: fechas como texto -> tipo date (permite rangos y $dateDiff).
    # Desnormalización: se copia la zona de la ruta en la orden para filtrar sin $lookup.
    ordenes = [
        {**o, "fecha_envio": fecha(o["fecha_envio"]), "zona": zona_por_ruta[o["ruta_id"]]}
        for o in datos["ordenes_entrega"]
    ]
    seguimiento = [
        {**s, "historial": [{**h, "fecha": fecha(h["fecha"])} for h in s["historial"]]}
        for s in datos["seguimiento"]
    ]
    # Campo derivado: el caso pide "recomendación"; se considera que recomienda si puntaje >= 4.
    valoraciones = [{**v, "recomienda": v["puntaje"] >= 4} for v in datos["valoraciones"]]

    return {
        "clientes": clientes,
        "rutas": rutas,
        "ordenes_entrega": ordenes,
        "seguimiento": seguimiento,
        "valoraciones": valoraciones,
    }


def main():
    client, db = get_db()
    crudos = {n: leer_json(n) for n in VALIDADORES}
    docs = transformar(crudos)

    for nombre, validador in VALIDADORES.items():
        db.drop_collection(nombre)
        try:
            db.create_collection(
                nombre,
                validator={"$jsonSchema": validador},
                validationLevel="strict",
                validationAction="error",
            )
        except CollectionInvalid as e:
            log.warning("%s ya existía: %s", nombre, e)
        for claves, opciones in INDICES.get(nombre, []):
            db[nombre].create_index(claves, **opciones)
        log.info("Colección '%s' creada con $jsonSchema e índices %s", nombre, list(db[nombre].index_information()))

    for nombre, lista in docs.items():
        try:
            res = db[nombre].insert_many(lista, ordered=False)
            log.info("Insertados %d documentos en '%s'", len(res.inserted_ids), nombre)
        except BulkWriteError as e:
            log.error("Errores al insertar en '%s': %s", nombre, e.details["writeErrors"][:3])

    # Secuencias para generar IDs nuevos sin chocar con los existentes (usadas por servicio.siguiente_id)
    db.drop_collection("contadores")
    db.contadores.insert_many([
        {"_id": "cli", "seq": max(int(c["_id"].split("_")[1]) for c in docs["clientes"])},
        {"_id": "orden", "seq": max(int(o["_id"].split("_")[1]) for o in docs["ordenes_entrega"])},
    ])

    print("\n=== VERIFICACIÓN DE CARGA ===")
    print(f"{'colección':<18}{'archivo':>9}{'en BD':>8}  estado")
    for nombre in VALIDADORES:
        esperado, real = len(crudos[nombre]), db[nombre].count_documents({})
        print(f"{nombre:<18}{esperado:>9}{real:>8}  {'OK' if esperado == real else 'DIFERENCIA'}")

    print("\nEjemplo de documento en ordenes_entrega:")
    print(db.ordenes_entrega.find_one({"_id": "orden_1"}))
    print("\nEjemplo de documento en seguimiento:")
    print(db.seguimiento.find_one({"orden_id": "orden_1"}))
    client.close()


if __name__ == "__main__":
    main()
