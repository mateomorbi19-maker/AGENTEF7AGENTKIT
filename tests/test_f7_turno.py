"""Pruebas del turno de F7 y de la web en modo F7. Sin red y sin gastar tokens.

El modelo es uno falso que devuelve respuestas armadas a mano (con o sin
pedidos de herramientas) y anota lo que recibe. La planilla es una inventada,
con importes inventados.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente.f7.salida import MARCA_MEMORIA  # noqa: E402
from agente.f7.textos import ACK_BORRAR, SALUDO_INICIAL  # noqa: E402
from agente.f7.turno import AgenteF7  # noqa: E402

# Importes inventados, con la forma de la hoja oficial.
PLANILLA = [
    {"title": "Fundas a medida", "sheetId": 877828453, "values": [
        ["RENAULT"],
        ["Marca y Modelo de vehículo", "Juego completo (5 plazas)", "", "2 ASIENTOS INDIVIDUALES", ""],
        ["", "EFECTIVO", "TRANF", "EFECTIVO", "TRANF"],
        ["CLIO", 140000, 150000, 80000, 90000]]},
]


def leer_hojas_falso(titulos):
    return [copy.deepcopy(h) for h in PLANILLA if h["title"] in titulos]


class ModeloFalso:
    """Devuelve las respuestas en orden y anota cada entrada que recibe."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.entradas: list[list] = []
        self.herramientas = None

    def bind_tools(self, herramientas, **kwargs):
        self.herramientas = herramientas
        return self

    def invoke(self, mensajes):
        self.entradas.append(list(mensajes))
        if not self.respuestas:
            raise AssertionError("se llamó al modelo más veces de las previstas")
        return self.respuestas.pop(0)


def llamada(nombre, argumento, valor, ident="t1"):
    return AIMessage("", tool_calls=[{"name": nombre, "args": {argumento: valor}, "id": ident}])


def agente(respuestas):
    modelo = ModeloFalso(respuestas)
    return AgenteF7(modelo, leer_hojas=leer_hojas_falso), modelo


def tipos(resultado):
    return [g.tipo for g in resultado.globos]


# -- borrar ---------------------------------------------------------------------


def test_borrar_confirma_saca_humano_y_arranca_memoria_nueva():
    a, modelo = agente([])
    a.sesion.etiquetas[:] = ["cliente", "humano"]
    a.memoria = [("human", "hola"), ("ai", "buenas")]
    a.sesion.multimedia_registrada.append(
        {"asset_id": "AL01", "version": "v", "aceptado": True, "hay_envio_incierto": False}
    )

    r = a.responder("borrar")

    assert [(g.tipo, g.texto) for g in r.globos] == [("borrar", ACK_BORRAR)]
    assert a.sesion.etiquetas == ["cliente"]
    assert a.memoria == []
    assert a.sesion.multimedia_registrada == []
    assert a.sesion.epoca == r.detalle["message_id"]
    assert modelo.entradas == [], "borrar no pasa por el modelo"


def test_despues_de_borrar_vuelve_a_saludar():
    a, _ = agente([AIMessage("Buenas"), AIMessage("Hola de nuevo")])
    assert tipos(a.responder("hola"))[0] == "saludo"
    a.responder("borrar")
    assert tipos(a.responder("hola"))[0] == "saludo"


# -- saludo y memoria -----------------------------------------------------------


def test_saludo_solo_en_el_primer_mensaje_y_memoria_entre_turnos():
    a, modelo = agente([AIMessage("En qué te puedo ayudar?"), AIMessage("Dale")])

    r1 = a.responder("hola")
    assert r1.error is None
    assert r1.globos[0].tipo == "saludo" and r1.globos[0].texto == SALUDO_INICIAL
    assert tipos(r1)[1:] == ["texto"]
    assert r1.detalle["saludo"] is True

    r2 = a.responder("quiero fundas")
    assert r2.error is None
    assert "saludo" not in tipos(r2)
    assert [g.texto for g in r2.globos] == ["Dale"]

    # El segundo turno ve lo hablado: el lote anterior, la salida segura y el lote nuevo.
    segunda = modelo.entradas[1]
    assert isinstance(segunda[0], SystemMessage)
    assert [type(m) for m in segunda[1:]] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in segunda[1:]] == ["hola", "En qué te puedo ayudar?", "quiero fundas"]
    assert a.memoria[-2:] == [("human", "quiero fundas"), ("ai", "Dale")]


def test_el_prompt_va_en_dos_bloques_y_solo_el_fijo_se_cachea():
    a, modelo = agente([AIMessage("Hola")])
    r = a.responder("hola")

    sistema = modelo.entradas[0][0]
    assert isinstance(sistema.content, list) and len(sistema.content) == 2
    fijo, resto = sistema.content
    assert fijo["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in resto
    completo = fijo["text"] + resto["text"]
    assert "CONTEXTO OPERATIVO SUMINISTRADO POR EL WORKFLOW" in resto["text"]
    assert "El flujo ya envió su saludo inicial en este turno." in completo
    assert r.detalle["bloques_usados"][:3] == ["base", "recorrido", "conocimiento"]
    assert r.detalle["prompt_version"]
    # Las tres herramientas, con el esquema de n8n.
    nombres = [h.name for h in modelo.herramientas]
    assert nombres == ["buscar_precio", "enviar_multimedia", "derivar_humano"]
    esquema = modelo.herramientas[0].args_schema
    assert esquema["required"] == ["pedido"] and esquema["additionalProperties"] is False


def test_si_falla_el_modelo_el_error_llega_y_no_se_guarda_memoria():
    class Roto(ModeloFalso):
        def invoke(self, mensajes):
            raise RuntimeError("se cayó la API")

    a = AgenteF7(Roto([]), leer_hojas=leer_hojas_falso)
    r = a.responder("hola")
    assert "se cayó la API" in r.error
    assert tipos(r) == ["saludo"]
    assert a.memoria == []


# -- cotización -----------------------------------------------------------------


def test_cotizacion_manda_el_globo_descarta_el_texto_libre_y_anota_la_memoria():
    pedido = {"consultas": [{"producto": "fundas", "modelo": "Clio"}], "tipo_solicitud": "consulta"}
    a, modelo = agente([
        llamada("buscar_precio", "pedido", pedido),
        AIMessage("Te paso el presupuesto: sale $999.999 por transferencia"),
    ])

    r = a.responder("hola, precio de fundas para clio\nen el taller")

    assert r.error is None, r.error
    assert r.detalle["modalidad"] == "caba"
    # Antes de la primera cotización de fundas a medida va su presentación con el video (paso 2).
    assert tipos(r) == ["saludo", "texto", "texto", "multimedia", "cotizacion"]
    cotizacion = r.globos[-1].texto
    assert "Clio" in cotizacion and "$150.000" in cotizacion
    assert "999.999" not in " ".join(g.texto for g in r.globos)

    # La herramienta le devolvió al modelo el JSON del subflujo.
    resultado = modelo.entradas[1][-1]
    assert isinstance(resultado, ToolMessage)
    assert json.loads(resultado.content)["estado"] == "cotizado"
    assert r.detalle["herramientas"][0]["herramienta"] == "buscar_precio"
    assert r.detalle["herramientas"][0]["resultado"]["estado"] == "cotizado"
    assert r.detalle["control"]["final"]["output"] == ""

    # En la memoria queda la nota de cotización, no el texto crudo con el importe.
    rol, guardado = a.memoria[-1]
    assert rol == "ai" and MARCA_MEMORIA in guardado
    assert "999.999" not in guardado and "150.000" not in guardado


# -- derivación -----------------------------------------------------------------


def test_derivacion_confirma_el_pase_y_el_turno_siguiente_calla():
    a, modelo = agente([
        llamada("derivar_humano", "motivo", "pago"),
        AIMessage("Listo, te paso con Candela"),
    ])

    r = a.responder("ya quiero pagar la seña")
    assert r.error is None, r.error
    assert tipos(r) == ["saludo", "derivacion"]
    assert "humano" in a.sesion.etiquetas
    assert r.detalle["nota"]

    llamadas = len(modelo.entradas)
    r2 = a.responder("hola? sigue ahí?")
    assert r2.globos == [] and r2.error is None
    assert r2.detalle["accion"] == "silencio_humano" and r2.detalle["nota"]
    assert len(modelo.entradas) == llamadas, "con «humano» no se llama al modelo"


def test_pedido_de_persona_sin_derivar_dispara_la_derivacion_automatica():
    a, _ = agente([AIMessage("Claro, en un rato te escribe alguien")])

    r = a.responder("quiero hablar con una persona")

    assert r.error is None, r.error
    assert r.detalle["derivacion_automatica"]["motivo"] == "revision_especial"
    assert r.detalle["derivacion_automatica"]["solicitud_id"].endswith(":derivacion-v1")
    assert "derivacion" in tipos(r)
    assert "humano" in a.sesion.etiquetas


# -- web --------------------------------------------------------------------------


def _eventos_sse(cuerpo: str) -> list[tuple[str, dict]]:
    eventos = []
    for bloque in cuerpo.strip().split("\n\n"):
        tipo = next(l[7:] for l in bloque.splitlines() if l.startswith("event: "))
        datos = next(l[6:] for l in bloque.splitlines() if l.startswith("data: "))
        eventos.append((tipo, json.loads(datos)))
    return eventos


@pytest.fixture
def web_f7(monkeypatch):
    from fastapi.testclient import TestClient

    from agente.web import app as web

    monkeypatch.setenv("AGENTE", "f7")
    falso, modelo = agente([
        AIMessage(
            "Hola. En qué te ayudo?",
            usage_metadata={"input_tokens": 10, "output_tokens": 3, "total_tokens": 13},
        ),
    ])
    monkeypatch.setattr(web, "_agente_f7", falso)
    return TestClient(web.app), web, modelo


def test_web_en_modo_f7_manda_un_globo_por_mensaje(web_f7):
    cliente, web, _ = web_f7

    r = cliente.post("/api/mensaje", json={"texto": "hola"})
    assert r.status_code == 200
    eventos = _eventos_sse(r.text)

    globos = [d for t, d in eventos if t == "globo"]
    assert [g["tipo"] for g in globos] == ["saludo", "texto", "texto"]
    assert globos[0]["texto"] == SALUDO_INICIAL
    assert [g["texto"] for g in globos[1:]] == ["Hola", "En qué te ayudo?"]

    tipos_evento = [t for t, _ in eventos]
    assert tipos_evento[-2:] == ["detalle", "fin"]
    detalle = dict(eventos)["detalle"]
    assert detalle["fase"] and detalle["modalidad"] == "sin_confirmar"
    fin = dict(eventos)["fin"]
    assert fin["tokens_entrada"] == 10 and fin["tokens_salida"] == 3
    assert fin["mensajes_en_memoria"] == 2

    assert cliente.get("/api/estado").json()["agente"] == "f7"
    assert cliente.post("/api/reiniciar").json()["mensajes_en_memoria"] == 0
    assert web._agente_f7.memoria == []


def test_web_en_modo_f7_edita_el_prompt_de_f7(web_f7, monkeypatch, tmp_path):
    cliente, web, _ = web_f7
    from agente.f7 import prompt

    p = cliente.get("/api/prompt").json()
    assert "<!-- BLOQUE base -->" in p["texto"]
    assert p["ruta"].endswith("SYSTEM_PROMPT_F7_V1.md")

    # Guardar va al archivo de F7 (acá, a una copia) y avisa si se rompió un bloque.
    copia = tmp_path / "prompt.md"
    monkeypatch.setattr(prompt, "RUTA_PROMPT", copia)
    r = cliente.post("/api/prompt", json={"texto": "<!-- BLOQUE base -->\nsolo base"}).json()
    assert r["ok"] and "Falta bloque" in r["aviso"]
    assert copia.read_text(encoding="utf-8").startswith("<!-- BLOQUE base -->")


def test_web_media_solo_del_catalogo(web_f7, monkeypatch, tmp_path):
    cliente, web, _ = web_f7
    monkeypatch.setenv("F7_MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(web, "_MEDIA_ENCONTRADA", {})

    assert cliente.get("/api/f7/media/NO-EXISTE").status_code == 404
    assert cliente.get("/api/f7/media/AL01").status_code == 404  # sin copia local

    pieza = web._piezas_catalogo_f7()["AL01"]
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / pieza["nombre_archivo"]).write_bytes(b"imagen")
    r = cliente.get("/api/f7/media/AL01")
    assert r.status_code == 200 and r.content == b"imagen"


def test_sin_agente_f7_la_web_sigue_siendo_la_del_kit(monkeypatch):
    from fastapi.testclient import TestClient

    from agente.web import app as web

    monkeypatch.delenv("AGENTE", raising=False)
    assert web.modo_f7() is False
    assert TestClient(web.app).get("/api/estado").json()["agente"] == "kit"


# -- Pedido de Mateo del 17/11: la presentación de fundas va con su video -------

from agente.f7.turno import PRESENTACION_FUNDAS  # noqa: E402

PREGUNTA_MODALIDAD = ("Hacemos envios a todo el pais y nuestro taller esta situado en CABA. "
                      "Quisieras la opción de envio o colocarlo en nuestro taller?")


def test_presentacion_va_con_el_video_y_despues_la_pregunta():
    a, _ = agente([AIMessage(PRESENTACION_FUNDAS + "\n\n" + PREGUNTA_MODALIDAD)])
    r = a.responder("hola, precio de fundas para clio")
    assert r.error is None, r.error
    assert tipos(r) == ["saludo", "texto", "texto", "multimedia", "texto", "texto"]
    assert r.globos[1].texto.startswith("Cada funda se realiza a medida")
    assert r.globos[3].datos["asset_id"] == "MP02"
    assert r.globos[-1].texto.startswith("Quisieras la opción de envio")
    assert r.detalle["video_presentacion_automatico"]["estado"] == "aceptado"


def test_presentacion_con_cotizacion_en_el_mismo_turno():
    pedido = {"consultas": [{"producto": "fundas", "modelo": "Clio"}], "tipo_solicitud": "consulta"}
    a, _ = agente([
        AIMessage("", tool_calls=[
            {"name": "enviar_multimedia", "id": "t1",
             "args": {"solicitudes": [{"producto": "fundas", "contenido": "presentacion", "formato": "video"}]}},
            {"name": "buscar_precio", "id": "t2", "args": {"pedido": pedido}},
        ]),
        AIMessage(PRESENTACION_FUNDAS),
    ])
    r = a.responder("hola, precio de fundas para clio\nen el taller")
    assert r.error is None, r.error
    # El control borra el texto libre cuando hay cotización: la presentación sale igual, primero.
    assert tipos(r) == ["saludo", "texto", "texto", "multimedia", "cotizacion"]
    assert "video_presentacion_automatico" not in r.detalle  # el video lo pidió el agente
    assert a.memoria[-1][1].startswith(PRESENTACION_FUNDAS)  # va una sola vez: queda en la memoria


def test_el_video_de_presentacion_no_se_repite():
    a, _ = agente([AIMessage(PRESENTACION_FUNDAS), AIMessage(PRESENTACION_FUNDAS)])
    a.responder("precio de fundas para clio")
    r = a.responder("y las fundas como son?")
    assert "multimedia" not in tipos(r)


def test_si_manda_el_video_sin_presentar_se_agrega_la_presentacion():
    a, _ = agente([
        llamada("enviar_multimedia", "solicitudes",
                [{"producto": "fundas", "contenido": "presentacion", "formato": "video"}]),
        AIMessage(PREGUNTA_MODALIDAD),
    ])
    r = a.responder("cuanto salen las fundas para un clio")
    assert r.error is None, r.error
    assert tipos(r) == ["saludo", "texto", "texto", "multimedia", "texto", "texto"]
    assert r.globos[1].texto.startswith("Cada funda se realiza a medida")


def test_si_pide_videos_no_se_agrega_la_presentacion():
    a, _ = agente([
        llamada("enviar_multimedia", "solicitudes",
                [{"producto": "fundas", "contenido": "presentacion", "formato": "video"}]),
        AIMessage(""),
    ])
    r = a.responder("tenes videos de las fundas?")
    assert tipos(r) == ["saludo", "multimedia"]


def test_la_presentacion_no_se_repite_aunque_el_agente_la_escriba():
    a, _ = agente([AIMessage(PRESENTACION_FUNDAS + "\n\n" + PREGUNTA_MODALIDAD),
                   AIMessage(PRESENTACION_FUNDAS + "\n\nDale")])
    a.responder("precio de fundas para clio")
    r = a.responder("ok")
    assert all(not g.texto.startswith("Cada funda") for g in r.globos)


def test_el_video_ya_mandado_no_se_reenvia_si_no_lo_pidio():
    video = [{"producto": "fundas", "contenido": "presentacion", "formato": "video"}]
    a, _ = agente([
        llamada("enviar_multimedia", "solicitudes", video), AIMessage("Listo"),
        llamada("enviar_multimedia", "solicitudes", video, ident="t2"), AIMessage("Dale"),
        llamada("enviar_multimedia", "solicitudes", video, ident="t3"), AIMessage(""),
    ])
    a.responder("precio de fundas para clio")
    r = a.responder("en el taller")  # no pidió videos: no se reenvía
    assert "multimedia" not in tipos(r)
    assert r.detalle["herramientas"][0]["resultado"]["omitidos"][0]["asset_id"] == "MP02"
    r = a.responder("me mandas el video de nuevo?")  # lo pidió: se reenvía
    assert "multimedia" in tipos(r)


# -- Corrección del 20/11 (campaña de pruebas): la pregunta de retapizar ----------
# Con «precio de fundas tipo tapizado para una Hilux 2020» el agente salteó el
# paso 1 bis. Ahora el código avisa en el prompt del turno que la pregunta está
# pendiente, para que no dependa de que el modelo se acuerde.

from agente.f7.prompt import AVISO_PASO_1BIS, frases_paso_1bis, leer_bloques  # noqa: E402


def _sistema(modelo, n=0) -> str:
    contenido = modelo.entradas[n][0].content
    return "".join(b["text"] for b in contenido) if isinstance(contenido, list) else contenido


def test_las_frases_del_paso_1bis_salen_del_prompt():
    frases = frases_paso_1bis(leer_bloques())
    assert len(frases) == 3
    assert frases[0] == "Quisieras cambiar tu tapizado o protegerlo con unas fundas que se colocan por encima?"
    assert frases[1].startswith("Pudieras acercarte a nuestro taller")
    assert frases[2].startswith("En ese caso podemos ofrecerte nuestras fundas a medida")


@pytest.mark.parametrize("texto", [
    "precio de fundas tipo tapizado para una Hilux 2020",
    "Hola quiero retapizar las butacas de mi auto",
    "buenas, hacen tapizados? soy de cordoba capital",
    "cuanto sale tapizar los asientos de un gol",
])
def test_si_nombra_tapizado_y_la_pregunta_no_se_hizo_el_turno_lo_avisa(texto):
    pregunta = frases_paso_1bis(leer_bloques())[0]
    a, modelo = agente([AIMessage(pregunta)])
    r = a.responder(texto)
    sistema = _sistema(modelo)
    assert AVISO_PASO_1BIS in sistema
    assert pregunta in sistema.split(AVISO_PASO_1BIS, 1)[1], "el aviso trae la pregunta literal"
    assert r.detalle["pregunta_tapizado_pendiente"] is True


def test_con_el_aviso_la_accion_final_no_empuja_a_cotizar():
    a, modelo = agente([AIMessage("ok")])
    a.responder("precio de fundas tipo tapizado para una Hilux 2020")  # fase cotizacion
    accion = _sistema(modelo).rsplit("ACCIÓN FINAL:", 1)[1]
    assert "buscar_precio AHORA" not in accion
    assert "1 bis" in accion


def test_si_la_pregunta_ya_se_hizo_no_avisa_de_nuevo():
    pregunta = frases_paso_1bis(leer_bloques())[0]
    a, modelo = agente([AIMessage(pregunta), AIMessage("Qué vehículo tenés?")])
    a.responder("quiero retapizar")
    r = a.responder("cambiar el tapizado, esta roto")
    assert AVISO_PASO_1BIS not in _sistema(modelo, 1)
    assert r.detalle["pregunta_tapizado_pendiente"] is False


def test_si_ya_se_pregunto_por_el_taller_tampoco_avisa():
    taller = frases_paso_1bis(leer_bloques())[1]
    a, modelo = agente([AIMessage(taller), AIMessage("Qué modelo de auto es?")])
    a.responder("quiero cambiar el tapizado completo, no fundas")
    a.responder("si puedo ir, es para tapizar un etios")
    assert AVISO_PASO_1BIS not in _sistema(modelo, 1)


def test_sin_nombrar_tapizado_no_hay_aviso():
    a, modelo = agente([AIMessage("Dale")])
    r = a.responder("quiero fundas para un clio")
    assert AVISO_PASO_1BIS not in _sistema(modelo)
    assert r.detalle["pregunta_tapizado_pendiente"] is False


# -- Corrección del 20/11 (campaña de pruebas): las frases fijas en el texto final ----
# El modelo a veces reformula la pregunta de modalidad («…o retirarlo en nuestro taller»:
# retirar no es colocar) o avisa «El video ya quedó enviado». Eso no le llega al cliente.


def test_la_pregunta_de_modalidad_reformulada_sale_con_la_frase_del_guion():
    from agente.f7.partir import partir_respuesta_f7
    from agente.f7.precios.herramienta import PREGUNTA_MODALIDAD

    reformulada = ("Para poder darte el precio necesito saber si preferís envío o retirarlo en nuestro taller en CABA. "
                   "¿Cuál de las dos opciones te queda mejor?")
    a, _ = agente([AIMessage("Dale"), AIMessage(reformulada)])
    a.responder("hola")

    r = a.responder("me decis el precio?")

    assert r.error is None
    assert [g.texto for g in r.globos if g.tipo == "texto"] == partir_respuesta_f7(PREGUNTA_MODALIDAD)
    assert r.detalle["salida_modelo"] == reformulada, "el detalle conserva lo que escribió el modelo"
    assert r.detalle["control"]["frases_corregidas"] is True
    # En la memoria queda lo que se mandó: el modelo no vuelve a leer «retirarlo» como algo dicho.
    assert a.memoria[-1] == ("ai", PREGUNTA_MODALIDAD)


def test_no_le_llega_al_cliente_el_aviso_de_que_el_video_ya_se_mando():
    a, _ = agente([AIMessage("Dale"), AIMessage("El video ya quedó enviado. Qué modelo de vehículo tenés?")])
    a.responder("hola")

    r = a.responder("fundas")

    assert [g.texto for g in r.globos if g.tipo == "texto"] == ["Qué modelo de vehículo tenés?"]
    assert a.memoria[-1] == ("ai", "Qué modelo de vehículo tenés?")


def test_un_texto_sin_nada_que_corregir_sale_igual():
    a, _ = agente([AIMessage("Dale"), AIMessage("Qué modelo de vehículo tenés?")])
    a.responder("hola")

    r = a.responder("fundas")

    assert [g.texto for g in r.globos if g.tipo == "texto"] == ["Qué modelo de vehículo tenés?"]
    assert r.detalle["control"]["frases_corregidas"] is False
    assert r.detalle["memoria"]["estado"] == "sin_cambio"


# -- Corrección del 20/11 (campaña de pruebas): la misma cotización en otro turno ------
# buscar_precio ya no manda dos veces el mismo texto. Pero si el cliente pide de nuevo el
# precio y el turno no tiene otra cosa para decirle, no puede quedar en silencio.


def _con_cotizacion_ya_enviada(respuesta_del_segundo_turno):
    pedido = {"consultas": [{"producto": "fundas", "modelo": "Clio"}], "tipo_solicitud": "consulta"}
    a, _ = agente([
        llamada("buscar_precio", "pedido", pedido), AIMessage(""),
        llamada("buscar_precio", "pedido", pedido, ident="t2"), AIMessage(respuesta_del_segundo_turno),
    ])
    primero = a.responder("hola, precio de fundas para clio\nen el taller")
    assert tipos(primero)[-1] == "cotizacion"
    return a, primero.globos[-1].texto


def test_si_el_cliente_pide_de_nuevo_el_precio_la_cotizacion_se_vuelve_a_mandar():
    a, cotizacion = _con_cotizacion_ya_enviada("")

    r = a.responder("me repetis el precio?")

    assert r.error is None, r.error
    assert [(g.tipo, g.texto) for g in r.globos] == [("cotizacion", cotizacion)]
    assert r.detalle["cotizacion_reenviada"] is True


def test_si_el_turno_tiene_otra_respuesta_la_cotizacion_no_se_repite():
    a, _ = _con_cotizacion_ya_enviada("El trabajo lo coordinás con Candela.")

    r = a.responder("y como coordino?")

    assert r.error is None, r.error
    assert tipos(r) == ["texto"]
    assert r.detalle.get("cotizacion_reenviada") is not True


# -- Re-prueba del 20/11: el aviso del paso 1 bis solo cuando piden un tapizado -------
# En la re-prueba el aviso saltó con «q no destruyan el tapizado»: el cliente nombraba el
# tapizado que ya tiene el auto y pedía fundas para cuidarlo. Eso no es pedir retapizar.

from agente.f7.prompt import nombra_tapizado  # noqa: E402


@pytest.mark.parametrize("texto", [
    "retapizar los asientos", "quiero retapizar", "cuanto sale tapizar los asientos de un gol",
    "buenas, hacen tapizados? soy de cordoba capital", "precio de fundas tipo tapizado para una Hilux 2020",
    "hacen tapiceria?", "precio de tapizado para un gol", "quiero un tapizado nuevo",
    "tapizado completo cuanto sale", "necesito cambiar el tapizado de las butacas",
    "quiero renovar mi tapizado", "Tapizan butacas?", "Hola quiero retapizar las butacas de mi auto",
])
def test_pedir_un_tapizado_dispara_el_aviso(texto):
    assert nombra_tapizado(texto) is True


@pytest.mark.parametrize("texto", [
    "negro algun diseño clasico, es para un uber no me interesa mucho el diseño sino q no destruyan el tapizado"
    " y q la funda dure, q salen y q demora tienen para enviarlas?",
    "fundas para proteger el tapizado original", "quiero cuidar mi tapizado",
    "tengo tapizado de cuero y quiero fundas", "las fundas arruinan el tapizado?",
    "busco fundas porque el tapizado esta sano y lo quiero mantener",
    "quiero fundas para un clio", "", None,
])
def test_nombrar_el_tapizado_que_ya_tiene_no_dispara_el_aviso(texto):
    assert nombra_tapizado(texto) is False


@pytest.mark.parametrize("texto", [
    # Re-prueba del 20/11 (C19): un techo, unos paneles o el volante no son tapicería de butacas.
    "y ya que estoy cuanto sale tapizar el techo?", "tapizan paneles de puerta?", "quiero tapizar el volante",
    "el tapizado del techo se esta cayendo, lo arreglan?",
])
def test_un_trabajo_que_no_es_de_butacas_no_dispara_el_aviso(texto):
    assert nombra_tapizado(texto) is False


@pytest.mark.parametrize("texto", ["quiero retapizar los asientos y el techo", "retapizar un gol 3 puertas"])
def test_con_butacas_en_el_pedido_el_aviso_sigue(texto):
    assert nombra_tapizado(texto) is True


def test_el_prompt_pide_contestar_la_otra_pregunta_junto_a_una_aclaracion():
    # Re-prueba del 20/11 (C04): con una aclaración de precios en el turno, el modelo copiaba la
    # continuación y dejaba sin contestar «la colocación con qué cargo cuenta?».
    from agente.f7.precios.descripcion import DESCRIPCION_PEDIDO_BUSCAR_PRECIO
    from agente.f7.precios.salida_agente import INSTRUCCIONES
    from agente.f7.prompt import RUTA_PROMPT

    lineas = Path(RUTA_PROMPT).read_text(encoding="utf-8").splitlines()
    regla5 = next(linea for linea in lineas if linea.startswith("5. Cotización enviada/omitida"))
    assert "otra pregunta concreta" in regla5 and "párrafo aparte" in regla5
    assert "párrafo aparte" in INSTRUCCIONES
    # Y el techo no se consulta como tapicería de butacas.
    assert "tapizado de techo" in DESCRIPCION_PEDIDO_BUSCAR_PRECIO


# -- Campaña de multimedia del 21/11: qué pidió el cliente, reenvío y retapizar ----------------
# Decisiones de Mateo: si piden fotos va el video, y si preguntan la diferencia entre las fundas
# va el video comparativo, sin la pregunta de retapizar.


@pytest.mark.parametrize("texto, esperado", [
    ("¿Tienen fotos de las alfombras?", dict(fotos=True, video=False, reenvio=False)),
    ("tenes algun video?", dict(fotos=False, video=True, reenvio=False)),
    ("mandame fotos y videos de todo", dict(fotos=True, video=True, reenvio=False)),
    ("no me cargó, me lo pasás de nuevo?", dict(fotos=False, video=False, reenvio=True)),
    ("me reenviás el de la colocación? no lo pude abrir", dict(fotos=False, video=False, reenvio=True)),
    ("se me borró, mandamelo otra vez", dict(reenvio=True)),
    # Pedir de nuevo el precio no es pedir de nuevo el material.
    ("me pasas de nuevo el precio? no lo encuentro", dict(reenvio=False)),
    ("con envio a cordoba", dict(fotos=False, video=False, reenvio=False)),
])
def test_que_material_pide_el_cliente(texto, esperado):
    from agente.f7.prompt import pedido_de_material

    pedido = pedido_de_material(texto)
    assert {k: pedido[k] for k in esperado} == esperado


@pytest.mark.parametrize("historial, texto, esperado", [
    ([], "fotos eh, videos no puedo ver con los datos", True),
    (["fotos eh, videos no puedo ver con los datos"], "dale mandame lo que tengas en foto", True),
    ([], "no pude abrir el video, me lo mandás de nuevo?", False),
    ([], "tenes fotos?", False),
])
def test_si_el_cliente_aviso_que_no_puede_ver_videos(historial, texto, esperado):
    from agente.f7.prompt import pedido_de_material

    assert pedido_de_material(texto, historial)["sin_video"] is esperado


@pytest.mark.parametrize("texto", [
    "Hola, qué diferencia hay entre las fundas a medida y las tipo tapizado?",
    "Hola, estoy entre las fundas comunes y las tipo tapizado para un 208, cuál es la diferencia?",
    "cual me conviene, la funda comun o la tipo tapizado?",
    "Hola, las fundas tipo tapizado que van por encima se notan que son fundas o quedan como de fábrica?",
    "quiero fundas tipo tapizado, las que se colocan por encima del original, para un Cronos",
    "de las fundas tipo tapizado (las que cubren el tapizado) tenés fotos de trabajos terminados?",
])
def test_la_pregunta_de_retapizar_no_va_si_pide_la_diferencia_o_ya_dijo_que_son_fundas(texto):
    assert nombra_tapizado(texto) is False


@pytest.mark.parametrize("texto", [
    "Hola, precio de fundas tipo tapizado para un Gol Trend",
    "Hola, tenés algún video de las fundas tipo tapizado?",
    "quiero retapizar, que diferencia hay con ponerle fundas?",
])
def test_la_pregunta_de_retapizar_sigue_en_los_demas_casos(texto):
    assert nombra_tapizado(texto) is True


def test_el_pedido_de_material_anterior_a_la_pregunta_de_retapizar_queda_avisado():
    pregunta = frases_paso_1bis(leer_bloques())[0]
    a, modelo = agente([AIMessage(pregunta), AIMessage("")])
    a.responder("Hola, tenés algún video de las fundas tipo tapizado?")
    a.responder("las fundas que van por encima")
    sistema = _sistema(modelo, 1)
    assert "PEDIDO DE MATERIAL PENDIENTE" in sistema
    assert "tenés algún video de las fundas tipo tapizado" in sistema


def test_sin_un_pedido_de_material_antes_no_hay_aviso_de_pendiente():
    pregunta = frases_paso_1bis(leer_bloques())[0]
    a, modelo = agente([AIMessage(pregunta), AIMessage("")])
    a.responder("Hola, precio de fundas tipo tapizado para un Gol Trend")
    a.responder("las fundas que van por encima")
    assert "PEDIDO DE MATERIAL PENDIENTE" not in _sistema(modelo, 1)


# -- Campaña de multimedia del 21/11: el material antes de la primera cotización ----------------
# Paso 4 del guion: con el producto y la modalidad claros y sin material previo, primero se
# muestra el producto y después se cotiza. Se cumplía con fundas a medida y nunca con tipo
# tapizado, alfombras y cubrevolante.

PLANILLA.append({"title": "Otros", "sheetId": 59879218, "values": [
    ["OTROS ACCESORIOS"],
    ["Producto/servicio", "Valor EFECTIVO", "TRANSFERENCIA + 21%", "POSNET o CUOTAS 21% + 9%"],
    [],
    ["CUBRE VOLANTE", 20000, 22000, 25000]]})
CUBREVOLANTE = {"consultas": [{"producto": "cubrevolante"}], "tipo_solicitud": "consulta"}
VIDEO_CUBREVOLANTE = [{"producto": "cubrevolante", "contenido": "presentacion"}]
ALFOMBRA = [{"producto": "alfombra", "contenido": "presentacion"}]


def piezas(r):
    return [g.datos["asset_id"] for g in r.globos if g.tipo == "multimedia"]


def test_antes_de_la_primera_cotizacion_sale_el_material_del_producto():
    a, _ = agente([llamada("buscar_precio", "pedido", CUBREVOLANTE), AIMessage("")])
    r = a.responder("hola, cuanto sale el cubrevolante? con envio")
    assert r.error is None, r.error
    assert tipos(r) == ["saludo", "multimedia", "cotizacion"]
    assert piezas(r) == ["CV01"]
    assert r.detalle["material_automatico"]["productos"] == ["cubrevolante"]


def test_si_ya_vio_el_material_no_se_manda_de_nuevo_al_cotizar():
    a, _ = agente([
        llamada("enviar_multimedia", "solicitudes", VIDEO_CUBREVOLANTE), AIMessage(""),
        llamada("buscar_precio", "pedido", CUBREVOLANTE, ident="t2"), AIMessage(""),
    ])
    assert piezas(a.responder("me mostras un video del cubrevolante?")) == ["CV01"]
    r = a.responder("cuanto sale? con envio")
    assert tipos(r) == ["cotizacion"] and "material_automatico" not in r.detalle


def test_si_el_cliente_no_quiere_el_video_no_se_manda_al_cotizar():
    a, _ = agente([llamada("buscar_precio", "pedido", CUBREVOLANTE), AIMessage("")])
    r = a.responder("hola, el video del cubrevolante ya lo vi, no me lo mandes. pasame el precio con envio")
    assert tipos(r) == ["saludo", "cotizacion"]


def test_si_el_modelo_ya_mando_material_en_el_turno_el_codigo_no_agrega_otro():
    a, _ = agente([
        AIMessage("", tool_calls=[
            {"name": "enviar_multimedia", "id": "t1", "args": {"solicitudes": VIDEO_CUBREVOLANTE}},
            {"name": "buscar_precio", "id": "t2", "args": {"pedido": CUBREVOLANTE}}]),
        AIMessage(""),
    ])
    r = a.responder("hola, cuanto sale el cubrevolante? con envio")
    assert tipos(r) == ["saludo", "multimedia", "cotizacion"] and "material_automatico" not in r.detalle


def test_las_fundas_a_medida_siguen_con_su_presentacion_y_no_con_este_camino():
    pedido = {"consultas": [{"producto": "fundas", "modelo": "Clio"}], "tipo_solicitud": "consulta"}
    a, _ = agente([llamada("buscar_precio", "pedido", pedido), AIMessage("")])
    r = a.responder("hola, precio de fundas para clio\nen el taller")
    assert "material_automatico" not in r.detalle and r.detalle["presentacion_automatica"] is True


def test_si_pide_que_le_reenvien_el_material_sin_decir_video_se_reenvia():
    a, _ = agente([
        llamada("enviar_multimedia", "solicitudes", ALFOMBRA), AIMessage(""),
        llamada("enviar_multimedia", "solicitudes", [{**ALFOMBRA[0], "reenvio_solicitado": True}], ident="t2"),
        AIMessage(""),
    ])
    assert piezas(a.responder("tenes algun video de las alfombras?")) == ["AL01", "N8N01"]
    assert piezas(a.responder("no me cargó, me lo pasás de nuevo?")) == ["AL01", "N8N01"]


def test_si_piden_fotos_sale_el_video_y_si_ya_lo_tiene_no_se_repite():
    a, _ = agente([
        llamada("enviar_multimedia", "solicitudes", [{**ALFOMBRA[0], "formato": "foto"}]), AIMessage(""),
        llamada("enviar_multimedia", "solicitudes", ALFOMBRA, ident="t2"), AIMessage(""),
    ])
    assert piezas(a.responder("¿Tienen fotos de las alfombras?")) == ["AL01", "N8N01"]
    r = a.responder("y fotos no tenes?")
    assert piezas(r) == []
    assert "catálogo" in r.detalle["herramientas"][0]["resultado"]["indicacion"]


def test_el_guion_tiene_las_decisiones_de_mateo_del_21_11():
    from agente.f7.prompt import RUTA_PROMPT

    guion = Path(RUTA_PROMPT).read_text(encoding="utf-8")
    # 2. Diferencia entre las fundas: video comparativo y esta pregunta, tal cual la dictó.
    assert "«Cual de las dos opciones se adapta mas a lo que estas buscando?»" in guion
    assert "se adapta a lo que estabas buscando" not in guion
    assert "ni hagas la pregunta del paso 1 bis" in guion
    # 1. Si piden fotos va el video y no se dice que no hay fotos.
    assert "Nunca digas que no hay o que no tenés fotos" in guion
    assert "No sustituyas formato" not in guion


# -- Re-prueba de multimedia del 21/11: las frases del guion salen tal cual ----------------------
# El modelo copió la frase nueva con tildes y signo de apertura. El guion pide las frases citadas
# sin reformular: si solo cambian tildes o signos, sale la del guion.


def test_la_frase_del_guion_con_tildes_agregadas_sale_tal_cual():
    a, _ = agente([AIMessage("Dale"), AIMessage("¿Cuál de las dos opciones se adapta más a lo que estás buscando?")])
    a.responder("hola")
    r = a.responder("no se cual elegir")
    assert [g.texto for g in r.globos if g.tipo == "texto"] == [
        "Cual de las dos opciones se adapta mas a lo que estas buscando?"]
    assert r.detalle["control"]["frases_corregidas"] is True


def test_un_texto_que_solo_se_parece_a_una_frase_del_guion_no_se_toca():
    texto = "Cuál de las dos te gusta más?"
    a, _ = agente([AIMessage("Dale"), AIMessage(texto)])
    a.responder("hola")
    r = a.responder("no se cual elegir")
    assert [g.texto for g in r.globos if g.tipo == "texto"] == [texto]


def test_el_guion_dice_cuando_pasar_el_catalogo():
    from agente.f7.prompt import RUTA_PROMPT

    guion = Path(RUTA_PROMPT).read_text(encoding="utf-8")
    assert "pasalo cuando lo pidan" in guion
    assert "o duda entre las dos" not in guion


# -- Re-prueba de multimedia del 21/11, segunda vuelta --------------------------------------------

COMPARATIVO = [{"producto": "fundas", "contenido": "comparacion", "formato": "video"},
               {"producto": "tipo tapizado", "contenido": "comparacion", "formato": "video"}]


@pytest.mark.parametrize("texto, esperado", [
    ("mandame el video", True), ("me mostrás un video de las alfombras?", True), ("pasame fotos de los diseños", True),
    ("se ve en algún video?", False), ("y fotos no tenés entonces? solo video?", False), ("con envio", False),
])
def test_pedir_que_le_manden_material_no_es_lo_mismo_que_nombrarlo(texto, esperado):
    from agente.f7.prompt import pedido_de_material

    assert pedido_de_material(texto)["pide_envio"] is esperado


def test_nombrar_un_video_no_hace_reenviar_lo_que_ya_tiene():
    detalle = [{"producto": "fundas", "contenido": "calidad"}]
    a, _ = agente([
        llamada("enviar_multimedia", "solicitudes", detalle), AIMessage(""),
        llamada("enviar_multimedia", "solicitudes", detalle, ident="t2"), AIMessage("Sí, se ve en el video que te mandé"),
    ])
    assert piezas(a.responder("tenes algun video del detalle de las fundas?")) == ["N8N05", "N8N06"]
    r = a.responder("y el respaldo se puede rebatir? se ve en algún video?")
    assert piezas(r) == []
    assert [g.texto for g in r.globos if g.tipo == "texto"] == ["Sí, se ve en el video que te mandé"]


def test_el_pedido_de_reenvio_queda_avisado_al_modelo():
    a, modelo = agente([llamada("enviar_multimedia", "solicitudes", ALFOMBRA), AIMessage(""), AIMessage("")])
    a.responder("tenes algun video de las alfombras?")
    a.responder("no me cargó, me lo pasás de nuevo?")
    assert "PEDIDO DE REENVÍO" in _sistema(modelo, 2)
    assert "PEDIDO DE REENVÍO" not in _sistema(modelo, 0)


def test_el_video_pendiente_de_tipo_tapizado_sale_aunque_el_modelo_pida_el_de_fundas():
    pregunta = frases_paso_1bis(leer_bloques())[0]
    a, _ = agente([
        AIMessage(pregunta),
        llamada("enviar_multimedia", "solicitudes", [{"producto": "fundas", "contenido": "presentacion", "formato": "video"}]),
        AIMessage(""),
    ])
    a.responder("Hola, tenés algún video de las fundas tipo tapizado?")
    r = a.responder("las fundas que van por encima")
    assert piezas(r) == ["TT01"]


def test_despues_del_comparativo_no_se_avisa_la_pregunta_de_retapizar():
    a, _ = agente([llamada("enviar_multimedia", "solicitudes", COMPARATIVO), AIMessage(""), AIMessage("")])
    a.responder("que diferencia hay entre las fundas a medida y las tipo tapizado?")
    r = a.responder("me quedo con la tipo tapizado")
    assert r.detalle["pregunta_tapizado_pendiente"] is False


def test_al_cliente_no_se_le_dice_que_no_hay_fotos():
    a, _ = agente([AIMessage("Dale"), AIMessage(
        "Fotos como tal no tenemos, pero podés ver más opciones en nuestro catálogo: https://wa.me/c/5491156013327")])
    a.responder("hola")
    r = a.responder("y fotos no tenes?")
    assert [g.texto for g in r.globos if g.tipo == "texto"] == [
        "Podés ver más opciones en nuestro catálogo: https://wa.me/c/5491156013327"]


def test_si_salio_el_video_no_se_dice_que_no_hay_fotos_ni_se_agrega_el_catalogo():
    # Decisión de Mateo del 21/11: «simplemente se envía el video y ya».
    a, _ = agente([llamada("enviar_multimedia", "solicitudes", ALFOMBRA),
                   AIMessage("Por el momento no tengo fotos de las alfombras para enviarte")])
    r = a.responder("tenés fotos de las alfombras?")
    assert piezas(r) == ["AL01", "N8N01"]
    assert [g.texto for g in r.globos if g.tipo == "texto"] == []


def _aviso_de_reenvio(modelo, n) -> str:
    return next((l for l in _sistema(modelo, n).splitlines() if "PEDIDO DE REENVÍO" in l), "")


def test_el_aviso_de_reenvio_nombra_el_ultimo_material_que_salio():
    a, modelo = agente([llamada("enviar_multimedia", "solicitudes", VIDEO_CUBREVOLANTE), AIMessage(""),
                        llamada("enviar_multimedia", "solicitudes", ALFOMBRA, ident="t2"), AIMessage(""),
                        AIMessage("")])
    a.responder("tenes algun video del cubrevolante?")
    a.responder("y de las alfombras?")
    a.responder("no me cargó, me lo pasás de nuevo?")
    aviso = _aviso_de_reenvio(modelo, 4)
    assert "«Presentación de alfombra», «Colocación de alfombra»" in aviso
    assert "cubrevolante" not in aviso.lower()


def test_el_aviso_de_reenvio_cuenta_el_material_que_salio_solo_antes_de_cotizar():
    # Re-prueba del 21/11: el video había salido solo antes de la cotización y, ante «no me cargó,
    # me lo pasás de nuevo?», el modelo creyó que le pedían la cotización y mandó a buscar más arriba.
    a, modelo = agente([llamada("buscar_precio", "pedido", CUBREVOLANTE), AIMessage(""), AIMessage("")])
    a.responder("hola, cuanto sale el cubrevolante? con envio")
    a.responder("no me cargó, me lo pasás de nuevo?")
    aviso = _aviso_de_reenvio(modelo, 2)
    assert "«Presentación de cubrevolante»" in aviso and "no un mensaje de texto" in aviso


def test_sin_material_mandado_el_aviso_de_reenvio_no_nombra_ninguno():
    a, modelo = agente([AIMessage("Dale"), AIMessage("")])
    a.responder("hola")
    a.responder("no me cargó, me lo pasás de nuevo?")
    assert "«" not in _aviso_de_reenvio(modelo, 1)


# ---------- Re-prueba del 21/11: la presentación de las fundas a medida no se saltea ----------
# Paso 2 del guion: con el modelo conocido va la presentación, una vez, con su video. Después de
# ver colores y diseños (o el comparativo) el cliente pidió el precio y salió la cotización sola.

FUNDAS_CLIO = {"consultas": [{"producto": "fundas", "modelo": "Clio"}], "tipo_solicitud": "consulta"}


def _textos(r):
    return [g.texto for g in r.globos if g.tipo == "texto"]


def test_la_primera_cotizacion_de_fundas_a_medida_lleva_la_presentacion_con_su_video():
    from agente.f7.partir import partir_respuesta_f7
    from agente.f7.turno import PRESENTACION_FUNDAS

    a, _ = agente([llamada("buscar_precio", "pedido", FUNDAS_CLIO), AIMessage("")])
    r = a.responder("hola, precio de fundas para clio\nen el taller")
    assert r.error is None, r.error
    assert tipos(r) == ["saludo", "texto", "texto", "multimedia", "cotizacion"]
    assert piezas(r) == ["MP02"] and _textos(r) == partir_respuesta_f7(PRESENTACION_FUNDAS)


def test_si_ya_vio_fotos_de_fundas_la_presentacion_igual_va_antes_de_cotizar():
    a, _ = agente([
        llamada("enviar_multimedia", "solicitudes", [{"producto": "fundas", "contenido": "colores"}]), AIMessage(""),
        llamada("buscar_precio", "pedido", FUNDAS_CLIO, ident="t2"), AIMessage(""),
    ])
    assert piezas(a.responder("en que colores vienen las fundas a medida?")) == ["MP04"]
    r = a.responder("tengo un clio, lo coloco en el taller. cuanto sale?")
    assert tipos(r) == ["texto", "texto", "multimedia", "cotizacion"] and piezas(r) == ["MP02"]


def test_si_ya_se_presento_la_cotizacion_de_fundas_sale_sola():
    a, _ = agente([AIMessage(PRESENTACION_FUNDAS + "\n\n" + PREGUNTA_MODALIDAD),
                   llamada("buscar_precio", "pedido", FUNDAS_CLIO), AIMessage("")])
    assert piezas(a.responder("hola, fundas para un clio")) == ["MP02"]
    r = a.responder("lo coloco en el taller")
    assert tipos(r) == ["cotizacion"]


def test_si_no_quiere_que_le_manden_material_la_cotizacion_de_fundas_sale_sola():
    a, _ = agente([llamada("buscar_precio", "pedido", FUNDAS_CLIO), AIMessage("")])
    r = a.responder("hola, el video de las fundas ya lo vi, no me lo mandes. precio para un clio, en el taller")
    assert tipos(r) == ["saludo", "cotizacion"]


# ---------- Prueba de «romper el flujo» del 21/11 ----------

@pytest.mark.parametrize("texto", [
    "tengo un Clio 2, quiero cambiarle el tapizado porque está todo roto",                       # R13
    "quiero tapizar los asientos de mi Amarok pero no quiero fundas, quiero algo que quede original",  # R28
    "necesito un tapizado nuevo para un Gol",
])
def test_si_ya_dijo_que_quiere_cambiar_el_tapizado_no_se_le_pregunta_de_nuevo(texto):
    a, modelo = agente([AIMessage("")])
    a.responder(texto)
    aviso = _sistema(modelo, 0)
    assert "ya dijo que quiere cambiar el tapizado" in aviso
    assert "Hacela ahora, sola y tal cual" not in aviso


@pytest.mark.parametrize("texto", [
    "quiero retapizar un Falcon 80, todo original",                                              # R11
    "quiero retapizar los asientos de una Hilux y además fundas para un Gol",                    # R55
    "quiero cambiar el tapizado o ponerle fundas, no sé",
    "precio de fundas tipo tapizado para una Hilux",
])
def test_si_no_lo_dijo_la_pregunta_de_retapizar_sigue_pendiente(texto):
    a, modelo = agente([AIMessage("")])
    a.responder(texto)
    assert "Hacela ahora, sola y tal cual" in _sistema(modelo, 0)


HORARIO = "Te esperamos de lunes a viernes de 9 a 18 hs y sábado de 9 a 14 hs"


def test_una_pregunta_del_cliente_no_queda_sin_ninguna_respuesta():
    # R16: «y con el 10% de descuento cuánto me queda?» y el agente no mandó nada.
    a, _ = agente([AIMessage("Dale"), AIMessage("")])
    a.responder("hola")
    r = a.responder("y con el 10% de descuento cuánto me queda entonces?")
    assert tipos(r) == ["derivacion"] and "humano" in a.sesion.etiquetas
    assert r.detalle["derivacion_por_silencio"]["motivo"] == "revision_especial"


@pytest.mark.parametrize("texto", ["👍", "gracias", "ok dale", "qué bueno, gracias"])
def test_si_no_pregunto_nada_el_silencio_no_pasa_la_conversacion(texto):
    a, _ = agente([AIMessage("Dale"), AIMessage("")])
    a.responder("hola")
    r = a.responder(texto)
    assert tipos(r) == [] and "humano" not in a.sesion.etiquetas


def test_si_pregunta_los_horarios_y_el_modelo_no_los_dice_salen_igual():
    # R20: «qué horarios tienen? atienden sábados a la tarde?» y recibió solo la cotización.
    a, _ = agente([llamada("buscar_precio", "pedido", FUNDAS_CLIO), AIMessage("")])
    r = a.responder("hola, fundas para un clio, lo coloco en el taller. qué horarios tienen? atienden sábados a la tarde?")
    assert tipos(r)[-2:] == ["cotizacion", "texto"] and r.globos[-1].texto == HORARIO


def test_si_el_modelo_ya_dijo_el_horario_no_se_agrega_otra_vez():
    a, _ = agente([AIMessage(HORARIO + ", así que los sábados no atendemos por la tarde")])
    r = a.responder("atienden los sábados a la tarde?")
    assert _textos(r) == [HORARIO + ", así que los sábados no atendemos por la tarde"]


def test_si_pregunta_donde_estan_sale_la_direccion_del_guion():
    a, _ = agente([AIMessage("")])
    r = a.responder("dónde quedan?")
    assert _textos(r) == ["📍La dirección es Av. Olivera 1265 , CABA",
                          "Nuestra ubicación exacta la podes ver ingresando a este link "
                          "https://maps.app.goo.gl/Nsyib1THu4WCN2L8A?g_st=ipc"]


def test_no_sale_que_hay_fundas_para_un_auto_si_no_se_consulto_la_planilla():
    # R08: «Sí, tenemos fundas para el BYD Dolphin», y no figura.
    a, _ = agente([AIMessage("Sí, tenemos fundas para el BYD Dolphin.\n\n" + PREGUNTA_MODALIDAD)])
    r = a.responder("tienen fundas para un BYD Dolphin?")
    assert not any("BYD" in t for t in _textos(r)) and _textos(r)[-1].startswith("Quisieras la opción")


def test_despues_de_la_pregunta_de_modalidad_no_sale_otra_pregunta():
    # R27: «envío o taller?» y «crédito o débito?» en el mismo mensaje.
    a, _ = agente([AIMessage(PREGUNTA_MODALIDAD + "\n\nPara pagar con tarjeta, es crédito o débito?")])
    r = a.responder("cuánto salen las fundas para un 208 pagando con tarjeta?")
    assert _textos(r)[-1].startswith("Quisieras la opción") and not any("débito" in t for t in _textos(r))


def test_una_pregunta_con_signo_tampoco_queda_sin_respuesta():
    a, _ = agente([AIMessage("Dale"), AIMessage("")])
    a.responder("hola")
    r = a.responder("y tienen stock?")
    assert tipos(r) == ["derivacion"]
