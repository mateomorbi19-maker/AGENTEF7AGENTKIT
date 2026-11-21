"""Lo que F7 lee de un mensaje que no es solo texto.

El lector del kit le cuenta al agente todo lo que llega («[La persona mandó una
foto…]», «[Respondiendo a…]»). F7 no: hace lo mismo que hacía n8n.

- Un audio se transcribe y entra como si el cliente lo hubiera escrito, sin
  agregados. El turno de F7 mira el texto del cliente para decidir cosas (si
  pidió fotos, si eligió envío o taller): una nota entre corchetes lo confundiría.
- Una foto, un video, un archivo o una ubicación no se leen: con texto, cuenta
  el texto; sin texto, el mensaje se deja pasar sin contestar.
- Un mensaje citado tampoco se agrega: cuenta lo que escribió.

Si un audio no se puede escuchar (falta la clave de OpenAI o falló), la charla
pasa a una persona en vez de quedar sin respuesta.
"""

from __future__ import annotations

import logging

from ..canales.adjuntos import (
    MAXIMO_DE_ADJUNTOS,
    TOPE_AUDIO,
    Lector,
    Leido,
    _limpio,
    _nombre_del_archivo,
    adjuntos_de,
)
from ..canales.base import MensajeEntrante

registro = logging.getLogger("agente.f7.lector")


class LectorF7(Lector):
    """El lector de adjuntos para F7: solo lo escrito y los audios."""

    def leer(self, mensaje: MensajeEntrante) -> Leido:
        evento = mensaje.datos or {}
        partes: list[str] = []
        a_una_persona = ""
        errores: list[str] = []

        for adjunto in adjuntos_de(evento)[:MAXIMO_DE_ADJUNTOS]:
            if str(adjunto.get("file_type") or "").strip().lower() != "audio":
                continue
            if self.transcribir is None:
                a_una_persona = a_una_persona or "llegó un audio y no hay cómo escucharlo (falta OPENAI_API_KEY)"
                continue
            try:
                datos, tipo = self._bajar(adjunto, mensaje.conversacion, evento.get("id"), TOPE_AUDIO)
                dicho = _limpio(self.transcribir(datos, tipo, _nombre_del_archivo(adjunto) or "audio.ogg"))
            except Exception as e:
                registro.warning("[%s] no se pudo escuchar un audio: %s", mensaje.conversacion, e)
                a_una_persona = a_una_persona or "llegó un audio y no se pudo escuchar"
                errores.append(f"No se pudo escuchar un audio: {type(e).__name__}: {e}")
                continue
            if dicho:
                partes.append(dicho)

        if mensaje.texto:
            partes.append(mensaje.texto)

        # Si hay que pasarla a una persona, el agente no contesta nada de este mensaje.
        texto = "" if a_una_persona else "\n".join(partes)
        return Leido(texto, a_una_persona=a_una_persona, error="; ".join(errores))
