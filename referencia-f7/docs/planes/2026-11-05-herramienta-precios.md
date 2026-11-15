# Herramienta de precios F7 — implementación aprobada

Objetivo: consultar la planilla oficial en vivo, cotizar con importes verificables y habilitar `buscar_precio` en el prompt del principal unificado.

Arquitectura: un subworkflow nuevo; validación de pedido → metadata de Sheets → lectura de hojas pertinentes con valores numéricos → parser y búsqueda determinísticos → aclaración o cotización → control humano y envío idempotente de una plantilla por Chatwoot → resultado estructurado. El principal conserva transporte, audio, buffer, modelo y credenciales. No se agregan managers ni sincronizadores de precios.

Tecnología: n8n, Google Sheets API, OAuth existente, JavaScript puro embebido en Code, Postgres para registro de cotizaciones, Chatwoot mediante credencial existente.

Especificación: diseño aceptado en el chat por Mateo el 2026-11-05. Contrato pedido `{consultas:[{producto,modelo?,anio?,configuracion?,cantidad?}],modalidad:caba|envio,tipo_solicitud:consulta|comparacion|combo}`. El modelo solo suministra `pedido`; cuenta, conversación, identificador y modo los fija el caller. Productos: fundas, tipo tapizado, tapiceria, alfombra, funda baul, cobertor caja, espuma, otros, cubrevolante.

Restricciones: no alterar planilla ni credenciales; no conectar flujos antiguos; no commits; sin envíos a clientes en pruebas. El principal permanece inactivo. Herramientas mandan la cotización, agente únicamente continuación o aclaración. No hay precios inferidos por porcentajes, aproximación de vehículo ni celda vacía convertida en cero. Precio no confirma medidas, existencia ni turno. Año solo cuando discrimina filas reales. Alternativas no se suman. En combos incompletos no hay total global.

Decisión comercial confirmada por Mateo: «El precio en cuotas es el mismo que de transferencia». Se aplica incluso cuando `Otros` contiene otra columna POSNET; se conserva evidencia del importe de transferencia y de este override. Envío no ofrece efectivo; costo de envío y medidas se confirman por separado. No se presupone una tarifa de flete.

Foco de revisión: límites de bloques y headers variables; duplicados conflictivos; selección por año/configuración; sumas por medio de pago; fallos de lectura; no repetir POST incierto; contexto confiable y bloqueo humano; prompt usa herramienta en el turno adecuado y no reescribe importes.

## Tareas y registro

- [x] Exportar y comparar principal, multimedia y herramienta antigua: sin diferencias.
- [x] Leer metadata y las ocho hojas oficiales; fixture y anomalías documentadas.
- [x] Verificar IDs de credenciales existentes sin leer valores secretos.
- [x] Motor puro y pruebas (agente precios_motor):35 casos específicos.
- [x] Texto del prompt y contrato de herramienta (agente precios_prompt):v4 con retorno compacto y continuación literal.
- [x] Constructor de subworkflow y transporte (root):ID uNguhYLYJ4vEASG0.
- [x] Integración preservando principal y multimedia (root):64 nodos, dos herramientas.
- [x] Pruebas unitarias, runtime sin mensajes y pequeño muestreo de LLM:209pass,0fail,4TODO; ejecución36307; rondaHaiku final3/3.
- [x] Revisión independiente y correcciones necesarias: rangos entre cláusulas, títuloMusso, entrega y retorno compacto.
- [x] Guardar en n8n, verificar lectura posterior, export y documentación final:diff limpio de principal/hijo/multimedia.

Se trabaja en el workspace actual para conservar los cambios ya autorizados de esta sesión; no se crea un checkout vacío ni se commitea el trabajo previo. Cada colaborador tiene archivos exclusivos. El registro permanece aquí para reanudar sin repetir implementación.

Cierre: guardado inactivo, sin publicación/activación ni envío real de cotizaciones. Runtime leyó las ocho hojas vía OAuth Drive existente (Sheets antiguo vencido); no hubo cambios de credenciales. Ensayo inicial Haiku falló y se conserva; el retorno compacto evita repetir importes en la ronda final. USD0,184324 entre ambas rondas. Pendientes de producción en ESTADO_Y_BACKLOG sección17.
