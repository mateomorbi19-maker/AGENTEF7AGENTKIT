"""Fotos y videos de F7: la herramienta enviar_multimedia.

- seleccion.py: qué piezas del catálogo salen para cada pedido (port de seleccion.mjs).
- descripcion.py: lo que ve el modelo, byte a byte.
- herramienta.py: el envío a la sesión local, con el mismo resultado que hoy da n8n.
"""

from agente.f7.multimedia.herramienta import (
    ARGUMENTO,
    DESCRIPCION,
    DESCRIPCION_ARGUMENTO,
    NOMBRE,
    ejecutar,
)

__all__ = ["ARGUMENTO", "DESCRIPCION", "DESCRIPCION_ARGUMENTO", "NOMBRE", "ejecutar"]
