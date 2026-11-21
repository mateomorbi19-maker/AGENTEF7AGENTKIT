"""Lo que el agente de F7 recuerda de cada conversación, guardado en una base.

En la web de pruebas todo vive en memoria: hay una sola conversación y se
pierde al cerrar. En el servidor hay muchas a la vez, y un reinicio (o un
deploy) no puede hacerles perder el hilo. Acá se guarda, por conversación:

- la memoria del agente: lo que dijo el cliente y la salida segura de cada turno;
- la época de «borrar»;
- las fotos y los videos que ya se mandaron;
- los registros de las tres herramientas (cotizaciones, envíos y pases);
- el contador de ids.

Las etiquetas NO se guardan: la verdad está en Chatwoot y se leen en cada turno.
Lo que se mandó en un turno tampoco: es de ese turno y nada más.

Además queda una fila por turno con su detalle (qué entró, qué fase, qué
herramientas, qué decidió el control). Es lo que se mira cuando alguien
pregunta «¿por qué contestó eso?».
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Callable

from .local import SesionLocal

VERSION = 1


def empaquetar(sesion: SesionLocal, memoria: list[tuple[str, str]]) -> str:
    """La conversación como texto JSON, lista para guardar.

    Si algo de adentro no se puede escribir como JSON, falla acá y con ruido:
    guardar «más o menos» sería levantar después una conversación distinta.
    """
    return json.dumps(
        {
            "version": VERSION,
            "epoca": sesion.epoca,
            "ultimo_message_id": sesion._ultimo_message_id,
            "multimedia_registrada": sesion.multimedia_registrada,
            "registros": sesion.registros,
            "memoria": [[rol, texto] for rol, texto in memoria],
        },
        ensure_ascii=False,
    )


def desempaquetar(texto: str, conversation_id: int) -> tuple[SesionLocal, list[tuple[str, str]]]:
    """Lo guardado, de vuelta como la sesión y la memoria que usa el turno."""
    datos = json.loads(texto)
    sesion = SesionLocal(
        conversation_id=conversation_id,
        epoca=int(datos.get("epoca") or 0),
        multimedia_registrada=list(datos.get("multimedia_registrada") or []),
        registros=dict(datos.get("registros") or {}),
        _ultimo_message_id=int(datos.get("ultimo_message_id") or 0),
    )
    memoria = [(str(rol), str(dicho)) for rol, dicho in datos.get("memoria") or []]
    return sesion, memoria


def _detalle_a_json(detalle: dict) -> str:
    # El detalle es para leerlo una persona: lo que no es JSON va como texto.
    return json.dumps(detalle, ensure_ascii=False, default=str)


def _ahora() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


_CONVERSACION_DE_PRUEBA = "__arranque__"


class _ConPrueba:
    """Lo que comparten los almacenes: probarse de punta a punta al arrancar."""

    def probar(self) -> None:
        """Guarda, lee y borra una fila de prueba. Si la base no anda, se nota acá y no con un cliente."""
        marca = "prueba " + _ahora()
        self.guardar(_CONVERSACION_DE_PRUEBA, marca)
        leido = self.cargar(_CONVERSACION_DE_PRUEBA)
        self.olvidar(_CONVERSACION_DE_PRUEBA)
        if leido != marca:
            raise RuntimeError("la base no devolvió lo que se le acababa de guardar")


class AlmacenEnMemoria(_ConPrueba):
    """Para las pruebas: lo mismo que la base, pero se pierde al cerrar."""

    def __init__(self) -> None:
        self._estados: dict[str, str] = {}
        self._turnos: list[tuple[str, dict]] = []

    def preparar(self) -> None:
        pass

    def cargar(self, conversacion: str) -> str | None:
        return self._estados.get(str(conversacion))

    def guardar(self, conversacion: str, estado: str) -> None:
        self._estados[str(conversacion)] = estado

    def olvidar(self, conversacion: str) -> None:
        self._estados.pop(str(conversacion), None)

    def anotar_turno(self, conversacion: str, detalle: dict) -> None:
        self._turnos.append((str(conversacion), json.loads(_detalle_a_json(detalle))))

    def turnos(self, conversacion: str) -> list[dict]:
        return [d for c, d in self._turnos if c == str(conversacion)]


_TABLAS = (
    "CREATE TABLE IF NOT EXISTS f7_conversaciones ("
    "conversacion TEXT PRIMARY KEY, estado TEXT NOT NULL, actualizado TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS f7_turnos ("
    "conversacion TEXT NOT NULL, creado TEXT NOT NULL, detalle TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS f7_turnos_por_conversacion ON f7_turnos (conversacion, creado)",
)


class AlmacenSQL(_ConPrueba):
    """La base de verdad: SQLite en tu máquina, Postgres en el servidor.

    Las consultas son las mismas para las dos; lo único que cambia es cómo se
    marca un valor («?» en SQLite, «%s» en Postgres). Cada operación abre su
    conexión y la cierra: son dos o tres por turno, y así una conexión que se
    cayó de noche no deja al agente sin memoria a la mañana.
    """

    def __init__(self, conectar: Callable[[], object], marcador: str = "?") -> None:
        self._conectar = conectar
        self._marcador = marcador

    @classmethod
    def sqlite(cls, ruta: str | Path) -> "AlmacenSQL":
        ruta = Path(ruta)

        def conectar():
            ruta.parent.mkdir(parents=True, exist_ok=True)
            return sqlite3.connect(ruta, timeout=30)

        return cls(conectar, "?")

    @classmethod
    def postgres(cls, dsn: str) -> "AlmacenSQL":
        def conectar():
            import psycopg  # solo hace falta en el servidor

            return psycopg.connect(dsn, connect_timeout=10)

        return cls(conectar, "%s")

    def _ejecutar(self, sql: str, valores: tuple = (), traer: str = ""):
        conexion = self._conectar()
        try:
            cursor = conexion.execute(sql.replace("?", self._marcador), valores)
            if traer == "una":
                resultado = cursor.fetchone()
            elif traer == "todas":
                resultado = cursor.fetchall()
            else:
                resultado = None
            conexion.commit()
            return resultado
        finally:
            conexion.close()

    def preparar(self) -> None:
        """Crea las tablas si no están. Si la base no contesta, falla acá: al arrancar."""
        for tabla in _TABLAS:
            self._ejecutar(tabla)

    def cargar(self, conversacion: str) -> str | None:
        fila = self._ejecutar(
            "SELECT estado FROM f7_conversaciones WHERE conversacion = ?", (str(conversacion),), "una"
        )
        return fila[0] if fila else None

    def guardar(self, conversacion: str, estado: str) -> None:
        self._ejecutar(
            "INSERT INTO f7_conversaciones (conversacion, estado, actualizado) VALUES (?, ?, ?) "
            "ON CONFLICT (conversacion) DO UPDATE SET "
            "estado = excluded.estado, actualizado = excluded.actualizado",
            (str(conversacion), estado, _ahora()),
        )

    def olvidar(self, conversacion: str) -> None:
        self._ejecutar("DELETE FROM f7_conversaciones WHERE conversacion = ?", (str(conversacion),))

    def anotar_turno(self, conversacion: str, detalle: dict) -> None:
        self._ejecutar(
            "INSERT INTO f7_turnos (conversacion, creado, detalle) VALUES (?, ?, ?)",
            (str(conversacion), _ahora(), _detalle_a_json(detalle)),
        )

    def turnos(self, conversacion: str) -> list[dict]:
        filas = self._ejecutar(
            "SELECT detalle FROM f7_turnos WHERE conversacion = ? ORDER BY creado",
            (str(conversacion),),
            "todas",
        )
        return [json.loads(fila[0]) for fila in filas or []]
