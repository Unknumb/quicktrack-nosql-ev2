"""
Carga las 5 colecciones de QuickTrack (anexo Forma B) en Azure Cosmos DB for NoSQL,
la misma cuenta/base que usaste en el LAB 3.1.2.

Diferencia clave con MongoDB: Cosmos DB for NoSQL exige un campo 'id' (string) y no usa '_id'.
Por eso este script copia '_id' -> 'id' (se conserva '_id' para trazabilidad).
Los 5 contenedores se crean con partition key distinta según el patrón de consulta.

Variables de entorno (NO las pegues en el código ni las subas al repo):
  COSMOS_ENDPOINT = https://<tu-cuenta>.documents.azure.com:443/
  COSMOS_KEY      = <clave primaria>
  COSMOS_DB       = quicktrack          (opcional)

Uso:
  python cargar_cosmos.py --datos "../../data" --dry-run   # solo valida, no toca Azure
  python cargar_cosmos.py --datos "../../data"             # carga real (idempotente: upsert)
  python cargar_cosmos.py --datos ... --throughput 400                          # cuenta con throughput aprovisionado
"""
import argparse
import json
import os
from pathlib import Path

# contenedor -> (archivo, partition key)
CONTENEDORES = {
    "clientes":        ("clientes.json",        "/pais"),
    "rutas":           ("rutas.json",           "/zona"),
    "ordenes_entrega": ("ordenes_entrega.json", "/ruta_id"),
    "seguimiento":     ("seguimiento.json",     "/orden_id"),
    "valoraciones":    ("valoraciones.json",    "/orden_id"),
}


def leer(path: Path) -> list[dict]:
    txt = path.read_text(encoding="utf-8-sig").strip()
    try:
        d = json.loads(txt)
        return d if isinstance(d, list) else [d]
    except json.JSONDecodeError:                      # JSON Lines
        return [json.loads(l) for l in txt.splitlines() if l.strip()]


def preparar(doc: dict) -> dict:
    d = dict(doc)
    d["id"] = str(d["_id"])                           # Cosmos exige 'id' string
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--throughput", type=int, default=None,
                    help="RU/s compartidos por toda la base (ej. 400). Úsalo si tu cuenta NO es serverless, "
                         "para no pagar 400 RU/s por cada contenedor. En cuentas serverless, no lo uses.")
    a = ap.parse_args()

    docs = {c: [preparar(x) for x in leer(a.datos / f)] for c, (f, _) in CONTENEDORES.items()}
    for c, (_, pk) in CONTENEDORES.items():
        faltan = sum(1 for x in docs[c] if pk.lstrip("/") not in x)
        print(f"{c:16s} {len(docs[c]):4d} docs | partition key {pk:10s} | sin partition key: {faltan}")
        assert faltan == 0, f"{c}: hay documentos sin {pk}"
    if a.dry_run:
        print("\n[dry-run] Validación OK. No se escribió nada en Azure.")
        return

    from azure.cosmos import CosmosClient, PartitionKey   # import tardío: el dry-run no lo necesita
    cli = CosmosClient(os.environ["COSMOS_ENDPOINT"], credential=os.environ["COSMOS_KEY"])
    db = cli.create_database_if_not_exists(os.getenv("COSMOS_DB", "quicktrack"),
                                           offer_throughput=a.throughput)
    for c, (_, pk) in CONTENEDORES.items():
        cont = db.create_container_if_not_exists(id=c, partition_key=PartitionKey(path=pk))
        for x in docs[c]:
            cont.upsert_item(x)
        n = list(cont.query_items("SELECT VALUE COUNT(1) FROM c", enable_cross_partition_query=True))[0]
        print(f"OK {c}: {n} documentos en Cosmos DB")


if __name__ == "__main__":
    main()
