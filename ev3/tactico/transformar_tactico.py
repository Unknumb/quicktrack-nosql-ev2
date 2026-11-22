"""
QuickTrack · Pregunta TÁCTICA · Transformación en Python (la parte ETL del flujo) previa al dashboard.

Entrada  : los 3 archivos JSON que deja Azure Data Factory en Blob Storage
           (ordenes_planas.json, rutas.json, seguimiento_eventos.json).
Salida   : out/tactico_ordenes.csv   -> tabla de hechos para Power BI (1 fila por orden)
           out/tactico_zona_tramo.csv -> resumen para validar los visuales
           out/calidad_datos.txt      -> evidencia de limpieza (para el informe)

Uso:
  # con lo que descargaste de Blob (salida de ADF)
  python transformar_tactico.py --entrada ./adf_salida

  # para probar sin Azure: arma el mismo aplanado desde los JSON crudos de la EP2
  python transformar_tactico.py --desde-crudo "../../data"
"""
import argparse
import json
from pathlib import Path

import pandas as pd

TRAMOS = [(0, 500, "1. Corta (<500 km)"),
          (500, 1000, "2. Media (500-999 km)"),
          (1000, 1500, "3. Larga (1.000-1.499 km)"),
          (1500, float("inf"), "4. Muy larga (>=1.500 km)")]


def leer_json(path: Path) -> list[dict]:
    """ADF escribe 'Set of objects' (JSON Lines) o 'Array of objects'; soporta ambos."""
    txt = path.read_text(encoding="utf-8-sig").strip()
    try:
        data = json.loads(txt)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return [json.loads(linea) for linea in txt.splitlines() if linea.strip()]


def aplanar_crudo(carpeta: Path) -> dict[str, list[dict]]:
    """Réplica local de lo que hacen las consultas de ADF (ver adf_consultas.md)."""
    ordenes = [{"id": o["_id"], "cliente_id": o["cliente_id"], "ruta_id": o["ruta_id"],
                "fecha_envio": o["fecha_envio"], "estado": o["estado"],
                "medio_pago": o["medio_pago"], "total": o["total"]}
               for o in leer_json(carpeta / "ordenes_entrega.json")]
    rutas = [{"id": r["_id"], "zona": r["zona"], "ciudad_origen": r["ciudad_origen"],
              "ciudad_destino": r["ciudad_destino"], "distancia_km": r["distancia_km"]}
             for r in leer_json(carpeta / "rutas.json")]
    eventos = [{"orden_id": s["orden_id"], "estado_evento": h["estado"], "fecha_evento": h["fecha"]}
               for s in leer_json(carpeta / "seguimiento.json") for h in s["historial"]]
    return {"ordenes": ordenes, "rutas": rutas, "eventos": eventos}


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--entrada", type=Path, help="carpeta con la salida de ADF")
    g.add_argument("--desde-crudo", type=Path, help="carpeta data/ de la EP2 (prueba local)")
    ap.add_argument("--salida", type=Path, default=Path(__file__).parent / "out")
    a = ap.parse_args()
    a.salida.mkdir(exist_ok=True)

    if a.entrada:
        src = {"ordenes": leer_json(a.entrada / "ordenes_planas.json"),
               "rutas": leer_json(a.entrada / "rutas.json"),
               "eventos": leer_json(a.entrada / "seguimiento_eventos.json")}
    else:
        src = aplanar_crudo(a.desde_crudo)
    ordenes, rutas, eventos = (pd.DataFrame(src[k]) for k in ("ordenes", "rutas", "eventos"))
    cal = []  # líneas de evidencia de calidad

    # 1) LIMPIEZA ----------------------------------------------------------------------------
    dups = {}
    for nombre, df in (("ordenes", ordenes), ("rutas", rutas)):
        dups[nombre] = int(df.duplicated("id").sum())
        cal.append(f"{nombre}: {len(df)} filas, {dups[nombre]} duplicados por 'id' (eliminados)")
    ordenes = ordenes.drop_duplicates("id")
    rutas = rutas.drop_duplicates("id")
    par = rutas.groupby(["ciudad_origen", "ciudad_destino"]).agg(
        rutas=("id", "size"), zonas=("zona", "nunique"),
        dif_km=("distancia_km", lambda s: s.max() - s.min()))
    cal.append(f"rutas: {len(par)} pares origen-destino únicos en {len(rutas)} rutas; {int((par['zonas'] > 1).sum())} pares "
               f"aparecen en más de una zona y {int((par['dif_km'] > 200).sum())} con diferencias de distancia > 200 km "
               f"(p.ej. misma ciudad origen-destino con 114 y 1.946 km) -> distancia_km con baja Confidence; "
               f"no se usa la etiqueta origen->destino como dimensión")
    for col in ("zona", "ciudad_origen", "ciudad_destino"):
        rutas[col] = rutas[col].astype(str).str.strip().str.title()           # normalización de texto
    ordenes["estado"] = ordenes["estado"].astype(str).str.strip()
    nulos = int(ordenes[["id", "ruta_id", "estado", "total"]].isna().sum().sum())
    cal.append(f"ordenes: {nulos} nulos en id/ruta_id/estado/total")

    # 2) CONVERSIÓN DE TIPOS -----------------------------------------------------------------
    ordenes["total"] = pd.to_numeric(ordenes["total"], errors="coerce")
    ordenes["fecha_envio"] = pd.to_datetime(ordenes["fecha_envio"])
    rutas["distancia_km"] = pd.to_numeric(rutas["distancia_km"], errors="coerce")
    eventos["fecha_evento"] = pd.to_datetime(eventos["fecha_evento"])

    # 3) HISTORIAL (ya aplanado por ADF) -> 1 fila por orden ----------------------------------
    eventos = eventos.sort_values(["orden_id", "fecha_evento"])
    seg = eventos.groupby("orden_id").agg(
        n_eventos=("estado_evento", "size"),
        primer_evento=("fecha_evento", "min"),
        ultimo_evento=("fecha_evento", "max"),
        ultimo_estado=("estado_evento", "last"),
    ).reset_index()
    seg["dias_ciclo"] = (seg["ultimo_evento"] - seg["primer_evento"]).dt.days
    seg["llego_entregado"] = (seg["ultimo_estado"] == "Entregado").astype(int)
    brechas = eventos.groupby("orden_id")["fecha_evento"].diff().dt.days.dropna()
    cal.append(f"historial: brecha entre eventos consecutivos -> valores {sorted(brechas.unique().tolist())} días "
               f"({len(brechas)} pares). Con brecha constante, dias_ciclo no discrimina: se documenta y no se usa como KPI.")

    # 4) INTEGRACIÓN (ordenes + rutas + seguimiento) ------------------------------------------
    f = ordenes.merge(rutas, left_on="ruta_id", right_on="id", how="left", suffixes=("", "_ruta"))
    huerfanas = int(f["zona"].isna().sum())
    cal.append(f"integridad: {huerfanas} órdenes sin ruta válida")
    f = f.merge(seg, left_on="id", right_on="orden_id", how="left")
    cal.append(f"integridad: {int(f['n_eventos'].isna().sum())} órdenes sin seguimiento")

    # 5) CAMPOS DERIVADOS -----------------------------------------------------------------------
    f["cancelada"] = (f["estado"] == "Cancelado").astype(int)
    f["ingreso_perdido"] = f["total"].where(f["cancelada"] == 1, 0.0)
    f["tramo_distancia"] = pd.cut(f["distancia_km"], [t[0] for t in TRAMOS] + [float("inf")],
                                  labels=[t[2] for t in TRAMOS], right=False)
    inconsistente = int(((f["cancelada"] == 1) & (f["llego_entregado"] == 1)).sum())
    cal.append(f"consistencia: {inconsistente} órdenes 'Cancelado' cuyo historial llega a 'Entregado' "
               f"(historial no confiable -> se usa solo el estado de la orden como fuente de cancelación)")
    coincide = int((f["estado"] == f["ultimo_estado"]).sum())
    cal.append(f"consistencia: estado de la orden = último evento del historial solo en {coincide}/{len(f)} órdenes")

    # El historial se evaluó (ver calidad_datos.txt) pero RICE lo descarta como KPI: no entra al modelo.
    # Tampoco entran fecha_envio ni medio_pago (RICE < 0,5 para la pregunta táctica).
    cols = ["id", "estado", "cancelada", "total", "ingreso_perdido", "ruta_id", "zona", "distancia_km", "tramo_distancia"]
    f = f[cols].rename(columns={"id": "orden_id"})
    f.to_csv(a.salida / "tactico_ordenes.csv", index=False, encoding="utf-8-sig")

    # Versión para Power BI en la nube: SIN decimales. Con la configuración regional es-CL el punto decimal
    # se lee como separador de miles ("134152.77" -> 13.415.277). Los montos van en centavos (enteros exactos)
    # y la distancia en km enteros (el tramo ya está calculado con la distancia original).
    pbi = f.copy()
    pbi["total_centavos"] = (pbi.pop("total") * 100).round().astype("int64")
    pbi["ingreso_perdido_centavos"] = (pbi.pop("ingreso_perdido") * 100).round().astype("int64")
    pbi["distancia_km"] = pbi["distancia_km"].round().astype("int64")
    pbi = pbi[["orden_id", "estado", "cancelada", "total_centavos", "ingreso_perdido_centavos",
               "ruta_id", "zona", "distancia_km", "tramo_distancia"]]
    (a.salida / "powerbi").mkdir(exist_ok=True)
    pbi.to_csv(a.salida / "powerbi" / "tactico_ordenes.csv", index=False, encoding="utf-8-sig")

    # 6) RESUMEN (para validar contra Power BI) -------------------------------------------------
    res = (f.groupby(["zona", "tramo_distancia"], observed=True)
             .agg(ordenes=("orden_id", "size"), canceladas=("cancelada", "sum"),
                  ingreso_perdido=("ingreso_perdido", "sum")).reset_index())
    res["ingreso_perdido"] = res["ingreso_perdido"].round(2)
    res["pct_cancelacion"] = (100 * res["canceladas"] / res["ordenes"]).round(1)
    res.to_csv(a.salida / "tactico_zona_tramo.csv", index=False, encoding="utf-8-sig")
    (a.salida / "calidad_datos.txt").write_text("\n".join(cal), encoding="utf-8")

    # Salida en consola
    print("\n".join(cal))
    glob = 100 * f["cancelada"].mean()
    por_zona = (f.groupby("zona").agg(ordenes=("orden_id", "size"), canceladas=("cancelada", "sum"),
                                      ingreso_perdido=("ingreso_perdido", "sum"),
                                      km_medio=("distancia_km", "mean")))
    por_zona["pct_cancelacion"] = 100 * por_zona["canceladas"] / por_zona["ordenes"]
    por_zona["critica"] = por_zona["pct_cancelacion"] > glob
    print(f"\n% cancelación global: {glob:.1f}% | ingreso perdido total: ${f['ingreso_perdido'].sum():,.0f}")
    print(por_zona.sort_values("pct_cancelacion", ascending=False).round(1).to_string())
    print("\nPor tramo de distancia:")
    t = f.groupby("tramo_distancia", observed=True).agg(ordenes=("orden_id", "size"), canceladas=("cancelada", "sum"))
    t["pct_cancelacion"] = (100 * t["canceladas"] / t["ordenes"]).round(1)
    print(t.to_string())
    print(f"\nArchivos en: {a.salida}")


if __name__ == "__main__":
    main()
