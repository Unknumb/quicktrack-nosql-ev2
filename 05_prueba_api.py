"""
05 - Prueba end-to-end de la API REST (alternativa a Postman).
Requiere la API corriendo en otra terminal:  python app.py

Muestra lectura/escritura en tiempo real: lo que se escribe por la API se
lee inmediatamente después desde la base.
Uso:  python 05_prueba_api.py
"""
import json
import time

import requests

API = "http://localhost:5050"


def llamar(metodo, ruta, cuerpo=None):
    t0 = time.perf_counter()
    r = requests.request(metodo, API + ruta, json=cuerpo, timeout=10)
    ms = (time.perf_counter() - t0) * 1000
    print(f"\n{metodo} {ruta} -> {r.status_code} ({ms:.0f} ms) X-Request-ID={r.headers.get('X-Request-ID')}")
    try:
        datos = r.json()
    except ValueError:
        datos = r.text
    texto = json.dumps(datos, ensure_ascii=False, indent=2)
    print(texto[:700] + ("\n..." if len(texto) > 700 else ""))
    return r.status_code, datos


def main():
    try:
        llamar("GET", "/health")
    except requests.ConnectionError:
        raise SystemExit("La API no responde. Ejecuta primero:  python app.py")

    llamar("GET", "/ordenes?zona=Norte&estado=Entregado&limite=3")
    llamar("GET", "/kpis/zonas")

    _, cliente = llamar("POST", "/clientes", {"nombre": "Cliente API", "correo": f"api{int(time.time())}@quicktrack.cl",
                                              "pais": "Chile"})
    _, orden = llamar("POST", "/ordenes", {"cliente_id": cliente["_id"], "ruta_id": "ruta_5",
                                           "total": 32500, "medio_pago": "Transferencia"})
    oid = orden["_id"]
    llamar("GET", f"/ordenes/{oid}")  # lectura inmediata de lo recién escrito
    for estado in ["Despachado", "En tránsito", "Entregado"]:
        llamar("PATCH", f"/ordenes/{oid}/estado", {"estado": estado})
    llamar("POST", "/valoraciones", {"orden_id": oid, "puntaje": 4, "comentario": "Muy buen servicio"})
    llamar("GET", f"/ordenes/{oid}")

    print("\n######## Casos de error controlados ########")
    llamar("POST", "/ordenes", {"cliente_id": "cli_1", "ruta_id": "ruta_1", "total": "mucho", "medio_pago": "Tarjeta"})
    llamar("POST", "/ordenes", {"cliente_id": "cli_00000", "ruta_id": "ruta_1", "total": 100, "medio_pago": "Tarjeta"})
    llamar("PATCH", f"/ordenes/{oid}/estado", {"estado": "En preparación"})
    llamar("GET", "/ordenes?zona=Marte")
    llamar("GET", "/ordenes/orden_inexistente")

    llamar("DELETE", f"/ordenes/{oid}")
    llamar("GET", f"/ordenes/{oid}")


if __name__ == "__main__":
    main()
