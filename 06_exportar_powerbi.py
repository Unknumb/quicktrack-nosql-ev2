"""
06 - Exporta los datos de MongoDB Atlas a Excel para Power BI.

Une las 5 colecciones con $lookup en una tabla de hechos (una fila por orden)
y agrega tablas resumen. Los registros de prueba creados por la API/Postman
(fecha_envio en 2026) se excluyen para no distorsionar los indicadores.

Uso:  python 06_exportar_powerbi.py
Salida: powerbi/quicktrack_powerbi.xlsx
"""
from datetime import datetime

import pandas as pd

from db import BASE_DIR, get_db, get_logger

log = get_logger("powerbi")
SALIDA = BASE_DIR / "powerbi"
SALIDA.mkdir(exist_ok=True)
CORTE_PRUEBAS = datetime(2026, 1, 1)

PIPELINE_ORDENES = [
    {"$match": {"fecha_envio": {"$lt": CORTE_PRUEBAS}}},
    {"$lookup": {"from": "clientes", "localField": "cliente_id", "foreignField": "_id", "as": "c"}},
    {"$lookup": {"from": "rutas", "localField": "ruta_id", "foreignField": "_id", "as": "r"}},
    {"$lookup": {"from": "valoraciones", "localField": "_id", "foreignField": "orden_id", "as": "v"}},
    {"$lookup": {"from": "seguimiento", "localField": "_id", "foreignField": "orden_id", "as": "s"}},
    {"$set": {"c": {"$first": "$c"}, "r": {"$first": "$r"}, "v": {"$first": "$v"}, "s": {"$first": "$s"}}},
    {"$set": {"entrega": {"$first": {"$filter": {"input": "$s.historial", "cond": {"$eq": ["$$this.estado", "Entregado"]}}}}}},
    {"$project": {
        "_id": 0,
        "orden_id": "$_id",
        "cliente_id": 1,
        "cliente": "$c.nombre",
        "zona": 1,
        "ruta_id": 1,
        "ciudad_origen": "$r.ciudad_origen",
        "ciudad_destino": "$r.ciudad_destino",
        "ruta": {"$concat": ["$r.ciudad_origen", " → ", "$r.ciudad_destino"]},
        "distancia_km": "$r.distancia_km",
        "fecha_envio": 1,
        "estado": 1,
        "medio_pago": 1,
        "total": 1,
        "puntaje": "$v.puntaje",
        "comentario": "$v.comentario",
        "recomienda": {"$cond": ["$v.recomienda", 1, 0]},
        "con_retraso": {"$cond": [{"$eq": ["$v.comentario", "Tuvo retraso"]}, 1, 0]},
        "cancelada": {"$cond": [{"$eq": ["$estado", "Cancelado"]}, 1, 0]},
        "entregada": {"$cond": [{"$eq": ["$estado", "Entregado"]}, 1, 0]},
        "eventos_seguimiento": {"$size": {"$ifNull": ["$s.historial", []]}},
        "dias_entrega": {"$dateDiff": {"startDate": {"$min": "$s.historial.fecha"},
                                       "endDate": "$entrega.fecha", "unit": "day"}},
        "requiere_revision": {"$cond": [{"$ifNull": ["$s.requiere_revision", False]}, 1, 0]},
    }},
    {"$sort": {"fecha_envio": 1}},
]


def main():
    client, db = get_db()
    ordenes = pd.DataFrame(db.ordenes_entrega.aggregate(PIPELINE_ORDENES))
    ordenes["anio"] = ordenes["fecha_envio"].dt.year
    ordenes["mes"] = ordenes["fecha_envio"].dt.to_period("M").dt.to_timestamp()

    kpi_zona = (ordenes.groupby("zona")
                .agg(ordenes=("orden_id", "count"), ventas=("total", "sum"),
                     pct_canceladas=("cancelada", "mean"), pct_retraso=("con_retraso", "mean"),
                     puntaje_promedio=("puntaje", "mean"), pct_recomienda=("recomienda", "mean"),
                     distancia_promedio_km=("distancia_km", "mean"))
                .reset_index())
    for col in ["pct_canceladas", "pct_retraso", "pct_recomienda"]:
        kpi_zona[col] = (kpi_zona[col] * 100).round(1)
    kpi_zona = kpi_zona.round({"ventas": 0, "puntaje_promedio": 2, "distancia_promedio_km": 1})

    medio_pago = (ordenes.groupby("medio_pago")
                  .agg(ordenes=("orden_id", "count"), puntaje_promedio=("puntaje", "mean"),
                       pct_recomienda=("recomienda", "mean"), ventas=("total", "sum"))
                  .reset_index())
    medio_pago["pct_recomienda"] = (medio_pago["pct_recomienda"] * 100).round(1)
    medio_pago = medio_pago.round({"puntaje_promedio": 2, "ventas": 0})

    comentarios = (ordenes.groupby("comentario").agg(cantidad=("orden_id", "count"),
                                                     puntaje_promedio=("puntaje", "mean"))
                   .reset_index().round(2).sort_values("cantidad", ascending=False))

    rutas = pd.DataFrame(db.rutas.find({}, {"_id": 0, "ruta_id": "$_id", "zona": 1, "ciudad_origen": 1,
                                            "ciudad_destino": 1, "distancia_km": 1}))

    archivo = SALIDA / "quicktrack_powerbi.xlsx"
    with pd.ExcelWriter(archivo, engine="openpyxl") as xls:
        ordenes.to_excel(xls, sheet_name="ordenes", index=False)
        kpi_zona.to_excel(xls, sheet_name="kpi_zona", index=False)
        medio_pago.to_excel(xls, sheet_name="medio_pago", index=False)
        comentarios.to_excel(xls, sheet_name="comentarios", index=False)
        rutas.to_excel(xls, sheet_name="rutas", index=False)

    log.info("Exportadas %d órdenes a %s", len(ordenes), archivo)
    print(f"\nÓrdenes exportadas: {len(ordenes)} (sin registros de prueba)")
    print("\nKPI por zona:\n" + kpi_zona.to_string(index=False))
    print("\nPor medio de pago:\n" + medio_pago.to_string(index=False))
    print(f"\nArchivo para Power BI: {archivo}")
    client.close()


if __name__ == "__main__":
    main()
