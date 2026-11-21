"""derivar_humano (pase a Candela) en la web de pruebas. Sin red ni gasto.

Los resultados esperados salen de comparar con el código del subflujo de n8n
(«F7 · Derivar a Candela · v1») corrido en Node con las mismas entradas.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente.f7 import derivacion  # noqa: E402
from agente.f7.derivacion import motor  # noqa: E402
from agente.f7.local import ContextoTurno, SesionLocal  # noqa: E402

ACK = "La conversación quedó asignada a Candela para continuar con tu consulta."
CANDELA = {"id": 3, "nombre": "Candela", "cuenta_chatwoot": "Melanie"}


def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _turno(etiquetas=(), ultimo=9, conversacion=5):
    sesion = SesionLocal(conversation_id=conversacion, etiquetas=list(etiquetas))
    return sesion, ContextoTurno(sesion=sesion, ultimo_message_id=ultimo)


def test_contrato_y_textos():
    assert derivacion.NOMBRE == "derivar_humano"
    assert derivacion.ARGUMENTO == "motivo"
    assert motor.ACK == ACK
    assert motor.ERROR_PASE == "No pude completar el pase a Candela."
    assert derivacion.DESCRIPCION.startswith("Pasa la conversación actual a Candela, que usa la cuenta Melanie en Chatwoot.")
    assert derivacion.DESCRIPCION.count("\n") == 3
    assert derivacion.DESCRIPCION.endswith("Ante error sin resultado, no afirmes el pase ni reintentes.")
    assert derivacion.DESCRIPCION_ARGUMENTO == (
        "Motivo de intervención solicitado por el cliente. Elegí exactamente uno: avance_compra, pago, turno, "
        "persona, posventa o revision_especial. No incluyas destinatarios, texto ni otros datos."
    )


def test_motivo_invalido_no_toca_nada():
    for motivo in ("otro", "Pago", " pago", "", None, 1):
        sesion, ctx = _turno(["cliente"])
        r = derivacion.ejecutar(motivo, ctx)
        assert _json(r) == (
            '{"estado":"entrada_invalida","bot_pausado":null,"asignacion_confirmada":false,"destino":null,'
            '"envio":{"estado":"no_corresponde"},"motivo":"motivo_o_contexto_invalido","requiere_revision":false,'
            '"continuacion_obligatoria":"No pude completar el pase a Candela."}'
        )
        assert sesion.etiquetas == ["cliente"]
        assert sesion.salientes == []
        assert sesion.registro("derivacion") == {}


def test_solicitud_sin_mensaje_es_entrada_invalida():
    # Sin un message_id válido la solicitud_id no cumple la regex (en n8n el principal ni llama).
    sesion, ctx = _turno(ultimo=0)
    assert derivacion.ejecutar("pago", ctx)["estado"] == "entrada_invalida"
    assert sesion.salientes == []


def test_derivacion_ok():
    sesion, ctx = _turno(["cliente", "vip"])
    r = derivacion.ejecutar("persona", ctx)
    assert sesion.etiquetas == ["cliente", "vip", "humano"]
    assert len(sesion.salientes) == 1
    globo = sesion.salientes[0]
    assert globo.tipo == "derivacion"
    assert globo.texto == ACK
    assert _json(r) == (
        '{"estado":"derivado","bot_pausado":true,"asignacion_confirmada":true,'
        '"destino":{"id":3,"nombre":"Candela","cuenta_chatwoot":"Melanie"},'
        '"envio":{"estado":"aceptado","motivo":null,"chatwoot_message_id":%d},'
        '"motivo":null,"requiere_revision":false,"continuacion_obligatoria":"","registro_confirmado":true}'
        % globo.chatwoot_message_id
    )
    fila = sesion.registro("derivacion")["cw:1:5:9:derivacion-v1"]
    assert fila["estado"] == "finalizado" and fila["motivo"] == "persona"


def test_etiquetas_repetidas_se_unifican():
    sesion, ctx = _turno(["cliente", "cliente"])
    assert derivacion.ejecutar("turno", ctx)["estado"] == "derivado"
    assert sesion.etiquetas == ["cliente", "humano"]


def test_ya_tomada_no_toca_nada():
    # «humano» sin mayúsculas ni espacios (trim de JS: ﻿ sí, \x1c no).
    for etiquetas in (["vip", "humano"], [" Humano "], ["HUMANO﻿"]):
        sesion, ctx = _turno(etiquetas)
        r = derivacion.ejecutar("pago", ctx)
        assert r == {
            "estado": "control_humano",
            "bot_pausado": True,
            "asignacion_confirmada": False,
            "destino": None,
            "envio": {"estado": "no_corresponde"},
            "motivo": "conversacion_ya_tomada",
            "requiere_revision": False,
            "continuacion_obligatoria": "",
            "registro_confirmado": True,
        }
        assert sesion.etiquetas == etiquetas
        assert sesion.salientes == []
    sesion, ctx = _turno(["\x1chumano"])
    assert derivacion.ejecutar("pago", ctx)["estado"] == "derivado"


def test_repetida_devuelve_el_original():
    sesion, ctx = _turno(["cliente"])
    primero = derivacion.ejecutar("pago", ctx)
    id_original = primero["envio"]["chatwoot_message_id"]
    sesion.salientes.clear()
    r = derivacion.ejecutar("pago", ctx)
    assert sesion.salientes == []  # no se reenvía la confirmación
    assert sesion.etiquetas == ["cliente", "humano"]
    # Viene de la fila guardada: orden de claves de jsonb, como en producción.
    assert _json(r) == (
        '{"envio":{"estado":"omitido","motivo":null,"chatwoot_message_id":%d},"estado":"derivado","motivo":null,'
        '"destino":{"id":3,"nombre":"Candela","cuenta_chatwoot":"Melanie"},"bot_pausado":true,'
        '"requiere_revision":false,"asignacion_confirmada":true,"continuacion_obligatoria":"",'
        '"repetido":true,"verificacion":"ejecucion_original"}' % id_original
    )
    assert r["destino"] == CANDELA


def test_misma_solicitud_con_otro_motivo_es_incompatible():
    sesion, ctx = _turno()
    derivacion.ejecutar("pago", ctx)
    sesion.salientes.clear()
    r = derivacion.ejecutar("revision_especial", ctx)
    assert r["estado"] == "entrada_invalida"
    assert r["motivo"] == "solicitud_incompatible"
    assert r["repetido"] is True
    assert r["continuacion_obligatoria"] == ""
    assert sesion.salientes == []


def test_otra_solicitud_mientras_hay_una_en_curso():
    sesion, ctx = _turno(ultimo=12)
    sesion.registro("derivacion")["cw:1:5:9:derivacion-v1"] = {"motivo": "pago", "estado": "enviando", "resultado": None}
    r = derivacion.ejecutar("pago", ctx)
    assert r["estado"] == "entrada_invalida" and r["motivo"] == "solicitud_incompatible" and r["repetido"] is True
    assert sesion.etiquetas == [] and sesion.salientes == []


def test_misma_solicitud_en_curso_es_desconocido():
    sesion, ctx = _turno()
    sesion.registro("derivacion")["cw:1:5:9:derivacion-v1"] = {"motivo": "pago", "estado": "enviando", "resultado": None}
    r = derivacion.ejecutar("pago", ctx)
    assert _json(r) == (
        '{"estado":"desconocido","bot_pausado":null,"asignacion_confirmada":false,"destino":null,'
        '"envio":{"estado":"desconocido"},"motivo":"solicitud_en_curso_o_incierta","requiere_revision":true,'
        '"continuacion_obligatoria":"","repetido":true}'
    )


def test_turno_siguiente_deriva_de_nuevo_si_sacaron_humano():
    sesion, ctx = _turno()
    derivacion.ejecutar("pago", ctx)
    sesion.etiquetas.remove("humano")
    sesion.salientes.clear()
    r = derivacion.ejecutar("avance_compra", ContextoTurno(sesion=sesion, ultimo_message_id=20))
    assert r["estado"] == "derivado" and [g.texto for g in sesion.salientes] == [ACK]


def test_simular_no_toca_nada():
    sesion = SesionLocal()
    ctx = ContextoTurno(sesion=sesion, ultimo_message_id=9, modo="simular")
    r = derivacion.ejecutar("persona", ctx)
    assert r["estado"] == "simulado" and r["confirmacion_prevista"] == ACK and r["destino_previsto"] == CANDELA
    assert sesion.etiquetas == [] and sesion.salientes == [] and sesion.registros == {}


def test_motor_casos_de_la_comparacion_con_js():
    ctx = {"modo": "enviar", "account_id": 1, "conversation_id": 5}
    # Status como texto («200») vale; 200.5 no; error {} es «truthy» en JS.
    cuerpo = {"id": 5, "labels": [], "status": "open"}
    assert motor.leer_conversacion({"statusCode": "200", "body": cuerpo}, ctx)["verificada"] is True
    assert motor.leer_conversacion({"statusCode": 200.5, "body": cuerpo}, ctx)["motivo"] == "conversacion_no_verificable"
    assert motor.leer_conversacion({"statusCode": 200, "error": {}, "body": cuerpo}, ctx)["motivo"] == "conversacion_no_verificable"
    # True no es 5 en JS.
    assert motor.leer_conversacion({"statusCode": 200, "body": {**cuerpo, "id": True}}, ctx)["motivo"] == "identidad_no_coincide"
    # Regex con $ de JS: un salto de línea final no pasa.
    raw = {"motivo": "pago", "modo": "enviar", "account_id": 1, "conversation_id": 5}
    assert motor.validar_entrada({**raw, "solicitud_id": "cw:1:5:9:derivacion-v1\n"}) == {"ok": False}
    assert motor.validar_entrada({**raw, "solicitud_id": "cw:1:5:٣:derivacion-v1"}) == {"ok": False}
    assert motor.validar_entrada({**raw, "solicitud_id": "cw:1:5:" + "1" * 33 + ":derivacion-v1"}) == {"ok": False}
    assert motor.validar_entrada({**raw, "conversation_id": 5.0, "solicitud_id": "cw:1:5:9:derivacion-v1"})["ok"] is True
    # Ack: 404 es fallido; un texto distinto es desconocido.
    ack = {"id": 11, "conversation_id": 5, "message_type": 1, "private": False, "content": ACK}
    assert motor.evaluar_ack({"statusCode": 404}, ctx)["motivo"] == "http_404"
    assert motor.evaluar_ack({"statusCode": 200, "body": {**ack, "content": ACK + " "}}, ctx)["motivo"] == "respuesta_no_coincide"
    assert motor.evaluar_ack({"statusCode": 200, "body": {**ack, "status": "failed"}}, ctx) == {
        "estado": "fallido", "motivo": "canal_rechazo_envio", "chatwoot_message_id": 11}
    # Sin can_reply: derivado sin mensaje.
    r = motor.decidir_confirmacion(
        {"statusCode": 200, "body": {"id": 5, "labels": ["humano"], "status": "open", "assignee_id": 3}}, ctx, [], 0, 1)
    assert r["enviar_ack"] is False
    assert r["resultado"]["envio"] == {"estado": "no_corresponde", "motivo": "ventana_no_habilitada"}
