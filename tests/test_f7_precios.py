"""Pruebas de buscar_precio de F7. No salen a internet ni gastan tokens.

La planilla es una inventada, chiquita y con importes inventados, con la misma
forma que la oficial. Los textos esperados salen de correr el motor original
de n8n (motor.mjs y salida-agente.mjs) sobre esta misma planilla.
"""

from __future__ import annotations

import copy
import datetime as dt
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente.f7.local import ContextoTurno, SesionLocal  # noqa: E402
from agente.f7.precios import herramienta, planilla  # noqa: E402
from agente.f7.precios.descripcion import (  # noqa: E402
    DESCRIPCION_BUSCAR_PRECIO,
    DESCRIPCION_PEDIDO_BUSCAR_PRECIO,
)
from agente.f7.precios.motor import cotizar, dinero, js_numero, normalizar_entrada  # noqa: E402
from agente.f7.precios.salida_agente import ERROR_ENVIO, INSTRUCCIONES  # noqa: E402

CIERRE = "Quisieras aprovechar el valor en transferencia o en 3 cuotas sin interes?"
# Desde el 16/11 (textos de Mateo): si se confundió o no es un vehículo, que lo repita;
# si es un vehículo que no está en la lista, que pase por el taller.
CONFUSION = "Creo que tuviste una confusion, repetime tu modelo de vehiculo asi veo si contamos con las medidas"
SIN_MEDIDAS = ("No contamos con las medidas de tu vehiculo, te invito a pasar por nuestro taller en CABA para "
               "tomarlas y asi poder confeccionar las fundas")

# Importes inventados. La forma copia la de la planilla oficial.
PLANILLA = [
    {"title": "Fundas a medida", "sheetId": 877828453, "values": [
        ["RENAULT"],
        ["Marca y Modelo de vehículo", "Juego completo (5 plazas)", "", "2 ASIENTOS INDIVIDUALES", ""],
        ["", "EFECTIVO", "TRANF", "EFECTIVO", "TRANF"],
        ["CLIO", 140000, 150000, 80000, 90000],
        ["DUSTER", 160000, 170000, 90000, 95000],
        ["DUSTER 2017+", 165000, 175000, 92000, 97000],
        ["FORD"],
        ["RANGER", 200000, 210000, 110000, 120000.5]]},
    {"title": "TIPO TAPIZADO", "sheetId": 613213257, "values": [
        ["Marca y Modelo de vehículo", "Juego completo (5 plazas)", "", "2 ASIENTOS INDIVIDUALES", ""],
        ["", "EFECTIVO", "TRANF", "EFECTIVO", "TRANF"],
        ["CLIO", 120000, 130000, 70000, 75000]]},
    {"title": "TAPICERIA", "sheetId": 972378170, "values": [
        ["TOYOTA"],
        ["Marca y Modelo de vehículo", "Juego completo (5 plazas)", "", "2 ASIENTOS INDIVIDUALES", ""],
        ["", "EFECTIVO", "TRANF", "EFECTIVO", "TRANF"],
        ["ETIOS", 300000, 330000, 160000, 175000]]},
    {"title": "Termoformadas", "sheetId": 0, "values": [
        ["Marca", "Vehículo/Modelo", "EFECTIVO", "TRANSFERENCIA"],
        ["Ford", "Ford Ranger 2016 - 2022", 50000, 55000],
        ["Ford", "Ford Ranger 2023+", 60000, 65000],
        ["Renault", "Renault Clio", 30000, 33000]]},
    {"title": "ESPUMAS", "sheetId": 1953604758, "values": [
        ["RECAMBIO DE GOMA ESPUMA"],
        ["Vehiculos", "RESPALDO", "", "ASIENTO"],
        ["", "EFECTIVO", "TRANSFERENCIA", "EFECTIVO", "TRANSFERENCIA"],
        ["CLIO S R", 10000, 11000, 12000, 13000]]},
    {"title": "Otros", "sheetId": 59879218, "values": [
        ["OTROS ACCESORIOS"],
        ["Producto/servicio", "Valor EFECTIVO", "TRANSFERENCIA + 21%", "POSNET o CUOTAS 21% + 9%"],
        [],
        ["CUBRE VOLANTE", 20000, 22000, 25000],
        ["TAPIZADO DE TECHO", 90000, 99000, 110000]]},
]


class LectorFalso:
    """Hace de la planilla: devuelve las hojas pedidas y anota cada lectura."""

    def __init__(self, falla: Exception | None = None):
        self.pedidas: list[list[str]] = []
        self.falla = falla

    def __call__(self, titulos):
        self.pedidas.append(list(titulos))
        if self.falla:
            raise self.falla
        return [copy.deepcopy(h) for h in PLANILLA if h["title"] in titulos]


def pedido(consultas, tipo="consulta", metodo=None, **extra):
    p = {"consultas": consultas, "tipo_solicitud": tipo, **extra}
    if metodo:
        p["metodo_pago"] = metodo
    return p


def contexto(sesion=None, modalidad="caba", ultimo=None):
    sesion = sesion or SesionLocal(conversation_id=7)
    if ultimo is None:
        ultimo = sesion.nuevo_message_id()
    return ContextoTurno(sesion=sesion, ultimo_message_id=ultimo, modalidad_confirmada=modalidad)


def correr(p, ctx=None, lector=None, **kw):
    ctx = ctx or contexto(**kw)
    lector = lector or LectorFalso()
    return herramienta.ejecutar(p, ctx, leer_hojas=lector), ctx, lector


def cotizacion_local(p, modalidad="caba"):
    """El motor solo, sin herramienta: lo que en n8n sale de «Resolver cotizacion»."""
    n = normalizar_entrada({**p, "modalidad": modalidad})
    assert n["ok"], n["errores"]
    hojas = [h for h in PLANILLA if h["title"] in n["hojas"]]
    return cotizar(n["entrada"], hojas, "2026-11-15T00:00:00.000Z")


# --- Contrato -------------------------------------------------------------

def test_contrato_de_la_herramienta():
    assert herramienta.NOMBRE == "buscar_precio"
    assert herramienta.ARGUMENTO == "pedido"
    assert herramienta.DESCRIPCION is DESCRIPCION_BUSCAR_PRECIO
    assert herramienta.DESCRIPCION_ARGUMENTO is DESCRIPCION_PEDIDO_BUSCAR_PRECIO
    # La descripción de buscar_precio cambió el 16/11 (sin pregunta final, pedido
    # de Mateo). La del argumento sigue igual a la de n8n.
    # 4530 de n8n más la aclaración del 20/11: un techo no es tapicería de butacas.
    assert len(DESCRIPCION_PEDIDO_BUSCAR_PRECIO) == 4530 + 136
    assert CIERRE not in DESCRIPCION_BUSCAR_PRECIO


# --- Envío de la cotización (camino feliz) ----------------------------------

def test_cotiza_y_manda_un_solo_mensaje_por_transferencia():
    r, ctx, lector = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]))
    assert lector.pedidas == [["Fundas a medida"]]
    [globo] = ctx.sesion.salientes
    assert globo.tipo == "cotizacion"
    assert globo.texto == ("El juego completo de fundas a medida para Clio (5 plazas) sale $150.000 por "
                           "transferencia.")
    assert r["estado"] == "cotizado"
    assert r["envio"] == {"estado": "aceptado", "motivo": None, "chatwoot_message_id": globo.chatwoot_message_id,
                          "registro_confirmado": True}
    assert r["cotizacion_enviada"] is True
    assert r["continuacion_obligatoria"] == ""
    assert r["pregunta_comercial_incluida"] is False
    assert r["metodo_pago"] == "transferencia"
    assert r["items"] == [{"producto": "fundas", "modelo": "CLIO", "estado": "cotizado", "cantidad": 1,
                           "configuracion": "Juego completo (5 plazas)",
                           "medios_disponibles": ["efectivo", "transferencia", "cuotas"]}]
    assert r["instrucciones"] == INSTRUCCIONES
    assert list(r) == ["estado", "items", "envio", "consultado_en", "metodo_pago", "pregunta_comercial_incluida",
                       "cotizacion_enviada", "continuacion_obligatoria", "instrucciones"]
    # Al modelo no le llega ningún importe.
    assert "150" not in str(r)
    fila = ctx.sesion.registro("precios")[ctx.solicitud_id("precios-v1")]
    assert fila["estado"] == "aceptado" and fila["chatwoot_message_id"] == globo.chatwoot_message_id


@pytest.mark.parametrize("p, modalidad, texto", [
    (pedido([{"producto": "fundas", "modelo": "Clio"}], metodo="efectivo"), "caba",
     "El juego completo de fundas a medida para Clio (5 plazas) sale $140.000 en efectivo."),
    (pedido([{"producto": "fundas", "modelo": "Clio"}], metodo="cuotas"), "caba",
     "El juego completo de fundas a medida para Clio (5 plazas) sale $150.000 en total, en 3 cuotas sin interés."),
    (pedido([{"producto": "fundas", "modelo": "Clio"}, {"producto": "alfombra", "modelo": "Ranger", "anio": 2024}],
            tipo="combo"), "caba",
     "El juego completo de fundas a medida para Clio (5 plazas) y la alfombra termoformada para Ford Ranger 2023+ "
     "salen $215.000 por transferencia."),
    (pedido([{"producto": "fundas", "modelo": "Clio"}, {"producto": "tipo tapizado", "modelo": "Clio"}],
            tipo="comparacion"), "caba",
     "El juego completo de fundas a medida para Clio (5 plazas) sale $150.000 por transferencia. El juego completo "
     "de fundas tipo tapizado para Clio (5 plazas) sale $130.000 por transferencia."),
    (pedido([{"producto": "fundas", "modelo": "Clio", "configuracion": "2 plazas"}]), "caba",
     "El juego de fundas a medida para Clio (2 plazas) sale $90.000 por transferencia."),
    (pedido([{"producto": "fundas", "modelo": "Ranger", "configuracion": "dos asientos"}]), "caba",
     "El juego de fundas a medida para Ranger (2 plazas) sale $120.000,50 por transferencia."),
    (pedido([{"producto": "cubrevolante"}]), "envio",
     "El cubrevolante sale $22.000 por transferencia."),
    (pedido([{"producto": "fundas", "modelo": "Clio", "cantidad": 2}]), "caba",
     "Los 2 juegos completos de fundas a medida para Clio (5 plazas cada uno) salen $300.000 por transferencia en "
     "total ($150.000 por juego)."),
    (pedido([{"producto": "cubrevolante", "cantidad": 3}], metodo="cuotas"), "caba",
     "Los 3 cubrevolantes salen $66.000 en total, en 3 cuotas sin interés ($22.000 por unidad)."),
    (pedido([{"producto": "fundas", "modelo": "Clio", "cantidad": 2}, {"producto": "cubrevolante"}], tipo="combo",
            metodo="efectivo"), "caba",
     "Los 2 juegos completos de fundas a medida para Clio (5 plazas cada uno) y el cubrevolante salen $300.000 en "
     "efectivo."),
    (pedido([{"producto": "fundas", "modelo": "Duster", "anio": 2019}]), "caba",
     "El juego completo de fundas a medida para Duster 2017+ (5 plazas) sale $175.000 por transferencia."),
    (pedido([{"producto": "fundas", "modelo": "Clio"}, {"producto": "fundas", "modelo": "Batimovil"}]), "caba",
     "El juego completo de fundas a medida para Clio (5 plazas) sale $150.000 por transferencia.\n\n"
     "Fundas a medida para Batimovil: pendiente de confirmación."),
])
def test_textos_de_la_cotizacion(p, modalidad, texto):
    r, ctx, _ = correr(p, modalidad=modalidad)
    assert [g.texto for g in ctx.sesion.salientes] == [texto]
    assert r["envio"]["estado"] == "aceptado"
    assert CIERRE not in texto


# --- Pedido de Mateo del 16/11: juego completo de fundas con envío -----------

ENVIO_FUNDAS = (
    "El juego completo de fundas en cuero automotor y a medida tiene un valor de $150.000 en el diseño y color que "
    "elijas.\n\nAbonando en transferencia tenes un 10% de descuento realizando una seña en el encargo y el restante "
    "previo a su envio.(abonas en dos partes)\n\nTambién podes abonar en 3 cuotas sin interés los días miércoles y "
    "sábado en el precio indicado"
)


@pytest.mark.parametrize("metodo", [None, "cuotas"])
def test_con_envio_el_juego_completo_de_fundas_sale_con_el_texto_de_mateo(metodo):
    # El importe es el de la columna de transferencia del juego completo (inventado: 150.000).
    r, ctx, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}], metodo=metodo), modalidad="envio")
    assert [g.texto for g in ctx.sesion.salientes] == [ENVIO_FUNDAS]
    assert r["estado"] == "cotizado" and r["cotizacion_enviada"] is True
    assert r["continuacion_obligatoria"] == ""
    assert r["pregunta_comercial_incluida"] is False
    assert "150" not in str(r)


def test_en_el_taller_el_juego_completo_sigue_con_el_texto_de_siempre():
    _, ctx, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]), modalidad="caba")
    assert [g.texto for g in ctx.sesion.salientes] == [
        "El juego completo de fundas a medida para Clio (5 plazas) sale $150.000 por transferencia."]


@pytest.mark.parametrize("consultas, tipo, texto", [
    ([{"producto": "fundas", "modelo": "Clio", "configuracion": "2 plazas"}], "consulta",
     "El juego de fundas a medida para Clio (2 plazas) sale $90.000 por transferencia."),
    ([{"producto": "fundas", "modelo": "Clio", "cantidad": 2}], "consulta",
     "Los 2 juegos completos de fundas a medida para Clio (5 plazas cada uno) salen $300.000 por transferencia en "
     "total ($150.000 por juego)."),
    ([{"producto": "fundas", "modelo": "Clio"}, {"producto": "cubrevolante"}], "combo",
     "El juego completo de fundas a medida para Clio (5 plazas) y el cubrevolante salen $172.000 por transferencia."),
    ([{"producto": "tipo tapizado", "modelo": "Clio"}], "consulta",
     "El juego completo de fundas tipo tapizado para Clio (5 plazas) sale $130.000 por transferencia."),
])
def test_con_envio_lo_demas_sigue_igual_y_sin_pregunta_final(consultas, tipo, texto):
    _, ctx, _ = correr(pedido(consultas, tipo=tipo), modalidad="envio")
    assert [g.texto for g in ctx.sesion.salientes] == [texto]


def test_efectivo_con_envio_se_borra_y_cuotas_copia_transferencia():
    res = cotizacion_local(pedido([{"producto": "fundas", "modelo": "Clio"}]), modalidad="envio")
    assert res["items"][0]["precios"] == {"transferencia": 150000, "cuotas": 150000}
    combo = cotizacion_local(pedido([{"producto": "fundas", "modelo": "Clio", "cantidad": 2},
                                     {"producto": "cubrevolante"}], tipo="combo", metodo="efectivo"))
    assert combo["totales"] == {"efectivo": 300000, "transferencia": 322000, "cuotas": 322000}
    assert combo["items"][0]["subtotales"] == {"efectivo": 280000, "transferencia": 300000, "cuotas": 300000}


def test_parcial_devuelve_el_motivo_del_que_falta():
    r, _, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}, {"producto": "fundas", "modelo": "Batimovil"}]))
    assert r["estado"] == "parcial"
    assert r["cotizacion_enviada"] is True
    assert r["continuacion_obligatoria"] == CONFUSION  # «Batimovil» no es un vehículo de la lista


# --- Sin envío: aclaraciones, medios y faltantes ----------------------------

@pytest.mark.parametrize("p, modalidad, estado, continuacion", [
    (pedido([{"producto": "fundas", "modelo": "Clio"}], metodo="efectivo"), "envio", "metodo_no_disponible",
     "El efectivo es solo para el taller de CABA. ¿Preferís venir al taller o mantener el envío?"),
    (pedido([{"producto": "fundas", "modelo": "Batimovil"}]), "caba", "no_disponible", CONFUSION),
    (pedido([{"producto": "fundas", "modelo": "Renault Batimovil"}]), "caba", "no_disponible", SIN_MEDIDAS),
    (pedido([{"producto": "alfombra", "modelo": "Ranger"}]), "caba", "requiere_aclaracion",
     "Para alfombra, ¿cuál de estas opciones corresponde a tu vehículo: Ford Ranger 2016 - 2022 o Ford Ranger 2023+?"),
    (pedido([{"producto": "espuma", "modelo": "Clio"}]), "caba", "requiere_aclaracion",
     "Para espuma, ¿cuál de estas opciones corresponde a tu vehículo: asiento o respaldo?"),
    (pedido([{"producto": "fundas", "modelo": "Duster"}]), "caba", "requiere_aclaracion",
     "Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: DUSTER o DUSTER 2017+?"),
    (pedido([{"producto": "fundas", "modelo": "Clia"}]), "caba", "no_disponible", CONFUSION),
    (pedido([{"producto": "otros", "modelo": "techo"}]), "envio", "no_disponible",
     "Este servicio se realiza de forma presencial en CABA y no está disponible para envío."),
    (pedido([{"producto": "fundas"}]), "caba", "requiere_aclaracion", "Confirmá la marca y el modelo del vehículo."),
])
def test_sin_cotizacion_no_manda_nada(p, modalidad, estado, continuacion):
    r, ctx, _ = correr(p, modalidad=modalidad)
    assert ctx.sesion.salientes == []
    assert ctx.sesion.registro("precios") == {}
    assert r["estado"] == estado
    assert r["envio"] == {"estado": "no_corresponde"}
    assert r["cotizacion_enviada"] is False
    assert r["continuacion_obligatoria"] == continuacion


def test_debito_pide_revision_especial():
    r, ctx, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}], metodo="debito"))
    assert ctx.sesion.salientes == []
    assert r["estado"] == "metodo_no_confirmado"
    assert r["requiere_derivacion"] == "revision_especial"
    assert r["continuacion_obligatoria"] == "Ese medio de pago necesita confirmación de Candela."


# --- Validación de entrada y modalidad ----------------------------------------

ENTRADA_INVALIDA = {"estado": "entrada_invalida", "items": [], "totales": None, "mensaje_cotizacion": None,
                    "aclaraciones": [], "envio": {"estado": "no_corresponde"}, "motivo": "pedido_o_contexto_invalido"}


@pytest.mark.parametrize("p", [
    pedido([{"producto": "fundas", "modelo": "Clio"}], extra=1),
    pedido([{"producto": "motos", "modelo": "Gilera"}]),
    pedido([{"producto": "fundas", "modelo": "Clio", "cantidad": 0}]),
    pedido([{"producto": "fundas", "modelo": "Clio", "cantidad": "2"}]),
    pedido([{"producto": "fundas", "modelo": "Clio", "anio": "09"}]),
    pedido([{"producto": "fundas", "modelo": "x" * 161}]),
    pedido([]),
    pedido([{"producto": "cubrevolante"}] * 11),
    pedido(["fundas"]),
    pedido([{"producto": "fundas", "modelo": "Clio"}], tipo="todo"),
    {"consultas": [{"producto": "fundas", "modelo": "Clio"}], "tipo_solicitud": "consulta", "metodo_pago": None},
    "fundas clio",
    None,
])
def test_entrada_invalida_no_lee_ni_manda(p):
    r, ctx, lector = correr(p)
    assert r == ENTRADA_INVALIDA
    assert lector.pedidas == [] and ctx.sesion.salientes == []


def test_contexto_invalido_es_entrada_invalida():
    r, ctx, lector = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]), ultimo=0)
    assert r == ENTRADA_INVALIDA and lector.pedidas == []


def test_normaliza_anio_texto_y_cantidad_con_punto():
    n = normalizar_entrada({"consultas": [{"producto": "Tapicería", "modelo": " Clio  2 ", "anio": " 2012 ",
                                           "cantidad": 2.0}], "modalidad": "CABA", "tipo_solicitud": "Consulta"})
    assert n["ok"]
    assert n["entrada"] == {"consultas": [{"producto": "tapiceria", "cantidad": 2, "modelo": "Clio 2", "anio": 2012}],
                            "modalidad": "caba", "tipo_solicitud": "consulta", "metodo_pago": "transferencia"}
    assert isinstance(n["entrada"]["consultas"][0]["cantidad"], int)


def test_sin_modalidad_confirmada_pregunta_sin_leer():
    r, ctx, lector = correr(pedido([{"producto": "fundas", "modelo": "Clio"}], modalidad="caba"),
                            modalidad="sin_confirmar")
    assert lector.pedidas == [] and ctx.sesion.salientes == []
    assert r["estado"] == "requiere_modalidad"
    assert r["motivo"] == "modalidad_no_confirmada_por_cliente"
    assert r["continuacion_obligatoria"] == ("Hacemos envios a todo el pais y nuestro taller esta situado en CABA. "
                                             "Quisieras la opción de envio o colocarlo en nuestro taller?")
    assert r["instrucciones"] == ("Copiá continuacion_obligatoria literalmente. No se consultó ni envió una "
                                  "cotización. No inventes modalidad ni reintentes en este turno.")


def test_la_modalidad_del_principal_pisa_la_del_modelo():
    r, ctx, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}], metodo="efectivo", modalidad="caba"),
                       modalidad="envio")
    assert r["estado"] == "metodo_no_disponible" and ctx.sesion.salientes == []


# --- Idempotencia, control humano, «borrar» y fallas ---------------------------

def test_mismo_pedido_en_el_mismo_turno_no_se_repite():
    p = pedido([{"producto": "fundas", "modelo": "Clio"}])
    r1, ctx, _ = correr(p)
    r2 = herramienta.ejecutar(p, ctx, leer_hojas=LectorFalso())
    assert len(ctx.sesion.salientes) == 1
    assert r2["envio"] == {"estado": "omitido", "chatwoot_message_id": str(r1["envio"]["chatwoot_message_id"]),
                           "motivo": "solicitud_ya_registrada"}
    assert r2["cotizacion_enviada"] is True and r2["continuacion_obligatoria"] == ""
    # Lo guardado vuelve como de Postgres (jsonb ordena las claves).
    assert r2["items"][0]["medios_disponibles"] == ["cuotas", "efectivo", "transferencia"]


def test_otro_pedido_con_la_misma_solicitud_queda_desconocido():
    r1, ctx, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]))
    r2 = herramienta.ejecutar(pedido([{"producto": "cubrevolante"}]), ctx, leer_hojas=LectorFalso())
    assert len(ctx.sesion.salientes) == 1
    assert r2["envio"]["estado"] == "desconocido"
    assert r2["envio"]["motivo"] == "solicitud_ocupada_o_incompatible"
    assert r2["continuacion_obligatoria"] == ERROR_ENVIO
    assert r2["items"][0]["producto"] == "cubrevolante"


def test_un_turno_nuevo_no_repite_la_misma_cotizacion():
    # Corrección del 20/11 (campaña de pruebas), punto 7. Esta prueba se llamaba
    # «test_un_turno_nuevo_vuelve_a_cotizar» y esperaba 2 mensajes: un turno nuevo volvía a
    # mandar la misma cotización. Ahora, si el texto es igual al de la última aceptada, se omite.
    r1, ctx, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]))
    ctx2 = contexto(sesion=ctx.sesion)
    r2 = herramienta.ejecutar(pedido([{"producto": "fundas", "modelo": "Clio"}]), ctx2, leer_hojas=LectorFalso())
    assert len(ctx.sesion.salientes) == 1
    assert (r2["envio"]["estado"], r2["envio"]["motivo"]) == ("omitido", "cotizacion_ya_enviada")


@pytest.mark.parametrize("etiquetas", [["humano"], [" Humano "], ["vip", "HUMANO"]])
def test_con_humano_no_manda_y_calla(etiquetas):
    sesion = SesionLocal(conversation_id=7, etiquetas=etiquetas)
    r, ctx, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]), ctx=contexto(sesion))
    assert sesion.salientes == []
    assert r["envio"] == {"estado": "control_humano", "motivo": "conversacion_con_humano",
                          "chatwoot_message_id": None, "registro_confirmado": True}
    assert r["continuacion_obligatoria"] == "" and r["cotizacion_enviada"] is False
    assert sesion.registro("precios")[ctx.solicitud_id("precios-v1")]["estado"] == "control_humano"


def test_etiquetas_no_verificables_bloquean():
    sesion = SesionLocal(conversation_id=7, etiquetas=["vip", 3])
    r, _, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]), ctx=contexto(sesion))
    assert sesion.salientes == []
    assert r["envio"]["estado"] == "fallido" and r["envio"]["motivo"] == "control_humano_no_verificable"
    assert r["continuacion_obligatoria"] == ERROR_ENVIO


def test_lote_anterior_a_borrar_no_manda():
    sesion = SesionLocal(conversation_id=7)
    ctx = contexto(sesion)
    sesion.epoca = sesion.nuevo_message_id()  # llegó un «borrar» después del lote
    r, _, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]), ctx=ctx)
    assert sesion.salientes == []
    assert r == {"estado": "control_humano", "motivo": "conversacion_reiniciada", "pausa_tecnica": True,
                 "bot_pausado": None, "asignacion_confirmada": False, "destino": None,
                 "envio": {"estado": "control_humano", "motivo": "conversacion_reiniciada", "chatwoot_message_id": None},
                 "continuacion_obligatoria": "", "registro_confirmado": True, "requiere_revision": False}


def test_si_no_se_puede_leer_la_planilla_es_error_de_consulta():
    r, ctx, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]),
                       lector=LectorFalso(planilla.ErrorPlanilla("no_se_pudo_bajar")))
    assert r == {"estado": "error_consulta", "items": [], "totales": None, "mensaje_cotizacion": None,
                 "aclaraciones": [], "envio": {"estado": "no_corresponde"},
                 "motivo": "no_se_pudo_leer_o_interpretar_planilla"}
    assert ctx.sesion.salientes == []


def test_hoja_que_no_se_entiende_es_error_del_motor():
    def lector(titulos):
        return [{"title": "Fundas a medida", "sheetId": 1, "values": [["nada"], ["CLIO", 1]]}]
    r, ctx, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]), lector=lector)
    assert r["estado"] == "error_consulta"
    assert r["continuacion_obligatoria"] == "Ahora no pude consultar el precio. Esa parte necesita revisión del equipo."
    assert ctx.sesion.salientes == []


def test_si_falla_el_envio_queda_desconocido():
    sesion = SesionLocal(conversation_id=7)

    def mandar_roto(*a, **k):
        raise RuntimeError("se cortó")
    sesion.mandar = mandar_roto
    r, _, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]), ctx=contexto(sesion))
    assert r["envio"] == {"estado": "desconocido", "motivo": "envio_no_confirmado", "chatwoot_message_id": None,
                          "registro_confirmado": True}
    assert r["continuacion_obligatoria"] == ERROR_ENVIO


# --- Formato y lectura de la planilla ------------------------------------------

@pytest.mark.parametrize("valor, texto", [
    (999, "$999"), (1234, "$1.234"), (150000, "$150.000"), (120000.5, "$120.000,50"),
    (1234567.25, "$1.234.567,25"), (0.5, "$0,50"),
])
def test_dinero_como_es_ar(valor, texto):
    assert dinero(valor) == texto


@pytest.mark.parametrize("valor, texto", [(5.0, "5"), (1e21, "1e+21"), (0.000001, "0.000001"), (1e-7, "1e-7"),
                                          (1.5, "1.5"), (2009, "2009")])
def test_numeros_como_string_de_js(valor, texto):
    assert js_numero(valor) == texto


def _xlsx(hojas: dict[str, list[list]]) -> bytes:
    from openpyxl import Workbook
    libro = Workbook()
    libro.remove(libro.active)
    for titulo, filas in hojas.items():
        hoja = libro.create_sheet(titulo)
        for fila in filas:
            hoja.append(fila)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def test_xlsx_queda_como_batchget():
    contenido = _xlsx({
        "Otros": [["OTROS"], [None, None], ["CUBRE VOLANTE", 20000, 22000.0, None, None],
                  ["FECHA", dt.datetime(2026, 11, 15, 12)], [None]],
        "Cobertores de caja ": [["x"]],
    })
    [hoja] = planilla.hojas_desde_xlsx(contenido, ["Otros", "Otros"])
    assert hoja["title"] == "Otros" and hoja["sheetId"] == 59879218
    assert hoja["values"] == [["OTROS"], [], ["CUBRE VOLANTE", 20000, 22000], ["FECHA", 46341.5]]
    assert isinstance(hoja["values"][2][2], int)
    assert hoja["range"] == "'Otros'!A1:C4"
    [caja] = planilla.hojas_desde_xlsx(contenido, ["Cobertores de caja "])
    assert caja["values"] == [["x"]]


@pytest.mark.parametrize("titulos, motivo", [
    (["ESPUMAS"], "estructura_de_hojas_cambio"),
    (["Hoja rara"], "hoja_no_permitida"),
    ([], "hojas_invalidas"),
])
def test_xlsx_controla_las_hojas(titulos, motivo):
    contenido = _xlsx({"Otros": [["OTROS"]]})
    with pytest.raises(planilla.ErrorPlanilla, match=motivo):
        planilla.hojas_desde_xlsx(contenido, titulos)


def test_xlsx_respeta_el_tope_de_columnas():
    contenido = _xlsx({"Otros": [["x"] * 61]})
    with pytest.raises(planilla.ErrorPlanilla, match="dimensiones_fuera_de_limite"):
        planilla.hojas_desde_xlsx(contenido, ["Otros"])


def test_solo_sigue_redirecciones_de_google():
    import httpx
    assert planilla._host_permitido(httpx.URL("https://docs.google.com/x"))
    assert planilla._host_permitido(httpx.URL("https://doc-0c-ak-sheets.googleusercontent.com/x"))
    assert not planilla._host_permitido(httpx.URL("http://docs.google.com/x"))
    assert not planilla._host_permitido(httpx.URL("https://evil.com/googleusercontent.com"))
    assert not planilla._host_permitido(httpx.URL("https://googleusercontent.com.evil.com/x"))


# --- Pedido de Mateo del 17/11: de a una pregunta, primero el modelo ----------

def test_sin_modelo_ni_modalidad_pregunta_primero_el_modelo():
    r, ctx, lector = correr(pedido([{"producto": "fundas"}]), modalidad="sin_confirmar")
    assert r["estado"] == "requiere_aclaracion"
    assert r["continuacion_obligatoria"] == "Confirmá la marca y el modelo del vehículo."
    assert ctx.sesion.salientes == [] and lector.pedidas == []


def test_con_modelo_y_sin_modalidad_pregunta_solo_la_modalidad():
    r, _, _ = correr(pedido([{"producto": "fundas", "modelo": "Clio"}]), modalidad="sin_confirmar")
    assert r["estado"] == "requiere_modalidad"
    assert r["continuacion_obligatoria"] == ("Hacemos envios a todo el pais y nuestro taller esta situado en CABA. "
                                             "Quisieras la opción de envio o colocarlo en nuestro taller?")


# --- Pedido de Mateo del 20/11: la tapicería es solo en el taller de CABA -----
# No se ofrece envío: buscar_precio no pregunta «envío o taller» y cotiza para el taller.

def _modalidad_cotizada(ctx):
    """La modalidad con la que quedó anotado el único pedido del turno."""
    (fila,) = ctx.sesion.registro("precios").values()
    return fila["pedido"]["modalidad"]


def test_tapiceria_sin_modalidad_cotiza_para_el_taller_sin_preguntar():
    r, ctx, _ = correr(pedido([{"producto": "tapiceria", "modelo": "Etios"}]), modalidad="sin_confirmar")
    assert r["estado"] == "cotizado" and r["cotizacion_enviada"] is True
    assert [g.tipo for g in ctx.sesion.salientes] == ["cotizacion"]
    assert _modalidad_cotizada(ctx) == "caba"


def test_tapiceria_no_arrastra_un_envio_elegido_antes():
    """Si antes eligió envío para otro producto, la tapicería igual se cotiza para el taller."""
    r, ctx, _ = correr(pedido([{"producto": "Tapicería", "modelo": "Etios"}]), modalidad="envio")
    assert r["estado"] == "cotizado" and r["cotizacion_enviada"] is True
    assert _modalidad_cotizada(ctx) == "caba"


def test_tapiceria_sin_modelo_pide_el_modelo_y_no_la_modalidad():
    r, ctx, _ = correr(pedido([{"producto": "tapiceria"}]), modalidad="sin_confirmar")
    assert r["estado"] == "requiere_aclaracion"
    assert r["continuacion_obligatoria"] == "Confirmá la marca y el modelo del vehículo."
    assert ctx.sesion.salientes == []


def test_tapiceria_junto_con_fundas_sigue_preguntando_la_modalidad():
    """La regla vale para pedidos de tapicería sola: las fundas sí pueden ir por envío."""
    consultas = [{"producto": "tapiceria", "modelo": "Etios"}, {"producto": "fundas", "modelo": "Clio"}]
    r, ctx, _ = correr(pedido(consultas, tipo="comparacion"), modalidad="sin_confirmar")
    assert r["estado"] == "requiere_modalidad" and ctx.sesion.salientes == []


# =============================================================================
# Corrección del 20/11 (campaña de pruebas)
# =============================================================================
# Filas con la forma y los nombres de la planilla oficial que dieron problemas en la
# campaña de pruebas. Los importes son inventados.

_ENC = ["Marca y Modelo de vehículo", "Juego completo (5 plazas)", "", "2 ASIENTOS INDIVIDUALES", "",
        "BUTACA Y BUTACON", "", "7 ASIENTOS", ""]
_MEDIOS = ["", "EFECTIVO", "TRANF", "EFECTIVO", "TRANF", "EFECTIVO", "TRANF", "EFECTIVO", "TRANF"]
_ENC_TAPICERIA = ["Marca y Modelo de vehículo", "5 PLAZAS", "", "2 PLAZAS", "", "1 BUTACA Y BUTACON", "",
                  "7 PLAZAS", ""]
PLANILLA_CAMPANA = [
    {"title": "Fundas a medida", "sheetId": 877828453, "values": [
        ["RENAULT"], _ENC, _MEDIOS,
        ["DUSTER ", 160000, 170000, 90000, 95000],
        ["DUSTER 2017+", 165000, 175000, 92000, 97000],
        ["CHEVROLET"], _ENC, _MEDIOS,
        ["ONIX GEN 1 ", 141000, 151000, 81000, 91000],
        ["ONIX GEN 2 (2020+)", 142000, 152000, 82000, 92000],
        ["VOLKSWAGEN"], _ENC, _MEDIOS,
        ["SURAN 2017-2019", 143000, 153000, 83000, 93000],
        ["SURAN 2009", 144000, 154000, 84000, 94000],
        ["Saveiro DOBLE CABINA", 145000, 155000, 85000, 95000],
        ["Saveiro cross", 146000, 156000, 86000, 96000],
        ["PEUGEOT"], _ENC, _MEDIOS,
        ["208 GT ", 147000, 157000, 87000, 97000],
        [208, 148000, 158000, 88000, 98000],  # en la planilla esta celda es un número
        ["PARTNER", 149000, 159000, 89000, 99000],
        ["TOYOTA"], _ENC, _MEDIOS,
        ["HILUX CABINA DOBLE - 2005/2015", 200000, 210000, 100000, 110000],
        ["HILUX 2026", 201000, 211000, 101000, 111000],
        ["HILUX CABINA SIMPLE ", "-", "-", 102000, 112000, 62000, 72000],  # sin juego de 5 plazas
        ["SW4 2010", 203000, 213000, 103000, 113000],
    ]},
    {"title": "TIPO TAPIZADO", "sheetId": 613213257, "values": [
        ["TOYOTA"], _ENC[:5], _MEDIOS[:5],
        ["HILUX 2017", 300000, 310000, 150000, 160000],
        ["HILUX 2013", 301000, 311000, 151000, 161000],
    ]},
    {"title": "TAPICERIA", "sheetId": 972378170, "values": [
        ["VOLKSWAGEN"], _ENC_TAPICERIA, _MEDIOS,
        ["GOL TREND", 400000, 440000, 200000, 220000, 250000, 275000],
        ["PEUGEOT"], _ENC_TAPICERIA, _MEDIOS,
        ["BOXER", "", "", 210000, 230000, 260000, 285000],
    ]},
    {"title": "Termoformadas", "sheetId": 0, "values": [
        ["Marca", "Vehículo/Modelo", "EFECTIVO", "TRANSFERENCIA"],
        ["Fiat", "Fiat Argo - Cronos - Pulse (Todos) ", 30000, 33000],
        ["Ford", "Ford Ranger 2023+", 60000, 65000],
        ["Ford", "Ford Ranger Cabina Simple 2012 +", 40000, 44000],
        ["Ford", "Ford Ranger 2012 hasta 2022", 50000, 55000],
    ]},
    {"title": "ESPUMAS", "sheetId": 1953604758, "values": [
        ["RECAMBIO DE GOMA ESPUMA"],
        ["Vehiculos", "RESPALDO", "", "ASIENTO"],
        ["", "EFECTIVO", "TRANSFERENCIA", "EFECTIVO", "TRANSFERENCIA"],
        ["KANGOO Viejo y Nuevo ( Que años? ", 10000, 11000, 12000, 13000],  # nota interna sin cerrar
    ]},
    {"title": "Otros", "sheetId": 59879218, "values": [
        ["OTROS ACCESORIOS"],
        ["Producto/servicio", "Valor EFECTIVO", "TRANSFERENCIA + 21%", "POSNET o CUOTAS 21% + 9%"],
        [],
        ["CUBRE VOLANTE", 20000, 22000, 25000],
        ["PANELES DE PUERTA", 70000, 77000, 85000],
        ["RELLENO", 50000, 55000, 60000],
        ["ESPUMA DE ASIENTOS", 80000, 88000, 96000],  # no hay tapizado de techo
    ]},
]
SIN_PRECIO_DE_LISTA = "La lista no tiene un precio numérico disponible para esta configuración y modalidad."
ANIO_NO_CUBIERTO = "El año indicado no está cubierto por las variantes publicadas."
CONFIGURACION_SIN_CONFIRMAR = "La configuración indicada necesita confirmación para este producto."


def lector_campana(titulos):
    return [copy.deepcopy(h) for h in PLANILLA_CAMPANA if h["title"] in titulos]


def campana(consultas, sesion=None, modalidad="caba", ctx=None, **extra):
    """buscar_precio sobre la planilla de la campaña.

    Cada llamada es un turno nuevo de la conversación de `sesion`, salvo que se pase el `ctx`
    de una llamada anterior (otra llamada dentro del mismo turno).
    """
    ctx = ctx or contexto(sesion, modalidad=modalidad)
    return herramienta.ejecutar(pedido(consultas, **extra), ctx, leer_hojas=lector_campana), ctx


def item_campana(consulta, modalidad="caba", **kw):
    """El motor solo sobre la planilla de la campaña: el ítem resuelto de una consulta."""
    n = normalizar_entrada({"consultas": [consulta], "modalidad": modalidad, "tipo_solicitud": "consulta"})
    assert n["ok"], n["errores"]
    hojas = [h for h in PLANILLA_CAMPANA if h["title"] in n["hojas"]]
    return cotizar(n["entrada"], hojas, None, **kw)["items"][0]


def textos(ctx):
    return [g.texto for g in ctx.sesion.salientes]


# --- Punto 8: el nombre que ve el cliente va sin la nota interna de la planilla ---------------

from agente.f7.precios.motor import modelo_legible  # noqa: E402
from agente.f7.precios.salida_agente import resumir_para_agente  # noqa: E402


def test_la_cotizacion_no_muestra_la_nota_interna_de_la_planilla():
    r, ctx = campana([{"producto": "espuma", "modelo": "Kangoo", "configuracion": "asiento"}])
    assert textos(ctx) == ["La espuma de asiento para Kangoo Viejo y Nuevo sale $13.000 por transferencia."]
    assert r["estado"] == "cotizado"
    # Al modelo le sigue llegando el nombre tal cual está en la planilla.
    assert r["items"][0]["modelo"] == "KANGOO Viejo y Nuevo ( Que años?"


@pytest.mark.parametrize("fila, legible", [
    ("KANGOO Viejo y Nuevo ( Que años? ", "Kangoo Viejo y Nuevo"),  # paréntesis sin cerrar
    ("KANGOO (Que años?) Viejo", "Kangoo Viejo"),                   # nota con pregunta
    ("ONIX GEN 2 (2020+)", "Onix Gen 2 (2020+)"),                   # como hoy
    ("Fiat Argo - Cronos - Pulse (Todos) ", "Fiat Argo - Cronos - Pulse (Todos)"),
    ("S-10 ( CABINA SIMPLE )", "S-10 ( Cabina Simple )"),
    ("Juego completo (5 plazas)", "Juego Completo (5 Plazas)"),     # los paréntesis cerrados no se tocan
])
def test_el_nombre_legible_corta_solo_la_nota_interna(fila, legible):
    assert modelo_legible(fila) == legible


def test_las_opciones_ofrecidas_tampoco_muestran_la_nota_interna():
    resultado = {"estado": "requiere_aclaracion", "items": [{
        "producto": "espuma", "modelo": "Kangoo", "estado": "requiere_aclaracion", "cantidad": 1, "precios": {},
        "motivo": "Encontré más de una variante. Confirmá cuál corresponde a tu vehículo.",
        "opciones": [{"modelo": "KANGOO Viejo y Nuevo ( Que años?"}, {"modelo": "KANGOO 2020"}]}]}
    r = resumir_para_agente(resultado, {"estado": "no_corresponde"})
    assert r["continuacion_obligatoria"] == ("Para espuma, ¿cuál de estas opciones corresponde a tu vehículo: "
                                             "KANGOO Viejo y Nuevo o KANGOO 2020?")


# --- Punto 10: en alfombra, «habitáculo» o «completa» no eligen una fila -----------------------

ALFOMBRA_CRONOS = ("La alfombra termoformada para Fiat Argo - Cronos - Pulse (Todos) sale $33.000 por "
                   "transferencia.")


@pytest.mark.parametrize("configuracion", ["habitaculo", "Habitáculo", "completa", "completo", "juego", "todas",
                                           "juego completo", "juego de habitáculo"])
def test_alfombra_ignora_la_configuracion_que_repite_el_producto(configuracion):
    r, ctx = campana([{"producto": "alfombra", "modelo": "Cronos", "configuracion": configuracion}])
    assert textos(ctx) == [ALFOMBRA_CRONOS]
    assert r["estado"] == "cotizado"


def test_alfombra_sigue_filtrando_por_una_variante_de_verdad():
    _, ctx = campana([{"producto": "alfombra", "modelo": "Ranger", "anio": 2015, "configuracion": "cabina simple"}])
    assert textos(ctx) == ["La alfombra termoformada para Ford Ranger Cabina Simple 2012 + sale $44.000 por "
                           "transferencia."]


def test_alfombra_con_una_variante_que_no_esta_no_se_cotiza():
    # «trasera» no está en ninguna fila de Cronos y no se ignora (cómo sigue, en el punto 5).
    item = item_campana({"producto": "alfombra", "modelo": "Cronos", "configuracion": "trasera"})
    assert item["estado"] == "requiere_aclaracion" and item["motivo"] == CONFIGURACION_SIN_CONFIRMAR


def test_la_configuracion_que_repite_el_producto_solo_se_ignora_en_alfombra():
    item = item_campana({"producto": "otros", "modelo": "paneles de puerta", "configuracion": "completo"})
    assert item["estado"] == "requiere_aclaracion" and item["motivo"] == CONFIGURACION_SIN_CONFIRMAR


# --- Punto 9: techo, paneles o relleno pedidos como «tapiceria» van por «Otros» ---------------

NO_ESTA_EN_LA_LISTA = "No encontré ese modelo o producto en la lista consultada."
SOLO_EN_EL_TALLER = "Este servicio se realiza de forma presencial en CABA y no está disponible para envío."
TECHO = [{"producto": "tapiceria", "modelo": "Gol Trend", "configuracion": "techo"}]


@pytest.mark.parametrize("consulta, trabajo", [
    ({"producto": "tapiceria", "modelo": "Gol Trend", "configuracion": "techo"}, "tapizado de techo"),
    ({"producto": "Tapicería", "modelo": "techo de Gol Trend"}, "tapizado de techo"),
    ({"producto": "tapiceria", "configuracion": "paneles"}, "paneles de puerta"),
    ({"producto": "tapiceria", "modelo": "Gol Trend", "configuracion": "panel de puerta"}, "paneles de puerta"),
    ({"producto": "tapiceria", "modelo": "Gol Trend", "configuracion": "puertas"}, "paneles de puerta"),
    ({"producto": "tapiceria", "modelo": "Gol Trend", "configuracion": "relleno"}, "relleno"),
    ({"producto": "tapiceria", "modelo": "Gol Trend", "configuracion": "volante"}, "tapizado de volante"),
])
def test_un_trabajo_que_no_es_de_butacas_pedido_como_tapiceria_pasa_a_otros(consulta, trabajo):
    n = normalizar_entrada({"consultas": [{**consulta, "anio": 2015, "cantidad": 2}], "modalidad": "caba",
                            "tipo_solicitud": "consulta"})
    assert n["ok"] and n["hojas"] == ["Otros"]
    assert n["entrada"]["consultas"] == [{"producto": "otros", "cantidad": 2, "modelo": trabajo}]


@pytest.mark.parametrize("consulta", [
    {"producto": "tapiceria", "modelo": "Gol Trend"},
    {"producto": "tapiceria", "modelo": "Gol Trend", "configuracion": "2 plazas"},
    {"producto": "tapiceria", "modelo": "Gol Trend 5 puertas"},   # las puertas del auto no son paneles
    {"producto": "tapiceria", "modelo": "208 techo panorámico"},  # ni el techo del auto es un trabajo
    {"producto": "fundas", "modelo": "Gol Trend", "configuracion": "techo"},  # vale solo para tapicería
])
def test_lo_demas_sigue_con_su_producto(consulta):
    n = normalizar_entrada({"consultas": [consulta], "modalidad": "caba", "tipo_solicitud": "consulta"})
    assert n["ok"] and n["entrada"]["consultas"][0]["producto"] == consulta["producto"]


def test_tapizar_el_techo_no_pregunta_por_plazas_y_sale_por_el_camino_de_otros():
    pedidas = []

    def lector(titulos):
        pedidas.append(list(titulos))
        return lector_campana(titulos)
    ctx = contexto()
    r = herramienta.ejecutar(pedido(TECHO), ctx, leer_hojas=lector)
    assert pedidas == [["Otros"]]
    assert r["estado"] == "no_disponible" and ctx.sesion.salientes == []
    # La hoja real no tiene tapizado de techo. Desde el 21/11 no va el texto de sistema («No encontré
    # ese modelo o producto en la lista consultada»): pasa a una persona.
    assert r["continuacion_obligatoria"] == "" and r["requiere_derivacion"] == "revision_especial"
    assert (r["items"][0]["producto"], r["items"][0]["modelo"]) == ("otros", "tapizado de techo")


def test_si_el_techo_esta_en_la_hoja_se_cotiza_como_cualquier_otro():
    _, ctx, lector = correr(pedido([{"producto": "tapiceria", "modelo": "Etios", "configuracion": "techo"}]))
    assert lector.pedidas == [["Otros"]]
    assert [g.texto for g in ctx.sesion.salientes] == ["Tapizado de Techo sale $99.000 por transferencia."]


def test_paneles_pedidos_como_tapiceria_se_cotizan_desde_otros():
    _, ctx = campana([{"producto": "tapiceria", "modelo": "Gol Trend", "configuracion": "paneles de puerta"}])
    assert textos(ctx) == ["Paneles de Puerta sale $77.000 por transferencia."]


def test_un_pedido_de_techo_no_cuenta_como_tapiceria_de_butacas():
    # El techo sigue el camino de «otros». Desde el 21/11, sin modalidad elegida no pregunta «envío o
    # taller» (es un trabajo solo de taller); si el cliente eligió envío, le avisa que es presencial.
    r, _ = campana(TECHO, modalidad="sin_confirmar")
    assert r["estado"] != "requiere_modalidad"
    assert r["continuacion_obligatoria"] != herramienta.PREGUNTA_MODALIDAD
    r, _ = campana(TECHO, modalidad="envio")
    assert r["estado"] == "no_disponible" and r["continuacion_obligatoria"] == SOLO_EN_EL_TALLER


def test_un_pedido_de_techo_sin_vehiculo_no_pide_el_modelo():
    r, _ = campana([{"producto": "tapiceria", "configuracion": "techo"}], modalidad="sin_confirmar")
    # Como en «otros», no hace falta el vehículo; y desde el 21/11 tampoco la modalidad.
    assert r.get("motivo") != "modelo_no_informado" and r["estado"] != "requiere_modalidad"


def test_la_tapiceria_de_butacas_se_sigue_cotizando_para_el_taller():
    r, ctx = campana([{"producto": "tapiceria", "modelo": "Gol Trend"}], modalidad="envio")
    assert textos(ctx) == ["El trabajo de tapicería para Gol Trend (5 plazas) sale $440.000 por transferencia."]
    assert _modalidad_cotizada(ctx) == "caba"


# --- Punto 5: lo que el cliente no puede resolver pasa a una persona --------------------------
# El resumen para el modelo ya no trae el texto de sistema: pide la derivación y la
# continuación va vacía (el control de salida pasa la conversación a una persona).

def pasa_a_una_persona(r):
    return r.get("requiere_derivacion") == "revision_especial" and r["continuacion_obligatoria"] == ""


@pytest.mark.parametrize("consulta", [
    {"producto": "fundas", "modelo": "SW4", "anio": 2020},             # una sola variante: SW4 2010
    {"producto": "fundas", "modelo": "SW4 2020"},                      # el año escrito junto al modelo
    {"producto": "fundas", "modelo": "Suran", "anio": 2012},           # SURAN 2017-2019 y SURAN 2009
    {"producto": "tipo tapizado", "modelo": "Hilux", "anio": 2020},    # HILUX 2017 y HILUX 2013
])
def test_anio_no_cubierto_pasa_a_una_persona(consulta):
    r, ctx = campana([consulta])
    assert pasa_a_una_persona(r)
    assert r["estado"] == "requiere_aclaracion" and r["envio"] == {"estado": "no_corresponde"}
    assert r["cotizacion_enviada"] is False and ctx.sesion.salientes == []
    assert r["items"][0]["motivo"] == ANIO_NO_CUBIERTO  # queda como dato para el modelo
    assert list(r) == ["estado", "items", "envio", "consultado_en", "metodo_pago", "pregunta_comercial_incluida",
                       "requiere_derivacion", "cotizacion_enviada", "continuacion_obligatoria", "instrucciones"]


def test_sin_el_anio_se_sigue_pidiendo_como_antes():
    r, _ = campana([{"producto": "fundas", "modelo": "SW4"}])
    assert "requiere_derivacion" not in r
    assert r["continuacion_obligatoria"] == "De qué año es tu vehículo?"  # texto del 21/11


def test_configuracion_que_no_coincide_con_nada_pasa_a_una_persona():
    r, ctx = campana([{"producto": "alfombra", "modelo": "Cronos", "configuracion": "trasera"}])
    assert pasa_a_una_persona(r) and ctx.sesion.salientes == []
    assert r["estado"] == "requiere_aclaracion" and r["items"][0]["motivo"] == CONFIGURACION_SIN_CONFIRMAR


def test_sin_precio_numerico_pasa_a_una_persona():
    # HILUX CABINA SIMPLE no tiene juego de 5 plazas: esas celdas dicen «-».
    r, ctx = campana([{"producto": "fundas", "modelo": "Hilux cabina simple"}])
    assert pasa_a_una_persona(r) and ctx.sesion.salientes == []
    assert r["estado"] == "no_disponible"
    assert (r["items"][0]["modelo"], r["items"][0]["motivo"]) == ("HILUX CABINA SIMPLE", SIN_PRECIO_DE_LISTA)


PARTNER_Y_SW4 = [{"producto": "fundas", "modelo": "Partner"}, {"producto": "fundas", "modelo": "SW4", "anio": 2020}]


def test_si_otro_item_se_cotizo_la_cotizacion_parcial_se_manda_igual():
    r, ctx = campana(PARTNER_Y_SW4)
    assert textos(ctx) == ["El juego completo de fundas a medida para Partner (5 plazas) sale $159.000 por "
                           "transferencia.\n\nFundas a medida para SW4: pendiente de confirmación."]
    assert r["estado"] == "parcial" and r["envio"]["estado"] == "aceptado" and r["cotizacion_enviada"] is True
    assert pasa_a_una_persona(r)


def test_si_el_envio_de_la_parcial_no_se_confirma_va_el_aviso_de_siempre():
    sesion = SesionLocal(conversation_id=7)

    def mandar_roto(*a, **k):
        raise RuntimeError("se cortó")
    sesion.mandar = mandar_roto
    r, _ = campana(PARTNER_Y_SW4, sesion=sesion)
    assert r["envio"]["estado"] == "desconocido" and r["continuacion_obligatoria"] == ERROR_ENVIO
    assert "requiere_derivacion" not in r


@pytest.mark.parametrize("consultas, modalidad, continuacion", [
    ([{"producto": "fundas", "modelo": "Batimovil"}], "caba", CONFUSION),
    ([{"producto": "fundas", "modelo": "Renault Batimovil"}], "caba", SIN_MEDIDAS),
    ([{"producto": "otros", "modelo": "tapizado de techo"}], "envio", SOLO_EN_EL_TALLER),
    ([{"producto": "espuma", "modelo": "Kangoo"}], "caba",
     "Para espuma, ¿cuál de estas opciones corresponde a tu vehículo: asiento o respaldo?"),
    ([{"producto": "fundas", "modelo": "Suran"}], "caba",
     "Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: SURAN 2017-2019 o SURAN 2009?"),
])
def test_los_demas_textos_le_siguen_llegando_al_cliente(consultas, modalidad, continuacion):
    r, _ = campana(consultas, modalidad=modalidad)
    assert "requiere_derivacion" not in r
    assert r["continuacion_obligatoria"] == continuacion


# --- Punto 2: si el cliente dio el año, el año decide entre las opciones ----------------------

@pytest.mark.parametrize("anio, texto", [
    (2021, "El juego completo de fundas a medida para Onix Gen 2 (2020+) (5 plazas) sale $152.000 por "
           "transferencia."),
    (2015, "El juego completo de fundas a medida para Onix Gen 1 (5 plazas) sale $151.000 por transferencia."),
])
def test_el_anio_decide_la_generacion(anio, texto):
    r, ctx = campana([{"producto": "fundas", "modelo": "Onix", "anio": anio}])
    assert textos(ctx) == [texto] and r["estado"] == "cotizado"


def test_sin_el_anio_se_siguen_ofreciendo_las_dos_generaciones():
    r, ctx = campana([{"producto": "fundas", "modelo": "Onix"}])
    assert ctx.sesion.salientes == [] and "requiere_derivacion" not in r
    assert r["continuacion_obligatoria"] == ("Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: "
                                             "ONIX GEN 1 o ONIX GEN 2 (2020+)?")


@pytest.mark.parametrize("anio, fila", [(2010, "DUSTER"), (2019, "DUSTER 2017+")])
def test_la_fila_sin_anios_sigue_siendo_la_base_frente_a_la_que_tiene_anios(anio, fila):
    item = item_campana({"producto": "fundas", "modelo": "Duster", "anio": anio})
    assert (item["estado"], item["modelo"]) == ("cotizado", fila)


# «ecosport kinetic» no cierra con una sola fila: el buscador ofrece las tres.
HOJA_ECO = {"title": "Fundas a medida", "sheetId": 877828453, "values": [
    ["FORD"], _ENC[:3], _MEDIOS[:3],
    ["ECO SPORT 2003-2013", 100000, 110000],
    ["ECO KINECTIC 2013+", 200000, 220000],
    ["ECO KINECTIC 2000-2002", 300000, 330000],
]}


def item_eco(anio=None):
    consulta = {"producto": "fundas", "modelo": "ecosport kinetic", **({"anio": anio} if anio else {})}
    n = normalizar_entrada({"consultas": [consulta], "modalidad": "caba", "tipo_solicitud": "consulta"})
    assert n["ok"], n["errores"]
    return cotizar(n["entrada"], [HOJA_ECO], None)["items"][0]


def test_con_opciones_y_sin_anio_se_ofrecen_todas():
    item = item_eco()
    assert item["estado"] == "requiere_aclaracion"
    assert item["opciones"] == [{"modelo": "ECO SPORT 2003-2013"}, {"modelo": "ECO KINECTIC 2013+"},
                                {"modelo": "ECO KINECTIC 2000-2002"}]


@pytest.mark.parametrize("anio, fila", [(2008, "ECO SPORT 2003-2013"), (2015, "ECO KINECTIC 2013+"),
                                        (2001, "ECO KINECTIC 2000-2002")])
def test_con_opciones_el_anio_descarta_y_si_queda_una_sola_se_elige(anio, fila):
    item = item_eco(anio)
    assert (item["estado"], item["modelo"]) == ("cotizado", fila)


def test_con_opciones_si_el_anio_deja_mas_de_una_se_ofrecen_solo_esas():
    item = item_eco(2013)
    assert item["estado"] == "requiere_aclaracion" and "requiere_derivacion" not in item
    assert item["opciones"] == [{"modelo": "ECO SPORT 2003-2013"}, {"modelo": "ECO KINECTIC 2013+"}]


def test_con_opciones_si_el_anio_las_descarta_todas_es_anio_no_cubierto():
    item = item_eco(1990)
    assert item["motivo"] == ANIO_NO_CUBIERTO and item["requiere_derivacion"] == "revision_especial"


# --- Punto 3: no elegir una variante que contradice lo que dijo el cliente --------------------

def test_saveiro_cabina_simple_no_cotiza_la_doble_cabina():
    r, ctx = campana([{"producto": "fundas", "modelo": "Saveiro CABINA SIMPLE"}])
    assert ctx.sesion.salientes == [] and "requiere_derivacion" not in r
    assert r["estado"] == "no_disponible" and r["continuacion_obligatoria"] == SIN_MEDIDAS


@pytest.mark.parametrize("consulta", [
    {"producto": "fundas", "modelo": "Saveiro"},
    {"producto": "fundas", "modelo": "Saveiro", "anio": 1997},
])
def test_saveiro_a_secas_ofrece_las_dos_variantes(consulta):
    r, ctx = campana([consulta])
    assert ctx.sesion.salientes == [] and "requiere_derivacion" not in r
    assert r["continuacion_obligatoria"] == ("Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: "
                                             "Saveiro DOBLE CABINA o Saveiro cross?")


@pytest.mark.parametrize("modelo, texto", [
    ("Saveiro doble cabina", "El juego completo de fundas a medida para Saveiro Doble Cabina (5 plazas) sale "
                             "$155.000 por transferencia."),
    ("Saveiro cross", "El juego completo de fundas a medida para Saveiro Cross (5 plazas) sale $156.000 por "
                      "transferencia."),
])
def test_saveiro_con_la_variante_nombrada_se_cotiza(modelo, texto):
    _, ctx = campana([{"producto": "fundas", "modelo": modelo}])
    assert textos(ctx) == [texto]


def item_de(hoja, consulta):
    """El motor solo sobre una hoja armada para la prueba."""
    n = normalizar_entrada({"consultas": [consulta], "modalidad": "caba", "tipo_solicitud": "consulta"})
    assert n["ok"], n["errores"]
    return cotizar(n["entrada"], [hoja], None)["items"][0]


def test_en_alfombra_la_cabina_llega_en_la_configuracion():
    hoja = {"title": "Termoformadas", "sheetId": 0, "values": [
        ["Marca", "Vehículo/Modelo", "EFECTIVO", "TRANSFERENCIA"],
        ["Toyota", "Toyota Hilux Cabina Simple", 40000, 44000],
        ["Toyota", "Toyota Hilux Cabina Doble", 50000, 55000]]}
    item = item_de(hoja, {"producto": "alfombra", "modelo": "Hilux", "configuracion": "cabina simple"})
    assert (item["estado"], item["modelo"]) == ("cotizado", "Toyota Hilux Cabina Simple")
    # Sin nombrar la cabina, se ofrecen las dos.
    item = item_de(hoja, {"producto": "alfombra", "modelo": "Hilux"})
    assert item["estado"] == "requiere_aclaracion"
    assert item["opciones"] == [{"modelo": "Toyota Hilux Cabina Simple"}, {"modelo": "Toyota Hilux Cabina Doble"}]


def test_en_alfombra_la_cabina_coincide_aunque_la_planilla_la_escriba_al_reves():
    # La planilla escribe «DOBLE CABINA» y «CABINA SIMPLE»; el modelo manda «cabina doble».
    hoja = {"title": "Termoformadas", "sheetId": 0, "values": [
        ["Marca", "Vehículo/Modelo", "EFECTIVO", "TRANSFERENCIA"],
        ["Volkswagen", "Volkswagen Saveiro Doble Cabina", 40000, 44000],
        ["Volkswagen", "Volkswagen Saveiro Cabina Simple", 50000, 55000]]}
    item = item_de(hoja, {"producto": "alfombra", "modelo": "Saveiro", "configuracion": "cabina doble"})
    assert (item["estado"], item["modelo"]) == ("cotizado", "Volkswagen Saveiro Doble Cabina")
    # Con algo más que la cabina, la configuración sigue siendo un filtro por el nombre.
    item = item_de(hoja, {"producto": "alfombra", "modelo": "Saveiro", "configuracion": "cabina doble trasera"})
    assert item["motivo"] == CONFIGURACION_SIN_CONFIRMAR


def test_alfombra_con_una_cabina_que_la_fila_no_nombra_pasa_a_una_persona():
    # Cronos no tiene filas por cabina: «cabina simple» es una configuración que no coincide con nada.
    r, _ = campana([{"producto": "alfombra", "modelo": "Cronos", "configuracion": "cabina simple"}])
    assert pasa_a_una_persona(r) and r["items"][0]["motivo"] == CONFIGURACION_SIN_CONFIRMAR


def test_en_fundas_la_cabina_en_la_configuracion_tambien_elige_la_fila():
    # «cabina simple» no es una cobertura: se pregunta cuál, entre las de esa fila.
    r, _ = campana([{"producto": "fundas", "modelo": "Hilux", "configuracion": "cabina simple"}])
    assert r["continuacion_obligatoria"] == ("Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: "
                                             "2 plazas o butaca y butacón?")


# --- Punto 4: no elegir por descarte una variante que el cliente no pidió ---------------------

@pytest.mark.parametrize("consulta", [
    {"producto": "fundas", "modelo": "Hilux", "anio": 2020},
    {"producto": "fundas", "modelo": "HILUX 2017"},                # copió la variante de otra hoja
    {"producto": "fundas", "modelo": "HILUX 2017", "anio": 2020},  # vale el año que dio el cliente
])
def test_hilux_de_un_anio_que_no_esta_no_se_cotiza_como_cabina_simple(consulta):
    # HILUX CABINA SIMPLE no tiene años en el nombre, pero el cliente no pidió cabina simple.
    r, ctx = campana([consulta])
    assert pasa_a_una_persona(r) and ctx.sesion.salientes == []
    assert r["items"][0]["motivo"] == ANIO_NO_CUBIERTO


def test_si_el_anio_del_cliente_no_es_el_escrito_en_el_modelo_vale_el_del_cliente():
    item = item_campana({"producto": "fundas", "modelo": "Duster 2017", "anio": 2010})
    assert (item["estado"], item["modelo"]) == ("cotizado", "DUSTER")


def test_hilux_cabina_simple_es_esa_fila():
    _, ctx = campana([{"producto": "fundas", "modelo": "Hilux cabina simple", "configuracion": "2 plazas"}])
    assert textos(ctx) == ["El juego de fundas a medida para Hilux Cabina Simple (2 plazas) sale $112.000 por "
                           "transferencia."]


def test_hilux_del_anio_de_la_fila_general_es_esa_fila():
    _, ctx = campana([{"producto": "fundas", "modelo": "Hilux", "anio": 2026}])
    assert textos(ctx) == ["El juego completo de fundas a medida para Hilux 2026 (5 plazas) sale $211.000 por "
                           "transferencia."]


@pytest.mark.parametrize("anio, ofrece", [
    (None, "HILUX CABINA DOBLE - 2005/2015 o HILUX 2026 o HILUX CABINA SIMPLE"),
    # 2015 lo cubre la doble cabina, pero el cliente no dijo la cabina: la simple sigue en pie.
    (2015, "HILUX CABINA DOBLE - 2005/2015 o HILUX CABINA SIMPLE"),
])
def test_hilux_sin_decidir_la_cabina_se_pregunta(anio, ofrece):
    r, _ = campana([{"producto": "fundas", "modelo": "Hilux", **({"anio": anio} if anio else {})}])
    assert "requiere_derivacion" not in r
    assert r["continuacion_obligatoria"] == f"Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: {ofrece}?"


HOJA_HILUX = {"title": "Fundas a medida", "sheetId": 877828453, "values": [
    ["TOYOTA"], _ENC[:3], _MEDIOS[:3],
    ["HILUX CABINA DOBLE 2016+", 100000, 110000],
    ["HILUX 2005-2015", 200000, 220000]]}


def test_una_fila_de_cabina_que_el_cliente_no_nombro_no_se_elige_sola():
    # 2020 solo lo cubre la doble cabina. No se cotiza por descarte: se le confirma.
    item = item_de(HOJA_HILUX, {"producto": "fundas", "modelo": "Hilux", "anio": 2020})
    assert item["estado"] == "requiere_aclaracion" and "requiere_derivacion" not in item
    assert item["opciones"] == [{"modelo": "HILUX CABINA DOBLE 2016+"}]
    item = item_de(HOJA_HILUX, {"producto": "fundas", "modelo": "Hilux doble cabina", "anio": 2020})
    assert (item["estado"], item["modelo"]) == ("cotizado", "HILUX CABINA DOBLE 2016+")
    item = item_de(HOJA_HILUX, {"producto": "fundas", "modelo": "Hilux", "anio": 2010})
    assert (item["estado"], item["modelo"]) == ("cotizado", "HILUX 2005-2015")


HOJA_S10 = {"title": "Fundas a medida", "sheetId": 877828453, "values": [
    ["CHEVROLET"], _ENC[:3], _MEDIOS[:3],
    ["S-10 ( CABINA SIMPLE )", 100000, 110000],
    ["S-10 ( CABINA DOBLE ) 2012+", 200000, 220000]]}


def test_la_cabina_sin_anios_no_absorbe_el_anio_que_la_otra_no_cubre():
    item = item_de(HOJA_S10, {"producto": "fundas", "modelo": "S10", "anio": 2008})
    assert item["motivo"] == ANIO_NO_CUBIERTO and item["requiere_derivacion"] == "revision_especial"
    # Si el año no descarta ninguna, se pregunta la cabina; si la nombra, es esa.
    item = item_de(HOJA_S10, {"producto": "fundas", "modelo": "S10", "anio": 2015})
    assert item["opciones"] == [{"modelo": "S-10 ( CABINA SIMPLE )"}, {"modelo": "S-10 ( CABINA DOBLE ) 2012+"}]
    item = item_de(HOJA_S10, {"producto": "fundas", "modelo": "S10 cabina simple", "anio": 2008})
    assert (item["estado"], item["modelo"]) == ("cotizado", "S-10 ( CABINA SIMPLE )")


# --- Punto 1: elegir una opción cuyo nombre está contenido en otra ----------------------------
# La herramienta recuerda qué opciones ofreció en la conversación. Si en un turno posterior
# llega el nombre exacto de una, es esa.

from agente.f7.precios.motor import clave_opcion  # noqa: E402

EL_208 = [{"producto": "fundas", "modelo": "208"}]
OPCIONES_208 = "Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: 208 GT o 208?"
OPCIONES_DUSTER = "Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: DUSTER o DUSTER 2017+?"
COTIZACION_208 = "El juego completo de fundas a medida para 208 (5 plazas) sale $158.000 por transferencia."
COTIZACION_DUSTER = "El juego completo de fundas a medida para Duster (5 plazas) sale $170.000 por transferencia."
COTIZACION_DUSTER_2017 = ("El juego completo de fundas a medida para Duster 2017+ (5 plazas) sale $175.000 por "
                          "transferencia.")


def test_el_208_se_puede_elegir_despues_de_que_se_ofrecieron_las_opciones():
    sesion = SesionLocal(conversation_id=7)
    r, ctx = campana(EL_208, sesion)
    assert r["continuacion_obligatoria"] == OPCIONES_208 and textos(ctx) == []  # la primera vez pregunta
    # El cliente contesta «208 común» y el modelo vuelve a mandar «208».
    r, ctx = campana(EL_208, sesion)
    assert textos(ctx) == [COTIZACION_208]
    assert r["estado"] == "cotizado" and r["continuacion_obligatoria"] == ""
    assert r["items"][0]["modelo"] == "208"


@pytest.mark.parametrize("elegida, texto", [
    ("Duster", COTIZACION_DUSTER),
    ("DUSTER 2017+", COTIZACION_DUSTER_2017),  # copiada tal cual: no se le vuelve a pedir el año
    ("duster 2017 +", COTIZACION_DUSTER_2017),
])
def test_duster_se_elige_con_el_nombre_exacto_de_la_opcion(elegida, texto):
    sesion = SesionLocal(conversation_id=7)
    r, _ = campana([{"producto": "fundas", "modelo": "Duster"}], sesion)
    assert r["continuacion_obligatoria"] == OPCIONES_DUSTER
    _, ctx = campana([{"producto": "fundas", "modelo": elegida}], sesion)
    assert textos(ctx) == [texto]


@pytest.mark.parametrize("primero, despues, texto", [
    ("Peugeot 208", "Peugeot 208", COTIZACION_208),  # la marca que agrega el cliente no cambia el nombre
    ("208", "peugeot 208", COTIZACION_208),
    ("Renault Duster", "Renault DUSTER 2017+", COTIZACION_DUSTER_2017),
])
def test_el_nombre_exacto_vale_con_o_sin_la_marca(primero, despues, texto):
    sesion = SesionLocal(conversation_id=7)
    r, ctx = campana([{"producto": "fundas", "modelo": primero}], sesion)
    assert r["estado"] == "requiere_aclaracion" and textos(ctx) == []
    _, ctx = campana([{"producto": "fundas", "modelo": despues}], sesion)
    assert textos(ctx) == [texto]


def test_en_alfombra_la_opcion_elegida_trae_la_marca_en_el_nombre():
    sesion = SesionLocal(conversation_id=7)
    r, _ = campana([{"producto": "alfombra", "modelo": "Ranger", "anio": 2015}], sesion)
    assert r["continuacion_obligatoria"] == ("Para alfombra, ¿cuál de estas opciones corresponde a tu vehículo: "
                                             "Ford Ranger Cabina Simple 2012 + o Ford Ranger 2012 hasta 2022?")
    _, ctx = campana([{"producto": "alfombra", "modelo": "Ranger 2012 hasta 2022", "anio": 2015}], sesion)
    assert textos(ctx) == ["La alfombra termoformada para Ford Ranger 2012 hasta 2022 sale $55.000 por "
                           "transferencia."]


def test_sin_haber_ofrecido_las_opciones_el_nombre_exacto_no_alcanza():
    r, ctx = campana([{"producto": "fundas", "modelo": "DUSTER 2017+"}])
    assert r["continuacion_obligatoria"] == OPCIONES_DUSTER and textos(ctx) == []


def test_otra_llamada_en_el_mismo_turno_no_es_la_respuesta_del_cliente():
    _, ctx = campana(EL_208)
    r, _ = campana(EL_208, ctx=ctx)  # el modelo reintenta sin que el cliente haya visto la pregunta
    assert r["continuacion_obligatoria"] == OPCIONES_208 and textos(ctx) == []


def test_las_opciones_ofrecidas_antes_de_borrar_no_cuentan():
    sesion = SesionLocal(conversation_id=7)
    campana(EL_208, sesion)
    sesion.epoca = sesion.nuevo_message_id()  # el cliente escribió «borrar»
    r, ctx = campana(EL_208, sesion)
    assert r["continuacion_obligatoria"] == OPCIONES_208 and textos(ctx) == []


def test_si_despues_de_las_opciones_llega_el_anio_decide_el_anio():
    sesion = SesionLocal(conversation_id=7)
    campana([{"producto": "fundas", "modelo": "Duster"}], sesion)
    _, ctx = campana([{"producto": "fundas", "modelo": "Duster", "anio": 2019}], sesion)
    assert textos(ctx) == [COTIZACION_DUSTER_2017]


def test_las_opciones_ofrecidas_quedan_en_un_registro_de_la_sesion():
    sesion = SesionLocal(conversation_id=7)
    campana(EL_208, sesion)
    memoria = sesion.registro("precios_aclaraciones")["0"]  # una entrada por época («borrar»)
    assert set(memoria["ofrecidas"]) == {clave_opcion("208 GT "), clave_opcion(208)} == {"208 gt", "208"}


def test_el_motor_elige_por_nombre_solo_entre_las_ofrecidas():
    consulta = {"producto": "fundas", "modelo": "208"}
    assert item_campana(consulta)["estado"] == "requiere_aclaracion"
    assert item_campana(consulta, ofrecidas={"duster"})["estado"] == "requiere_aclaracion"
    item = item_campana(consulta, ofrecidas={"208 gt", "208"})
    assert (item["estado"], item["modelo"]) == ("cotizado", "208")


HOJA_2008 = {"title": "Fundas a medida", "sheetId": 877828453, "values": [
    ["PEUGEOT"], _ENC[:3], _MEDIOS[:3],
    ["2008 (Hasta Junio 2024)", 100000, 110000],
    ["2008 (Desde Julio 2024)", 200000, 220000]]}


def test_la_variante_elegida_no_se_vuelve_a_confirmar():
    # 2024 es el año de corte de las dos filas: sin elegir, se pregunta; elegida una, se cotiza.
    consulta = {"producto": "fundas", "modelo": "2008 (Desde Julio 2024)", "anio": 2024}
    ofrecidas = {clave_opcion("2008 (Hasta Junio 2024)"), clave_opcion("2008 (Desde Julio 2024)")}
    assert item_de(HOJA_2008, consulta)["estado"] == "requiere_aclaracion"
    n = normalizar_entrada({"consultas": [consulta], "modalidad": "caba", "tipo_solicitud": "consulta"})
    item = cotizar(n["entrada"], [HOJA_2008], None, ofrecidas=ofrecidas)["items"][0]
    assert (item["estado"], item["modelo"]) == ("cotizado", "2008 (Desde Julio 2024)")


# --- Punto 6: no repetir la misma aclaración ---------------------------------------------------
# Si la herramienta está por devolver lo mismo que devolvió en el turno anterior en que se usó,
# no lo repite: la conversación pasa a una persona.

PARTNER_3_PLAZAS = [{"producto": "fundas", "modelo": "Partner", "configuracion": "3 plazas"}]
OPCIONES_PARTNER = "Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: 5 plazas o 2 plazas?"


def test_la_misma_aclaracion_no_se_repite_y_pasa_a_una_persona():
    sesion = SesionLocal(conversation_id=7)
    r, _ = campana(PARTNER_3_PLAZAS, sesion)
    assert r["continuacion_obligatoria"] == OPCIONES_PARTNER and "requiere_derivacion" not in r  # primero pregunta
    # El cliente explica que son 3 asientos y el modelo manda lo mismo.
    r, ctx = campana(PARTNER_3_PLAZAS, sesion)
    assert pasa_a_una_persona(r) and textos(ctx) == []
    assert r["estado"] == "requiere_aclaracion" and r["envio"] == {"estado": "no_corresponde"}
    assert list(r) == ["estado", "items", "envio", "consultado_en", "metodo_pago", "pregunta_comercial_incluida",
                       "requiere_derivacion", "cotizacion_enviada", "continuacion_obligatoria", "instrucciones"]
    # Y si vuelve a salir, sigue sin repetirse.
    r, _ = campana(PARTNER_3_PLAZAS, sesion)
    assert pasa_a_una_persona(r)


def test_cuenta_la_aclaracion_aunque_el_pedido_venga_escrito_distinto():
    sesion = SesionLocal(conversation_id=7)
    campana(PARTNER_3_PLAZAS, sesion)
    r, _ = campana([{"producto": "fundas", "modelo": "Partner", "configuracion": "3 asientos"}], sesion)
    assert pasa_a_una_persona(r)


def test_otra_llamada_en_el_mismo_turno_no_cuenta_como_repeticion():
    # El cliente todavía no vio la pregunta: se le hace. Si en el turno siguiente vuelve a salir, no.
    _, ctx = campana(PARTNER_3_PLAZAS)
    r, _ = campana(PARTNER_3_PLAZAS, ctx=ctx)
    assert r["continuacion_obligatoria"] == OPCIONES_PARTNER and "requiere_derivacion" not in r
    r, _ = campana(PARTNER_3_PLAZAS, ctx.sesion)
    assert pasa_a_una_persona(r)


def test_si_en_el_medio_devolvio_otra_cosa_se_vuelve_a_preguntar():
    sesion = SesionLocal(conversation_id=7)
    campana(PARTNER_3_PLAZAS, sesion)
    r, _ = campana(EL_208, sesion)
    assert r["continuacion_obligatoria"] == OPCIONES_208
    r, _ = campana(PARTNER_3_PLAZAS, sesion)
    assert r["continuacion_obligatoria"] == OPCIONES_PARTNER and "requiere_derivacion" not in r


def test_despues_de_borrar_la_aclaracion_se_vuelve_a_hacer():
    sesion = SesionLocal(conversation_id=7)
    campana(PARTNER_3_PLAZAS, sesion)
    sesion.epoca = sesion.nuevo_message_id()  # el cliente escribió «borrar»
    r, _ = campana(PARTNER_3_PLAZAS, sesion)
    assert r["continuacion_obligatoria"] == OPCIONES_PARTNER and "requiere_derivacion" not in r


def test_tampoco_se_le_pide_dos_veces_seguidas_que_repita_el_modelo():
    sesion = SesionLocal(conversation_id=7)
    r, _ = campana([{"producto": "fundas", "modelo": "Batimovil"}], sesion)
    assert r["continuacion_obligatoria"] == CONFUSION
    r, _ = campana([{"producto": "fundas", "modelo": "Batimobil"}], sesion)
    assert pasa_a_una_persona(r) and r["estado"] == "no_disponible"


def test_las_dos_preguntas_del_recorrido_se_siguen_haciendo():
    # El modelo y la modalidad se piden en el recorrido de venta: no cuentan como aclaración repetida.
    sesion = SesionLocal(conversation_id=7)
    for _ in range(2):
        r, _ = campana([{"producto": "fundas", "modelo": "Partner"}], sesion, modalidad="sin_confirmar")
        assert r["continuacion_obligatoria"] == herramienta.PREGUNTA_MODALIDAD and "requiere_derivacion" not in r
    for _ in range(2):
        r, _ = campana([{"producto": "fundas"}], sesion)
        assert r["continuacion_obligatoria"] == herramienta.PREGUNTA_MODELO and "requiere_derivacion" not in r


def test_una_cotizacion_en_el_medio_tampoco_es_repeticion():
    sesion = SesionLocal(conversation_id=7)
    campana(PARTNER_3_PLAZAS, sesion)
    r, _ = campana([{"producto": "fundas", "modelo": "Partner"}], sesion)
    assert r["estado"] == "cotizado" and r["continuacion_obligatoria"] == ""
    r, _ = campana(PARTNER_3_PLAZAS, sesion)
    assert r["continuacion_obligatoria"] == OPCIONES_PARTNER


# --- Punto 7: no volver a mandar la misma cotización ------------------------------------------
# Si el texto es idéntico al de la última cotización aceptada desde el último «borrar», no sale.

PARTNER = [{"producto": "fundas", "modelo": "Partner"}]
COTIZACION_PARTNER = "El juego completo de fundas a medida para Partner (5 plazas) sale $159.000 por transferencia."


def test_la_misma_cotizacion_no_se_manda_dos_veces_en_la_conversacion():
    sesion = SesionLocal(conversation_id=7)
    r1, _ = campana(PARTNER, sesion)
    r2, ctx2 = campana(PARTNER, sesion)  # otro turno
    assert textos(ctx2) == [COTIZACION_PARTNER]  # salió una sola vez
    assert r2["estado"] == "cotizado" and "requiere_derivacion" not in r2
    assert r2["envio"] == {"estado": "omitido", "motivo": "cotizacion_ya_enviada",
                           "chatwoot_message_id": r1["envio"]["chatwoot_message_id"], "registro_confirmado": True}
    assert r2["cotizacion_enviada"] is True and r2["continuacion_obligatoria"] == ""
    assert sesion.registro("precios")[ctx2.solicitud_id("precios-v1")]["estado"] == "omitido"
    # Otra llamada dentro de ese turno y un tercer turno tampoco la mandan.
    r3, _ = campana(PARTNER, ctx=ctx2)
    assert r3["envio"]["estado"] == "omitido" and r3["continuacion_obligatoria"] == ""
    r4, _ = campana(PARTNER, sesion)
    assert r4["envio"]["motivo"] == "cotizacion_ya_enviada" and len(sesion.salientes) == 1


def test_si_la_cotizacion_cambia_se_manda():
    sesion = SesionLocal(conversation_id=7)
    campana(PARTNER, sesion)
    _, ctx = campana(PARTNER, sesion, metodo="efectivo")  # otro medio de pago: otro texto
    assert textos(ctx) == [COTIZACION_PARTNER,
                           "El juego completo de fundas a medida para Partner (5 plazas) sale $149.000 en efectivo."]
    # Volver a la primera también se manda: la última aceptada es la de efectivo.
    r, _ = campana(PARTNER, sesion)
    assert r["envio"]["estado"] == "aceptado" and len(sesion.salientes) == 3


def test_despues_de_borrar_la_cotizacion_se_vuelve_a_mandar():
    sesion = SesionLocal(conversation_id=7)
    campana(PARTNER, sesion)
    sesion.epoca = sesion.nuevo_message_id()  # el cliente escribió «borrar»
    r, _ = campana(PARTNER, sesion)
    assert r["envio"]["estado"] == "aceptado" and len(sesion.salientes) == 2


def test_una_cotizacion_que_no_llego_a_salir_se_manda_despues():
    sesion = SesionLocal(conversation_id=7, etiquetas=["humano"])
    r, _ = campana(PARTNER, sesion)
    assert r["envio"]["estado"] == "control_humano" and sesion.salientes == []
    sesion.etiquetas.clear()
    r, ctx = campana(PARTNER, sesion)
    assert r["envio"]["estado"] == "aceptado" and textos(ctx) == [COTIZACION_PARTNER]


def test_con_humano_la_cotizacion_repetida_sigue_siendo_silencio():
    sesion = SesionLocal(conversation_id=7)
    campana(PARTNER, sesion)
    sesion.etiquetas.append("humano")
    r, _ = campana(PARTNER, sesion)
    assert r["envio"]["estado"] == "control_humano" and len(sesion.salientes) == 1


def test_la_parcial_repetida_no_sale_y_su_aclaracion_pasa_a_una_persona():
    sesion = SesionLocal(conversation_id=7)
    consultas = PARTNER + PARTNER_3_PLAZAS  # una se cotiza; la otra pregunta «5 plazas o 2 plazas»
    r, _ = campana(consultas, sesion)
    assert r["estado"] == "parcial" and r["continuacion_obligatoria"] == OPCIONES_PARTNER
    r, _ = campana(consultas, sesion)
    assert len(sesion.salientes) == 1 and r["envio"]["motivo"] == "cotizacion_ya_enviada"
    assert pasa_a_una_persona(r)


# --- Puntos 1, 6 y 7: bordes de la memoria de la conversación ---------------------------------

def test_lo_que_no_se_le_mostro_al_cliente_no_queda_como_ofrecido():
    sesion = SesionLocal(conversation_id=7)
    r, _ = campana([{"producto": "fundas", "modelo": "Suran", "anio": 2012}], sesion)
    assert pasa_a_una_persona(r) and r["items"][0]["opciones"]  # las variantes quedan como dato para el modelo
    assert sesion.registro("precios_aclaraciones")["0"]["ofrecidas"] == {}


def test_un_lote_anterior_a_borrar_no_toca_la_memoria():
    sesion = SesionLocal(conversation_id=7)
    ctx = contexto(sesion)
    sesion.epoca = sesion.nuevo_message_id()  # llegó «borrar» después del lote
    herramienta.ejecutar(pedido(EL_208), ctx, leer_hojas=lector_campana)
    assert sesion.registro("precios_aclaraciones") == {}


def test_si_la_memoria_no_se_puede_leer_la_herramienta_contesta_igual():
    sesion = SesionLocal(conversation_id=7)
    sesion.registro("precios_aclaraciones")["0"] = {"otra": "cosa"}
    r, _ = campana(EL_208, sesion)
    assert r["continuacion_obligatoria"] == OPCIONES_208
    r, ctx = campana(PARTNER, sesion)
    assert r["envio"]["estado"] == "aceptado" and textos(ctx) == [COTIZACION_PARTNER]


def test_el_medio_de_pago_sin_confirmar_repetido_sigue_pidiendo_la_derivacion():
    sesion = SesionLocal(conversation_id=7)
    r, _ = campana(PARTNER, sesion, metodo="debito")
    assert r["requiere_derivacion"] == "revision_especial"
    assert r["continuacion_obligatoria"] == "Ese medio de pago necesita confirmación de Candela."
    r, _ = campana(PARTNER, sesion, metodo="debito")
    assert pasa_a_una_persona(r) and r["estado"] == "metodo_no_confirmado"
    assert list(r).index("requiere_derivacion") < list(r).index("cotizacion_enviada")


# --- Corrección del 20/11: la cotización repetida vuelve a salir si el turno iba a quedar mudo ---
# No repetir la cotización está bien cuando el turno tiene otra cosa para decir. Si el cliente
# pide de nuevo el mismo precio y no hay nada más para mandarle, el turno la reenvía con esto.


def test_la_cotizacion_omitida_por_repetida_se_puede_volver_a_mandar():
    sesion = SesionLocal(conversation_id=7)
    campana(PARTNER, sesion)
    r2, ctx2 = campana(PARTNER, sesion)  # otro turno: se omite por repetida
    assert r2["envio"]["motivo"] == "cotizacion_ya_enviada" and len(sesion.salientes) == 1

    assert herramienta.reenviar_repetida(ctx2) is True

    assert textos(ctx2) == [COTIZACION_PARTNER, COTIZACION_PARTNER]
    assert sesion.salientes[-1].tipo == "cotizacion"
    fila = sesion.registro("precios")[ctx2.solicitud_id("precios-v1")]
    assert fila["estado"] == "aceptado"
    assert fila["chatwoot_message_id"] == sesion.salientes[-1].chatwoot_message_id
    # Una sola vez por turno.
    assert herramienta.reenviar_repetida(ctx2) is False and len(sesion.salientes) == 2
    # Y en el turno siguiente sigue sin repetirse sola.
    r3, _ = campana(PARTNER, sesion)
    assert r3["envio"]["motivo"] == "cotizacion_ya_enviada" and len(sesion.salientes) == 2


def test_sin_una_cotizacion_omitida_por_repetida_no_se_reenvia_nada():
    sesion = SesionLocal(conversation_id=7)
    _, ctx = campana(PARTNER, sesion)  # salió normalmente
    assert herramienta.reenviar_repetida(ctx) is False
    assert herramienta.reenviar_repetida(contexto(sesion)) is False  # un turno sin buscar_precio
    assert len(sesion.salientes) == 1


def test_con_humano_la_cotizacion_repetida_no_se_reenvia():
    sesion = SesionLocal(conversation_id=7)
    campana(PARTNER, sesion)
    _, ctx2 = campana(PARTNER, sesion)
    sesion.etiquetas.append("humano")
    assert herramienta.reenviar_repetida(ctx2) is False and len(sesion.salientes) == 1


# --- Re-prueba del 20/11: la variante que ya se cotizó se reconoce por su nombre ---------------
# Onix 2021 se cotizó como «ONIX GEN 2 (2020+)». En el turno siguiente el modelo copió ese
# nombre sin repetir el año y la herramienta le pidió al cliente que confirmara el año.


def test_la_variante_ya_cotizada_se_reconoce_por_su_nombre_sin_repetir_el_anio():
    sesion = SesionLocal(conversation_id=7)
    r1, _ = campana([{"producto": "fundas", "modelo": "Onix", "anio": 2021}], sesion, modalidad="envio")
    assert r1["estado"] == "cotizado" and r1["items"][0]["modelo"] == "ONIX GEN 2 (2020+)"

    r2, _ = campana([{"producto": "fundas", "modelo": "ONIX GEN 2 (2020+)"}], sesion, metodo="efectivo")

    assert r2["estado"] == "cotizado", r2.get("continuacion_obligatoria")
    assert r2["envio"]["estado"] == "aceptado" and r2["continuacion_obligatoria"] == ""


def test_sin_haberla_cotizado_antes_la_variante_con_anios_sigue_pidiendo_el_anio():
    r, _ = campana([{"producto": "fundas", "modelo": "ONIX GEN 2 (2020+)"}])
    assert r["estado"] == "requiere_aclaracion"
    assert r["continuacion_obligatoria"] == "De qué año es tu vehículo?"


# --- Re-prueba del 20/11 (C04): si algo no se puede resolver, pasa a una persona ya ------------
# Fundas para Suran (hay que elegir la variante), cubrevolante y una alfombra que la planilla no
# resuelve. Se probó preguntar primero la variante y derivar después: el modelo reintentó sin la
# configuración pedida («trasera») y cotizó una alfombra completa. Queda la regla simple.

ALFOMBRA_SIN_RESOLVER = {"producto": "alfombra", "modelo": "Cronos", "configuracion": "trasera"}


def test_si_un_item_no_se_puede_resolver_pasa_a_una_persona_aunque_otro_tenga_una_aclaracion():
    r, ctx = campana([{"producto": "fundas", "modelo": "Suran"}, {"producto": "cubrevolante"}, ALFOMBRA_SIN_RESOLVER],
                     tipo="combo")
    assert r["estado"] == "parcial" and pasa_a_una_persona(r)
    # Lo que sí se pudo cotizar le llega igual.
    assert "El cubrevolante sale $22.000 por transferencia." in textos(ctx)[0]


# --- Prueba de «romper el flujo» del 21/11: trabajos que son solo de taller -------------------
# Techo, paneles, relleno y espuma se hacen solo en el taller (guion). El agente preguntaba
# «envío o taller», en un caso justo después de que el cliente dijera que podía ir (R32, R44).

@pytest.mark.parametrize("consultas", [
    [{"producto": "otros", "modelo": "tapizado de techo"}],
    [{"producto": "tapiceria", "modelo": "Clio", "configuracion": "techo"}],
    [{"producto": "espuma", "modelo": "Clio", "configuracion": "asiento"}],
])
def test_los_trabajos_de_taller_se_cotizan_sin_preguntar_envio_o_taller(consultas):
    r, ctx, _ = correr(pedido(consultas), modalidad="sin_confirmar")
    assert r["estado"] == "cotizado", r
    assert _modalidad_cotizada(ctx) == "caba"


@pytest.mark.parametrize("consultas", [
    [{"producto": "otros", "modelo": "paneles de puerta"}],
    [{"producto": "espuma", "modelo": "Clio", "configuracion": "asiento"}],
])
def test_paneles_y_espuma_con_envio_avisan_que_son_solo_de_taller(consultas):
    r, ctx, _ = correr(pedido(consultas), modalidad="envio")
    assert r["continuacion_obligatoria"] == SOLO_EN_EL_TALLER and ctx.sesion.salientes == []


def test_un_trabajo_de_taller_junto_con_fundas_sigue_preguntando_la_modalidad():
    consultas = [{"producto": "otros", "modelo": "tapizado de techo"}, {"producto": "fundas", "modelo": "Clio"}]
    r, ctx, _ = correr(pedido(consultas), modalidad="sin_confirmar")
    assert r["estado"] == "requiere_modalidad" and ctx.sesion.salientes == []


# --- Prueba de «romper el flujo» del 21/11: aclaraciones de modelo ----------------------------
# Las filas están copiadas de la planilla real, con otros importes.

PLANILLA_2111 = [
    {"title": "Fundas a medida", "sheetId": 877828453, "values": [
        ["FORD"], _ENC, _MEDIOS,
        ["ECO SPORT", 140000, 150000, 80000, 90000],
        ["ECO KINECTIC", 141000, 151000, 81000, 91000],
        ["ECO TITANIUM", 142000, 152000, 82000, 92000],
        ["VOLKSWAGEN"], _ENC, _MEDIOS,
        ["Saveiro DOBLE CABINA", 145000, 155000, 85000, 95000],
        ["Saveiro cross", 146000, 156000, 86000, 96000],
        ["RENAULT"], _ENC, _MEDIOS,
        ["STEPWEEY", 147000, 157000, 87000, 97000],
        ["SANDERO ", 148000, 158000, 88000, 98000],
    ]},
    {"title": "TIPO TAPIZADO", "sheetId": 613213257, "values": [
        ["FIAT"], _ENC[:5], _MEDIOS[:5],
        ["Cronos  ", 300000, 310000, 150000, 160000],
    ]},
    {"title": "Termoformadas", "sheetId": 0, "values": [
        ["  Marca", "Vehículo/Modelo ", "EFECTIVO", "TRANSFERENCIA"],
        ["TOYOTA", "Toyota Hilux 05-15", 30000, 33000],
        ["Toyota ", "Toyota Hilux 2016+", 31000, 34000],
        ["Toyota ", "Toyota Hilux con Overmat 2016 +", 32000, 35000],
        ["Toyota ", "Toyota Hilux Cabina Simple 2016 +", 29000, 32000],
        ["Volkswagen", "Volkswagen Gol - Gol Trend 2007 - 2022 (sin posa vasos trasero)", 28000, 31000],
    ]},
    {"title": "Funda Baúl - Antiderrame", "sheetId": 941782890, "values": [
        ["FUNDA ANTIDERRAME BAÚL"],
        ["Marca", "Vehículo/Modelo ", "", "EFECTIVO", "TRANSFERENCIA"],
        ["TOYOTA", "Corolla G12", "", 17000, 21000],
        ["TOYOTA", "T-Cross", "", 17000, 21000],
        ["TOYOTA", "Taos", "", 17000, 21000],
    ]},
    {"title": "Otros", "sheetId": 59879218, "values": [
        ["OTROS ACCESORIOS"],
        ["Producto/servicio", "Valor EFECTIVO", "TRANSFERENCIA + 21%", "POSNET o CUOTAS 21% + 9%"],
        [],
        ["CUBRE VOLANTE", 20000, 22000, 25000],
        ["PANELES DE PUERTA", 70000, 77000, 85000],
    ]},
]


from agente.f7.precios.vehiculos import TEXTO_SIN_MEDIDAS, buscar  # noqa: E402


def lector_2111(titulos):
    return [copy.deepcopy(h) for h in PLANILLA_2111 if h["title"] in titulos]


def el_2111(consultas, sesion=None, modalidad="caba", texto="", **extra):
    """buscar_precio sobre esa planilla; `texto` es lo que escribió el cliente en este turno."""
    ctx = contexto(sesion, modalidad=modalidad)
    ctx.texto_cliente = texto
    return herramienta.ejecutar(pedido(consultas, **extra), ctx, leer_hojas=lector_2111), ctx


def test_ecosport_kinetic_es_la_fila_eco_kinectic():
    # R09: había dicho «kinetik» y le preguntaron «ECO SPORT o ECO KINECTIC?».
    r, ctx = el_2111([{"producto": "fundas", "modelo": "EcoSport Kinetic", "anio": 2014}])
    assert r["estado"] == "cotizado", r
    assert "Eco Kinectic" in textos(ctx)[0]
    r, ctx = el_2111([{"producto": "fundas", "modelo": "ecosport"}])
    assert r["estado"] == "cotizado" and "Eco Sport" in textos(ctx)[0]


def test_gol_saveiro_sigue_siendo_una_pregunta():
    # Dos modelos distintos en el mismo pedido: ahí sí se pregunta (regla de oro del buscador).
    filas = [{"modelo": "GOL", "marca": "volkswagen"}, {"modelo": "SAVEIRO", "marca": "volkswagen"}]
    assert buscar("gol saveiro", filas)["indices"] == [0, 1]


def test_la_configuracion_unidad_no_es_una_configuracion():
    # R06: el modelo copió «Unidad» de la cotización anterior y la alfombra quedó «pendiente».
    sesion = SesionLocal(conversation_id=7)
    r, _ = el_2111([{"producto": "alfombra", "modelo": "Hilux", "anio": 2020, "configuracion": "cabina doble"}], sesion)
    assert r["estado"] == "cotizado", r
    r, ctx = el_2111([{"producto": "alfombra", "modelo": "Toyota Hilux 2016+", "configuracion": "Unidad", "cantidad": 1},
                      {"producto": "cubrevolante"}], sesion, tipo="combo")
    assert r["estado"] == "cotizado", r


def test_la_cabina_que_escribio_el_cliente_cuenta_aunque_el_modelo_no_la_pase():
    # R06: «es 2020 doble cabina» y volvió a preguntar si era la común o la cabina simple.
    r, ctx = el_2111([{"producto": "alfombra", "modelo": "Hilux", "anio": 2020}], texto="es 2020 doble cabina")
    assert r["estado"] == "cotizado", r
    assert "Toyota Hilux 2016+" in textos(ctx)[0]
    # R40: dijo «Saveiro cabina simple» y le ofrecieron «DOBLE CABINA o Saveiro cross».
    r, ctx = el_2111([{"producto": "fundas", "modelo": "Saveiro", "configuracion": "2 plazas"}],
                     texto="necesito fundas solo para las dos butacas de adelante de una Saveiro cabina simple")
    assert r["estado"] == "no_disponible" and r["continuacion_obligatoria"] == TEXTO_SIN_MEDIDAS
    # Si nombra las dos cabinas (dos vehículos), no se adivina a cuál corresponde.
    r, _ = el_2111([{"producto": "alfombra", "modelo": "Hilux", "anio": 2020}],
                   texto="una hilux doble cabina y una ranger cabina simple")
    assert r["estado"] == "requiere_aclaracion"


def test_dos_palabras_que_son_dos_filas_distintas_se_siguen_preguntando():
    # R43 (funda de baúl para Corolla Cross: «Corolla G12 o T-Cross?») queda como estaba: no hay
    # manera segura de saber si la segunda palabra es otro auto o una versión (Corsa Classic).
    r, ctx = el_2111([{"producto": "funda baul", "modelo": "Corolla Cross"}])
    assert r["estado"] == "requiere_aclaracion" and textos(ctx) == []


def test_lo_que_no_esta_en_la_lista_pasa_a_una_persona_sin_texto_de_sistema():
    # R32: «No encontré ese modelo o producto en la lista consultada».
    r, ctx = el_2111([{"producto": "otros", "modelo": "tapizado de techo"}])
    assert r["continuacion_obligatoria"] == "" and r["requiere_derivacion"] == "revision_especial", r


def test_tipo_tapizado_sin_tarifa_para_ese_auto_no_le_dice_al_cliente_que_se_confundio():
    # R46: Sandero Stepway existe; lo que no hay es tipo tapizado para ese auto.
    r, _ = el_2111([{"producto": "tipo tapizado", "modelo": "Sandero Stepway"}], modalidad="envio")
    assert r["continuacion_obligatoria"] == TEXTO_SIN_MEDIDAS


def test_la_pregunta_por_el_anio_no_tiene_tono_de_sistema():
    # R26: «Confirmá el año del vehículo para esta variante publicada. Opción publicada: …».
    r, _ = el_2111([{"producto": "alfombra", "modelo": "Gol"}])
    assert r["estado"] == "requiere_aclaracion"
    assert r["continuacion_obligatoria"] == "De qué año es tu vehículo?"


def test_un_servicio_pendiente_se_nombra_sin_producto_o_servicio_para():
    # R32: «Producto o servicio para Tapizado de Techo: pendiente de confirmación».
    r, ctx = el_2111([{"producto": "otros", "modelo": "tapizado de techo"}, {"producto": "otros", "modelo": "paneles de puerta"}])
    assert textos(ctx) == ["Tapizado de Techo: pendiente de confirmación.\n\nPaneles de Puerta sale $77.000 por transferencia."]
    assert r["requiere_derivacion"] == "revision_especial"


def test_ecosport_kinetik_con_k_tambien_es_la_fila_eco_kinectic():
    # R09: el cliente escribió «ecoesport kinetik» y el modelo pasó «Ecosport Kinetik».
    r, ctx = el_2111([{"producto": "fundas", "modelo": "Ecosport Kinetik", "anio": 2014}])
    assert r["estado"] == "cotizado", r
    assert "Eco Kinectic" in textos(ctx)[0]


@pytest.mark.parametrize("producto", ["funda baul", "alfombra"])
def test_un_auto_que_no_esta_en_una_lista_corta_no_es_una_confusion_del_cliente(producto):
    # R41: funda de baúl para un Gol Power. La hoja no lo tiene; no es que el cliente escribió mal.
    r, ctx = el_2111([{"producto": producto, "modelo": "Gol Power" if producto == "funda baul" else "Duna"}])
    assert r["continuacion_obligatoria"] == "" and r["requiere_derivacion"] == "revision_especial", r
    assert textos(ctx) == []


def test_en_fundas_a_medida_lo_que_no_se_parece_a_nada_sigue_pidiendo_que_lo_repita():
    from agente.f7.precios.vehiculos import TEXTO_CONFUSION

    r, _ = el_2111([{"producto": "fundas", "modelo": "asdasd"}])
    assert r["continuacion_obligatoria"] == TEXTO_CONFUSION
