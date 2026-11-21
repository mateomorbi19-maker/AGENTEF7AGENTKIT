"""Lo que en producción hacen Chatwoot y Postgres, para la web de pruebas.

En n8n, las herramientas de F7 mandan sus propios mensajes a Chatwoot: la
cotización, las fotos y los videos, y la confirmación del pase. Además anotan
en Postgres lo que ya mandaron.

En la web de pruebas no hay Chatwoot ni Postgres. Todo eso pasa acá, en
memoria. Lo que «se manda» queda en `salientes`, y la web lo muestra como lo
vería el cliente.

Este archivo es el contrato que comparten las herramientas y el turno:
- Cada herramienta recibe el argumento del modelo y un `ContextoTurno`, que
  el modelo no ve.
- Cada herramienta devuelve el mismo objeto JSON que devuelve hoy su
  subflujo de n8n.
- Lo que la herramienta le mandaría al cliente lo deja con
  `contexto.sesion.mandar(...)`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

# F7 atiende solo la cuenta 1 de Chatwoot. Las herramientas validan este
# número igual que en n8n.
ACCOUNT_ID = 1


@dataclass
class Globo:
    """Un mensaje que le llegaría al cliente por WhatsApp.

    tipo:
      "texto"      → lo que escribe el agente (ya controlado y partido)
      "saludo"     → el saludo fijo del primer mensaje
      "cotizacion" → la cotización que manda buscar_precio
      "multimedia" → una foto o un video que manda enviar_multimedia
      "derivacion" → la confirmación fija del pase a Candela
      "borrar"     → la confirmación del comando «borrar»
    """

    tipo: str
    texto: str = ""
    datos: dict = field(default_factory=dict)
    chatwoot_message_id: int = 0


@dataclass
class SesionLocal:
    """Una conversación de la web de pruebas: lo que en producción es Chatwoot + Postgres."""

    conversation_id: int = 1
    # La época de «borrar»: el id del último mensaje «borrar» (0 si nunca hubo).
    epoca: int = 0
    # Las etiquetas de la conversación en Chatwoot. «humano» calla al bot.
    etiquetas: list[str] = field(default_factory=list)
    # Lo que en producción sale de f7_multimedia_envios para el prompt
    # (MULTIMEDIA REGISTRADA): una fila por pieza, con las claves que espera
    # resumirMultimedia: asset_id, version, aceptado (bool),
    # hay_envio_incierto (bool). Se vacía con «borrar».
    multimedia_registrada: list[dict] = field(default_factory=list)
    # Los registros de cada herramienta (lo que en n8n son sus tablas de
    # Postgres), por herramienta y por solicitud_id:
    #   registros["precios"]["cw:1:1:7:precios-v1"] = {...}
    registros: dict[str, dict[str, dict]] = field(default_factory=dict)
    # Lo que «se mandó» al cliente. El turno lo vacía al empezar y la web lo
    # muestra al terminar.
    salientes: list[Globo] = field(default_factory=list)
    _ultimo_message_id: int = 0

    def nuevo_message_id(self) -> int:
        """Un id nuevo, como los de Chatwoot: entrantes y salientes comparten la cuenta."""
        self._ultimo_message_id += 1
        return self._ultimo_message_id

    def mandar(self, tipo: str, texto: str = "", **datos) -> Globo:
        """Manda un mensaje al cliente (acá: lo deja para que la web lo muestre).

        Devuelve el globo con su `chatwoot_message_id`, que las herramientas
        usan igual que el id que devuelve Chatwoot cuando acepta un mensaje.
        """
        globo = Globo(tipo, texto, dict(datos), self.nuevo_message_id())
        self.salientes.append(globo)
        return globo

    def registro(self, herramienta: str) -> dict[str, dict]:
        """La «tabla» de una herramienta: solicitud_id → lo que guardó."""
        return self.registros.setdefault(herramienta, {})


@dataclass
class ContextoTurno:
    """Lo que el código le agrega a cada herramienta y el modelo no ve.

    En n8n son account_id, conversation_id, solicitud_id y modo, más
    modalidad_confirmada en precios.
    """

    sesion: SesionLocal
    # El id del último mensaje del cliente en este turno (del lote).
    ultimo_message_id: int
    # La modalidad que calculó el principal: "caba", "envio" o "sin_confirmar".
    modalidad_confirmada: str = "sin_confirmar"
    # En producción el principal siempre pide "enviar". Acá también: lo que
    # cambia es a dónde va lo mandado (a la web en vez de a Chatwoot).
    modo: str = "enviar"
    # Cuándo arrancó el turno, para los topes de tiempo de las herramientas.
    inicio: float = field(default_factory=time.monotonic)
    # Si el cliente pidió fotos o videos en este mensaje. Si no los pidió, no se
    # reenvía material que ya se mandó en la conversación (pedido de Mateo, 17/11).
    pidio_multimedia: bool = True
    # Decisión de Mateo del 21/11 (campaña de multimedia): si piden fotos, va el video. Para eso
    # enviar_multimedia necesita saber qué pidió el cliente en este lote (fotos, video) y si avisó
    # en la conversación que no puede ver videos.
    pidio_fotos: bool = False
    pidio_video: bool = False
    sin_video: bool = False
    # Re-prueba del 21/11. Nombrar un video («se ve en algún video?») no es pedir que lo manden de
    # nuevo: con esto en True lo ya mandado se reenvía solo si el modelo marca reenvio_solicitado.
    reenvio_solo_marcado: bool = False
    # El producto del pedido de material que quedó pendiente por la pregunta del paso 1 bis.
    producto_pendiente: str | None = None
    # Prueba del 21/11: lo que escribió el cliente en este turno. buscar_precio lo usa solo para
    # saber qué cabina nombró («es 2020 doble cabina») cuando el modelo no la pasa.
    texto_cliente: str = ""

    @property
    def account_id(self) -> int:
        return ACCOUNT_ID

    @property
    def conversation_id(self) -> int:
        return self.sesion.conversation_id

    def solicitud_id(self, sufijo: str) -> str:
        """cw:1:<conversación>:<último message_id del lote>:<sufijo>, como en n8n."""
        return f"cw:{ACCOUNT_ID}:{self.conversation_id}:{self.ultimo_message_id}:{sufijo}"

    def segundos(self) -> float:
        """Cuánto pasó desde que arrancó el turno."""
        return time.monotonic() - self.inicio
