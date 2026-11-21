"""Las tres herramientas de F7 como herramientas de LangChain.

El modelo ve exactamente lo mismo que en n8n: el nombre, la descripción y un
solo argumento con su descripción, sin forma impuesta (decisión D7):

    {"type": "object",
     "properties": {<argumento>: {"description": <descripción del argumento>}},
     "required": [<argumento>],
     "additionalProperties": false}

El `ContextoTurno` (conversación, último mensaje del lote, modalidad) no lo
ve el modelo: cada turno arma sus herramientas cerrando sobre su contexto.

Cada llamada queda anotada en `pasos` con la forma de los
`intermediateSteps` de n8n, que es lo que espera el control de salida:
    {"action": {"tool": <nombre>, "toolInput": {<argumento>: ...}}, "observation": <resultado>}
"""

from __future__ import annotations

import json
from typing import Callable

from langchain_core.tools import StructuredTool

from . import derivacion, multimedia
from .local import ContextoTurno
from .precios import herramienta as precios


def esquema(argumento: str, descripcion_argumento: str) -> dict:
    """El esquema JSON del argumento, igual al de n8n."""
    return {
        "type": "object",
        "properties": {argumento: {"description": descripcion_argumento}},
        "required": [argumento],
        "additionalProperties": False,
    }


def _herramienta(modulo, ejecutar: Callable, contexto: ContextoTurno, pasos: list) -> StructuredTool:
    def correr(**entrada) -> str:
        resultado = ejecutar(entrada.get(modulo.ARGUMENTO), contexto)
        pasos.append(
            {
                "action": {"tool": modulo.NOMBRE, "toolInput": dict(entrada)},
                "observation": resultado,
            }
        )
        return json.dumps(resultado, ensure_ascii=False)

    return StructuredTool.from_function(
        func=correr,
        name=modulo.NOMBRE,
        description=modulo.DESCRIPCION,
        args_schema=esquema(modulo.ARGUMENTO, modulo.DESCRIPCION_ARGUMENTO),
    )


def crear_herramientas(
    contexto: ContextoTurno,
    pasos: list,
    *,
    leer_hojas: Callable[[list[str]], list[dict]] | None = None,
) -> list[StructuredTool]:
    """Las tres herramientas de este turno, en el orden del principal de n8n.

    `leer_hojas` reemplaza la lectura de la planilla (para las pruebas sin red).
    """

    def ejecutar_precio(pedido, ctx):
        return precios.ejecutar(pedido, ctx, leer_hojas=leer_hojas)

    return [
        _herramienta(precios, ejecutar_precio, contexto, pasos),
        _herramienta(multimedia, multimedia.ejecutar, contexto, pasos),
        _herramienta(derivacion, derivacion.ejecutar, contexto, pasos),
    ]
