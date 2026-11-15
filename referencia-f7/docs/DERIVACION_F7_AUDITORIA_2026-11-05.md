# Auditoría de derivación F7 — 2026-11-05

Estado: auditoría de solo lectura; no se enviaron mensajes, no se cambiaron labels, usuarios, equipos, credenciales, bases ni workflows. Este informe es la única escritura del subagente.

## Conclusión

La herramienta legacy `nY0ek62uCk0MDt0R` no asigna a Candela: manda un mensaje y agrega labels. No conviene conectarla al principal nuevo como si resolviera el pase efectivo. Chatwoot account 1 no tiene un usuario ni equipo verificable llamado Candela. La identidad operativa requiere la respuesta de Mateo, ya solicitada por el agente principal; no asumir que Candela usa otra cuenta.

Puede prepararse una herramienta nueva que distinga pausa del bot, atención pendiente en bandeja y asignación específica confirmada. El estado `pendiente_asignacion` no equivale a `derivado` ni autoriza afirmar que se notificó a Candela.

## Evidencia viva de Chatwoot

Consultas GET usando el token local solo en memoria; host `chatwoot.teotec.org`, account `1`:

| Consulta | Resultado |
|---|---|
| `/api/v1/accounts/1/agents` | HTTP 200: Alan id 2, Mateo Morbiducci id 1, Melanie id 3. Todos administradores y offline al consultar. |
| `/api/v1/accounts/1/teams` | HTTP 200: lista vacía. |
| `/api/v1/accounts/1/automation_rules` | HTTP 200: lista vacía. No se verificó automatización de label a Candela. |
| `/api/v1/accounts/1/labels` | HTTP 200: butacas id 1, combo id 3, cuotas id 4. No figura `humano`, `turno` ni `venta` en el listado global. |
| `/api/v1/accounts/1/inboxes` | HTTP 200: F7 inbox id 1, WhatsApp; Test Bot API id 3. Ambos con asignación automática habilitada. |
| `/api/v1/accounts/1/inbox_members/1` | HTTP 200: solo Mateo Morbiducci id 1. |
| `/api/v1/accounts/1/inbox_members/3` | HTTP 200: lista vacía. |
| `/api/v1/accounts/1/conversations/24` | HTTP 404. La conversación histórica de smoke-test no sirve como destino verificado hoy. |

Que un usuario esté offline no implica que no se le pueda asignar; el problema aquí es que Candela no está identificada. Tampoco debe interpretarse la ausencia del label global como prueba suficiente de que el endpoint no pueda guardarlo en una conversación: ese efecto requiere prueba aislada de runtime. No se realizó durante esta auditoría.

## Fuente comercial y señales de pase

Fuente original: `C:/Users/mateo/Downloads/brief-comercial.md`, §8, líneas 262–281. El texto establece:

- Línea 265: el agente manda precios y preguntas para reunir información; después Candela cierra la venta, envía alias, confirma modelo y color, pide datos y fotos finales, las analiza y carga el pedido.
- Líneas 270–274: un accesorio suelto que necesita turno según disponibilidad se deriva siempre a Candela. CABA requiere turno; envío no implica turno; Bariloche tiene colocador.
- Línea 281: todo lo posterior a cotización y elección de diseño/color continúa manualmente.

`C:/Users/mateo/Downloads/cierre.md`, línea 190, aclara que cobertura, simulaciones y huecos preceden a las preguntas finales. La simulación de líneas 205–212 que se presenta como Candela, envía alias y declara el pedido señado no amplía el permiso del bot. Las líneas 413–415 mantienen situaciones de excepción sin resolución universal: no inventar políticas.

La definición de Mateo del 29/10 en `docs/ANALISIS_NUEVO_BRIEF_F7_2026-10-20.md`, §10, confirma el alcance: el bot asesora, muestra contenido, cotiza y detecta intención de avanzar; Candela sigue cierre/pago/pedido. No hace falta volver a pedir aprobación general.

El prompt actual `prompts/SYSTEM_PROMPT_F7_V1.md` conserva estos disparadores:

- Recorrido §7: cierre normal tras asesoramiento/contenido/cotización y preferencias; no retener al cliente con preguntas de diseño cuando pide una persona, pago, reserva, posventa o revisión especial.
- Errores: reclamo, pago ya realizado, reintegro, comprobante, cambio de tela/color de un trabajo entregado y descuento especial requieren revisión de Candela.
- Objeciones: insistencia en comenzar sin seña requiere revisión; no conceder excepción.
- Seguimiento: un «dale», «gracias» o emoji sin referente claro no confirma encargo ni turno.

Actualizar solo las declaraciones de capacidad y acción de derivación cuando exista la herramienta. El prompt actual afirma que el pase no está implementado; conectarla sin actualizar esas reglas dejaría un contrato contradictorio. No trasladar alias, cobro, validación de comprobantes ni carga del pedido al bot.

## Auditoría por nodo del legacy

Workflow `Herramienta humano`, activo, 32 nodos; draft y versión activa coinciden al consultar. `versionId=activeVersionId=792d24c6-8fd6-41c4-a159-64acf85a42b0`.

| Nodo o familia inspeccionada | Función y hallazgo |
|---|---|
| `When Executed by Another Workflow` | Inputs explícitos: conversation_id, telefono, motivo. Sin account, modo simulación ni solicitud idempotente. |
| `Switch Motivo` | Cinco coincidencias exactas: butacas_originales, turno, combo, cuotas, venta. Sin salida fallback. No cubre persona, posventa o revisión general del prompt nuevo. |
| `Mensaje Butacas Originales`, `Mensaje Turno`, `Mensaje Combo`, `Mensaje Cuotas`, `Mensaje Venta` | POST público a messages. Mensajes prometen contacto o coordinación antes de que haya pausa/asignación verificada. Ninguno asigna agente. Credencial Chatwoot `EppfgYwuOOf4NkuN`; no tokens literales en estos nodos. |
| `Log Butacas`, `Log Turno`, `Log Combo`, `Log Cuotas`, `Log Venta` | Invocan Log Mensaje `oFPF8jUXl7JSTTiO`, sin esperar subworkflow. El contenido se mantiene duplicado entre HTTP y log; Butacas incluso difiere en tilde de «contactará». |
| `Obtener Labels Actuales` | GET conversación después del mensaje y log. Usa `$json.conversation_id` del item previo, a diferencia de las otras ramas que anclan al trigger. Dependencia frágil del retorno del Execute Workflow. |
| `Obtener Labels Turno`, `Obtener Labels Combo`, `Obtener Labels Cuotas`, `Obtener Labels Venta` | GET conversación anclado al trigger. |
| `Preparar Labels`, `Preparar Labels Turno`, `Preparar Labels Combo`, `Preparar Labels Cuotas`, `Preparar Labels Venta` | Unen el array leído con `humano` y la etiqueta del motivo; preservan el snapshot de etiquetas. No existe asignación ni verificación posterior. |
| `Agregar Label Humano`, `Agregar Label Turno`, `Agregar Label Combo`, `Agregar Label Cuotas`, `Agregar Label Venta` | POST `/labels` reemplaza el array completo. Conserva lo leído, pero puede pisar etiquetas agregadas concurrentemente después del GET. |
| `Output`, `Output Turno`, `Output Combo`, `Output Cuotas`, `Output Venta` | Devuelven que la conversación fue derivada aunque solo se etiquetó. No comprueban assignee, estado open ni persistencia de humano. |

Problemas que impiden reuso directo: orden mensaje→log→label; ausencia de asignación; no idempotencia; no simulación; no gestión de resultado incierto; HTTP sin timeout explícito ni rama de error; motivos y frases de una versión comercial anterior. No se modificó el legacy.

## Principal nuevo y silencio

`m7jZDzyP17BayLrI` seguía inactivo al consultar, con 64 nodos. `Verificar Label Humano` lee correctamente `body.conversation.labels`. `Consultar conversación actual` y `Sigue habilitado el bot?` revalidan el label antes de entrar al procesamiento comercial.

Sin embargo, la ruta `AI Agent` → `devuelve outputs` → `Hay respuesta?` → fragmentación → `1ª Parte Respuesta1` no vuelve a consultar el control humano antes de cada POST. La herramienta de pase y una persona pueden poner humano mientras el agente responde. Para afirmar silencio efectivo, hace falta una barrera determinística posterior al agente y antes de cada fragmento; el prompt solo no alcanza. El camino de salida vacía ya existe mediante `skip_send`.

## Contrato mínimo recomendado

Herramienta separada `derivar_humano`, con trigger Define Below y un único retorno estable. Reusar la credencial existente; no crear ni modificar credenciales. Los motivos los selecciona el modelo; todos los identificadores y configuración de destino los fija el caller.

Inputs confiables: `account_id=1`, `conversation_id`, `solicitud_id=cw:1:<conversacion>:<ultimo_message_id_consumido>:derivacion-v1`, `modo`, último mensaje real y límites de ejecución. Solo `motivo` viene del modelo, enum sugerido: avance_compra, pago, turno, persona, posventa, revision_especial. No aceptar assignee_id, team_id, labels, URL o texto de confirmación del modelo.

Flujo de producción propuesto:

1. Validar contrato y resolver configuración de destino. No inventar ID de Candela. Si Mateo elige bandeja sin asignación, conservar esa decisión como modo explícito.
2. Reclamar idempotencia por solicitud y leer conversación actual. Si humano ya estaba presente por otra toma, devolver control_humano sin sobrescribir al operador ni mandar mensaje.
3. Agregar humano preservando todas las etiquetas leídas. Leer/verificar persistencia. Guardar fase alcanzada para distinguir un pase propio incompleto de uno ajeno al reintentar.
4. Abrir con `POST .../toggle_status` y body `{status:'open'}` si hace falta. No usar toggle sin status explícito.
5. Si hay destino autorizado, `POST .../assignments` con assignee_id real, previamente validado contra account y bandeja. No confiar en HTTP 200 sin comparar el GET posterior. No sustituirlo por Mateo u otro usuario sin decisión.
6. Verificar label, status y destino con GET. Una asignación automática al abrir no confirma identidad de Candela.
7. Opcional: nota privada con motivo y cita del mensaje entrante real, no un resumen libre que invente datos. Registrar su id y estado por solicitud; no duplicarla tras timeout. Para el mínimo puede omitirse si la conversación ya contiene toda la información.
8. El texto de confirmación, si se manda, sale desde la herramienta después de la verificación y queda idempotente. El agente devuelve vacío al tomar el control humano. No prometer tiempo de respuesta. No reintentar POST de mensajes/nota tras timeout o 5xx sin conciliación.

| Estado de retorno | Significado estricto |
|---|---|
| derivado | Humano persistido, open y asignación al destino autorizado confirmados. No acredita lectura ni atención de Candela. |
| pendiente_asignacion | Pausa y open confirmados; no hay asignación específica confirmada. No decir «derivado a Candela». |
| control_humano | El equipo ya tenía la conversación. No nuevas acciones comerciales ni mensajes. |
| parcial | Alguna acción se confirmó, otra falló; conservar detalle y bot_pausado real. |
| fallido | No se logró el pase y se conoce el fracaso. |
| desconocido | Alguna escritura pudo ocurrir; no repetir ni afirmar resultado. Requiere conciliación. |
| simulado | No modificó Chatwoot, no envió mensajes ni escribió en tablas operativas. |
| entrada_invalida | No ejecutó efectos. |

Retorno propuesto: `estado`, `bot_pausado`, `asignacion_confirmada`, `destino` solo verificado, `nota.estado`, `mensaje.estado`, `continuacion_obligatoria`, `requiere_revision`. No usar un solo booleano ok para todo.

## Fuentes API y límites

- [Asignar conversación](https://developers.chatwoot.com/api-reference/conversation-assignments/assign-conversation): POST assignments con assignee_id o team_id. La identidad debe venir de configuración verificada.
- [Agregar labels](https://developers.chatwoot.com/api-reference/conversations/add-labels): reemplaza la lista completa de la conversación. Requiere preservar etiquetas y considerar concurrencia.
- [Cambiar estado](https://developers.chatwoot.com/api-reference/conversations/toggle-status): permite fijar explícitamente open.
- [Servicio de asignación de Chatwoot](https://github.com/chatwoot/chatwoot/blob/develop/app/services/conversations/assignment_service.rb): el código actual busca un usuario por id; por eso se recomienda verificación posterior, no asumir éxito por respuesta HTTP.

La documentación/source upstream no identifica la versión exacta instalada. La instancia aceptó api_access_token en los GET realizados; no cambiar la credencial por ejemplos recientes de Authorization Bearer. Esta auditoría no acredita runtime de los POST propuestos.

## Actualización posterior — identidad confirmada e implementación local

Mateo confirmó en esta sesión que Candela usa **Melanie id 3**. Esa respuesta resuelve el bloqueo de identidad del relevamiento inicial. Se preparó una herramienta nueva en `src/derivacion/`, con destino fijo y sin tocar el legacy, los miembros de inbox, permisos o credenciales. Ver `docs/HERRAMIENTA_DERIVACION_F7_V1.md` para el contrato implementado, SQL, pruebas y límites. El subagente no creó/publicó workflows ni ejecutó escrituras de Chatwoot; la integración y runtime corresponden al agente principal.
