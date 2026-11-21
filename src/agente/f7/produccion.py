"""El agente de F7 atendiendo de verdad: una conversación de Chatwoot por vez.

    lo guardado de esa conversación → las etiquetas de Chatwoot → el turno
    (turno.py, el mismo de la web de pruebas) → guardar → mandar por Chatwoot

Lo que cambia respecto de la web de pruebas es de dónde sale la conversación
(de la base, no de la memoria del proceso) y a dónde va lo que se manda (a
Chatwoot, no a la pantalla).

**Se manda todo al final, en el orden en que quedó.** El turno reordena lo que
arma: la presentación va antes de su video, el material antes de la cotización.
Mandarlo a medida que sale sería mandarlo en otro orden que el que se probó.
Y tiene una ventaja: si el turno falla a mitad de camino, no salió nada y no
se guardó nada. Para el cliente y para la memoria, ese turno no existió.

**El pase a Candela y «borrar» se hacen en Chatwoot al llegar a su mensaje**:
primero la etiqueta, abrir y asignar (o sacar la etiqueta), y recién después
la confirmación.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path
from typing import Callable

from .estado import desempaquetar, empaquetar
from .local import Globo, SesionLocal
from .multimedia.seleccion import cargar_catalogo
from .prompt import RUTA_PROMPT, leer_bloques
from .turno import AgenteF7, ResultadoTurno, _es_humano

registro = logging.getLogger("agente.f7.produccion")

# En n8n, 2 segundos fijos entre un mensaje y el siguiente (también entre fotos).
PAUSA_ENTRE_MENSAJES = 2.0


class ErrorDeTurnoF7(Exception):
    """El turno no se pudo completar (el modelo, la planilla, el código). No salió ni se guardó nada."""


class ErrorDeEntrega(Exception):
    """El turno se completó y se guardó, pero Chatwoot no aceptó algo de lo que había que mandar."""

    # El servidor lo mira para decir, en el aviso, que el problema es de Chatwoot y no del modelo.
    de_chatwoot = True


class ErrorDeArranque(Exception):
    """Falta algo sin lo cual no se puede atender. Se avisa al arrancar, no con un cliente esperando."""


def piezas_con_problemas(carpeta: Path | str | None) -> list[str]:
    """Las fotos y videos del catálogo que no están en la carpeta o no son los del catálogo."""
    if not carpeta:
        return ["no hay carpeta de fotos y videos (F7_MEDIA_DIR)"]
    carpeta = Path(carpeta)
    problemas = []
    for pieza in cargar_catalogo().get("assets", []):
        if not pieza.get("habilitado", True):
            continue
        nombre = pieza["nombre_archivo"]
        ruta = carpeta / nombre
        if not ruta.is_file():
            problemas.append(f"{pieza['id']}: falta {nombre}")
            continue
        datos = ruta.read_bytes()
        if len(datos) != pieza.get("bytes") or hashlib.sha256(datos).hexdigest() != pieza.get("sha256"):
            problemas.append(f"{pieza['id']}: {nombre} no es el archivo del catálogo")
    return problemas


class AtencionF7:
    """Atiende las conversaciones de F7 que entran por Chatwoot.

    `canal`    el ChatwootF7 (canal.py)
    `almacen`  dónde se guarda cada conversación (estado.py)
    `modelo`   un modelo ya armado (las pruebas pasan uno falso); si no, se arma con `config`
    `dormir`   la espera entre mensajes (las pruebas la anotan en vez de esperar)
    """

    def __init__(
        self,
        canal,
        almacen,
        *,
        config=None,
        modelo=None,
        leer_hojas=None,
        ruta_prompt: Path | str | None = None,
        carpeta_media: Path | str | None = None,
        pausa: float = PAUSA_ENTRE_MENSAJES,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.canal = canal
        self.almacen = almacen
        self.config = config
        self._modelo = modelo
        self.leer_hojas = leer_hojas
        self.ruta_prompt = Path(ruta_prompt) if ruta_prompt else RUTA_PROMPT
        self.carpeta_media = Path(carpeta_media) if carpeta_media else None
        self.pausa = pausa
        self._dormir = dormir
        # Cuántas veces llegó «borrar» a cada conversación. Un turno que arrancó
        # antes del último «borrar» ya no vale: ni se guarda ni se manda.
        self._cortes: dict[str, int] = {}
        self._candado = threading.Lock()
        # Cómo salió la lectura de la planilla de precios al arrancar (lo muestra el /salud).
        self.estado_de_la_planilla = "sin revisar"

    # -- Al arrancar -------------------------------------------------------------

    def revisar(self) -> None:
        """Lo que tiene que estar antes de atender a nadie. Si falta algo, falla acá."""
        try:
            self.almacen.preparar()
            self.almacen.probar()
        except Exception as e:
            raise ErrorDeArranque(
                "No se pudo usar la base donde se guardan las conversaciones "
                f"({type(e).__name__}: {e}). En el servidor, revisá POSTGRES_DSN."
            ) from e
        try:
            leer_bloques(self.ruta_prompt)
        except Exception as e:
            raise ErrorDeArranque(f"No se pudo leer el guion de F7 ({self.ruta_prompt}): {e}") from e
        problemas = piezas_con_problemas(self.carpeta_media)
        if problemas:
            raise ErrorDeArranque(
                f"Faltan fotos o videos del catálogo en «{self.carpeta_media}»: " + "; ".join(problemas)
            )

    def revisar_planilla(self) -> str:
        """Lee la planilla de precios una vez, al arrancar.

        Si el servidor no llega a Google o alguien le cambió el nombre a una
        hoja, mejor saberlo ya y no con un cliente pidiendo precio. No impide
        arrancar (lo demás funciona): queda avisado en el registro y en el /salud.
        """
        from .precios import planilla

        leer = self.leer_hojas or planilla.leer_hojas
        try:
            leer(list(planilla.HOJAS))
            self.estado_de_la_planilla = "ok"
        except Exception as e:
            self.estado_de_la_planilla = f"error: {e}"
            registro.error(
                "No se pudo leer la planilla de precios (%s): el agente no va a poder cotizar hasta que se arregle.",
                e,
            )
        return self.estado_de_la_planilla

    # -- «borrar» ---------------------------------------------------------------

    def pedir_corte(self, conversacion: str) -> None:
        """Llegó «borrar»: lo que esa conversación tenga a medio hacer ya no sale."""
        with self._candado:
            self._cortes[str(conversacion)] = self._cortes.get(str(conversacion), 0) + 1

    def _corte(self, conversacion: str) -> int:
        return self._cortes.get(conversacion, 0)

    def corte_actual(self, conversacion: str) -> int:
        """El número de «borrar» que lleva la conversación. El servidor lo anota cuando un lote
        sale de la ráfaga, para que no se conteste si antes de que le toque llega un «borrar»."""
        return self._corte(str(conversacion))

    def olvidar(self, conversacion: str) -> None:
        """Borra lo guardado de una conversación (para volver a probar desde cero)."""
        self.almacen.olvidar(str(conversacion))

    # -- Un turno ----------------------------------------------------------------

    def preparar_modelo(self) -> None:
        """Arma el modelo, una sola vez: lo comparten todas las conversaciones.

        El servidor lo llama al arrancar. Armarlo tarda unos segundos (le
        pregunta al proveedor el tope de respuesta del modelo): mejor ahí que
        con el primer cliente esperando.
        """
        if self._modelo is None:
            with self._candado:
                if self._modelo is None:
                    self._modelo = AgenteF7(config=self.config).modelo

    def _agente(self, sesion: SesionLocal, memoria: list) -> AgenteF7:
        self.preparar_modelo()
        agente = AgenteF7(
            self._modelo, config=self.config, leer_hojas=self.leer_hojas, ruta_prompt=self.ruta_prompt
        )
        agente.sesion, agente.memoria = sesion, memoria
        return agente

    def atender(self, conversacion: str, texto: str, corte: int | None = None) -> ResultadoTurno:
        """Un lote del cliente, de punta a punta. Bloquea: el servidor lo corre en un hilo aparte.

        `corte` es lo que devolvió `corte_actual` cuando el lote salió de la ráfaga
        (si no se pasa, se toma ahora).

        Lanza ErrorDeTurnoF7 si el turno no se pudo completar (no salió nada) y
        ErrorDeEntrega si Chatwoot no aceptó algo de lo que había que mandar.
        """
        conversacion = str(conversacion)
        if corte is None:
            corte = self._corte(conversacion)
        elif corte != self._corte(conversacion):
            registro.info("[%s] llegó «borrar» antes de que le tocara: no se contesta", conversacion)
            return ResultadoTurno([], {
                "lote": texto, "accion": "descartado_por_borrar",
                "nota": "Llegó «borrar» antes de que a este lote le tocara: no se contestó.",
            })

        guardado = self.almacen.cargar(conversacion)
        numero = int(conversacion)
        if guardado:
            sesion, memoria = desempaquetar(guardado, numero)
        else:
            sesion, memoria = SesionLocal(conversation_id=numero), []
        # La verdad sobre «humano» está en Chatwoot. Si no se puede leer, no se contesta.
        sesion.etiquetas[:] = self.canal.etiquetas(conversacion)
        tenia_humano = any(_es_humano(e) for e in sesion.etiquetas)

        agente = self._agente(sesion, memoria)
        resultado = agente.responder(texto)
        if resultado.error:
            # No se guarda ni se manda nada, pero queda anotado: es lo que se mira después.
            self._anotar(conversacion, resultado, {"enviados": [], "sin_envio": "error"})
            raise ErrorDeTurnoF7(resultado.error)

        accion = resultado.detalle.get("accion")
        if accion == "silencio_humano":
            registro.info("[%s] tiene «humano»: no contesto", conversacion)
            return resultado
        if accion != "borrar" and self._corte(conversacion) != corte:
            registro.info("[%s] llegó «borrar» mientras pensaba: el turno se descarta", conversacion)
            resultado.detalle["nota"] = "Llegó «borrar» mientras el agente pensaba: el turno se descartó."
            return resultado

        self.almacen.guardar(conversacion, empaquetar(sesion, agente.memoria))
        entrega: dict = {"enviados": [], "sin_envio": ""}
        try:
            self._entregar(conversacion, resultado, sesion, tenia_humano, corte, entrega)
        finally:
            self._anotar(conversacion, resultado, entrega)
        return resultado

    # -- Mandar lo que dejó el turno ------------------------------------------------

    def _entregar(self, conversacion, resultado, sesion, tenia_humano, corte, entrega) -> None:
        globos = resultado.globos
        es_borrar = resultado.detalle.get("accion") == "borrar"
        # El turno pasó la charla a Candela si la etiqueta apareció durante el turno.
        derivo = not tenia_humano and any(_es_humano(e) for e in sesion.etiquetas)
        if not globos and not derivo:
            return
        try:
            # ¿La tomó una persona mientras el modelo pensaba? El pase de este turno todavía
            # no está en Chatwoot: si la etiqueta ya figura ahí, la puso otro.
            if not es_borrar and any(_es_humano(e) for e in self.canal.etiquetas(conversacion)):
                entrega["sin_envio"] = "humano"
                registro.info("[%s] le pusieron «humano» mientras pensaba: no mando nada", conversacion)
                return

            pase_hecho = False
            mandados = 0
            # La foto o el video que acaba de salir y todavía no se sabe si llegó.
            en_camino: tuple[int, dict] | None = None
            confirmar_entregas = True
            for globo in globos:
                if self._corte(conversacion) != corte:
                    entrega["sin_envio"] = "borrar"
                    registro.info("[%s] llegó «borrar»: no mando lo que faltaba", conversacion)
                    return
                if globo.tipo == "borrar":
                    self.canal.quitar_humano(conversacion)
                elif globo.tipo == "derivacion":
                    pase_hecho = True
                    if not self.canal.derivar(conversacion):
                        # Quedó pausado pero no asignado a Candela: no se le afirma al cliente.
                        entrega["enviados"].append(
                            {"tipo": globo.tipo, "chatwoot_id": None, "nota": "pase sin confirmar: no se avisó"}
                        )
                        continue
                if globo.tipo != "multimedia" and not globo.texto.strip():
                    continue
                if en_camino is not None:
                    # WhatsApp entrega un video bastante después que un texto: si lo que sigue
                    # sale sin esperar, al cliente le llega antes (la cotización antes que el video).
                    if confirmar_entregas:
                        llego = self.canal.esperar_entrega(conversacion, en_camino[0], dormir=self._dormir)
                        en_camino[1]["entrega"] = llego
                        if llego == "sin_confirmar":
                            # Chatwoot no está informando entregas: no se pierde ese rato otra vez.
                            confirmar_entregas = False
                    en_camino = None
                if mandados:
                    self._dormir(self.pausa)
                ident = self._mandar(conversacion, globo)
                mandados += 1
                ficha = {"tipo": globo.tipo, "chatwoot_id": ident}
                if globo.tipo == "multimedia":
                    ficha["asset_id"] = globo.datos.get("asset_id")
                    if ident is not None:
                        en_camino = (ident, ficha)
                entrega["enviados"].append(ficha)

            if derivo and not pase_hecho:
                # El turno pausó al agente sin dejar confirmación: el pase se hace igual.
                self.canal.derivar(conversacion)
            registro.info("[%s] -> %s mensaje(s)", conversacion, mandados)
        except ErrorDeEntrega:
            raise
        except Exception as e:
            raise ErrorDeEntrega(f"{type(e).__name__}: {e}") from e

    def _mandar(self, conversacion: str, globo: Globo) -> int | None:
        if globo.tipo != "multimedia":
            return self.canal.enviar_texto(conversacion, globo.texto)
        nombre = str(globo.datos.get("nombre_archivo") or "")
        if self.carpeta_media is None or not nombre or Path(nombre).name != nombre:
            raise ErrorDeEntrega(f"No se puede mandar la pieza {globo.datos.get('asset_id')}: falta su archivo.")
        return self.canal.enviar_archivo(
            conversacion,
            self.carpeta_media / nombre,
            nombre,
            str(globo.datos.get("mime") or "application/octet-stream"),
        )

    def _anotar(self, conversacion: str, resultado: ResultadoTurno, entrega: dict) -> None:
        """El detalle del turno, para poder mirar después por qué contestó lo que contestó."""
        try:
            self.almacen.anotar_turno(
                conversacion,
                {**resultado.detalle, "entrega": entrega["enviados"], "sin_envio": entrega["sin_envio"]},
            )
        except Exception as e:  # que no se pueda anotar no puede voltear la respuesta
            registro.error("[%s] no se pudo anotar el turno: %s", conversacion, e)

    # -- Para el /salud del servidor --------------------------------------------------

    def salud(self) -> dict:
        """Lo que el /salud dice de F7: sirve para ver, desde afuera, qué quedó desplegado."""
        from .prompt import PROMPT_VERSION

        return {
            "agente": "f7",
            "prompt": PROMPT_VERSION,
            "bandeja": getattr(self.canal, "bandeja_id", "") or "todas",
            "planilla": self.estado_de_la_planilla,
            "fotos_y_videos": sum(1 for p in cargar_catalogo().get("assets", []) if p.get("habilitado", True)),
        }
