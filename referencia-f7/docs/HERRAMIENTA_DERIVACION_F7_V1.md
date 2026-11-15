# Derivar a Candela — F7 v1

Preparada localmente el 05/11/2026. El subagente no creó ni publicó workflows y no ejecutó POST a Chatwoot. El agente principal integra y verifica el despliegue por separado.

## Destino y alcance

Mateo confirmó que Candela usa la cuenta Chatwoot **Melanie, usuario 3**, dentro de account 1. La herramienta incorpora ese ID fijo; el modelo no elige cuenta, conversación, usuario, equipo, URL ni texto del mensaje. Usa las credenciales existentes: Chatwoot `EppfgYwuOOf4NkuN` y Postgres `xUzf8N4tUBZ8OH2Z`.

La cuenta Melanie apareció como administradora en GET `/agents`. Aunque no figura como miembro de inbox 1, el [control de conversación de Chatwoot](https://github.com/chatwoot/chatwoot/blob/develop/app/policies/conversation_policy.rb) permite acceso a administradores; el [servicio de asignación](https://github.com/chatwoot/chatwoot/blob/develop/app/services/conversations/assignment_service.rb) busca el usuario dentro de la cuenta. Es evidencia de código upstream, no una prueba iniciando sesión como Melanie. No se agregaron miembros, permisos ni credenciales.

La [autoasignación de Chatwoot](https://github.com/chatwoot/chatwoot/blob/develop/app/models/concerns/auto_assignment_handler.rb) puede sustituir al asignado cuando se abre una conversación y ese usuario no pertenece al inbox. Por eso el orden es **humano → open → asignación 3 → GET de verificación**. Un cambio manual posterior de estado puede volver a disparar la autoasignación de la instancia; la herramienta no modifica esa configuración.

## Contrato

Export del constructor: `construirWorkflowDerivacion()` en `src/derivacion/construir.mjs`, sin argumentos. Devuelve un workflow nuevo de 43 nodos incluyendo tres notas, con timeout de 180 segundos. Export de la descripción: `descripcionDerivacion` en `src/derivacion/descripcion.mjs`.

Trigger `Recibir derivacion`, Define Below:

```json
{
  "motivo": "persona",
  "account_id": 1,
  "conversation_id": 27,
  "solicitud_id": "cw:1:27:999:derivacion-v1",
  "modo": "enviar"
}
```

Solo `motivo` proviene del modelo: `avance_compra`, `pago`, `turno`, `persona`, `posventa`, `revision_especial`. Los otros cuatro campos son confiables y los fija el caller; el ID incluye el último mensaje consumido, no reloj ni ejecución. El principal limita una llamada por turno y debe aplicar su presupuesto de inicio de herramientas.

`modo: simular` termina antes de DB y Chatwoot. Admite el ejemplo mínimo `{motivo:'persona',modo:'simular'}` y devuelve plan de acciones y texto previsto, con `estado: simulado`, `envio.estado: simulado` y continuación vacía. No comprueba identidad/asignación viva ni representa un pase realizado.

## Ejecución y resultados

La herramienta valida cuenta/conversación/solicitud y reserva la operación en `public.f7_derivaciones`. Lee el chat; si ya tiene label humano, termina como `control_humano`, sin reasignar ni enviar confirmación, aunque lo tenga otra persona.

Para un pase nuevo conserva las etiquetas actuales y agrega humano, verifica, fija estado open, verifica, asigna usuario 3 y vuelve a verificar. Cada escritura de estado se confirma por una lectura posterior; un timeout del POST puede quedar reconciliado por ese GET sin repetir la escritura. Las tres condiciones y las etiquetas originales deben seguir verificadas para permitir confirmación.

Antes del mensaje se exige `can_reply === true`, tiempo disponible y una reserva SQL de envío. Luego se hace otro GET inmediatamente antes del POST. Si alguien tomó el chat, cambió la asignación, faltan labels o se cerró la ventana, no se manda confirmación.

La confirmación fija, aprobada para esta herramienta, es:

> La conversación quedó asignada a Candela para continuar con tu consulta.

No promete plazo de respuesta ni confirma pago, pedido o turno. No se manda nota privada: la conversación ya conserva el historial. El modelo recibe una salida compacta con `estado`, `bot_pausado`, `asignacion_confirmada`, `destino`, `envio`, `motivo`, `requiere_revision`, `continuacion_obligatoria` y `registro_confirmado` cuando corresponde.

| Estado | Interpretación |
|---|---|
| `derivado` | Se verificaron humano, open y usuario 3. `envio.estado` informa aparte el resultado de la confirmación. |
| `control_humano` | Ya estaba tomado. No se tocó la asignación ni se mandó otro mensaje. |
| `pendiente_asignacion` | Humano/open verificados, destino 3 no confirmado. |
| `parcial` | Se confirmó parte del pase, falta otra condición o persistencia. |
| `fallido` | La verificación conoce que el pase no se completó. |
| `desconocido` | No se pudo verificar el efecto actual o la solicitud ya estaba en curso. |
| `entrada_invalida` | Inputs fuera del contrato o solicitud incompatible; sin nuevos efectos. |
| `simulado` | Ningún efecto remoto. |

`bot_pausado` puede ser null cuando el estado actual no es verificable. `asignacion_confirmada` solo es true con triple verificación. El destino devuelto entonces es `{id:3,nombre:'Candela',cuenta_chatwoot:'Melanie'}`. Nunca se presenta pendiente_asignacion como éxito. Una repetición finalizada devuelve el resultado original marcado `repetido:true` y `verificacion:ejecucion_original`; no representa una nueva comprobación del estado actual.

`envio.estado: aceptado` acredita creación del mensaje en Chatwoot, no entrega/lectura. La repetición de un mensaje aceptado informa `omitido`. Timeouts, 408, 5xx o cuerpo inconsistente quedan `desconocido`; no se reintenta el POST. `can_reply` false o ausente impide el mensaje pero no revierte el pase confirmado.

Cuando hay pausa o efecto incierto, la continuación obligatoria es vacía. El principal debe copiarla y aplicar su propia barrera determinística antes de cada fragmento de salida. La herramienta no puede impedir por sí sola un mensaje residual de otra rama del principal. Reanudar la atención requiere una decisión del operador; esta herramienta nunca quita humano.

## Idempotencia y fallos

La tabla es aislada, usa RLS y SQL parametrizado. Clave por cuenta/conversación/solicitud y owner de ejecución; un índice único parcial permite una sola derivación en curso por conversación. Otra conversación no queda bloqueada.

Estados internos: reservado, enviando y finalizado. El resultado final registra por separado éxito/fallo/incertidumbre del pase y de su mensaje. `enviando` se persiste antes del único POST de confirmación. Si la escritura final falla, se conserva el bloqueo y no se manda de nuevo. Un proceso cortado en reservado/enviando exige conciliación; no borrar filas para forzar un reintento.

El endpoint de labels reemplaza la lista completa: se preserva el snapshot leído y se verifican sus etiquetas. Esto reduce pérdida accidental, pero no es una transacción contra escrituras simultáneas de operadores externos. Tampoco el GET inmediatamente antes del mensaje elimina la mínima carrera entre verificación y POST. La versión actual de la API no ofrece una escritura condicional para agrupar esas operaciones.

## Verificación local

- 21 pruebas aprobadas, sin fallos ni omitidas en la suite `tests/derivacion*.test.mjs`, con SQL real PGlite. Cubre idempotencia/propiedad/concurrencia, simulación sin I/O, preservación de labels, humano previo, orden open→asignación, can_reply, asignación fallida, timeout conciliado por GET, pérdida de etiquetas, toma por otro operador antes del mensaje y confirmación incierta sin segundo POST.
- Validador n8n runtime sobre el constructor: válido, cero errores y cero advertencias; 40 nodos operativos, 61 conexiones, 29 expresiones. Los tres sticky notes explican los 43 nodos totales.
- El harness de recorrido simula HTTP y persistencia para recorrer el grafo; se distingue de la prueba SQL real local. No acredita runtime en n8n ni asignación real en Chatwoot.

Fuentes originales y auditoría inicial: `docs/DERIVACION_F7_AUDITORIA_2026-11-05.md`. Código puro: `src/derivacion/motor.mjs`; esquema/consultas: `src/derivacion/sql.mjs`.
