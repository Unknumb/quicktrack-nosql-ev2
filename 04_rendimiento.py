"""
04 - Evaluación de eficiencia de consultas (IE6).

  A) Sobre los datos reales: explain('executionStats') con índice vs. forzando
     COLLSCAN, y bytes transferidos con / sin proyección.
  B) Prueba de volumen: colección temporal con N órdenes sintéticas para ver
     cómo crece la diferencia al aumentar los datos. Se elimina al terminar.

Uso:  python 04_rendimiento.py [N]   (N por defecto = 20000)
"""
import random
import statistics
import sys
import time
from datetime import datetime, timedelta

import bson
import pandas as pd

from db import BASE_DIR, get_db, get_logger

log = get_logger("rendimiento")
ZONAS = ["Norte", "Centro", "Sur", "Oriente", "Poniente"]
ESTADOS = ["En preparación", "Despachado", "En tránsito", "Entregado", "Cancelado"]


def medir(coleccion, filtro, proyeccion=None, orden=None, hint=None, repeticiones=10):
    """Devuelve métricas del plan (explain) + tiempo promedio medido desde el cliente + bytes."""
    def cursor():
        c = coleccion.find(filtro, proyeccion)
        if orden:
            c = c.sort(orden)
        if hint:
            c = c.hint(hint)
        return c

    plan = cursor().explain()
    stats = plan["executionStats"]
    etapa = plan["queryPlanner"]["winningPlan"]
    etapas = []
    while etapa:  # recorre el árbol del plan (FETCH -> IXSCAN, SORT -> COLLSCAN, ...)
        etapas.append(etapa.get("stage"))
        etapa = etapa.get("inputStage") or (etapa.get("queryPlan") if "queryPlan" in etapa else None)
    tiempos = []
    for _ in range(repeticiones):
        t0 = time.perf_counter()
        docs = list(cursor())
        tiempos.append((time.perf_counter() - t0) * 1000)
    return {
        "plan": " > ".join(s for s in etapas if s),
        "docs_examinados": stats["totalDocsExamined"],
        "claves_examinadas": stats["totalKeysExamined"],
        "devueltos": stats["nReturned"],
        "ms_servidor": stats["executionTimeMillis"],
        "ms_cliente_prom": round(statistics.mean(tiempos), 2),
        "kb_transferidos": round(sum(len(bson.encode(d)) for d in docs) / 1024, 2),
    }


def parte_a(db):
    print("\n=== A) Datos reales (100 órdenes) ===")
    filtro = {"zona": "Norte", "estado": "Entregado", "total": {"$gt": 100000}}
    proy = {"_id": 1, "total": 1, "fecha_envio": 1}
    filas = [
        {"caso": "C1 sin índice (COLLSCAN forzado)", **medir(db.ordenes_entrega, filtro, proy, [("total", -1)], hint={"$natural": 1})},
        {"caso": "C1 con índice ix_zona_estado_total", **medir(db.ordenes_entrega, filtro, proy, [("total", -1)])},
        {"caso": "C1 con índice SIN proyección", **medir(db.ordenes_entrega, filtro, None, [("total", -1)])},
        {"caso": "Valoraciones puntaje<=2 COLLSCAN", **medir(db.valoraciones, {"puntaje": {"$lte": 2}}, hint={"$natural": 1})},
        {"caso": "Valoraciones puntaje<=2 ix_puntaje", **medir(db.valoraciones, {"puntaje": {"$lte": 2}})},
    ]
    return pd.DataFrame(filas)


def parte_b(db, n):
    print(f"\n=== B) Prueba de volumen ({n} órdenes sintéticas en 'ordenes_bench') ===")
    bench = db.ordenes_bench
    bench.drop()
    random.seed(42)
    inicio = datetime(2022, 1, 1)
    lote = []
    t0 = time.perf_counter()
    for i in range(n):
        lote.append({"_id": f"b_{i}", "cliente_id": f"cli_{random.randint(1, 5000)}", "zona": random.choice(ZONAS),
                     "estado": random.choice(ESTADOS), "medio_pago": random.choice(["Tarjeta", "Efectivo", "Transferencia"]),
                     "fecha_envio": inicio + timedelta(days=random.randint(0, 1000)),
                     "total": round(random.uniform(10000, 200000), 2)})
        if len(lote) == 5000:
            bench.insert_many(lote, ordered=False)
            lote = []
    if lote:
        bench.insert_many(lote, ordered=False)
    print(f"Insertados {bench.count_documents({})} docs en {time.perf_counter() - t0:.1f} s")

    filtro = {"zona": "Norte", "estado": "Entregado", "total": {"$gt": 190000}}
    proy = {"_id": 1, "total": 1}
    filas = [{"caso": f"{n} docs SIN índice", **medir(bench, filtro, proy, [("total", -1)], repeticiones=5)}]
    bench.create_index([("zona", 1), ("estado", 1), ("total", -1)])
    filas.append({"caso": f"{n} docs CON índice compuesto", **medir(bench, filtro, proy, [("total", -1)], repeticiones=5)})
    filas.append({"caso": f"{n} docs índice SIN proyección", **medir(bench, filtro, None, [("total", -1)], repeticiones=5)})
    bench.drop()
    log.info("Colección ordenes_bench eliminada")
    return pd.DataFrame(filas)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    client, db = get_db()
    pd.set_option("display.width", 220)
    a = parte_a(db)
    print(a.to_string(index=False))
    b = parte_b(db, n)
    print(b.to_string(index=False))
    pd.concat([a, b]).to_csv(BASE_DIR / "resultados" / "rendimiento.csv", index=False)

    sin, con = b.iloc[0], b.iloc[1]
    print("\n=== Conclusiones automáticas ===")
    print(f"- Con {n} docs el índice compuesto reduce los documentos examinados de {sin.docs_examinados} "
          f"a {con.docs_examinados} ({100 * (1 - con.docs_examinados / max(sin.docs_examinados, 1)):.1f}% menos).")
    print(f"- Tiempo cliente: {sin.ms_cliente_prom} ms -> {con.ms_cliente_prom} ms.")
    print(f"- La proyección reduce los datos transferidos de {b.iloc[2].kb_transferidos} KB a {con.kb_transferidos} KB.")
    print("- Con solo 100 docs la diferencia es mínima (todo cabe en memoria); el beneficio aparece al crecer el volumen.")
    client.close()


if __name__ == "__main__":
    main()
