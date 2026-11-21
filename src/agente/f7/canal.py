"""El canal de Chatwoot con lo que F7 necesita y el kit no trae.

El kit sabe recibir, contestar texto y poner la etiqueta del traspaso. F7 además:

- atiende una sola bandeja (la del WhatsApp de F7): la cuenta tiene otra, de pruebas;
- deja pasar «borrar» aunque la charla esté con «humano»: es lo que la reactiva;
- manda fotos y videos como adjuntos, sin pie de foto;
- al pasar la charla a Candela la abre y se la asigna, además de la etiqueta;
- al borrar, saca solo la etiqueta «humano».

Las llamadas son las mismas que hacía n8n (ver referencia-f7/logica).
"""

from __future__ import annotations

import json
import logging
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..canales.adjuntos import adjuntos_de
from ..canales.base import MensajeEntrante
from ..canales.chatwoot import _ABRIDOR, Chatwoot, ErrorDeChatwoot
from .derivacion import motor
from .textos import es_comando_borrar

registro = logging.getLogger("agente.f7.canal")

# Subir un video de varios MB tarda bastante más que una llamada común.
ESPERA_DE_SUBIDA = 120

_SALTO = bytes([13, 10])  # el salto de línea de un formulario HTTP

# Cómo informa Chatwoot el estado de un mensaje que salió: con la palabra o, según la versión, con el número.
_ESTADOS_DE_ENTREGA = {0: "sent", 1: "delivered", 2: "read", 3: "failed"}


def _id_de(respuesta) -> int | None:
    valor = respuesta.get("id") if isinstance(respuesta, dict) else None
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _limpio(valor: str) -> str:
    """Un nombre que va adentro de una cabecera: sin comillas ni saltos."""
    return "".join(c for c in str(valor) if c != '"' and ord(c) >= 32)


class ChatwootF7(Chatwoot):
    """La bandeja de WhatsApp de F7."""

    def __init__(
        self,
        url: str,
        token: str,
        cuenta_id: str | int,
        etiqueta_humano: str = "humano",
        bandeja_id: str | int | None = None,
        destino_id: int = motor.DESTINO_ID,
    ) -> None:
        super().__init__(url=url, token=token, cuenta_id=cuenta_id, etiqueta_humano=etiqueta_humano)
        # La bandeja que se atiende. Vacío = todas las de la cuenta.
        self.bandeja_id = str(bandeja_id or "").strip()
        # A quién se le asigna la charla en un pase: Candela (usuario 3 de Chatwoot).
        self.destino_id = destino_id

    # -- Entrada ---------------------------------------------------------------

    def es_borrar(self, mensaje: MensajeEntrante) -> bool:
        """Si el mensaje entero es el comando «borrar». Tiene que ser texto escrito, sin adjuntos."""
        evento = mensaje.datos if isinstance(mensaje.datos, dict) else {}
        return es_comando_borrar(mensaje.texto) and not adjuntos_de(evento)

    def deberia_responder(self, mensaje: MensajeEntrante) -> bool:
        evento = mensaje.datos if isinstance(mensaje.datos, dict) else {}
        if not self._es_de_esta_cuenta(evento) or not self._es_de_la_bandeja(evento):
            return False
        return super().deberia_responder(mensaje)

    def _es_de_esta_cuenta(self, evento: dict) -> bool:
        cuenta = evento.get("account")
        valor = cuenta.get("id") if isinstance(cuenta, dict) else evento.get("account_id")
        return valor is None or str(valor) == self.cuenta_id

    def _es_de_la_bandeja(self, evento: dict) -> bool:
        if not self.bandeja_id:
            return True
        bandeja = evento.get("inbox")
        valor = bandeja.get("id") if isinstance(bandeja, dict) else None
        if valor is None:
            conversacion = evento.get("conversation")
            valor = conversacion.get("inbox_id") if isinstance(conversacion, dict) else None
        # Igual que hoy en n8n: si el evento no dice de qué bandeja es, pasa.
        return valor is None or str(valor) == self.bandeja_id

    def _la_atiende_una_persona(self, evento: dict) -> bool:
        # «borrar» pasa aunque esté «humano»: saca la etiqueta y reactiva al agente.
        contenido = evento.get("content")
        if isinstance(contenido, str) and es_comando_borrar(contenido.strip()) and not adjuntos_de(evento):
            return False
        return super()._la_atiende_una_persona(evento)

    # -- Etiquetas ---------------------------------------------------------------

    def etiquetas(self, conversacion: str) -> list[str]:
        """Las etiquetas de la conversación, ahora. Si Chatwoot no contesta, falla (no se adivina)."""
        respuesta = self._api("GET", f"conversations/{conversacion}/labels")
        return [str(e) for e in respuesta.get("payload") or []]

    def quitar_humano(self, conversacion: str) -> None:
        """Saca solo la etiqueta «humano»: las demás quedan, y la charla sigue asignada a quien estaba."""
        actuales = self.etiquetas(conversacion)
        resto = [e for e in actuales if e.strip().lower() != self.etiqueta_humano]
        if len(resto) != len(actuales):
            self._api("POST", f"conversations/{conversacion}/labels", {"labels": resto})

    # -- El pase a Candela ---------------------------------------------------------

    def derivar(self, conversacion: str) -> bool:
        """Pasa la charla a Candela: «humano» → abierta → asignada a ella.

        Ese orden importa: al abrir, Chatwoot puede autoasignar a otra persona,
        así que la asignación va al final. Si la etiqueta no se puede poner,
        falla (el agente seguiría hablando). Devuelve True solo si al final la
        charla quedó asignada a Candela: recién ahí se le puede decir al cliente.
        """
        super().pasar_a_persona(conversacion)
        try:
            self._api("POST", f"conversations/{conversacion}/toggle_status", {"status": "open"})
            self._api("POST", f"conversations/{conversacion}/assignments", {"assignee_id": self.destino_id})
            datos = self._api("GET", f"conversations/{conversacion}")
        except Exception as e:  # el bot ya quedó pausado: lo que falta es la asignación
            registro.error("[%s] quedó con «humano» pero no se pudo asignar: %s", conversacion, e)
            return False
        meta = datos.get("meta") if isinstance(datos, dict) else None
        asignado = ((meta or {}).get("assignee") or {}).get("id")
        if asignado != self.destino_id:
            registro.error("[%s] quedó con «humano» pero asignada a %s", conversacion, asignado)
            return False
        return True

    def pasar_a_persona(self, conversacion: str) -> None:
        """Lo que usa el servidor cuando algo falla: en F7, «una persona» es Candela."""
        self.derivar(conversacion)

    # -- Salida ----------------------------------------------------------------

    def enviar_texto(self, conversacion: str, texto: str) -> int | None:
        """Un mensaje de texto al cliente. Devuelve el id que le puso Chatwoot."""
        return _id_de(self._api(
            "POST",
            f"conversations/{conversacion}/messages",
            {"content": texto, "message_type": "outgoing", "private": False},
        ))

    def enviar_archivo(self, conversacion: str, ruta: Path | str, nombre: str, mime: str) -> int | None:
        """Una foto o un video al cliente, sin texto. Devuelve el id que le puso Chatwoot."""
        return _id_de(self._subir(
            f"conversations/{conversacion}/messages",
            {"message_type": "outgoing", "private": "false"},
            ("attachments[]", nombre, mime, Path(ruta).read_bytes()),
        ))

    def esperar_entrega(self, conversacion: str, id_mensaje, intentos: int = 10, cada: float = 1.5,
                        dormir=time.sleep) -> str:
        """Espera a que WhatsApp confirme que un mensaje llegó al teléfono del cliente.

        Un video tarda varios segundos en entregarse y un texto, casi nada: si
        después de un video se manda el texto que sigue sin esperar, al cliente
        le llegan al revés. Devuelve «entregado», «fallido» o «sin_confirmar»
        (se cansó de preguntar: unos 15 segundos).
        """
        for intento in range(intentos):
            if intento:
                dormir(cada)
            try:
                mensaje = self.mensaje(conversacion, id_mensaje)
            except Exception:
                mensaje = None
            estado = (mensaje or {}).get("status")
            if isinstance(estado, int) and not isinstance(estado, bool):
                estado = _ESTADOS_DE_ENTREGA.get(estado)
            estado = str(estado or "").strip().lower()
            if estado in ("delivered", "read"):
                return "entregado"
            if estado == "failed":
                return "fallido"
        return "sin_confirmar"

    def _subir(self, camino: str, campos: dict[str, str], archivo: tuple[str, str, str, bytes]) -> dict:
        """Un POST con formulario (multipart): es como Chatwoot recibe los adjuntos.

        No se reintenta: si se corta a mitad de camino, el mensaje puede haber
        salido igual, y reintentar sería mandarlo dos veces.
        """
        limite = "f7" + secrets.token_hex(16)
        borde = b"--" + limite.encode("ascii")
        partes = []
        for clave, valor in campos.items():
            partes += [
                borde, _SALTO,
                f'Content-Disposition: form-data; name="{_limpio(clave)}"'.encode("utf-8"), _SALTO, _SALTO,
                str(valor).encode("utf-8"), _SALTO,
            ]
        campo, nombre, mime, datos = archivo
        partes += [
            borde, _SALTO,
            f'Content-Disposition: form-data; name="{_limpio(campo)}"; filename="{_limpio(nombre)}"'.encode("utf-8"),
            _SALTO,
            f"Content-Type: {_limpio(mime)}".encode("utf-8"), _SALTO, _SALTO,
            datos, _SALTO,
            borde, b"--", _SALTO,
        ]
        pedido = urllib.request.Request(
            f"{self.url}/api/v1/accounts/{self.cuenta_id}/{camino}",
            data=b"".join(partes),
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={limite}",
                "api_access_token": self.token,
            },
        )
        try:
            with _ABRIDOR.open(pedido, timeout=ESPERA_DE_SUBIDA) as respuesta:
                cuerpo = respuesta.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:300]
            raise ErrorDeChatwoot(
                f"Chatwoot devolvió {e.code} al subir un archivo en {camino}: {detalle}"
            ) from None
        return json.loads(cuerpo) if cuerpo else {}
