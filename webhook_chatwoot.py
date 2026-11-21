"""El agente atendiendo WhatsApp, a través de Chatwoot.

    python webhook_chatwoot.py

Esto es lo que corre en el servidor. A diferencia del bot de Telegram, acá
**no salimos a buscar los mensajes**: Chatwoot nos pega a una URL. Por eso
necesita dominio y HTTPS, y por eso no sirve levantarlo en tu computadora
salvo para probar que arranca.

El recorrido completo:

    persona → WhatsApp → Meta → Chatwoot → este servidor → agente
                                    ↑                         │
                                    └──────── respuesta ──────┘

Antes de arrancar, en el .env:

    CHATWOOT_URL, CHATWOOT_TOKEN, CHATWOOT_CUENTA_ID
    CHATWOOT_WEBHOOK_TOKEN   ← el secreto que va en la URL del webhook

Para cortar: Ctrl+C.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agente.consola import preparar  # noqa: E402

preparar()  # antes de imprimir nada, para que las tildes no rompan Windows

import logging  # noqa: E402

import uvicorn  # noqa: E402

from agente import Config, ErrorDeConfiguracion  # noqa: E402
from agente.f7.produccion import ErrorDeArranque  # noqa: E402
from agente.f7.servidor import crear_app_f7, modo_f7  # noqa: E402
from agente.web.webhook import crear_app  # noqa: E402

AMBAR = "\033[38;5;214m"
GRIS = "\033[90m"
ROJO = "\033[91m"
FIN = "\033[0m"


def armar_app(config):
    """El servidor que corresponde: AGENTE=f7 (el agente de F7) o AGENTE=kit (el genérico del kit).

    En este proyecto hay que decirlo. Si arrancara el genérico por un olvido,
    un bot sin el guion de F7 terminaría atendiendo a sus clientes.
    """
    agente = (os.getenv("AGENTE") or "").strip().lower()
    if agente == "f7":
        return crear_app_f7(config)
    if agente == "kit":
        return crear_app(config)
    raise ErrorDeConfiguracion(
        "Falta decir qué agente atiende. Agregá AGENTE=f7 a las variables del servidor "
        "(o AGENTE=kit si de verdad querés el agente genérico del kit)."
    )


def main() -> int:
    # En el servidor los logs son lo único que se ve: sin esto, el panel
    # queda mudo y no hay forma de saber si un mensaje llegó.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        config = Config.desde_entorno()
        app = armar_app(config)
    except (ErrorDeConfiguracion, ErrorDeArranque, ValueError) as e:
        print(f"{ROJO}{e}{FIN}")
        return 1

    puerto = int(os.getenv("PUERTO", "8000"))

    print(f"\n{AMBAR}Webhook escuchando{FIN} - puerto {puerto}")
    print(f"{GRIS}   {config.proveedor} - {config.modelo}{' - agente F7' if modo_f7() else ''}{FIN}")
    print(f"{GRIS}   POST /chatwoot/<token>   ·   GET /salud{FIN}\n")

    # host 0.0.0.0 porque adentro de un contenedor, escuchar solo en
    # localhost es escuchar en un lugar al que nadie puede entrar.
    uvicorn.run(app, host="0.0.0.0", port=puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
