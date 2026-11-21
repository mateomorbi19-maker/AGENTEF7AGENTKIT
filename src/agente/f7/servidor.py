"""El servidor de WhatsApp con el agente de F7 adentro.

`webhook_chatwoot.py` llama a `crear_app_f7` cuando la configuración dice
AGENTE=f7. Arma las cuatro piezas propias de F7 y se las pasa al servidor del kit:

    el canal (canal.py) · dónde se guarda cada conversación (estado.py)
    quién atiende (produccion.py) · cómo se leen los audios (lector.py)

Antes de devolver el servidor revisa que esté todo: la base, el guion y las
fotos y videos. Si falta algo no arranca, y dice qué falta.

Variables propias de F7 (además de las del kit):

    AGENTE=f7              prende este modo
    CHATWOOT_BANDEJA_ID    la bandeja que se atiende. Sin poner: la 1 (el WhatsApp
                           de F7). Vacía: todas las de la cuenta.
    F7_MEDIA_DIR           la carpeta de fotos y videos. Sin poner: recursos/f7-media.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..canales.adjuntos import TranscriptorOpenAI
from ..config import RAIZ, Config
from .canal import ChatwootF7
from .estado import AlmacenSQL
from .lector import LectorF7
from .produccion import AtencionF7

# La bandeja del WhatsApp de F7 en la cuenta 1 de Chatwoot (la 3 es «Test Bot API»).
BANDEJA_DE_F7 = "1"
CARPETA_DE_MEDIA = RAIZ / "recursos" / "f7-media"


def modo_f7() -> bool:
    """Si la configuración pide el agente de F7 (AGENTE=f7)."""
    return (os.getenv("AGENTE") or "").strip().lower() == "f7"


def carpeta_de_media() -> Path:
    valor = (os.getenv("F7_MEDIA_DIR") or "").strip()
    if not valor:
        return CARPETA_DE_MEDIA
    carpeta = Path(valor)
    return carpeta if carpeta.is_absolute() else RAIZ / carpeta


def bandeja_configurada() -> str:
    valor = os.getenv("CHATWOOT_BANDEJA_ID")
    return BANDEJA_DE_F7 if valor is None else valor.strip()


def almacen_de(config: Config) -> AlmacenSQL:
    """Postgres en el servidor (MODO=produccion); en tu máquina, un archivo al lado del SQLite del kit."""
    if config.modo == "produccion":
        return AlmacenSQL.postgres(config.postgres_dsn)
    return AlmacenSQL.sqlite(Path(config.sqlite_ruta).with_name("f7-conversaciones.db"))


def lector_de(config: Config, canal) -> LectorF7:
    """Los audios se transcriben con OpenAI; sin su clave, un audio pasa a una persona."""
    transcribir = None
    if config.transcribir_audios and config.clave_openai:
        transcribir = TranscriptorOpenAI(config.clave_openai, config.modelo_transcripcion)
    return LectorF7(canal, transcribir=transcribir)


def crear_app_f7(
    config: Config | None = None,
    *,
    modelo=None,
    canal=None,
    almacen=None,
    lector=None,
    carpeta_media: Path | str | None = None,
    leer_hojas=None,
    avisos=None,
    tope=None,
):
    """El servidor del kit con el agente de F7. Las piezas se pueden pasar armadas (las pruebas)."""
    from ..web.webhook import crear_app, validar_token

    config = config or Config.desde_entorno()
    validar_token(config.chatwoot_webhook_token)

    canal = canal or ChatwootF7(
        url=config.chatwoot_url,
        token=config.chatwoot_token,
        cuenta_id=config.chatwoot_cuenta_id,
        etiqueta_humano=config.chatwoot_etiqueta_humano,
        bandeja_id=bandeja_configurada(),
    )
    atencion = AtencionF7(
        canal,
        almacen or almacen_de(config),
        config=config,
        modelo=modelo,
        leer_hojas=leer_hojas,
        carpeta_media=carpeta_media or carpeta_de_media(),
    )
    atencion.revisar()
    atencion.preparar_modelo()
    atencion.revisar_planilla()

    return crear_app(
        config,
        canal=canal,
        avisos=avisos,
        tope=tope,
        lector=lector or lector_de(config, canal),
        f7=atencion,
    )
