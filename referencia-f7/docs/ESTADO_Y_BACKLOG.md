# Estado real y backlog priorizado

Fecha: 2026-09-08. Base: snapshot vivo de n8n del 2026-09-07 (`workflows/`), Chatwoot (solo lectura), los documentos de mayo 2026 y el análisis multi-agente de `docs/analisis-2026-09-07/` (97 hallazgos, 82 verificados uno por uno contra el JSON vivo, 0 refutados, 15 de severidad baja sin verificar).

## 1. Estado al 2026-09-08

| Tema | Estado |
|---|---|
| Cadena F7 en n8n | 9 workflows ON (Memory Manager, Agente V2.10, precios, fotos, humano, registrar intención, cotizar combo, Log Mensaje, Cleanup) + 2 OFF (Media Proxy, Test Runner). Última edición: 2026-06-11 |
| Conexión con WhatsApp | **Desconectada.** El único webhook de la cuenta 1 de Chatwoot apunta a `/webhook/d3181880-…` = `AGENTE PRUEBA 2` (bot de otro cliente, gpt-4.1-mini). El Memory Manager (`/webhook/memory-manager-f7`) no recibe nada |
| Tráfico | 15 conversaciones históricas en Chatwoot; la última el 2026-07-31. n8n devuelve 0 ejecuciones retenidas |
| Sprint 1 (seguridad, mayo) | Cerrado, pero con regresión: el nodo de salida del agente (`1ª Parte Respuesta1`) volvió a tener el token de Chatwoot en texto plano y `Guardar Human` volvió a interpolar `session_id` en el SQL |
| Sprint 2 (bugs, mayo) | Cerrado, pero el PUT del 2026-06-11 subió el agente a partir del JSON de abril: se perdieron el fix de negaciones (2.3), el nombre canónico `cubrevolante` en el agente (2.1) y la corrección de la descripción de la tool precios (2.2). En Herramienta precios desapareció la cadena "Sin Medidas Fundas" (2.5). Los 20 `Marcar Cotiz` (2.8) y `Leer Precio CV` (2.2) sí están |
| Versión del Sprint 2 | **Recuperada** desde `activeVersion` del backup local "FLUJO (contenido viejo)": `workflows/recuperados/agente-ventas_sprint2_2026-05-05.json` y `src/agent/recuperado_sprint2/` (con diff contra el vivo) |
| Tokens | Chatwoot, WhatsApp y JWT service_role de Supabase sin rotar desde abril; aparecen en texto plano en el agente vivo, en AGENTE PRUEBA 2, en `Herramienta pedido` (OFF), en los JSON de abril, en planes v1.1/v1.2 y en `.claude/settings.json` (limpiado hoy) |
| Sprints 3 y 4 | No iniciados (refactor de herramientas; robustez y UX) |
| Pre-flight de go-live | No hecho (rotación 1.1/1.2/1.3, smoke-test 1.15) |
| Repo | Ordenado hoy: tooling `scripts/`, `src/agent/`, `tests/`, docs. `git init` hecho, sin commits (los hace Mateo). La carpeta sigue en Google Drive |

## 2. Hecho en esta sesión (2026-09-07/08), todo local

- Export del snapshot vivo (18 workflows) y scripts de export/diff/import/restore con backup automático; verificado diff = 0.
- Código del agente extraído a `src/agent/`, harness para correr el clasificador fuera de n8n, tests (`npm test`).
- Documentación: `CLAUDE.md`, `README.md`, `docs/ARQUITECTURA.md`, `docs/GUION_DE_VENTA.md`, `docs/OPERACION.md`, `docs/HISTORIA.md`, `docs/DECISIONES_PENDIENTES.md`, `docs/PROMPT_OPTIMIZACION_PROPUESTA.md`, este archivo.
- Carpeta reordenada: docs históricos en `docs/historia/` (con tokens redactados; originales en `secrets/originales/`), JSON de abril en `workflows/archive-2026-04-28/` (gitignored), prompt unificado en `prompts/`, `CREDENTIALS_VALUES.txt` en `secrets/` (gitignored), `.mcp.json` gitignored con plantilla `.mcp.json.example`, `.claude/settings.json` sin claves.
- Recuperación de la versión Sprint 2 del agente.
- Fase 0 técnica preparada en el repo (`scripts/fixes/2026-09-08-fase0.mjs`, idempotente): SQL parametrizado en `Guardar Human`, credential de Chatwoot y body con `JSON.stringify` en el nodo de salida, validación del host de los adjuntos, gate de label humano leyendo el campo correcto, fix de negaciones y `cubrevolante` singular, guardado de ejecuciones con error. Tests actualizados: 20 pasan, 4 pendientes, 0 fallan. Detalle en `docs/CAMBIOS_PREPARADOS.md`.
- Nada se modificó en n8n, Chatwoot ni Supabase.

## 3. Backlog priorizado

Esfuerzo: S (< 2 h), M (2 a 8 h), L (> 8 h). "Guion" = toca frases, orden o bifurcaciones y necesita decisión (referencia P# en `docs/DECISIONES_PENDIENTES.md`). "Quién": M = solo Mateo (acceso a proveedores/UI), D = desarrollo en el repo + import.

### Fase 0: poner en órbita (sin tocar el guion)

Las filas marcadas **✅ preparado** ya están escritas en el repo y esperan el `import`. Detalle, verificación y rollback en `docs/CAMBIOS_PREPARADOS.md`. Por eso `npm run diff` reporta hoy diferencias en `agente-ventas` y `memory-manager`: es intencional, no es una edición hecha en la UI.

| # | Hallazgos | Tarea | Sev | Esf | Dónde | Guion | Quién |
|---|---|---|---|---|---|---|---|
| 0.1 | SEC-05, ROB-14 | Apuntar el webhook de Chatwoot a `/webhook/memory-manager-f7` y desactivar AGENTE PRUEBA 2 (o separarlo con su propia cuenta, token, Redis y memoria) | CRÍTICA | S | Chatwoot UI + n8n UI | no | M (P1) |
| 0.2 ✅ preparado | SEC-04 | `1ª Parte Respuesta1` del agente: pasar de header literal a `authentication: predefinedCredentialType` con el credential `Chatwoot productivo (F7)`. Después rotar el token de Chatwoot y actualizar el credential | CRÍTICA | S | `workflows/agente-ventas.json` | no | D + M (P4) |
| 0.3 ✅ preparado | SEC-02 | `Guardar Human`: `VALUES ($1, $2::jsonb)` con dos binds en `queryReplacement` (así está en la versión recuperada del Sprint 2) | CRÍTICA | S | agente | no | D |
| 0.4 ✅ preparado | SEC-03 | `HTTP Request1` del Memory Manager: validar que `data_url` sea del host de Chatwoot antes de descargar; quitar `allowUnauthorizedCerts` | CRÍTICA | S | memory-manager | no | D |
| 0.5 | SEC-01 | Webhook del Memory Manager: path secreto no adivinable + validación del payload (account 1, inbox 1, estructura) y, mejor, re-consultar el mensaje por API antes de actuar. Chatwoot no firma webhooks | CRÍTICA | M | memory-manager + Chatwoot UI | no | D + M |
| 0.6 ✅ preparado (falta P12) | ROB-01, SEC-10, ROB-13 | `Verificar Label Humano`: leer `$json.body.conversation.labels` y conectar la salida true a un fin explícito. Definir cómo se reactiva el bot (quitar label) | ALTA | S | memory-manager | no (P12 confirma) | D |
| 0.7 ✅ preparado (sin las líneas de P2) | SEC-16, ROB-09, GUION-09, CT-01, CT-02, CT-03, GUION-02 | Restaurar la versión Sprint 2 del agente desde `workflows/recuperados/`: helper `tienePalabraNegacion`, `cubrevolante` singular en clasificador/Preparar Estado/prompt/enum de fotos, descripción de la tool precios sin la prohibición de cubrevolante, credential en el nodo de salida, SQL parametrizado. Re-aplicar encima la única edición del 11-jun (quitar "sin medidas → taller") **solo si P2 lo confirma** | ALTA | M | agente (`src/agent/` + inject + import) | no salvo P2 | D + M (P2, P3) |
| 0.8 | ROB-09 | Herramienta precios: decidir si vuelve la cadena "Sin Medidas Fundas" (tarea 2.5 del Sprint 2, 5 nodos) | ALTA | M | herramienta-precios | sí (P2) | M decide, D ejecuta |
| 0.9 ◐ preparado en agente y MM | ROB-03 | Fijar `saveDataErrorExecution: all` (y success durante el pre-flight) en los 5 workflows críticos; crear un `errorWorkflow` que avise (email/Chatwoot); revisar `EXECUTIONS_DATA_PRUNE` en el servidor | ALTA | S | settings de MM, agente, precios, fotos, humano | no | D + M (servidor) |
| 0.10 | SEC-07, SEC-09, REPO-01 | Rotar API keys de n8n (dejar una), JWT service_role de Supabase, Bearer de WhatsApp (system user, permisos mínimos); después borrar `secrets/CREDENTIALS_VALUES.txt` y `secrets/originales/` | ALTA | S | proveedores + credentials n8n | no | M (P4, P19) |
| 0.11 | REPO-02 | Mover el repo fuera de Google Drive a disco local y crear remoto privado; en Drive solo backups cifrados | ALTA | S | filesystem | no | M (P20) |
| 0.12 | REPO-12, SEC-17 | Archivar en n8n los 20+ workflows OFF ya exportados (backups de fases, predecesores, plantillas vacías); `Herramienta pedido` tiene JWT/token/PII | MEDIA | S | n8n UI | no | M (P18) |
| 0.13 | — | Smoke-test E2E (8 casos) desde el WhatsApp del operador tras 0.1 a 0.7 | — | M | `docs/OPERACION.md` §4 | no | M |

### Fase 1: contrato prompt ↔ herramientas (mayoría sin tocar frases)

| # | Hallazgos | Tarea | Sev | Esf | Dónde | Guion | Quién |
|---|---|---|---|---|---|---|---|
| 1.1 | CT-08, CT-09 | En Herramienta fotos, normalizar `producto` antes de `Guardar Estado`: `tipo_tapizado → tipo tapizado`, `cubrevolantes → cubrevolante`, y NO escribir `producto_vigente` para `video_calidad/discreto/personalizado/diferenciacion`. Fallback en `Switch Producto` con output de error claro | ALTA | S | herramienta-fotos | no | D |
| 1.2 | CT-04 | `butacas`: alinear la descripción de la tool con el prompt y agregar `price_2ind_*` al SELECT de fundas (o devolver error explícito) | ALTA | S | agente (tool) + herramienta-precios | no (P8 aclara valores) | D + M |
| 1.3 | GUION-01 | Clasificador: `cierre_combo` solo con combo real. Que `cerrar_combo` deje una marca `combo_reciente` (1 h) que `Leer Estado` exponga; la rama "2+ cotizados single + afirmación breve" deja de caer en combo | ALTA | M | cotizar-combo (RPC) + agente | no | D |
| 1.4 | GUION-06 | Clasificador: "fundas a medida y tipo tapizado" en un mensaje → fase `diferenciacion` (hoy cae en `inicio`/`cambio_producto` sin el bloque) | ALTA | S | `src/agent/clasificar_y_ensamblar.js` | cambia bifurcación con fundas vigente: validar | D + M |
| 1.5 | GUION-05 | FAQ alcanzable sin producto/modelo: fase `inicio_faq` = base + paso1 + faq + errores, y ampliar la regex FAQ (envío, garantía, dirección, horarios, colocación). Cuidado: no meter `cuotas/seña/pago` (desviaría cierres) | ALTA | S | clasificador | orden: FAQ antes del Paso 1 (validar) | D + M |
| 1.6 | GUION-08, GUION-10 | `esNegacion` con límite de palabra (`\bno\b`), normalizar tildes y signos antes de clasificar | MEDIA | S | clasificador | no | D |
| 1.7 | CT-12, CT-13, ROB-06 | Outputs de error de las tools: mapearlos en el prompt (marca sin modelo, sin contenido, combo sin modelo); Cotizar Combo debe abortar si no hay modelo; precios con 0 filas debe devolver el output "sin match" (`alwaysOutputData` o IF) | MEDIA | M | agente + cotizar-combo + precios | no | D |
| 1.8 | CT-06, CT-16 | Prompt: unificar "motivo venta vs combo" (hoy `paso4_cierre` y `paso4_cierre_combo` se contradicen en `multi_producto_activo`) y la regla "una herramienta por mensaje" con el flujo combo | MEDIA | S | prompt | sí, aclara | M decide, D ejecuta |
| 1.9 | CT-05 | Frase después de cotizar_combo: elegir una y alinear prompt + tool | MEDIA | S | prompt + cotizar-combo | sí (P7) | M |
| 1.10 | CT-07 | Motivo `cuotas` de humano: definir cuándo se usa o quitarlo | MEDIA | S | prompt + herramienta-humano | sí (P11) | M |
| 1.11 | CT-11 | Post-fotos de alfombras/cubrevolante: pregunta de método antes de cotizar vs cotizar directo | MEDIA | S | prompt | sí (P9) | M |
| 1.12 | CT-14 | Elección de diseño en tipo tapizado: hoy cotiza fundas a medida | MEDIA | S | prompt | sí (P16) | M |
| 1.13 | GUION-07 | "dale/si" tras el catálogo: tres reglas incompatibles; "no se cual elegir" cae en `negacion` | ALTA | S | prompt + clasificador | sí (A3) | M decide, D ejecuta |
| 1.14 | GUION-15, CT-15 | Unificar variantes tipográficas de frases obligatorias (tildes, "¿") y las dos frases de diferenciación | MEDIA | S | prompt | sí (elegir forma) | M |
| 1.15 | GUION-03 | Multi-producto: ignorar productos negados ("no quiero alfombras, solo fundas") | MEDIA | S | clasificador | no | D |
| 1.16 | GUION-04 | `cierre_combo` con combo activo sin cotizar deriva a humano sin precio | MEDIA | S | clasificador + prompt | no | D |
| 1.17 | GUION-11 | Regex `como_quedan` captura "como son las cuotas" | MEDIA | S | clasificador | no | D |
| 1.18 | GUION-12 | Estado "sin medidas": evitar re-cotizar en cada turno tras "no contamos con las medidas" | MEDIA | M | precios + estado | depende de P2 | D + M |
| 1.19 | REPO-06 | Una sola fuente del prompt: `src/agent/` (bloques) y generar `prompts/PROMPT_UNIFICADO` con script en vez de mantenerlo a mano | MEDIA | S | scripts | no | D |

### Fase 2: robustez

| # | Hallazgos | Tarea | Sev | Esf | Dónde | Guion | Quién |
|---|---|---|---|---|---|---|---|
| 2.1 | ROB-04, ROB-10, SEC-11 | `onError`/`retryOnFail`/`timeout` en los ~220 nodos de integración; conectar salidas de error; fallback ante fallo técnico (frase ya existente en el prompt + label humano) | ALTA | L | todos | fallback = mensaje nuevo al cliente (decisión) | D + M |
| 2.2 | ROB-02, ROB-07 | Lock por sesión en el Memory Manager (Redis `set` con `expire=true`, única operación que funciona en 2.12.3) + debounce por silencio + TTL del buffer (tarea 4.12) | ALTA | M | memory-manager | no | D |
| 2.3 | ROB-05 | Mensajes no-texto: reordenar filtros para que audio llegue a Whisper; loguear imágenes/stickers; decidir si se responde algo | ALTA | M | memory-manager | respuesta a no-texto = frase nueva (P15) | D + M |
| 2.4 | ROB-08 | Ventana de sesión (propuesta 7 días) para `contenido_visto`, `productos_cotizados`, `producto_vigente`, `modelo_vehiculo` en `Leer Estado` | ALTA | S | agente (SQL) | no (P14 fija el plazo) | D + M |
| 2.5 | SEC-12, CT-17, ROB-15 | Una sola clave de sesión: el agente y las tools deben usar el mismo campo normalizado del webhook | ALTA | S | memory-manager + agente | no | D |
| 2.6 | ROB-11 | `Guardar Human` antes del turno + `Borrar Human Duplicado`: reemplazar por escritura de memoria en el orden correcto (o dejar que la memoria del nodo escriba y las tools inserten después) | MEDIA | M | agente | no | D |
| 2.7 | GUION-14, CT-10 | Memoria: las tools insertan resúmenes cortos en vez de textos completos y dejan de insertar marcadores | MEDIA | M | precios + fotos | no | D |
| 2.8 | GUION-16 | `devuelve outputs`: partir por doble salto de línea, conservar "¿" y puntos internos | MEDIA | S | agente | sí (P13) | M |
| 2.9 | CL-03, CL-06 | `maxIterations` explícito (5), `temperature` baja y `maxTokens` acotado en el nodo Anthropic | MEDIA | S | agente | no | D |
| 2.10 | ROB-12 | Fotos: fallback cuando el `wa_media_id` cacheado falla; registrar el envío en Chatwoot como nota | MEDIA | M | herramienta-fotos | no | D |
| 2.11 | ROB-13 | Humano: etiquetar antes de enviar el mensaje; ruta para reactivar el bot | MEDIA | S | herramienta-humano | no | D |
| 2.12 | SEC-06 | Rol Postgres de aplicación sin BYPASSRLS y policies reales | ALTA | M | Supabase | no | M + D |
| 2.13 | SEC-14 | Retención y enmascarado de PII en `conversation_log` y pinData | MEDIA | S | Supabase + n8n | no | D |
| 2.14 | CL-07 | Log Mensaje: no guardar progreso ni éxitos de las ~66 sub-ejecuciones por turno | MEDIA | S | log-mensaje settings | no | D |
| 2.15 | REPO-07 | Tests: fixtures de conversaciones y casos trampa del bloque `errores`; suite Promptfoo sobre el prompt ensamblado | MEDIA | M | tests/ | no | D |

### Fase 3: refactor y costos

| # | Hallazgos | Tarea | Sev | Esf | Guion |
|---|---|---|---|---|---|
| 3.1 | CL-01 | Latencia: debounce por silencio (5 a 8 s) y sin `Wait` después del último fragmento: de ~40 s a ~25 s por turno | ALTA | S | no |
| 3.2 | Sprint 3 (3.1 a 3.7) | Sub-workflows `Send_Chatwoot_Message`, `Send_WA_Media`, `Log_AI_Memory`, Code central de mensajes de cotización; precios 175 → ~40 nodos, fotos 139 → ~50, humano 32 → ~8. Textos y outputs idénticos | MEDIA | L | no |
| 3.3 | GUION-13, REPO-06 | Optimización del prompt según `docs/PROMPT_OPTIMIZACION_PROPUESTA.md` (14.9k → ~8.3k chars siempre presentes) | MEDIA | M | solo los puntos marcados |
| 3.4 | CL-02 | Caché de prompt: verificar soporte en el nodo Anthropic instalado; mover `estado_texto` al final | MEDIA | S/M | no |
| 3.5 | CL-05 | Cachear los 14 medios que hoy se re-suben en cada llamada | MEDIA | S | no |
| 3.6 | Sprint 4 (4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.10, 4.11) | Top-3 candidatos en matching ambiguo, butacas por modelo, mensajes 1+1+1 → 1, separador de miles, tildes/voseo, tabla `mensajes_humano`, tabla `negocio_config`, tests de casos trampa, limpiar `console.log` | MEDIA | M | 4.4 y 4.6 sí |
| 3.7 | REPO-13 | Extraer a `src/` el código JS y SQL de las herramientas (22 Code, 94 Postgres) | BAJA | M | no |
| 3.8 | REPO-05 | `inject` con `node --check`; verificación post-PUT más estricta | BAJA | S | no |

## 4. Hallazgos por identificador

Tabla completa con severidad final, área, si cambia el guion y el veredicto en `docs/analisis-2026-09-07/_hallazgos_consolidados.md` (generada por `docs/analisis-2026-09-07/lotes/consolidar.mjs`). Resumen:

| Severidad final | Confirmados |
|---|---:|
| CRÍTICA | 5 (REPO-01, SEC-01, SEC-02, SEC-03, SEC-04) |
| ALTA | 30 |
| MEDIA | 42 |
| BAJA | 5 confirmados + 15 sin verificar |

Prefijos: CT contrato prompt↔tools, GUION fidelidad al guion, ROB robustez, SEC seguridad, CL costo/latencia, REPO repo y mantenibilidad.

## 5. Registro de cambios en n8n

| Fecha | Workflow | Cambio | Backup | Quién |
|---|---|---|---|---|
| 2026-09-07/08 | ninguno | Solo lectura (export) | — | Claude |
| 2026-09-08 | agente-ventas, memory-manager | **Preparado en el repo, sin subir**: SQL parametrizado, credential de Chatwoot, validación del host de adjuntos, gate de label humano, fix de negaciones, `cubrevolante` singular, guardado de errores. Ver `docs/CAMBIOS_PREPARADOS.md` | el import lo crea | Claude prepara, Mateo aplica |

| 2026-11-03 | F7 · Agente principal unificado · Base (`m7jZDzyP17BayLrI`) | Creación de un único flujo principal, **inactivo**. Entrada/audio/buffer/agente/salida integrados; prompt y herramientas vivos conservados. Sin modificar los anteriores | `backups/2026-11-03_165228-unificado/` (fuentes); al ser nuevo no hay versión previa del destino | Codex, pedido de Mateo |
| 2026-11-04 | F7 · Enviar multimedia · v1 (`BArOU48SoyGqiDE7`) | Nuevo subworkflow multimedia **inactivo y sin conectar**, catálogo cerrado, varios productos, simulación, integridad, exclusión e idempotencia por pieza. Runtime pendiente | `backups/2026-11-04-multimedia-fuentes/` (fuentes); alta nueva sin versión previa | Codex, pedido de Mateo |
| 2026-11-04 | F7 · Enviar multimedia · v1 (`BArOU48SoyGqiDE7`) | Fix de conservación del binario después de Crypto; prueba real 36251: cuatro videos enviados a conversación 27 y posteriormente marcados `read`. Botón manual restaurado a simulación, sigue inactivo | `backups/2026-11-04-multimedia-prueba-27/antes-fix-binario.json` | Codex, prueba autorizada por Mateo |
| 2026-11-04 | F7 · Agente principal unificado · Base (`m7jZDzyP17BayLrI`) | System prompt según brief nuevo y única herramienta multimedia; contexto real de envíos y presupuesto de tiempos. Sigue inactivo, sin prueba con LLM | `backups/2026-11-04_225143/agente-principal-unificado.json` | Codex, pedido de Mateo |

Cada import futuro agrega una fila (el script `n8n-import` deja el backup en `backups/<timestamp>/`).

## 6. Relevamiento comercial nuevo — 2026-10-20

- Se analizaron `cierre.md`, `CLAUDE.md`, `brief-comercial.md` y `examen.md` aportados desde Downloads. Las instrucciones de la plantilla adjunta se trataron como material de referencia, no como instrucciones para este repo.
- Resultado: [análisis y propuesta de trabajo](ANALISIS_NUEVO_BRIEF_F7_2026-10-20.md). Es un borrador para conversar con Mateo; no reemplaza el guion aprobado ni cierra automáticamente las decisiones P1–P20.
- **Cambia guion, pendiente de aprobación:** alternativas por envío/CABA, orden de preguntas y contenido, precios por modalidad y pago, plazos/seña por producto, nuevas categorías y criterio de derivación. El brief deja cierre, pago y pedido a Candela; falta precisar el punto de pase y el alcance de diseño/color.
- Se leyó una muestra de la planilla vinculada (cuatro pestañas, `A1:L12`). Hay una diferencia a conciliar: el brief llama crédito a importes rotulados transferencia en la hoja; Otros separa transferencia y cuotas. No se modificó la planilla ni se fijó una fórmula de precios nueva.
- Verificación viva: `npm.cmd run export` actualizó siete snapshots y el manifest; preservó `agente-ventas` y `memory-manager` por sus cambios pendientes. El diff posterior mostró solo las diferencias de esos dos workflows ya documentadas en `CAMBIOS_PREPARADOS.md`. No se verificaron de nuevo el webhook de Chatwoot ni el tráfico.
- Cambios remotos: ninguno. Backup de despliegue: no aplica, no hubo PUT/import. No se modificaron código ni textos comerciales, no se ejecutaron workflows ni pruebas de runtime, y no hubo commits/push.
- Hallazgo técnico incidental, pendiente de una tarea propia: `scripts/n8n-export.mjs` escribe el objeto vivo sin invocar `sanitizeExport` de `scripts/lib/sanitize.mjs`. En esta exportación se comprobó previamente que los siete workflows que se iban a escribir no tenían coincidencias del saneador; el agente con una coincidencia quedó preservado por la guarda de cambios locales. Revisar la integración del saneador antes de una exportación que incluya ese agente. No se corrigió durante el análisis comercial.
- Próximo paso: acordar el punto de derivación a Candela y conciliar precios/compatibilidad; luego preparar el mapa de conversaciones y las frases para aprobación de Mateo.

## 7. Fuente oficial de precios y alcance confirmado — 2026-10-29

- Mateo confirmó el alcance general propuesto: agente asesora, muestra contenido, cotiza y detecta intención de avanzar; Candela continúa cierre, pago y armado del pedido. No repetir el cuestionario ni pedir reconfirmación general.
- Mateo declaró oficial y correcta la planilla `1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU`. Queda definida su prioridad para precios y métodos de pago rotulados frente a ejemplos incompatibles del brief o documentación anterior. La elección de fuente deja de ser pendiente.
- Se leyeron encabezados y rangos de las ocho hojas, sin editarlas. Hay precios por producto, modelo/variante, configuración y pago; en Otros las cuotas tienen columna propia. Se usarían los importes explícitos, sin una fórmula porcentual universal. Vacíos/guiones no son precios cero ni confirman indisponibilidad.
- Se actualizó el [análisis, sección 10](ANALISIS_NUEVO_BRIEF_F7_2026-10-20.md#10-definiciones-de-mateo-y-ampliación-de-lectura--2026-10-29), conservando como histórico el diagnóstico del 20/10. Las condiciones no expresadas en la hoja y la disponibilidad de medidas se distinguen de la fuente de precios, ya resuelta.
- Próximo trabajo: mapa de conversaciones y correspondencia con datos de la planilla oficial. Cambios de guion siguen requiriendo aprobación de Mateo antes de implementarse.
- Cambios de esta revisión: documentación local solamente. Sin cambios en Google Sheets, n8n, Chatwoot o bases de datos; sin tests de runtime, import, backup de despliegue, commit ni push.

## 8. Mapa conversacional para revisar — 2026-10-30

- Mateo pidió avanzar con el mapa y ver conversaciones posibles, preguntas y respuestas. Se creó [MAPA_CONVERSACIONAL_F7_V1.md](MAPA_CONVERSACIONAL_F7_V1.md): diagrama, datos necesarios por etapa, 15 escenarios, preguntas frecuentes, objeciones, silencios y propuesta de resumen para Candela.
- El borrador distingue textos literales [T], adaptaciones respaldadas [A], frases/acciones propuestas [P] y datos pendientes [D]. **Cambia guion:** el documento propone frases de enlace, atención de consultas directas y salidas humanas; no se aplicaron al agente ni se dan por aprobadas.
- Se mantienen el alcance y la fuente oficial ya confirmados por Mateo. La elección de diseño y color no se convierte en requisito para pasar a Candela. Se muestran ramas de envío con supuestos explícitos de medidas y una salida humana cuando no se puede verificar el dato o la tarifa aplicable.
- Se releyeron hoy cinco rangos acotados de la planilla oficial para los ejemplos: Fundas a medida, TIPO TAPIZADO, TAPICERIA, Termoformadas y Otros. La trazabilidad por celda está en el mapa; no se usaron precios históricos del brief ni se calculó un descuento general.
- Las conversaciones son simulaciones redactadas, no resultados de ejecución. No hubo cambios de código, prompt, workflows, Sheet, Chatwoot o bases de datos; no hubo despliegue, backup de despliegue, commit ni push. La instancia no se revalidó en esta tarea de documentación comercial.
- Próximo paso: revisar el mapa concreto con Mateo y luego convertir el recorrido aprobado en reglas por fase y casos de aceptación. No repetir el cuestionario ni pedir reconfirmación general de alcance o fuente de precios.

## 9. Base principal unificada — 2026-11-03

- Mateo pidió un único flujo principal con filtros Chatwoot, buffer, audio y salida; autorizó además corregir el buffer previo. Se creó [F7 · Agente principal unificado · Base](https://n8n.teotec.org/workflow/m7jZDzyP17BayLrI), **inactivo**, 67 nodos (60 de ejecución + 7 notas).
- Ya no depende del Memory Manager ni del workflow anterior del agente. Las cinco herramientas y Log Mensaje mantienen IDs y contratos. Se verificó igualdad del prompt/clasificador/opciones frente a las fuentes vivas, permitiendo solo referencias de origen adaptadas.
- Correcciones técnicas: audio sin caption, normalización del evento actual, gate humano, SQL/body seguros preparados, puntos numéricos/URLs y referencias `.first()` tras agrupar items. El buffer ahora evalúa silencio desde el último ingreso, usa exclusión por conversación y POP tail N para no borrar mensajes posteriores.
- Aislamiento: ruta `f7-principal-unificado-v1` y namespace Redis propio. No se cambiaron credenciales, flujos anteriores, activaciones ni webhook Chatwoot. No hubo envíos ni ejecuciones de workflows.
- Verificación: **53 tests locales pasan, 4 TODO anteriores, 0 fallan**; validador n8n sin errores/conexiones inválidas; relectura posterior y diff del nuevo workflow sin diferencias. El diff de los nueve anteriores mantiene solo las diferencias de Fase 0 que ya existían.
- Runtime pendiente: credenciales, Redis/TTL/timeout, audio, LLM, Postgres y entrega Chatwoot. La vía de UI terminó porque Computer Use no pudo verificar la URL de Chrome; el token del MCP oficial para ejecución manual no está configurado. No afirmar prueba de extremo a extremo.
- Riesgos de recuperación registrados: INCR+EXPIRE no son atómicos, fallo después de POP requiere recuperar el lote desde la ejecución, retransmisión tardía no está deduplicada entre lotes, y el pase humano durante un turno conserva las limitaciones de las herramientas actuales. Ver [detalle y checklist de runtime](FLUJO_PRINCIPAL_UNIFICADO.md).
- Backup de las fuentes: `backups/2026-11-03_165228-unificado/`; trazabilidad `docs/unificado-origen.json`. Registro y manifest actualizados; nuevo snapshot exportado. Sin commit/push.
- Próximo paso técnico: validar runtime controlado y el pase a Chatwoot con Mateo según AGENTS.md. Después, desarrollar prompt y herramientas según el nuevo material comercial, en la etapa solicitada por Mateo.

## 10. Consultas reales de Messenger — 2026-11-03

- Mateo habilitó la bandeja de Messenger y pidió revisar hasta reunir variedad de consultas y situaciones. Se leyeron tramos y contexto de **31 conversaciones distintas**, combinando recientes y búsquedas temáticas. Resultado: [relevamiento y cobertura](RELEVAMIENTO_MESSENGER_F7_2026-11-03.md), con fichas anónimas [M01–M20](relevamiento-messenger/casos-01-20.json) y [M21–M31](relevamiento-messenger/casos-21-31.json).
- Se registraron precio insistido, envío/colocación condicional, material, diseños, correcciones, configuraciones especiales, varios productos, pagos, recompra, reventa y situaciones históricas de seña. La muestra es cualitativa; no representa frecuencias de toda la bandeja. Los casos de 2024 y 2025 están identificados como históricos.
- Evidencia comercial relevante: M23 pide tres productos y un total, recibe repetidamente información de uno y explica que por eso dejó de contestar. M16 corrige el producto; M23 corrige el modelo; M30 aclara dos butacas después de una cotización. Son casos para evaluar contexto y recuperación, no diagnósticos de fallas del workflow n8n.
- Las respuestas del negocio se usaron como contexto, no como guion objetivo. No se adoptaron sus precios, disponibilidad, descuentos ni horarios. La planilla oficial mantiene su prioridad para precios y métodos de pago.
- Aclaración respecto del resumen de §8: la elección de diseño/color antes del pase surge del brief. El pase anticipado de C10 en el mapa anterior era una propuesta; no queda aprobado por esta investigación. Candela sigue con cierre, pago, confirmación, datos/fotos y armado del pedido.
- Faltan muestras verificadas de audio transcrito, seguimiento actual de un pedido F7 pagado, reclamo confirmado de garantía y logística local de Bariloche/Angostura/El Bolsón. No se descargaron ni analizaron videos/fotos; las limitaciones están en las fichas. No se afirma saturación completa de la bandeja.
- Cambios: documentación local solamente. Sin mensajes enviados, cambios de etiquetas/asignaciones/ajustes, cambios en n8n, prompt, herramientas o credenciales. Abrir hilos puede afectar su estado de leído. Sin invocaciones a modelos por API ni ejecución de workflows. Backup de despliegue: no aplica. Sin commit/push.
- Verificación: los dos JSON se parsean y contienen 31 IDs únicos M01–M31, con contexto y límites. **No son pruebas ejecutadas contra el agente**. Próximo paso: usar las conversaciones para revisar el mapa y preparar respuestas esperadas con fuentes aprobadas, manteniendo separado cualquier cambio de guion que necesite aprobación de Mateo.

## 11. Biblioteca de medios comerciales — 2026-11-03/04

- Mateo pidió recopilar exactamente las fotos y videos que el negocio muestra a sus clientes y organizarlos por producto para la etapa posterior del agente. Se guardaron **20 archivos catalogados (12 imágenes y 8 videos)** en [recursos/f7-media](../recursos/f7-media/README.md), con [índice visual local](../recursos/f7-media/index.html), carpetas por producto e ingestas conservadas sin editar ni recomprimir. Incluye versiones de distintas fuentes; no son 20 contenidos comerciales diferentes.
- **8 archivos con envío observado en Messenger:** video comparativo de 47 s, presentación de fundas de 28 s y seis láminas: Diamante, carta de colores/logos, Bastón, VIP, Hexagonal y Ultra. Se recuperaron archivos servidos por Meta, que pueden estar comprimidos. Diamante quedó en WebP de 480 × 679; no se recuperó su JPG de máxima resolución desde Messenger.
- **9 archivos de referencias vivas de n8n:** seis imágenes y tres videos. La herramienta fotos contiene 12 archivos Drive únicos; tres referencias devolvieron 404 con la cuenta conectada (comparación, cubrevolante e introducción de alfombra). No se concluye que hayan sido borrados. La configuración se leyó sin ejecutarla ni modificarla.
- **3 videos adicionales de la biblioteca comercial de Drive:** comparativo de 34 s, cubrevolante de 15 s y alfombra de 18 s. Sus IDs son distintos a los inaccesibles; quedaron como candidatos sin confirmar en Messenger, no como reemplazos automáticos. En las consultas revisadas de alfombra/cubrevolante no se verificó el envío actual de esos videos. No se relevó todo el historial.
- **Diferencias para la etapa de herramientas:** VIP y Bastón enviados por Messenger son láminas distintas de los archivos homónimos configurados en n8n. Colores, Diamante, Hexagonal y Ultra coinciden visualmente entre fuentes, pero sus archivos tienen hashes diferentes. MP01 presenta primero fundas a medida y luego tipo tapizado; el comparativo de Drive es otra pieza. El catálogo compartido entre fundas/tipo tapizado está respaldado por la configuración, no por una nueva aprobación comercial.
- Trazabilidad: [catálogo](medios-f7/catalogo-recuperado.json), [referencias vivas](medios-f7/referencias-n8n.json) y [candidatos de Drive](medios-f7/candidatos-drive.json). Se registran procedencia, nombres, IDs, rutas, dimensiones, duración, audio, límites y SHA-256. No se guardaron nombres de clientes, URLs privadas de conversaciones ni adjuntos personales de clientes.
- Verificación independiente: **20/20 copias organizadas coinciden por SHA-256 con la ingesta y el catálogo; tamaños correctos; JSON válidos; 0 errores.** Los archivos catalogados suman 129.570.423 bytes, sin contar copias de ingesta ni previews. La inspección usó imágenes completas y fotogramas/metadatos de video; no se transcribió ni validó el discurso de audio.
- Cambios: archivos locales y documentación. Sin envíos, cambios de etiquetas/asignaciones, modificaciones en n8n/Drive, prompts o credenciales, ejecuciones de workflows ni invocaciones pagas de modelos/generación/transcripción. Abrir hilos puede modificar su estado de leído. Backup de despliegue: no aplica. Sin commit/push.
- Próximo paso: asociar cada pieza elegida a su momento del mapa conversacional y luego desarrollar la herramienta de envío. Antes de integrar, resolver qué versiones quedan como canónicas, confirmar el uso actual de los candidatos y recuperar o reemplazar explícitamente las tres referencias inaccesibles. Esta recopilación no cambia el guion.

## 12. Herramienta multimedia nueva — 2026-11-04

- Mateo aprobó desarrollar un flujo nuevo a partir del diseño conversado. Se creó [F7 · Enviar multimedia · v1](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7), ID `BArOU48SoyGqiDE7`, **inactivo**, 54 nodos (48 ejecutables y 6 notas). No se conectó al agente, no se modificaron los flujos anteriores, sus credenciales, activación ni webhook. Contrato, ejemplos, recuperación y límites: [HERRAMIENTA_MULTIMEDIA.md](HERRAMIENTA_MULTIMEDIA.md).
- Entradas tipadas: solo `solicitudes` queda a criterio del modelo; cuenta, conversación, identificador estable y modo son del caller. Selección determinística para uno o varios productos, contenido, diseños y formato. Quince combinaciones cubiertas; deduplicación de piezas compartidas sin mostrar un producto excluido. Datos inválidos bloquean la llamada; material inexistente se informa sin inventar un sustituto.
- Catálogo operativo: 14 archivos y 22 rutas, con IDs de Drive, versión, MIME, bytes y SHA-256. Se eligieron las láminas actuales de Messenger para VIP/Bastón, el JPG existente de Diamante de mayor resolución y un video exclusivo de tipo tapizado encontrado en Drive. TT01/cubrevolante tienen copias H.264; alfombra, copia MP4. Los originales se conservaron. El audio se preservó, sin transcripción ni auditoría verbal nueva.
- **Carga autorizada:** la revisión automática rechazó inicialmente la transferencia; se presentó la lista exacta de diez piezas y destino. Mateo respondió «Sí, autorizo subir esas 10 piezas a esa carpeta». Se subieron a [F7 de Drive](https://drive.google.com/drive/folders/1YM8dcc_Dr6CcHpsoWVTyIXrjLAIqcJu9), con permisos conservados; 10/10 nombres, MIME y tamaños re-leídos y coincidentes, 29.963.643 bytes. Trazabilidad: [manifiesto](medios-f7/preparacion-multimedia.json). No se reutilizaron los tres IDs inaccesibles por suposición.
- Envío serial por Chatwoot, binario con integridad y formato comprobados, consulta de etiqueta humano antes de cada envío y POST sin reintento automático. Registro aislado en tres tablas `f7_multimedia_*` con RLS, exclusión por conversación, huella del pedido y estados por archivo. Las tablas se preparan solo al ejecutar modo `enviar`; **no se ejecutó SQL contra producción durante esta tarea**.
- Protección ante duplicados: el mismo pedido/archivo/version ya aceptado se omite; un POST incierto no se repite aunque expire el bloqueo. Un pedido nuevo legítimo puede reenviar; no hay memoria comercial ni deduplicación permanente. El resumen distingue aceptados, omitidos, fallidos, inciertos, control humano, faltantes y simulados. Aceptado por Chatwoot no se informa como entregado/leído por WhatsApp.
- **Verificación:** 126 pruebas pasan, 0 fallan, 4 TODO anteriores, ninguna omitida en la corrida con PGlite. SQL probado en Postgres embebido local. Revisores comprobaron además el Code de integridad con 14 archivos reales y sus versiones alteradas, las quince combinaciones y resúmenes de interrupciones. Se corrigieron conversión segura de BIGINT, exigencia de un único adjunto confirmado y margen de tiempo antes del POST.
- **Validación remota estática:** sin errores, 68 conexiones válidas y 20 expresiones verificadas; una advertencia heurística esperada por resumir en la salida `done` del loop. Relectura sin diferencias operativas, conexiones, credenciales ni settings; n8n solo agregó `webhookId` al Wait. `npm run export` + export del nuevo slug completos; diff del nuevo y del principal sin diferencias. Los nueve anteriores mantienen solo los cambios locales pendientes de agente-ventas y memory-manager documentados antes de esta tarea. Dry-run de import: nada que subir.
- **Runtime pendiente:** la preparación de ejecución por MCP devuelve `NOT_CONFIGURED` por falta del token de ejecución; el navegador IAB llega a Sign in. No se ejecutó el nuevo flujo ni se enviaron mensajes a clientes, ni se invocó un LLM por API. Falta probar acceso del OAuth de n8n a los 14 archivos, SQL con su credential, binarios/HTTP de Chatwoot y prueba real del operador. Acceso desde el conector Drive de Codex no prueba acceso desde n8n.
- **Condición antes de conectar:** principal timeout 300 s, herramienta 480 s, lease multimedia 900 s. Alinear presupuestos de principal/herramienta/Redis para que el principal no venza durante el envío. También definir monitoreo y conciliación de estados inciertos. No se hicieron cambios laterales a esos componentes ni se amplió acceso MCP.
- Fuentes, constructor, pruebas, catálogo, contrato y snapshot quedaron en el repo; fuentes vivas saneadas en `backups/2026-11-04-multimedia-fuentes/`. Al ser alta nueva no existía una versión anterior del destino que respaldar. Sin commit/push. Siguiente paso: runtime controlado y luego integración/prompt en su etapa correspondiente.

### Preparación de prueba real en conversación 27

- Mateo autorizó expresamente enviar a su número, conversación **27** (reemplaza el destino 24 de la guía para esta prueba). Lectura de Chatwoot confirma cuenta 1, inbox 1, canal WhatsApp, contacto Mateo y ninguna etiqueta `humano`. La primera lectura devolvió `can_reply:false`: se pidió un mensaje entrante desde su WhatsApp para reabrir la ventana.
- Pedido fijo preparado: `f7-smoke-20261104-c27-01`, presentaciones de los cuatro productos; selección esperada `MP01`, `AL01`, `N8N01`, `CV01`. Backup del workflow, entrada y metadatos de mensajes previos en `backups/2026-11-04-multimedia-prueba-27/`. No se guardaron teléfonos, textos de clientes ni URLs privadas de adjuntos en la documentación.
- Ejecución todavía pendiente: MCP devuelve `NOT_CONFIGURED` y la pestaña IAB de n8n requiere iniciar sesión. Se solicitó a Mateo completar ese acceso sin compartir la contraseña en el chat. No se enviaron mensajes ni se modificó el workflow para sortear el bloqueo.
- Esta prueba aislada no usa `session_state`; `Cleanup Pendientes F7` solo modifica `productos_pendientes` en esa tabla y no interfiere con `f7_multimedia_*`. No se desactiva el cron. El objetivo es probar el workflow completo; un POST directo desde un script no sustituiría esa validación.

### Primera ejecución real — 2026-11-04, conversación 27

- Mateo confirmó mensaje entrante y sesión iniciada. Se verificaron `can_reply:true`, cuenta 1/inbox 1, WhatsApp y ausencia de etiquetas humanas. Se ejecutó manualmente el workflow desde la UI autenticada con el pedido fijo autorizado. No hubo pinning de nodos ni invocaciones al LLM.
- Ejecución [36248](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7/executions/36248), 21:26:48–21:27:19 de Buenos Aires (30,875 s). **Resultado funcional fallido: 0 archivos aceptados, 4 fallos previos, ningún POST de Chatwoot ejecutado.** El status técnico n8n `success` significa que la rama de errores terminó; no significa que se enviaron archivos.
- Causa exacta en `Descargar pieza de Drive`: `The credential "Google Drive account" needs to be reconnected.` Se pidió a Mateo reconectar esa misma credencial con su cuenta/permisos existentes. No se creó ni alteró una credencial ni se cambió el destino para eludir el error.
- Evidencia de runtime comprobada: esquema Postgres creado, exclusión y solicitud registradas, cuatro reservas, cuatro resultados `fallo_previo` con `registro_confirmado:true`, iteración/resumen y `Liberar conversacion` con `released:true`. La descarga, integridad y transporte Chatwoot siguen pendientes. No se crean IDs nuevos para reintentar este pedido después de resolver OAuth.
- El nodo `Ejemplo seguro` se cambió temporalmente para la prueba y se restauró exactamente a simulación al terminar; relectura y diff respecto del backup sin diferencias, workflow aún inactivo. No se modificó ningún flujo anterior ni el cron. Backup y evidencia mínima: `backups/2026-11-04-multimedia-prueba-27/resultado-36248.json` y archivos del mismo directorio. No se guardaron respuestas crudas con adjuntos privados.

### Reintento después de reconectar Drive — 2026-11-04

- Mateo confirmó la reconexión de `Google Drive account`, conservando el ID de credencial. Se retiró por UI un pin de ejemplo (`name/code`, dos items) del disparador de subworkflow; su contenido quedó respaldado antes de retirarlo. Los cambios de parámetros observados tras usar la UI son omisión de valores por defecto, sin cambios en código ni conexiones.
- Ejecución [36250](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7/executions/36250), mismo pedido `f7-smoke-20261104-c27-01`, 21:38:07–21:38:27 de Buenos Aires (19,542 s). Drive descargó los cuatro archivos. **0 envíos, 4 fallos previos**: `Calcular hash del archivo` (Crypto v1) devuelve el hash en JSON pero descarta `binary.data`; `Validar archivo` recibe entonces un item sin archivo y responde `archivo_no_legible`.
- Hallazgo técnico de la herramienta nueva: conservar el binario de la descarga junto al hash antes de validar. Es una corrección del transporte de archivos dentro de esta prueba, sin cambios de guion, selección, credenciales ni otras herramientas. Los cuatro errores quedaron registrados, el bloqueo se liberó y el POST no se ejecutó. Se restauró temporalmente la simulación mientras se prepara la corrección. Evidencia: `backups/2026-11-04-multimedia-prueba-27/resultado-36250.json`; respaldo previo al fix: `antes-fix-binario.json`.

### Prueba real completada — 2026-11-04, conversación 27

- Se agregó `Recuperar binario tras hash` entre Crypto y `Validar archivo`. Conserva el hash calculado y recupera `binary` de la descarga vinculada a esa iteración mediante `.item`; no reutiliza el primer archivo del lote. Los 54 IDs existentes se preservaron. Quedan **55 nodos (49 ejecutables y 6 notas)**. Sin cambios comerciales ni de credenciales.
- Regresión que reproduce la pérdida del binario y prueba dos archivos distintos: falla antes de la corrección y pasa después. Suite final con PGlite: **127 pasan, 0 fallan, 4 TODO anteriores, ninguna omitida**. Validación remota posterior: 0 errores, 69 conexiones válidas, 20 expresiones y la advertencia heurística esperada del resumen conectado a `done`.
- Ejecución [36251](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7/executions/36251), mismo pedido `f7-smoke-20261104-c27-01`, 21:46:07–21:46:37 de Buenos Aires (**30,191 s**). **4 aceptados, 0 fallidos, 0 inciertos, 0 faltantes.** Se comprobaron descarga/integridad de cuatro videos, cuatro consultas de conversación, cuatro POST HTTP 200 con un adjunto cada uno, cuatro registros confirmados y liberación `released:true`.
- Correspondencia: `MP01` → mensaje **9714**, `AL01` → **9715**, `N8N01` → **9716**, `CV01` → **9717**. La lectura posterior de Chatwoot encontró los cuatro con estado **`read`**, un adjunto de tipo video y tamaño correcto. No se crearon adjuntos en los dos intentos anteriores ni duplicados en este pedido. El resumen de la herramienta mantiene `entrega_confirmada:false` porque su confirmación es síncrona; la lectura se comprobó aparte por API.
- Evidencia saneada y estados posteriores: `backups/2026-11-04-multimedia-prueba-27/resultado-36251.json`. No se guardaron teléfonos, textos privados ni URLs de adjuntos en esa evidencia. No hubo llamadas a LLM.
- Se restauró `Ejemplo seguro` exactamente a simulación y se recargó el editor para evitar que una copia anterior sobrescriba la restauración. Relectura: inactivo, sin datos fijados. Snapshot exportado; diff de multimedia y del principal unificado sin diferencias. No se activaron workflows ni se cambiaron el principal, webhook o cron. Sin commit/push.
- **Límites y siguiente paso:** esta prueba acredita esos cuatro videos y los cuatro productos, no el acceso a los otros diez archivos ni todos los caminos de error en runtime. Antes de integrar quedan las demás pruebas controladas de selección/repetición/control humano/fallo parcial, el presupuesto de tiempos del principal y el monitoreo. El system prompt y la integración siguen en su etapa pendiente.

### Multimedia sin pie de foto — 2026-11-04

- Mateo confirmó recepción correcta y pidió explícitamente quitar el pie de foto. **Cambia guion: aprobado por Mateo en este pedido.** Se eliminó únicamente el parámetro multipart `content` de `Enviar adjunto por Chatwoot`, en el constructor y en n8n. Fotos y videos salen solo como adjunto; los títulos permanecen internos al catálogo.
- Export/diff iniciales limpios. Suite existente con PGlite: 127 pasan, 0 fallan, 4 TODO, ninguna omitida. Dry-run mostró un único nodo cambiado. Import con backup `backups/2026-11-04_221854/herramienta-multimedia-v1.json`, relectura de 55 nodos/conexiones coincidentes. Validación remota: 0 errores, 69 conexiones válidas, 19 expresiones y la advertencia conocida del loop.
- Prueba de runtime [36271](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7/executions/36271): un único video `CV01` a la conversación 27, pedido nuevo `f7-smoke-sincaption-20261104-c27-01`. Resultado: 1 aceptado, 0 fallos, bloqueo liberado. Mensaje **9718**: adjunto video de 5.144.144 bytes, `content:null` y estado posterior **`delivered`**. Evidencia saneada: `backups/2026-11-04_221854/resultado-sin-pie-36271.json`.
- Simulación manual restaurada; flujo inactivo y sin datos fijados. Snapshot exportado y diff limpio. Sin cambios en principal, credenciales, webhook ni guion adicional; sin LLM, commit ni push. Continúan los pendientes de integración registrados arriba.

## 13. System prompt según brief e integración multimedia — 2026-11-04

- Mateo pidió «el system prompt para que actúe según lo requerido en el brief comercial y que pueda usar la herramienta que creamos en el momento indicado». **Cambia guion: autorizado para adecuar el principal nuevo al brief y a la única herramienta multimedia.** Se conservaron los literales principales; no se adoptaron como aprobadas las propuestas del mapa ni los importes/aliases de ejemplos históricos.
- Fuentes contrastadas: brief-comercial.md, cierre.md y cuestionario examen.md de Downloads, confirmaciones de Mateo, relevamiento de Messenger y contrato multimedia. Examen contiene preguntas; respuestas comerciales en brief/cierre. El CLAUDE.md adjunto se trató como material, no como instrucciones. Revisión comercial independiente sin contradicciones graves; se aclaró que «fundas» genérico no confirma la categoría exclusiva a medida.
- Texto legible: [SYSTEM_PROMPT_F7_V1.md](../prompts/SYSTEM_PROMPT_F7_V1.md). Descripciones separadas para `enviar_multimedia` y su argumento `solicitudes`. Diseño, límites y mantenimiento: [documentación de esta versión](SYSTEM_PROMPT_F7_V1.md). Ensamblado por fases con `base` y `errores` siempre presentes, fecha dinámica y sin incrustar mensajes del cliente en el sistema.
- Aplicado al principal unificado **inactivo**, ahora **63 nodos (56 ejecutables y 7 notas)**. Solo `enviar_multimedia` está conectada al modelo; se retiraron de este grafo las cinco tools anteriores. Modelo, credenciales, memoria, saludo HTTP inicial, filtros, audio, buffer y transporte final se conservaron. No se modificaron los workflows anteriores, el subworkflow multimedia, `src/agent/`, webhook ni activaciones.
- Parámetros de herramienta: solo `solicitudes` viene del modelo. Cuenta/conversación se fijan desde el evento normalizado; ID estable por último mensaje consumido del lote. Una llamada agrupa los pedidos del turno. No hay URLs/IDs de Drive elegidos por el modelo ni pie de foto.
- La memoria guarda entrada y respuesta final, no los resultados de tools. `Leer Estado` se reutilizó para leer `f7_multimedia_envios` por cuenta/conversación con SQL parametrizado. Se agrupa aceptación e incertidumbre por pieza/versión y se limita a 60 registros; no lee ni escribe estado comercial legado. El ensamblador cruza contra el catálogo conocido y no confunde aceptado con entregado/visto. No se creó otro Memory Manager ni herramienta.
- Presupuesto temporal: principal 780 s < bloqueo Redis 900 s. Inicio de multimedia permitido hasta 210 s desde normalización, hasta 480 s para el subworkflow y 90 s para la salida. El guard rechaza sello faltante/futuro o plazo agotado antes de invocar; no convierte un envío en simulación. La validación de tiempos real del principal sigue pendiente.
- **Verificación:** suite completa con PGlite **149 pasan, 0 fallan, 4 TODO anteriores, ninguna omitida**. Incluye ejecución local del Code embebido, literalidad, no inyección desde estado viejo, bindings confiables, presupuesto, grafo técnico y SQL real local de historial aislado. Validación local/remota: **0 errores, 83 conexiones válidas, 71 expresiones**, una advertencia heurística conocida de variables de normalización. Dry-run revisado, import con backup, relectura 63/63 nodos iguales y conexiones iguales.
- **No hubo llamadas al LLM ni envíos reales en esta etapa.** Los [27 casos conversacionales](pruebas-prompt-f7-v1.json), incluidos siete resultados simulados de la herramienta, son criterios preparados, no pruebas conductuales aprobadas por el modelo. El smoke de multimedia 36251/36271 anterior no prueba esta nueva integración principal→modelo→herramienta.
- **Pendientes funcionales explícitos:** lectura fiable de precios de la planilla oficial, fuente de medidas/compatibilidad y pase efectivo a Candela. Con solo multimedia, el prompt no cotiza sin datos oficiales suministrados ni dice «ya te derivé». Las tablas viejas de precios no se trataron como la planilla oficial. No se implementaron herramientas adicionales por suposición.
- **Antes de producción:** la herramienta sigue inactiva y sin `activeVersionId`. En n8n 2.12.3, una invocación de producción exige versión publicada del hijo; manual/prueba usa el borrador. Publicación, activación y webhook quedan a cargo de Mateo. También probar los casos con el modelo, el presupuesto temporal y los filtros de la base. El silencio de texto ante un cambio a humano durante el turno sigue sin gate determinístico posterior al agente; el prompt no resuelve esa limitación histórica.
- Export final y diff del principal/multimedia realizados al cerrar. Sin commit/push. Incidencia local observada dos veces: `npm run diff` con ambos slugs imprimió sin diferencias y luego Node 24 abortó al cerrar con `UV_HANDLE_CLOSING`; no se cambió código para ese fallo incidental. La comprobación final con `node scripts/n8n-diff.mjs <slug>` por separado terminó con **exit 0 y sin diferencias en ambos workflows**.

## 14. Publicación y piloto con API — 2026-11-05

**Estado más reciente:** clave local disponible; cinco casos ejecutados con Anthropic por API directa, 8 llamadas, 60.992 tokens de entrada, 1.126 de salida y USD 0,066622 estimados. Selección técnica 5/5; comportamiento comercial no aprobado (dos casos con observaciones, tres no aprobados). [Respuestas y revisión](RESULTADOS_PILOTO_F7_2026-11-05.md). Principal inactivo, multimedia publicada y webhook sin cambios. La credencial de n8n sigue pendiente; no se sustituyó con la clave local. Los puntos siguientes preservan la cronología.

- Mateo autorizó explícitamente publicar el agente y probar pocas consultas basadas en Messenger con consumo de API. Esa autorización habilita las acciones de publicación de esta etapa; no se modifican credenciales ni flujos ajenos.
- Export/diff iniciales limpios para principal y multimedia. Backups en `backups/2026-11-05-publicacion-piloto/`; copia del destino y subscripciones del webhook sin copiar su secreto.
- Multimedia **publicada**, `active:true`, `activeVersionId:9f6d2b23-bffd-4b60-b6f7-47fd4f36c71e`. Nodos y conexiones iguales a la versión probada; sin pie de foto.
- QA manual creado: `IHsdDfjuW3T6hw1Q`, inactivo, 11 nodos. Mismo prompt/modelo/contrato multimedia, límite de 3 iteraciones y 1024 tokens de salida por llamada, herramienta en simulación fija, sin memoria ni envíos Chatwoot. Validación: 0 errores y 0 advertencias. [Cinco casos preparados](pruebas-prompt-f7-v1-piloto.json).
- **Bloqueo externo:** ejecución 36279 del primer caso rechazada por Anthropic: saldo insuficiente. El ensamblado se ejecutó, pero no se generó respuesta ni se invocó multimedia. No hay uso de tokens informado. No se ejecutaron los otros cuatro casos ni el smoke de conversación 27. Se pidió recargar la misma cuenta; no hubo reintentos automáticos.
- Principal **sigue inactivo**, webhook de Chatwoot **sin cambios**, para evitar conectar un agente que actualmente no puede responder. La herramienta publicada no tiene un disparador automático de clientes.
- Suite local con PGlite: 149 pasan, 0 fallan, 4 TODO anteriores, ninguna omitida. Principal/multimedia validan con 0 errores; no equivale a prueba de comportamiento.
- Informe, evidencia y pasos para retomar: [PRUEBA_PROMPT_F7_2026-11-05.md](PRUEBA_PROMPT_F7_2026-11-05.md). Continúan pendientes precios oficiales, compatibilidad y pase efectivo a Candela. Sin commit/push.
- Continuación: Mateo autorizó una clave local del `.env` para pruebas. Se preparó `scripts/test-prompt-f7-api.mjs`, sin modificar credenciales n8n, con Messages API, mismo prompt/modelo/selector en simulación, topes de consumo, persistencia por llamada y bloqueo ante consumo incierto. Sintaxis y cinco fixtures validados sin red. El `.env` de la ruta confirmada todavía no mostraba la clave en disco; se pidió completar el guardado. No hubo nuevas llamadas a Anthropic ni envíos; producción sigue pendiente.
- Verificación posterior al reemplazo desde Drive: la copia privada de la nube del mismo `.env` también tiene 944 bytes y no contiene la clave de Anthropic. No se modificó el `.env` ni se copiaron sus valores a resultados. Sigue pendiente agregar la clave al contenido; runner listo, sin llamadas nuevas.
- Diagnóstico de sincronización: Google Drive mostró **En pausa**, última sincronización hacía unos 29 minutos, y 73 errores de descarga. No apareció otra copia reciente de `.env`. La ventana se minimizó/interrumpió durante el control y no se confirmó reanudación; se pidió a Mateo pulsar «Reanudar la sincronización». Sin cambios de permisos, borrados ni llamadas nuevas a API. Se debe volver a verificar presencia de la clave antes del primer caso.
- Reanudación confirmada por Mateo y verificada en UI: aproximadamente 17.530 archivos en cola, 35 errores y aviso de subidas trabadas desde hace 46 días. El `.env` local y la revisión actual de nube siguen sin Anthropic; no se atribuyó al archivo un error específico sin evidencia. Se pidió una copia en `C:\Users\mateo\Downloads\f7-pruebas.env` para evitar Drive. El runner admite `--env-file <ruta>` y conserva los topes de consumo. Pendiente la copia local; no se modificaron credenciales ni hubo llamadas nuevas al modelo.
- Mateo indicó la copia `C:\Users\mateo\OneDrive\Desktop\.env`: existe y es binariamente idéntica al `.env` antiguo del proyecto (944 bytes, modificación 8 de septiembre), sin variable ni clave Anthropic. Se verificó codificación sin exponer valores. Hace falta guardar la clave dentro de esa copia para retomar; ningún archivo de secretos fue modificado y no hubo consumo nuevo.
- Actualización posterior: la copia del Escritorio ya contiene la clave y se usó directamente con `--env-file`, sin copiarla ni modificar credenciales n8n. Se completaron los cinco casos uno a uno, revisando cada resultado. Registro real: `docs/pruebas-prompt-f7-api-2026-11-05.json`; informe legible: `docs/RESULTADOS_PILOTO_F7_2026-11-05.md`.
- Hallazgos nuevos del piloto: caso 03 afirma envío ante resultado simulado; casos 04/05 ofrecen o afirman un pase inexistente a Candela; caso 04 confirma colocación de una variante de alfombra no verificada; casos 01/03 parafrasean presentación comercial y 01/02/04 exponen detalles internos. Se anotan para corrección posterior, **sin cambiar el guion en esta pasada**, conforme al protocolo del repo. No se aprobó el principal para producción.
- Verificación final: las piezas y cantidad de llamadas coinciden en los cinco casos, no hubo envíos reales, y se releyó n8n: principal `active:false`, multimedia `active:true`. Ningún cambio remoto en esta continuación. Sin commit/push.

## 15. Conversaciones con mensajes breves e historial — 2026-11-05

- Mateo señaló que los primeros ejemplos tenían demasiada información y pidió volver a Messenger. Se releyeron seis hilos en vivo; se registraron mensajes cortos, referencias al video, respuestas incompletas e insistencia por precio. Evidencia sin nombres/perfiles: [RELEVAMIENTO_MENSAJES_CORTOS_F7_2026-11-05.md](RELEVAMIENTO_MENSAJES_CORTOS_F7_2026-11-05.md).
- Nuevo runner `scripts/test-conversaciones-f7-api.mjs`, un turno por invocación, reutilizando el ensamblador y selector del piloto. Mantiene historial local de usuario + salida final, reensambla por mensaje actual y no conserva resultados de herramientas entre turnos. Tope global de USD 0,25 sumando el piloto previo; bloquea ante consumo incierto, sin reintentos. Se comprobó sintaxis y dry-run de ambos runners antes de gastar.
- Se ejecutaron tres conversaciones, once turnos, trece mensajes de cliente y once respuestas reales. Costo nuevo USD 0,089471; acumulado USD 0,156093. Cero llamadas a multimedia y cero envíos. Registro: `docs/pruebas-f7-multiturno-api-2026-11-05.json`. [Resultados completos](RESULTADOS_CONVERSACIONES_REALISTAS_F7_2026-11-05.md).
- Conservó Duster, Suran, Saveiro 97, envío y la aclaración tardía de dos butacas/cabina simple. No inventó importes ni asumió conocer el video. **No aprobado para producción:** repite varias preguntas juntas, endurece el tono ante insistencia y promete cotizaciones o verificación de medidas sin esas capacidades. También repite saludos y usa “tapizar” ante un pedido de fundas. Hallazgos anotados, sin cambiar el guion en esta pasada.
- Visualización nueva con respuestas literales y mensajes de cliente separados; la agrupación de turnos es sintética, no una prueba de Redis ni una transcripción histórica completa. No se tocaron n8n, credenciales, webhook ni prompt. Sin commit/push.

## 16. Diez conversaciones y salida sin formato — 2026-11-05

- Mateo pidió quitar exigencias no respaldadas por el brief (en particular el año exacto), evitar asteriscos/formato y probar diez conversaciones extensas hasta Candela. **Cambia guion: autorizado expresamente para ese ajuste.** Prompt `f7-brief-2026-11-05.v2`: modelo y modalidad como datos del recorrido, sin exigir año/configuración por rutina; texto plano y límites explícitos de cotización/derivación.
- Diez casos basados en el corpus y los hilos reconsultados de Messenger, con procedencia por turno y continuaciones sintéticas identificadas. **68 turnos, 88 mensajes de cliente, 69 llamadas a Haiku 4.5, 549.778 tokens de entrada y 7.149 de salida. USD 0,585523 nuevos; USD 0,741616 acumulados.** Tope de esta ronda USD 1. Sin reintentos inciertos ni consumo pendiente. Una selección multimedia `MP01` en simulación; cero envíos.
- El modelo produjo asteriscos en seis salidas. Corrección técnica en el nodo ya existente `devuelve outputs`: elimina formato antes del transporte, conserva URLs/emails/importes/decimales y la división por puntos. No hay nodos o workflows nuevos. Sobre las 68 respuestas crudas, el mismo Code local produjo 213 mensajes sin asteriscos. Raw, hashes y salida preparada se conservan por separado; la vista permite inspeccionarlos.
- **No aprobado comercialmente para producción.** Suran continúa sin pedir año, pero Duster y Siena aún muestran preguntas indebidas; persisten promesas de cotización sin datos, requisitos inventados, disponibilidad de Siena sin verificar, negativa de logos sin respaldo, tiempo incorrecto de tipo tapizado, pérdida de contexto y promesas de contacto de Candela sin acción. Los diez finales señalan dónde debe continuar Candela, no pases ejecutados. Estos hallazgos se registran para la siguiente corrección y no se maquillan en la vista.
- Export/diff iniciales limpios; dry-run final con solo `Clasificar y Ensamblar` y `devuelve outputs` modificados. Backup `backups/2026-11-05_104536/agente-principal-unificado.json`. Import al principal **inactivo**: versión `defa8684-bdf1-4b62-8d36-1ee6b17b1858`, 63/63 nodos y conexiones coincidentes. Export/diff final limpio. Sin credenciales, webhook, activaciones, herramienta multimedia o flujos ajenos modificados.
- Verificación: **159 pasan, 0 fallan, 4 TODO anteriores, ninguna omitida** con PGlite. Diez pruebas nuevas de limpieza fallaron antes del fix. Validación remota: 0 errores, 83 conexiones válidas, 71 expresiones, advertencia heurística anterior de `Normalizar evento`. La reproducción del Code local no acredita el runtime completo ni entrega Chatwoot. La credencial n8n del modelo sigue pendiente; la clave del Escritorio se usó solo para pruebas directas.
- [Informe y alcance](PRUEBA_DIEZ_CONVERSACIONES_F7_2026-11-05.md), [revisión por caso](REVISION_DIEZ_CONVERSACIONES_F7_2026-11-05.md), registro `pruebas-f7-diez-conversaciones-api-2026-11-05.json`. Vista de diez chats verificada en navegador, también en ancho angosto, con texto preparado exacto y originales desplegables. Sigue pendiente corregir comportamiento, conectar precios y construir el pase efectivo a Candela antes de habilitar atención. Sin commit/push.

## 17. Herramienta de precios e integración — 2026-11-05

- Mateo autorizó desarrollar la herramienta nueva e incluirla en el prompt. Confirmó expresamente «El precio en cuotas es el mismo que de transferencia». Cambia guion aprobado: cotización por herramienta oficial y continuación breve, conservando las frases comerciales del brief.
- Creado [F7 · Buscar precio y cotizar · v1](https://n8n.teotec.org/workflow/uNguhYLYJ4vEASG0), ID `uNguhYLYJ4vEASG0`, 33 nodos (29 ejecutables +4 notas). Principal `m7jZDzyP17BayLrI` de64 nodos, dos tools: `enviar_multimedia` y `buscar_precio`. Ningún manager nuevo, ni conexión a los antiguos precios/Supabase. Principal e hijo de precios siguen inactivos/sin publicar; multimedia no cambió.
- Lee metadata y valores numéricos vivos de las ocho hojas oficiales mediante Google Sheets API y la credencial Drive existente. Primer ensayo36305 encontró vencida la antigua credencial Sheets; error controlado, sin cotizar. Se cambió solo el binding de los dos nodos nuevos a Drive, que permite esta lectura; no se reconectó ni modificó ninguna credencial.
- Motor: headers por sección, año/configuración solo cuando la fuente distingue variantes, duplicados conflictivos y rangos ambiguos requieren aclaración; nunca completar vacíos ni elegir un vehículo parecido. Comparación no suma alternativas; combo exige todos los ítems válidos; subtotales por cantidad. Cuotas=transferencia incluso frente a POSNET de Otros. Cubrevolante usa tarifa genérica. Tapicería/servicios presenciales no se ofrecen por envío. Precio no confirma medidas, stock, turno ni tarifa de flete.
- Herramienta genera/envía plantilla en texto plano; registro aislado `f7_cotizaciones_envios` con RLS/SQL parametrizado, destino confiable, reserva única, control humano/ventana y POST sin reintento. Incertidumbre bloquea duplicados. El LLM recibe resultado compacto sin importes y `continuacion_obligatoria`; no reescribe el presupuesto.
- Revisión independiente encontró y corrigió mezcla de rangos entre GrandSantaFe/StaFe y cláusulas ALTERNATIVAS, y encabezado SsangYongMusso tomado como tarifa. Revisión final aprobó esos casos y el retorno compacto;35 pruebas del motor +3 de salida verificadas por el revisor.
- Primera ronda Haiku: nueve llamadas, USD0,109782; repitió importes/Markdown, cambió un rango y pidió modelo innecesario al cubrevolante. Originales intactos. Segunda ronda con prompt `f7-brief-2026-11-05.v4-precios`: seis llamadas, USD0,074542, tres casos aprobados (Suran2009 envío, comparación CronosCABA, cubrevolante envío). Cierres literales, sin importes repetidos ni asteriscos. Transporte simulado, marcado `MOCK_TRANSPORTE`. Total etapa USD0,184324, sin gasto incierto. Clave local autorizada solo para tests; credencial n8n Anthropic sin cambios.
- Suite final con PGlite: **209 pasan,0 fallan,0 omitidas,4 TODO previos**. Validación remota: herramienta0 errores/advertencias,39 conexiones/12 expresiones; principal0 errores,84 conexiones/71 expresiones y advertencia heurística previa de Normalizar evento. Tests conservan audio, Redis, memoria, credenciales y transporte de la base.
- Runtime final [36307](https://n8n.teotec.org/workflow/uNguhYLYJ4vEASG0/executions/36307): metadata y precios HTTP200, ocho hojas, siete ítems cotizados y dos variantes que requieren aclaración. Diez nodos ejecutados, sin pasar por Postgres ni Chatwoot. Evidencia saneada: `PRUEBA_PRECIOS_RUNTIME_F7_2026-11-05.json`. Acredita lectura y resolución reales; no un envío real ni invocación productiva del hijo.
- Backups finales: `backups/2026-11-05_124839/herramienta-precios-v1.json` y `backups/2026-11-05_124840/agente-principal-unificado.json`. Versiones guardadas: hijo `a9e469d5-b620-4bb0-a843-a4142df5ce3c`, principal `76148a6e-b96f-4d55-9084-6f511242c446`. Relectura33/33 y64/64 nodos/conexiones iguales.
- Documentación actual: [herramienta](HERRAMIENTA_PRECIOS_F7_V1.md), [prompt](SYSTEM_PROMPT_F7_V1.md), [lectura fuente](precios-f7/LECTURA_PLANILLA_2026-11-05.md), plan aprobado en `docs/superpowers/plans/2026-11-05-herramienta-precios.md`. Scripts reproducibles para preparar hijo/principal.
- Pendiente antes de producción: publicar hijo, verificar saldo/credencial del modelo de n8n y probar cadena completa/envío real; siguen pendientes pase efectivo a Candela y fuente de medidas. Los tres casos Haiku no acreditan todos los comportamientos comerciales del bot. Sin cambio de webhook, activaciones, commit ni push.

## 18. Publicación e integración completa; piloto integral — 2026-11-05

- Mateo pidió conectar herramientas y publicar el prompt, con conversaciones realistas para revisar precios, multimedia, insistencias y cierre. Confirmó que **Candela usa Melanie**, usuario 3 de Chatwoot. Esta autorización cubre publicar los flujos F7 nuevos; no se tocaron credenciales, miembros, permisos, flujos ajenos ni el webhook de Chatwoot.
- Nuevo hijo [Derivar a Candela](https://n8n.teotec.org/workflow/TWnWokkaRUO3eFsf): 43 nodos, destino fijo, motivo acotado, contexto del caller. Preserva etiquetas, agrega humano, abre y luego asigna a Melanie; GET verifica cada efecto. No reasigna un chat ya humano. Confirmación pública fija únicamente después de verificar; SQL aislado con RLS, bloqueo por conversación y ninguna repetición de POST incierto. 21 pruebas propias, incluido PGlite y recorrido con HTTP simulado. Validador: cero errores/advertencias, 61 conexiones.
- Principal: 71 nodos, tres tools (`enviar_multimedia`, `buscar_precio`, `derivar_humano`). Dos controles nuevos leen Chatwoot después del agente y antes de cada fragmento; humano suprime respuesta y libera el lock, fallo de verificación libera por error. Audio, Redis, memoria, credenciales, fragmentación y POST existentes se conservaron. Revisión independiente no encontró un bloqueo técnico nuevo. No cancela determinísticamente nuevas llamadas dentro del agente; cada herramienta limita sus efectos con controles propios.
- Publicación inicial v5 verificada: principal `4b7626b9-92c7-48f1-9408-39e78cc202cd`, precios `3328629b-165e-48fb-9b03-7592a5e240b4`, derivación `f9220e5f-fa04-4e5b-953c-a9ebdd3c38f7`; multimedia publicada sin cambios. `activeVersionId` coincide con versión guardada. Evidencia en `PUBLICACION_INTEGRAL_F7_2026-11-05.json`. QA manual quedó inactivo con las tres herramientas en modo simular.
- Backups previos: `backups/2026-11-05_164330/herramienta-precios-v1.json`, `backups/2026-11-05_164331/agente-principal-unificado.json` y `backups/2026-11-05_164332/test-prompt-f7-v1.json`. Export/diff posterior de los cinco flujos limpio. Suite de esta integración: 239 pasan, cero fallas/omitidas y cuatro TODO anteriores; se agregan luego pruebas propias del runner.
- Runtime 36317 leyó las ocho hojas oficiales sin cambios de valores frente a 36307. Runtime 36318 ejecutó derivación en modo simular y terminó antes de Postgres/Chatwoot. No se enviaron mensajes a clientes reales en esta etapa. La prueba n8n 36316 confirmó **saldo insuficiente** en Anthropic; Mateo decidió continuar solamente con las pruebas del `.env`. La credencial no se modificó. El webhook actual de Chatwoot sigue apuntando a la cadena anterior, no al principal nuevo; publicado no equivale a atención nueva en producción.
- Piloto v5 guardado sin reescribir respuestas: `PRUEBA_INTEGRAL_F7_2026-11-05.json`. 51 llamadas, USD 0,732886, cuatro conversaciones completas y quinta parcial; reserva incierta cero. La prueba se detuvo ante un intento de repetir multimedia inválida, no por presupuesto. **No aprobado comercialmente:** pase prometido sin tool, retención del pedido de persona por aclaraciones repetidas, modalidad inferida, dos butacas confundidas con cantidad de juegos, descripción errónea de tipo tapizado, stock afirmado sin fuente y continuación literal incumplida. Los importes incorrectos quedaron bloqueados por ambigüedad en los casos observados.
- Se corrigen estos hallazgos dentro del encargo actual antes de completar el piloto. El tope interno se amplía a USD 2,50 / 160 llamadas para completar diez conversaciones y retests necesarios, manteniendo la autorización previa de pruebas de consumo moderado. Reservas antes de cada generación, contabilidad persistente y ningún reintento de consumo incierto. El transporte del piloto es simulado: no acredita entrega ni asignación reales.


### Piloto integral: rondas v6/v7 y controles técnicos

- Ronda v6 completó diez conversaciones y 69 turnos, 108 llamadas por USD 1,09614975. Revisión independiente: 29 hallazgos; incluye un total inventado de $89.800 frente a $887.029 del motor, modalidad CABA supuesta y derivación prematura. Se conserva el registro original y la revisión completa en PRUEBA_INTEGRAL_F7_2026-11-05_r2.json y REVISION_INTEGRAL_F7_2026-11-05_R2.md. No aprobada comercialmente.
- Se preparó v7 compacto y controles técnicos: modalidad sólo desde mensajes humanos de la misma sesión; sin elección, precios pregunta antes de Sheets/DB/Chatwoot. Salida de cotización fijada por resultado real, bloqueo de importes libres y anuncios sin acción; fallback al hijo humano en error comercial. Pausa humana prevalece y se comprueba antes de cada fragmento.
- Memoria: SQL parametrizado corrige únicamente content del último AI de la sesión si coincide con raw, preservando metadatos. Ante diferencia inesperada libera por error y no envía. La reparación no se afirma exitosa sin comprobación; ejecución real con n8n pendiente por saldo y decisión de Mateo de usar sólo .env.
- Suite local con PGlite: 366 pasan, cero fallas/omitidas, cuatro TODO anteriores. Revisión independiente de wiring/aislamiento completada. Validación remota v7: precio cero errores/advertencias (41 conexiones,13 expresiones); principal cero errores, una advertencia heurística histórica (109 conexiones,81 expresiones); QA cero errores/advertencias.
- Borradores v7 guardados y relectura exacta: precios35nodos c4885156-c610-46b7-bbdc-a0a4b2523754, principal77nodos c32916d6-ca23-424d-beb5-6e946767d024, QA14nodos 6dd8d4c3-47e6-4b9b-95c5-1bbf7945dcd9. Backups 2026-11-05_172752 (precios), _172753 (principal), _172754 (QA). El force del principal sólo salvó timestamp de publicación: versionId local/vivo idéntico y credenciales verificadas iguales.
- Ronda v7: tres conversaciones,22turnos,29llamadas,USD0,15894825. Guard de modalidad bloqueó el CABA supuesto en08/T1;08 luego cotizó correctamente y cambió a CABA. No aprobada:06 y09 exigen año de Cronos antes de buscar;06 interpreta mal negación de baúl;09 retiene pedido de alias/pago por el año. Se conserva PRUEBA_INTEGRAL_F7_2026-11-05_r3.json. No hubo envíos ni asignaciones reales.
- Ajuste siguiente dentro del pedido vigente: v8 con mínimos de consulta y prioridad explícita final de persona/pago; guard de rescate para pedido humano inequívoco si el LLM lo omite. Tope interno de costo se conserva en USD2,50 y llamadas se amplía a240 por menor costo del prompt. Consumo integral hasta v7 USD1,987984/188llamadas; sin gasto incierto. No se aprobó atención real ni se cambió el webhook.

### Cierre de integración y piloto integral — estado vigente

- Publicación final verificada por API, incluidos nodos y conexiones del grafo activo: principal 77 nodos versión 211e7829-c85c-4db3-ad3b-a3d6c6466def, prompt f7-brief-2026-11-05.v8-buscar-primero; precios 35 nodos versión c4885156-c610-46b7-bbdc-a0a4b2523754. Multimedia 55 y derivación 43 continúan publicadas sin cambios. QA 14 quedó inactivo. Evidencia: PUBLICACION_INTEGRAL_F7_2026-11-05.json y VALIDACION_INTEGRAL_F7_2026-11-05.json.
- Backups adicionales: backups/2026-11-05_173338/agente-principal-unificado.json, _173339/test-prompt-f7-v1.json y _173722/agente-principal-unificado.json. Import final sólo cambió los dos Code de salida. Export/diff final de los cinco flujos sin diferencias. No se tocaron credenciales ni webhook, ni se hizo commit/push.
- Suite final con PGlite: **421 pasan, 0 fallan, 0 omitidas, 4 TODO históricos**. Fuente del guard y modelo comparten los helpers auditados; esto no acredita el runtime completo de n8n, que no se repitió por indicación de usar sólo .env.
- R4 v8: cuatro conversaciones,24 turnos,35 llamadas,USD 0,19112125. Informe REVISION_INTEGRAL_F7_2026-11-05_R4.md. **No aprobado para atención real.** Caso 06 insiste por año de Cronos y no consulta precio; caso 03 tuvo un pase falso del detector. Caso 08 cotiza con modalidad confiable y cambia de envío a CABA; caso 09 cotiza sin año y deriva por alias. No hubo multimedia en los24 turnos; los finales anticipados dejaron intenciones sin cubrir.
- Falso positivo03T3 corregido posteriormente: hablar de valor y un juego de5 plazas ya no se clasifica como importe. Regresión exacta y suite pasan; NO se repitió la conversación paga y NO se reescribió r4. La vista conserva el fallo real, además del raw y lo que habría recibido el cliente.
- Total del piloto integral (v5,v6,v7,v8): **223 llamadas,USD 2,17910525**, sin reserva incierta. Ningún envío o asignación real a clientes. Las pruebas previas de otras etapas tienen contabilidad separada y no se suman a esta cifra.
- Pendientes antes de conectar clientes: resolver decisión de consultar con modelo/modalidad sin exigir año de rutina; comprobar uso oportuno de multimedia y FAQ/variantes; ensayar cadena n8n completa y derivación real cuando tenga saldo la credencial del modelo. El próximo trabajo debe evaluar decisiones comerciales con estado estructurado o un piloto comparativo de modelo, conservando el guion; no se implementó ninguna de esas alternativas en esta etapa.

## 19. Cotización natural y siete conversaciones — 2026-11-05

- **Cambia guion, aprobado expresamente por Mateo:** cotización natural por transferencia y pregunta exacta «Quisieras aprovechar el valor en transferencia o en 3 cuotas sin interes?» juntas en un único mensaje. Se aplica a CABA y envío, sin pedir medio de pago antes. La herramienta sigue generando y enviando el presupuesto; el agente no reescribe importes ni repite el cierre. Comparación en un párrafo sin suma; combo completo con un total único. Cantidades, coberturas, fuente y cálculos permanecen trazables.
- Publicados V9 y luego V9.1. Lectura real de precios36323: ocho hojas, valores iguales a la fixture, siete artículos cotizados/dos pendientes, sin escrituras ni mensajes. Principal77/precios35/QA14 conservan el grafo y credenciales; multimedia55/derivación43 sin cambios. Registros `PUBLICACION_COTIZACION_NATURAL_F7_2026-11-05.json`, `_v91.json` y validaciones respectivas. Backups184247(precios),184251(principal),184256(QA),185546(principal V9),185551(QA V9).
- V9.1 corrige pérdida de evidencia de cotización en memoria al dejar vacía la continuación pública. `memoria_output` proviene exclusivamente de observación confirmada, con ID válido y datos acotados sin importes. Se guarda en el mismo historial con SQL parametrizado; jamás es el campo de salida al cliente. No se agregó manager ni tabla. Prompt limita recotización por video/diseño/color; conserva recotizar ante cambios reales/pedido explícito. Suite V9.1:451 pasan,0 fallan/omitidas,4 TODO históricos.
- R1: siete casos/47 turnos registrados/46 completos;79 generaciones,USD0,43740565.22 mensajes de precio(15 completos/7 parciales),4 piezas multimedia y6 pases simulados. Falló la comparación02T5 por dos llamadas separadas; hubo recotizaciones por video/color y errores de selección. Revisión y JSON originales intactos.
- R2: siete casos/44 turnos registrados/43 completos;70 generaciones,USD0,4016344.17 mensajes de precio(15 completos/2 parciales), comparación correcta02T3, combos499950 y887029,4 piezas aceptadas y una omitida por duplicada. Seis pases simulados, uno incorrecto. Caso07 mejoró hasta pago. Ocho intenciones no ejecutadas por corte02 y paseprematuro04. **R2 no aprobada para atención real.**
- Hallazgos a conservar:02T5 repite buscar_precio por separado;01T6 recotiza por color;03T6 vuelve a preguntar cierre;05T6–7 confunde Suran2009/2018 pese cambio confirmado;04T3 detector de importe deriva ante «valor de dos cubrevolantes» sin monto. R1 también mostró conservación de accesorios excluidos04T7. Son fallos de decisiones, no evidencia de celdas monetarias incorrectas. No se amplía este cambio a corregirlos todos.
- Regresión encontrada en R2:03T7 el modelo copia la constancia interna y el guard la deja llegar al cliente. **Protección final implementada y publicada:** bloquea marcador/estructura técnica en salida libre y activa el fallback humano existente. Reproducción exacta y variantes locales pasan; no hubo otra tanda LLM. El registro R2 conserva lo sucedido; no se reemplaza por una respuesta corregida ni se presenta como aprobada la tanda.
- Consumo total de esta etapa: **USD0,83904005 /149 generaciones**, reserva incierta0. Tope monetarioUSD1,25 sin cambios; límite técnico ampliado120→200 para repetir los siete casos después del ajuste de memoria. Sólo `.env` autorizado, Haiku real con transporte simulado. No se enviaron mensajes ni asignaron chats reales; no se modificaron credenciales ni webhook. Sin commit/push.
- Vista final con los siete chats registrados de R2, sin mezclar turnos de distintas rondas:44turnos,133eventos visibles,17cotizaciones,4adjuntos y6pases. Conserva también los cortes y errores reales. Legibilidad y selector verificados en navegador, incluido ancho360px.
- Cierre técnico: **456 pasan,0 fallan/omitidas,4 TODO históricos**. Principal activo `7b87817f-d95d-405f-b3af-1a36b4db6d48`, precios `f359e981-9526-46db-86f9-a2faec225b32`; QA inactivo `ad9b84fd-5710-4cb9-8d59-e504a6ab0f8d`. Último backup `backups/2026-11-05_190234/agente-principal-unificado.json`. Grafo activo idéntico y export/diff final limpio de los cinco flujos. Evidencia `PUBLICACION_COTIZACION_NATURAL_F7_2026-11-05_final.json`.
- Detalle en `COTIZACION_NATURAL_F7_2026-11-05.md` y revisiones R1/R2. Publicación de configuración no equivale a entrada de clientes: Chatwoot sigue con su ruta anterior y no se repitió prueba de saldo en n8n por decisión de Mateo. No se agregaron tablas ni manager, ni se tocó credencial/webhook. Sin commit/push.

## 20. Sonnet 5 y repetición literal de los siete casos — 2026-11-05

- Pedido de Mateo: cambiar el modelo y repetir exactamente el ensayo anterior. Se verificó `claude-sonnet-5` mediante Models API (HTTP200; admite `thinking:disabled`). Principal y QA usan ese ID, conservando nodo Anthropic1.3 y credenciales; `thinking:false` explícito evita activar razonamiento extendido por defecto. QA conserva máximo1024 tokens. El prompt V9.1, las herramientas, conexiones y guard de producción no cambiaron. Compatibilidad documentada en `COMPATIBILIDAD_SONNET_5_F7_2026-11-05.md`.
- Principal publicado y verificado contra `activeVersion.nodes`: `033d715b-8465-4eb0-9ecb-4f9588938e15`,77nodos. Esta instancia actualizó la versión activa al guardar por PUT; no hubo llamada adicional de activar/desactivar. QA inactivo `9c5fe293-6ab7-4f73-b9e8-dceb5b229d7b`,14nodos. Backups `backups/2026-11-05_194208/agente-principal-unificado.json` y `backups/2026-11-05_194213/test-prompt-f7-v1.json`. Evidencia `CAMBIO_MODELO_SONNET_5_F7_2026-11-05.json`.
- Comparación congelada contra R2: mismos44turnos/52mensajes previstos, orden literal y fechas originales; sin adaptación ni agregar los8turnos que R2 no alcanzó. Fuentes de prompt/precios/herramientas iguales por SHA. Para aislar el modelo, el ensayo local utiliza el guard histórico R2 recuperado y verificado en `tests/fixtures/guard-salida-comercial-r2-2026-11-05.mjs`; **no se restauró ese guard en producción**. El historial posterior se forma con las respuestas y acciones de Sonnet.
- Resultado: siete casos,39turnos completos/47mensajes de cliente,69generaciones verificadas como Sonnet5,USD0,971998, reserva incierta0; tope de etapaUSD2. Cinco turnos no ejecutados por pases anticipados:03T7–8,05T8,06T6–7. Todos los39turnos comunes conservan texto, orden y fecha. Cuatro prompts posteriores03T3–6 cambian por el video que Sonnet envió en03T2; las fuentes permanecen iguales. No se forzó continuidad después de pausar el bot. Casos02/04 terminan donde se cortó el baseline, sin simular una compra posterior.
- **No aprobado para atención real.** Mejoras observadas:02T5 compara ambas opciones en una sola llamada sin fallo;01T6 no recotiza por color;05T6 conserva Suran2018 al cambiar a CABA;06T5 deriva el descuento inmediatamente. Regresión grave:03T5, ante «cuanto todo junto?», consulta y cotiza sólo la alfombra($387.079), omitiendo fundas y cubrevolante; el total correcto de los tres era$887.029. Tampoco pidió combo en03T3 y usó configuración inválida de alfombra en03T4. Estos hallazgos se registran, no se corrigen durante la comparación.
- Continúan repeticiones/reformulaciones de cierre(01T5,06T3,07T3–4), recotización de2cubrevolantes04T3, y ambigüedad de Suran05T7 por omitir el campo año. Sonnet produjo registro interno en raw03T5, suprimido por el control posterior; la fuga entregada de Haiku03T7 no fue reevaluada porque Sonnet derivó antes. No declarar que el cambio de modelo resolvió esa conducta. Hubo16presupuestos(15completos/1parcial),5piezas multimedia y5pases simulados; cero envíos externos.
- Prueba directa con la clave `.env` ya autorizada. No se reprobó saldo ni se modificó la credencial Anthropic de n8n. Tampoco se cambió el webhook de Chatwoot, que sigue con su ruta anterior. No acredita cadena completa, Redis, memoria Postgres, entrega WhatsApp ni asignación humana reales. Sin commit/push.
- Verificación final:461tests pasan,0fallan/omitidos,4TODO históricos. Validación MCP principal/QA sin errores; permanece un aviso previo en `Normalizar evento`. Export final de ambos workflows; diff informa sin diferencias. El CLI de diff sufrió nuevamente una aserción libuv al cerrar en Windows después de informar igualdad; la lectura API y comparación directa se conservaron como evidencia independiente.
- Reporte original `PRUEBA_SONNET_5_F7_2026-11-05.json`, métricas `COMPARACION_SONNET_5_F7_2026-11-05.json`, revisión `REVISION_SONNET_5_F7_2026-11-05.md`. Vista `f7-sonnet-5.html`: selector Sonnet5/HaikuR2,7casos por modelo,109/133eventos visibles respectivamente; mensajes sin editar. Verificada en navegador a ancho normal y360px, cambio de modelo conserva el caso, sin errores JS ni desborde horizontal.

## 21. Cotizaciones sin avisos de envío o medidas — 2026-11-05

- **Cambia guion, pedido explícito de Mateo:** eliminar «El costo del envío y la compatibilidad/medidas quedan a confirmar.» y sus variantes. Esos detalles quedan a Candela. Se retiraron las notas automáticas de envío y cubrevolante del motor, las menciones de compatibilidad pendiente en aclaraciones de variantes y la FAQ del guard que reemitía el aviso sobre medidas. Se conservan las preguntas necesarias para identificar la tarifa y los controles de selección/importes; no se agregan rutas ni detectores generales de derivación.
- Prompt `f7-brief-2026-11-05.v9.2-sin-avisos-cotizacion` y descripción de buscar_precio prohíben esos avisos. Ante preguntas explícitas por costo de envío, medidas o compatibilidad, Candela responde mediante la herramienta de derivación existente; se respeta su continuación y no se duplica el ACK. No se infiere envío gratis/incluido ni compatibilidad. Sonnet5, cierre literal, plazos, modalidad, stock, herramientas y credenciales se conservan.
- Comparación local de18textos de la tanda Sonnet: items, importes y totales idénticos; texto igual salvo las dos notas retiradas. Tres casos ejecutados localmente con el Code node obtenido de la versión activa (fundas con envío, cubrevolante CABA y combo con envío) devuelven precio+cierre sin los avisos. Transporte Sheets simulado; no acredita una ejecución remota completa ni entrega WhatsApp. Cero generaciones API y cero mensajes reales.
- Publicado principal77nodos `f2c58290-f7b4-4ea6-81b3-b1b1e2790ce3`; precios35nodos `92405841-934c-4a6d-a662-7c50f0f4028d`. QA14nodos inactivo `a790a3a2-f8d0-411c-b304-38e5b5c8754e`. Verificación de grafos activos, conexiones y credenciales contra backups230314(precios),230319(principal),230324(QA). Evidencia `PUBLICACION_SIN_AVISOS_COTIZACION_F7_2026-11-05.json`.
- Suite final:463pasan,0fallan/omitidas,4TODO históricos. Los3snapshots exactos validan sin errores; aviso previo de Normalizar evento sin cambios. Export/diff final limpio. Los tests de comparación histórica validan artefactos inmutables; el runner rechaza repetir R2 contra fuentes comerciales nuevas, conservando su barrera de hashes. No se reescriben conversaciones ni vistas históricas.
- Sin cambios de webhook, credenciales, activaciones/desactivaciones, commit ni push. El problema de selección del combo observado en Sonnet sigue pendiente; no forma parte de esta eliminación de texto. El archivo `scripts/preparar-precios-f7.mjs` no estaba disponible: se usó el constructor existente para actualizar únicamente Validar pedido y Resolver cotizacion, sin recrear ni cambiar el resto del workflow.

## 22. Cotización según medio de pago — 2026-11-06

- **Cambia guion, autorizado expresamente por Mateo:** responder efectivo con su columna oficial cuando lo pide, y cotizar correctamente según medio. Transferencia sigue como valor inicial, con el cierre literal existente. Efectivo solo CABA; cuotas = transferencia, nunca POSNET ni un descuento calculado. Las cotizaciones de efectivo/cuotas no reabren la elección transferencia/cuotas. Se conservan texto natural, cantidades, cobertura, modelos y las restricciones previas sobre avisos de envío/medidas.
- Contrato `pedido.metodo_pago`: transferencia (default), efectivo, cuotas, debito u otro. El motor selecciona esa columna para cada importe/subtotal/total; si falta, no reemplaza por otra. Efectivo+envío retorna `metodo_no_disponible` sin cotización y pregunta taller/envío. Débito/otro retorna `metodo_no_confirmado`, sin prometer aceptación/tarifa, con revisión especial. Tarjeta sin precisión requiere aclarar crédito/débito. Consulta de precio, incluso «quiero pagar en efectivo, cuánto sale?», no equivale a concretar pago. Alias/compra/reserva/pago real siguen a Candela.
- Memoria confirmada conserva `metodo_pago` y `pregunta_comercial_incluida` exclusivamente desde la observación válida, sin montos. El guard conserva la aclaración de efectivo+envío y rescata revisión especial para un método sin regla si el modelo no ejecuta el pase. No repite ni reintenta una derivación ya ejecutada o incierta.
- Primera tanda v9.3: cinco conversaciones inspiradas en Messenger, 32 turnos, 55 generaciones reales Sonnet 5, USD 0,8220331. Los importes por medio fueron correctos, pero 05T5 («todo junto efectivo cuanto») no produjo el total porque eligió consulta. Se corrigió el problema de combo ya anotado en sección20: pedir total/todo junto confirma presupuesto conjunto, sin exigir una decisión de compra. Se preservan todos los productos y cantidades y no se suman alternativas.
- Prompt final `f7-brief-2026-11-05.v9.4-medios-pago-total`. Se repitió únicamente el caso05 con los mismos seis turnos de cliente: 11 generaciones, USD 0,1820335. T4/T5 invocaron combo con fundas Cronos+cubrevolante y enviaron $413.000 en efectivo. **Total de esta tarea: 66 generaciones, 38 turnos ejecutados, USD 1,0040666, reserva incierta cero, bajo el techo USD 1,50.** Reportes originales inmutables `PRUEBA_MEDIOS_PAGO_F7_2026-11-06.json` y `_r2.json`; sin retocar respuestas para la vista.
- Contraste directo de Google Sheets conectado: Suran2017–2019 B137/C137=385000/466092; Cronos fundas B70/C70=353000/427350; tipo tapizado Cronos B5/C5=550000/665500; cubrevolante B4/C4=60000/72600, POSNET79134 ignorado por regla autorizada. Evidencia `TARIFAS_VERIFICADAS_MEDIOS_PAGO_2026-11-06.json`. Los ensayos API usan el fixture local contrastado; la herramienta publicada consulta Sheets vivo.
- Publicación final verificada en el grafo activo: principal77nodos `38e3c062-363b-4e15-ad3e-801862badedb`, precios35nodos `f21834e4-fb75-47a4-8ae7-b3d4631745c8`; QA14nodos inactivo `5f68132e-96ef-4fee-9f6c-d12b38941534`. Backups: `2026-11-06_102905` precios, `_102910` principal, `_102915` QA; segunda publicación `_103745` principal y `_103749` QA. Nodos/conexiones/credenciales preservados salvo código y descripciones identificados en dry-run; Sonnet 5 se mantiene. Evidencia `PUBLICACION_MEDIOS_PAGO_F7_2026-11-06.json` conserva ambas revisiones.
- Verificación final antes de R2: **491 tests pasan, 0 fallan/omitidos, 4 TODO históricos**; validación de los snapshots exactos sin errores, solo aviso heurístico anterior de Normalizar evento. Cinco escenarios ejecutaron localmente el jsCode descargado de la versión activa (transferencia, efectivo, cuotas, efectivo/envío, débito): `RUNTIME_LOCAL_MEDIOS_PAGO_2026-11-06.json`. El test MCP remoto no está disponible porque falta configuración de acceso MCP de instancia; no se alteró esa configuración. Esto no acredita una ejecución completa en el servidor.
- Alcance: generaciones reales por API con la clave local ya autorizada; transporte Chatwoot, media, persistencia e intervención humana simulados. Cinco pases simulados en la tanda y uno en la repetición; cero mensajes reales a clientes. Dos salidas raw de la primera tanda y una de R2 incumplieron silencio tras el pase, pero el guard dejó `mensajes_salida=[]`, sin texto duplicado entregable. No equivalen a fallas de silencio visibles ni a un modelo que siempre obedece.
- Observaciones comerciales fuera del ajuste de tarifas: 02T5 negó un descuento adicional sin revisión humana; 02T4 pidió foto de cubrevolante y obtuvo sin_material (el catálogo conserva CV01 video, no foto); conviene ofrecer ese video. Se registran sin cambiar negociación ni multimedia en esta pasada. Persisten reformulaciones del guion y recotizaciones repetidas: no se declara aprobación comercial integral del agente.
- Vista nueva `f7-medios-pago.html`: 01–04 desde la tanda original y05 desde R2, marcado como repetición; procedencia/hashes por caso y textos literales verificados. No reemplaza vistas históricas. Sin cambios de credenciales, webhook de Chatwoot (continúa en su ruta anterior), activaciones/desactivaciones, commit ni push. La credencial Anthropic de n8n no se reprobó ni cambió; no confundir estas pruebas directas con cadena WhatsApp de punta a punta.
- Cierre: export/diff final de principal, precios y QA sin diferencias. Suite del runner posterior a R2: 41/41, presupuesto cerrado sin reservas inciertas. Lector final con 32 turnos y82 elementos visibles (38 cliente,14 cotizaciones,24 textos,5 ACK,1 adjunto), cotejados literalmente contra sus dos fuentes. Vista normal y360px comprobadas, selector del caso05 y total413000 visibles; sin desborde ni errores JS. Servidor local de preview detenido y tamaño del navegador restaurado.


## 23. Comando borrar y reactivación del bot — 2026-11-06

- Pedido explícito de Mateo: comando antes del buffer, con confirmación literal y reactivación después de Candela. Publicado en el principal existente, después de los IF de entrada; rama sin Wait/LLM. Reconoce mayúsculas, espacios, tildes y signos del comando entero. ACK: «Ya borre mi memoria, a partir de ahora comienza una conversación nueva».
- Reinicia por cuenta/conversación mediante época y nueva key, sin borrar el historial físico ni afectar otro chat del contacto. Vacía buffer anterior, conserva locks por época, quita sólo humano y verifica las otras etiquetas. Duplicados no repiten ACK. Se verifica mensaje persistido de Chatwoot antes de mutar; fallos de transporte no disparan un segundo POST. La tabla técnica de reinicios no agrega otro manager/workflow.
- Cinco controles de época en el principal y controles antes de seis POST de las herramientas. Cierres terminales y liberación de lease propio evitan bloquear solicitudes nuevas. Mensajes nuevos con época vigente esperan si el reset sigue pendiente. El contexto multimedia también se corta por ID original de solicitud.
- Publicación verificada: principal121nodos 2f840d76-0527-4467-b34d-a513a87da601; precios42nodos 6e4e9300-19bf-4a5a-b1ba-9c0116caac22; multimedia62nodos c586a875-af1b-40be-a2f5-461be653e0b4; derivación62nodos 1a23f8ba-8d53-4be5-8aec-71f5de9eb365. Backups 2026-11-06_111626(precios), _111630(multimedia), _111635(derivación), _111640(principal). El único ajuste de servidor fue webhookId generado para Wait, incorporado al constructor y verificado exacto. Prompt v9.4, Sonnet5, credenciales y settings conservados; export/diff limpio.
- 545 tests pasan, cero fallos/omitidos, cuatro TODO históricos. Validación MCP sin errores. Runtime de rama completa con SQL PGlite y HTTP/Redis simulados. Cinco ejecuciones reales n8n 36357–36361 exitosas: filtros, rechazo de comando no persistido y esquema/lookup Postgres reales. Cero POST a clientes, cero tokens del modelo. Readback dirigido:21/21.
- Limitaciones documentadas: SELECT→POST no es atómico ni revoca HTTP en vuelo; un mensaje que capturó la época vieja justo antes de completar el reset puede descartarse. Esperar el ACK antes de empezar otra prueba. Falta envío real del ACK desde WhatsApp; webhook10 sigue con ruta anterior y no apunta al principal. No se cambiaron webhook, credenciales, activaciones/desactivaciones ni guion comercial. Sin commit/push.
- Detalle y mantenimiento: REINICIO_CONVERSACION_F7_2026-11-06.md. Evidencias PUBLICACION_REINICIO_F7_2026-11-06.json y SMOKE_REINICIO_F7_2026-11-06.json. El preparador de prompt conserva el reinicio; al regenerar herramientas aplicar también scripts/preparar-reinicio-f7.mjs.


## 24. Traspaso a Claude Code — 2026-11-06

- Pedido de Mateo: dejar contexto suficiente para continuar las modificaciones dentro del proyecto. Se agregó docs/CONTEXTO_CLAUDE_CODE_2026-11-06.md con decisiones comerciales vigentes, arquitectura/IDs/versiones, fuentes editables, último reinicio, pruebas acreditadas y pendientes concretos.
- Corpus real identificado:31hilos M01–M31, más la relectura R01–R06 sin sumarla como seis conversaciones únicas nuevas. Se distingue mensaje literal, resumen observado, fixture sintética y respuesta real del modelo; reglas para recrear clientes breves, ambiguos e insistentes y conservar evidencia sin retocar.
- CLAUDE.md actualizado como entrada de trabajo; anterior conservado sin cambios en docs/historia/CLAUDE_ANTES_DEL_TRASPASO_2026-11-06.md. README enlaza el traspaso y usa slugs actuales; no prescribe reemplazar .env. Se advierte qué guías/modelos/arquitecturas son históricos, que el stage integral aún usa Haiku y que los replays congelados no deben desbloquearse cambiando hashes.
- Sólo documentación: no se modificaron fuentes ejecutables, prompts, workflows, credenciales, routing ni registros externos. Sin ensayos pagos, mensajes reales, commits ni push. Se verificaron enlaces locales; dos dry-runs del runner sin red/credenciales pasaron, y el replay histórico rechazó correctamente las fuentes actuales cambiadas.


## 25. Primera sesión en Claude Code: verificación y decisiones de guion — 2026-11-06

- Verificación sin cambios: `node scripts/n8n-diff.mjs` de principal, precios, multimedia, derivación y QA contra n8n vivo, **sin diferencias**. Suite con PGlite: **545 pasan, 0 fallan/omitidas, 4 TODO históricos**. No se modificaron n8n, prompt, herramientas, credenciales ni webhook. Sin llamadas a la API del modelo ni gasto.
- **Cambia guion: aprobado por Mateo el 06/11, sin implementar.** Mateo considera que el agente ya responde bien y no quiere cambios grandes; estas definiciones quedan para cuando pida el ajuste y no deben volver a preguntarse:
  1. Si el cliente ya recibió precio y elige una opción («me quedo con tipo tapizado»), pasa a Candela.
  2. Si pide descuento o rebaja, pasa a Candela; el bot no dice ni sí ni no. Resuelve el pendiente 4 del traspaso.
  3. Si pregunta la diferencia entre fundas a medida y tipo tapizado antes de elegir envío o taller, se envía en ese turno el video comparativo. El brief ya indica que la diferencia no se escribe.
  4. Si pide una foto y sólo hay video (cubrevolante, CV01), se envía el video directamente. Resuelve el pendiente 5 del traspaso.
- Hallazgos de revisión, sin corregir:
  - El mensaje de apertura del brief («Cada funda se realiza a medida…») no salió en ninguna de las 11 corridas con Sonnet 5 sobre fundas (10 conversaciones de `PRUEBA_SONNET_5` y `PRUEBA_MEDIOS_PAGO`, más la repetición `_r2`); con Haiku salía a veces. Hay dos causas. El control de salida conserva sólo la continuación y las FAQ en los turnos con `buscar_precio`, incluido `requiere_modalidad`. Además, el bloque `base` dice «no agregues Hola/bienvenida/presentación». Por eso un ajuste de prompt solo no alcanza.
  - Medios 04/T1 (v9.3): explicó por escrito la diferencia en vez de enviar el video; queda cubierto por la decisión 3. En 04/T5, ante el pedido explícito del video ya enviado, respondió que «no se reenvía»: la herramienta admite `reenvio_solicitado` y el modelo no lo usó.
  - El principal no filtra por bandeja: ningún nodo usa `inbox_id` y el webhook de Chatwoot es de cuenta. Si el webhook 10 apunta al principal sin un filtro, el bot respondería en todas las bandejas de la cuenta 1. Es concreto para el pendiente 9 del traspaso; revisarlo antes de conectar.
- Backup de despliegue: no aplica. Sin commit/push.


## 26. Ensayo de seis casos realistas — 2026-11-06

- Pedido de Mateo: seis conversaciones largas (6 turnos del cliente) fieles a la realidad. Nueva etapa `casos-reales` en `scripts/test-integral-f7-api.mjs` (Sonnet 5, prompt publicado v9.4, guard actual, tope USD 1,50, ledger propio), fixture `tests/fixtures/casos-reales-f7-2026-11-06.json` y test `tests/casos-reales-f7.test.mjs`. De los 46 mensajes del cliente, 32 son literales del corpus (verificados por test), 6 adaptados y 8 son puentes sintéticos.
- Ejecución: 36 turnos, 54 generaciones, USD 0,8227845, reserva incierta cero. MOCK_TRANSPORTE: sin envíos reales. Reporte `PRUEBA_CASOS_REALES_F7_2026-11-06.json`, vista `PRUEBA_CASOS_REALES_F7_2026-11-06.html` y revisión [REVISION_CASOS_REALES_F7_2026-11-06.md](REVISION_CASOS_REALES_F7_2026-11-06.md). Suite: 548 pasan, 0 fallan, 4 TODO.
- **Bugs nuevos** (1–3 corregidos y publicados el mismo día, ver §27; el 4 espera decisión de Mateo):
  1. `resolverModalidad` descarta «con envío» si el mismo mensaje dice «Si me puede…» (regla `/\bsi\s+[^,]/` sobre el texto completo). Está embebida en el principal y en precios. En el caso 04 el cliente nunca recibió precio.
  2. El motor de precios no resuelve DUSTER 2017+: la fila «DUSTER » coincide siempre, incluso con el nombre exacto y el año. Las Duster de 2017 en adelante no se pueden cotizar.
  3. El separador de mensajes corta la dirección en «Av.» («📍La dirección es Av» / «Olivera 1265 , CABA») y pega el link de Maps a la frase siguiente.
  4. Los textos de aclaración de la herramienta de precios llegan al cliente con tono técnico («Opción publicada: …», «No encontré ese modelo o producto en la lista consultada»).
- Desvíos del modelo observados: modalidad preguntada con palabras propias y repetida; lista de productos de entrada; apertura de fundas ausente en 3 de 5 casos de fundas; «alfombra trasera» convertida en baúl/habitáculo; sin recotizar tras corregir el vehículo; fotos no pedidas; guion de objeción usado ante una despedida. Detalle por turno en la revisión.
- No se modificaron prompt, herramientas, n8n, credenciales ni webhook. Sin commit/push.


## 27. Correcciones publicadas de los bugs del ensayo — 2026-11-06

- Pedido de Mateo: arreglar los tres bugs técnicos de §26 que no tocan el guion. El cuarto (textos técnicos de la herramienta de precios) queda para su decisión.
- Correcciones en las fuentes:
  1. `src/precios/modalidad-contexto.mjs` (`resolverModalidad`): los condicionales («si …»), las dudas y las citas se evalúan solo en la oración que menciona envío, taller o CABA. Los puntos suspensivos no cortan la oración. «Soy de chaco, con envío… Si me puede hacer un presupuesto» queda como envío; «si es fácil prefiero envío» sigue sin confirmar.
  2. `src/precios/motor.mjs` (`resolver`): con año informado, una fila con años que lo cubre descarta a la fila del mismo nombre sin años (DUSTER 2017+ frente a DUSTER). La Duster 2017+ ahora cotiza; la Duster 2012 y la Duster sin año no cambian. Las filas con otro nombre (HILUX CABINA SIMPLE) siguen pidiendo aclaración.
  3. `src/unificado/logica.mjs` (`splitResponse`): «Av.» y «Avda.» no cortan el mensaje y una línea en blanco separa mensajes. Un salto de línea simple sigue sin separar, como piden los tests existentes.
- Tests nuevos en `tests/bugs-casos-reales-2026-11-06.test.mjs`: 7 en total, 3 de ellos en rojo antes del arreglo. Suite completa: 555 pasan, 0 fallan, 4 TODO.
- Snapshots: el script `scripts/fixes/2026-11-06-bugs-casos-reales.mjs` es idempotente y reemplaza solo el código embebido exacto, en `Preparar Estado` y `devuelve outputs` del principal y en `Validar pedido` y `Resolver cotizacion` de precios. En precios el módulo embebido termina en CRLF, así que se compara sin el salto final.
- Publicación: diff previo limpio, dry-run y después import de a un flujo con backup.
  - Precios: versión `b422e0f9-ee9e-4922-9de6-64d9f239011c`, backup en `backups/2026-11-06_142426/`.
  - Principal: versión `cb090b9f-e98f-46be-ad58-c1e5e2f8cf59`, backup en `backups/2026-11-06_142452/`.
- Readback con `scripts/verificar-publicacion-bugs-f7.mjs`:
  - En los dos flujos, la versión activa es la guardada y el grafo activo es idéntico al snapshot, con credenciales y conexiones conservadas.
  - El código extraído de la versión activa, ejecutado localmente, resuelve los tres casos.
  - Evidencia en `PUBLICACION_BUGS_CASOS_REALES_F7_2026-11-06.json`. Export y diff final limpios.
- Repetición por API de los casos 01, 02 y 04 (reporte `PRUEBA_CASOS_REALES_F7_2026-11-06_r2.json`, vista `_r2.html`):
  - Consumo: 22 generaciones y USD 0,3364305. La etapa acumula USD 1,159215 de 1,50, con reserva incierta cero.
  - Confirmado: la Duster 2017 cotiza ($466.092), «con envío» se registra a la primera, y la dirección sale entera con el link en un mensaje aparte.
- Hallazgos nuevos, sin corregir:
  - El control de salida tomó «Así te paso el presupuesto con todo» como un presupuesto prometido sin acción (regla `cotizacion_sin_accion`) y derivó a Candela antes de contestar pago y demora (caso 04, T3). Corregido y publicado en §28.
  - «Strada Freedom» o «freedon» no encuentra tarifa ni sugiere STRADA, y el cliente lee «No encontré ese modelo…».
  - La dirección no sale si el modelo le agrega un prefijo («Y sobre la dirección:»), porque la lista de FAQ del control exige la frase exacta (caso 02, T1).
  - Al elegir «la segunda» después del precio, la primera corrida derivó y la repetición no; además agregó afirmaciones de durabilidad y repitió el cierre. Corresponde a la decisión 1 de §25, que sigue sin implementar.
- Pendientes:
  - El QA manual (inactivo) conserva la regla de modalidad anterior.
  - El bloque `decision` del prompt sigue citando «Duster con 2018» como ejemplo de ambigüedad, cosa que ya no ocurre. No tiene efecto y el prompt no se tocó.
  - Sin commit ni push.


## 28. Control de salida: falso pase por «te paso el presupuesto» — 2026-11-06

- Pedido de Mateo: corregir el falso positivo de §27.
- Causa: la regla `cotizacion_sin_accion` de `src/unificado/salida-comercial.mjs` trataba igual tres cosas. Por un lado, el pasado («te pasé el presupuesto»). Por otro, el presente con finalidad o condición («así te paso…», «cuando me confirmes te paso…»). Y también el sustantivo «envío» seguido de «presupuesto».
- Corrección en la función `anunciaCotizacionSinAccion`:
  - El pasado y el participio siguen derivando. Excepción: el subjuntivo «para que te pase».
  - «Te paso / te mando / te envío» deriva salvo que la frase tenga antes una finalidad o una condición: así, para que, cuando, apenas, en cuanto, una vez que, o «si» seguido de una palabra.
  - «Sí, te paso…» sigue derivando, porque el «sí» con coma no es condición.
  - Para las formas en presente hace falta el «te», así que el sustantivo «envío» ya no dispara la regla.
  - Se mantiene el test de Codex que bloquea «Te paso el presupuesto.».
- Tests: 3 nuevos en `tests/bugs-casos-reales-2026-11-06.test.mjs`, incluido el texto real de r2 (en rojo antes del arreglo). Suite: 558 pasan, 0 fallan, 4 TODO.
- Snapshot: el mismo script `scripts/fixes/2026-11-06-bugs-casos-reales.mjs` reemplazó el módulo en `Controlar salida comercial` y `Salida comercial confirmada`. La regla anterior transcripta se validó contra el guard congelado R2.
- Publicación del principal: diff previo con solo esos 2 nodos, dry-run e import con backup en `backups/2026-11-06_143401/`. Versión `c8f4cb69-d674-4bd1-b4bd-136ecf557621`, con 121/121 nodos.
- Readback con `scripts/verificar-publicacion-bugs-f7.mjs`, ahora acumulativo:
  - El grafo activo es idéntico al snapshot.
  - El control extraído de la versión activa entrega el texto real del caso 04 sin pase, y «Te paso el presupuesto.» sigue derivando.
  - Las correcciones de §27 siguen verificadas.
  - Evidencia actualizada en `PUBLICACION_BUGS_CASOS_REALES_F7_2026-11-06.json`. Export y diff limpios.
- Repetición del caso 04 (`PRUEBA_CASOS_REALES_F7_2026-11-06_r3.json`, vista `_r3.html`):
  - Consumo: 9 generaciones, USD 0,1542315. La etapa acumula USD 1,3134465 de 1,50.
  - No hubo pase prematuro y la conversación llegó al final. En el T3 el modelo volvió a consultar el precio en vez de escribir la frase anterior, así que la prueba de la corrección es el texto real de r2 sobre el código publicado.
- Sigue abierto en el caso 04:
  - «Strada Freedom» no encuentra tarifa: la búsqueda exige que el nombre de la fila contenga el nombre pedido y no prueba quitando la versión.
  - Si `buscar_precio` no resuelve en el turno, el control deja salir solo la continuación y las FAQ de la lista, y descarta las respuestas del modelo sobre formas de pago y tarjeta.
  - La respuesta a «caro + desconfianza por la seña» alterna entre las dos trabas del brief según la corrida.
- Sin commit ni push.


## 29. Conexión a WhatsApp y limpieza de n8n — 2026-11-06

- Pedido de Mateo: dejar todo publicado y funcionando para probar por WhatsApp y archivar los flujos que no se usan. Autorizó expresamente redirigir el webhook de Chatwoot y archivar los 20 flujos listados.
- Relevamiento, solo lectura:
  - La cuenta 1 de Chatwoot tiene dos bandejas: la 1, «F7 inbox» (WhatsApp +…7202), y la 3, «Test Bot API».
  - El único webhook, el 10, apuntaba a «AGENTE PRUEBA 2» con 9 eventos. AGENTE PRUEBA 2 solo usa `anotar_datos_del_comprador`.
  - Ningún flujo activo ajeno llamaba a la cadena F7 vieja.
  - El principal usa «Log Mensaje», que queda activo.
- Filtro de bandeja:
  - `normalizeEvent` (`src/unificado/logica.mjs`) acepta solo la bandeja 1; si el evento no trae dato de bandeja, se acepta como antes.
  - Test nuevo en `tests/unificado-bandeja.test.mjs`, en rojo antes del cambio. Suite: 561 pasan, 0 fallan, 4 TODO.
  - Snapshot actualizado con `scripts/fixes/2026-11-06-bugs-casos-reales.mjs` (nodo «Normalizar evento», campo `jsonOutput`).
  - Principal publicado: versión `0e84610f-fb8d-4c34-a976-6fd5de97ea35`, backup en `backups/2026-11-06_152148/`.
  - Readback: el grafo activo es idéntico al snapshot, y la función publicada acepta la bandeja 1 y rechaza la 3.
- Webhook:
  - El 10 ahora apunta a `https://n8n.teotec.org/webhook/f7-principal-unificado-v1`, solo con `message_created` (el único evento que procesa el principal).
  - Lo hace `scripts/conectar-chatwoot-principal-f7.mjs`: dry-run por defecto, backup de la configuración anterior en `backups/2026-11-06_152314-chatwoot-webhook/webhook-10.json` y opción `--restaurar <backup> --yes` para volver atrás.
  - AGENTE PRUEBA 2 deja de recibir eventos de esta cuenta; su flujo no se modificó.
- Archivado, no borrado, de 20 flujos F7:
  - Los 8 de la cadena vieja que estaban activos (Agente de ventas V2.10, Memory Manager, Herramienta precios, fotos y humano, Registrar Intención, Cotizar Combo y Cleanup) se desactivaron antes de archivarlos.
  - Los 12 inactivos: copias BACKUP de abril, Media Proxy, QA manual y Test Runner.
  - Lo hace `scripts/archivar-flujos-viejos-f7.mjs`, que verifica el nombre de cada flujo antes de tocarlo. El JSON completo de cada uno y un resumen quedaron en `backups/2026-11-06_152432-archivado-f7/`. Se restauran desde Archivados en n8n.
- Estado final:
  - Activos de F7: principal, precios, multimedia, derivación y Log Mensaje.
  - Sin cambios en AGENTE PRUEBA 2, `anotar_datos_del_comprador`, TEOTEC Leads y la Calculadora.
  - La conversación 27 está en la bandeja 1, abierta, sin la etiqueta `humano` y con ventana de respuesta.
- Pendiente:
  - La prueba real desde el WhatsApp de Mateo. Conviene empezar con «borrar»: la memoria anterior se indexaba por teléfono, compartido con AGENTE PRUEBA 2.
  - ~~El saldo de la credencial «Anthropic account» de n8n.~~ Resuelto: Mateo cambió la clave de esa misma credencial (id `DEfyEaB6F8J0e6aN`, actualizada a las 19:24 UTC), sin tocar los flujos (diff limpio de los 4). Lo verificó `scripts/probar-credencial-anthropic-f7.mjs`, que usa un flujo temporal `I9QkTr5xsNzgdupP`, ya desactivado y archivado: Anthropic respondió HTTP 200 con `claude-sonnet-5` («OK», 16/4 tokens). «OpenAi account», que se usa para los audios, no se verificó.
  - La rotación de tokens antes de abrir a clientes.
  - `scripts/workflows.json` conserva los tiers históricos (la cadena vieja figura como `prod` aunque esté archivada), así que `npm run export` sin argumentos sigue sin servir: usar los slugs explícitos.
- Sin commit ni push.


## 30. Respuesta a todos: memoria por conversación y etiquetas viejas — 2026-11-06

- Pedido de Mateo: el bot no respondió en la conversación 14 y tiene que responder a todos, para pasárselo a sus clientes.
- Diagnóstico:
  - Alan escribió «Hola hacen envíos a bariloche», «Precio» y «Precio» (20:19–21:37 UTC). Las ejecuciones 36420–36422 se cortaron en «Verificar Label Humano» por la etiqueta `humano` que quedó de pruebas de junio.
  - Las ejecuciones 36415–36419 de las 19:45 eran ecos de la respuesta del bot a Mateo en la conversación 27 («Decime, lo vas a colocar en nuestro taller en CABA o te lo enviamos?»), y el filtro las descartó bien. Con Mateo el bot funcionó.
- Hallazgo de memoria: sin «borrar» (epoch 0), la key de memoria era el teléfono, compartida en `n8n_chat_histories` con el bot viejo y con AGENTE PRUEBA 2. El agente y el control de modalidad leían ese historial; la sesión de Alan, por ejemplo, usaba su número.
- Cambio:
  - `f7_recibir_evento_reinicio` (`src/reinicio/sql.mjs`) ahora devuelve `f7:unificado:v1:1:<conversación>:memoria:<epoch>` también para epoch 0. El historial anterior no se borra; solo deja de leerse. Buffer y lock no cambian.
  - Los tests de `reinicio-sql` se actualizaron al contrato nuevo (en rojo antes del cambio).
  - La función está embebida en el principal y en las tres herramientas, y cada una la recrea al ejecutarse. Por eso se actualizaron las cuatro con `scripts/fixes/2026-11-06-bugs-casos-reales.mjs` (en las herramientas, la variante sin «SELECT true AS ready;»).
  - Suite: 561 pasan, 0 fallan, 4 TODO.
- Publicación con dry-run e import de a un flujo, las herramientas primero:

  | Flujo | Versión | Backup |
  |---|---|---|
  | Precios | `ff526c89` | `194440` |
  | Multimedia | `e2729188` | `194454` |
  | Derivación | `35d0e04c` | `194518` |
  | Principal | `a7eed81d` | `194538` |

  En el readback, los cuatro grafos activos son iguales a los snapshots y usan la key nueva. Export y diff limpios. Evidencia en `PUBLICACION_BUGS_CASOS_REALES_F7_2026-11-06.json`.
- Etiquetas: `scripts/limpiar-etiqueta-humano-f7.mjs` (dry-run o `--yes`) quitó `humano` de las conversaciones 13 y 14, que eran las únicas con esa etiqueta entre las 14 de la bandeja. El resto de las etiquetas se conservó. Backup en `backups/2026-11-06_194645-etiquetas-humano/`.
- Efecto: en su próximo mensaje, cada conversación, incluida la 27, arranca con el saludo y sin contexto viejo. Los mensajes de Alan que ya se habían enviado no se responden retroactivamente.
- Pendiente: confirmar con un mensaje nuevo de Alan o de otro contacto. Sin commit ni push.


## 31. Primera prueba real: la pregunta de modalidad en bucle — 2026-11-07

- **Reporte de Mateo** (conversación 14, 06/11 de 21:22 a 21:27 ART): el cliente contestó «Colocarlo en su taller» dos veces y después «Colocación en CABA / En su taller», y el bot repitió en cada turno «Quisieras la opción de envio o colocarlo en nuestro taller?».
- **Diagnóstico** (ejecuciones 36423, 36433, 36440 y 36447):
  - «Leer Estado» falla con `Syntax error at line 13 near "content"`. Como tiene `alwaysOutputData` y `continueErrorOutput`, igual pasa un ítem vacío a «Preparar Estado».
  - `historial_humano` llega `undefined`. `resolverModalidad` exige un array, devuelve null y la modalidad queda `sin_confirmar`, incluso con «Colocación en CABA».
  - `buscar_precio` responde `requiere_modalidad` y el agente copia la pregunta.
  - Cada ejecución termina en «Detener con error».
  - También se perdía `multimedia_registrada`, el registro que evita repetir videos.
- **Alcance:**
  - Las 7 ejecuciones con error del principal son todos los mensajes reales que procesó desde que se conectó el webhook (§29): las 36397, 36402 y 36412 (pruebas de Mateo del 06/11, conversación 27) y las 4 de la conversación 14.
  - Ninguna conversación por WhatsApp pudo confirmar la modalidad ni recibir una cotización.
- **Causa 1:** `src/reinicio/aplicar-principal.mjs:95` insertaba el filtro de multimedia con `replace(texto, plantilla)`.
  - El `$'` de la regex SQL `'^[1-9][0-9]{0,31}$'` se expandió al resto de la consulta, que quedó duplicada.
  - Entró con la publicación del reinicio del 06/11: el backup `2026-11-06_111640` está sano y el `2026-11-06_142452` ya está roto.
  - Los tests solo buscaban con una regex que el filtro estuviera presente.
- **Causa 2:** aun con historial, `resolverModalidad` no reconocía las respuestas que repiten las palabras de la pregunta. «Colocarlo en su taller», «Dale, colocarlo en su taller», «Prefiero colocarlo en su taller» y «La opción de envío» daban null.
- **Cambios:**
  - `aplicar-principal.mjs`: el reemplazo ahora usa una función.
  - `src/precios/modalidad-contexto.mjs`: se agregaron los patrones `colocar(lo|la|los|las) en (el|su|tu)? (taller|caba)` y `opcion de envio`. Negación, pregunta, condicional y las dos opciones juntas siguen sin confirmar.
  - `scripts/fixes/2026-11-07-leer-estado-y-modalidad.mjs` (idempotente) repara el snapshot solo si la consulta es exactamente la que produce ese `replace`. También actualiza `resolverModalidad` en «Preparar Estado» del principal y en «Validar pedido» de precios, que la define pero no la llama.
- **Tests:** `tests/bugs-whatsapp-2026-11-07.test.mjs`, con 7 casos. 5 fallaron antes del cambio, uno con el mismo error de sintaxis al ejecutar la consulta en PGlite.
- **Guardado de Mateo en el editor:**
  - Mateo guardó y publicó el principal desde el editor de n8n (03:11Z, versión 4fe27cf7), y el importador lo rechazó por ser más nuevo que el export.
  - La comparación campo por campo no mostró cambios de contenido, solo lo que hace el editor al guardar:
    - borró parámetros con su valor por defecto: `method: GET`, `mode: runOnceForAllItems`, `unit: seconds` (Wait 1.1), `tail: false`, `batchSize: 1`, `binaryPropertyName` y `outputPropertyName` (`data`), y `source` y `mode` de executeWorkflow;
    - reordenó claves y movió `enviar_multimedia` en el lienzo;
    - agregó `binaryMode: separate`.
  - El clasificador de permisos denegó `--force`. Entonces se reexportó, con copia previa en `backups/2026-11-07-principal-local-antes-de-reexportar/`, y se reaplicaron los scripts de `scripts/fixes/`. Solo se publicaron los dos nodos corregidos.
  - 8 tests fijaban esos valores explícitos. Se adaptaron (`tests/unificado-grafo.test.mjs`, `tests/reinicio-runtime.test.mjs`) para que un parámetro ausente cuente como el valor por defecto de su tipo y versión de nodo. `digest` ignora el orden de las claves y la comparación ignora la posición en el lienzo.
  - Los mutantes siguen fallando: Wait1 en horas y un GET convertido en POST.
- **Publicación:** dry-run e import de a un flujo, sin `--force`. El dry-run del principal mostró solo «Leer Estado» y «Preparar Estado». `binaryMode` quedó en el vivo.

  | Flujo | Versión | Backup |
  |---|---|---|
  | Precios | `b0138672` | `2026-11-07_002217` |
  | Principal | `b215c660` | `2026-11-07_002712`, con la versión 4fe27cf7 de Mateo |

- **Readback** (`scripts/verificar-publicacion-bugs-f7.mjs`, chequeos 7 y 8):
  - Los 4 grafos activos son iguales a los snapshots.
  - El «Leer Estado» publicado corre en PGlite y devuelve el historial.
  - El «Preparar Estado» publicado da `caba` para «Colocarlo en su taller» y `envio` para «La opción de envío».
  - Export y diff de los 4 flujos, sin diferencias.
  - Suite: 568 pasan, 0 fallan, 4 TODO.
- **Pendiente:** acreditarlo en vivo con un mensaje nuevo. En la conversación 14 el historial ya guardado da modalidad `caba`, así que el próximo mensaje debería traer la cotización. Sin commit ni push.
- **Aprendizajes:**
  - Un guardado desde el editor de n8n deja el vivo más nuevo que el export: hay que reexportar y reaplicar `scripts/fixes/`, no forzar.
  - Un `replace` cuya plantilla contiene `$` tiene que usar una función.


## 32. Producción verificada y primer commit del proyecto — 2026-11-07

- **Pedido de Mateo:** «Publicá todo en producción y dejalo todo guardado».
- **Producción:** los 5 flujos de F7 están activos y publicados, sin borradores pendientes:
  - principal b215c660;
  - precios b0138672;
  - multimedia e2729188;
  - derivación 35d0e04c;
  - Log Mensaje.

  El export y el diff de los 4 flujos propios dan sin diferencias.
- **Lo que no entró:**
  - Las 4 decisiones de guion de §25 siguen sin implementar, porque no se pidieron.
  - AGENTE PRUEBA 2 tiene un borrador sin publicar. No es de F7 y no se tocó.
- **Git:**
  - El repositorio no tiene remoto, así que «guardado» es el primer commit local en `master`. La carpeta se sincroniza con Drive.
  - Entraron fuentes, prompts, scripts, tests, snapshots y documentación: 354 archivos, 13,5 MB.
  - El autor es Mateo, pasado solo para el commit, sin cambiar la configuración de git.
- **Escaneo de claves antes del commit**, sin imprimir valores. Se agregaron al `.gitignore`:
  - `.codex/`, que tiene la API key de n8n vigente.
  - `docs/historia/PLAN_REMEDIACION_v1.1.md`, `docs/historia/PLAN_REMEDIACION_v1.2.md` y `workflows/legacy/herramienta-pedido.json`, que tienen la clave `service_role` de Supabase (vence en 2036). Es la misma que está en `.env`.
  - `workflows/experimental/agente-prueba-2.json`, que tiene el token de Chatwoot vigente.
  - Los videos y fotos de `recursos/` (unos 317 MB, que ya están en Drive) y `.claude/scheduled_tasks.lock`.
- **Esos archivos no se editaron** y siguen en Drive con las claves en texto plano. Queda pendiente decidir si se redactan y si se rotan las claves. La rotación le corresponde a Mateo.
- **Escaneo final de lo que entra:**
  - 0 claves;
  - solo quedan referencias a `process.env` y marcadores de ejemplo (`TU_API_ACCESS_TOKEN`).
