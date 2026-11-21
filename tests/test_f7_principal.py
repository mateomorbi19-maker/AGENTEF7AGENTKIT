"""F7, principal sin red: prompt del turno, modalidad, partición, textos fijos y «borrar».

Los resultados esperados salen de correr el mismo caso con el código JS que
corre hoy en n8n (export agente-principal-unificado.json, versión publicada).
Los hash del prompt se calculan sobre la copia original de n8n
(referencia-f7/prompt/SYSTEM_PROMPT_F7_V1.md), no sobre
prompts/f7/SYSTEM_PROMPT_F7_V1.md. Así Mateo puede editar el prompt del agente
sin romper estas pruebas, que verifican que el armado sea igual al de JS.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente.f7.modalidad import modalidad_confirmada, preparar_estado, resolver_modalidad  # noqa: E402
from agente.f7.partir import partir_respuesta_f7  # noqa: E402
from agente.f7.prompt import (  # noqa: E402
    FASE_A_BLOQUES,
    clasificar_fase,
    ensamblar_prompt,
    fecha_buenos_aires,
    leer_bloques,
    leer_metadatos_catalogo,
    resumir_multimedia,
)
from agente.f7.textos import ACK_BORRAR, SALUDO_INICIAL, es_comando_borrar  # noqa: E402

FECHA = "2026-11-15T14:03:07.123-03:00"
REGISTROS = [
    {"asset_id": "MP02", "version": "2026-11-04.1", "aceptado": True, "hay_envio_incierto": False},
    {"asset_id": "MP02", "version": "2026-11-04.1", "aceptado": True, "hay_envio_incierto": False},
    {"asset_id": "TT01", "version": "2026-11-04.1", "aceptado": False, "hay_envio_incierto": True},
    {"asset_id": "MP04", "version": "viejo", "aceptado": True, "hay_envio_incierto": False},
    {"asset_id": "XX99", "version": "2026-11-04.1", "aceptado": True, "hay_envio_incierto": False},
    {"asset_id": "CV01", "version": "2026-11-04.1", "aceptado": False, "hay_envio_incierto": False},
]


PROMPT_ORIGINAL_N8N = (
    Path(__file__).resolve().parents[1] / "referencia-f7" / "prompt" / "SYSTEM_PROMPT_F7_V1.md"
)


@pytest.fixture(scope="module")
def bloques():
    return leer_bloques(PROMPT_ORIGINAL_N8N)


@pytest.fixture(scope="module")
def metadatos():
    return leer_metadatos_catalogo()


# --- Fase -------------------------------------------------------------------

@pytest.mark.parametrize("texto, fase", [
    ("Hola!", "inicio"),
    ("Buenas tardes!!", "inicio"),
    ("me mostrás fotos del diseño?", "multimedia"),
    ("cuánto sale en efectivo?", "cotizacion"),
    ("descuento en efectivo cuánto?", "cotizacion"),
    ("ya te mando el comprobante", "candela"),
    ("quiero pagar", "candela"),
    ("hay descuento?", "candela"),
    ("quién lo va a revisar", "candela"),
    ("me parece caro", "objeciones"),
    ("gol trend 2015", "seguimiento"),
    (None, "seguimiento"),
])
def test_clasificar_fase(texto, fase):
    assert clasificar_fase(texto) == fase


# --- Prompt armado ----------------------------------------------------------

@pytest.mark.parametrize("texto, saludo, modalidad, con_multimedia, fase, sha", [
    ("Hola!", True, "caba", False, "inicio", "2484f359fb2ae61eed5044065324bd7ad59e87b8f7d13a6e5cbbc06201567c05"),
    ("Hola!", False, "envio", True, "inicio", "987e99cc225524c1104985639c087e29a0fd5b617b5486fa3b0213a27a49b648"),
    ("Hola!", False, "otra", False, "inicio", "3bb336a723fc695a4a39d0723715c7fce9947db2509cee4cf8b58638c9a6b8aa"),
    ("me mostrás fotos del diseño?", True, "caba", False, "multimedia", "fe840392e559e37d90d9efad16bec0d2c023bfd2e4369f4491d3872d72d8042b"),
    ("me mostrás fotos del diseño?", False, "envio", True, "multimedia", "5a4cd9a5bc4cec9f8749e7942af9022b7c4e11513b0d84927c8e5e5b15c3e407"),
    ("me mostrás fotos del diseño?", False, "otra", False, "multimedia", "52000a8fb77bade5b9bad6495b98c41d207b5038e71eccc9bc68d3d13f33ac85"),
    ("cuánto sale en efectivo?", True, "caba", False, "cotizacion", "d6e308b962d34ae20f691a4cc4ae4f5579171a806ed251d213c25984e08581cd"),
    ("cuánto sale en efectivo?", False, "envio", True, "cotizacion", "8f74d73f288fab046a7ff6cad2189f956d6ab96e0520cb70040986b2d362b708"),
    ("cuánto sale en efectivo?", False, "otra", False, "cotizacion", "ce4609ddbdd0b787870dc5d354f891621e13bb17f781b719ad5ff3b5d3f5a564"),
    ("ya te mando el comprobante", True, "caba", False, "candela", "2efcfa93d436bde195ea48b84864c9d6d38786af463c8e111dadce72a21bb938"),
    ("ya te mando el comprobante", False, "envio", True, "candela", "d5e33ec61bb2f1e54332863d6c5f9997655e7f0aaab1aad8051712630c0822a6"),
    ("ya te mando el comprobante", False, "otra", False, "candela", "3ed45101943b58fa6c90b38ec71dabdddbfd8edfdcc83b6c2102c71aecc1b466"),
    ("me parece caro", True, "caba", False, "objeciones", "f458d87c0562436104473259d787f94a9be0a8b226221d2d8e0adc36f53a9a4a"),
    ("me parece caro", False, "envio", True, "objeciones", "9f701f8eb138242d63394d1d24e497666c5920ed7a99a182915db51e874e9928"),
    ("me parece caro", False, "otra", False, "objeciones", "4fae448e05e59a9f095cb46575368fd2c60bf7e1e1f76c522fa1bac62852b456"),
    ("gol trend 2015", True, "caba", False, "seguimiento", "ea1667965a6e6463837d7339eb9348ff30b02567b5a83db983e2835a2e647470"),
    ("gol trend 2015", False, "envio", True, "seguimiento", "1b9d1ea9d2b06952ea56a0bea089580c44dc23cd7a4ce51d35fcaad184b5ba30"),
    ("gol trend 2015", False, "otra", False, "seguimiento", "5b43b55e72e1a157b661763c172cb39cea40d1c33b7912f6d3e4805a32a9449f"),
])
def test_prompt_identico_al_de_js(bloques, metadatos, texto, saludo, modalidad, con_multimedia, fase, sha):
    entrada = {"texto": texto, "modalidad_confirmada": modalidad, "saludo_inicial_enviado": saludo,
               "multimedia_registrada": REGISTROS if con_multimedia else []}
    r = ensamblar_prompt(entrada, bloques, FECHA, metadatos)
    assert r["fase_detectada"] == fase
    assert r["bloques_usados"] == FASE_A_BLOQUES[fase]
    assert r["prompt_version"] == "f7-brief-2026-11-05.v9.4-medios-pago-total"
    assert hashlib.sha256(r["prompt_ensamblado"].encode("utf-8")).hexdigest() == sha


def test_prompt_con_fecha_invalida(bloques, metadatos):
    entrada = {"texto": "hola", "modalidad_confirmada": "caba", "saludo_inicial_enviado": True, "multimedia_registrada": []}
    r = ensamblar_prompt(entrada, bloques, "no es fecha", metadatos)
    assert hashlib.sha256(r["prompt_ensamblado"].encode("utf-8")).hexdigest() == (
        "250b632d155783fd0d2dae6ea9f2aafe2f520c8f9289ec515585dfeccbcd1f35")
    assert "Fecha actual en America/Argentina/Buenos_Aires: fecha no disponible\n" in r["prompt_ensamblado"]


def test_prompt_partes_variables(bloques, metadatos):
    entrada = {"texto": "precio", "modalidad_confirmada": "otra", "saludo_inicial_enviado": "true",
               "multimedia_registrada": []}
    p = ensamblar_prompt(entrada, bloques, FECHA, metadatos)["prompt_ensamblado"]
    assert "\nModalidad humana: sin_confirmar.\n" in p
    assert "\n- No reinicies el saludo: continuá según el historial y el mensaje actual.\n" in p
    assert "MULTIMEDIA REGISTRADA (datos internos, no copiar):\n[]\n" in p
    assert p.endswith("\nACCIÓN FINAL: Precio pendiente + modelo/modalidad conocidos: buscar_precio AHORA, omitiendo anio si falta.")
    assert p.startswith(bloques["base"] + "\n\n" + bloques["recorrido"])


def test_resumir_multimedia_igual_que_js(metadatos):
    assert resumir_multimedia(REGISTROS, metadatos) == [
        {"pieza": "MP02", "titulo": "Presentación de fundas a medida", "productos": ["fundas"],
         "contenidos": ["presentacion"], "formato": "video", "aceptado_por_chatwoot": True, "hay_envio_incierto": False},
        {"pieza": "TT01", "titulo": "Colocación y detalle de tipo tapizado", "productos": ["tipo tapizado"],
         "contenidos": ["presentacion", "calidad"], "formato": "video", "aceptado_por_chatwoot": False,
         "hay_envio_incierto": True},
    ]
    assert resumir_multimedia("x", metadatos) == []
    assert resumir_multimedia([None, 5, {"asset_id": 3}], metadatos) == []


def test_leer_bloques_valida(tmp_path):
    ruta = tmp_path / "p.md"
    ruta.write_text("<!-- BLOQUE base -->\na\n<!-- BLOQUE base -->\nb", encoding="utf-8")
    with pytest.raises(ValueError, match="Bloque duplicado: base"):
        leer_bloques(ruta)
    ruta.write_text("<!-- BLOQUE base -->\na\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Falta bloque de prompt: recorrido"):
        leer_bloques(ruta)


def test_fecha_buenos_aires():
    from datetime import datetime, timezone

    assert fecha_buenos_aires(datetime(2026, 11, 15, 17, 3, 7, 123456, tzinfo=timezone.utc)) == FECHA


# --- Modalidad --------------------------------------------------------------

@pytest.mark.parametrize("historial, texto, esperado", [
    ([], "con envío", "envio"),
    ([], "sí envío", "envio"),
    ([], "la opción de envío a Córdoba", "envio"),
    ([], "mandámelo", "envio"),
    ([], "me lo mandan a rosario", "envio"),
    ([], "en el taller", "caba"),
    ([], "colocarlo en su taller", "caba"),
    # Condicionales, dudas, citas y las dos opciones juntas: ambiguo.
    ([], "si es más barato, con envío", None),
    ([], "envío o taller, no sé", None),
    ([], "Si es muy difícil....lo llevo al taller", None),
    # Corrección del 20/11: reafirmar («como dije», «ya te dije») confirma. Con el resolver de n8n
    # contaba como cita y daba None.
    ([], "como dije, con envío", "envio"),
    (["con envío"], "no estoy seguro, envío", None),
    # Negaciones.
    ([], "no, envío no", None),
    (["con envío"], "no envío", None),
    ([], "no quiero envío, prefiero taller", "caba"),
    # Cambios y lo que no es una elección.
    (["con envío"], "mejor en el taller", "caba"),
    (["con envío"], "¿cuánto sale el envío?", "envio"),
    (["en el taller"], "hola", "caba"),
    ([], "vivo en caba por trabajo", None),
    ([], "envío. Si me puede hacer un presupuesto", "envio"),
    # Datos inválidos.
    (["x" * 20001], "con envío", None),
    (["con envío", 3], "con envío", None),
])
def test_resolver_modalidad(historial, texto, esperado):
    assert resolver_modalidad(historial, texto) == esperado
    assert modalidad_confirmada(historial, texto) == (esperado or "sin_confirmar")


def test_preparar_estado():
    datos = {"key": "1:7:0", "texto": "con envío"}
    e = preparar_estado(datos, "0", '[{"asset_id":"MP02"}]', '["hola","con envío"]')
    assert e == {"key": "1:7:0", "texto": "con envío", "estado_texto": "",
                 "multimedia_registrada": [{"asset_id": "MP02"}],
                 "saludo_inicial_gestionado_por_flujo": True, "saludo_inicial_enviado": True,
                 "modalidad_confirmada": "envio", "context_guard": True}
    e = preparar_estado(datos, 3, "no es json", "tampoco")
    assert e["multimedia_registrada"] == [] and e["saludo_inicial_enviado"] is False
    assert e["modalidad_confirmada"] == "sin_confirmar"


# --- Partición --------------------------------------------------------------

@pytest.mark.parametrize("texto, globos", [
    ("Hola. Te paso el link https://maps.app.goo.gl/Nsyib1THu4WCN2L8A?g_st=ipc. Te esperamos.",
     ["Hola", "Te paso el link https://maps.app.goo.gl/Nsyib1THu4WCN2L8A?g_st=ipc", "Te esperamos"]),
    ("La dirección es Av. Olivera 1265, CABA. Abrimos 9.30 hs.",
     ["La dirección es Av. Olivera 1265, CABA", "Abrimos 9.30 hs"]),
    ("Sale $123.456 por transferencia. ¿Te sirve?", ["Sale $123.456 por transferencia", "Te sirve?"]),
    ("**Fundas** a medida:\n- Cuero automotor\n- Colocación en el taller\n\n¿Querés ver fotos?",
     ["Fundas a medida: Cuero automotor Colocación en el taller", "Querés ver fotos?"]),
    ("Mirá [el mapa](https://maps.app.goo.gl/abc_(1)) y escribime a _ventas@f7.com.ar_.",
     ["Mirá el mapa https://maps.app.goo.gl/abc_(1) y escribime a ventas@f7.com.ar"]),
    ('Dijo "perfecto". Listo!', ["Dijo perfecto", "Listo!"]),
    ("Primer párrafo sin punto\n\nSegundo párrafo", ["Primer párrafo sin punto", "Segundo párrafo"]),
    ("# Título\n```\ncodigo\n```\n~~tachado~~ y _énfasis_.", ["Título codigo tachado y énfasis"]),
    ("Hola,\nte respondo. ¿Avanzamos?", ["Hola, te respondo", "Avanzamos?"]),
    ("Escribí a www.f7.com.ar. Gracias!", ["Escribí a www.f7.com.ar", "Gracias!"]),
    ("", []),
    (None, []),
])
def test_partir_respuesta(texto, globos):
    assert partir_respuesta_f7(texto) == globos


# --- Textos fijos y «borrar» ------------------------------------------------

def test_textos_fijos():
    assert SALUDO_INICIAL == "Hola, te comunicaste con F7-Automotriz"
    assert ACK_BORRAR == "Ya borre mi memoria, a partir de ahora comienza una conversación nueva"


@pytest.mark.parametrize("texto", [
    "borrar", "Borrar", "borrá", "Bórrame la memoria", "borra todo", "¡borrar el historial!",
    "  BORRAR!!  ", "borrar mi memoria", "borrar la  memoria", "ｂｏｒｒａｒ", "borrar?",
])
def test_es_comando_borrar(texto):
    assert es_comando_borrar(texto) is True


@pytest.mark.parametrize("texto", ["borrar memoria", "borrarlo", "por favor borrar", "borrar todo ya", "", None, 5])
def test_no_es_comando_borrar(texto):
    assert es_comando_borrar(texto) is False


# --- Cambios de Mateo del 17/11 ---------------------------------------------
# El resolver de n8n no entendía respuestas naturales y el agente volvía a
# preguntar envío o taller («Coloco en Cab» → otra vez la pregunta).

@pytest.mark.parametrize("texto, esperado", [
    ("Coloco en Cab", "caba"), ("Coloco en CABA", "caba"), ("lo coloco en el taller", "caba"),
    ("retiro en el taller", "caba"), ("en Capital", "caba"), ("lo hago en el taller", "caba"),
    ("en el taler", "caba"), ("dale, lo coloco en caba", "caba"),
    ("me lo mandan", "envio"), ("lo quiero con envio", "envio"), ("mandalo", "envio"),
    ("por correo", "envio"), ("a mi casa", "envio"), ("si, me lo mandan", "envio"),
    # Lo que no es una elección sigue sin contar.
    ("¿hacen envíos a Neuquén?", "sin_confirmar"), ("¿coloco en caba?", "sin_confirmar"),
    ("si coloco en caba cuanto sale?", "caba"), ("me lo mandan?", "sin_confirmar"),
    ("no, en caba no", "sin_confirmar"), ("envio o taller?", "sin_confirmar"),
    ("lo coloco yo", "sin_confirmar"), ("tienen taller en caba?", "sin_confirmar"),
    ("si me lo mandan, mejor", "sin_confirmar"), ("vivo en Neuquén", "sin_confirmar"),
])
def test_modalidad_respuestas_naturales(texto, esperado):
    assert modalidad_confirmada([texto], texto) == esperado


def test_modalidad_la_conversacion_de_mateo():
    historial = ["¿Tienen fotos de las alfombras?", "Preco de fundas por favor", "Coloco en Cab", "Toyota",
                 "Toyota Etios"]
    assert modalidad_confirmada(historial, historial[-1]) == "caba"


def test_partir_no_corta_en_etc():
    assert partir_respuesta_f7("Qué modelo tenés? (por ejemplo Corolla, Hilux, Etios, etc.)") == [
        "Qué modelo tenés? (por ejemplo Corolla, Hilux, Etios, etc.)"]


# --- Corrección del 20/11: modalidad dicha de forma natural -----------------
# Campaña de pruebas con conversaciones reales: el agente repetía «envío o
# taller» aunque el cliente ya había contestado, y una pregunta posterior
# borraba la modalidad ya confirmada.

def _modalidad_20_11(historial, texto):
    """Resuelve sin el lote en el historial y con el lote (como en el turno real): tiene que dar igual."""
    resultado = resolver_modalidad(historial, texto)
    assert resolver_modalidad([*historial, texto], texto) == resultado
    return resultado


@pytest.mark.parametrize("texto", [
    # Un adverbio (o «yo») entre el verbo y «en el taller».
    "Es el mismo modelo de suran que el del video\nlo coloco ahi en el taller",
    "lo coloco ahi en el taller", "Lo coloco ahí en el taller", "lo coloco allá en el taller",
    "lo coloco alla en el taller", "lo coloco directamente en el taller", "lo coloco yo en el taller",
    "LO COLOCO AHI EN EL TALLER", "las coloco ahí en Capital", "lo coloco ahi en capital federal",
    "voy directamente al taller", "ahí en el taller",
    # Reafirmar («ya te dije») no es citar otra cosa: confirma.
    "en el taller!! ya te lo dije arriba", "en el taller, ya te lo dije", "en el taller te dije",
    "ya te dije que en el taller",
    # Pedir el precio de la opción taller es elegirla.
    "hola, cuanto salen las fundas para un 208 colocadas ahi en capital?",
    "cuanto sale colocado en el taller?", "precio con colocacion en el taller",
    "¿Cuánto sale colocado en el taller?", "Precio con colocación en el taller",
    "cuanto salen colocadas en capital federal?", "cuanto salen colocadas allá en el taller?",
])
def test_modalidad_natural_taller(texto):
    assert _modalidad_20_11([], texto) == "caba"


@pytest.mark.parametrize("texto", [
    # Reafirmar confirma.
    "envio, ya te dije q soy de mendoza", "Con envío, como te dije", "te dije con envio",
    # Pedir el precio de la opción envío es elegirla.
    "Hola precio de fundas para un Onix 2021 con envio a Bahia Blanca, pago en efectivo",
    "La de envío cuánto salen", "cuanto sale con envio? y le pueden bordar el logo de ford?",
    "precio con envio", "cuanto sale por envio a cordoba",
    "Precio con envío", "¿Cuánto sale con envío a Córdoba?", "y con envio cuanto sale?",
    "la opcion de envio cuanto sale?",
    # «capital» como parte del nombre de la ciudad no es el taller de CABA.
    "cuanto sale con envio a cordoba capital?",
])
def test_modalidad_natural_envio(texto):
    assert _modalidad_20_11([], texto) == "envio"


@pytest.mark.parametrize("texto", [
    # Guion: preguntar si hacen envíos, por el costo o el tiempo del envío, o vivir lejos, no es elegir envío.
    "hacen envios?", "¿Hacen envíos a Mendoza?", "mandan a cordoba?",
    "hola soy de mndoza, mandan para un cronos? lisa q sale? gracias",
    "negro algun diseño clasico, es para un uber no me interesa mucho el diseño sino q no destruyan el tapizado"
    " y q la funda dure, q salen y q demora tienen para enviarlas?",
    "cuanto me sale el envio a ushuaia de un cubrevolante?", "cuanto sale el envio?", "el envio es gratis?",
    "cuanto tarda el envio?", "cuanto tarda con envio?",
    "soy de cordoba capital", "no puedo, estoy en cordoba",
    # Preguntar por el taller o por la colocación tampoco es elegir el taller.
    "donde queda el taller?", "atienden los sabados en el taller?", "la colocacion esta incluida?",
    "La colocación con qué cargo cuenta?", "cuanto sale la colocacion en el taller?",
    "lo coloco ahi en el taller?", "decime si la colocacion esta incluida",
    # Preguntar qué incluye un precio no es pedir el precio de esa opción.
    "ese precio es con envio?",
    # Las dos opciones, condicionales y citas de verdad siguen sin ser una elección.
    "envio o taller?", "cual me conviene, envio o colocarlo ahi?",
    "cuanto sale con envio y cuanto colocado en el taller?",
    "Si es muy difícil....lo llevaría a colocar\nPero si es fácil, no tendría inconveniente en recibirlo y hacerlo yo",
    # («si lo coloco ahi en el taller cuanto sale?» dejó de estar acá el 21/11: pedir el precio de un
    # escenario lo elige; ver test_modalidad_taller_dicho_de_otras_maneras.)
    "antes quería envío", "no te dije envio",
])
def test_modalidad_natural_no_elige(texto):
    assert _modalidad_20_11([], texto) is None


@pytest.mark.parametrize("historial, texto, esperado", [
    # Una pregunta posterior sobre la colocación o el envío no borra lo elegido.
    (["Lo coloco en el taller"],
     "dejá la alfombra. pasame el total de fundas y cubrevolante y decime si la colocacion esta incluida", "caba"),
    (["Lo coloco en el taller"], "y la colocacion la cobran aparte?", "caba"),
    ([], "Lo coloco en el taller\nLa colocación con qué cargo cuenta?", "caba"),
    (["con envio"], "cuanto tarda el envio?", "envio"),
    (["con envio"], "y cuanto sale el envio?", "envio"),
    (["con envio"], "queria saber si el envio tiene costo", "envio"),
    (["Lo coloco en el taller"], "ese precio es con envio?", "caba"),
    # Reafirmar lo ya elegido lo confirma.
    (["con envio"], "con envio, como te dije", "envio"),
    (["Lo coloco en el taller"], "en el taller, ya te lo dije", "caba"),
    # Los cambios de verdad, las negaciones y las dudas siguen como antes.
    (["con envio"], "mmm mejor paso por el taller y pago en efectivo, cuanto queda?", "caba"),
    (["Lo coloco en el taller"], "y con envio cuanto sale?", "envio"),
    (["con envio"], "no quiero envio", None),
    (["Lo coloco en el taller"], "no estoy seguro, capaz con envio", None),
    (["con envio"], "si me conviene voy al taller", None),
])
def test_modalidad_persiste(historial, texto, esperado):
    assert _modalidad_20_11(historial, texto) == esperado


@pytest.mark.parametrize("historial, texto", [
    # Reafirmar sin una elección que se reconozca sigue siendo ambiguo, igual que antes del 20/11.
    (["en el taller"], "lo que dije fue envio"),
    (["en el taller"], "no te dije envio"),
    (["con envio"], "no dije taller"),
])
def test_modalidad_reafirmar_sin_eleccion_clara_sigue_ambiguo(historial, texto):
    assert _modalidad_20_11(historial, texto) is None


# --- Corrección del 20/11, segunda parte ------------------------------------
# Respuestas reales del relevamiento de Messenger (M11, M15, M16) que tampoco se
# reconocían, y las variantes naturales del mismo error: el cliente ya nombró la
# opción al pedir o al preguntar el precio y el agente volvía a preguntar.

@pytest.mark.parametrize("texto, esperado", [
    # Respuestas reales de clientes.
    ("Hola buenos días quisiera colocarlo en CABA", "caba"),                          # M15
    ("Colocar y soy de flores CABA", "caba"),                                         # M11
    ("Hola  es para una suran2013  precio  colocación  incluida gracias", "caba"),    # M16
    # «Quisiera…», como en la pregunta del guion («Quisieras la opción de envio o colocarlo…»).
    ("quisiera la opcion de envio", "envio"), ("quisiera envio", "envio"),
    ("quisiera colocarlo en el taller", "caba"), ("colocarlo en nuestro taller", "caba"),
    ("colocarlo ahi en el taller", "caba"),
    # Un pedido que nombra una sola opción la elige, pregunte o no el precio.
    ("quiero las fundas con envio a cordoba", "envio"),
    ("quiero fundas para un gol con envio a salta", "envio"),
    ("las quiero colocadas en el taller", "caba"),
    ("cuanto es con envio a cordoba?", "envio"), ("a cuanto estan con envio?", "envio"),
    ("cuanto con envio?", "envio"), ("pasame el total con envio", "envio"),
    ("me cotizas con envio a cordoba?", "envio"), ("que costo tiene con envio?", "envio"),
    ("cuanto sale con envio a capital federal?", "envio"),
    ("cuanto sale con envio y cuanto tarda?", "envio"),
    ("cuanto sale con colocacion?", "caba"), ("precio con la colocacion en el taller", "caba"),
    ("cuanto sale en el taller?", "caba"), ("y en el taller cuanto sale?", "caba"),
    ("lo coloco en el taller cuanto sale", "caba"), ("coloco en caba cuanto sale?", "caba"),
    # Lo que el cliente afirma después de una pregunta se lee aparte.
    ("cuanto sale? lo coloco en el taller", "caba"),
    ("cuanto sale con envio? no soy de capital", "envio"),
    ("hacen envios a cordoba? con envio entonces", "envio"),
])
def test_modalidad_pedidos_que_nombran_una_opcion(texto, esperado):
    assert _modalidad_20_11([], texto) == esperado


@pytest.mark.parametrize("texto", [
    # Relevamiento de Messenger: lo que no fija una modalidad.
    "Me interesan los dos precios, soy de zonz sur, Florencio Varela, pero voy casi todos los días a Caba",  # M21
    "No voy a colocarlas allá!!!",                                                                           # M25
    "tengo una ecoesport 2013, vivo en Carlos Paz,  hacen envíos y que costo tienen?",
    "Luego te envío", "2026 soy de neuquen capital",
    # Dos opciones, comparaciones y alternativas.
    "cuanto sale con envio o retirando?", "sale lo mismo con envio que en el taller?",
    "cuanto sale colocado en el taller sin envio?",
    # Tiempo, costo del envío o de la colocación, y precios ya dados.
    "cuanto tiempo tarda con envio?", "cuanto demora con envio a cordoba?", "en cuanto llega con envio?",
    "precio del envio", "cuanto cobran por el envio?", "cuanto sale colocarlo en el taller?",
    "ese precio tiene la colocacion incluida?", "esos precios son con envio?", "el precio ya esta con envio?",
    "quisiera saber si hacen envios", "quisiera saber cuanto sale el envio",
    # Negar, o corregirse después de reafirmar.
    "no quiero con envio, cuanto sale?", "te dije envio pero voy yo",
    # Vivir en CABA no es elegir el taller.
    "estoy en caba, cuanto sale?", "cuanto sale? estoy en caba",
])
def test_modalidad_pedidos_que_no_eligen(texto):
    assert _modalidad_20_11([], texto) is None


@pytest.mark.parametrize("historial, texto, esperado", [
    (["con envio"], "y en el taller cuanto sale?", "caba"),
    (["con envio"], "pero ya te dije que con envio", "envio"),
    (["Lo coloco en el taller"], "cuanto sale con envio? no soy de capital", "envio"),
    (["con envio"], "cuanto tarda con envio?", "envio"),
    (["Lo coloco en el taller"], "sale lo mismo con envio que en el taller?", "caba"),
])
def test_modalidad_pedidos_con_historial(historial, texto, esperado):
    assert _modalidad_20_11(historial, texto) == esperado


# --- Prueba de «romper el flujo» del 21/11 ----------------------------------
# El agente preguntaba envío o taller aunque el cliente ya lo había dicho, no
# registraba el cambio de una opción a la otra y quedaba repitiendo la pregunta.

@pytest.mark.parametrize("historial, texto", [
    ([], "Buenas, fundas para Sandero con envío a Posadas, qué precio tienen?"),                                   # R16
    ([], "hola necesito alfombras para una hilux y fundas para un etios, las dos cosas con envio a neuquen capital"),  # R06
    ([], "ola kiero presio d las fundas pa mi ecoesport kinetik 2014 con embio a tucuman"),                        # R09
    (["con embio a tucuman"], "embio a tucuman t dije"),                                                           # R09
    ([], "fundas para un Sandero con envío"), ([], "alfombras para hilux con envio"),
    ([], "fundas sandero envio a posadas"), ([], "con enbio"),
    (["lo llevo al taller"], "al final solo la Amarok, y con envío a Trelew"),                                     # R02
    (["las coloco en el taller"], "y si mejor me las mandás a Tandil?"),                                           # R38
    (["las coloco en el taller"], "pero te pregunto con envío a Tandil"),                                          # R38
    (["las coloco en el taller"], "mandamelas a Tandil"),
    ([], "Hola, quiero alfombras para un Gol Power 2008, piso y baúl. Me las mandás a Paraná?"),                   # R41
    ([], "necesito que me las manden a Paraná"),
    ([], "todo por envío entonces"),
    (["Las fundas mandamelas a Corrientes y la alfombra la retiro yo en el taller"], "todo por envío entonces"),   # R36
    (["lo coloco en el taller"], "y con envío?"),
    (["lo coloco en el taller"], "cuánto sale si me las mandan?"),
])
def test_modalidad_envio_dicho_de_otras_maneras(historial, texto):
    assert _modalidad_20_11(historial, texto) == "envio"


@pytest.mark.parametrize("historial, texto", [
    ([], "a medida. es para colocar en el taller, cuánto salen?"),                                                 # R08
    ([], "fundas para una Toro para colocar en el taller"),
    ([], "lo quiero colocado"), ([], "cuánto sale colocado?"),
    (["con envio a san juan"], "y para colocar ahí cuánto sale? capaz viajo"),                                     # R35
    (["con envio a san juan"], "no, te pregunto cuánto sale si lo coloco en el taller"),                           # R35
    ([], "si lo coloco ahi en el taller cuanto sale?"),
    (["con envio"], "y si voy al taller?"), (["con envio"], "y si lo coloco en el taller?"),
    (["con envio"], "y colocadas en el taller?"), (["con envio"], "y en el taller?"),
])
def test_modalidad_taller_dicho_de_otras_maneras(historial, texto):
    assert _modalidad_20_11(historial, texto) == "caba"


@pytest.mark.parametrize("historial, texto, esperado", [
    # Lo que se parece a lo de arriba y no es una elección.
    ([], "precio del envio a cordoba", None),
    ([], "si voy al taller me hacen descuento?", None),
    ([], "capaz me las mandas a tandil?", None),
    ([], "me mandas fotos?", None), ([], "mandame el video", None),
    ([], "no me las mandes a tandil", None),
    ([], "cuánto salen con envío a Chaco y cuánto colocadas en el taller? quiero comparar", None),                 # R58
    ([], "Las fundas mandamelas a Corrientes y la alfombra la retiro yo en el taller", None),                      # R36
    ([], "que las retire mi hermano en el taller", None),
    (["lo coloco en el taller"], "mandame la ubicacion y el horario del taller", "caba"),
    (["lo coloco en el taller"], "me mandas la direccion?", "caba"),
    (["con envio"], "viene colocado?", "envio"),
])
def test_modalidad_parecidos_que_no_cambian_nada(historial, texto, esperado):
    assert _modalidad_20_11(historial, texto) == esperado


def test_partir_no_corta_en_una_abreviatura_pegada_a_la_palabra():
    # Prueba del 21/11 (R05): la pregunta por el Corolla salía en tres globos, cortada en «T.ENTERO».
    texto = ("Para fundas, ¿cuál de estas opciones corresponde a tu vehículo: COROLLA RESPALDO T.ENTERO - 2004 "
             "o COROLLA 2025 o COROLLA RESPALDO T.DIVIDIDOS- XLI 2017?")
    assert partir_respuesta_f7(texto) == [texto.replace("¿", "")]
    # Un punto de verdad sigue cortando, aunque falte el espacio.
    assert partir_respuesta_f7("Listo.Ahora va lo otro. Chau") == ["Listo", "Ahora va lo otro", "Chau"]


# --- Prueba de «romper el flujo» del 21/11: la fase del turno ----------------
# La respuesta fija a una objeción y la regla de pasar los turnos a Candela solo le llegaban al
# modelo con ciertas palabras. «Es carísimo» o «puedo ir mañana?» no estaban.

@pytest.mark.parametrize("texto, fase", [
    ("uh es carísimo, en mercado libre las consigo a 80 lucas", "objeciones"),     # R14
    ("en otro lado me cobran la mitad", "objeciones"),
    ("igual me parece mucha plata", "objeciones"),
    ("son muy caras", "objeciones"),
    ("no quiero señar sin ver el trabajo", "objeciones"),
    ("son confiables? tengo miedo de que sea una estafa", "objeciones"),
    ("perfecto. puedo ir mañana a la mañana?", "candela"),                          # R20
    ("cuándo puedo llevar el auto?", "candela"),
    ("puedo pasar el sábado a colocarlas?", "candela"),
    # Lo que se parece y no cambia de fase.
    ("cuál sale más barato?", "seguimiento"),
    ("voy mañana al taller, cuánto salen las fundas para un gol?", "cotizacion"),
    ("tienen garantía?", "seguimiento"),
    ("mañana te confirmo", "seguimiento"),
    ("puedo pagar mañana?", "seguimiento"),
    ("lo compré en mercado libre y vino fallado", "seguimiento"),
    ("puedo ir al taller o prefieren mandarlo?", "seguimiento"),
])
def test_fase_de_objeciones_y_turnos_dichos_de_otra_manera(texto, fase):
    assert clasificar_fase(texto) == fase


# Re-prueba del 21/11 (R55): «las fundas del Gol las coloco en el taller» no se reconocía porque
# la frase empieza por lo que se va a colocar, no por el verbo.
@pytest.mark.parametrize("texto, esperado", [
    ("las fundas del Gol las coloco en el taller", "caba"),
    ("el auto lo llevo al taller", "caba"),
    ("las alfombras las retiro por el taller", "caba"),
    ("las fundas me las mandan a Rosario", "envio"),
    ("las fundas las coloco en el taller?", None),
    ("las fundas no las coloco en el taller", None),
])
def test_modalidad_cuando_la_frase_empieza_por_el_producto(texto, esperado):
    assert _modalidad_20_11([], texto) == esperado
