"""La herramienta buscar_precio para la web de pruebas.

Sigue el mismo camino que el subflujo «F7 · Buscar precio y cotizar · v1» de
n8n en modo enviar, nodo por nodo, con tres reemplazos locales:
- Postgres (f7_cotizaciones_envios) → `contexto.sesion.registro('precios')`.
- GET de la conversación en Chatwoot → `contexto.sesion.etiquetas`
  (can_reply siempre true, identidad siempre coincide).
- POST a Chatwoot → `contexto.sesion.mandar('cotizacion', ...)`, que se toma
  como aceptado con el id del globo.

Devuelve exactamente lo que el subflujo le devuelve hoy al modelo. Nunca lanza
excepciones: cualquier falla sale como el objeto de error que corresponde.

Corrección del 20/11/2026 (campaña de pruebas). n8n ya no se usa y la herramienta
ahora recuerda la conversación desde el último «borrar»:
- qué opciones le ofreció al cliente, para reconocer la que elige después;
- cuál fue su última continuación, para no repetir la misma aclaración: la
  segunda vez devuelve `requiere_derivacion` y la continuación vacía;
- cuál fue la última cotización aceptada, para no mandar dos veces el mismo texto
  (`envio.estado` omitido, motivo cotizacion_ya_enviada).
Lo primero y lo segundo están en `sesion.registro('precios_aclaraciones')`; lo
tercero sale del registro 'precios' de siempre.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import uuid
from typing import Callable

from ..local import ContextoTurno
from . import planilla
from .descripcion import DESCRIPCION_BUSCAR_PRECIO, DESCRIPCION_PEDIDO_BUSCAR_PRECIO
from .motor import (_rx, clave_opcion, cotizar, es_entero_seguro, js_trim, normal, normalizar_entrada,
                    solo_taller, trabajo_sin_butacas)
from .salida_agente import derivar_en_vez_de_repetir, opciones_ofrecidas, resumir_para_agente
from .vehiculos import cabina_dicha

NOMBRE = "buscar_precio"
ARGUMENTO = "pedido"
DESCRIPCION = DESCRIPCION_BUSCAR_PRECIO
DESCRIPCION_ARGUMENTO = DESCRIPCION_PEDIDO_BUSCAR_PRECIO

PREGUNTA_MODALIDAD = ("Hacemos envios a todo el pais y nuestro taller esta situado en CABA. "
                      "Quisieras la opción de envio o colocarlo en nuestro taller?")
# Tope de «Evaluar control humano»: 140 s desde «Validar pedido».
TOPE_MS = 140000

_RX_SOLICITUD = _rx(r"^cw:1:[1-9]\d*:[1-9]\d{0,31}:precios-v1$")
_RX_MESSAGE_ID = _rx(r"^[1-9]\d{0,31}$")


def _entrada_invalida() -> dict:
    return {"estado": "entrada_invalida", "items": [], "totales": None, "mensaje_cotizacion": None, "aclaraciones": [],
            "envio": {"estado": "no_corresponde"}, "motivo": "pedido_o_contexto_invalido"}


def _error_de_consulta() -> dict:
    return {"estado": "error_consulta", "items": [], "totales": None, "mensaje_cotizacion": None, "aclaraciones": [],
            "envio": {"estado": "no_corresponde"}, "motivo": "no_se_pudo_leer_o_interpretar_planilla"}


def _validar_contexto(raw: dict) -> dict:
    """validarContexto de transporte.mjs."""
    if raw.get("modo") == "simular":
        return {"ok": True, "contexto": {"modo": "simular"}}
    conv = raw.get("conversation_id")
    if (raw.get("modo") != "enviar" or raw.get("account_id") != 1 or isinstance(raw.get("account_id"), bool)
            or not es_entero_seguro(conv) or conv < 1):
        return {"ok": False}
    sid = raw.get("solicitud_id")
    if not isinstance(sid, str) or not sid.startswith(f"cw:1:{conv}:") or not _RX_SOLICITUD.search(sid):
        return {"ok": False}
    return {"ok": True, "contexto": {"modo": "enviar", "account_id": 1, "conversation_id": conv,
                                     "solicitud_id": sid}}


# El texto del motor de n8n para cuando falta el vehículo.
PREGUNTA_MODELO = "Confirmá la marca y el modelo del vehículo."


def _falta_modelo(pedido) -> bool:
    """¿Alguna consulta de un producto para vehículo vino sin el modelo?"""
    if not isinstance(pedido, dict) or not isinstance(pedido.get("consultas"), list):
        return False
    for consulta in pedido["consultas"]:
        if not isinstance(consulta, dict):
            continue
        producto = str(consulta.get("producto") or "").strip().lower()
        # Corrección del 20/11 (campaña de pruebas): un techo o unos paneles pedidos como
        # «tapiceria» se consultan como «otros»: tampoco necesitan el vehículo.
        if producto in ("cubrevolante", "otros") or trabajo_sin_butacas(consulta):
            continue
        if not str(consulta.get("modelo") or "").strip():
            return True
    return False


def _solo_tapiceria(pedido) -> bool:
    """¿Todo lo que se pide cotizar es tapicería? Ese trabajo se hace solo en el taller de CABA."""
    if not isinstance(pedido, dict):
        return False
    consultas = pedido.get("consultas")
    if not isinstance(consultas, list) or not consultas:
        return False
    # Corrección del 20/11 (campaña de pruebas): la regla es para la tapicería de butacas. Un techo
    # o unos paneles pedidos como «tapiceria» no cuentan: siguen el camino de «otros».
    return all(isinstance(c, dict) and normal(c.get("producto")) == "tapiceria" and not trabajo_sin_butacas(c)
               for c in consultas)


def _cabina_del_turno(texto) -> str | None:
    """Prueba del 21/11 (R06, R40): la cabina que escribió el cliente en este turno.

    «Es 2020 doble cabina» y el modelo consultó solo el año: se volvía a preguntar entre la común
    y la cabina simple. Si el cliente nombra las dos cabinas (dos vehículos), no vale ninguna.
    """
    return cabina_dicha(texto) if isinstance(texto, str) else None


def _solo_taller(pedido) -> bool:
    """¿Todo lo que se pide cotizar se hace solo en el taller de CABA?"""
    consultas = pedido.get("consultas") if isinstance(pedido, dict) else None
    return isinstance(consultas, list) and bool(consultas) and all(solo_taller(c) for c in consultas)


def _preparar_pedido_con_modalidad(raw: dict) -> dict:
    """prepararPedidoConModalidad: la modalidad la pone el principal, no el modelo."""
    guard = raw.get("modo") == "enviar" or raw.get("context_guard") is True
    if not guard:
        return {"permitido": True, "pedido": raw.get("pedido")}
    modalidad = raw.get("modalidad_confirmada")
    if modalidad not in ("caba", "envio") and _falta_modelo(raw.get("pedido")):
        # Pedido de Mateo (17/11): de a una pregunta, y primero el modelo del vehículo;
        # la modalidad recién cuando el modelo se conoce.
        return {"permitido": False, "pedido": None, "resultado": {
            "estado": "requiere_aclaracion", "items": [], "totales": None, "mensaje_cotizacion": None,
            "aclaraciones": [], "envio": {"estado": "no_corresponde"}, "cotizacion_enviada": False,
            "motivo": "modelo_no_informado", "continuacion_obligatoria": PREGUNTA_MODELO,
            "instrucciones": "Copiá continuacion_obligatoria literalmente. No se consultó ni envió una cotización. "
                             "No preguntes la modalidad en este turno.",
        }}
    if _solo_tapiceria(raw.get("pedido")):
        # Pedido de Mateo (20/11): la tapicería se hace solo en el taller de CABA y no
        # se ofrece envío. No se pregunta «envío o taller», y tampoco vale un envío
        # elegido antes para otro producto: se cotiza siempre para el taller. El guion
        # pregunta antes si el cliente puede acercarse.
        modalidad = "caba"
    if modalidad not in ("caba", "envio") and _solo_taller(raw.get("pedido")):
        # Prueba del 21/11 (R32, R44): techo, paneles, relleno y espuma tampoco tienen envío. Sin
        # modalidad elegida no se pregunta «envío o taller»: se cotizan para el taller. Si el
        # cliente eligió envío, el motor le contesta que el trabajo es presencial.
        modalidad = "caba"
    if modalidad not in ("caba", "envio"):
        return {"permitido": False, "pedido": None, "resultado": {
            "estado": "requiere_modalidad", "items": [], "totales": None, "mensaje_cotizacion": None,
            "aclaraciones": [], "envio": {"estado": "no_corresponde"}, "cotizacion_enviada": False,
            "motivo": "modalidad_no_confirmada_por_cliente", "continuacion_obligatoria": PREGUNTA_MODALIDAD,
            "instrucciones": "Copiá continuacion_obligatoria literalmente. No se consultó ni envió una cotización. "
                             "No inventes modalidad ni reintentes en este turno.",
        }}
    pedido = raw.get("pedido")
    return {"permitido": True, "pedido": {**pedido, "modalidad": modalidad} if isinstance(pedido, dict) else pedido}


def _ahora_iso() -> str:
    """`new Date().toISOString()`."""
    ahora = dt.datetime.now(dt.timezone.utc)
    return ahora.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ahora.microsecond // 1000:03d}Z"


def _copia_json(valor):
    return json.loads(json.dumps(valor, ensure_ascii=False))


def _como_jsonb(valor):
    """Lo que vuelve de una columna jsonb: claves ordenadas por largo en bytes y después por bytes."""
    if isinstance(valor, dict):
        claves = sorted(valor, key=lambda k: (len(k.encode("utf-8")), k.encode("utf-8")))
        return {k: _como_jsonb(valor[k]) for k in claves}
    if isinstance(valor, list):
        return [_como_jsonb(v) for v in valor]
    return valor


def _texto_bigint(valor):
    """Postgres devuelve bigint a n8n como texto."""
    return None if valor is None else str(valor)


def _evaluar_conversacion(etiquetas) -> dict:
    """evaluarConversacion de entrega.mjs, con lo que hay en la sesión local."""
    if not isinstance(etiquetas, list) or any(not isinstance(e, str) for e in etiquetas):
        return {"permitido": False, "estado": "fallido", "motivo": "control_humano_no_verificable"}
    if any(js_trim(e).lower() == "humano" for e in etiquetas):
        return {"permitido": False, "estado": "control_humano", "motivo": "conversacion_con_humano"}
    return {"permitido": True, "estado": "habilitado", "motivo": None}


def _vigente(contexto: ContextoTurno, solicitud_id: str) -> bool:
    """«Vigencia antes de Enviar»: el lote tiene que ser posterior al último «borrar»."""
    partes = solicitud_id.split(":")
    if len(partes) != 5 or not _RX_MESSAGE_ID.search(partes[3]):
        return False
    return int(partes[3]) > int(contexto.sesion.epoca or 0)


def _ultima_aceptada(sesion, solicitud_id: str) -> dict | None:
    """La última cotización aceptada en la conversación después del último «borrar» (otro lote).

    Corrección del 20/11 (campaña de pruebas): sirve para no mandar dos veces el mismo texto.
    """
    ultima, lote = None, int(sesion.epoca or 0)
    for clave, fila in sesion.registro("precios").items():
        partes = str(clave).split(":")
        if (clave == solicitud_id or not isinstance(fila, dict) or fila.get("estado") != "aceptado"
                or len(partes) != 5 or not _RX_MESSAGE_ID.search(partes[3])):
            continue
        if int(partes[3]) > lote:
            ultima, lote = fila, int(partes[3])
    return ultima


# Corrección del 20/11 (campaña de pruebas). Lo que buscar_precio recuerda de la conversación
# queda en sesion.registro("precios_aclaraciones"), una entrada por época: lo anterior al
# último «borrar» queda en otra entrada y no se lee más.
REGISTRO_ACLARACIONES = "precios_aclaraciones"


def _memoria(contexto: ContextoTurno) -> dict | None:
    """La memoria de la herramienta en esta época (None si el lote es anterior al «borrar»).

    turno:        el lote (message_id) de esta llamada
    continuacion: la continuación que devolvió en este lote
    anterior:     la que había devuelto en el lote anterior en que se usó
    ofrecidas:    opción que se le ofreció al cliente (clave_opcion) → lote en que se ofreció primero
    """
    epoca = int(contexto.sesion.epoca or 0)
    turno = contexto.ultimo_message_id
    if not es_entero_seguro(turno) or turno <= epoca:
        return None
    memoria = contexto.sesion.registro(REGISTRO_ACLARACIONES).setdefault(
        str(epoca), {"turno": None, "continuacion": None, "anterior": None, "ofrecidas": {}})
    if memoria["turno"] != turno:
        # Empieza otro lote: lo último que devolvió es lo último que vio el cliente.
        memoria.update(turno=turno, anterior=memoria["continuacion"], continuacion=None)
    return memoria


def _ya_ofrecidas(memoria: dict | None) -> set:
    """Las opciones que el cliente ya vio en lotes anteriores. Las de este lote todavía no las contestó."""
    try:
        return {clave for clave, lote in memoria["ofrecidas"].items() if lote != memoria["turno"]}
    except Exception:  # sin memoria no hay nada ofrecido: se pregunta como la primera vez
        return set()


def _recordar(resultado: dict, memoria: dict | None) -> dict:
    """Anota lo que este resultado le dice al cliente y no deja repetir la misma aclaración."""
    continuacion = resultado.get("continuacion_obligatoria")
    if memoria is None or not isinstance(continuacion, str):
        return resultado
    memoria["continuacion"] = continuacion
    # Lo mismo que vio el cliente en el lote anterior: no se repite, pasa a una persona. Otra
    # llamada dentro del mismo lote no cuenta (el cliente todavía no la vio). Las dos preguntas
    # del recorrido de venta (vehículo y modalidad) se siguen haciendo como siempre.
    if continuacion and continuacion == memoria["anterior"] and continuacion not in (PREGUNTA_MODALIDAD,
                                                                                    PREGUNTA_MODELO):
        return derivar_en_vez_de_repetir(resultado)
    for modelo in opciones_ofrecidas(resultado):
        if clave_opcion(modelo):
            memoria["ofrecidas"].setdefault(clave_opcion(modelo), memoria["turno"])
    # Re-prueba del 20/11: la variante que se cotizó también queda anotada. Si después llega su
    # nombre tal cual («ONIX GEN 2 (2020+)») sin el año, es esa: no se le pide confirmar el año.
    for item in resultado.get("items") or []:
        if isinstance(item, dict) and item.get("estado") == "cotizado" and clave_opcion(item.get("modelo")):
            memoria["ofrecidas"].setdefault(clave_opcion(item["modelo"]), memoria["turno"])
    return resultado


def ejecutar(pedido, contexto: ContextoTurno, *,
             leer_hojas: Callable[[list[str]], list[dict]] | None = None) -> dict:
    """Corre buscar_precio con el pedido del modelo. Devuelve el objeto que ve el modelo.

    `leer_hojas` reemplaza la lectura de la planilla (para las pruebas sin red).
    """
    try:
        memoria = _memoria(contexto)
    except Exception:
        memoria = None
    try:
        resultado = _ejecutar(pedido, contexto, leer_hojas or planilla.leer_hojas, memoria)
    except Exception:  # una herramienta no lanza: lo inesperado es un error de consulta
        return _error_de_consulta()
    try:
        return _recordar(resultado, memoria)
    except Exception:  # la memoria no puede romper un resultado que ya está resuelto
        return resultado


def _ejecutar(pedido, contexto: ContextoTurno, leer_hojas, memoria: dict | None = None) -> dict:
    inicio = time.monotonic()
    sesion = contexto.sesion
    raw = {"pedido": pedido, "account_id": contexto.account_id, "conversation_id": contexto.conversation_id,
           "solicitud_id": contexto.solicitud_id("precios-v1"), "modo": contexto.modo,
           "modalidad_confirmada": contexto.modalidad_confirmada, "context_guard": True}

    # «Validar pedido» (PR1 y PR2). Si el nodo falla, n8n sale por «Entrada invalida».
    try:
        guard = _preparar_pedido_con_modalidad(raw)
        n = normalizar_entrada(guard["pedido"]) if guard["permitido"] else {"ok": False, "entrada": None}
        ctx = _validar_contexto(raw)
    except Exception:
        return _entrada_invalida()
    if not (n["ok"] and ctx["ok"]):
        if ctx["ok"] and not guard["permitido"]:
            return guard["resultado"]  # «Preguntar modalidad»
        return _entrada_invalida()
    entrada = n["entrada"]
    modo = ctx["contexto"]["modo"]

    # «Leer metadata Sheets», «Preparar rangos oficiales», «Leer precios oficiales» (PR3).
    try:
        sheets = leer_hojas(n["hojas"])
        # Corrección del 20/11 (campaña de pruebas): el motor recibe las opciones ya ofrecidas.
        res = cotizar(entrada, sheets, _ahora_iso(), _ya_ofrecidas(memoria),
                      cabina_cliente=_cabina_del_turno(contexto.texto_cliente))
    except Exception:
        return _error_de_consulta()

    # «Enviar cotizacion»: solo con modo enviar, mensaje y estado cotizado o parcial.
    mensaje = res.get("mensaje_cotizacion")
    if not (modo == "enviar" and isinstance(mensaje, str) and mensaje and res["estado"] in ("cotizado", "parcial")):
        if modo == "simular":
            return {**res, "envio": {"estado": "simulado"}}
        return resumir_para_agente(res, {"estado": "no_corresponde"}, entrada)

    # «Reservar cotizacion» (PR7).
    solicitud_id = ctx["contexto"]["solicitud_id"]
    try:
        registro = sesion.registro("precios")
        dueno = uuid.uuid4().hex
        previo = registro.get(solicitud_id)
        if previo is None:
            fila = {"account_id": 1, "conversation_id": ctx["contexto"]["conversation_id"],
                    "solicitud_id": solicitud_id, "owner_execution": dueno, "pedido": _copia_json(entrada),
                    "resultado": _como_jsonb(_copia_json(res)), "estado": "reservado",
                    "chatwoot_message_id": None, "motivo": None}
            registro[solicitud_id] = fila
    except Exception:
        return resumir_para_agente(res, {"estado": "desconocido", "motivo": "persistencia_no_confirmada_no_reintentar"},
                                   entrada)

    if previo is not None:
        # «Resolver repeticion».
        compatible = previo.get("pedido") == _copia_json(entrada)
        estado_previo = previo.get("estado")
        # Corrección del 20/11: lo omitido por repetido (cotizacion_ya_enviada) también está resuelto.
        estado = ("omitido" if compatible and estado_previo in ("aceptado", "omitido")
                  else estado_previo if compatible and estado_previo in ("fallido", "control_humano")
                  else "desconocido")
        base = previo["resultado"] if compatible and previo.get("resultado") is not None else res
        return resumir_para_agente(base, {"estado": estado,
                                          "chatwoot_message_id": _texto_bigint(previo.get("chatwoot_message_id")),
                                          "motivo": "solicitud_ya_registrada" if compatible
                                          else "solicitud_ocupada_o_incompatible"}, entrada)

    def registrar(estado, message_id, motivo) -> bool:
        """«Registrar resultado»: solo la misma ejecución y desde reservado o enviando."""
        if fila["owner_execution"] != dueno or fila["estado"] not in ("reservado", "enviando", estado):
            return False
        fila.update({"estado": estado, "chatwoot_message_id": message_id, "motivo": motivo})
        return True

    def devolver_envio(envio: dict) -> dict:
        registrado = registrar(envio["estado"], envio.get("chatwoot_message_id"), envio.get("motivo"))
        return resumir_para_agente(res, {**envio, "registro_confirmado": registrado,
                                         **({} if registrado else {"advertencia": "registro_no_confirmado_no_reintentar"})},
                                   entrada)

    # «Evaluar control humano» (PR8).
    gate = _evaluar_conversacion(sesion.etiquetas)
    if gate["permitido"] and (time.monotonic() - inicio) * 1000 > TOPE_MS:
        gate = {"permitido": False, "estado": "fallido", "motivo": "tiempo_agotado"}
    if not gate["permitido"]:
        # «Bloqueado antes de enviar».
        return devolver_envio({"estado": "control_humano" if gate["estado"] == "control_humano" else "fallido",
                               "motivo": gate["motivo"], "chatwoot_message_id": None})

    # «Marcar inicio del envio».
    if fila["owner_execution"] != dueno or fila["estado"] != "reservado":
        return resumir_para_agente(res, {"estado": "desconocido", "motivo": "persistencia_no_confirmada_no_reintentar"},
                                   entrada)
    fila["estado"] = "enviando"

    # «Vigencia antes de Enviar cotizacion Chatwoot»: el corte por «borrar».
    if not _vigente(contexto, solicitud_id):
        registrado = registrar("control_humano", None, "conversacion_reiniciada")
        return {"estado": "control_humano", "motivo": "conversacion_reiniciada", "pausa_tecnica": True,
                "bot_pausado": None, "asignacion_confirmada": False, "destino": None,
                "envio": {"estado": "control_humano", "motivo": "conversacion_reiniciada", "chatwoot_message_id": None},
                "continuacion_obligatoria": "", "registro_confirmado": registrado, "requiere_revision": not registrado,
                **({} if registrado else {"advertencia": "cierre_de_registro_no_confirmado_no_reintentar"})}

    # Corrección del 20/11 (campaña de pruebas): la misma cotización no se manda dos veces en la
    # conversación. Si el texto es idéntico al de la última aceptada, se omite.
    repetida = _ultima_aceptada(sesion, solicitud_id)
    if repetida is not None and (repetida.get("resultado") or {}).get("mensaje_cotizacion") == mensaje:
        return devolver_envio({"estado": "omitido", "motivo": "cotizacion_ya_enviada",
                               "chatwoot_message_id": repetida.get("chatwoot_message_id")})

    # «Enviar cotizacion Chatwoot» + «Evaluar envio» (PR9): un solo intento.
    try:
        globo = sesion.mandar("cotizacion", mensaje)
        message_id = globo.chatwoot_message_id
        if es_entero_seguro(message_id) and message_id > 0 and globo.texto == mensaje:
            envio = {"estado": "aceptado", "motivo": None, "chatwoot_message_id": message_id}
        else:
            envio = {"estado": "desconocido", "motivo": "respuesta_no_coincide", "chatwoot_message_id": None}
    except Exception:
        envio = {"estado": "desconocido", "motivo": "envio_no_confirmado", "chatwoot_message_id": None}

    # «Registrar resultado» + «Devolver envio» (PR10).
    return devolver_envio(envio)


def reenviar_repetida(contexto: ContextoTurno) -> bool:
    """Manda de nuevo la cotización que este turno omitió por repetida. Devuelve True si salió.

    Corrección del 20/11 (campaña de pruebas): la misma cotización no se manda dos veces cuando
    el turno tiene otra cosa para decirle al cliente. Si iba a quedar en silencio (el cliente
    pidió otra vez el mismo precio), el turno la vuelve a mandar con esta función.
    """
    sesion = contexto.sesion
    solicitud_id = contexto.solicitud_id("precios-v1")
    fila = sesion.registro("precios").get(solicitud_id)
    if (not isinstance(fila, dict) or fila.get("estado") != "omitido"
            or fila.get("motivo") != "cotizacion_ya_enviada"):
        return False
    mensaje = (fila.get("resultado") or {}).get("mensaje_cotizacion")
    if not isinstance(mensaje, str) or not mensaje:
        return False
    if not _evaluar_conversacion(sesion.etiquetas)["permitido"] or not _vigente(contexto, solicitud_id):
        return False
    globo = sesion.mandar("cotizacion", mensaje)
    fila.update({"estado": "aceptado", "chatwoot_message_id": globo.chatwoot_message_id,
                 "motivo": "reenviada_a_pedido"})
    return True
