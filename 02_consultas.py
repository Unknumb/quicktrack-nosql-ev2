"""
02 - Consultas de lectura sobre QuickTrack: filtros, proyecciones, búsquedas
compuestas, ordenamientos y agregaciones, cada una ligada a un requerimiento
de negocio. Los resultados se muestran en tabla y se exportan a resultados/*.csv
(sirven también como fuente para Power BI).

Uso:  python 02_consultas.py
"""
import time
from datetime import datetime

import pandas as pd

from db import BASE_DIR, get_db, get_logger

log = get_logger("consultas")
SALIDA = BASE_DIR / "resultados"
SALIDA.mkdir(exist_ok=True)
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def consultas(db):
    """Cada consulta: (código, requerimiento de negocio, función que devuelve un cursor/lista)."""
    return [
        (
            "C1_entregas_norte_alto_valor",
            "Logística necesita las órdenes ENTREGADAS de la zona Norte con total > $100.000, "
            "de mayor a menor valor (filtro + proyección + orden).",
            lambda: db.ordenes_entrega.find(
                {"zona": "Norte", "estado": "Entregado", "total": {"$gt": 100000}},
                {"_id": 1, "cliente_id": 1, "fecha_envio": 1, "total": 1},
            ).sort("total", -1),
        ),
        (
            "C2_pendientes_efectivo_2024",
            "Finanzas quiere las órdenes de 2024 pagadas en Efectivo que siguen 'En preparación' o 'En tránsito' "
            "(búsqueda compuesta con $and implícito, $in y rango de fechas).",
            lambda: db.ordenes_entrega.find(
                {
                    "medio_pago": "Efectivo",
                    "estado": {"$in": ["En preparación", "En tránsito"]},
                    "fecha_envio": {"$gte": datetime(2024, 1, 1), "$lt": datetime(2025, 1, 1)},
                },
                {"_id": 1, "zona": 1, "estado": 1, "fecha_envio": 1, "total": 1},
            ).sort([("fecha_envio", 1)]),
        ),
        (
            "C3_valoraciones_criticas",
            "Atención al cliente necesita las valoraciones críticas: puntaje <= 2 O comentario de retraso/producto dañado "
            "(operador $or + $lte + $in).",
            lambda: db.valoraciones.find(
                {"$or": [{"puntaje": {"$lte": 2}}, {"comentario": {"$in": ["Tuvo retraso", "Producto en mal estado"]}}]},
                {"_id": 0, "orden_id": 1, "puntaje": 1, "comentario": 1},
            ).sort([("puntaje", 1), ("orden_id", 1)]),
        ),
        (
            "C4_rutas_largas_por_zona",
            "Planificación de rutas: las 3 rutas más largas de cada zona para revisar optimización "
            "(agregación $sort + $group + $slice).",
            lambda: db.rutas.aggregate([
                {"$sort": {"distancia_km": -1}},
                {"$group": {
                    "_id": "$zona",
                    "rutas_mas_largas": {"$push": {"$concat": ["$ciudad_origen", " → ", "$ciudad_destino"]}},
                    "km": {"$push": "$distancia_km"},
                    "km_promedio_zona": {"$avg": "$distancia_km"},
                }},
                {"$project": {"zona": "$_id", "_id": 0, "km_promedio_zona": {"$round": ["$km_promedio_zona", 1]},
                              "top3": {"$slice": ["$rutas_mas_largas", 3]}, "top3_km": {"$slice": ["$km", 3]}}},
                {"$sort": {"km_promedio_zona": -1}},
            ]),
        ),
        (
            "C5_zonas_criticas",
            "Gerencia: KPI por zona — n° órdenes, % canceladas, puntaje promedio y % con comentario de retraso "
            "($lookup ordenes→valoraciones + $group + $cond).",
            lambda: db.ordenes_entrega.aggregate([
                {"$lookup": {"from": "valoraciones", "localField": "_id", "foreignField": "orden_id", "as": "val"}},
                {"$unwind": {"path": "$val", "preserveNullAndEmptyArrays": True}},
                {"$group": {
                    "_id": "$zona",
                    "ordenes": {"$sum": 1},
                    "canceladas": {"$sum": {"$cond": [{"$eq": ["$estado", "Cancelado"]}, 1, 0]}},
                    "retrasos": {"$sum": {"$cond": [{"$eq": ["$val.comentario", "Tuvo retraso"]}, 1, 0]}},
                    "puntaje_prom": {"$avg": "$val.puntaje"},
                    "ventas": {"$sum": "$total"},
                }},
                {"$project": {
                    "_id": 0, "zona": "$_id", "ordenes": 1, "ventas": {"$round": ["$ventas", 0]},
                    "pct_canceladas": {"$round": [{"$multiply": [{"$divide": ["$canceladas", "$ordenes"]}, 100]}, 1]},
                    "pct_retraso": {"$round": [{"$multiply": [{"$divide": ["$retrasos", "$ordenes"]}, 100]}, 1]},
                    "puntaje_prom": {"$round": ["$puntaje_prom", 2]},
                }},
                {"$sort": {"puntaje_prom": 1}},
            ]),
        ),
        (
            "C6_satisfaccion_medio_pago",
            "Marketing: % de clientes que recomiendan (puntaje >= 4) según medio de pago.",
            lambda: db.valoraciones.aggregate([
                {"$lookup": {"from": "ordenes_entrega", "localField": "orden_id", "foreignField": "_id", "as": "o"}},
                {"$unwind": "$o"},
                {"$group": {"_id": "$o.medio_pago", "valoraciones": {"$sum": 1},
                            "recomiendan": {"$sum": {"$cond": ["$recomienda", 1, 0]}},
                            "puntaje_prom": {"$avg": "$puntaje"}}},
                {"$project": {"_id": 0, "medio_pago": "$_id", "valoraciones": 1,
                              "pct_recomienda": {"$round": [{"$multiply": [{"$divide": ["$recomiendan", "$valoraciones"]}, 100]}, 1]},
                              "puntaje_prom": {"$round": ["$puntaje_prom", 2]}}},
                {"$sort": {"pct_recomienda": -1}},
            ]),
        ),
        (
            "C7_tiempo_entrega_por_zona",
            "Cumplimiento de plazos: días promedio desde el primer evento hasta 'Entregado' por zona "
            "($elemMatch implícito, $filter, $dateDiff).",
            lambda: db.seguimiento.aggregate([
                {"$match": {"historial.estado": "Entregado"}},
                {"$project": {
                    "orden_id": 1,
                    "inicio": {"$min": "$historial.fecha"},
                    "entrega": {"$first": {"$filter": {"input": "$historial", "cond": {"$eq": ["$$this.estado", "Entregado"]}}}},
                }},
                {"$project": {"orden_id": 1, "dias": {"$dateDiff": {"startDate": "$inicio", "endDate": "$entrega.fecha", "unit": "day"}}}},
                {"$lookup": {"from": "ordenes_entrega", "localField": "orden_id", "foreignField": "_id", "as": "o"}},
                {"$unwind": "$o"},
                {"$group": {"_id": "$o.zona", "entregas": {"$sum": 1}, "dias_prom": {"$avg": "$dias"}, "dias_max": {"$max": "$dias"}}},
                {"$project": {"_id": 0, "zona": "$_id", "entregas": 1, "dias_prom": {"$round": ["$dias_prom", 1]}, "dias_max": 1}},
                {"$sort": {"dias_prom": -1}},
            ]),
        ),
        (
            "C8_top_clientes",
            "Comercial: top 5 clientes por monto total enviado, con nombre y correo ($group + $lookup clientes + $limit).",
            lambda: db.ordenes_entrega.aggregate([
                {"$match": {"estado": {"$ne": "Cancelado"}}},
                {"$group": {"_id": "$cliente_id", "ordenes": {"$sum": 1}, "monto": {"$sum": "$total"}}},
                {"$sort": {"monto": -1}},
                {"$limit": 5},
                {"$lookup": {"from": "clientes", "localField": "_id", "foreignField": "_id", "as": "c"}},
                {"$project": {"_id": 0, "cliente_id": "$_id", "nombre": {"$first": "$c.nombre"},
                              "correo": {"$first": "$c.correo"}, "ordenes": 1, "monto": {"$round": ["$monto", 0]}}},
            ]),
        ),
    ]


def main():
    client, db = get_db()
    for codigo, requerimiento, ejecutar in consultas(db):
        t0 = time.perf_counter()
        filas = list(ejecutar())
        ms = (time.perf_counter() - t0) * 1000
        df = pd.DataFrame(filas)
        print("\n" + "=" * 100)
        print(f"{codigo}\nRequerimiento: {requerimiento}")
        print(f"Resultados: {len(df)} documentos | tiempo: {ms:.1f} ms")
        print("-" * 100)
        print(df.head(15).to_string(index=False) if not df.empty else "(sin resultados)")
        df.to_csv(SALIDA / f"{codigo}.csv", index=False)
        log.info("%s -> %d docs en %.1f ms", codigo, len(df), ms)
    print(f"\nCSV exportados en: {SALIDA}")
    client.close()


if __name__ == "__main__":
    main()
