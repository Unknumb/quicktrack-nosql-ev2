"""
03 - Caso de negocio CRUD completo + validación de errores.

Simula el ciclo de vida de un envío en QuickTrack:
  1. CREATE  registrar cliente y orden (orden + seguimiento en transacción)
  2. READ    consultar la orden completa ($lookup a cliente, ruta, seguimiento)
  3. UPDATE  avanzar estados (transacción + $push al historial), actualización masiva
  4. CREATE  registrar valoración
  5. Pruebas de errores: duplicados, esquema inválido, referencias inexistentes, transición inválida
  6. Validación de integridad del dataset: detecta y corrige inconsistencias
  7. DELETE  eliminación en cascada y verificación final

Uso:  python 03_crud.py
"""
from pymongo.errors import DuplicateKeyError, WriteError

import servicio as svc
from db import get_db, get_logger

log = get_logger("crud")
CORREO_PRUEBA = "ana.prueba@quicktrack.cl"


def titulo(t):
    print("\n" + "=" * 90 + f"\n{t}\n" + "=" * 90)


def ok(msg):
    print(f"  [OK] {msg}")


def esperado_error(descripcion, fn):
    """Ejecuta algo que DEBE fallar y muestra cómo se controló el error."""
    try:
        fn()
        print(f"  [FALLO] {descripcion}: no se detectó el error")
    except svc.ErrorNegocio as e:
        print(f"  [RECHAZADO {e.status}] {descripcion} -> {e}")
    except DuplicateKeyError as e:
        print(f"  [RECHAZADO por MongoDB E11000] {descripcion} -> clave duplicada {e.details.get('keyValue')}")
    except WriteError as e:
        print(f"  [RECHAZADO por MongoDB código {e.code}] {descripcion} -> {e.details.get('errmsg')}")


def limpiar_pruebas(client, db):
    cli = db.clientes.find_one({"correo": CORREO_PRUEBA})
    if cli:
        for o in db.ordenes_entrega.find({"cliente_id": cli["_id"]}, {"_id": 1}):
            svc.eliminar_orden(client, db, o["_id"])
        db.clientes.delete_one({"_id": cli["_id"]})
        log.info("Datos de una ejecución anterior eliminados (%s)", cli["_id"])


def main():
    client, db = get_db()
    limpiar_pruebas(client, db)
    conteo_inicial = {c: db[c].count_documents({}) for c in ["clientes", "ordenes_entrega", "seguimiento", "valoraciones"]}
    print("Conteo inicial:", conteo_inicial)

    # ------------------------------------------------------------------ CREATE
    titulo("1. CREATE - Registrar cliente y orden de envío")
    cliente = svc.crear_cliente(db, {"nombre": "Ana Prueba", "correo": CORREO_PRUEBA, "pais": "Chile"})
    ok(f"Cliente insertado: {cliente}")
    orden = svc.crear_orden(client, db, {"cliente_id": cliente["_id"], "ruta_id": "ruta_10",
                                         "total": 45990, "medio_pago": "Tarjeta"})
    ok(f"Orden insertada: {orden}")
    ok(f"Seguimiento creado en la misma transacción: {db.seguimiento.find_one({'orden_id': orden['_id']})}")
    oid = orden["_id"]

    # ------------------------------------------------------------------ READ
    titulo("2. READ - Consultar la orden completa (cliente + ruta + seguimiento)")
    completa = svc.obtener_orden(db, oid)
    ok(f"Orden {oid} | cliente: {completa['cliente']['nombre']} | ruta: "
       f"{completa['ruta']['ciudad_origen']} -> {completa['ruta']['ciudad_destino']} | estado: {completa['estado']}")

    # ------------------------------------------------------------------ UPDATE
    titulo("3. UPDATE - Avanzar estados del envío (transacción orden + seguimiento)")
    for estado in ["Despachado", "En tránsito", "Entregado"]:
        r = svc.cambiar_estado(client, db, oid, estado)
        ok(f"{r['estado_anterior']} -> {r['estado_nuevo']}")
    seg = db.seguimiento.find_one({"orden_id": oid}, {"_id": 0, "estado_actual": 1, "historial.estado": 1})
    ok(f"Seguimiento tras actualizar: {seg}")

    titulo("4. CREATE - Valoración del cliente")
    val = svc.crear_valoracion(db, {"orden_id": oid, "puntaje": 5, "comentario": "Entrega a tiempo"})
    ok(f"Valoración insertada: {val}")

    titulo("4b. UPDATE masivo - Marcar valoraciones críticas para que atención al cliente contacte")
    r = db.valoraciones.update_many({"puntaje": {"$lte": 2}, "requiere_contacto": {"$exists": False}},
                                    {"$set": {"requiere_contacto": True}})
    ok(f"update_many: {r.matched_count} encontradas, {r.modified_count} modificadas")
    ok(f"Verificación: {db.valoraciones.count_documents({'requiere_contacto': True})} valoraciones marcadas")

    # ------------------------------------------------------------------ ERRORES
    titulo("5. CONTROL DE ERRORES - operaciones inválidas que deben ser rechazadas")
    esperado_error("Cliente con correo duplicado",
                   lambda: svc.crear_cliente(db, {"nombre": "Otra Ana", "correo": CORREO_PRUEBA}))
    esperado_error("Cliente con correo inválido",
                   lambda: svc.crear_cliente(db, {"nombre": "Sin Correo", "correo": "no-es-correo"}))
    esperado_error("Orden con cliente inexistente",
                   lambda: svc.crear_orden(client, db, {"cliente_id": "cli_99999", "ruta_id": "ruta_1",
                                                        "total": 1000, "medio_pago": "Tarjeta"}))
    esperado_error("Orden con total negativo",
                   lambda: svc.crear_orden(client, db, {"cliente_id": cliente["_id"], "ruta_id": "ruta_1",
                                                        "total": -50, "medio_pago": "Tarjeta"}))
    esperado_error("Transición de estado inválida (Entregado -> En preparación)",
                   lambda: svc.cambiar_estado(client, db, oid, "En preparación"))
    esperado_error("Segunda valoración para la misma orden",
                   lambda: svc.crear_valoracion(db, {"orden_id": oid, "puntaje": 1}))
    esperado_error("Valorar una orden que no fue entregada",
                   lambda: svc.crear_valoracion(db, {"orden_id": "orden_1", "puntaje": 3}))
    print("  -- Segunda línea de defensa: validación en la propia base ($jsonSchema / índices únicos) --")
    esperado_error("Insert directo con puntaje 9 (fuera de 1-5)",
                   lambda: db.valoraciones.insert_one({"_id": "val_x", "orden_id": "orden_x", "puntaje": 9}))
    esperado_error("Insert directo con estado inexistente",
                   lambda: db.ordenes_entrega.insert_one({"_id": "orden_x", "cliente_id": "cli_1", "ruta_id": "ruta_1",
                                                          "fecha_envio": completa["fecha_envio"], "estado": "Perdido",
                                                          "total": 10.0}))
    esperado_error("Insert directo con _id duplicado",
                   lambda: db.ordenes_entrega.insert_one({**completa_sin_lookups(completa)}))

    # ------------------------------------------------------------------ INTEGRIDAD
    titulo("6. VALIDACIÓN DE INTEGRIDAD DEL DATASET - detección y corrección")
    # 6.1 estado_actual del seguimiento distinto al último evento del historial
    filtro_inc = {"$expr": {"$ne": ["$estado_actual", {"$last": "$historial.estado"}]}}
    n = db.seguimiento.count_documents(filtro_inc)
    print(f"  6.1 Seguimientos cuyo estado_actual no coincide con el último evento del historial: {n}")
    r = db.seguimiento.update_many(filtro_inc, [{"$set": {"estado_actual": {"$last": "$historial.estado"}}}])
    ok(f"Corregidos con update por pipeline: {r.modified_count}. Restantes: {db.seguimiento.count_documents(filtro_inc)}")

    # 6.2 estado de la orden distinto al del seguimiento
    pipeline_desfase = [
        {"$lookup": {"from": "seguimiento", "localField": "_id", "foreignField": "orden_id", "as": "s"}},
        {"$set": {"estado_seg": {"$first": "$s.estado_actual"}}},
        {"$match": {"$expr": {"$ne": ["$estado", "$estado_seg"]}}},
        {"$project": {"estado": 1, "estado_seg": 1}},
    ]
    desfases = list(db.ordenes_entrega.aggregate(pipeline_desfase))
    canceladas = [d for d in desfases if d["estado"] == "Cancelado"]
    print(f"  6.2 Órdenes cuyo estado difiere del seguimiento: {len(desfases)} "
          f"({len(canceladas)} canceladas con seguimiento activo)")
    # Regla: el seguimiento es la fuente de verdad logística; las canceladas se marcan para revisión manual
    for d in desfases:
        if d["estado"] == "Cancelado":
            db.seguimiento.update_one({"orden_id": d["_id"]}, {"$set": {"requiere_revision": True}})
        else:
            db.ordenes_entrega.update_one({"_id": d["_id"]}, {"$set": {"estado": d["estado_seg"]}})
    restantes = [d for d in db.ordenes_entrega.aggregate(pipeline_desfase) if d["estado"] != "Cancelado"]
    ok(f"Sincronizadas {len(desfases) - len(canceladas)} órdenes; {len(canceladas)} marcadas requiere_revision; "
       f"desfases no explicados restantes: {len(restantes)}")

    # 6.3 referencias huérfanas
    huerfanas = list(db.ordenes_entrega.aggregate([
        {"$lookup": {"from": "clientes", "localField": "cliente_id", "foreignField": "_id", "as": "c"}},
        {"$match": {"c": {"$size": 0}}}, {"$count": "n"}]))
    print(f"  6.3 Órdenes con cliente inexistente: {huerfanas[0]['n'] if huerfanas else 0} "
          "(antes de normalizar clientes._id de 1 -> 'cli_1' eran 100 de 100)")
    # 6.4 duplicados
    dups = list(db.clientes.aggregate([{"$group": {"_id": "$correo", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
    print(f"  6.4 Correos de cliente duplicados: {len(dups)} (protegido por índice único ux_correo)")

    # ------------------------------------------------------------------ DELETE
    titulo("7. DELETE - Eliminación en cascada de la orden de prueba y del cliente")
    r = svc.eliminar_orden(client, db, oid)
    ok(f"Eliminados: {r['eliminados']}")
    r2 = db.clientes.delete_one({"_id": cliente["_id"]})
    ok(f"Cliente eliminado: {r2.deleted_count}")
    esperado_error("Consultar la orden eliminada", lambda: svc.obtener_orden(db, oid))

    conteo_final = {c: db[c].count_documents({}) for c in conteo_inicial}
    print("\nConteo final:", conteo_final)
    print("Sin pérdida ni duplicación de datos:", "SÍ" if conteo_final == conteo_inicial else "NO")
    client.close()


def completa_sin_lookups(doc):
    return {k: v for k, v in doc.items() if k not in ("cliente", "ruta", "seguimiento", "valoracion")}


if __name__ == "__main__":
    main()
