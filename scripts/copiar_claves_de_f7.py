"""Copia las claves del proyecto viejo (n8n) al .env de este proyecto, sin mostrarlas,
y prueba que anden.

Lo corre Mateo con doble clic en «copiar-claves-de-f7.cmd». Para Claude Code,
el .env viejo y la carpeta secrets/ están protegidos a propósito (regla del
8/9 en «Agente f7 completo/.claude/settings.json»). Este script lo corre la
persona y no imprime ningún valor: solo dice qué copió, de dónde y si anda.

Busca, en este orden:
  ANTHROPIC_API_KEY  →  OneDrive\\Desktop\\.env, Desktop\\.env y el .env del proyecto viejo
  OPENAI_API_KEY     →  el .env del proyecto viejo y después los del Escritorio
  CHATWOOT_TOKEN     →  el .env del proyecto viejo: cualquier variable CHATWOOT_…TOKEN/KEY,
                        salvo la del webhook

Si una clave ya tiene valor en el .env nuevo, no la pisa.

Después prueba cada clave con una consulta que no gasta saldo (la lista de
modelos de Anthropic y de OpenAI, y el perfil en Chatwoot) y deja el resultado
—sin ningún valor— en datos/verificacion-claves.json, para que Claude Code lo lea.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENV_NUEVO = RAIZ / ".env"
ENV_VIEJO = RAIZ.parent / "Agente f7 completo" / ".env"
REPORTE = RAIZ / "datos" / "verificacion-claves.json"  # datos/ está en .gitignore
CASA = Path.home()
ESCRITORIOS = [
    CASA / "OneDrive" / "Desktop" / ".env",
    CASA / "OneDrive" / "Escritorio" / ".env",
    CASA / "Desktop" / ".env",
]

LINEA = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")

# Cómo tiene que verse cada clave. Si lo que se encuentra no tiene esa forma,
# no se copia: mejor un hueco a la vista que una clave equivocada.
FORMA = {
    "ANTHROPIC_API_KEY": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "OPENAI_API_KEY": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    "CHATWOOT_TOKEN": re.compile(r"[A-Za-z0-9_\-]{16,}"),
}

PREFERIDAS_CHATWOOT = [
    "CHATWOOT_TOKEN",
    "CHATWOOT_API_TOKEN",
    "CHATWOOT_API_ACCESS_TOKEN",
    "CHATWOOT_ACCESS_TOKEN",
    "CHATWOOT_API_KEY",
]


def leer(ruta: Path) -> dict[str, str]:
    """Las variables con valor de un .env. Nunca se imprimen."""
    valores: dict[str, str] = {}
    if not ruta.is_file():
        return valores
    for linea in ruta.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if linea.lstrip().startswith("#"):
            continue
        m = LINEA.match(linea)
        if not m:
            continue
        nombre, valor = m.group(1), m.group(2)
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        else:
            valor = valor.split(" #", 1)[0].strip()
        if valor:
            valores[nombre] = valor
    return valores


def nombres_chatwoot(valores: dict[str, str]) -> list[str]:
    candidatos = [n for n in PREFERIDAS_CHATWOOT if n in valores]
    for n in sorted(valores):
        if (
            "CHATWOOT" in n
            and ("TOKEN" in n or "KEY" in n)
            and "WEBHOOK" not in n
            and n not in candidatos
        ):
            candidatos.append(n)
    return candidatos


def escribir(cambios: dict[str, str]) -> None:
    texto = ENV_NUEVO.read_text(encoding="utf-8")
    for nombre, valor in cambios.items():
        patron = re.compile(rf"^{nombre}=.*$", re.M)
        texto, n = patron.subn(lambda _m, v=valor, k=nombre: f"{k}={v}", texto, count=1)
        if n == 0:
            texto = texto.rstrip("\n") + f"\n{nombre}={valor}\n"
    # Primero a un archivo aparte y después se reemplaza de una: si algo se
    # corta a mitad, el .env queda como estaba (el .gitignore cubre .env*).
    temporal = ENV_NUEVO.with_name(".env.copiando")
    temporal.write_text(texto, encoding="utf-8")
    temporal.replace(ENV_NUEVO)


# --- Prueba de las claves -------------------------------------------------


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
    """Una clave nunca viaja a otro lado porque el servidor redirija."""

    def redirect_request(self, *args, **kwargs):  # noqa: D401
        return None


_ABRIR = urllib.request.build_opener(_SinRedirecciones())


def _pedir(url: str, cabeceras: dict[str, str]) -> tuple[int, object]:
    """GET y devuelve (código HTTP, JSON o None). -1 si no hubo conexión."""
    cabeceras = {"User-Agent": "agente-f7-verificacion/1.0", "Accept": "application/json", **cabeceras}
    pedido = urllib.request.Request(url, headers=cabeceras, method="GET")
    try:
        with _ABRIR.open(pedido, timeout=20) as r:
            cuerpo = r.read(2_000_000)
            try:
                return r.status, json.loads(cuerpo)
            except ValueError:
                return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:  # sin conexión, DNS, certificado: sin detalles
        return -1, None


def verificar(valores: dict[str, str]) -> dict[str, dict]:
    resultado: dict[str, dict] = {}

    clave = valores.get("ANTHROPIC_API_KEY")
    if clave:
        codigo, datos = _pedir(
            "https://api.anthropic.com/v1/models?limit=1000",
            {"x-api-key": clave, "anthropic-version": "2023-06-01"},
        )
        ids = [m.get("id", "") for m in (datos or {}).get("data", [])] if isinstance(datos, dict) else []
        resultado["ANTHROPIC_API_KEY"] = {
            "esta": True,
            "anda": codigo == 200,
            "http": codigo,
            "tiene_sonnet_5": any(i.startswith("claude-sonnet-5") for i in ids) if codigo == 200 else None,
        }
    else:
        resultado["ANTHROPIC_API_KEY"] = {"esta": False}

    clave = valores.get("OPENAI_API_KEY")
    if clave:
        codigo, _ = _pedir("https://api.openai.com/v1/models", {"Authorization": f"Bearer {clave}"})
        resultado["OPENAI_API_KEY"] = {"esta": True, "anda": codigo == 200, "http": codigo}
    else:
        resultado["OPENAI_API_KEY"] = {"esta": False}

    clave = valores.get("CHATWOOT_TOKEN")
    url = (valores.get("CHATWOOT_URL") or "").rstrip("/")
    if clave and url.startswith("https://"):
        codigo, datos = _pedir(f"{url}/api/v1/profile", {"api_access_token": clave})
        cuenta = str(valores.get("CHATWOOT_CUENTA_ID") or "1")
        rol = None
        if codigo == 200 and isinstance(datos, dict):
            for c in datos.get("accounts") or []:
                if str(c.get("id")) == cuenta:
                    rol = c.get("role")
        resultado["CHATWOOT_TOKEN"] = {
            "esta": True,
            "anda": codigo == 200,
            "http": codigo,
            "cuenta": cuenta,
            "rol_en_la_cuenta": rol,
        }
    else:
        resultado["CHATWOOT_TOKEN"] = {"esta": bool(clave), "anda": None if clave else False}

    return resultado


def mostrar(resultado: dict[str, dict]) -> None:
    print("  Prueba de las claves (consultas que no gastan saldo):")
    for nombre, r in resultado.items():
        if not r.get("esta"):
            print(f"    {nombre}: falta")
        elif r.get("anda"):
            extra = ""
            if nombre == "ANTHROPIC_API_KEY":
                extra = " (tiene Sonnet 5)" if r.get("tiene_sonnet_5") else " (OJO: no aparece Sonnet 5)"
            if nombre == "CHATWOOT_TOKEN":
                extra = f" (rol en la cuenta {r.get('cuenta')}: {r.get('rol_en_la_cuenta') or 'no tiene acceso'})"
            print(f"    {nombre}: anda{extra}")
        elif r.get("http") == -1:
            print(f"    {nombre}: no pude probarla (sin conexion)")
        else:
            print(f"    {nombre}: NO ANDA (respuesta {r.get('http')})")


def main() -> int:
    print()
    print("  Copiar claves del proyecto viejo (n8n) a este proyecto")
    print("  -------------------------------------------------------")
    print("  (no se muestra ningun valor)")
    print()
    if not ENV_NUEVO.is_file():
        print(f"  No encuentro el .env de este proyecto: {ENV_NUEVO}")
        return 1

    actuales = leer(ENV_NUEVO)
    viejo = leer(ENV_VIEJO)
    escritorio = [(r, leer(r)) for r in ESCRITORIOS]

    fuentes: dict[str, list[tuple[str, str, str]]] = {
        "ANTHROPIC_API_KEY": [(str(r), "ANTHROPIC_API_KEY", v["ANTHROPIC_API_KEY"]) for r, v in escritorio if "ANTHROPIC_API_KEY" in v]
        + ([(str(ENV_VIEJO), "ANTHROPIC_API_KEY", viejo["ANTHROPIC_API_KEY"])] if "ANTHROPIC_API_KEY" in viejo else []),
        "OPENAI_API_KEY": ([(str(ENV_VIEJO), "OPENAI_API_KEY", viejo["OPENAI_API_KEY"])] if "OPENAI_API_KEY" in viejo else [])
        + [(str(r), "OPENAI_API_KEY", v["OPENAI_API_KEY"]) for r, v in escritorio if "OPENAI_API_KEY" in v],
        "CHATWOOT_TOKEN": [(str(ENV_VIEJO), n, viejo[n]) for n in nombres_chatwoot(viejo)],
    }

    cambios: dict[str, str] = {}
    faltan: list[str] = []
    origen: dict[str, str] = {}
    for clave, opciones in fuentes.items():
        if actuales.get(clave):
            print(f"  YA ESTABA  {clave}: ya tenia valor, no la toque")
            origen[clave] = "ya estaba"
            continue
        elegida = next(((f, n, v) for f, n, v in opciones if FORMA[clave].fullmatch(v)), None)
        if elegida:
            f, n, v = elegida
            cambios[clave] = v
            origen[clave] = f"{f} (variable {n})"
            print(f"  OK         {clave}: copiada desde {f} (variable {n})")
        else:
            faltan.append(clave)
            motivo = "la encontre pero no tiene forma de clave" if opciones else "no la encontre"
            origen[clave] = motivo
            print(f"  FALTA      {clave}: {motivo}")

    if cambios:
        escribir(cambios)

    print()
    resultado = verificar(leer(ENV_NUEVO))
    mostrar(resultado)

    REPORTE.parent.mkdir(parents=True, exist_ok=True)
    REPORTE.write_text(
        json.dumps(
            {
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "origen": origen,
                "prueba": resultado,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    if "ANTHROPIC_API_KEY" in cambios:
        print("  Ojo: la clave de Claude copiada es la de tu compu. Puede no ser la")
        print("  misma cuenta (ni el mismo saldo) que usa hoy n8n.")
    if faltan:
        print("  Las que faltan pegalas a mano en el .env (EMPEZAR_ACA.md dice de donde)")
        print("  y volve a hacer doble clic en este archivo para probarlas.")
        if viejo:
            # Solo en tu pantalla: el reporte que lee Claude Code no los lleva.
            print("  Nombres de variables que hay en el .env viejo (solo nombres):")
            print("    " + ", ".join(sorted(viejo)))
    print("  Listo: avisale a Claude Code; el resultado (sin valores) quedo en")
    print(f"  {REPORTE}")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # sin el detalle: podría arrastrar un valor
        print(f"  Algo fallo ({type(e).__name__}). El .env quedo como estaba o con lo ya copiado.")
        sys.exit(1)
