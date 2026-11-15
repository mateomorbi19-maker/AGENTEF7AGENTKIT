# Herramienta multimedia F7 — plan de implementación

> Ejecución autorizada por Mateo: «Perfecto avancemos con el desarrollo de la herramienta haz un flujo nuevo». Se implementa el diseño explicado y aprobado en el chat; no se pide una segunda aprobación de ese diseño. Trabajo por componentes con revisión independiente, sin commits.

**Objetivo:** crear un nuevo workflow n8n `F7 · Enviar multimedia · v1`, invocable como una sola herramienta, capaz de seleccionar y enviar uno o varios productos sin alterar los workflows existentes.

**Arquitectura:** entradas tipadas → selección determinística desde catálogo cerrado → simulación sin I/O o envío serial por Chatwoot → registro por pieza → respuesta estructurada. Destino, modo y solicitud_id provienen del flujo llamador; el modelo solo decide solicitudes comerciales. Persistencia aislada mediante tres tablas Postgres para exclusión por conversación, huella de solicitud e historial por pieza.

**Tecnologías:** n8n (versiones de nodos ya usadas en la instancia), JavaScript/Node 24, Postgres, Google Drive, Chatwoot. Sin LLM dentro de la herramienta.

## Restricciones

- Nuevo flujo inactivo; no conectar al principal ni reemplazar la herramienta anterior en esta etapa.
- Credenciales existentes por referencia, sin crear/editar/rotar valores.
- Conservar originales multimedia; usar copias compatibles y un catálogo versionado.
- Mensajes limitados a adjuntos, sin pie de foto ni texto, según corrección explícita de Mateo del 2026-11-04. Títulos del catálogo solo internos. Sin cotizaciones ni cierres.
- Ningún envío real a clientes durante el desarrollo. La prueba real desde WhatsApp corresponde a Mateo según AGENTS.md.
- Si un medio no está disponible o no corresponde, devolver `sin_material`; nunca reemplazarlo por otro producto.
- No repetir automáticamente un POST de resultado incierto. Registrar y reconciliar antes de reintentar.
- Export inicial comprobado: solo diferencias anteriores de agente-ventas y memory-manager. Fuentes saneadas en backups/2026-11-04-multimedia-fuentes/.

## Componentes y comprobaciones

- [x] `src/multimedia/seleccion.mjs`: normalización estricta, listas por producto, formatos, diseños, comparación, eliminación de duplicados, resumen. Tests de las 15 combinaciones de productos y casos inválidos/mixtos/faltantes.
- [x] `src/multimedia/catalogo.json`: catálogo operativo con IDs remotos, versiones, hash, MIME, tamaño, productos visibles y rutas. Verificar material exclusivo tipo tapizado, archivos actuales VIP/Bastón y compatibilidad de medios.
- [x] `src/multimedia/sql.mjs` y `entrega.mjs`: bloqueo con vencimiento, idempotencia por solicitud/pieza, estados conservadores ante fallas y validación de respuestas Chatwoot. Tests de tiempo de espera, error parcial, control humano y respuestas malformadas.
- [x] `src/multimedia/construir.mjs`: generar un grafo legible con trigger tipado, simulación manual, nodos HTTP/Drive/Postgres, bifurcaciones de error conectadas y bucle serial.
- [x] Pruebas locales de código embebido y grafo, suite del repo, validación n8n. Revisor independiente antes del alta.
- [x] Crear nuevo workflow, releer y comparar nodos/conexiones/credenciales. No confundir validación estática con runtime. Creado `BArOU48SoyGqiDE7`; prueba real posterior autorizada por Mateo en conversación 27: ejecución 36251, cuatro videos enviados y lectura confirmada por consulta posterior a Chatwoot.
- [x] Registrar ID en scripts/workflows.json, exportar snapshot nuevo, documentar contrato/uso/límites y actualizar backlog.

## Riesgos que deben cubrir los tests

- Contexto o destinatario faltante, alterado o enviado como texto libre: fallar antes de enviar.
- Archivo compartido que nombra productos excluidos: no seleccionarlo.
- Misma solicitud_id con contenido diferente: rechazarla.
- Doble ejecución, error después de iniciar POST o de aceptar el canal: no reenviar por suposición.
- Error de consulta del control humano o pérdida del registro persistente: detener envíos de forma conservadora.

## Preparación externa

La carga inicial de archivos a Drive fue rechazada por auto-review por requerir autorización explícita de transferencia al destino. Mateo autorizó las diez piezas concretas a la carpeta `1YM8dcc_Dr6CcHpsoWVTyIXrjLAIqcJu9`; se completó la carga y se verificaron nombres, MIME y tamaños. Se conservaron originales y permisos. La autorización y el resultado constan en el manifiesto.

Revisión independiente: se corrigieron el ID BIGINT de replays y el margen de tiempo previo al POST. Mateo inició sesión y reconectó Drive; la prueba real autorizada descubrió que Crypto descarta el binario. Se corrigió con recuperación de la descarga vinculada a cada iteración y una regresión local. Ejecución 36251: cuatro videos aceptados, cuatro registros confirmados, bloqueo liberado; Chatwoot los marcó después `read`. Sigue pendiente probar el resto de los archivos y otros caminos en runtime. El MCP de ejecución no está configurado; se usó la UI autenticada sin ampliar acceso. Antes de integrar, alinear timeout de principal (300 s) y herramienta (480 s). Detalle y evidencias en `docs/ESTADO_Y_BACKLOG.md`, sección 12.
