"""Lo que el modelo lee de derivar_humano: la descripción y la del argumento.

Copiadas byte a byte del nodo «derivar_humano» del principal publicado
(referencia-f7/n8n/agente-principal-unificado.json). No tocar: son contrato.
"""

DESCRIPCION_DERIVAR_HUMANO = (
    "Pasa la conversación actual a Candela, que usa la cuenta Melanie en Chatwoot. Usala cuando está listo para cerrar la compra, concretar el pago o reservar, pide una persona, consulta posventa o necesita revisión especial. Preguntar cuánto sale en efectivo, transferencia o cuotas, incluso \"quiero pagar en efectivo, cuánto sale?\", es consultar un precio: usá buscar_precio. Débito u otro medio sin regla autorizada requiere revision_especial, sin prometer aceptación ni tarifa. No retengas con preguntas de diseño/color si pide atención humana. No deriva por gracias, emoji, dale sin referente claro ni diseño aislado.\n"
    "Solo elegís motivo: avance_compra, pago, turno, persona, posventa o revision_especial. Cuenta, conversación, solicitud, modo y destino los fija el sistema. No inventes otro identificador ni repitas la llamada para sortear un fallo.\n"
    "La herramienta agrega humano preservando etiquetas, abre el chat y lo asigna al usuario autorizado. Verifica las tres acciones antes de mandar una única confirmación. Un chat que ya tiene humano se deja intacto, aun si está asignado a otro operador. El pase no confirma que Candela lo haya leído, que atenderá en un plazo, un pago, pedido ni turno.\n"
    "Leé estado y envio.estado por separado: derivado confirma pausa/apertura/asignación, no entrega del mensaje; control_humano significa que ya lo tomó el equipo; pendiente_asignacion/parcial/desconocido requieren revisión y nunca significan pase confirmado. simulado no modifica nada. Copiá continuacion_obligatoria literalmente como toda tu salida, incluso si está vacía; no agregues despedidas, preguntas ni otra herramienta. Ante error sin resultado, no afirmes el pase ni reintentes."
)

DESCRIPCION_MOTIVO = (
    "Motivo de intervención solicitado por el cliente. Elegí exactamente uno: avance_compra, pago, turno, persona, posventa o revision_especial. No incluyas destinatarios, texto ni otros datos."
)
