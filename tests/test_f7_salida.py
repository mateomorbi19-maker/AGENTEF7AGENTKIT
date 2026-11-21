"""Control de salida comercial de F7 (P13) y nota de cotización en la memoria (P14).

Los resultados esperados salen de correr el código del nodo de n8n con node.
Sin red ni gasto. Los importes son inventados.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente.f7.salida import (  # noqa: E402
    ErrorDeSalida,
    contiene_importe,
    controlar_salida_comercial,
    memoria_cotizacion_confirmada,
    reparar_memoria_comercial,
    requiere_revision_comercial,
    salida_comercial_confirmada,
    solicitud_humana_explicita,
    texto_para_memoria,
    verificar_memoria_comercial,
)


def paso(tool, observation):
    return {"action": {"tool": tool, "toolInput": {}}, "observation": observation}


def cotizacion(**cambios):
    r = {
        "estado": "cotizado",
        "cotizacion_enviada": True,
        "envio": {"estado": "aceptado", "chatwoot_message_id": 55},
        "items": [{"producto": "fundas", "modelo": "Suran", "configuracion": "5 plazas", "cantidad": 1, "estado": "cotizado"}],
        "metodo_pago": "transferencia",
        "continuacion_obligatoria": "",
    }
    r.update(cambios)
    return r


def control(output, pasos=(), cliente="hola"):
    return controlar_salida_comercial({"output": output, "intermediateSteps": list(pasos)}, texto_cliente=cliente)


# ---------------------------------------------------------------- pausa y derivación


def test_pausa_por_resultado_calla_y_pausa():
    s = control("Ya te mandé las fotos", [paso("enviar_multimedia", {"estado": "control_humano"})])
    assert s == {
        "output": "",
        "requiere_derivacion": False,
        "bot_pausado": True,
        "estado": "control_humano",
        "control_salida": {
            "motivo": "control_humano", "modificada": True, "importe_modelo_bloqueado": False,
            "resultado_incierto": False, "faq_pendientes": [], "faq_preservadas": [],
            "bot_pausado": True, "estado": "control_humano",
        },
    }


def test_pausa_con_observacion_como_string_json():
    s = control("hola", [paso("buscar_precio", json.dumps({"envio": {"estado": "control_humano"}}))])
    assert s["bot_pausado"] is True and s["estado"] == "control_humano"


@pytest.mark.parametrize("estado", ["pendiente_asignacion", "parcial", "fallido", "desconocido", "simulado", "entrada_invalida"])
def test_derivar_humano_sale_la_continuacion(estado):
    s = control("Te paso con Candela!!", [paso("derivar_humano", {"estado": estado, "continuacion_obligatoria": "Te derivo"})])
    assert s["output"] == "Te derivo"
    assert s["requiere_derivacion"] is False
    assert s["control_salida"]["motivo"] == "resultado_derivacion"
    assert s["control_salida"]["resultado_incierto"] is (estado != "simulado")


def test_derivar_humano_fuera_de_contrato():
    s = control("x", [paso("derivar_humano", {"estado": "raro"})])
    assert s["output"] == "No pude confirmar el pase. Esa parte necesita revisión del equipo."
    assert s["estado"] == "raro" and s["control_salida"]["resultado_incierto"] is True


def test_debito_metodo_no_confirmado_deriva():
    r = cotizacion(estado="metodo_no_confirmado", requiere_derivacion="revision_especial", envio={"estado": "no_corresponde"})
    s = control("Te consulto", [paso("buscar_precio", r)])
    assert (s["output"], s["requiere_derivacion"], s["control_salida"]["motivo"]) == ("", True, "revision_especial")


# ---------------------------------------------------------------- pedido humano explícito


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("pasame el alias", "pago"),
        ("ya pagué", "pago"),
        ("quiero pagar", "pago"),
        ("quiero pagar en efectivo cuanto sale?", None),
        ("quiero pagar ya en efectivo cuanto sale", "pago"),
        ("ya la mande, me confirmas si llego", "pago"),
        ("quiero hablar con una persona", "persona"),
        ("QUIERO HABLAR CON UNA PERSONA", "persona"),
        ("quiero hablar con candela", "persona"),
        ("quiero un turno", "turno"),
        ("necesito reservar", "reserva"),
        ("me la cambian? se rompio", "posventa"),
        # La coma parte la frase: el «no» queda en otra parte (igual que en n8n).
        ("no, ya pagué", "pago"),
        ("no ya pagué", None),
        ("si quiero pagar", None),
        ("quizás quiero hablar con alguien", None),
        ('"quiero hablar con alguien"', None),
        ("tal vez quiero un turno", None),
        ("hola", None),
    ],
)
def test_solicitud_humana_explicita(texto, esperado):
    assert solicitud_humana_explicita(texto) == esperado


def test_pedido_humano_calla_y_deriva():
    s = control("Claro, te paso con alguien", cliente="quiero hablar con una persona")
    assert s["output"] == "" and s["requiere_derivacion"] is True
    assert s["control_salida"]["motivo"] == "solicitud_humana_no_atendida"
    assert s["control_salida"]["solicitud_humana_detectada"] == "persona"


# ---------------------------------------------------------------- buscar_precio


def test_cotizado_descarta_texto_libre_y_deja_nota_de_memoria():
    s = control("Te paso el presupuesto", [paso("buscar_precio", cotizacion())], cliente="precio fundas suran")
    assert s["output"] == "" and s["requiere_derivacion"] is False
    assert s["control_salida"]["motivo"] == "continuacion_de_herramienta"
    assert s["memoria_output"] == (
        '[Registro interno de cotización confirmada] {"herramienta":"buscar_precio","estado":"cotizado",'
        '"situacion":"aceptada_por_chatwoot","items":[{"producto":"fundas","modelo":"Suran",'
        '"configuracion":"5 plazas","cantidad":1,"estado":"cotizado"}],"metodo_pago":"transferencia"}'
    )


def test_faq_literal_preguntada_sale_con_la_continuacion():
    raw = "Te esperamos de lunes a viernes de 9 a 18 hs y sábado de 9 a 14 hs. Además te hago un descuento"
    r = cotizacion(continuacion_obligatoria="Cualquier consulta avisame", envio={"estado": "omitido", "chatwoot_message_id": 7})
    s = control(raw, [paso("buscar_precio", r)], cliente="que horario tienen? y garantia?")
    assert s["output"] == "Te esperamos de lunes a viernes de 9 a 18 hs y sábado de 9 a 14 hs\n\nCualquier consulta avisame"
    assert s["control_salida"]["faq_preservadas"] == ["horario"]
    assert s["control_salida"]["faq_pendientes"] == ["garantia"]
    assert '"situacion":"ya_aceptada_por_chatwoot"' in s["memoria_output"]


def test_faq_de_producto_solo_con_ese_producto():
    raw = "La confección aproximada es de 5 días hábiles desde la seña."
    r = cotizacion(items=[{"producto": "tipo tapizado", "cantidad": 1, "estado": "cotizado"}])
    s = control(raw, [paso("buscar_precio", r)], cliente="cuanto tarda la confeccion?")
    assert s["output"] == "" and s["control_salida"]["faq_pendientes"] == ["demora"]


def test_precio_fuera_de_contrato():
    s = control("Sale 1200", [paso("buscar_precio", {"estado": "cotizado", "envio": {"estado": "aceptado"}})])
    assert s["output"] == "No pude confirmar el resultado de la consulta de precios. Esa parte necesita revisión del equipo."
    assert s["control_salida"]["motivo"] == "precio_sin_contrato"
    assert s["control_salida"]["importe_modelo_bloqueado"] is True


@pytest.mark.parametrize(
    "cambios",
    [
        {"cotizacion_enviada": False},
        {"envio": {"estado": "fallido", "chatwoot_message_id": 55}},
        {"envio": {"estado": "aceptado", "chatwoot_message_id": 0}},
        {"metodo_pago": "debito"},
        {"metodo_pago": None},
        {"pregunta_comercial_incluida": "si"},
        {"items": [{"producto": "fundas", "modelo": "Cronos 12000", "cantidad": 1, "estado": "cotizado"}]},
        {"items": [{"producto": "fundas", "cantidad": 1, "estado": "sin_precio"}]},
        {"estado": "parcial"},
    ],
)
def test_sin_nota_de_memoria(cambios):
    assert memoria_cotizacion_confirmada(cotizacion(**cambios)) is None


# ---------------------------------------------------------------- sin herramienta de precios


@pytest.mark.parametrize(
    "texto",
    [
        "Sale $45.000", "sale 45000", "son 45 mil pesos", "ARS 1200", "usd 30", "cuesta 1200",
        "el total es 1200", "precio: 900", "cuotas de 500", "45k", "12.500", "cuarenta y cinco mil",
        "ciento veinte pesos", "1200 dolares", "sale 1200",
    ],
)
def test_importes_se_detectan(texto):
    assert contiene_importe(texto) is True


@pytest.mark.parametrize(
    "texto",
    [
        "3 cuotas sin interés", "12 cuotas", "2 plazas", "5 butacas", "7 días hábiles", "4 a 5 horas",
        "6 meses", "2 años", "un juego", "cuesta dos juegos", "queda en 3 cuotas", "vale la pena",
        "https://maps.app.goo.gl/123456789", "1265",
    ],
)
def test_cantidades_no_son_importes(texto):
    assert contiene_importe(texto) is False


@pytest.mark.parametrize(
    "texto, motivo",
    [
        ("Sale $45.000", "importe_sin_herramienta"),
        ("nota interna de la cotizacion", "registro_interno_no_publicable"),
        ("Te pasé el presupuesto", "cotizacion_sin_accion"),
        ("te paso el presupuesto", "cotizacion_sin_accion"),
        ("cotización enviada", "cotizacion_sin_accion"),
    ],
)
def test_sin_precio_bloquea_y_deriva(texto, motivo):
    s = control(texto, [paso("enviar_multimedia", {"estado": "enviado"})])
    assert (s["output"], s["requiere_derivacion"], s["control_salida"]["motivo"]) == ("", True, motivo)


@pytest.mark.parametrize(
    "texto",
    ["Tenemos negro y gris", "cuando me confirmes te paso el presupuesto", "así te paso el presupuesto", "si queres te paso el presupuesto"],
)
def test_texto_normal_sale_tal_cual(texto):
    s = control(texto)
    assert s["output"] == texto and s["requiere_derivacion"] is False
    assert s["control_salida"]["motivo"] == "texto_sin_importes" and s["control_salida"]["modificada"] is False


# ---------------------------------------------------------------- segunda pasada y memoria


def test_segunda_pasada_sin_derivar_devuelve_lo_mismo():
    s = control("Tenemos negro y gris")
    assert requiere_revision_comercial(s) is False
    assert salida_comercial_confirmada(s, "Tenemos negro y gris") is s


def test_segunda_pasada_despues_de_derivar():
    s = control("Sale $45.000")
    assert requiere_revision_comercial(s) is True
    final = salida_comercial_confirmada(
        {"estado": "pendiente_asignacion", "continuacion_obligatoria": "Te paso con Candela"}, "Sale $45.000"
    )
    assert final["output"] == "Te paso con Candela"
    assert final["control_salida"]["motivo"] == "resultado_derivacion"
    assert final["control_salida"]["origen"] == "revision_deterministica"
    pausado = salida_comercial_confirmada({"estado": "derivado", "bot_pausado": True}, "Sale $45.000")
    assert pausado["output"] == "" and pausado["bot_pausado"] is True


def test_memoria_guarda_la_salida_segura():
    raw = "Te paso el presupuesto"
    final = salida_comercial_confirmada(control(raw, [paso("buscar_precio", cotizacion())]), raw)
    segura = texto_para_memoria(final, raw)
    assert segura.startswith("[Registro interno de cotización confirmada] ")
    memoria = reparar_memoria_comercial(raw, raw, segura)
    assert memoria == {"memoria_confirmada": True, "estado_memoria": "actualizada", "contenido": segura}
    assert verificar_memoria_comercial(final, memoria)["memoria_comercial"] is memoria
    assert reparar_memoria_comercial(segura, raw, segura)["estado_memoria"] == "ya_corregida"
    assert reparar_memoria_comercial(None, "a", "a")["estado_memoria"] == "sin_cambio"
    with pytest.raises(ErrorDeSalida):
        verificar_memoria_comercial(final, reparar_memoria_comercial("otra cosa", raw, segura))


# ================================================================ Corrección del 20/11
# Corrección del 20/11 (campaña de pruebas con conversaciones reales). n8n ya no se
# usa: estos resultados no salen del nodo, salen de lo que pasó en la campaña.
# (A) las respuestas del modelo ya no se pierden cuando corrió buscar_precio;
# (B) la herramienta de precios puede pedir el pase a Candela con cualquier estado;
# (C) corregir_frases deja la pregunta de modalidad como la escribe el guion.


# ---------------------------------------------------------------- (A) respuestas que se perdían

from agente.f7.precios.herramienta import PREGUNTA_MODALIDAD  # noqa: E402

OPCIONES_SURAN = "Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: SURAN 2017-2019 o SURAN 2009?"
COLOCACION = "Sobre la colocación: en nuestro taller de CABA está incluida sin cargo extra."
LOGO = ("Sobre el logo bordado: se puede evaluar, Candela te confirma factibilidad y detalles "
        "una vez que avancemos con el pedido.")
PLAZOS = ("La confección demora 5 días hábiles desde la seña, y la colocación lleva entre 4 y 5 horas "
          "(eso ya en destino, una vez enviada).")
NOTA_SURAN = (
    '[Registro interno de cotización confirmada] {"herramienta":"buscar_precio","estado":"cotizado",'
    '"situacion":"aceptada_por_chatwoot","items":[{"producto":"fundas","modelo":"Suran",'
    '"configuracion":"5 plazas","cantidad":1,"estado":"cotizado"}],"metodo_pago":"transferencia"}'
)
INCLUIDA = "La colocación en nuestro taller de CABA está incluida."
PIDE_MODELO = "Confirmá la marca y el modelo del vehículo."
EFECTIVO = "El efectivo es solo para el taller de CABA. ¿Preferís venir al taller o mantener el envío?"


def pide_modalidad():
    """Lo que devuelve buscar_precio cuando todavía no se sabe si es envío o taller."""
    return {
        "estado": "requiere_modalidad", "items": [], "totales": None, "mensaje_cotizacion": None,
        "aclaraciones": [], "envio": {"estado": "no_corresponde"}, "cotizacion_enviada": False,
        "motivo": "modalidad_no_confirmada_por_cliente", "continuacion_obligatoria": PREGUNTA_MODALIDAD,
        "instrucciones": "Copiá continuacion_obligatoria literalmente. No se consultó ni envió una cotización. "
                         "No inventes modalidad ni reintentes en este turno.",
    }


def pide_aclaracion(continuacion, producto="fundas"):
    """Resultado de buscar_precio sin cotización enviada y con una pregunta pendiente."""
    return cotizacion(
        estado="requiere_aclaracion", cotizacion_enviada=False, envio={"estado": "no_corresponde"},
        continuacion_obligatoria=continuacion,
        items=[{"producto": producto, "modelo": "Suran", "cantidad": 1, "estado": "requiere_aclaracion"}],
    )


def test_caso_real_la_respuesta_sobre_la_colocacion_sale_antes_de_la_continuacion():
    raw = ("Para fundas, cuál de estas opciones corresponde a tu vehículo: SURAN 2017-2019 o SURAN 2009? "
           "Y para la alfombra también necesito que me confirmes el año de tu Suran.\n\n" + COLOCACION)
    r = cotizacion(estado="parcial", continuacion_obligatoria=OPCIONES_SURAN, items=[
        {"producto": "fundas", "modelo": "Suran", "cantidad": 1, "estado": "requiere_aclaracion"},
        {"producto": "alfombra", "modelo": "Suran", "cantidad": 1, "estado": "cotizado"},
    ])
    s = control(raw, [paso("buscar_precio", r)],
                cliente="precio de fundas y alfombra para suran\nla colocacion la cobran aparte?")
    assert s["output"] == COLOCACION + "\n\n" + OPCIONES_SURAN
    assert (s["requiere_derivacion"], s["control_salida"]["motivo"]) == (False, "continuacion_de_herramienta")


def test_caso_real_la_respuesta_sobre_el_logo_sale_antes_de_la_pregunta_de_modalidad():
    raw = PREGUNTA_MODALIDAD + "\n\n" + LOGO
    s = control(raw, [paso("buscar_precio", pide_modalidad())],
                cliente="cuanto salen las fundas para un gol? le pueden bordar el logo?")
    assert s["output"] == LOGO + "\n\n" + PREGUNTA_MODALIDAD
    # Sin cotización no hay nota: a la memoria va la misma salida.
    assert texto_para_memoria(s, raw) == LOGO + "\n\n" + PREGUNTA_MODALIDAD


def test_caso_real_los_plazos_no_son_importes_y_salen():
    s = control(PLAZOS, [paso("buscar_precio", cotizacion())], cliente="cuanto demoran?")
    assert s["output"] == PLAZOS
    assert s["control_salida"]["modificada"] is False


def test_lo_conservado_tambien_queda_en_la_memoria_con_la_nota_de_cotizacion():
    s = control(PLAZOS, [paso("buscar_precio", cotizacion())], cliente="cuanto demoran?")
    assert texto_para_memoria(s, PLAZOS) == PLAZOS + "\n\n" + NOTA_SURAN


def test_caso_real_la_respuesta_que_habla_del_valor_no_sale():
    raw = "Sí, es la misma configuración de 2 asientos individuales, el valor ya te lo pasé arriba."
    s = control(raw, [paso("buscar_precio", cotizacion())], cliente="es la misma configuracion?")
    assert s["output"] == ""
    assert s["memoria_output"] == NOTA_SURAN


def test_caso_real_la_continuacion_copiada_sale_una_sola_vez():
    continuacion = ("Para tapiceria, ¿cuál de estas opciones corresponde a tu vehículo: "
                    "5 plazas o 2 plazas o butaca y butacón?")
    raw = "Para tapiceria, cuál de estas opciones corresponde a tu vehículo: 5 plazas o 2 plazas o butaca y butacón?"
    s = control(raw, [paso("buscar_precio", pide_aclaracion(continuacion, "tapiceria"))],
                cliente="precio de tapizado para hilux")
    assert s["output"] == continuacion


def test_un_parrafo_que_mezcla_respuesta_y_pregunta_se_descarta_entero():
    raw = ("La colocación en nuestro taller de CABA está incluida. "
           "Para fundas, cuál corresponde: SURAN 2017-2019 o SURAN 2009?")
    s = control(raw, [paso("buscar_precio", pide_aclaracion(OPCIONES_SURAN))],
                cliente="precio de fundas para suran, la colocacion la cobran aparte?")
    assert s["output"] == OPCIONES_SURAN


@pytest.mark.parametrize(
    "parrafo",
    [
        "Querés ver más diseños?",                                  # pregunta
        "¿Te muestro más diseños",                                  # pregunta sin el signo de cierre
        "Te queda en 45 mil con la colocación.",                    # importe
        "Está incluida en el precio.",
        "El valor ya te lo pasé arriba.",
        "La cotización es la misma para cualquier color.",
        "El presupuesto no cambia por el color.",
        "El total es el mismo con cualquier diseño.",
        "Con otro color sale lo mismo.",
        "Los otros diseños cuestan lo mismo.",
        "Además te hago un descuento.",
        "Ya te envié la cotización.",                               # anuncia una cotización
        '{"situacion":"aceptada_por_chatwoot","metodo_pago":"transferencia"}',  # registro interno
    ],
)
def test_el_parrafo_que_no_es_respuesta_no_sale_y_el_otro_si(parrafo):
    respuesta = "La colocación en nuestro taller de CABA está incluida."
    for raw in (respuesta + "\n\n" + parrafo, parrafo + "\n\n" + respuesta):
        s = control(raw, [paso("buscar_precio", cotizacion())], cliente="la colocacion esta incluida?")
        assert s["output"] == respuesta


def test_el_signo_de_pregunta_de_un_link_no_es_una_pregunta():
    link = ("Nuestra ubicación exacta la podes ver ingresando a este link "
            "https://maps.app.goo.gl/Nsyib1THu4WCN2L8A?g_st=ipc")
    s = control(link, [paso("buscar_precio", cotizacion())], cliente="precio de fundas para suran y pasame la ubicacion")
    assert s["output"] == link


def test_la_faq_canonica_no_se_duplica_y_el_resto_del_parrafo_sale():
    raw = "📍La dirección es Av. Olivera 1265 , CABA. La colocación la hacemos ahí mismo y está incluida."
    s = control(raw, [paso("buscar_precio", cotizacion())], cliente="donde estan? la colocacion esta incluida?")
    assert s["output"] == (
        "📍La dirección es Av. Olivera 1265 , CABA.\n\nLa colocación la hacemos ahí mismo y está incluida.")
    assert s["control_salida"]["faq_preservadas"] == ["ubicacion"]


def test_la_frase_de_la_lista_cerrada_sale_aunque_la_pregunta_no_se_reconozca():
    # «para cuando estarian» no entra en las formas de pregunta por demora que conoce preservar_faq.
    raw = "La confección aproximada es de 5 días hábiles desde la seña."
    s = control(raw, [paso("buscar_precio", cotizacion())], cliente="precio de fundas para suran y para cuando estarian")
    assert s["output"] == raw
    assert s["control_salida"]["faq_preservadas"] == []


@pytest.mark.parametrize(
    "continuacion, repetido",
    [
        (PIDE_MODELO, "Confirmá la marca y el modelo del vehículo."),                       # copiada
        (EFECTIVO, "El efectivo es solo para el taller de CABA."),                          # una de sus oraciones
        (OPCIONES_SURAN, "SURAN 2017-2019 o SURAN 2009."),                                  # un tramo
        # Copiada adentro de otra frase.
        (PIDE_MODELO, "Así avanzo con tu consulta: confirmá la marca y el modelo del vehículo y seguimos por acá."),
        # Con otras palabras.
        (PIDE_MODELO, "Necesito que me confirmes la marca y el modelo de tu vehículo."),
        ("Ese medio de pago necesita confirmación de Candela.", "Ese medio de pago lo tiene que confirmar Candela."),
        (OPCIONES_SURAN, "Decime si tu Suran es 2017-2019 o 2009."),                        # pide el mismo dato
    ],
)
def test_el_parrafo_que_repite_la_continuacion_sin_signo_de_pregunta_no_sale(continuacion, repetido):
    for raw in (repetido + "\n\n" + INCLUIDA, INCLUIDA + "\n\n" + repetido):
        s = control(raw, [paso("buscar_precio", pide_aclaracion(continuacion))], cliente="la colocacion esta incluida?")
        assert s["output"] == INCLUIDA + "\n\n" + continuacion


@pytest.mark.parametrize(
    "respuesta",
    [
        "Sí, colocamos en nuestro taller de CABA.",
        "En nuestro taller.",
        "Las dos opciones, envío o colocación en el taller, tienen la misma garantía.",
    ],
)
def test_nombrar_el_taller_no_es_repetir_la_pregunta_de_modalidad(respuesta):
    s = control(respuesta, [paso("buscar_precio", pide_modalidad())],
                cliente="cuanto salen las fundas para un gol? ustedes las colocan?")
    assert s["output"] == respuesta + "\n\n" + PREGUNTA_MODALIDAD


@pytest.mark.parametrize(
    "resultado, esperado",
    [(pide_modalidad(), LOGO + "\n\n" + PREGUNTA_MODALIDAD), (cotizacion(), LOGO)],
)
def test_el_parrafo_que_pide_elegir_envio_o_taller_no_sale_como_respuesta(resultado, esperado):
    raw = "Podés elegir envío o colocarlo en nuestro taller de CABA.\n\n" + LOGO
    s = control(raw, [paso("buscar_precio", resultado)], cliente="le pueden bordar el logo?")
    assert s["output"] == esperado


def test_el_orden_es_faq_canonica_despues_las_respuestas_y_al_final_la_continuacion():
    raw = "Te esperamos de lunes a viernes de 9 a 18 hs y sábado de 9 a 14 hs.\n\n" + INCLUIDA
    s = control(raw, [paso("buscar_precio", pide_aclaracion(OPCIONES_SURAN))],
                cliente="precio de fundas para suran\nque horario tienen? la colocacion esta incluida?")
    assert s["output"] == (
        "Te esperamos de lunes a viernes de 9 a 18 hs y sábado de 9 a 14 hs\n\n" + INCLUIDA + "\n\n" + OPCIONES_SURAN)


# ---------------------------------------------------------------- (B) pase pedido por la herramienta


def pide_pase(**cambios):
    """Resultado de buscar_precio que pide el pase: el contrato acordado con la herramienta."""
    r = cotizacion(estado="requiere_aclaracion", requiere_derivacion="revision_especial",
                   continuacion_obligatoria="", envio={"estado": "no_corresponde"})
    r.update(cambios)
    return r


@pytest.mark.parametrize("estado", ["requiere_aclaracion", "no_disponible", "parcial", "cotizado", "estado_nuevo"])
@pytest.mark.parametrize("envio", ["no_corresponde", "aceptado", "omitido"])
def test_la_herramienta_pide_el_pase_con_cualquier_estado(estado, envio):
    r = pide_pase(estado=estado, envio={"estado": envio, "chatwoot_message_id": 55})
    s = control("Dame un momento que lo consulto", [paso("buscar_precio", r)], cliente="precio fundas duster 2018")
    assert (s["output"], s["requiere_derivacion"], s["control_salida"]["motivo"]) == ("", True, "revision_especial")


@pytest.mark.parametrize("envio", ["fallido", "desconocido"])
def test_el_pase_de_la_herramienta_no_vale_con_envio_incierto(envio):
    aviso = "No pude confirmar el envío de la cotización. Esa parte necesita revisión del equipo."
    r = pide_pase(estado="parcial", continuacion_obligatoria=aviso, envio={"estado": envio})
    s = control("", [paso("buscar_precio", r)])
    assert (s["output"], s["requiere_derivacion"], s["control_salida"]["motivo"]) == (
        aviso, False, "continuacion_de_herramienta")


def test_el_pase_lo_decide_el_ultimo_resultado_de_precios():
    s = control("", [paso("buscar_precio", cotizacion()), paso("buscar_precio", pide_pase())])
    assert (s["requiere_derivacion"], s["control_salida"]["motivo"]) == (True, "revision_especial")
    s = control("", [paso("buscar_precio", pide_pase()), paso("buscar_precio", cotizacion())])
    assert (s["requiere_derivacion"], s["control_salida"]["motivo"]) == (False, "continuacion_de_herramienta")


def test_pausa_y_resultado_de_derivacion_van_antes_que_el_pase_de_la_herramienta():
    pausado = control("", [paso("buscar_precio", pide_pase()), paso("enviar_multimedia", {"estado": "control_humano"})])
    assert (pausado["bot_pausado"], pausado["requiere_derivacion"], pausado["control_salida"]["motivo"]) == (
        True, False, "control_humano")
    derivado = control("", [
        paso("buscar_precio", pide_pase()),
        paso("derivar_humano", {"estado": "pendiente_asignacion", "continuacion_obligatoria": "Te derivo"}),
    ])
    assert (derivado["output"], derivado["requiere_derivacion"], derivado["control_salida"]["motivo"]) == (
        "Te derivo", False, "resultado_derivacion")


# ---------------------------------------------------------------- (C) frases fijas del guion

from agente.f7.salida import corregir_frases  # noqa: E402

PRESENTACION = ("Cada funda se realiza a medida y por encargo para cada butaca , el material que utilizamos "
                "es cuero automotor. Podes elegir diseño y color que te guste")


@pytest.mark.parametrize(
    "texto",
    [
        # Casos reales de la campaña.
        "Para poder darte el precio necesito saber si preferís envío o retirarlo en nuestro taller en CABA. "
        "Cuál de las dos opciones te queda mejor?",
        "El video ya quedó enviado. Contanos si preferís envío o retirarlo en nuestro taller de CABA para poder cotizarte",
        # La literal con tildes vuelve a la del guion, que no las lleva.
        "Hacemos envíos a todo el país y nuestro taller está situado en CABA. "
        "Quisieras la opción de envío o colocarlo en nuestro taller?",
        # Otras formas de preguntar lo mismo.
        "¿Lo querés con envío a domicilio o lo colocamos nosotros en el taller?",
        "Decime si preferís que te lo mandemos o colocarlo en nuestro taller de CABA.",
        "¿Querés que te lo enviemos o preferís venir a colocarlo?",
        "Hacemos envíos a todo el país y también colocamos en nuestro taller de CABA. "
        "¿Qué preferís, envío o colocación en el taller?",
    ],
)
def test_la_pregunta_de_modalidad_reformulada_vuelve_a_la_literal(texto):
    assert corregir_frases(texto) == PREGUNTA_MODALIDAD


@pytest.mark.parametrize(
    "texto",
    [
        "",
        PREGUNTA_MODALIDAD,
        PRESENTACION + "\n\n" + PREGUNTA_MODALIDAD,
        # Con la literal en el texto no se toca ninguna pregunta de modalidad.
        PREGUNTA_MODALIDAD.replace("CABA. ", "CABA.\n"),
        PREGUNTA_MODALIDAD + " Cuál de las dos opciones te queda mejor?",
        # Otras frases fijas del guion: no se tocan.
        "Si, hacemos envios a Mendoza y a todo el pais",
        "El efectivo es solo para el taller de CABA. ¿Preferís venir al taller o mantener el envío?",
        "Nuestro taller esta en Av Olivera 1265, CABA.",
        "Pudieras acercarte a nuestro taller para realizar este trabajo? Nuestro taller esta en Av Olivera 1265, CABA.\n"
        "https://maps.app.goo.gl/Nsyib1THu4WCN2L8A?g_st=ipc",
        "La confección tarda 5 días hábiles desde la seña y la colocación lleva entre 4 y 5 horas",
        PRESENTACION,
        # La misma elección dicha de otra forma después de hablar del efectivo: tampoco se toca.
        "Con envío no hay efectivo, solo en el taller. ¿Preferís envío o venir al taller?",
        # Nombran el envío y el taller, pero no piden elegir la modalidad.
        "Trabajamos con envío o con colocación en nuestro taller de CABA.",
        "Las dos opciones, envío o colocación en el taller, tienen la misma garantía.",
        "Se puede con envío o con colocación en el taller, lo cual no cambia la garantía.",
        "No hace falta definir ahora tu preferencia de envío o colocación en el taller.",
        "Si querés te mando la ubicación de nuestro taller en CABA.",
        "¿Querés que te mande fotos de trabajos hechos en nuestro taller?",
        "¿Preferís que te mande el video o las fotos del taller?",
        # Hablan del material, pero no anuncian que ya se envió.
        "Las fotos que te envié son de trabajos reales.",
        "En el video se ve cómo queda colocada la funda.",
    ],
)
def test_lo_que_no_hay_que_corregir_vuelve_igual(texto):
    assert corregir_frases(texto) == texto


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("El video ya quedó enviado.", ""),
        ("Las fotos ya fueron enviadas. Cualquier duda avisame.", "Cualquier duda avisame."),
        ("La colocación está incluida.\n\nLas fotos ya fueron enviadas.", "La colocación está incluida."),
        ("La colocación está incluida. Ya te envié el video. La garantía es de 90 días.",
         "La colocación está incluida. La garantía es de 90 días."),
        ("Te mandé las fotos de los diseños.\n\nLa colocación está incluida.", "La colocación está incluida."),
        # El punto y aparte que separaba dos párrafos no se pierde.
        ("La colocación está incluida. El video ya quedó enviado.\n\nLa garantía es de 90 días.",
         "La colocación está incluida.\n\nLa garantía es de 90 días."),
        ("La colocación está incluida.\n\nEl video ya quedó enviado. La garantía es de 90 días.",
         "La colocación está incluida.\n\nLa garantía es de 90 días."),
        ("El video de presentación ya fue enviado", ""),
        ("Ya quedaron enviadas las fotos.", ""),
        # Con la pregunta literal al lado: el anuncio se va y la pregunta no se toca.
        ("El video ya quedó enviado.\n\n" + PREGUNTA_MODALIDAD, PREGUNTA_MODALIDAD),
    ],
)
def test_los_anuncios_de_material_ya_enviado_se_quitan(texto, esperado):
    assert corregir_frases(texto) == esperado


def test_al_corregir_la_pregunta_el_resto_del_texto_queda_como_estaba():
    texto = PRESENTACION + "\n\nPara cotizarte necesito saber si preferís envío o colocarlo en nuestro taller."
    assert corregir_frases(texto) == PRESENTACION + "\n\n" + PREGUNTA_MODALIDAD


def test_la_pregunta_de_modalidad_queda_una_sola_vez():
    texto = ("Preferís envío o colocarlo en el taller?\n\nLa garantía es de 90 días.\n\n"
             "Decime si querés envío o colocación en el taller.")
    assert corregir_frases(texto) == PREGUNTA_MODALIDAD + "\n\nLa garantía es de 90 días."


@pytest.mark.parametrize(
    "texto, esperado",
    [
        # Lo que la literal ya dice (envíos a todo el país, taller en CABA) no queda repetido.
        ("Hacemos envíos a todo el país. Nuestro taller está en CABA. ¿Preferís envío o colocarlo en el taller?",
         PREGUNTA_MODALIDAD),
        # Lo que la literal no dice (el lugar que preguntó, la dirección) queda.
        ("Si, hacemos envios a Mendoza y a todo el pais. Preferís envío o colocarlo en el taller?",
         "Si, hacemos envios a Mendoza y a todo el pais. " + PREGUNTA_MODALIDAD),
        ("Nuestro taller esta en Av Olivera 1265, CABA. ¿Preferís envío o colocarlo en el taller?",
         "Nuestro taller esta en Av Olivera 1265, CABA. " + PREGUNTA_MODALIDAD),
    ],
)
def test_la_presentacion_de_la_pregunta_de_modalidad_no_queda_dos_veces(texto, esperado):
    assert corregir_frases(texto) == esperado


@pytest.mark.parametrize(
    "despues",
    ["¿Cuál es el modelo de tu auto?", "El envío es lo que te conviene si estás lejos."],
)
def test_lo_que_sigue_a_la_pregunta_y_no_es_insistir_queda(despues):
    texto = "¿Preferís envío o colocarlo en nuestro taller? " + despues
    assert corregir_frases(texto) == PREGUNTA_MODALIDAD + " " + despues


def test_la_nota_interna_de_cotizacion_no_se_toca_diga_lo_que_diga():
    # El turno corrige también lo que va a la memoria, que termina con la nota interna.
    nota = (
        '[Registro interno de cotización confirmada] {"herramienta":"buscar_precio","estado":"cotizado",'
        '"situacion":"aceptada_por_chatwoot","items":[{"producto":"fundas","modelo":"S10 2.8 Cab. Doble",'
        '"configuracion":"Envío o colocación en taller?","cantidad":1,"estado":"cotizado"}],'
        '"metodo_pago":"transferencia"}'
    )
    assert corregir_frases(nota) == nota
    assert corregir_frases(INCLUIDA + "\n\n" + nota) == INCLUIDA + "\n\n" + nota
    assert corregir_frases("Decime si preferís envío o colocarlo en el taller.\n\n" + nota) == (
        PREGUNTA_MODALIDAD + "\n\n" + nota)
    assert corregir_frases("El video ya quedó enviado.\n\n" + nota) == nota


# ================================================================ Campaña de multimedia del 21/11
# La corrección (A) del 20/11 dejaba pasar relleno del modelo junto a la cotización cuando el
# cliente no había preguntado nada más: «No tengo nada más para agregar por ahora», «No prometas
# pago…». Ahora lo que escribe el modelo al lado de buscar_precio sale solo si el cliente
# preguntó o pidió otra cosa además del precio.


@pytest.mark.parametrize(
    "cliente, relleno",
    [
        ("tengo una Toro, con envío a Neuquén, cuánto sale?",
         "No pude seguir aquí ya que el límite de turnos ha sido alcanzado."),
        ("con envío a Córdoba", "No prometas pago, demora de envio especifica o compatibilidad sin que lo pidan."),
        ("me quedo con la tipo tapizado. lo coloco en el taller", "No tengo nada más para agregar por ahora."),
        ("Hola, el video del cubrevolante ya lo vi en Instagram, no me lo mandes. Pasame nomás el precio con envío "
         "a Córdoba", "No hay texto adicional."),
        ("me sirve. precio con envío a Corrientes?",
         "El video del cubrevolante ya te lo había enviado antes en la conversación, fijate más arriba."),
    ],
)
def test_caso_real_el_relleno_del_modelo_no_sale_si_el_cliente_solo_pidio_el_precio(cliente, relleno):
    s = control(relleno, [paso("buscar_precio", cotizacion())], cliente=cliente)
    assert s["output"] == ""


@pytest.mark.parametrize(
    "cliente, respuesta",
    [
        ("cuanto sale con envio? y le pueden bordar el logo de ford?",
         "El bordado de logo es algo que coordina Candela para confirmar factibilidad."),
        ("Lo coloco en el taller\nLa colocación con qué cargo cuenta?",
         "La colocación en nuestro taller de CABA está incluida, sin cargo adicional."),
        ("sí, puedo ir. pero antes quiero ver algún trabajo, tenés fotos o video?",
         "Por ahora no tenemos fotos o videos de trabajos de tapicería para enviar por este medio."),
        ("es negro, para un uber, q salen y q demora tienen para enviarlas?", "Eso lo coordina Candela con el envío."),
        ("precio de fundas para un gol y decime si le ponen el logo", "El logo lo coordina Candela."),
    ],
)
def test_caso_real_la_respuesta_sale_si_el_cliente_pregunto_otra_cosa(cliente, respuesta):
    s = control(respuesta, [paso("buscar_precio", cotizacion())], cliente=cliente)
    assert s["output"] == respuesta


# ================================================================ Re-prueba de multimedia del 21/11
# Decisión de Mateo: no se dice «No tengo fotos». Si la oración sigue con un «pero…», queda esa
# parte; si era lo único que había para decir, va el catálogo del guion.

URL = "https://wa.me/c/5491156013327"


@pytest.mark.parametrize(
    "texto, esperado",
    [
        (f"Fotos como tal no tenemos, pero podés ver más opciones en nuestro catálogo: {URL}",
         f"Podés ver más opciones en nuestro catálogo: {URL}"),
        (f"No contamos con fotos propias de la funda de baúl, pero en el catálogo podés ver ejemplos: {URL}",
         f"En el catálogo podés ver ejemplos: {URL}"),
        (f"Para la funda de baúl no tenemos fotos o video propios, pero podés ver ejemplos en nuestro catálogo: {URL}",
         f"Podés ver ejemplos en nuestro catálogo: {URL}"),
        ("Por el momento no tengo fotos disponibles de los cubrevolantes para enviarte. Cualquier otra consulta, decime.",
         "Cualquier otra consulta, decime."),
        ("Por ahora no tengo fotos disponibles de tipo tapizado para enviarte, disculpá", f"Catálogo: {URL}"),
        ("El material que utilizamos es cuero automotor.", "El material que utilizamos es cuero automotor."),
        ("No tenemos envío para ese trabajo, se hace en el taller.", "No tenemos envío para ese trabajo, se hace en el taller."),
        ("", ""),
    ],
)
def test_no_se_niega_que_haya_fotos(texto, esperado):
    from agente.f7.salida import sin_negar_fotos

    assert sin_negar_fotos(texto, URL) == esperado


@pytest.mark.parametrize("relleno", ["Perfecto.", "¡Listo!", "Dale", "Genial!"])
def test_una_interjeccion_suelta_no_es_una_respuesta(relleno):
    s = control(relleno, [paso("buscar_precio", cotizacion())], cliente="si puedo ir. tenes fotos o video?")
    assert s["output"] == ""


def test_el_catalogo_pedido_sale_junto_a_la_cotizacion():
    # Re-prueba del 21/11: pidió fotos de un trabajo de tapicería junto con el precio; salió la
    # cotización con un «Perfecto» y sin el catálogo.
    link = "Podés ver trabajos en nuestro catálogo: https://wa.me/c/5491156013327"
    s = control("Perfecto.\n\n" + link, [paso("buscar_precio", cotizacion())],
                cliente="sí, puedo ir. pero antes quiero ver algún trabajo, tenés fotos o video?")
    assert s["output"] == link


@pytest.mark.parametrize("texto", [
    "No hay problema, ahí te mando el video",
    "No tenemos cuero natural, el material es cuero automotor",
    "No tenemos ese material, trabajamos con cuero automotor",
    "En el video se ve que no hay que desarmar la butaca",
    "No tengo problema en pasarte las fotos",
    "Las fotos son de trabajos nuestros, no tenemos intermediarios",
])
def test_una_frase_parecida_que_no_niega_fotos_queda_como_esta(texto):
    from agente.f7.salida import sin_negar_fotos

    assert sin_negar_fotos(texto, URL) == texto


@pytest.mark.parametrize("texto", [
    "No tengo disponible por este canal material de funda de baúl para mostrarte",
    "No puedo enviarte fotos por este medio",
    "Por ahora de alfombras tengo disponible solo el video, fotos no tengo para mandarte",
    "No tenemos ese material por acá",
    "No tengo imágenes de colores de cubrevolante para enviarte en este momento",
    "De ese producto no hay fotos ni videos",
    "Por este medio no tenemos disponibles fotos de cobertores de caja",
    "No cuento con videos para compartir de ese trabajo puntual",
])
def test_otras_formas_de_negar_fotos_tampoco_salen(texto):
    from agente.f7.salida import sin_negar_fotos

    assert sin_negar_fotos(texto, URL) == f"Catálogo: {URL}"


def test_sin_catalogo_para_ofrecer_la_negativa_se_borra_y_nada_mas():
    from agente.f7.salida import sin_negar_fotos

    assert sin_negar_fotos("Por el momento no tengo fotos de las alfombras", None) == ""


@pytest.mark.parametrize("texto, esperado", [
    # Re-prueba del 21/11, segunda vuelta: lo negó con otras palabras.
    (f"Funda baúl no tiene material fotográfico en nuestro sistema, pero podés ver variedad en el catálogo: {URL}",
     f"Podés ver variedad en el catálogo: {URL}"),
    (f"No tenemos ese contenido específico por acá, pero en el catálogo podés ver más: {URL}",
     f"En el catálogo podés ver más: {URL}"),
    ("De ese trabajo no existen videos", f"Catálogo: {URL}"),
    # «Material» y «contenido» cuentan solo si esa parte de la oración habla de mostrarlo.
    ("El cuero no tiene material sintético, lo podés ver en el video",
     "El cuero no tiene material sintético, lo podés ver en el video"),
    ("La funda no tiene contenido de fábrica, te mando el video", "La funda no tiene contenido de fábrica, te mando el video"),
])
def test_negar_el_material_con_otras_palabras_tampoco_sale(texto, esperado):
    from agente.f7.salida import sin_negar_fotos

    assert sin_negar_fotos(texto, URL) == esperado


# ---------- Prueba de «romper el flujo» del 21/11 ----------

MODALIDAD = ("Hacemos envios a todo el pais y nuestro taller esta situado en CABA. "
             "Quisieras la opción de envio o colocarlo en nuestro taller?")


@pytest.mark.parametrize("texto, esperado", [
    # R08 y R10: afirmó que había fundas para un BYD Dolphin y para un Scania sin consultar la planilla.
    ("Sí, tenemos fundas para el BYD Dolphin. Te gustaría recibir más información?", "Te gustaría recibir más información?"),
    ("Sí, hacemos fundas a medida para camiones, incluido Scania.\n\n" + MODALIDAD, MODALIDAD),
    ("Tenemos alfombras para tu Cronos", ""),
    ("Sí, contamos con cobertor de caja para la Partner", ""),
])
def test_no_se_afirma_que_hay_un_producto_para_un_vehiculo_sin_consultar(texto, esperado):
    from agente.f7.salida import sin_afirmar_disponibilidad

    assert sin_afirmar_disponibilidad(texto) == esperado


@pytest.mark.parametrize("texto", [
    "Si, hacemos envios a Tierra del Fuego y a todo el pais",
    "Sí, hacemos tapizado de paneles de puerta, ese trabajo se realiza en nuestro taller de CABA",
    "Sí, realizamos el cambio de espuma en los asientos",
    "Contas con garantía de fábrica por 90 días desde su colocación",
    "Cada funda se realiza a medida y por encargo para cada butaca , el material que utilizamos es cuero automotor",
    "Las alfombras termoformadas cubren por completo el piso de tu vehículo, evitando derrames o futuros daños",
    "Para qué modelo de vehículo las necesitás?",
    "",
])
def test_lo_que_no_afirma_disponibilidad_para_un_vehiculo_queda_igual(texto):
    from agente.f7.salida import sin_afirmar_disponibilidad

    assert sin_afirmar_disponibilidad(texto) == texto


def test_despues_de_la_pregunta_de_modalidad_no_va_otra_pregunta():
    # R27: cerró con «envío o taller?» y «crédito o débito?» en el mismo mensaje.
    from agente.f7.salida import una_sola_pregunta

    texto = "Si, hacemos envios a San Luis y a todo el pais.\n\n" + MODALIDAD
    assert una_sola_pregunta(texto + "\n\nPara pagar con tarjeta, es crédito o débito?") == texto
    assert una_sola_pregunta(texto) == texto
    # Sin la pregunta de modalidad no se toca nada.
    otro = "Qué modelo de vehículo es? Y de qué año?"
    assert una_sola_pregunta(otro) == otro
