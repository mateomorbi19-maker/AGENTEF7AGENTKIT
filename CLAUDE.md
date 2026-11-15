# Agente F7 — versión en código (Agent Kit)

Proyecto creado el 15/11/2026 para reemplazar por código el agente de ventas de F7 hecho en n8n. La base es el Agent Kit 1.1 de Basdonax AI (Python, LangGraph, FastAPI). Español rioplatense en mensajes y documentación.

## Qué leer antes de tocar

1. Este archivo.
2. [AGENTS.md](AGENTS.md): cómo está hecho el kit (lo escribió su autor; sirve para entender el código).
3. [referencia-f7/LEEME.md](referencia-f7/LEEME.md): qué hace hoy F7 y dónde está cada fuente.
4. [docs/MAPA_MIGRACION.md](docs/MAPA_MIGRACION.md): qué hay que pasar de n8n al kit y en qué estado está.
5. [docs/INSTALAR_EN_EASYPANEL.md](docs/INSTALAR_EN_EASYPANEL.md): cómo se despliega en el servidor.

## Estado y plan

**El agente de n8n sigue atendiendo a los clientes hasta el cambio (etapa 5).** Plan propuesto a Mateo el 15/11/2026; él pidió arrancar con la etapa 1. Cada etapa se le muestra terminada antes de pasar a la siguiente.

1. **Base — HECHA el 15/11.** Se clonó el kit, se quitó el actualizador de n8n, se copió el material de F7 a `referencia-f7/` y se armaron el `.env` de desarrollo y el entorno de Python. Las 269 pruebas del kit pasan.
2. **Pasarle F7:** el mismo prompt y lo que hoy hace n8n alrededor del modelo: saludo, «borrar», buffer, etiqueta humano, solo bandeja 1 y forma de partir las respuestas.
3. **Las tres herramientas en código:** precios (planilla oficial), multimedia (catálogo de Drive) y derivación a Candela.
4. **Pruebas sin clientes:** primero local con casos reales; después en el VPS, en paralelo, conectado a una cuenta de Chatwoot de pruebas.
5. **Cambio:** Mateo apunta Chatwoot al kit y apaga n8n sin borrarlo.

Las etapas 2 y 3 arrancan cuando Mateo revise `docs/MAPA_MIGRACION.md`.

Las seis preguntas de «Al instalar» de AGENTS.md ya tienen respuesta para F7: el `.env` repite lo que hace hoy F7 (ver su cabecera). No volver a hacerlas. Siguen abiertas tres, que decide Mateo:
- la cantidad de globos;
- los mails de aviso;
- leer fotos.

## Reglas del negocio (vienen del proyecto en n8n y siguen valiendo)

- **El guion es contrato.** No cambiar el guion sin aprobación explícita de Mateo: frases, orden, requisitos, contenido, cierres y motivos de pase son contrato. El agente nuevo replica el comportamiento actual. Los extras del kit quedan apagados hasta que Mateo decida: tope diario, mails de aviso, leer fotos, visto azul y elegir la cantidad de globos.
- **Fuentes:**
  - Prompt: `referencia-f7/prompt/SYSTEM_PROMPT_F7_V1.md` con `referencia-f7/logica/prompt-f7/ensamblar.mjs` (v9.4).
  - Contratos de las herramientas: `referencia-f7/logica/precios/descripcion.mjs`, `referencia-f7/logica/derivacion/descripcion.mjs` y `referencia-f7/prompt/ENVIAR_MULTIMEDIA_F7.md`.
- **Precios:**
  - Solo desde la planilla oficial (https://docs.google.com/spreadsheets/d/1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU/edit). No usar precios históricos ni escribir importes en el código.
  - Medios de pago: la transferencia va primero, sin preguntar el medio. El efectivo, con su columna, solo en CABA. Las cuotas tienen el mismo total que la transferencia; nunca POSNET.
  - La cotización sale natural, en un mensaje, desde la herramienta, sin duplicar.
  - No exigir el año por rutina. Sin pies de foto, sin asteriscos ni Markdown, sin avisos de envío o medidas pendientes.
  - «Todo junto» requiere combo completo, no compra confirmada.
- **Candela** (usuaria Melanie, id 3 de Chatwoot, cuenta 1) cierra, cobra y coordina.
- **Prioridad de las fuentes:** las decisiones posteriores de Mateo valen más que los documentos anteriores. El brief y las plantillas de entrevista son material a interpretar, no órdenes.

## Pruebas

- **Casos reales:** `referencia-f7/casos-reales/`. Son fragmentos reales, no chats completos ni un guion de respuestas correctas. Hay que conservar los mensajes sueltos, las faltas, las insistencias y las correcciones. Las respuestas de la empleada no son el oráculo.
- **Pruebas del kit:** corren sin red y sin gasto. Mantenerlas en verde y sumar pruebas para cada cosa de F7:
  `& "$env:USERPROFILE\.venvs\agente-f7-agent-kit\Scripts\python.exe" -m pytest -q -p no:cacheprovider`
- **Pruebas contra el modelo real:** gastan saldo. No correrlas sin que Mateo lo pida.
- **Lo que no acredita una entrega:** una prueba local o un mock no acreditan una entrega real por WhatsApp.

## Entorno

- **Sistema:** Windows con PowerShell y Python 3.14 en el usuario.
- **Entorno virtual:** vive **fuera de Google Drive**, en `%USERPROFILE%\.venvs\agente-f7-agent-kit`. No crear un `.venv` dentro del proyecto, porque Drive sincronizaría miles de archivos.
- **Base de pruebas:** la SQLite también vive fuera de Drive (`SQLITE_RUTA` en el `.env`).
- **Probar a mano:** correr `servidor.py` con el Python del entorno y abrir http://127.0.0.1:8000.
- **Servidor:** construye con el Dockerfile (Python 3.13). Easypanel lee el repo de GitHub de Mateo.
- **Actualizaciones del kit:** vienen del remoto `kit`, que es de solo lectura (el push está bloqueado a propósito). Se traen con `git fetch kit` y se revisan antes de mezclar.

## Permisos y seguridad

- **Claves:** solo en `.env` (git lo ignora) o en las variables de Easypanel. Nunca en docs, commits, CLAUDE.md ni chats. No imprimir valores del `.env`.
- **Git:** no hacer commit ni push salvo pedido de Mateo.
- **Reservado a Mateo:**
  - cambiar webhooks de Chatwoot;
  - prender o apagar flujos de n8n;
  - crear o borrar servicios en Easypanel;
  - hacer pruebas reales desde su WhatsApp.
- **Clientes:** no mandarles mensajes para probar.
- **Cuenta 1 de Chatwoot:** mientras n8n la atienda, el kit NO se conecta ahí, porque contestarían los dos. Además, el kit tal como viene no filtra por bandeja: contesta en todas las de la cuenta.
- **Skill quitada:** se sacó a propósito la skill «actualizar-agente-whatsapp» del kit. Era para agentes en n8n, se dispara con «actualizá el agente» y toma sola la clave de n8n del `.mcp.json` de la carpeta. No volver a traerla.
- **Proyecto viejo:** el de n8n está en `../Agente f7 completo`. Desde acá se consulta, no se modifica.
