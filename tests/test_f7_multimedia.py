"""Pruebas de enviar_multimedia de F7. No salen a internet ni gastan saldo.

Los resultados esperados salen de comparar el port con el JS que corre hoy en
n8n (nodo «Planificar contenido») y coinciden con la tabla «Qué sale para cada
pedido» de docs/MAPA_MIGRACION.md §3.2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from agente.f7.local import ContextoTurno, SesionLocal  # noqa: E402
from agente.f7.multimedia import herramienta  # noqa: E402
from agente.f7.multimedia.descripcion import (  # noqa: E402
    DESCRIPCION_ENVIAR_MULTIMEDIA,
    DESCRIPCION_SOLICITUDES,
)
from agente.f7.multimedia.seleccion import (  # noqa: E402
    cargar_catalogo,
    etiqueta,
    locale_compare,
    normalizar_entrada,
    planificar_seleccion,
)

CATALOGO = cargar_catalogo()


def pres(producto, **extra):
    return {"producto": producto, "contenido": "presentacion", **extra}


def plan_de(solicitudes, modo="simular"):
    entrada = {"solicitudes": solicitudes, "modo": modo, "account_id": 1,
               "conversation_id": 42, "solicitud_id": "cw:1:42:100:multimedia-v1"}
    return planificar_seleccion(entrada, CATALOGO)


def contexto(ultimo=10, **sesion):
    return ContextoTurno(sesion=SesionLocal(conversation_id=42, **sesion), ultimo_message_id=ultimo)


# ---------- Descripciones y catálogo ----------

def test_las_descripciones_parten_del_export_y_suman_las_decisiones_del_21_11():
    from agente.f7.multimedia.descripcion import DESCRIPCION_BASE, SOLICITUDES_BASE

    leer = lambda nombre: (RAIZ / "referencia-f7" / "prompt" / nombre).read_text(encoding="utf-8")
    # La base sigue siendo, byte a byte, la del export de n8n.
    assert DESCRIPCION_BASE == leer("ENVIAR_MULTIMEDIA_F7.md") and len(DESCRIPCION_BASE) == 4245
    assert SOLICITUDES_BASE == leer("SOLICITUDES_MULTIMEDIA_F7.md") and len(SOLICITUDES_BASE) == 872
    # Decisión de Mateo del 21/11: si piden fotos va el video y nunca se dice que no hay fotos.
    assert "no mandes un video como reemplazo" not in DESCRIPCION_ENVIAR_MULTIMEDIA
    assert "nunca digas que no hay fotos" in DESCRIPCION_ENVIAR_MULTIMEDIA
    assert "Conservá foto/video según lo pedido" not in DESCRIPCION_SOLICITUDES
    # El modelo sabe qué piezas hay (pasó a Candela una consulta por el respaldo rebatible).
    assert "MATERIAL QUE EXISTE" in DESCRIPCION_ENVIAR_MULTIMEDIA
    assert "Respaldo rebatible con fundas" in DESCRIPCION_ENVIAR_MULTIMEDIA
    assert DESCRIPCION_SOLICITUDES.endswith("ni URLs.\n")
    assert herramienta.NOMBRE == "enviar_multimedia"
    assert herramienta.ARGUMENTO == "solicitudes"


def test_catalogo_igual_a_la_referencia():
    referencia = json.loads((RAIZ / "referencia-f7/logica/multimedia/catalogo.json").read_text(encoding="utf-8"))
    assert CATALOGO == referencia
    assert CATALOGO["version"] == "2026-11-04.1"
    assert len(CATALOGO["assets"]) == 14 and len(CATALOGO["rutas"]) == 22


# ---------- Qué sale para cada pedido (MAPA §3.2) ----------

@pytest.mark.parametrize("solicitudes, piezas", [
    ([pres("fundas")], ["MP02"]),
    ([pres("tipo tapizado")], ["TT01"]),
    ([pres("fundas"), pres("tipo tapizado")], ["MP01"]),
    ([pres("alfombra")], ["AL01", "N8N01"]),
    ([pres("cubrevolante")], ["CV01"]),
    ([pres(p) for p in ["fundas", "tipo tapizado", "alfombra", "cubrevolante"]], ["MP01", "AL01", "N8N01", "CV01"]),
    ([{"producto": "fundas", "contenido": "comparacion", "formato": "video"},
      {"producto": "tipo tapizado", "contenido": "comparacion", "formato": "video"}], ["MP01"]),
    ([{"producto": "fundas", "contenido": "colores"}], ["MP04"]),
    ([{"producto": "tipo tapizado", "contenido": "colores"}], ["MP04"]),
    ([{"producto": "fundas", "contenido": "disenos"}], ["MP05", "MP06", "MP07", "N8N10", "MP08"]),
    ([{"producto": "tipo tapizado", "contenido": "disenos"}], ["MP05", "MP06", "MP07", "N8N10", "MP08"]),
    ([{"producto": "fundas", "contenido": "disenos", "disenos": ["baston", "ultra"], "formato": "foto"}], ["MP05", "MP08"]),
    # Diseños repetidos: se dedupean, no es error.
    ([{"producto": "fundas", "contenido": "disenos", "disenos": ["ultra", "baston", "ultra"]}], ["MP05", "MP08"]),
    ([{"producto": "fundas", "contenido": "calidad"}], ["N8N05", "N8N06"]),
    ([{"producto": "tipo tapizado", "contenido": "calidad"}], ["TT01"]),
    ([{"producto": "alfombra", "contenido": "calidad"}], ["N8N01"]),
    ([{"producto": "cubrevolante", "contenido": "calidad"}], ["CV01"]),
    # Normaliza mayúsculas, tildes y espacios.
    ([{"producto": "Fundas", "contenido": "Presentación"},
      {"producto": "  Tipo   Tapizado", "contenido": "PRESENTACION", "formato": "VIDEO"}], ["MP01"]),
    # 16 iguales: una sola pieza.
    ([pres("fundas")] * 16, ["MP02"]),
    # Orden: primera solicitud que la pidió, orden del catálogo, id.
    ([{"producto": "fundas", "contenido": "disenos"}, {"producto": "tipo tapizado", "contenido": "disenos"},
      pres("fundas"), pres("tipo tapizado"), pres("alfombra"), pres("cubrevolante"),
      {"producto": "fundas", "contenido": "calidad"}, {"producto": "fundas", "contenido": "colores"}],
     ["MP05", "MP06", "MP07", "N8N10", "MP08", "MP01", "AL01", "N8N01", "CV01", "N8N05", "N8N06", "MP04"]),
])
def test_que_sale_para_cada_pedido(solicitudes, piezas):
    plan = plan_de(solicitudes)
    assert plan["estado"] == "listo"
    assert [p["asset_id"] for p in plan["plan"]] == piezas
    assert [p["posicion"] for p in plan["plan"]] == list(range(1, len(piezas) + 1))


@pytest.mark.parametrize("solicitudes, estado, piezas, faltantes", [
    ([pres("fundas", formato="foto")], "sin_material", [], [(0, None, "sin_material_compatible")]),
    ([pres("fundas", formato="video"), pres("tipo tapizado", formato="foto")], "parcial", ["MP02"],
     [(1, None, "sin_material_compatible")]),
    ([{"producto": "alfombra", "contenido": "colores"}], "sin_material", [], [(0, None, "sin_material_especifico")]),
    ([{"producto": "cubrevolante", "contenido": "disenos"}], "sin_material", [], [(0, None, "sin_material_especifico")]),
    ([{"producto": "fundas", "contenido": "disenos", "disenos": ["rojo"]}], "sin_material", [],
     [(0, "rojo", "sin_material_especifico")]),
])
def test_faltantes(solicitudes, estado, piezas, faltantes):
    plan = plan_de(solicitudes)
    assert plan["ok"] is True and plan["estado"] == estado
    assert [p["asset_id"] for p in plan["plan"]] == piezas
    assert [(f["solicitud_indice"], f["diseno"], f["motivo"]) for f in plan["faltantes"]] == faltantes


# ---------- Entradas inválidas (todo o nada) ----------

@pytest.mark.parametrize("solicitudes, errores", [
    ([pres("tapiceria")], [{"campo": "solicitudes[0].producto", "motivo": "producto_no_permitido"}]),
    ([pres("cobertores")], [{"campo": "solicitudes[0].producto", "motivo": "producto_no_permitido"}]),
    ([pres("fundas", extra=1)], [{"campo": "solicitudes[0]", "motivo": "campo_no_permitido"}]),
    ([{"producto": "fundas", "contenido": "comparacion"}],
     [{"campo": "solicitudes", "motivo": "comparacion_requiere_ambas_fundas"}]),
    ([{"producto": "fundas", "contenido": "comparacion"}, {"producto": "alfombra", "contenido": "comparacion"},
      {"producto": "tipo tapizado", "contenido": "comparacion"}],
     [{"campo": "solicitudes", "motivo": "comparacion_requiere_ambas_fundas"}]),
    ([pres("fundas")] * 17, [{"campo": "solicitudes", "motivo": "cantidad_fuera_de_limite"}]),
    ([], [{"campo": "solicitudes", "motivo": "cantidad_fuera_de_limite"}]),
    ('[{"producto":"fundas","contenido":"presentacion"}]', [{"campo": "solicitudes", "motivo": "cantidad_fuera_de_limite"}]),
    ([pres("fundas", reenvio_solicitado="si")], [{"campo": "solicitudes[0].reenvio_solicitado", "motivo": "booleano_requerido"}]),
    ([{"producto": "fundas", "contenido": "colores", "disenos": ["baston"]}],
     [{"campo": "solicitudes[0].disenos", "motivo": "filtro_de_disenos_invalido"}]),
    ([{"producto": "fundas", "contenido": "disenos", "disenos": ["Bastón", "ultra_"]}],
     [{"campo": "solicitudes[0].disenos", "motivo": "nombre_de_diseno_invalido"}]),
    ([pres("fundas", formato=None)], [{"campo": "solicitudes[0].formato", "motivo": "formato_no_permitido"}]),
    (["fundas"], [{"campo": "solicitudes[0]", "motivo": "objeto_requerido"}]),
])
def test_entrada_invalida(solicitudes, errores):
    plan = plan_de(solicitudes)
    assert plan["ok"] is False and plan["estado"] == "entrada_invalida"
    assert plan["errores"] == errores
    assert plan["plan"] == [] and plan["contexto"] is None


def test_normalizar_entrada_defaults_y_contexto():
    r = normalizar_entrada({"solicitudes": [pres("fundas")]})
    assert r["ok"] is True
    assert r["entrada"] == {"account_id": 1, "conversation_id": None, "solicitud_id": None, "modo": "simular",
                            "solicitudes": [{"producto": "fundas", "contenido": "presentacion", "formato": "auto",
                                             "reenvio_solicitado": False}]}
    r = normalizar_entrada({"solicitudes": [pres("fundas")], "modo": "enviar"})
    assert r["errores"] == [{"campo": "conversation_id", "motivo": "entero_positivo_requerido"},
                            {"campo": "solicitud_id", "motivo": "identificador_requerido"}]
    # true no es 1.
    r = normalizar_entrada({"solicitudes": [pres("fundas")], "account_id": True})
    assert r["errores"] == [{"campo": "account_id", "motivo": "cuenta_no_permitida"}]
    # ^...$ de JS no deja pasar un salto de línea final.
    r = normalizar_entrada({"solicitudes": [pres("fundas")], "solicitud_id": "ok\n"})
    assert r["errores"] == [{"campo": "solicitud_id", "motivo": "identificador_requerido"}]


def test_etiqueta_y_locale_compare_como_js():
    assert etiqueta("  Tipo \tTapizado ") == "tipo tapizado"
    assert etiqueta("﻿Diseños") == "disenos"
    assert etiqueta(3) is None
    # Salidas de String.localeCompare en Node 24.
    assert locale_compare("a", "B") == -1
    assert locale_compare("_", "-") == -1
    assert locale_compare("-", ":") == -1
    assert locale_compare("9", "a") == -1
    assert locale_compare("a", "A") == -1
    assert locale_compare("MP08", "N8N10") == -1


# ---------- La herramienta en la sesión local ----------

def test_simular_no_manda_nada():
    ctx = contexto()
    ctx.modo = "simular"
    r = herramienta.ejecutar([pres("alfombra")], ctx)
    assert r["estado"] == "simulado" and r["ok"] is True
    assert [s["asset_id"] for s in r["simulados"]] == ["AL01", "N8N01"]
    assert ctx.sesion.salientes == []


def test_enviar_manda_un_globo_por_pieza_y_devuelve_el_resumen():
    ctx = contexto(ultimo=10)
    r = herramienta.ejecutar([pres("alfombra"), pres("cubrevolante")], ctx)
    ids = [g.chatwoot_message_id for g in ctx.sesion.salientes]
    assert [(g.tipo, g.texto, g.datos["asset_id"]) for g in ctx.sesion.salientes] == [
        ("multimedia", "", "AL01"), ("multimedia", "", "N8N01"), ("multimedia", "", "CV01")]
    assert ctx.sesion.salientes[0].datos == {
        "asset_id": "AL01", "version": "2026-11-04.1", "formato": "video", "mime": "video/mp4",
        "nombre_archivo": CATALOGO["assets"][9]["nombre_archivo"], "titulo": "Presentación de alfombra"}
    assert r == {
        "ok": True, "estado": "aceptado", "solicitud_id": "cw:1:42:10:multimedia-v1", "modo": "enviar",
        "entrega_confirmada": False,
        "aceptados": [
            {"asset_id": "AL01", "version": "2026-11-04.1", "estado": "aceptado", "motivo": None,
             "chatwoot_message_id": ids[0], "solicitud_indices": [0]},
            {"asset_id": "N8N01", "version": "2026-11-04.1", "estado": "aceptado", "motivo": None,
             "chatwoot_message_id": ids[1], "solicitud_indices": [0]},
            {"asset_id": "CV01", "version": "2026-11-04.1", "estado": "aceptado", "motivo": None,
             "chatwoot_message_id": ids[2], "solicitud_indices": [1]},
        ],
        "omitidos": [], "fallidos": [], "desconocidos": [], "control_humano": [], "simulados": [],
        "faltantes": [], "errores": [],
        "solicitudes": [
            {"solicitud_indice": 0, "producto": "alfombra", "contenido": "presentacion", "estado": "aceptado",
             "asset_ids": ["AL01", "N8N01"], "faltantes": []},
            {"solicitud_indice": 1, "producto": "cubrevolante", "contenido": "presentacion", "estado": "aceptado",
             "asset_ids": ["CV01"], "faltantes": []},
        ],
    }
    # Lo que el prompt mostraría como MULTIMEDIA REGISTRADA: la más reciente primero. Las piezas
    # que salieron juntas comparten `lote`, el mensaje del cliente que las originó (el 10).
    assert ctx.sesion.multimedia_registrada == [
        {"asset_id": a, "version": "2026-11-04.1", "aceptado": True, "hay_envio_incierto": False, "lote": 10}
        for a in ["CV01", "N8N01", "AL01"]]


def test_misma_solicitud_sale_omitido_y_turno_nuevo_vuelve_a_mandar():
    ctx = contexto(ultimo=10)
    herramienta.ejecutar([pres("fundas")], ctx)
    primer_id = ctx.sesion.salientes[0].chatwoot_message_id
    r = herramienta.ejecutar([pres("fundas")], ctx)
    assert len(ctx.sesion.salientes) == 1
    assert r["estado"] == "omitido" and r["ok"] is True
    assert r["omitidos"] == [{"asset_id": "MP02", "version": "2026-11-04.1", "estado": "omitido",
                              "motivo": "ya_aceptado_en_esta_solicitud", "chatwoot_message_id": primer_id,
                              "solicitud_indices": [0]}]
    # Misma solicitud_id con otro pedido: se rechaza entero.
    r = herramienta.ejecutar([pres("cubrevolante")], ctx)
    assert r["estado"] == "fallido" and r["ok"] is False
    assert r["fallidos"][0]["motivo"] == "conversacion_ocupada_o_solicitud_incompatible"
    assert len(ctx.sesion.salientes) == 1
    # Turno nuevo: otra solicitud_id, se vuelve a mandar y sube al primer lugar del registro.
    ctx.ultimo_message_id = 15
    assert herramienta.ejecutar([pres("cubrevolante")], ctx)["estado"] == "aceptado"
    ctx.ultimo_message_id = 20
    r = herramienta.ejecutar([pres("fundas")], ctx)
    assert r["estado"] == "aceptado"
    assert [g.datos["asset_id"] for g in ctx.sesion.salientes] == ["MP02", "CV01", "MP02"]
    assert [f["asset_id"] for f in ctx.sesion.multimedia_registrada] == ["MP02", "CV01"]


def test_control_humano_corta_el_lote():
    ctx = contexto(etiquetas=["clientes", " HUMANO "])
    r = herramienta.ejecutar([pres("alfombra")], ctx)
    assert ctx.sesion.salientes == []
    assert ctx.sesion.multimedia_registrada == []
    assert r["estado"] == "control_humano" and r["ok"] is False
    assert [(i["asset_id"], i["motivo"]) for i in r["control_humano"]] == [
        ("AL01", "conversacion_con_humano"), ("N8N01", "lote_detenido_sin_intentar_envio")]
    assert r["lote_detenido"] is True and r["advertencias"] == []
    assert list(r)[-2:] == ["lote_detenido", "advertencias"]
    # Sin la etiqueta, la misma solicitud puede volver a intentar (quedó fallo_previo).
    ctx.sesion.etiquetas = []
    r = herramienta.ejecutar([pres("alfombra")], ctx)
    assert r["estado"] == "aceptado"
    assert len(ctx.sesion.salientes) == 2


def test_entrada_invalida_y_sin_material_no_mandan():
    ctx = contexto()
    r = herramienta.ejecutar([{"producto": "fundas", "contenido": "comparacion"}], ctx)
    assert r == {"ok": False, "estado": "entrada_invalida", "solicitud_id": None, "modo": "simular",
                 "entrega_confirmada": False, "aceptados": [], "omitidos": [], "fallidos": [], "desconocidos": [],
                 "control_humano": [], "simulados": [], "faltantes": [],
                 "errores": [{"campo": "solicitudes", "motivo": "comparacion_requiere_ambas_fundas"}],
                 "solicitudes": []}
    # Hasta el 21/11 acá se probaba pedir fotos de la presentación de fundas: ahora eso manda el video
    # (decisión de Mateo). Sin material sigue siendo lo que no existe, como los colores de alfombras.
    r = herramienta.ejecutar([{"producto": "alfombra", "contenido": "colores"}], ctx)
    assert r["estado"] == "sin_material" and r["modo"] == "enviar" and r["ok"] is False
    assert ctx.sesion.salientes == [] and ctx.sesion.registros.get("multimedia", {}) == {}


def test_pedido_anterior_al_borrar_devuelve_reinicio():
    ctx = contexto(ultimo=10, epoca=10)
    r = herramienta.ejecutar([pres("fundas")], ctx)
    assert ctx.sesion.salientes == []
    assert r == {"estado": "control_humano", "motivo": "conversacion_reiniciada", "pausa_tecnica": True,
                 "bot_pausado": None, "asignacion_confirmada": False, "destino": None,
                 "envio": {"estado": "control_humano", "motivo": "conversacion_reiniciada", "chatwoot_message_id": None},
                 "continuacion_obligatoria": "", "registro_confirmado": True, "requiere_revision": False}


def test_errores_del_llamador_salen_como_objeto():
    assert herramienta.ejecutar([pres("fundas")], contexto(ultimo=0)) == {
        "error": "Falta un ID de mensaje consumido válido para multimedia"}
    assert herramienta.ejecutar({"solicitudes": [pres("fundas")]}, contexto())["estado"] == "entrada_invalida"


# ---------- Decisión de Mateo del 21/11: si piden fotos, va el video ----------
# «Si pide fotos del producto se envía el video directamente, no se dice "No tengo fotos"».
# Si ya tiene ese video (o no puede ver videos) y el producto tiene fotos de diseños, van esas.


def pedir(sesion, solicitudes, **banderas):
    """Un turno nuevo de la conversación: devuelve el resultado y las piezas que salieron en este pedido."""
    antes = len(sesion.salientes)
    ctx = ContextoTurno(sesion=sesion, ultimo_message_id=sesion.nuevo_message_id() + 100, **banderas)
    r = herramienta.ejecutar(solicitudes, ctx)
    return r, [g.datos["asset_id"] for g in sesion.salientes[antes:]]


DISENOS = ["MP05", "MP06", "MP07", "N8N10", "MP08"]


@pytest.mark.parametrize("solicitud, piezas", [
    ({"producto": "alfombra", "contenido": "presentacion", "formato": "foto"}, ["AL01", "N8N01"]),
    ({"producto": "cubrevolante", "contenido": "presentacion", "formato": "foto"}, ["CV01"]),
    ({"producto": "fundas", "contenido": "presentacion", "formato": "foto"}, ["MP02"]),
    ({"producto": "tipo tapizado", "contenido": "calidad", "formato": "foto"}, ["TT01"]),
])
def test_piden_fotos_de_algo_que_solo_tiene_video_y_sale_el_video(solicitud, piezas):
    r, salieron = pedir(SesionLocal(conversation_id=42), [solicitud], pidio_fotos=True)
    assert salieron == piezas
    assert r["estado"] == "aceptado" and r["faltantes"] == []
    assert r["sustituciones"] == [{"solicitud_indice": 0, "pedido": "foto", "enviado": "video"}]
    assert "no digas que" in r["indicacion"].lower()


def test_si_ya_tiene_el_video_y_pide_fotos_van_las_fotos_de_disenos():
    sesion = SesionLocal(conversation_id=42)
    pedir(sesion, [{"producto": "fundas", "contenido": "presentacion", "formato": "video"}])
    r, salieron = pedir(sesion, [{"producto": "fundas", "contenido": "presentacion", "formato": "foto"}],
                        pidio_fotos=True, pidio_multimedia=True)
    assert salieron == DISENOS
    assert r["sustituciones"][0]["enviado"] == "fotos de diseños"
    # El modelo no siempre marca el formato, y las fotos que ya tiene no se repiten: sigue la carta.
    r, salieron = pedir(sesion, [{"producto": "fundas", "contenido": "presentacion", "formato": "auto"}],
                        pidio_fotos=True, pidio_multimedia=True)
    assert salieron == ["MP04"] and r["sustituciones"][0]["enviado"] == "carta de colores"


def test_si_ya_tiene_el_video_y_no_hay_fotos_no_se_repite_y_va_el_catalogo():
    sesion = SesionLocal(conversation_id=42)
    pedir(sesion, [{"producto": "alfombra", "contenido": "presentacion"}])
    for formato in ("foto", "auto"):
        r, salieron = pedir(sesion, [{"producto": "alfombra", "contenido": "presentacion", "formato": formato}],
                            pidio_fotos=True, pidio_multimedia=True)
        assert salieron == [], formato
        assert "catálogo" in r["indicacion"] and "no digas que" in r["indicacion"].lower()


def test_si_no_puede_ver_videos_van_las_fotos_de_disenos_o_el_catalogo():
    r, salieron = pedir(SesionLocal(conversation_id=42),
                        [{"producto": "tipo tapizado", "contenido": "calidad", "formato": "foto"}],
                        pidio_fotos=True, sin_video=True)
    assert salieron == DISENOS
    r, salieron = pedir(SesionLocal(conversation_id=42),
                        [{"producto": "cubrevolante", "contenido": "presentacion", "formato": "foto"}],
                        pidio_fotos=True, sin_video=True)
    assert salieron == [] and "catálogo" in r["indicacion"]


@pytest.mark.parametrize("solicitud, piezas", [
    ({"producto": "fundas", "contenido": "disenos", "formato": "foto"}, DISENOS),
    ({"producto": "tipo tapizado", "contenido": "colores", "formato": "foto"}, ["MP04"]),
    ({"producto": "alfombra", "contenido": "presentacion", "formato": "video"}, ["AL01", "N8N01"]),
])
def test_lo_que_ya_andaba_bien_no_cambia(solicitud, piezas):
    r, salieron = pedir(SesionLocal(conversation_id=42), [solicitud], pidio_fotos=True)
    assert salieron == piezas
    assert "sustituciones" not in r and "indicacion" not in r


def test_si_el_cliente_pidio_fotos_y_el_modelo_no_marco_el_formato_la_indicacion_va_igual():
    r, salieron = pedir(SesionLocal(conversation_id=42), [{"producto": "cubrevolante", "contenido": "presentacion"}],
                        pidio_fotos=True)
    assert salieron == ["CV01"]
    assert "sustituciones" not in r  # el modelo no pidió «foto»: no se le cambió nada
    assert "no digas que" in r["indicacion"].lower()


def test_sin_pedido_de_fotos_no_hay_indicacion():
    r, salieron = pedir(SesionLocal(conversation_id=42), [{"producto": "cubrevolante", "contenido": "presentacion"}])
    assert salieron == ["CV01"] and "indicacion" not in r and "sustituciones" not in r


def test_un_reenvio_pedido_del_video_se_sigue_mandando():
    sesion = SesionLocal(conversation_id=42)
    pedir(sesion, [{"producto": "alfombra", "contenido": "presentacion"}])
    # Pide de nuevo «el video»: no es un pedido de fotos.
    r, salieron = pedir(sesion, [{"producto": "alfombra", "contenido": "presentacion", "reenvio_solicitado": True}],
                        pidio_video=True, pidio_multimedia=True)
    assert salieron == ["AL01", "N8N01"] and "sustituciones" not in r


def test_el_material_que_existe_sale_del_catalogo():
    from agente.f7.multimedia.descripcion import material_que_existe

    texto = material_que_existe(CATALOGO)
    for pieza in CATALOGO["assets"]:
        assert pieza["titulo"] in texto, pieza["id"]
    assert "- alfombra: presentacion = videos «Presentación de alfombra», «Colocación de alfombra»" in texto
    assert "- cubrevolante: presentacion = video «Presentación de cubrevolante»" in texto
    assert "disenos = fotos «Diseño Bastón», «Diseño VIP», «Diseño Hexagonal», «Diseño Diamante», «Diseño Ultra»" in texto
    assert "comparacion" in texto and "«Comparación de fundas y tipo tapizado»" in texto
    # De alfombras y cubrevolante no hay colores ni diseños: no figuran en sus renglones.
    renglon = next(l for l in texto.splitlines() if l.startswith("- alfombra:"))
    assert "colores" not in renglon and "disenos" not in renglon


# ---------- Re-prueba de multimedia del 21/11: no repetir lo que el cliente ya tiene ----------


def test_sin_pedido_de_reenvio_lo_que_ya_tiene_no_sale_aunque_venga_con_material_nuevo():
    sesion = SesionLocal(conversation_id=42)
    pedir(sesion, [{"producto": "fundas", "contenido": "presentacion"}])
    r, salieron = pedir(sesion, [{"producto": "fundas", "contenido": "presentacion"},
                                 {"producto": "alfombra", "contenido": "presentacion"}], pidio_multimedia=False)
    assert salieron == ["AL01", "N8N01"]
    assert [o["asset_id"] for o in r["omitidos"]] == ["MP02"]


def test_nombrar_un_video_no_alcanza_para_reenviar_lo_que_ya_tiene():
    # «se ve en algún video?»: nombra un video, pero no pide que se lo manden de nuevo.
    sesion = SesionLocal(conversation_id=42)
    detalle = [{"producto": "fundas", "contenido": "calidad"}]
    pedir(sesion, detalle)
    r, salieron = pedir(sesion, detalle, pidio_video=True, reenvio_solo_marcado=True)
    assert salieron == [] and r["estado"] == "omitido"
    # Si el modelo marca que el cliente pidió verlo de nuevo, sale.
    r, salieron = pedir(sesion, [{**detalle[0], "reenvio_solicitado": True}], pidio_video=True, reenvio_solo_marcado=True)
    assert salieron == ["N8N05", "N8N06"]


def test_si_nombra_fotos_y_video_y_ya_tiene_el_video_es_un_pedido_de_fotos():
    # «y fotos no tenés entonces? solo video?»
    sesion = SesionLocal(conversation_id=42)
    pedir(sesion, [{"producto": "alfombra", "contenido": "presentacion"}])
    r, salieron = pedir(sesion, [{"producto": "alfombra", "contenido": "presentacion"}], pidio_fotos=True, pidio_video=True)
    assert salieron == [] and "catálogo" in r["indicacion"]


def test_las_fotos_que_ya_tiene_no_se_repiten_y_despues_va_el_catalogo():
    sesion = SesionLocal(conversation_id=42)
    foto = [{"producto": "tipo tapizado", "contenido": "presentacion", "formato": "foto"}]
    assert pedir(sesion, foto, pidio_fotos=True, sin_video=True)[1] == DISENOS
    assert pedir(sesion, foto, pidio_fotos=True, sin_video=True)[1] == ["MP04"]
    r, salieron = pedir(sesion, foto, pidio_fotos=True, sin_video=True)
    assert salieron == [] and "catálogo" in r["indicacion"]


def test_el_video_pedido_antes_de_la_pregunta_de_retapizar_es_el_de_tipo_tapizado():
    r, salieron = pedir(SesionLocal(conversation_id=42),
                        [{"producto": "fundas", "contenido": "presentacion", "formato": "video"}],
                        producto_pendiente="tipo tapizado")
    assert salieron == ["TT01"]
    assert r["sustituciones"] == [{"solicitud_indice": 0, "pedido": "fundas", "enviado": "tipo tapizado"}]


def test_el_material_avisa_que_disenos_y_colores_son_los_mismos_en_las_dos_fundas():
    # Re-prueba del 21/11: ante «y de los diseños de las fundas?» preguntó de cuál de las dos.
    import copy

    from agente.f7.multimedia.descripcion import material_que_existe

    aviso = "son las mismas fotos para fundas y tipo tapizado"
    texto = material_que_existe(CATALOGO)
    assert aviso in texto and "sin preguntar de cuál" in texto
    # Sale del catálogo: si dejan de compartirlas, no lo dice.
    otro = copy.deepcopy(CATALOGO)
    otro["rutas"] = [r for r in otro["rutas"]
                     if not (r["producto"] == "tipo tapizado" and r["contenido"] in ("disenos", "colores"))]
    assert aviso not in material_que_existe(otro)
