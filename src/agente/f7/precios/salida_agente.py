"""Lo que buscar_precio le devuelve al modelo: port de salida-agente.mjs.

El presupuesto completo y su evidencia quedan en el registro de la
herramienta. Tras enviarlo, el modelo recibe el estado. Desde el 16/11 el
mensaje no lleva pregunta final (pedido de Mateo). Sin importes.

Corrección del 20/11/2026 (campaña de pruebas): si el motor marcó un ítem con
`requiere_derivacion` (año no cubierto, configuración que no coincide con nada,
fila sin precio numérico), el resumen no lleva ese texto de sistema. Lleva
`requiere_derivacion: revision_especial` y la continuación vacía, para que la
conversación pase a una persona.
"""

from __future__ import annotations

import re

from .motor import PREGUNTA_ANIO, _rx, js_str, js_trim, nombre_limpio

INSTRUCCIONES = (
    "Consultar cuánto sale con un medio de pago no es confirmar una compra. Si pide comprar, pagar, reservar, "
    "una persona o posventa, priorizá derivar_humano. Con metodo_no_confirmado invocá derivar_humano con "
    "revision_especial sin prometer tarifa ni aceptación. Con metodo_no_disponible copiá continuacion_obligatoria. "
    "Con cotización aceptada u omitida y continuación vacía no repitas presupuesto ni agregues otra elección de "
    "pago: la herramienta ya dio el valor solicitado. Si hay otra duda factual explícita, podés responderla "
    "brevemente. Las aclaraciones y errores conservan su continuación literal. Si el cliente preguntó además otra "
    "cosa concreta, respondela en un párrafo aparte, sin importes ni otra pregunta. No agregues importes ni cambies "
    "rangos de año. Control humano o bot pausado exige silencio."
)
ERROR_ENVIO = "No pude confirmar el envío de la cotización. Esa parte necesita revisión del equipo."
ERROR_CONSULTA = "Ahora no pude consultar el precio. Esa parte necesita revisión del equipo."

_RX_MARCAS = re.compile(r"[*_`#<>]")
_RX_SALTOS = re.compile(r"[\r\n\t]+")
_RX_CONFLICTO = _rx(r"importes distintos|contradic|inconsisten|no coincide")


def _limpio(valor) -> str:
    return js_trim(_RX_SALTOS.sub(" ", _RX_MARCAS.sub("", js_str("" if valor is None else valor))))


def _verdadero(valor) -> bool:
    """Verdad de JS: una lista o un dict vacíos también valen."""
    if isinstance(valor, (list, dict)):
        return True
    return bool(valor)


def _aclaracion(pendiente: dict) -> tuple[str, list]:
    """El texto que le pide la aclaración al cliente y los modelos que le ofrece en ese texto."""
    posibles = pendiente.get("opciones") or []
    # Corrección del 20/11 (campaña de pruebas): el nombre va sin la nota interna de la planilla.
    opciones = [t for t in (_limpio(nombre_limpio(o["modelo"]) if o.get("modelo") is not None
                                    else o.get("configuracion"))
                            for o in posibles) if t]
    conflicto = bool(_RX_CONFLICTO.search(js_str(pendiente.get("motivo") if pendiente.get("motivo") is not None
                                                  else "")))
    if len(opciones) > 1 and not conflicto:
        texto = (f"Para {_limpio(pendiente['producto'])}, ¿cuál de estas opciones corresponde a tu "
                 f"vehículo: {' o '.join(opciones)}?")
    elif _limpio(pendiente.get("motivo")) == PREGUNTA_ANIO:
        # Prueba del 21/11 (R26): la pregunta por el año va sola, sin «Opción publicada: …».
        texto = PREGUNTA_ANIO
    else:
        texto = _limpio(pendiente.get("motivo")) + (
            f" Opción publicada: {opciones[0]}." if len(opciones) == 1 and not conflicto else "")
    modelos = [] if conflicto else [o["modelo"] for o in posibles if o.get("modelo") is not None]
    return texto, modelos


def opciones_ofrecidas(resumen: dict) -> list:
    """Los modelos que un resumen le ofrece al cliente en su continuación (ninguno si no pregunta).

    Corrección del 20/11 (campaña de pruebas): la herramienta los recuerda para reconocer, en
    el turno siguiente, cuál eligió el cliente.
    """
    for pendiente in (i for i in resumen.get("items") or [] if i.get("estado") == "requiere_aclaracion"):
        texto, modelos = _aclaracion(pendiente)
        if texto and resumen.get("continuacion_obligatoria") == texto:
            return modelos
    return []


def derivar_en_vez_de_repetir(resumen: dict) -> dict:
    """El mismo resumen, pidiendo la derivación en lugar de repetir su continuación.

    Corrección del 20/11 (campaña de pruebas): la herramienta no le hace dos veces seguidas la
    misma aclaración al cliente; la segunda vez pasa a una persona.
    """
    salida = {}
    for clave, valor in resumen.items():
        if clave == "cotizacion_enviada":
            salida.setdefault("requiere_derivacion", "revision_especial")
        salida[clave] = valor
    salida["requiere_derivacion"] = "revision_especial"
    salida["continuacion_obligatoria"] = ""
    return salida


def resumir_para_agente(resultado: dict, envio: dict, pedido=None) -> dict:
    """`resumirParaAgente(resultado, envio, pedido)`. Las claves que en JS quedan `undefined` no van."""
    items = []
    for i in resultado.get("items") or []:
        item = {"producto": i.get("producto"), "modelo": i.get("modelo"), "estado": i.get("estado"),
                "cantidad": i.get("cantidad")}
        if "configuracion" in i:
            item["configuracion"] = i["configuracion"]
        if _verdadero(i.get("motivo")):
            item["motivo"] = i["motivo"]
        if _verdadero(i.get("opciones")):
            item["opciones"] = i["opciones"]
        item["medios_disponibles"] = list(i.get("precios") or {})
        items.append(item)
    continuacion = ""
    estado_envio = (envio or {}).get("estado")
    aceptado = estado_envio in ("aceptado", "omitido")
    pendiente = next((i for i in items if i["estado"] == "requiere_aclaracion"), None)
    # Corrección del 20/11 (campaña de pruebas): año no cubierto, configuración que no coincide con
    # nada o fila sin precio numérico. El cliente no lo puede resolver: en vez del texto de
    # sistema, el resumen pide la derivación y la continuación va vacía.
    # Re-prueba del 20/11 (C04): vale aunque otro ítem tenga una aclaración que el cliente podría
    # contestar. Seguir preguntando dejaba al modelo reintentar sin la configuración pedida
    # («alfombra trasera») y cotizar otra cosa: si algo no se puede resolver, pasa a una persona.
    derivar = (any(i.get("requiere_derivacion") for i in resultado.get("items") or [])
               and estado_envio not in ("control_humano", "desconocido", "fallido"))
    if estado_envio == "control_humano":
        continuacion = ""
    elif estado_envio in ("desconocido", "fallido"):
        continuacion = ERROR_ENVIO
    elif derivar:
        continuacion = ""
    elif pendiente:
        continuacion = _aclaracion(pendiente)[0]
    elif aceptado and resultado.get("estado") == "cotizado":
        # La herramienta ya mandó el presupuesto en un único mensaje.
        continuacion = ""
    elif resultado.get("estado") == "error_consulta":
        continuacion = ERROR_CONSULTA
    else:
        sin_precio = next((i for i in items if i["estado"] in ("sin_precio", "no_encontrado")), None)
        if sin_precio:
            continuacion = _limpio(sin_precio.get("motivo"))
        else:
            aclaraciones = resultado.get("aclaraciones") or []
            continuacion = _limpio(aclaraciones[0] if aclaraciones else None)
    salida = {"estado": resultado.get("estado"), "items": items, "envio": envio}
    if "consultado_en" in resultado:
        salida["consultado_en"] = resultado["consultado_en"]
    if "metodo_pago" in resultado:
        salida["metodo_pago"] = resultado["metodo_pago"]
    salida["pregunta_comercial_incluida"] = resultado.get("pregunta_comercial_incluida") is True
    if resultado.get("estado") == "metodo_no_confirmado" or derivar:
        salida["requiere_derivacion"] = "revision_especial"
    salida["cotizacion_enviada"] = aceptado
    salida["continuacion_obligatoria"] = continuacion
    salida["instrucciones"] = INSTRUCCIONES
    return salida
