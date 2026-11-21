"""Pruebas del agente de F7 en el servidor: memoria en la base, Chatwoot y el webhook.

Sin red y sin gastar tokens: el modelo y Chatwoot son de mentira.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from test_f7_turno import ModeloFalso, leer_hojas_falso, llamada  # noqa: E402

from test_chatwoot import evento  # noqa: E402

from agente.canales.chatwoot import ErrorDeChatwoot  # noqa: E402
from agente.f7.canal import ChatwootF7  # noqa: E402
from agente.f7.estado import (  # noqa: E402
    AlmacenEnMemoria,
    AlmacenSQL,
    desempaquetar,
    empaquetar,
)
from agente.f7.derivacion import motor as motor_derivacion  # noqa: E402
from agente.f7.local import SesionLocal  # noqa: E402
from agente.f7.multimedia.seleccion import cargar_catalogo  # noqa: E402
from agente.f7.produccion import AtencionF7, ErrorDeEntrega, ErrorDeTurnoF7  # noqa: E402
from agente.f7.textos import ACK_BORRAR, SALUDO_INICIAL  # noqa: E402
from agente.f7.turno import AgenteF7  # noqa: E402

PEDIDO_CLIO = {"consultas": [{"producto": "fundas", "modelo": "Clio"}], "tipo_solicitud": "consulta"}
VIDEO_FUNDAS = [{"producto": "fundas", "contenido": "presentacion", "formato": "video"}]


# -- El estado de una conversación: va a la base y vuelve igual --------------------


def test_el_estado_va_y_vuelve_igual():
    sesion = SesionLocal(conversation_id=27, epoca=5)
    sesion.multimedia_registrada.append(
        {"asset_id": "MP02", "version": "v1", "aceptado": True, "hay_envio_incierto": False}
    )
    sesion.registro("precios")["cw:1:27:9:precios-v1"] = {"estado": "aceptado", "pedido": {"a": 1}}
    sesion.nuevo_message_id()
    sesion.nuevo_message_id()
    memoria = [("human", "hola"), ("ai", "Buenas")]

    vuelta, memoria_vuelta = desempaquetar(empaquetar(sesion, memoria), 27)

    assert vuelta.conversation_id == 27
    assert vuelta.epoca == 5
    assert vuelta.multimedia_registrada == sesion.multimedia_registrada
    assert vuelta.registros == sesion.registros
    assert memoria_vuelta == memoria
    assert vuelta.nuevo_message_id() == 3, "los ids siguen desde donde quedaron"


def test_las_etiquetas_y_lo_mandado_no_se_guardan():
    # Las etiquetas viven en Chatwoot (se leen en cada turno) y lo mandado es del turno.
    sesion = SesionLocal(conversation_id=27)
    sesion.etiquetas.append("humano")
    sesion.mandar("texto", "hola")

    vuelta, _ = desempaquetar(empaquetar(sesion, []), 27)

    assert vuelta.etiquetas == [] and vuelta.salientes == []


def test_una_conversacion_de_verdad_se_guarda_y_sigue_donde_quedo():
    modelo = ModeloFalso([
        llamada("buscar_precio", "pedido", PEDIDO_CLIO), AIMessage(""),
        llamada("enviar_multimedia", "solicitudes", VIDEO_FUNDAS, ident="t2"), AIMessage("Dale"),
    ])
    a = AgenteF7(modelo, leer_hojas=leer_hojas_falso)
    primero = a.responder("hola, precio de fundas para clio\nen el taller")
    assert primero.error is None, primero.error

    # Se guarda y se levanta en otro agente, como después de reiniciar el servidor.
    guardado = empaquetar(a.sesion, a.memoria)
    b = AgenteF7(modelo, leer_hojas=leer_hojas_falso)
    b.sesion, b.memoria = desempaquetar(guardado, a.sesion.conversation_id)
    segundo = b.responder("dale")

    assert segundo.error is None, segundo.error
    tipos = [g.tipo for g in segundo.globos]
    assert "saludo" not in tipos, "ya había saludado: no saluda de nuevo"
    assert "multimedia" not in tipos, "el video de presentación ya se mandó: no se repite"
    assert b.memoria[0] == ("human", "hola, precio de fundas para clio\nen el taller")


def test_los_registros_de_las_tres_herramientas_vuelven_iguales():
    # Si una herramienta empieza a guardar algo que no es JSON, esto lo avisa.
    modelo = ModeloFalso([
        llamada("buscar_precio", "pedido", PEDIDO_CLIO), AIMessage(""),
        llamada("enviar_multimedia", "solicitudes", [{"producto": "fundas", "contenido": "disenos"}], ident="t2"),
        AIMessage("Dale"),
        llamada("derivar_humano", "motivo", "pago", ident="t3"), AIMessage("Listo"),
    ])
    a = AgenteF7(modelo, leer_hojas=leer_hojas_falso)
    for lote in ("hola, precio de fundas para clio\nen el taller", "me mandas fotos de los diseños?",
                 "quiero pagar la seña"):
        assert a.responder(lote).error is None

    vuelta, memoria = desempaquetar(empaquetar(a.sesion, a.memoria), a.sesion.conversation_id)

    assert set(a.sesion.registros) >= {"precios", "multimedia", "derivacion"}
    assert vuelta.registros == a.sesion.registros
    assert vuelta.multimedia_registrada == a.sesion.multimedia_registrada
    assert memoria == a.memoria


# -- Dónde se guarda: en memoria (pruebas) o en una base (SQLite o Postgres) --------


@pytest.fixture(params=["memoria", "sqlite"])
def almacen(request, tmp_path):
    guardado = AlmacenEnMemoria() if request.param == "memoria" else AlmacenSQL.sqlite(tmp_path / "f7.db")
    guardado.preparar()
    return guardado


def test_una_conversacion_nueva_no_tiene_nada_guardado(almacen):
    assert almacen.cargar("27") is None


def test_guarda_y_trae_por_conversacion(almacen):
    almacen.guardar("27", "uno")
    almacen.guardar("28", "dos")
    almacen.guardar("27", "tres")  # pisa lo anterior de esa conversación
    assert almacen.cargar("27") == "tres"
    assert almacen.cargar("28") == "dos"


def test_olvidar_borra_solo_esa_conversacion(almacen):
    almacen.guardar("27", "uno")
    almacen.guardar("28", "dos")
    almacen.olvidar("27")
    assert almacen.cargar("27") is None
    assert almacen.cargar("28") == "dos"


def test_cada_turno_queda_anotado(almacen):
    almacen.anotar_turno("27", {"lote": "hola", "fase": "inicio"})
    almacen.anotar_turno("27", {"lote": "precio"})
    almacen.anotar_turno("28", {"lote": "otra"})
    assert [t["lote"] for t in almacen.turnos("27")] == ["hola", "precio"]


def test_un_detalle_con_algo_raro_igual_se_anota(almacen):
    # El detalle del turno trae de todo: lo que no es JSON se guarda como texto en vez de romper.
    almacen.anotar_turno("27", {"ruta": Path("x"), "conjunto": {1}})
    assert almacen.turnos("27")[0]["ruta"] == "x"


def test_lo_guardado_sobrevive_a_un_reinicio(tmp_path):
    ruta = tmp_path / "f7.db"
    uno = AlmacenSQL.sqlite(ruta)
    uno.preparar()
    uno.guardar("27", "estado")

    otro = AlmacenSQL.sqlite(ruta)
    otro.preparar()

    assert otro.cargar("27") == "estado"


class _ConexionEspia:
    """Una conexión que no llega a ninguna base: anota lo que se le pide."""

    def __init__(self, pedidos):
        self.pedidos = pedidos

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, valores=()):
        self.pedidos.append(sql)
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def commit(self):
        pass

    def close(self):
        pass


def test_con_postgres_las_consultas_usan_sus_marcadores():
    pedidos: list[str] = []
    guardado = AlmacenSQL(lambda: _ConexionEspia(pedidos), marcador="%s")
    guardado.preparar()
    guardado.guardar("27", "estado")
    guardado.cargar("27")
    guardado.anotar_turno("27", {"lote": "hola"})
    guardado.olvidar("27")

    con_valores = [p for p in pedidos if "%s" in p]
    assert len(con_valores) == 4, "guardar, cargar, anotar y olvidar llevan valores"
    assert not any("?" in p for p in pedidos), "el «?» es de SQLite: Postgres no lo entiende"


# -- El canal de F7: Chatwoot, pero con lo que F7 necesita -------------------------


class CanalDeMentira(ChatwootF7):
    """El canal de F7 con una API de mentira: anota lo que se le pide y lo recuerda."""

    def __init__(self, etiquetas=None, bandeja_id="1", falla=None):
        super().__init__(
            url="https://chatwoot.ejemplo.com",
            token="token-falso",
            cuenta_id=1,
            etiqueta_humano="humano",
            bandeja_id=bandeja_id,
        )
        self.llamadas: list[tuple] = []
        self._iniciales = list(etiquetas or [])
        self.etiquetas_de: dict[str, list[str]] = {}
        self.estado: dict[str, str] = {}
        self.asignado: dict[str, int] = {}
        self.falla = falla or (lambda metodo, camino: None)
        # Si la bandeja tiene autoasignación, Chatwoot puede dejar la charla con otra persona.
        self.reasignado_a: int | None = None
        # Lo que contesta Chatwoot cada vez que se le pregunta si un mensaje ya se entregó.
        self.estados_de_entrega: list = []
        self._id = 9000

    def _etiquetas_actuales(self, conversacion) -> list[str]:
        return self.etiquetas_de.setdefault(str(conversacion), list(self._iniciales))

    def _revisar(self, metodo, camino):
        error = self.falla(metodo, camino)
        if error is not None:
            raise error

    def _api(self, metodo, camino, datos=None):
        self.llamadas.append((metodo, camino, datos))
        self._revisar(metodo, camino)
        partes = camino.split("/")
        conversacion = partes[1] if len(partes) > 1 else ""
        if camino.endswith("/labels"):
            if metodo == "POST":
                self.etiquetas_de[conversacion] = list(datos["labels"])
            return {"payload": list(self._etiquetas_actuales(conversacion))}
        if camino.endswith("/toggle_status"):
            self.estado[conversacion] = datos["status"]
            return {"payload": {"success": True, "current_status": datos["status"]}}
        if camino.endswith("/assignments"):
            self.asignado[conversacion] = datos["assignee_id"]
            return {"id": datos["assignee_id"]}
        if camino.endswith("/messages") and metodo == "POST":
            self._id += 1
            return {"id": self._id, "content": datos.get("content")}
        if metodo == "GET" and partes[-1].split("?")[0] == "messages":
            # Cada consulta devuelve el estado siguiente de la lista; sin lista, ya está entregado.
            estado = self.estados_de_entrega.pop(0) if self.estados_de_entrega else "delivered"
            return {"payload": [{"id": i, "status": estado} for i in range(9001, self._id + 1)]}
        if metodo == "GET" and len(partes) == 2 and partes[0] == "conversations":
            quien = self.reasignado_a or self.asignado.get(conversacion)
            return {
                "id": int(conversacion),
                "status": self.estado.get(conversacion, "open"),
                "labels": list(self._etiquetas_actuales(conversacion)),
                "meta": {"assignee": {"id": quien} if quien else None},
            }
        return {}

    def _subir(self, camino, campos, archivo):
        campo, nombre, mime, datos = archivo
        self.llamadas.append(("SUBIR", camino, {"campos": dict(campos), "archivo": (campo, nombre, mime),
                                                "bytes": len(datos)}))
        self._revisar("SUBIR", camino)
        self._id += 1
        return {"id": self._id}

    def consultas_de_entrega(self) -> list[int]:
        """En qué lugar de la lista de llamadas se preguntó por la entrega de un mensaje."""
        return [i for i, (metodo, camino, _) in enumerate(self.llamadas)
                if metodo == "GET" and camino.split("?")[0].endswith("/messages")]

    def mandado(self, conversacion="27") -> list[tuple[str, str]]:
        """Lo que le llegó al cliente, en orden: ("texto", contenido) o ("archivo", nombre)."""
        salida = []
        for metodo, camino, datos in self.llamadas:
            if camino != f"conversations/{conversacion}/messages":
                continue
            if metodo == "POST":
                salida.append(("texto", datos["content"]))
            elif metodo == "SUBIR":
                salida.append(("archivo", datos["archivo"][1]))
        return salida

    def escrituras(self) -> list[str]:
        """Los cambios hechos a la conversación (no los mensajes), en orden."""
        return [camino.split("/")[-1] for metodo, camino, _ in self.llamadas
                if metodo == "POST" and not camino.endswith("/messages")]


def test_solo_se_atiende_la_bandeja_de_f7():
    canal = CanalDeMentira(bandeja_id="1")
    de_f7 = canal.traducir(evento("hola", id_mensaje=1, inbox={"id": 1, "name": "F7 inbox"}))
    de_otra = canal.traducir(evento("hola", id_mensaje=2, inbox={"id": 3, "name": "Test Bot API"}))

    assert canal.deberia_responder(de_f7) is True
    assert canal.deberia_responder(de_otra) is False


def test_la_bandeja_tambien_se_lee_de_la_conversacion():
    canal = CanalDeMentira(bandeja_id="1")
    otra = evento("hola", id_mensaje=1, inbox=None)
    otra["conversation"]["inbox_id"] = 3

    assert canal.deberia_responder(canal.traducir(otra)) is False


def test_si_el_evento_no_dice_la_bandeja_se_atiende():
    # Igual que hoy: (inbox == null || inbox === 1).
    canal = CanalDeMentira(bandeja_id="1")
    assert canal.deberia_responder(canal.traducir(evento("hola", inbox=None))) is True


def test_sin_bandeja_configurada_se_atienden_todas():
    canal = CanalDeMentira(bandeja_id="")
    assert canal.deberia_responder(canal.traducir(evento("hola", inbox={"id": 3}))) is True


def test_un_evento_de_otra_cuenta_no_se_atiende():
    canal = CanalDeMentira()
    assert canal.deberia_responder(canal.traducir(evento("hola", account={"id": 2}))) is False


def test_con_humano_no_se_contesta_pero_borrar_si():
    canal = CanalDeMentira()
    normal = canal.traducir(evento("hola", id_mensaje=1, etiquetas=["humano"]))
    borrar = canal.traducir(evento("Borrar", id_mensaje=2, etiquetas=["humano"]))

    assert canal.deberia_responder(normal) is False
    assert canal.deberia_responder(borrar) is True


def test_borrar_con_una_foto_no_es_el_comando():
    canal = CanalDeMentira()
    con_foto = evento("borrar", etiquetas=["humano"], attachments=[{"id": 1, "file_type": "image"}])

    assert canal.es_borrar(canal.traducir(con_foto)) is False
    assert canal.deberia_responder(canal.traducir(con_foto)) is False


def test_un_texto_sale_como_mensaje_y_devuelve_su_id():
    canal = CanalDeMentira()

    ident = canal.enviar_texto("27", "Hola")

    assert canal.llamadas[-1] == (
        "POST", "conversations/27/messages", {"content": "Hola", "message_type": "outgoing", "private": False}
    )
    assert ident == 9001


def test_un_archivo_sale_solo_sin_pie_de_foto(tmp_path):
    video = tmp_path / "MP02.mp4"
    video.write_bytes(b"VIDEO")
    canal = CanalDeMentira()

    ident = canal.enviar_archivo("27", video, "MP02-presentacion.mp4", "video/mp4")

    metodo, camino, datos = canal.llamadas[-1]
    assert (metodo, camino) == ("SUBIR", "conversations/27/messages")
    assert datos["campos"] == {"message_type": "outgoing", "private": "false"}, "sin «content»: sin pie de foto"
    assert datos["archivo"] == ("attachments[]", "MP02-presentacion.mp4", "video/mp4")
    assert datos["bytes"] == 5
    assert ident == 9001


def test_el_archivo_viaja_como_formulario_y_con_el_token(monkeypatch, tmp_path):
    from agente.f7 import canal as modulo

    pedidos = []

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"id": 4321}'

    class Abridor:
        def open(self, pedido, timeout=None):
            pedidos.append((pedido, timeout))
            return Respuesta()

    monkeypatch.setattr(modulo, "_ABRIDOR", Abridor())
    contenido = bytes([255, 216]) + b"FOTO"
    foto = tmp_path / "f.jpg"
    foto.write_bytes(contenido)
    canal = ChatwootF7(url="https://chatwoot.ejemplo.com", token="token-falso", cuenta_id=1)

    assert canal.enviar_archivo("27", foto, "MP04-carta.jpg", "image/jpeg") == 4321

    pedido, espera = pedidos[0]
    assert pedido.full_url == "https://chatwoot.ejemplo.com/api/v1/accounts/1/conversations/27/messages"
    assert pedido.get_method() == "POST"
    assert pedido.get_header("Api_access_token") == "token-falso"
    assert pedido.get_header("Content-type").startswith("multipart/form-data; boundary=")
    assert espera >= 60, "subir un video tarda más que una llamada común"
    cuerpo = pedido.data
    assert b'name="attachments[]"; filename="MP04-carta.jpg"' in cuerpo
    assert b"Content-Type: image/jpeg" in cuerpo
    assert contenido in cuerpo
    assert b'name="message_type"' in cuerpo and b"outgoing" in cuerpo
    assert b'name="content"' not in cuerpo


def test_el_pase_pone_humano_abre_y_asigna_a_candela_en_ese_orden():
    canal = CanalDeMentira(etiquetas=["cliente-vip"])

    assert canal.derivar("27") is True

    assert canal.escrituras() == ["labels", "toggle_status", "assignments"]
    assert canal.etiquetas_de["27"] == ["cliente-vip", "humano"]
    assert canal.estado["27"] == "open"
    assert canal.asignado["27"] == 3


def test_si_no_se_puede_asignar_el_bot_queda_pausado_y_el_pase_no_se_confirma():
    canal = CanalDeMentira(
        falla=lambda metodo, camino: ErrorDeChatwoot("500") if camino.endswith("/assignments") else None
    )

    assert canal.derivar("27") is False
    assert "humano" in canal.etiquetas_de["27"]


def test_si_chatwoot_termina_asignando_a_otra_persona_el_pase_no_se_confirma():
    canal = CanalDeMentira()
    canal.reasignado_a = 7  # la autoasignación de la bandeja puso a otro

    assert canal.derivar("27") is False
    assert "humano" in canal.etiquetas_de["27"]


def test_si_no_se_puede_poner_humano_el_pase_falla():
    canal = CanalDeMentira(
        falla=lambda metodo, camino: ErrorDeChatwoot("500") if camino.endswith("/labels") else None
    )

    with pytest.raises(ErrorDeChatwoot):
        canal.derivar("27")


def test_pasar_a_una_persona_tambien_la_deja_con_candela():
    # Lo usa el servidor cuando algo falla: la charla no puede quedar en el limbo.
    canal = CanalDeMentira()

    canal.pasar_a_persona("27")

    assert "humano" in canal.etiquetas_de["27"]
    assert canal.asignado["27"] == 3


def test_borrar_saca_solo_la_etiqueta_humano():
    canal = CanalDeMentira(etiquetas=["cliente-vip", "Humano"])

    canal.quitar_humano("27")

    assert canal.etiquetas_de["27"] == ["cliente-vip"]
    assert "27" not in canal.asignado, "no se desasigna a Candela"


def test_sin_humano_borrar_no_toca_las_etiquetas():
    canal = CanalDeMentira(etiquetas=["cliente-vip"])

    canal.quitar_humano("27")

    assert canal.escrituras() == []


def test_las_etiquetas_se_leen_de_chatwoot_y_si_no_se_puede_se_entera():
    assert CanalDeMentira(etiquetas=["a"]).etiquetas("27") == ["a"]

    roto = CanalDeMentira(falla=lambda metodo, camino: ErrorDeChatwoot("caído"))
    with pytest.raises(ErrorDeChatwoot):
        roto.etiquetas("27")


# -- La atención: un mensaje de Chatwoot entra, corre el turno y sale la respuesta ----

VIDEO_DE_PRESENTACION = "MP02-presentacion-fundas-a-medida-messenger.mp4"


@pytest.fixture
def media(tmp_path):
    """Una carpeta con un archivo de mentira por cada pieza del catálogo."""
    carpeta = tmp_path / "media"
    carpeta.mkdir()
    for pieza in cargar_catalogo()["assets"]:
        (carpeta / pieza["nombre_archivo"]).write_bytes(pieza["id"].encode())
    return carpeta


def atencion(respuestas, canal=None, almacen=None, media=None, modelo=None):
    """La atención de F7 con todo de mentira. Devuelve (servicio, canal, almacen, modelo, pausas)."""
    modelo = modelo or ModeloFalso(respuestas)
    canal = canal or CanalDeMentira()
    almacen = almacen or AlmacenEnMemoria()
    pausas: list[float] = []
    servicio = AtencionF7(
        canal, almacen, modelo=modelo, leer_hojas=leer_hojas_falso,
        carpeta_media=media, pausa=2.0, dormir=pausas.append,
    )
    return servicio, canal, almacen, modelo, pausas


def test_el_primer_mensaje_saluda_y_contesta_por_chatwoot():
    servicio, canal, _, _, _ = atencion([AIMessage("En qué te puedo ayudar?")])

    servicio.atender("27", "hola")

    assert canal.mandado() == [("texto", SALUDO_INICIAL), ("texto", "En qué te puedo ayudar?")]


def test_la_conversacion_sigue_aunque_se_reinicie_el_servidor():
    almacen = AlmacenEnMemoria()
    antes, _, _, _, _ = atencion([AIMessage("En qué te puedo ayudar?")], almacen=almacen)
    antes.atender("27", "hola")

    # Otro servicio, con la misma base: como después de un deploy.
    despues, canal, _, modelo, _ = atencion([AIMessage("Dale")], almacen=almacen)
    despues.atender("27", "quiero fundas")

    assert canal.mandado() == [("texto", "Dale")], "no saluda de nuevo"
    visto = [m.content for m in modelo.entradas[0][1:]]
    assert visto == ["hola", "En qué te puedo ayudar?", "quiero fundas"]


def test_cada_conversacion_tiene_su_propia_memoria():
    servicio, canal, _, _, _ = atencion([AIMessage("Buenas"), AIMessage("Buenas")])

    servicio.atender("27", "hola")
    servicio.atender("28", "hola")

    assert canal.mandado("27")[0] == ("texto", SALUDO_INICIAL)
    assert canal.mandado("28")[0] == ("texto", SALUDO_INICIAL)


def test_la_cotizacion_y_el_video_salen_en_el_orden_del_turno(media):
    servicio, canal, _, _, _ = atencion(
        [llamada("buscar_precio", "pedido", PEDIDO_CLIO), AIMessage("")], media=media
    )

    servicio.atender("27", "hola, precio de fundas para clio\nen el taller")

    mandado = canal.mandado()
    assert [tipo for tipo, _ in mandado] == ["texto", "texto", "texto", "archivo", "texto"]
    assert mandado[0][1] == SALUDO_INICIAL
    assert mandado[1][1].startswith("Cada funda se realiza a medida")
    assert mandado[3] == ("archivo", VIDEO_DE_PRESENTACION)
    assert "$150.000" in mandado[4][1]


def test_el_video_sale_con_su_archivo_y_su_tipo(media):
    servicio, canal, _, _, _ = atencion(
        [llamada("enviar_multimedia", "solicitudes", VIDEO_FUNDAS), AIMessage("")], media=media
    )

    servicio.atender("27", "me mandas el video de las fundas?")

    subidas = [datos for metodo, _, datos in canal.llamadas if metodo == "SUBIR"]
    assert subidas[0]["archivo"] == ("attachments[]", VIDEO_DE_PRESENTACION, "video/mp4")
    assert subidas[0]["bytes"] == len(b"MP02"), "se manda el archivo de la carpeta, entero"


def test_entre_un_mensaje_y_el_siguiente_hay_una_pausa():
    servicio, canal, _, _, pausas = atencion([AIMessage("En qué te puedo ayudar?")])

    servicio.atender("27", "hola")

    assert len(canal.mandado()) == 2
    assert pausas == [2.0], "una pausa entre los dos mensajes, ninguna antes del primero"


def test_cada_turno_queda_anotado_con_lo_que_se_mando():
    servicio, _, almacen, _, _ = atencion([AIMessage("En qué te puedo ayudar?")])

    servicio.atender("27", "hola")

    turno = almacen.turnos("27")[0]
    assert turno["lote"] == "hola"
    assert [e["tipo"] for e in turno["entrega"]] == ["saludo", "texto"]
    assert [e["chatwoot_id"] for e in turno["entrega"]] == [9001, 9002]


def test_el_pase_a_candela_se_hace_en_chatwoot_antes_de_confirmarlo():
    servicio, canal, _, _, _ = atencion(
        [llamada("derivar_humano", "motivo", "pago"), AIMessage("Listo, te paso con Candela")]
    )

    servicio.atender("27", "ya quiero pagar la seña")

    assert canal.mandado() == [("texto", SALUDO_INICIAL), ("texto", motor_derivacion.ACK)]
    assert canal.etiquetas_de["27"] == ["humano"]
    assert canal.asignado["27"] == 3
    caminos = [camino for _, camino, _ in canal.llamadas]
    confirmacion = max(i for i, c in enumerate(caminos) if c.endswith("/messages"))
    assert caminos.index("conversations/27/assignments") < confirmacion, "primero se asigna, después se avisa"


def test_si_el_pase_no_quedo_asignado_no_se_le_confirma_al_cliente():
    canal = CanalDeMentira()
    canal.reasignado_a = 7
    servicio, _, _, _, _ = atencion(
        [llamada("derivar_humano", "motivo", "pago"), AIMessage("Listo")], canal=canal
    )

    servicio.atender("27", "ya quiero pagar la seña")

    assert canal.mandado() == [("texto", SALUDO_INICIAL)]
    assert "humano" in canal.etiquetas_de["27"], "el agente igual queda pausado"


def test_con_humano_no_se_llama_al_modelo_ni_se_manda_nada():
    canal = CanalDeMentira(etiquetas=["humano"])
    servicio, _, _, modelo, _ = atencion([AIMessage("no debería salir")], canal=canal)

    servicio.atender("27", "hola? sigue ahí?")

    assert canal.mandado() == []
    assert modelo.entradas == []


def test_si_una_persona_toma_la_charla_mientras_piensa_no_se_manda_nada():
    canal = CanalDeMentira()

    class ModeloLento(ModeloFalso):
        def invoke(self, mensajes):
            canal.etiquetas_de["27"] = ["humano"]  # Candela la agarró mientras el modelo pensaba
            return super().invoke(mensajes)

    servicio, _, _, _, _ = atencion([], canal=canal, modelo=ModeloLento([AIMessage("En qué te ayudo?")]))

    servicio.atender("27", "hola")

    assert canal.mandado() == []


def test_borrar_saca_humano_en_chatwoot_confirma_y_arranca_de_cero():
    almacen = AlmacenEnMemoria()
    canal = CanalDeMentira()
    servicio, _, _, _, _ = atencion(
        [AIMessage("En qué te puedo ayudar?"), AIMessage("Hola de nuevo")], canal=canal, almacen=almacen
    )
    servicio.atender("27", "hola")
    canal.etiquetas_de["27"] = ["cliente-vip", "humano"]
    canal.llamadas.clear()

    servicio.atender("27", "borrar")

    assert canal.etiquetas_de["27"] == ["cliente-vip"]
    assert canal.mandado() == [("texto", ACK_BORRAR)]

    canal.llamadas.clear()
    servicio.atender("27", "hola")
    assert canal.mandado()[0] == ("texto", SALUDO_INICIAL), "después de borrar, saluda como al principio"


def test_si_falla_el_modelo_no_sale_nada_y_la_conversacion_queda_como_estaba():
    class Roto(ModeloFalso):
        def invoke(self, mensajes):
            raise RuntimeError("se cayó la API")

    servicio, canal, almacen, _, _ = atencion([], modelo=Roto([]))

    with pytest.raises(ErrorDeTurnoF7, match="se cayó la API"):
        servicio.atender("27", "hola")

    assert canal.mandado() == [], "ni el saludo: el turno no existió"
    assert almacen.cargar("27") is None


def test_si_chatwoot_rechaza_un_mensaje_se_entera_quien_llama():
    canal = CanalDeMentira(
        falla=lambda metodo, camino: ErrorDeChatwoot("500") if camino.endswith("/messages") else None
    )
    servicio, _, almacen, _, _ = atencion([AIMessage("En qué te puedo ayudar?")], canal=canal)

    with pytest.raises(ErrorDeEntrega):
        servicio.atender("27", "hola")

    assert almacen.cargar("27") is not None, "el turno se guardó: lo que falló fue mandar"


def test_si_no_se_pueden_leer_las_etiquetas_no_se_contesta():
    canal = CanalDeMentira(
        falla=lambda metodo, camino: ErrorDeChatwoot("caído") if camino.endswith("/labels") else None
    )
    servicio, _, _, modelo, _ = atencion([AIMessage("no debería salir")], canal=canal)

    with pytest.raises(ErrorDeChatwoot):
        servicio.atender("27", "hola")

    assert modelo.entradas == [], "sin saber si la atiende una persona, no se gasta ni un token"


def test_borrar_corta_el_turno_que_estaba_pensando():
    canal = CanalDeMentira()
    almacen = AlmacenEnMemoria()
    donde = {}

    class ModeloLento(ModeloFalso):
        def invoke(self, mensajes):
            donde["servicio"].pedir_corte("27")  # llegó «borrar» mientras el modelo pensaba
            return super().invoke(mensajes)

    servicio, _, _, _, _ = atencion(
        [], canal=canal, almacen=almacen, modelo=ModeloLento([AIMessage("En qué te ayudo?")])
    )
    donde["servicio"] = servicio

    servicio.atender("27", "hola")

    assert canal.mandado() == [], "lo que venía de antes del borrar no se manda"
    assert almacen.cargar("27") is None, "ni se guarda"


def test_olvidar_borra_lo_guardado_de_esa_conversacion():
    servicio, canal, almacen, _, _ = atencion([AIMessage("Buenas"), AIMessage("Buenas")])
    servicio.atender("27", "hola")

    servicio.olvidar("27")

    assert almacen.cargar("27") is None


# -- El servidor: Chatwoot avisa y contesta el agente de F7 --------------------------

from test_chatwoot import TOKEN, AvisosFalsos, esperar  # noqa: E402

from agente.canales.buffer import BufferDeMensajes  # noqa: E402
from agente.config import Config  # noqa: E402
from agente.f7.lector import LectorF7  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


def config_de_prueba(**ajustes) -> Config:
    config = Config(
        proveedor="claude",
        modelo="modelo-de-prueba",
        api_key="no-hace-falta",
        max_tokens=1024,
        memoria_mensajes=20,
        prompt_sistema=RAIZ / "prompts/sistema.md",
    )
    config.chatwoot_webhook_token = TOKEN
    config.buffer_segundos = 0
    for nombre, valor in ajustes.items():
        setattr(config, nombre, valor)
    return config


def servidor(servicio, canal, lector=None, avisos=None, **ajustes):
    """El webhook del kit con el agente de F7 adentro, todo de mentira."""
    pytest.importorskip("httpx", reason="TestClient de FastAPI necesita httpx")
    from fastapi.testclient import TestClient

    from agente.web.webhook import crear_app

    return TestClient(
        crear_app(
            config_de_prueba(**ajustes),
            canal=canal,
            avisos=avisos or AvisosFalsos(),
            lector=lector or LectorF7(canal),
            f7=servicio,
        )
    )


def test_un_mensaje_de_whatsapp_da_la_vuelta_completa():
    servicio, canal, _, _, _ = atencion([AIMessage("En qué te puedo ayudar?")])

    with servidor(servicio, canal) as web:
        respuesta = web.post(f"/chatwoot/{TOKEN}", json=evento("hola", conversacion=27))

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "recibido"
    assert canal.mandado() == [("texto", SALUDO_INICIAL), ("texto", "En qué te puedo ayudar?")]


def test_un_mensaje_de_otra_bandeja_no_se_contesta():
    servicio, canal, _, modelo, _ = atencion([AIMessage("no debería salir")])

    with servidor(servicio, canal) as web:
        respuesta = web.post(
            f"/chatwoot/{TOKEN}", json=evento("hola", conversacion=27, inbox={"id": 3, "name": "Test Bot API"})
        )

    assert respuesta.json()["estado"] == "ignorado"
    assert canal.mandado() == [] and modelo.entradas == []


def test_si_falla_el_modelo_la_charla_pasa_a_candela_y_el_cliente_no_ve_el_error():
    class Roto(ModeloFalso):
        def invoke(self, mensajes):
            raise RuntimeError("se cayó la API")

    servicio, canal, _, _, _ = atencion([], modelo=Roto([]))
    avisos = AvisosFalsos()

    with servidor(servicio, canal, avisos=avisos) as web:
        web.post(f"/chatwoot/{TOKEN}", json=evento("hola", conversacion=27))

    assert canal.mandado() == []
    assert "humano" in canal.etiquetas_de["27"]
    assert canal.asignado["27"] == 3
    assert len(avisos.mandados) == 1 and "se cayó la API" in avisos.mandados[0][1]


def test_borrar_no_espera_a_la_rafaga_y_tira_lo_que_estaba_juntado():
    servicio, canal, _, modelo, _ = atencion([AIMessage("no debería salir")])

    # Con 30 segundos de espera, «hola» queda juntándose; «borrar» sale ya.
    with servidor(servicio, canal, buffer_segundos=30) as web:
        web.post(f"/chatwoot/{TOKEN}", json=evento("hola", conversacion=27, id_mensaje=1))
        respuesta = web.post(f"/chatwoot/{TOKEN}", json=evento("borrar", conversacion=27, id_mensaje=2))
        assert respuesta.json()["estado"] == "borrar"
        assert esperar(lambda: canal.mandado() == [("texto", ACK_BORRAR)])

    assert canal.mandado() == [("texto", ACK_BORRAR)], "el «hola» de antes del borrar no se contesta"
    assert modelo.entradas == []


def test_borrar_funciona_aunque_la_charla_este_con_humano():
    canal = CanalDeMentira(etiquetas=["humano"])
    servicio, _, _, _, _ = atencion([], canal=canal)

    with servidor(servicio, canal) as web:
        web.post(f"/chatwoot/{TOKEN}", json=evento("Borrar", conversacion=27, etiquetas=["humano"]))
        assert esperar(lambda: canal.mandado() == [("texto", ACK_BORRAR)])

    assert canal.etiquetas_de["27"] == []


def test_descartar_tira_lo_juntado_sin_contestarlo():
    import asyncio

    contestados: list[tuple[str, str]] = []

    async def anotar(conversacion, texto):
        contestados.append((conversacion, texto))

    async def escena():
        buffer = BufferDeMensajes(0.05, anotar)
        await buffer.agregar("27", "hola")
        await buffer.agregar("28", "buenas")
        assert buffer.descartar("27") == 1
        await asyncio.sleep(0.2)

    asyncio.run(escena())

    assert contestados == [("28", "buenas")]


FOTO = {"id": 71, "file_type": "image", "data_url": "https://chatwoot.ejemplo.com/rails/active_storage/f.jpg"}
AUDIO = {"id": 72, "file_type": "audio", "data_url": "https://chatwoot.ejemplo.com/rails/active_storage/a.ogg"}


def test_una_foto_sin_texto_se_deja_pasar_como_hoy():
    servicio, canal, _, modelo, _ = atencion([AIMessage("no debería salir")])

    with servidor(servicio, canal) as web:
        web.post(f"/chatwoot/{TOKEN}", json=evento("", conversacion=27, attachments=[FOTO]))

    assert canal.mandado() == [] and modelo.entradas == []
    assert canal.escrituras() == [], "ni se contesta ni se pasa a nadie"


def test_una_foto_con_texto_cuenta_solo_el_texto():
    servicio, canal, _, modelo, _ = atencion([AIMessage("Dale")])

    with servidor(servicio, canal) as web:
        web.post(f"/chatwoot/{TOKEN}", json=evento("tienen para este auto?", conversacion=27, attachments=[FOTO]))

    assert modelo.entradas[0][-1].content == "tienen para este auto?"


def test_un_audio_se_contesta_con_lo_que_dice():
    canal = CanalDeMentira()
    canal.bajar = lambda direccion, tope: (b"audio", "audio/ogg")
    servicio, _, _, modelo, _ = atencion([AIMessage("Dale")], canal=canal)
    lector = LectorF7(canal, transcribir=lambda datos, tipo, nombre: "quiero fundas para un clio")

    with servidor(servicio, canal, lector=lector) as web:
        web.post(f"/chatwoot/{TOKEN}", json=evento("", conversacion=27, attachments=[AUDIO]))
        assert esperar(lambda: len(canal.mandado()) == 2)

    assert modelo.entradas[0][-1].content == "quiero fundas para un clio", "el audio entra como texto, sin agregados"


def test_un_audio_que_no_se_puede_escuchar_pasa_a_candela():
    servicio, canal, _, modelo, _ = atencion([AIMessage("no debería salir")])

    with servidor(servicio, canal, lector=LectorF7(canal)) as web:  # sin clave de OpenAI: no hay cómo escucharlo
        web.post(f"/chatwoot/{TOKEN}", json=evento("", conversacion=27, attachments=[AUDIO]))
        assert esperar(lambda: canal.asignado.get("27") == 3)

    assert "humano" in canal.etiquetas_de["27"]
    assert canal.mandado() == [] and modelo.entradas == []


def test_el_salud_dice_que_atiende_f7():
    servicio, canal, _, _, _ = atencion([])

    with servidor(servicio, canal) as web:
        datos = web.get("/salud").json()

    assert datos["estado"] == "ok"
    assert datos["agente"] == "f7"
    assert datos["bandeja"] == "1"
    assert datos["prompt"]


def test_reset_borra_lo_guardado_de_f7():
    servicio, canal, almacen, _, _ = atencion([AIMessage("Buenas")])

    with servidor(servicio, canal) as web:
        web.post(f"/chatwoot/{TOKEN}", json=evento("hola", conversacion=27))
        assert almacen.cargar("27") is not None
        respuesta = web.post(f"/reset/{TOKEN}", json={"conversacion": "27"})

    assert respuesta.json()["estado"] == "ok"
    assert almacen.cargar("27") is None


# -- Al arrancar: si falta algo, no arranca -------------------------------------------

from agente.f7.produccion import ErrorDeArranque, piezas_con_problemas  # noqa: E402
from agente.f7.servidor import crear_app_f7  # noqa: E402


def test_sin_las_fotos_y_videos_el_servidor_no_arranca(tmp_path):
    with pytest.raises(ErrorDeArranque, match="MP01"):
        crear_app_f7(
            config_de_prueba(), modelo=ModeloFalso([]), canal=CanalDeMentira(),
            almacen=AlmacenEnMemoria(), carpeta_media=tmp_path,
        )


def test_un_archivo_cambiado_tampoco_sirve(media):
    # Los de la carpeta de mentira tienen el nombre correcto y otro contenido.
    problemas = piezas_con_problemas(media)
    assert len(problemas) == 14 and "no es el archivo del catálogo" in problemas[0]


def test_las_fotos_y_videos_del_proyecto_son_las_del_catalogo():
    assert piezas_con_problemas(RAIZ / "recursos" / "f7-media") == []


def test_con_todo_en_su_lugar_el_servidor_arranca():
    from fastapi.testclient import TestClient

    app = crear_app_f7(
        config_de_prueba(), modelo=ModeloFalso([AIMessage("Buenas")]), canal=CanalDeMentira(),
        almacen=AlmacenEnMemoria(), leer_hojas=leer_hojas_falso,
    )

    with TestClient(app) as web:
        assert web.get("/salud").json()["agente"] == "f7"
        web.post(f"/chatwoot/{TOKEN}", json=evento("hola", conversacion=27))


def test_la_base_se_prueba_de_punta_a_punta_y_no_deja_rastro(almacen):
    almacen.probar()
    assert almacen.cargar("__arranque__") is None


def test_si_la_base_no_devuelve_lo_que_se_guardo_se_nota():
    class Olvidadizo(AlmacenEnMemoria):
        def cargar(self, conversacion):
            return None

    with pytest.raises(RuntimeError):
        Olvidadizo().probar()


def test_sin_base_el_servidor_no_arranca_y_dice_que_revisar():
    class SinBase(AlmacenEnMemoria):
        def preparar(self):
            raise ConnectionError("no se puede conectar")

    with pytest.raises(ErrorDeArranque, match="POSTGRES_DSN"):
        crear_app_f7(config_de_prueba(), modelo=ModeloFalso([]), canal=CanalDeMentira(), almacen=SinBase())


def test_con_agente_f7_arranca_el_servidor_de_f7_y_si_no_el_del_kit(monkeypatch):
    sys.path.insert(0, str(RAIZ))
    import webhook_chatwoot as entrada

    armados = []
    monkeypatch.setattr(entrada, "crear_app_f7", lambda config: armados.append("f7") or "servidor-f7")
    monkeypatch.setattr(entrada, "crear_app", lambda config: armados.append("kit") or "servidor-kit")

    monkeypatch.setenv("AGENTE", "f7")
    assert entrada.armar_app(object()) == "servidor-f7"
    monkeypatch.setenv("AGENTE", "kit")
    assert entrada.armar_app(object()) == "servidor-kit"
    assert armados == ["f7", "kit"]


def test_si_no_se_dice_que_agente_atiende_el_servidor_no_arranca(monkeypatch):
    # Arrancar el agente genérico por un olvido sería poner un bot sin guion a atender a los clientes de F7.
    from agente import ErrorDeConfiguracion

    sys.path.insert(0, str(RAIZ))
    import webhook_chatwoot as entrada

    monkeypatch.setattr(entrada, "crear_app", lambda config: "servidor-kit")
    monkeypatch.delenv("AGENTE", raising=False)

    with pytest.raises(ErrorDeConfiguracion, match="AGENTE=f7"):
        entrada.armar_app(object())


def test_en_tu_maquina_las_conversaciones_van_a_un_archivo_al_lado_del_del_kit(tmp_path):
    from agente.f7.servidor import almacen_de

    config = config_de_prueba(sqlite_ruta=str(tmp_path / "datos" / "conversaciones.db"))

    almacen = almacen_de(config)
    almacen.preparar()
    almacen.guardar("27", "estado")

    assert (tmp_path / "datos" / "f7-conversaciones.db").is_file()


def test_el_modelo_se_arma_al_arrancar_y_no_con_el_primer_cliente(monkeypatch):
    armados = []
    monkeypatch.setattr(
        "agente.modelos.crear_modelo", lambda **datos: armados.append(datos["modelo"]) or ModeloFalso([])
    )

    crear_app_f7(
        config_de_prueba(), canal=CanalDeMentira(), almacen=AlmacenEnMemoria(), leer_hojas=leer_hojas_falso
    )

    assert armados == ["modelo-de-prueba"]


# -- El orden en WhatsApp: un video tarda más en llegar que un texto -----------------


def _donde(canal, condicion) -> list[int]:
    return [i for i, llamada_hecha in enumerate(canal.llamadas) if condicion(*llamada_hecha)]


def test_el_canal_sabe_cuando_un_mensaje_ya_se_entrego():
    canal = CanalDeMentira()
    ident = canal.enviar_texto("27", "hola")
    esperas: list[float] = []

    canal.estados_de_entrega = ["sent", 0, "delivered"]
    assert canal.esperar_entrega("27", ident, dormir=esperas.append) == "entregado"
    assert len(esperas) == 2, "espera entre una consulta y la siguiente, no después de la última"

    canal.estados_de_entrega = [2]  # así lo manda Chatwoot en algunas versiones: 2 es «leído»
    assert canal.esperar_entrega("27", ident, dormir=esperas.append) == "entregado"
    canal.estados_de_entrega = ["failed"]
    assert canal.esperar_entrega("27", ident, dormir=esperas.append) == "fallido"
    canal.estados_de_entrega = ["sent"] * 50
    assert canal.esperar_entrega("27", ident, dormir=esperas.append) == "sin_confirmar"


def test_despues_de_un_video_espera_a_que_llegue_antes_de_mandar_lo_siguiente(media):
    # Sin esperar, la cotización (texto) le llegaría al cliente antes que el video.
    canal = CanalDeMentira()
    canal.estados_de_entrega = ["sent", "sent", "delivered"]
    servicio, _, _, _, _ = atencion(
        [llamada("buscar_precio", "pedido", PEDIDO_CLIO), AIMessage("")], canal=canal, media=media
    )

    servicio.atender("27", "hola, precio de fundas para clio\nen el taller")

    subida = _donde(canal, lambda metodo, camino, _: metodo == "SUBIR")[0]
    consultas = canal.consultas_de_entrega()
    cotizacion = _donde(canal, lambda metodo, camino, _: metodo == "POST" and camino.endswith("/messages"))[-1]
    assert len(consultas) == 3
    assert subida < consultas[0] and consultas[-1] < cotizacion


def test_si_whatsapp_no_confirma_la_entrega_igual_se_manda_lo_que_sigue(media):
    canal = CanalDeMentira()
    canal.estados_de_entrega = ["sent"] * 500
    servicio, _, _, _, _ = atencion(
        [llamada("buscar_precio", "pedido", PEDIDO_CLIO), AIMessage("")], canal=canal, media=media
    )

    servicio.atender("27", "hola, precio de fundas para clio\nen el taller")

    assert "$150.000" in canal.mandado()[-1][1]
    assert len(canal.consultas_de_entrega()) <= 12, "se cansa de preguntar"


def test_si_no_confirma_una_vez_no_vuelve_a_esperar_en_ese_turno(media):
    # Cinco fotos seguidas: si Chatwoot no informa entregas, no se pierde un rato por cada una.
    canal = CanalDeMentira()
    canal.estados_de_entrega = ["sent"] * 500
    servicio, _, _, _, _ = atencion(
        [llamada("enviar_multimedia", "solicitudes", [{"producto": "fundas", "contenido": "disenos"}]),
         AIMessage("")],
        canal=canal, media=media,
    )

    servicio.atender("27", "me mandas fotos de los diseños?")

    subidas = _donde(canal, lambda metodo, camino, _: metodo == "SUBIR")
    consultas = canal.consultas_de_entrega()
    assert len(subidas) >= 3
    assert consultas and all(subidas[0] < c < subidas[1] for c in consultas), "solo esperó después de la primera"


def test_si_lo_ultimo_que_sale_es_el_video_no_se_queda_esperando(media):
    servicio, canal, _, _, _ = atencion(
        [llamada("enviar_multimedia", "solicitudes", VIDEO_FUNDAS), AIMessage("")], media=media
    )

    servicio.atender("27", "me mandas el video de las fundas?")

    assert canal.mandado()[-1][0] == "archivo"
    assert canal.consultas_de_entrega() == []


# -- La planilla de precios se prueba al arrancar --------------------------------------

from agente.f7.precios.planilla import ErrorPlanilla  # noqa: E402


def app_f7(**piezas):
    """El servidor de F7 completo, con todo de mentira salvo lo que la prueba cambie."""
    piezas.setdefault("modelo", ModeloFalso([]))
    piezas.setdefault("canal", CanalDeMentira())
    piezas.setdefault("almacen", AlmacenEnMemoria())
    piezas.setdefault("leer_hojas", leer_hojas_falso)
    return crear_app_f7(config_de_prueba(), **piezas)


def test_al_arrancar_se_lee_la_planilla_de_precios_y_el_salud_lo_cuenta():
    from fastapi.testclient import TestClient

    pedidas = []

    def leer(titulos):
        pedidas.append(list(titulos))
        return leer_hojas_falso(titulos)

    with TestClient(app_f7(leer_hojas=leer)) as web:
        assert web.get("/salud").json()["planilla"] == "ok"

    assert len(pedidas) == 1, "una vez, al arrancar: el /salud no la baja de nuevo"
    assert len(pedidas[0]) == 8 and "Fundas a medida" in pedidas[0]


def test_si_la_planilla_no_se_puede_leer_arranca_igual_y_el_salud_lo_avisa():
    from fastapi.testclient import TestClient

    def leer(titulos):
        raise ErrorPlanilla("no_se_pudo_bajar")

    with TestClient(app_f7(leer_hojas=leer)) as web:
        assert web.get("/salud").json()["planilla"] == "error: no_se_pudo_bajar"


def test_un_turno_que_falla_tambien_queda_anotado():
    # Es lo primero que se mira cuando alguien dice «no me contestó».
    class Roto(ModeloFalso):
        def invoke(self, mensajes):
            raise RuntimeError("se cayó la API")

    servicio, _, almacen, _, _ = atencion([], modelo=Roto([]))

    with pytest.raises(ErrorDeTurnoF7):
        servicio.atender("27", "hola")

    turno = almacen.turnos("27")[0]
    assert turno["lote"] == "hola"
    assert "se cayó la API" in turno["error"]
    assert turno["entrega"] == [] and turno["sin_envio"] == "error"


def test_lo_que_estaba_en_cola_antes_de_un_borrar_no_se_contesta():
    servicio, canal, almacen, modelo, _ = atencion([AIMessage("no debería salir")])

    en_cola = servicio.corte_actual("27")  # el lote ya salió de la ráfaga y espera su turno...
    servicio.pedir_corte("27")             # ...y antes de que le toque, llega «borrar»
    resultado = servicio.atender("27", "hola", en_cola)

    assert canal.mandado() == [] and modelo.entradas == [], "ni se piensa: no se gasta un token"
    assert almacen.cargar("27") is None
    assert resultado.globos == []
