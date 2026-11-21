"""derivar_humano: el pase a Candela, para la web de pruebas.

Recorre el mismo camino que el subflujo «F7 · Derivar a Candela · v1» en
modo enviar, con la misma lógica (motor.py). Lo que en producción son
Chatwoot y Postgres acá es la SesionLocal:
- la tabla f7_derivaciones es `sesion.registro("derivacion")`;
- las etiquetas de la conversación son `sesion.etiquetas`;
- la confirmación al cliente sale con `sesion.mandar("derivacion", ACK)`.

Abrir la conversación y asignarla al usuario 3 se dan por hechos: en local
no hay bandeja ni usuarios. Tampoco hay corte por «borrar» en el medio
(DE6): en la web el turno no se pisa con otro.

Cómo la usa el principal (P13 y DE10): la llama el modelo con su `motivo`, y
el control de salida, por su cuenta, con `ejecutar("revision_especial",
contexto)`: la misma función, el mismo ContextoTurno y por lo tanto la misma
solicitud_id del turno. El control nunca deriva si en el turno ya hubo
derivar_humano. El tope de 510 s para arrancar un pase es del principal
(en n8n tira «Tiempo insuficiente para iniciar derivación» antes de llamar);
esta función no lo mira.
"""

from __future__ import annotations

import time

from agente.f7.local import ContextoTurno, SesionLocal

from . import motor
from .descripcion import DESCRIPCION_DERIVAR_HUMANO, DESCRIPCION_MOTIVO

NOMBRE = "derivar_humano"
ARGUMENTO = "motivo"
DESCRIPCION = DESCRIPCION_DERIVAR_HUMANO
DESCRIPCION_ARGUMENTO = DESCRIPCION_MOTIVO

SUFIJO_SOLICITUD = "derivacion-v1"
_EN_CURSO = ("reservado", "enviando")


def ejecutar(motivo, contexto: ContextoTurno) -> dict:
    """Pasa la conversación a Candela. Devuelve el objeto que devuelve hoy el subflujo.

    Nunca lanza: cualquier error sale como objeto.
    """
    try:
        return _ejecutar(motivo, contexto)
    except Exception:  # noqa: BLE001 - la herramienta no puede romper el turno
        # Solo en local: en n8n sería un error del nodo. Como «desconocido»,
        # el control de salida no afirma el pase ni reintenta.
        return motor.resultado("desconocido", None, "error_local_no_reintentar")


def _ahora_ms() -> float:
    return time.monotonic() * 1000


def _ejecutar(motivo, contexto: ContextoTurno) -> dict:
    inicio_ms = _ahora_ms()  # «Validar derivacion» guarda inicio_ms
    raw = {
        "motivo": motivo,
        "modo": contexto.modo,
        "account_id": contexto.account_id,
        "conversation_id": contexto.conversation_id,
        "solicitud_id": contexto.solicitud_id(SUFIJO_SOLICITUD),
    }
    entrada = motor.validar_entrada(raw)
    if not entrada["ok"]:
        return motor.resultado_entrada_invalida()
    if entrada["contexto"]["modo"] == "simular":
        return motor.resultado_simulacion()

    ctx = entrada["contexto"]
    sesion = contexto.sesion
    registro = sesion.registro("derivacion")
    sid = ctx["solicitud_id"]

    # DE2: reservar (una sola en curso por conversación).
    fila = _reservar(registro, sid, entrada["motivo"])
    if not fila["acquired"]:
        return motor.resolver_repeticion(fila)

    # En local la conversación arranca abierta y sin asignar.
    chat = {"status": "open", "assignee_id": None}

    # DE3: lectura inicial.
    inicio = motor.evaluar_inicio(_leer(sesion, chat), ctx)
    if not inicio["continuar"]:
        return _registrar(registro, sid, inicio["resultado"])
    iniciales = inicio["verificacion"]["labels"]

    # DE4.1: «humano» conservando las demás etiquetas.
    sesion.etiquetas[:] = inicio["labels"]
    etapa = _etapa(sesion, chat, ctx, "pausa", iniciales, inicio_ms)
    if not etapa["continuar"]:
        return _registrar(registro, sid, etapa["resultado"])

    # DE4.2: abrir.
    chat["status"] = "open"
    etapa = _etapa(sesion, chat, ctx, "apertura", iniciales, inicio_ms)
    if not etapa["continuar"]:
        return _registrar(registro, sid, etapa["resultado"])

    # DE4.3: asignar a Candela (usuario 3).
    chat["assignee_id"] = motor.DESTINO_ID
    decision = motor.decidir_confirmacion(_leer(sesion, chat), ctx, iniciales, inicio_ms, _ahora_ms())
    if not decision["enviar_ack"]:
        return _registrar(registro, sid, decision["resultado"])

    # DE5: marcar «enviando», revalidar y mandar una única confirmación.
    registro[sid].update(estado="enviando", resultado=motor.como_jsonb(decision["resultado"]))
    revalidacion = motor.decidir_confirmacion(_leer(sesion, chat), ctx, iniciales, inicio_ms, _ahora_ms())
    if not revalidacion["enviar_ack"]:
        return _registrar(registro, sid, revalidacion["resultado"])

    globo = sesion.mandar("derivacion", motor.ACK)
    envio = motor.evaluar_ack(_respuesta_mensaje(sesion, globo), ctx)
    final = {**revalidacion["resultado"], "envio": envio, "requiere_revision": envio["estado"] != "aceptado"}
    return _registrar(registro, sid, final)


def _reservar(registro: dict, sid: str, motivo: str) -> dict:
    """La consulta «Reservar derivacion» sobre el registro en memoria."""
    choca = sid in registro or any(f.get("estado") in _EN_CURSO for f in registro.values())
    if not choca:
        registro[sid] = {"motivo": motivo, "estado": "reservado", "resultado": None}
        return {"acquired": True, "compatible": True, "estado": "reservado", "resultado": None}
    if sid in registro:
        sid_existente = sid
    else:
        sid_existente = next(k for k, f in registro.items() if f.get("estado") in _EN_CURSO)
    existente = registro[sid_existente]
    return {
        "acquired": False,
        "compatible": existente.get("motivo") == motivo and sid_existente == sid,
        "estado": existente.get("estado"),
        "resultado": existente.get("resultado"),
    }


def _registrar(registro: dict, sid: str, resultado: dict) -> dict:
    """«Registrar resultado de derivacion» + «Devolver resultado registrado»."""
    registro[sid].update(estado="finalizado", resultado=motor.como_jsonb(resultado))
    return {**resultado, "registro_confirmado": True}


def _leer(sesion: SesionLocal, chat: dict) -> dict:
    """Lo que devolvería el GET de la conversación en Chatwoot."""
    return {
        "statusCode": 200,
        "body": {
            "id": sesion.conversation_id,
            "account_id": 1,
            "labels": list(sesion.etiquetas),
            "status": chat["status"],
            "can_reply": True,
            "meta": {"assignee": {"id": chat["assignee_id"]} if chat["assignee_id"] is not None else None},
        },
    }


def _etapa(sesion, chat, ctx, etapa, iniciales, inicio_ms) -> dict:
    """«Evaluar pausa» y «Evaluar apertura», con su corte a los 140 s."""
    r = motor.evaluar_etapa(_leer(sesion, chat), ctx, etapa, iniciales)
    if r["continuar"] and _ahora_ms() - inicio_ms > 140000:
        r = {"continuar": False, "resultado": motor.resultado("parcial", r["verificacion"], "tiempo_agotado")}
    return r


def _respuesta_mensaje(sesion: SesionLocal, globo) -> dict:
    """Lo que devolvería Chatwoot al aceptar el mensaje de confirmación."""
    return {
        "statusCode": 200,
        "body": {
            "id": globo.chatwoot_message_id,
            "content": globo.texto,
            "account_id": 1,
            "conversation_id": sesion.conversation_id,
            "message_type": 1,
            "private": False,
            "status": "sent",
            "content_attributes": {},
        },
    }
