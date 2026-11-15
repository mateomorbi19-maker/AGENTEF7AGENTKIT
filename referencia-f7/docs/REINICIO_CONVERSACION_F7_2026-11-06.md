# Comando borrar — 6 de noviembre de 2026

Implementación autorizada por Mateo: reiniciar el contexto del chat y quitar la pausa humana, aun después de derivar a Candela. No cambia el guion comercial ni el modelo.

## Comportamiento

- Se detecta después de los tres IF de entrada, antes de audio, Redis y modelo. La rama del comando no atraviesa ningún Wait ni llama al LLM.
- Reconoce el comando entero con mayúsculas, tildes, espacios y signos: `borrar`, `BORRAR`, `/borrar`, `¡borrá!`, `borrame`, `borrar mi memoria`, `borrar todo`. Una consulta que contiene la palabra, como `no quiero borrar nada`, no lo activa.
- La confirmación es exactamente: `Ya borre mi memoria, a partir de ahora comienza una conversación nueva`.
- Quita únicamente la etiqueta `humano`, conserva las otras etiquetas y verifica la lectura posterior. No desasigna a Melanie ni modifica la bandeja.
- Un webhook duplicado del mismo comando no reinicia otra vez ni manda dos confirmaciones. Si falla la verificación o el envío queda incierto, no se reintenta el POST a ciegas.
- Para empezar una prueba nueva, enviar el comando y esperar esa confirmación antes del siguiente mensaje.

## Sesión y concurrencia

La memoria anterior estaba indexada por teléfono. El reinicio usa una nueva clave por cuenta/conversación/ID del comando, de modo que un chat distinto del mismo contacto no pierda contexto. El historial anterior y la auditoría quedan conservados, fuera del contexto nuevo del agente: esto no es un borrado físico de Chatwoot o de registros históricos.

La tabla `f7_reinicios_conversacion` registra la última época, ejecución dueña, preparación y resultado del ACK. La función SQL valida datos parametrizados, conserva el mayor ID y evita doble reserva. Usa la credencial Postgres existente; RLS habilitado y función SECURITY INVOKER.

El buffer de la sesión anterior se vacía; el lock anterior no se elimina desde el comando. Las ejecuciones conservan sus claves originales y no pueden liberar el bloqueo de la sesión nueva. Se verifica la época antes de encolar, consumir, llamar al agente, saludar y enviar cada fragmento. Un mensaje posterior que ya obtuvo la época nueva mientras termina el reset espera un segundo y revalida; ese Wait pertenece al mensaje normal, no al comando.

Precios, multimedia y derivación verifican el corte antes de sus seis POST externos. Ante una ejecución obsoleta cierran sus registros y liberan sólo su propio lease. Las piezas multimedia del contexto se filtran por el ID del mensaje que originó la solicitud, no por la fecha de actualización de su resultado.

Límites conocidos: un HTTP que ya empezó no puede revocarse; la consulta SQL y el POST no forman una transacción atómica. Un mensaje nuevo que llega antes de completar el comando y capturó la época anterior se descarta al detectar el cambio para no responder con contexto viejo. Esperar el ACK evita esa carrera. No se promete cancelación retroactiva de mensajes ya enviados.

El webhook actual carece de autenticación propia. Antes de cualquier efecto del comando se consulta el mensaje persistido en Chatwoot y se comprueban ID, cuenta, conversación, contacto, contenido, carácter entrante/público y fecha reciente. Un evento inventado o repetido desde un historial viejo no alcanza para reiniciar.

## Publicación y comprobaciones

Se publicaron el principal y las tres herramientas, una por vez, con backup previo. No se creó un workflow adicional, no se alteraron credentials ni se activó/desactivó nada. Sonnet 5, prompt v9.4, argumentos de herramientas y textos comerciales permanecen iguales.

| Flujo | Nodos | Versión activa |
|---|---:|---|
| Principal | 121 | `2f840d76-0527-4467-b34d-a513a87da601` |
| Precios | 42 | `6e4e9300-19bf-4a5a-b1ba-9c0116caac22` |
| Multimedia | 62 | `c586a875-af1b-40be-a2f5-461be653e0b4` |
| Derivación | 62 | `1a23f8ba-8d53-4be5-8aec-71f5de9eb365` |

- Suite completa: 545 pasan, cero fallos/omitidos, cuatro TODO históricos. Validación MCP de los cuatro snapshots sin errores.
- Runtime local de los nodos exactos: SQL real en PGlite; HTTP y Redis simulados. Verifica reinicio completo, aislamiento de memoria, otros chats intactos, duplicados, comandos falsos y fallas de transporte/confirmación.
- Cinco ejecuciones reales n8n `36357`–`36361`: filtros de nota privada, eco e identidad inválida; comando no persistido rechazado mediante GET real; evento normal con pausa humana que ejecuta el esquema/función Postgres reales y termina antes de Redis. Todas exitosas, cero POST, cero LLM, cero reinicios de chats reales.
- Readback: grafo publicado, conexiones, settings y credenciales cotejados; export/diff de los cuatro flujos limpio. n8n agregó automáticamente un `webhookId` al Wait nuevo; se conservó y se volvió a comprobar igualdad exacta. Las 21 pruebas dirigidas de grafo/runtime también pasan sobre el readback.
- Falta probar `borrar` de punta a punta desde WhatsApp. La confirmación y Redis no se ensayaron remotamente contra una conversación real. El webhook 10 de Chatwoot sigue apuntando a la ruta anterior, no al principal; no se modificó esa configuración reservada al operador.

Evidencia: `PUBLICACION_REINICIO_F7_2026-11-06.json`, `SMOKE_REINICIO_F7_2026-11-06.json`. Backups previos en `backups/2026-11-06_111626` (precios), `_111630` (multimedia), `_111635` (derivación), `_111640` (principal).

## Mantenimiento

`node scripts/preparar-reinicio-f7.mjs` aplica localmente la capa idempotente al principal y herramientas existentes; no publica. `scripts/preparar-prompt-f7.mjs` la reaplica al final si ya estaba instalada. Si se reconstruye una herramienta desde su constructor original, ejecutar también el preparador de reinicio antes del import. No cambiar solicitudes/IDs del caller para reiniciar; forman parte del contrato de idempotencia.

`node scripts/smoke-reinicio-f7.mjs` repite sólo las cinco verificaciones remotas sin efectos de envío. No acredita un ACK real. `node scripts/verificar-publicacion-reinicio-f7.mjs` realiza readback, compara credenciales y registra el destino del webhook sin exponer su URL ni secretos. Sin commits ni push.
