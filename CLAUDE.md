# Agente F7 — versión en código (Agent Kit)

Proyecto creado el 15/11/2026 para reemplazar por código el agente de ventas de F7 hecho en n8n. La base es el Agent Kit 1.1 de Basdonax AI (Python, LangGraph, FastAPI). Español rioplatense en mensajes y documentación.

## Qué leer antes de tocar

1. Este archivo.
2. [AGENTS.md](AGENTS.md): cómo está hecho el kit (lo escribió su autor; sirve para entender el código).
3. [referencia-f7/LEEME.md](referencia-f7/LEEME.md): qué hace hoy F7 y dónde está cada fuente.
4. [docs/MAPA_MIGRACION.md](docs/MAPA_MIGRACION.md): qué hay que pasar de n8n al kit y en qué estado está.
5. [docs/INSTALAR_EN_EASYPANEL.md](docs/INSTALAR_EN_EASYPANEL.md): cómo se despliega en el servidor.

## Estado y plan

**El 20/11 Mateo aclaró que el agente de n8n no se usa más: todo el trabajo va sobre este agente en código.** Plan propuesto a Mateo el 15/11/2026; él pidió arrancar con la etapa 1. Cada etapa se le muestra terminada antes de pasar a la siguiente.

1. **Base — HECHA el 15/11.** Se clonó el kit, se quitó el actualizador de n8n, se copió el material de F7 a `referencia-f7/` y se armaron el `.env` de desarrollo y el entorno de Python. Las 269 pruebas del kit pasan.
2. **Pasarle F7:** el mismo prompt y lo que hoy hace n8n alrededor del modelo: saludo, «borrar», buffer, etiqueta humano, solo bandeja 1 y forma de partir las respuestas.
3. **Las tres herramientas en código:** precios (planilla oficial), multimedia (catálogo de Drive) y derivación a Candela.
4. **Pruebas sin clientes:** primero local con casos reales; después en el VPS, en paralelo, conectado a una cuenta de Chatwoot de pruebas.
5. **Cambio:** Mateo apunta Chatwoot al kit y apaga n8n sin borrarlo.

**Etapas 2 y 3 en la web de pruebas local: HECHAS el 15/11, a pedido de Mateo.** El código está en `src/agente/f7/` y se activa con `AGENTE=f7` en el `.env`. El prompt está en `prompts/f7/SYSTEM_PROMPT_F7_V1.md`. Las piezas se compararon con el código de n8n y dieron igual. Lo que las herramientas mandarían a Chatwoot se muestra en la web. Los precios se leen en vivo del XLSX público de la planilla oficial (en n8n se usa la API de Sheets). La conexión a Chatwoot se hizo el 21/11: ver «Conexión a WhatsApp por Chatwoot».

Las seis preguntas de «Al instalar» de AGENTS.md ya tienen respuesta para F7: el `.env` repite lo que hace hoy F7 (ver su cabecera). No volver a hacerlas. Siguen abiertas tres, que decide Mateo:
- la cantidad de globos;
- los mails de aviso;
- leer fotos.

## Conexión a WhatsApp por Chatwoot (21/11)

Pedido de Mateo del 21/11: conectar este agente a la línea de WhatsApp de F7 (cuenta 1 de Chatwoot, bandeja 1, hoy apuntada a n8n) para que los dueños lo prueben. **El código está hecho y probado en local. Subirlo a GitHub lo pide Mateo; desplegar en Easypanel y cambiar el webhook de Chatwoot los hace él** (pasos en `docs/INSTALAR_EN_EASYPANEL.md`).

Con `AGENTE=f7`, `webhook_chatwoot.py` arma el servidor con `crear_app_f7`:

- `src/agente/f7/servidor.py`: arma las piezas y revisa al arrancar la base, el guion, las 14 fotos y videos (por hash) y la planilla de precios. Si falta algo no arranca; la planilla solo avisa (registro y `/salud`).
- `src/agente/f7/canal.py` (`ChatwootF7`): atiende solo la bandeja `CHATWOOT_BANDEJA_ID` (sin poner: la 1); «borrar» pasa aunque esté «humano»; adjuntos sin pie de foto; pase a Candela (humano → abrir → asignar al usuario 3 → verificar).
- `src/agente/f7/produccion.py` (`AtencionF7`): carga la conversación, corre **el mismo turno de la web de pruebas**, guarda y manda todo al final, en el orden del turno. Si el turno falla, no sale ni se guarda nada.
- `src/agente/f7/estado.py`: por conversación, la memoria, la época, lo ya mandado y los registros de las herramientas (tabla `f7_conversaciones`), más una fila por turno con su detalle (`f7_turnos`). Postgres en el servidor, SQLite en local. Las etiquetas no se guardan: se leen de Chatwoot en cada turno.
- `src/agente/f7/lector.py`: los audios entran como texto, sin agregados; fotos, videos y citas no se leen (igual que en n8n).
- `recursos/f7-media/`: las 14 piezas del catálogo viajan dentro de la imagen. No se usa Drive.
- Del kit se tocó lo mínimo: `web/webhook.py` (parámetro `f7`), `canales/buffer.py` (`descartar`), `webhook_chatwoot.py` y el Dockerfile.

Decisiones que tomó Claude al construirlo, avisadas a Mateo (las puede cambiar):

- Fotos y videos como copias dentro del agente, no desde Drive (D6 del mapa).
- Base propia del proyecto en Easypanel; el agente arranca sin el historial de n8n (D4 y D5).
- Si el turno falla o Chatwoot rechaza un envío, el cliente no ve el error y la charla pasa a Candela («humano» + asignada), sin confirmación. Para devolverla al agente: sacar la etiqueta o escribir «borrar».
- Un audio que no se puede escuchar (sin `OPENAI_API_KEY` o con error) también pasa a Candela, sin contestar.
- Después de una foto o un video se espera hasta unos 15 s a que WhatsApp confirme la entrega antes de mandar lo que sigue, para que no llegue desordenado. Entre mensajes, 2 s como en n8n.
- Sin «escribiendo…», visto ni tope diario (extras del kit apagados, como hasta ahora).

Qué se probó: las pruebas de `tests/test_f7_produccion.py` (modelo y Chatwoot de mentira); los 14 archivos subidos por HTTP real a un Chatwoot de mentira (llegaron idénticos); el servidor real en modo F7 con «borrar», otra bandeja, token equivocado, foto y audio; las consultas de la base contra un Postgres embebido. **Qué no se probó:** WhatsApp y Chatwoot reales, el modelo real corriendo en el servidor y el conector de Postgres en el servidor. Eso se ve recién al desplegar.

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
  - **Búsqueda del vehículo:** desde el 16/11 la hace `src/agente/f7/precios/vehiculos.py`, a pedido de Mateo. Tolera cómo escribe la gente por WhatsApp. Nunca elige otro vehículo: ante la duda ofrece opciones, y si no hay nada parecido pide el modelo de nuevo. El resto del motor (años, variantes, precio) sigue siendo el port de n8n.
- **Retapizar o tipo tapizado:** regla del 20/11, a pedido de Mateo. Está en el paso «1 bis» del recorrido del prompt, con las tres frases literales que dio él.
  - Ante «retapizar» o «fundas tipo tapizado», el agente pregunta primero si quiere cambiar el tapizado o cubrirlo con fundas.
  - La tapicería se hace solo en el taller de CABA: no se pregunta «envío o taller». Se pregunta si puede acercarse, con la dirección y el link. Si no puede, se ofrecen las fundas a medida.
  - `buscar_precio` cotiza la tapicería sola siempre para el taller (`_solo_tapiceria` en `src/agente/f7/precios/herramienta.py`).
- **Correcciones del 20/11 (campaña de pruebas):** Mateo pidió corregir solo lo marcado «Error» en el informe de la campaña; lo de «Para mejorar» no se tocó. Después se re-probaron contra el modelo real las 14 conversaciones que fallaban. Las transcripciones quedaron en `datos/reprueba-2026-11-20.json` (git lo ignora).
  - **Envío o taller** (`src/agente/f7/modalidad.py`): reconoce la elección dicha de forma natural («lo coloco ahí en el taller», «ya te dije, con envío», «quisiera colocarlo en CABA») y cuando el cliente pide el precio de una sola opción («cuánto sale con envío?»). Una pregunta posterior ya no borra lo confirmado. Sigue sin ser elección preguntar si hacen envíos, cuánto sale o tarda el envío, o vivir lejos: es regla del guion.
  - **Precios** (`src/agente/f7/precios/`): el año decide la variante, no se elige una cabina que el cliente no nombró y la opción elegida se reconoce por su nombre («208»). Si la planilla no cubre el año o la configuración, si no hay precio o si habría que repetir la misma aclaración, la conversación pasa sola a Candela con lo que sí se pudo cotizar, en vez de mandar un texto de sistema. La misma cotización no se manda dos veces, salvo que el turno fuera a quedar en silencio. Techo, paneles y relleno se consultan como «otros», no como tapicería de butacas.
  - **Control de salida** (`src/agente/f7/salida.py`): lo que el modelo le contesta al cliente sale junto con la cotización o la aclaración; antes se descartaba. `corregir_frases` deja la pregunta de modalidad con la frase literal («colocarlo», no «retirarlo») y quita avisos como «el video ya quedó enviado».
  - **Prompt** (`prompts/f7/SYSTEM_PROMPT_F7_V1.md`): cinco líneas de resguardo, sin frases nuevas para el cliente. Mateo todavía tiene que confirmarlas o redactarlas:
    - butacas que no son las originales del vehículo pasan a Candela;
    - el material no se define ni se compara, y no se recomienda envío o taller;
    - «fundas tipo tapizado» también dispara la pregunta del paso 1 bis (además lo avisa el turno: `pregunta_tapizado_pendiente`);
    - con una aclaración de precios en el turno, se contesta también la otra pregunta del cliente;
    - el plazo de espuma y de otros trabajos de taller no está definido: no se estima.
  - **Rótulos de la planilla que hoy mandan a Candela:** Suran (solo 2009 y 2017-2019), Hilux (2005/2015, 2026 y cabina simple; tipo tapizado 2017 y 2013), SW4 (solo 2010), Saveiro (sin cabina simple), Partner de 3 asientos, alfombra trasera sola y tapizado de techo. «2005/2015» se lee como dos años sueltos, no como rango.
  - **Visto y sin tocar:** si el cliente pide que le repitan un precio, el modelo pasa a Candela en vez de volver a consultar. Dos textos de la herramienta suenan a sistema («Confirmá el año del vehículo para esta variante publicada…», «No encontré ese modelo o producto en la lista consultada»).
- **Campaña de multimedia del 21/11:** 35 conversaciones contra el modelo real para ver si manda las fotos y los videos correctos (7 escenarios por cada producto con material y 7 con productos que no tienen). Informe: https://claude.ai/artifact/JMn8cyf7ZVFh4mcfNkiXXU. Transcripciones en `datos/prueba-multimedia-2026-11-21.json`.
  - **Corregido ese día:** la corrección del 20/11 dejaba pasar relleno del modelo junto a la cotización («No tengo nada más para agregar por ahora»). Ahora lo que el modelo escribe al lado de `buscar_precio` sale solo si el cliente preguntó otra cosa además del precio (`_pregunto_otra_cosa` en `src/agente/f7/salida.py`).
  - **Decisiones de Mateo del 21/11 (son guion):** (1) si piden fotos de un producto se manda el video directamente; nunca se dice «no tengo fotos» ni «te paso un video». (2) Si preguntan la diferencia entre las dos fundas va el video comparativo y después solo «Cual de las dos opciones se adapta mas a lo que estas buscando?».
  - **Corregido el 21/11 y re-probado** con los mismos 35 escenarios (99 mensajes): de 19 con errores a 0, quedan 2 «para mejorar». Informe: https://claude.ai/artifact/W7WzfEJyPLxNKionYvUjnM. Transcripciones en `datos/reprueba-multimedia-2026-11-21.json`.
    - Fotos pedidas: lo resuelve `enviar_multimedia` (`_regla_de_fotos` en `src/agente/f7/multimedia/herramienta.py`). Manda el video; si ya lo tiene, las fotos de diseños y la carta de colores (fundas y tipo tapizado); si no queda nada, devuelve `indicacion` de pasar el catálogo. `sin_negar_fotos` (`src/agente/f7/salida.py`) borra del texto final cualquier «no tengo fotos».
    - Antes de la primera cotización el código manda el material del producto (`_material_antes_de_cotizar` en `src/agente/f7/turno.py`): tipo tapizado, alfombras y cubrevolante, y la presentación de fundas a medida con su video si nunca se hizo. No sale si el cliente ya lo vio o pidió que no se lo manden.
    - El aviso del paso 1 bis no salta si pregunta la diferencia entre las fundas, si ya dijo que van por encima o si ya vio el comparativo. El pedido de fotos o video que quedó pendiente por esa pregunta sale cuando la contesta, del producto pedido.
    - Reenvío: `pedido_de_material` (`src/agente/f7/prompt.py`) reconoce «me lo pasás de nuevo» o «no me cargó», y el prompt del turno le dice al modelo cuál fue el último material mandado (las filas de `multimedia_registrada` llevan `lote`). Nombrar un video sin pedirlo no lo reenvía (`reenvio_solo_marcado`).
    - La descripción de `enviar_multimedia` termina con la lista «MATERIAL QUE EXISTE», armada del catálogo, para que el modelo sepa qué piezas hay.
  - **Espera definición de Mateo:** si el cliente pide un video que ya recibió sin decir «de nuevo», hoy el agente le contesta que se fije más arriba y no lo repite.
- **Prueba de «romper el flujo» del 21/11:** 54 conversaciones (165 mensajes) contra el modelo real buscando errores dentro de lo que el agente debe responder. 27 con errores, 9 para mejorar, 18 bien. Informe: https://claude.ai/artifact/8w9N83F2vk9wTiWKvFBNKx. Transcripciones en `datos/prueba-romper-flujo-2026-11-21.json`.
  - **Corregido el 21/11 (pedido de Mateo) y re-probado contra el modelo real** con 26 conversaciones (49 mensajes, USD 1,08): 21 de las que habían fallado, con sus mismos mensajes, y 5 de control. Todo lo corregido respondió bien. La re-prueba mostró dos cosas más, corregidas en el momento: ante «tenés fotos de las fundas a medida?» pedía el modelo del auto antes de mandar el video (una frase nueva del guion; ajustada), y «las fundas del Gol las coloco en el taller» no se reconocía como taller. Transcripciones en `datos/reprueba-romper-flujo-2026-11-21.json`. No se repitieron los casos que quedaron sin tocar ni los que son solo de código (Corolla partido en globos, dos preguntas juntas).
    - Envío o taller (`src/agente/f7/modalidad.py`): reconoce el envío nombrado al final de un pedido («fundas para Sandero con envío a Posadas», «todo por envío entonces»), los pedidos directos («Me las mandás a Paraná?», «mandamelas a Tandil», «y con envío?», «es para colocar en el taller», «lo quiero colocado»), el precio de un escenario («cuánto sale si lo coloco en el taller», «y si voy al taller?») y «embio/enbio». Sobre los 557 mensajes grabados cambian solo los 12 que estaban mal.
    - Trabajos solo de taller: techo, paneles, relleno y espuma se cotizan para el taller sin preguntar la modalidad (`solo_taller` en `precios/motor.py`); con envío elegido contestan que son presenciales.
    - Aclaraciones de modelo (`precios/`): «ecosport kinetic/kinetik» va a ECO KINECTIC; la cabina que escribe el cliente vale aunque el modelo no la pase (`ContextoTurno.texto_cliente`); «Unidad» no cuenta como configuración; lo que no está en una lista corta (alfombras, funda de baúl, techo) pasa a Candela sin texto de sistema; tipo tapizado sin tarifa para ese auto usa «No contamos con las medidas…» y no «Creo que tuviste una confusion»; la pregunta por el año es «De qué año es tu vehículo?».
    - Texto final (`salida.py`, `partir.py`, `turno.py`): no se parte en «T.ENTERO»; no se afirma que hay un producto para un vehículo sin una cotización (`sin_afirmar_disponibilidad`); después de la pregunta de modalidad no va otra pregunta (`una_sola_pregunta`); el horario y la dirección del guion salen siempre que los preguntan; una pregunta del cliente que quedaría sin ninguna respuesta pasa a Candela (`derivacion_por_silencio`).
    - Fase del turno (`clasificar_fase` en `prompt.py`): «carísimo», «en otro lado me cobran…», «sin ver» y similares traen el bloque de objeciones; «puedo ir mañana?» va como turno. Si el cliente ya dijo «quiero cambiarle el tapizado», el aviso del paso 1 bis manda directo a la pregunta del taller.
    - Guion: 8 instrucciones nuevas o ampliadas (trabajos solo de taller, no afirmar que un precio ya incluye el descuento, plazo cuando preguntan si llega para una fecha, envío al exterior y retiro por terceros a Candela, promociones y turnos a Candela, no asumir el producto, horarios junto a la cotización, no preguntar cuál de las dos fundas describiéndolas). La copia anterior está en `datos/guion-antes-de-las-correcciones-2026-11-21.md`.
  - **Sin corregir, a propósito:** el 10% por transferencia en cotizaciones de varios productos con envío, la fila de Amarok 2022 en tipo tapizado (cotiza «Amarok V6»; las tres filas tienen el mismo precio), los dos precios cuando piden comparar envío y taller, el pedido con una cosa por envío y otra por taller (sigue preguntando), y si «lo confirma Candela» debe pasar la conversación: esperan definición de Mateo. La funda de baúl para Corolla Cross sigue ofreciendo «Corolla G12 o T-Cross» (cualquier regla ahí puede cotizar otro auto). Las demoras (hasta 88 s con mensajes muy cargados) tampoco se tocaron.
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
- **Cuenta 1 de Chatwoot:** Chatwoot le avisa a un solo agente por vez. Si quedan activos el webhook de n8n y el de este agente, contestan los dos. El agente genérico del kit no filtra por bandeja; el de F7 (`AGENTE=f7`) atiende solo la que dice `CHATWOOT_BANDEJA_ID`.
- **Skill quitada:** se sacó a propósito la skill «actualizar-agente-whatsapp» del kit. Era para agentes en n8n, se dispara con «actualizá el agente» y toma sola la clave de n8n del `.mcp.json` de la carpeta. No volver a traerla.
- **Proyecto viejo:** el de n8n está en `../Agente f7 completo`. Desde acá se consulta, no se modifica.
