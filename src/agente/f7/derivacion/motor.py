"""Lógica pura de la derivación a Candela, portada tal cual de n8n.

Fuente: el código de los nodos del subflujo publicado «F7 · Derivar a
Candela · v1» (referencia-f7/n8n/herramienta-derivacion-v1.json), que es el
mismo que referencia-f7/logica/derivacion/motor.mjs. Sin red ni secretos.

Las respuestas de Chatwoot llegan acá con la forma que les da n8n:
{"statusCode": 200, "body": {...}} o {"error": {...}}.

Comparaciones de JS que importan: `===` no confunde True con 1, y los
números enteros pueden venir como float (5.0 === 5 en JS).
"""

from __future__ import annotations

import json
import math
import re

DESTINO_ID = 3  # Mateo confirmó: Candela usa la cuenta Melanie (05/11/2026).
MOTIVOS = ["avance_compra", "pago", "turno", "persona", "posventa", "revision_especial"]
ACK = "La conversación quedó asignada a Candela para continuar con tu consulta."
ERROR_PASE = "No pude completar el pase a Candela."

_MAX_SEGURO = 2**53 - 1
_SOLICITUD = re.compile(r"^cw:1:[1-9]\d*:[1-9]\d{0,31}:derivacion-v1\Z", re.ASCII)
_CLAVES_ENTRADA = ("motivo", "modo", "account_id", "conversation_id", "solicitud_id")
_FALTA = object()

# Lo que String.prototype.trim de JS considera espacio.
_ESPACIOS_JS = (
    "\t\n\x0b\x0c\r \xa0        "
    "        　﻿"
)
_NUMERO_JS = re.compile(r"[+-]?(?:\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)", re.ASCII)


# ---------------------------------------------------------------- ayudas JS

def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _igual(a, b) -> bool:
    """`a === b` de JS para valores JSON."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _es_numero(a) and _es_numero(b):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if a is None and b is None:
        return True
    return a is b


def _incluye(lista, v) -> bool:
    """`lista.includes(v)` de JS."""
    return any(_igual(x, v) for x in lista)


def _verdad(v) -> bool:
    """Si `v` es «truthy» en JS ({} y [] lo son; NaN no)."""
    if v is None or v is False:
        return False
    if _es_numero(v):
        return not (v == 0 or (isinstance(v, float) and math.isnan(v)))
    if isinstance(v, str):
        return v != ""
    return True


def _prop(o, clave):
    """`o?.clave` de JS sobre JSON: None si no hay objeto o no está la clave."""
    return o.get(clave) if isinstance(o, dict) else None


def _plano(v) -> bool:
    return isinstance(v, dict)


def _entero_seguro(v) -> bool:
    """Number.isSafeInteger."""
    if not _es_numero(v):
        return False
    if isinstance(v, float) and (not math.isfinite(v) or not v.is_integer()):
        return False
    return abs(v) <= _MAX_SEGURO


def _positivo(v) -> bool:
    return _entero_seguro(v) and v > 0


def _numero(v) -> float:
    """Number(v) de JS para valores JSON (lo que no sabe convertir da NaN)."""
    if v is None:
        return math.nan
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if _es_numero(v):
        return float(v)
    if isinstance(v, str):
        s = v.strip(_ESPACIOS_JS)
        if s == "":
            return 0.0
        if s in ("Infinity", "+Infinity"):
            return math.inf
        if s == "-Infinity":
            return -math.inf
        if _NUMERO_JS.fullmatch(s):
            return float(s)
        for prefijo, base in (("0x", 16), ("0o", 8), ("0b", 2)):
            if s[:2].lower() == prefijo:
                try:
                    return float(int(s[2:], base)) if re.fullmatch(r"[0-9a-fA-F]+", s[2:], re.ASCII) else math.nan
                except ValueError:
                    return math.nan
        return math.nan
    return math.nan


def _primero(*valores):
    """`a ?? b ?? c` de JS (None hace de null y de undefined)."""
    for v in valores:
        if v is not None:
            return v
    return None


def _http_status(r) -> int | None:
    e = _prop(r, "error")
    n = _numero(_primero(
        _prop(r, "statusCode"),
        _prop(e, "statusCode"),
        _prop(e, "httpCode"),
        _prop(_prop(e, "response"), "status"),
    ))
    if math.isfinite(n) and n.is_integer() and 100 <= n <= 599:
        return int(n)
    return None


def _trim(s: str) -> str:
    return s.strip(_ESPACIOS_JS)


def _texto_numero(v) -> str:
    """`${v}` de JS para un entero seguro."""
    return str(int(v))


# ------------------------------------------------------------------ motor

def resultado(estado, verificacion=None, motivo=None, envio=_FALTA) -> dict:
    """El objeto base que ve el modelo (DE7)."""
    if envio is _FALTA:
        envio = {"estado": "no_corresponde"}
    verificada = _prop(verificacion, "verificada") is True
    pausado = verificacion.get("bot_pausado") if verificada else None
    asignado = (
        verificada
        and pausado is True
        and verificacion.get("abierta") is True
        and _igual(verificacion.get("assignee_id"), DESTINO_ID)
    )
    return {
        "estado": estado,
        "bot_pausado": pausado,
        "asignacion_confirmada": asignado,
        "destino": {"id": DESTINO_ID, "nombre": "Candela", "cuenta_chatwoot": "Melanie"} if asignado else None,
        "envio": envio,
        "motivo": motivo,
        "requiere_revision": estado in ("fallido", "parcial", "desconocido", "pendiente_asignacion"),
        "continuacion_obligatoria": "",
    }


def validar_entrada(raw) -> dict:
    """DE1: solo {motivo, modo, account_id, conversation_id, solicitud_id}."""
    if not _plano(raw) or not _incluye(MOTIVOS, raw.get("motivo")) or not _incluye(["simular", "enviar"], raw.get("modo")):
        return {"ok": False}
    if any(k not in _CLAVES_ENTRADA for k in raw):
        return {"ok": False}
    if raw["modo"] == "simular":
        return {"ok": True, "motivo": raw["motivo"], "contexto": {"modo": "simular"}}
    conv = raw.get("conversation_id")
    sid = raw.get("solicitud_id")
    if not _igual(raw.get("account_id"), 1) or not _positivo(conv) or not isinstance(sid, str):
        return {"ok": False}
    if not _SOLICITUD.match(sid) or not sid.startswith(f"cw:1:{_texto_numero(conv)}:"):
        return {"ok": False}
    return {
        "ok": True,
        "motivo": raw["motivo"],
        "contexto": {"modo": "enviar", "account_id": 1, "conversation_id": conv, "solicitud_id": sid},
    }


def leer_conversacion(response, contexto) -> dict:
    """Verifica la lectura de la conversación (GET de Chatwoot)."""

    def invalida(motivo):
        return {"verificada": False, "motivo": motivo}

    if not _igual(_prop(contexto, "account_id"), 1) or not _positivo(_prop(contexto, "conversation_id")):
        return invalida("contexto_invalido")
    status = _http_status(response)
    b = _prop(response, "body")
    if not status or status < 200 or status >= 300 or _verdad(_prop(response, "error")):
        return invalida("conversacion_no_verificable")
    if (
        not _plano(b)
        or not _igual(b.get("id"), contexto["conversation_id"])
        or ("account_id" in b and not _igual(b["account_id"], 1))
    ):
        return invalida("identidad_no_coincide")
    labels = b.get("labels")
    if not isinstance(labels, list) or any(not isinstance(l, str) for l in labels):
        return invalida("labels_no_verificables")
    assignee = _primero(_prop(_prop(b.get("meta"), "assignee"), "id"), b.get("assignee_id"))
    if assignee is not None and not _positivo(assignee):
        return invalida("asignacion_no_verificable")
    if not _incluye(["open", "pending", "resolved", "snoozed"], b.get("status")):
        return invalida("estado_no_verificable")
    return {
        "verificada": True,
        "bot_pausado": any(_trim(l).lower() == "humano" for l in labels),
        "labels": list(labels),
        "abierta": b["status"] == "open",
        "status": b["status"],
        "can_reply": b.get("can_reply") is True,
        "assignee_id": assignee,
        "motivo": None,
    }


def evaluar_inicio(response, contexto) -> dict:
    """DE3: lectura inicial. Con «humano» ya puesto no se toca nada."""
    v = leer_conversacion(response, contexto)
    if not v["verificada"]:
        return {"continuar": False, "resultado": {**resultado("fallido", None, v["motivo"]), "continuacion_obligatoria": ERROR_PASE}}
    if v["bot_pausado"]:
        return {"continuar": False, "resultado": resultado("control_humano", v, "conversacion_ya_tomada")}
    return {"continuar": True, "verificacion": v, "labels": list(dict.fromkeys([*v["labels"], "humano"]))}


def evaluar_etapa(response, contexto, etapa, labels_iniciales=()) -> dict:
    """DE4: verificación después de pausar, abrir o asignar."""
    v = leer_conversacion(response, contexto)
    if not v["verificada"]:
        return {"continuar": False, "resultado": resultado("desconocido", None, v["motivo"])}
    if not v["bot_pausado"]:
        return {"continuar": False, "resultado": resultado("fallido", v, "pausa_no_confirmada")}
    if not all(l in v["labels"] for l in labels_iniciales):
        return {"continuar": False, "resultado": resultado("parcial", v, "etiquetas_originales_no_confirmadas")}
    if etapa != "pausa" and not v["abierta"]:
        return {"continuar": False, "resultado": resultado("parcial", v, "apertura_no_confirmada")}
    if etapa == "asignacion" and not _igual(v["assignee_id"], DESTINO_ID):
        return {"continuar": False, "resultado": resultado("pendiente_asignacion", v, "destino_no_confirmado")}
    return {"continuar": True, "verificacion": v}


def decidir_confirmacion(response, contexto, labels_iniciales, inicio_ms, ahora_ms) -> dict:
    """DE5: si corresponde mandar la confirmación (140 s como máximo)."""
    etapa = evaluar_etapa(response, contexto, "asignacion", labels_iniciales)
    if not etapa["continuar"]:
        return {"enviar_ack": False, "resultado": etapa["resultado"]}
    v = etapa["verificacion"]
    tiempo = (
        _es_numero(inicio_ms) and math.isfinite(inicio_ms)
        and _es_numero(ahora_ms) and math.isfinite(ahora_ms)
        and ahora_ms >= inicio_ms and ahora_ms - inicio_ms <= 140000
    )
    enviar_ack = v["can_reply"] and tiempo
    motivo = None if enviar_ack else ("ventana_no_habilitada" if not v["can_reply"] else "tiempo_agotado")
    return {
        "enviar_ack": enviar_ack,
        "verificacion": v,
        "resultado": resultado("derivado", v, motivo, {"estado": "no_corresponde", "motivo": motivo}),
    }


def evaluar_ack(response, contexto) -> dict:
    """DE5: cómo terminó el POST de la confirmación."""

    def incierto(motivo):
        return {"estado": "desconocido", "motivo": motivo, "chatwoot_message_id": None}

    if not _igual(_prop(contexto, "account_id"), 1) or not _positivo(_prop(contexto, "conversation_id")):
        return incierto("contexto_invalido")
    status = _http_status(response)
    if status is not None and 400 <= status < 500 and status != 408:
        return {"estado": "fallido", "motivo": f"http_{status}", "chatwoot_message_id": None}
    if not status or status < 200 or status >= 300 or _verdad(_prop(response, "error")):
        return incierto("confirmacion_no_verificable")
    b = _prop(response, "body")
    if (
        not _plano(b)
        or not _positivo(b.get("id"))
        or not _igual(b.get("conversation_id"), contexto["conversation_id"])
        or ("account_id" in b and not _igual(b["account_id"], 1))
        or not _incluye([1, "outgoing"], b.get("message_type"))
        or b.get("private", _FALTA) is not False
        or not _igual(b.get("content"), ACK)
    ):
        return incierto("respuesta_no_coincide")
    if _igual(b.get("status"), "failed") or _igual(b.get("status"), 3) or _verdad(_prop(b.get("content_attributes"), "external_error")):
        return {"estado": "fallido", "motivo": "canal_rechazo_envio", "chatwoot_message_id": b["id"]}
    return {"estado": "aceptado", "motivo": None, "chatwoot_message_id": b["id"]}


def resolver_repeticion(row) -> dict:
    """DE2: la solicitud ya estaba registrada (o hay otra en curso)."""
    if _prop(row, "compatible") is not True:
        return {**resultado("entrada_invalida", None, "solicitud_incompatible"), "repetido": True}
    previo = row.get("resultado")
    if _igual(row.get("estado"), "finalizado") and _plano(previo):
        r = dict(previo)
        r["repetido"] = True
        r["verificacion"] = "ejecucion_original"
        envio = previo.get("envio", _FALTA)
        if _igual(_prop(envio, "estado"), "aceptado"):
            r["envio"] = {**envio, "estado": "omitido"}
        elif envio is not _FALTA:
            r["envio"] = envio
        r["continuacion_obligatoria"] = ""
        return r
    en_vuelo = "desconocido" if _igual(row.get("estado"), "enviando") else "no_corresponde"
    return {**resultado("desconocido", None, "solicitud_en_curso_o_incierta", {"estado": en_vuelo}), "repetido": True}


def resultado_simulacion() -> dict:
    """DE12: modo simular, sin efectos (el principal nunca lo usa)."""
    return {
        **resultado("simulado", None, None, {"estado": "simulado"}),
        "destino_previsto": {"id": 3, "nombre": "Candela", "cuenta_chatwoot": "Melanie"},
        "acciones_previstas": [
            "preservar_labels_y_agregar_humano",
            "abrir_conversacion",
            "asignar_usuario_3",
            "verificar",
            "confirmar_si_can_reply",
        ],
        "confirmacion_prevista": ACK,
    }


def resultado_entrada_invalida() -> dict:
    """Nodo «Entrada invalida»."""
    return {**resultado("entrada_invalida", None, "motivo_o_contexto_invalido"), "continuacion_obligatoria": ERROR_PASE}


def como_jsonb(valor):
    """Lo que devuelve Postgres al leer un jsonb: claves por largo y después por bytes.

    El resultado repetido sale de la fila guardada, así que en producción llega
    con este orden.
    """
    if isinstance(valor, dict):
        claves = sorted(valor, key=lambda k: (len(k.encode("utf-8")), k.encode("utf-8")))
        return {k: como_jsonb(valor[k]) for k in claves}
    if isinstance(valor, list):
        return [como_jsonb(v) for v in valor]
    return json.loads(json.dumps(valor))
