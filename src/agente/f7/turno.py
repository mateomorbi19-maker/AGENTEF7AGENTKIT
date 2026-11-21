"""Un turno de F7: lo que hoy hace el principal de n8n con cada lote del cliente.

    borrar? → humano? → saludo si es el primer mensaje de la época → modalidad
    → fase y prompt del turno → modelo + herramientas → control de salida
    (y derivación automática si lo pide) → memoria (lote + salida segura +
    nota de cotización) → humano? → partir la respuesta → mandar

Es para la web de pruebas: la conversación vive en una `SesionLocal` y la
memoria en este objeto, dentro del proceso (se pierde al reiniciar el
servidor). Lo que «se manda» al cliente sale como una lista de globos, en el
orden en que le llegarían.

Diferencias a propósito con n8n, por ser la web de pruebas:
- No hay buffer ni la espera de 7 s antes del saludo: cada envío de la web
  es un lote.
- Si falla el modelo o el control, el error se muestra en pantalla (en
  producción sería silencio).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from . import derivacion
from .herramientas import crear_herramientas
from .multimedia import herramienta as multimedia
from .local import ContextoTurno, Globo, SesionLocal
from .modalidad import preparar_estado
from .partir import partir_respuesta_f7
from .precios import herramienta as precios
from .prompt import (
    RUTA_PROMPT,
    catalogo_del_guion,
    clasificar_fase,
    ensamblar_prompt,
    frases_de_ubicacion_y_horario,
    frases_del_guion,
    fecha_buenos_aires,
    frases_paso_1bis,
    leer_bloques,
    leer_metadatos_catalogo,
    nombra_tapizado,
    pedido_de_material,
)
from .salida import (
    MOTIVO_DERIVACION_CONTROL,
    controlar_salida_comercial,
    corregir_frases,
    frases_tal_cual,
    reparar_memoria_comercial,
    requiere_revision_comercial,
    salida_comercial_confirmada,
    sin_afirmar_disponibilidad,
    sin_negar_fotos,
    texto_para_memoria,
    una_sola_pregunta,
    verificar_memoria_comercial,
)
from .textos import ACK_BORRAR, SALUDO_INICIAL, es_comando_borrar

# La ventana de la memoria de n8n: 30 interacciones (hasta 60 mensajes).
INTERACCIONES_EN_MEMORIA = 30
# Cuántos mensajes del cliente mira la modalidad («Leer Estado»).
HISTORIAL_HUMANO = 30
# El tope de vueltas modelo → herramientas del agente de n8n.
VUELTAS_MAXIMAS = 10
# En n8n, la derivación automática no arranca pasados 510 s del turno.
TOPE_DERIVACION_SEGUNDOS = 510
# El tramo fijo del prompt (igual en todas las fases): es el que se cachea.
BLOQUES_FIJOS = ("base", "recorrido", "conocimiento")

# La presentación de las fundas del guion (paso 2 del recorrido), tal cual, y el
# video que va con ella (pedido de Mateo, 17/11).
PRESENTACION_FUNDAS = ("Cada funda se realiza a medida y por encargo para cada butaca , el material que "
                       "utilizamos es cuero automotor. Podes elegir diseño y color que te guste")
VIDEO_PRESENTACION_FUNDAS = "MP02"
VIDEO_COMPARATIVO = "MP01"
# Campaña de multimedia del 21/11. Paso 4 del guion: con el producto y la modalidad claros y sin
# material previo, primero se muestra el producto y después se cotiza. Las fundas a medida ya
# tienen su presentación con video; estos son los otros productos con material.
PRODUCTOS_QUE_SE_MUESTRAN_AL_COTIZAR = ("tipo tapizado", "alfombra", "cubrevolante")
# «no me lo mandes», «ya lo vi»: el cliente no quiere que le manden el material.
_RX_NO_QUIERE_MATERIAL = re.compile(
    r"\bno me (?:lo|la|los|las) (?:mand|envi|pas)\w*"
    r"|\bno (?:hace falta|necesito|quiero) (?:que me (?:mand|envi|pas)\w*|(?:el|los|ver) (?:videos?|fotos?|material))"
    r"|\bya (?:lo|la|los|las) vi\b"
)


def _plano(texto: str) -> str:
    """Minúsculas, sin tildes ni signos: para reconocer la presentación aunque cambie un detalle."""
    import unicodedata

    sin = "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower()
    return " ".join("".join(c if c.isalnum() else " " for c in sin).split())


# Prueba de «romper el flujo» del 21/11 (sobre el texto del cliente en minúsculas y sin tildes).
_RX_PREGUNTA_HORARIO = re.compile(
    r"\bhorarios?\b|\b(?:a|hasta) que hora\b|\bque dias? (?:atienden|abren|trabajan|estan)\b|\bestan abiertos?\b"
    r"|\b(?:atienden|abren|trabajan)\b[^.?!\n]*\b(?:sabados?|domingos?|findes?|fin de semana|tarde|manana|mediodia)\b"
)
_RX_PREGUNTA_UBICACION = re.compile(
    r"\bdonde (?:estan|queda|quedan|se encuentran|los encuentro)\b|\bdireccion\b|\bubicacion\b|\bubicados\b|\bcomo llego\b"
)
# Una pregunta de verdad: con signo, o con «cuánto», «cuándo», «dónde» o «cuál». «Qué bueno» no.
_RX_PREGUNTA_DEL_CLIENTE = re.compile(r"\?|\b(?:cuanto|cuanta|cuantos|cuantas|cuando|donde|cual|cuales)\b")


def _presenta_fundas(texto: str) -> bool:
    return "cada funda se realiza a medida" in _plano(texto)


def _es_parte_de_presentacion(parte: str) -> bool:
    plano = _plano(parte)
    return plano.startswith("cada funda se realiza a medida") or plano.startswith("podes elegir diseno y color")


class ErrorDeTurno(Exception):
    """El turno no puede seguir. En n8n sería «Conservar error»: no sale nada."""


@dataclass
class ResultadoTurno:
    globos: list[Globo]
    detalle: dict
    error: str | None = None
    mensajes_en_memoria: int = 0


@dataclass
class _Uso:
    entrada: int = 0
    salida: int = 0
    cache_leidos: int = 0
    cache_guardados: int = 0

    def sumar(self, mensaje) -> None:
        uso = getattr(mensaje, "usage_metadata", None) or {}
        detalle = uso.get("input_token_details") or {}
        self.entrada += uso.get("input_tokens", 0) or 0
        self.salida += uso.get("output_tokens", 0) or 0
        self.cache_leidos += detalle.get("cache_read", 0) or 0
        self.cache_guardados += detalle.get("cache_creation", 0) or 0

    def a_dict(self) -> dict:
        return {
            "entrada": self.entrada,
            "salida": self.salida,
            "cache_leidos": self.cache_leidos,
            "cache_guardados": self.cache_guardados,
        }


def _es_humano(etiqueta) -> bool:
    return isinstance(etiqueta, str) and etiqueta.strip().lower() == "humano"


def _texto_de(mensaje) -> str:
    contenido = getattr(mensaje, "content", "")
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "".join(
            b.get("text", "")
            for b in contenido
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


class AgenteF7:
    """El agente de F7 para la web de pruebas: una conversación por vez.

    `modelo`: un modelo de LangChain ya armado (las pruebas pasan uno falso).
    Si no se pasa, se arma con `config` (o con el .env) la primera vez.
    """

    def __init__(
        self,
        modelo=None,
        *,
        config=None,
        leer_hojas=None,
        ruta_prompt: Path | str | None = None,
    ) -> None:
        self.config = config
        self._modelo = modelo
        self.leer_hojas = leer_hojas
        self.ruta_prompt = Path(ruta_prompt) if ruta_prompt else RUTA_PROMPT
        self.sesion = SesionLocal()
        # La memoria de la época actual: [("human"|"ai", texto)], como la
        # guarda n8n (solo el lote y la salida segura, sin herramientas).
        self.memoria: list[tuple[str, str]] = []

    # -- Modelo ---------------------------------------------------------------

    @property
    def modelo(self):
        if self._modelo is None:
            from ..config import Config
            from ..modelos import crear_modelo

            if self.config is None:
                self.config = Config.desde_entorno()
            self._modelo = crear_modelo(
                proveedor=self.config.proveedor,
                api_key=self.config.api_key,
                modelo=self.config.modelo,
                max_tokens=self.config.max_tokens,
            )
        return self._modelo

    def cambiar_config(self, config) -> None:
        """Otro proveedor o modelo: la conversación y la memoria se conservan."""
        self.config = config
        self._modelo = None

    @property
    def nombre_modelo(self) -> str:
        return self.config.modelo if self.config is not None else "modelo-de-prueba"

    def _usar_cache(self) -> bool:
        if self.config is None:
            return True
        return bool(self.config.cache) and self.config.proveedor == "claude"

    # -- Conversación ---------------------------------------------------------

    def reiniciar(self) -> None:
        """Conversación nueva de cero: sesión, etiquetas, registros y memoria."""
        self.sesion = SesionLocal()
        self.memoria = []

    def mensajes_en_memoria(self) -> int:
        return len(self.memoria)

    def _memoria_para_modelo(self) -> list:
        ventana = self.memoria[-2 * INTERACCIONES_EN_MEMORIA:]
        while ventana and ventana[0][0] != "human":
            ventana = ventana[1:]
        mensajes = []
        for rol, texto in ventana:
            if rol == "human":
                mensajes.append(HumanMessage(texto))
            elif texto:
                # Un silencio queda en la memoria como texto vacío, pero la API
                # de Claude no acepta mensajes vacíos: no se manda.
                mensajes.append(AIMessage(texto))
        return mensajes

    def _sistema(self, prompt: str, bloques: dict) -> SystemMessage:
        fijo = "\n\n".join(bloques[k] for k in BLOQUES_FIJOS)
        if self._usar_cache() and prompt.startswith(fijo) and len(prompt) > len(fijo):
            return SystemMessage(
                content=[
                    {"type": "text", "text": fijo, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": prompt[len(fijo):]},
                ]
            )
        return SystemMessage(prompt)

    # -- El turno -------------------------------------------------------------

    def responder(self, texto: str) -> ResultadoTurno:
        """Un lote del cliente. Devuelve los globos que le llegarían y el detalle."""
        sesion = self.sesion
        message_id = sesion.nuevo_message_id()
        sesion.salientes.clear()
        detalle: dict = {"message_id": message_id, "lote": texto, "nota": None}

        def resultado(error: str | None = None) -> ResultadoTurno:
            if error:
                detalle["error"] = error
            return ResultadoTurno(
                list(sesion.salientes), detalle, error, self.mensajes_en_memoria()
            )

        # b. «borrar»: época nueva, sin «humano», memoria nueva.
        if es_comando_borrar(texto):
            sesion.epoca = message_id
            sesion.etiquetas[:] = [e for e in sesion.etiquetas if not _es_humano(e)]
            self.memoria = []
            sesion.multimedia_registrada.clear()
            sesion.mandar("borrar", ACK_BORRAR)
            detalle["accion"] = "borrar"
            detalle["etiquetas"] = list(sesion.etiquetas)
            return resultado()

        # c. Con «humano», silencio total: ni memoria ni modelo.
        if any(_es_humano(e) for e in sesion.etiquetas):
            detalle["accion"] = "silencio_humano"
            detalle["etiquetas"] = list(sesion.etiquetas)
            detalle["nota"] = (
                "El bot está pausado (etiqueta «humano»): no contesta ni guarda nada. "
                "Escribí «borrar» o tocá «Borrar conversación» para reactivarlo."
            )
            return resultado()

        try:
            return self._turno(texto, message_id, detalle, resultado)
        except Exception as e:  # el error tiene que llegar a la pantalla
            return resultado(f"{type(e).__name__}: {e}")

    def _turno(self, texto, message_id, detalle, resultado) -> ResultadoTurno:
        sesion = self.sesion
        humanos_previos = [t for rol, t in self.memoria if rol == "human"]

        # d. Saludo fijo si es el primer mensaje del cliente en esta época.
        saludo = not humanos_previos
        if saludo:
            sesion.mandar("saludo", SALUDO_INICIAL)
        detalle["saludo"] = saludo

        # e. Modalidad: los últimos 30 mensajes del cliente ya con el lote.
        historial = (humanos_previos + [texto])[-HISTORIAL_HUMANO:]
        estado = preparar_estado(
            {"key": f"1:{sesion.conversation_id}:{sesion.epoca}", "texto": texto},
            len(humanos_previos),
            list(sesion.multimedia_registrada),
            historial,
        )
        modalidad = estado["modalidad_confirmada"]
        detalle["modalidad"] = modalidad

        # f. Prompt del turno, leído del archivo en cada mensaje.
        bloques = leer_bloques(self.ruta_prompt)
        # Corrección del 20/11 (campaña de pruebas): si el cliente nombra tapizar o
        # tapizado y el paso 1 bis todavía no se hizo, el prompt del turno lo avisa.
        estado["pregunta_tapizado_pendiente"] = self._tapizado_pendiente(texto, bloques, sesion)
        detalle["pregunta_tapizado_pendiente"] = estado["pregunta_tapizado_pendiente"]
        # Campaña de multimedia del 21/11: el pedido de material que quedó sin atender por esa pregunta.
        estado["material_pendiente"] = self._material_pendiente(bloques)
        # Qué pidió el cliente (fotos, video, un reenvío) lo decide el código mirando su mensaje,
        # no el modelo.
        pedido = pedido_de_material(texto, [t for rol, t in self.memoria if rol == "human"])
        detalle["pedido_de_material"] = pedido
        estado["reenvio_pedido"] = pedido["reenvio"]
        armado = ensamblar_prompt(
            estado, bloques, fecha_buenos_aires(), leer_metadatos_catalogo()
        )
        detalle["fase"] = armado["fase_detectada"]
        detalle["prompt_version"] = armado["prompt_version"]
        detalle["bloques_usados"] = armado["bloques_usados"]

        # g. Modelo + herramientas, de a una llamada y en orden.
        contexto = ContextoTurno(
            sesion=sesion, ultimo_message_id=message_id, modalidad_confirmada=modalidad,
            # Si el cliente no pidió fotos ni videos, lo ya mandado no se reenvía. Pedir un reenvío
            # sin decir «video» («me lo pasás de nuevo?») también es pedirlo.
            pidio_multimedia=armado["fase_detectada"] == "multimedia" or pedido["reenvio"],
            pidio_fotos=pedido["fotos"], pidio_video=pedido["video"], sin_video=pedido["sin_video"],
            # Re-prueba del 21/11: nombrar un video («se ve en algún video?») no es pedir que se lo
            # manden otra vez. Lo que ya tiene se repite solo si lo pide o si el modelo lo marca.
            reenvio_solo_marcado=not (pedido["reenvio"] or pedido["pide_envio"]),
            texto_cliente=texto,
            # Pidió el video de «tipo tapizado» y recibió la pregunta del paso 1 bis: sale ese.
            producto_pendiente=(
                "tipo tapizado"
                if "tipo tapizado" in _plano(estado["material_pendiente"] or "") else None
            ),
        )
        pasos: list = []
        herramientas = crear_herramientas(contexto, pasos, leer_hojas=self.leer_hojas)
        por_nombre = {h.name: h for h in herramientas}
        modelo = self.modelo.bind_tools(herramientas)

        mensajes = [
            self._sistema(armado["prompt_ensamblado"], bloques),
            *self._memoria_para_modelo(),
            HumanMessage(texto),
        ]
        uso = _Uso()
        detalle["tokens"] = uso.a_dict()
        llamadas_detalle: list[dict] = []
        detalle["herramientas"] = llamadas_detalle

        respuesta = None
        for _ in range(VUELTAS_MAXIMAS):
            respuesta = self.modelo_invoke(modelo, mensajes)
            uso.sumar(respuesta)
            detalle["tokens"] = uso.a_dict()
            mensajes.append(respuesta)
            llamadas = getattr(respuesta, "tool_calls", None) or []
            if not llamadas:
                break
            for llamada in llamadas:
                herramienta = por_nombre.get(llamada.get("name"))
                antes = len(pasos)
                if herramienta is None:
                    contenido = json.dumps(
                        {"error": f"Herramienta desconocida: {llamada.get('name')}"},
                        ensure_ascii=False,
                    )
                    mensajes.append(ToolMessage(contenido, tool_call_id=llamada.get("id")))
                else:
                    mensajes.append(herramienta.invoke({**llamada, "type": "tool_call"}))
                llamadas_detalle.append(
                    {
                        "herramienta": llamada.get("name"),
                        "entrada": llamada.get("args"),
                        "resultado": pasos[-1]["observation"] if len(pasos) > antes else None,
                    }
                )
        else:
            raise ErrorDeTurno(
                f"El modelo siguió pidiendo herramientas después de {VUELTAS_MAXIMAS} vueltas."
            )

        raw = _texto_de(respuesta)
        detalle["salida_modelo"] = raw

        # La memoria de n8n guarda el lote y la salida cruda apenas termina el
        # modelo; la reparación de abajo la cambia por la salida segura.
        self.memoria.append(("human", texto))
        self.memoria.append(("ai", raw))

        # h. Control de salida y, si lo pide, derivación automática.
        agente_n8n = {"output": raw, "intermediateSteps": pasos}
        salida = controlar_salida_comercial(agente_n8n, texto_cliente=texto)
        detalle["control"] = {
            "decision": salida.get("output"),
            "motivo": (salida.get("control_salida") or {}).get("motivo"),
            "requiere_derivacion": salida.get("requiere_derivacion"),
            "control_salida": salida.get("control_salida"),
        }
        detalle["derivacion_automatica"] = None
        if requiere_revision_comercial(salida):
            if contexto.segundos() > TOPE_DERIVACION_SEGUNDOS:
                raise ErrorDeTurno("Tiempo insuficiente para iniciar derivación")
            dato = derivacion.ejecutar(MOTIVO_DERIVACION_CONTROL, contexto)
            detalle["derivacion_automatica"] = {
                "motivo": MOTIVO_DERIVACION_CONTROL,
                "solicitud_id": contexto.solicitud_id(derivacion.herramienta.SUFIJO_SOLICITUD),
                "resultado": dato,
            }
        else:
            dato = salida
        final = salida_comercial_confirmada(dato, raw, texto_cliente=texto)
        # Corrección del 20/11 (campaña de pruebas): las frases fijas del guion salen como son
        # («colocarlo», no «retirarlo») y no se avisa «el video ya quedó enviado». Se corrige lo
        # que se manda y lo que queda en la memoria; `salida_modelo` conserva lo que escribió el modelo.
        # Re-prueba de multimedia del 21/11: una frase del guion copiada con tildes o signos de más
        # también sale como está escrita.
        # Decisión de Mateo del 21/11: no se le dice al cliente que no hay fotos.
        literales = frases_del_guion(bloques)
        # Si en este turno ya salió material («se envía el video y ya»), no se agrega el catálogo.
        salio_material = any(g.tipo == "multimedia" for g in sesion.salientes)
        catalogo = None if salio_material else catalogo_del_guion(bloques)
        # Prueba de «romper el flujo» del 21/11: sin una cotización que lo respalde no se afirma que
        # hay un producto para un vehículo, y después de la pregunta de modalidad no va otra pregunta.
        cotizo = any((p.get("action") or {}).get("tool") == "buscar_precio"
                     and (p.get("observation") or {}).get("estado") in ("cotizado", "parcial") for p in pasos)

        def corregir(escrito: str) -> str:
            escrito = sin_negar_fotos(frases_tal_cual(corregir_frases(escrito), literales), catalogo)
            if not cotizo:
                escrito = sin_afirmar_disponibilidad(escrito)
            return una_sola_pregunta(escrito)

        corregida = {
            campo: corregir(final[campo])
            for campo in ("output", "memoria_output")
            if isinstance(final.get(campo), str)
        }
        detalle["control"]["frases_corregidas"] = any(corregida[c] != final[c] for c in corregida)
        final = {**final, **corregida}
        detalle["control"]["final"] = {
            "output": final.get("output"),
            "motivo": (final.get("control_salida") or {}).get("motivo"),
            "origen": (final.get("control_salida") or {}).get("origen"),
            "bot_pausado": final.get("bot_pausado"),
        }

        # i. Memoria: la salida segura (más la nota de cotización) en vez de la cruda.
        segura = texto_para_memoria(final, raw)
        memoria = reparar_memoria_comercial(self.memoria[-1][1], raw, segura)
        self.memoria[-1] = ("ai", memoria["contenido"])
        final = verificar_memoria_comercial(final, memoria)
        detalle["memoria"] = {
            "estado": memoria["estado_memoria"],
            "guardado": memoria["contenido"],
        }

        # j. ¿«humano» antes de mandar? Si el turno pasó a Candela, no sale texto.
        salida_final = final.get("output") or ""
        if any(_es_humano(e) for e in sesion.etiquetas):
            if salida_final:
                detalle["texto_no_enviado_por_humano"] = salida_final
            detalle["nota"] = "El bot quedó pausado: la conversación pasó a Candela (etiqueta «humano»)."
        else:
            self._material_antes_de_cotizar(contexto, pasos, detalle, raw)
            partes = partir_respuesta_f7(salida_final)
            # La presentación de fundas va una sola vez y siempre junto a su video.
            ya_presentado = any(_presenta_fundas(t) for rol, t in self.memoria[:-2] if rol == "ai")
            video_en_turno = any(g.tipo == "multimedia" and g.datos.get("asset_id") == VIDEO_PRESENTACION_FUNDAS
                                 for g in sesion.salientes)
            if ya_presentado:
                partes = [p for p in partes if not _es_parte_de_presentacion(p)]  # no se repite
            elif (_presenta_fundas(raw) or (video_en_turno and detalle.get("fase") != "multimedia")
                  or detalle.get("presentacion_automatica")):
                # Escribió la presentación, o mandó el video de presentación sin presentar
                # (si el cliente pidió videos o fotos, es otro pedido: no se agrega), o está
                # cotizando fundas a medida sin haberlas presentado nunca.
                partes = self._presentacion_con_video(partes, contexto, pasos, detalle)
            for parte in partes:
                sesion.mandar("texto", parte)
            # Prueba del 21/11 (R20): el horario y la dirección tienen frase fija en el guion. Si el
            # cliente los preguntó y en este turno no salieron, van igual.
            for frase in self._frases_fijas_que_faltan(texto, bloques, sesion):
                for parte in partir_respuesta_f7(frase):
                    sesion.mandar("texto", parte)
                self.memoria[-1] = ("ai", (frase + "\n\n" + self.memoria[-1][1]).strip())
            # Corrección del 20/11 (campaña de pruebas): buscar_precio no repite una cotización que
            # ya mandó. Si por eso el turno iba a quedar en silencio, el cliente la pidió de nuevo:
            # se le vuelve a mandar.
            if not any(g.tipo != "saludo" for g in sesion.salientes) and precios.reenviar_repetida(contexto):
                detalle["cotizacion_reenviada"] = True
            if (not any(g.tipo != "saludo" for g in sesion.salientes)
                    and ("?" in texto or _RX_PREGUNTA_DEL_CLIENTE.search(_plano(texto)))
                    and contexto.segundos() <= TOPE_DERIVACION_SEGUNDOS):
                # Prueba del 21/11 (R16): preguntó cuánto le quedaba con el descuento y no recibió nada.
                # Una pregunta no puede quedar sin ninguna respuesta: pasa a Candela.
                detalle["derivacion_por_silencio"] = {
                    "motivo": MOTIVO_DERIVACION_CONTROL,
                    "resultado": derivacion.ejecutar(MOTIVO_DERIVACION_CONTROL, contexto),
                }
            if not any(g.tipo != "saludo" for g in sesion.salientes):
                detalle["nota"] = (
                    "El control de salida no dejó texto para mandar "
                    f"(motivo: {detalle['control']['final']['motivo']})."
                )
        return resultado()

    def _frases_fijas_que_faltan(self, texto: str, bloques: dict, sesion) -> list[str]:
        """Las frases del guion de dirección y horario que el cliente preguntó y este turno no dijo."""
        plano = _plano(texto)
        pide = {"ubicacion": bool(_RX_PREGUNTA_UBICACION.search(plano)), "horario": bool(_RX_PREGUNTA_HORARIO.search(plano))}
        dicho = " ".join(_plano(g.texto) for g in sesion.salientes)
        ya = {"ubicacion": "olivera" in dicho, "horario": "9 a 18" in dicho}
        return [frase for tipo, frase in frases_de_ubicacion_y_horario(bloques) if pide[tipo] and not ya[tipo]]

    def _material_pendiente(self, bloques: dict) -> str | None:
        """El pedido de fotos o video que quedó sin atender porque se hizo la pregunta del paso 1 bis.

        Campaña de multimedia del 21/11: el cliente pidió el video de tipo tapizado, recibió la
        pregunta de retapizar y, al contestarla, el pedido se perdió.
        """
        if len(self.memoria) < 2 or self.memoria[-1][0] != "ai" or self.memoria[-2][0] != "human":
            return None
        frases = frases_paso_1bis(bloques)
        if not frases or _plano(frases[0])[:40] not in _plano(self.memoria[-1][1]):
            return None
        anterior = self.memoria[-2][1]
        return anterior if clasificar_fase(anterior) == "multimedia" else None

    def _material_antes_de_cotizar(self, contexto, pasos: list, detalle: dict, raw: str) -> None:
        """Manda el material del producto antes de su primera cotización, si el modelo no lo hizo.

        Campaña de multimedia del 21/11: con tipo tapizado, alfombras y cubrevolante el agente
        cotizaba sin mostrar nada. No se manda si el cliente ya vio material de ese producto, si
        dijo que no lo quiere o si el modelo ya usó enviar_multimedia en este turno.
        """
        sesion = contexto.sesion
        if not any(g.tipo == "cotizacion" for g in sesion.salientes):
            return
        if any((p.get("action") or {}).get("tool") == "enviar_multimedia" for p in pasos):
            return
        if any(_RX_NO_QUIERE_MATERIAL.search(_plano(t)) for rol, t in self.memoria if rol == "human"):
            return
        cotizados = {
            item.get("producto")
            for p in pasos if (p.get("action") or {}).get("tool") == "buscar_precio"
            for item in ((p.get("observation") or {}).get("items") or [])
            if isinstance(item, dict) and item.get("estado") == "cotizado"
        }
        vistos = {r.get("asset_id") for r in sesion.multimedia_registrada if r.get("aceptado")}
        faltan = [p for p in PRODUCTOS_QUE_SE_MUESTRAN_AL_COTIZAR
                  if p in cotizados and not (multimedia.piezas_de_producto(p) & vistos)]
        # Paso 2 del guion: la presentación de las fundas a medida va una vez en la conversación.
        # Re-prueba del 21/11: después de ver colores y diseños (o el comparativo) el cliente pidió
        # el precio y salió la cotización sin que la presentación se hubiera hecho nunca.
        presentar = (
            "fundas" in cotizados and "tipo tapizado" not in cotizados and not _presenta_fundas(raw)
            and not any(_presenta_fundas(t) for rol, t in self.memoria[:-2] if rol == "ai")
        )
        if presentar:
            detalle["presentacion_automatica"] = True  # el texto lo agrega _presentacion_con_video
        solicitudes = [{"producto": p, "contenido": "presentacion"} for p in faltan]
        if (presentar or _presenta_fundas(raw)) and VIDEO_PRESENTACION_FUNDAS not in vistos:
            # La presentación de fundas va con su video: sale en este mismo pedido.
            solicitudes.insert(0, {"producto": "fundas", "contenido": "presentacion", "formato": "video"})
        if not solicitudes or not (faltan or presentar):
            return
        antes = len(sesion.salientes)
        dato = multimedia.ejecutar(solicitudes, contexto)
        nuevos = sesion.salientes[antes:]
        del sesion.salientes[antes:]
        donde = next(i for i, g in enumerate(sesion.salientes) if g.tipo == "cotizacion")
        sesion.salientes[donde:donde] = nuevos
        if faltan:
            detalle["material_automatico"] = {"productos": faltan, "estado": dato.get("estado")}

    def _tapizado_pendiente(self, texto: str, bloques: dict, sesion=None) -> bool:
        """¿El lote nombra tapizar o tapizado y todavía no se hizo ninguna frase del paso 1 bis?

        Mira solo el lote de este turno: si el agente ya preguntó (o ya pasó a la
        pregunta del taller o a ofrecer fundas), el paso está resuelto.
        """
        if not nombra_tapizado(texto):
            return False
        # Re-prueba del 21/11: si ya vio el video comparativo, «tipo tapizado» es una de las dos fundas.
        if sesion is not None and any(
            r.get("asset_id") == VIDEO_COMPARATIVO and r.get("aceptado") for r in sesion.multimedia_registrada
        ):
            return False
        marcas = [_plano(f)[:40] for f in frases_paso_1bis(bloques)]
        if not marcas:
            return False
        dicho = [_plano(t) for rol, t in self.memoria if rol == "ai"]
        return not any(marca and marca in d for marca in marcas for d in dicho)

    def _presentacion_con_video(self, partes: list[str], contexto, pasos: list, detalle: dict) -> list[str]:
        """Pedido de Mateo (17/11): con la presentación de las fundas va el video de presentación.

        Orden: la presentación, el video y recién después lo demás (la pregunta de
        envío o la cotización). Si el agente no pidió el video, lo manda el código;
        si el agente mandó el video sin escribir la presentación, o el control la
        borró (hubo cotización en el mismo turno), la presentación se manda igual.
        Devuelve el texto que falta mandar después.
        """
        sesion = contexto.sesion
        presentacion = [p for p in partes if _es_parte_de_presentacion(p)]
        resto = [p for p in partes if not _es_parte_de_presentacion(p)]
        if not presentacion:
            presentacion = partir_respuesta_f7(PRESENTACION_FUNDAS)
            # Que la memoria también sepa que ya se presentó (va una sola vez).
            self.memoria[-1] = ("ai", PRESENTACION_FUNDAS + "\n\n" + self.memoria[-1][1])

        pidio_multimedia = any((p.get("action") or {}).get("tool") == "enviar_multimedia" for p in pasos)
        ya_mandado = any(r.get("asset_id") == VIDEO_PRESENTACION_FUNDAS for r in sesion.multimedia_registrada)
        if not pidio_multimedia and not ya_mandado:
            dato = multimedia.ejecutar(
                [{"producto": "fundas", "contenido": "presentacion", "formato": "video"}], contexto)
            detalle["video_presentacion_automatico"] = {"estado": dato.get("estado"),
                                                       "aceptados": dato.get("aceptados")}

        # Lo que ya salió en este turno (saludo, video, cotización) se reordena:
        # saludo, presentación, lo de las herramientas, y después el resto del texto.
        saludo = [g for g in sesion.salientes if g.tipo == "saludo"]
        herramientas = [g for g in sesion.salientes if g.tipo != "saludo"]
        sesion.salientes[:] = saludo
        for parte in presentacion:
            sesion.mandar("texto", parte)
        sesion.salientes.extend(herramientas)
        return resto

    def modelo_invoke(self, modelo, mensajes):
        """Una llamada al modelo (aparte para poder espiarla en las pruebas)."""
        return modelo.invoke(mensajes)
