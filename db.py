"""Conexión compartida a MongoDB Atlas + logging (trazabilidad)."""
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def get_logger(nombre: str) -> logging.Logger:
    logger = logging.getLogger(nombre)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    archivo = logging.FileHandler(LOG_DIR / "quicktrack.log", encoding="utf-8")
    archivo.setFormatter(fmt)
    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(fmt)
    logger.addHandler(archivo)
    logger.addHandler(consola)
    return logger


log = get_logger("db")


def get_db():
    """Devuelve (client, db). Falla con un mensaje claro si no hay conexión."""
    uri = os.getenv("MONGO_URI")
    if not uri:
        sys.exit("ERROR: falta MONGO_URI en el archivo .env (copia .env.example a .env)")
    db_name = os.getenv("DB_NAME", "quicktrack")
    try:
        client = MongoClient(
            uri,
            appname="quicktrack-ev2",
            serverSelectionTimeoutMS=8000,
            retryWrites=True,
            w="majority",
        )
        t0 = time.perf_counter()
        client.admin.command("ping")
        ms = (time.perf_counter() - t0) * 1000
        info = client.server_info()
        log.info("Conexión OK | servidor MongoDB %s | ping %.1f ms | base '%s'", info["version"], ms, db_name)
        return client, client[db_name]
    except ServerSelectionTimeoutError as e:
        log.error("No se pudo conectar (¿IP en Network Access de Atlas? ¿URI correcta?): %s", e)
        sys.exit(1)
    except (ConfigurationError, OperationFailure) as e:
        log.error("Error de configuración/credenciales: %s", e)
        sys.exit(1)
