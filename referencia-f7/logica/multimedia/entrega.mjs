// Funciones puras: no acceden a credenciales, red, base de datos ni estado de n8n.
// El generador del workflow incorpora este módulo en nodos Code.
function objetoPlano(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function enteroPositivo(value) {
  return Number.isSafeInteger(value) && value > 0;
}

function contextoValido(contexto) {
  return objetoPlano(contexto) && contexto.account_id === 1 && enteroPositivo(contexto.conversation_id);
}

function codigoHttp(response) {
  if (!objetoPlano(response)) return null;
  const value = response.statusCode ?? response.error?.statusCode ?? response.error?.httpCode ?? response.error?.response?.status;
  const code = typeof value === 'string' && /^\d{3}$/.test(value) ? Number(value) : value;
  return Number.isInteger(code) && code >= 100 && code <= 599 ? code : null;
}

/** Requiere la respuesta HTTP completa del GET de Chatwoot. La falta de labels bloquea. */
export function evaluarConversacion(response, contexto) {
  const bloquear = (motivo) => ({ permitido: false, estado: 'fallido', motivo });
  if (!contextoValido(contexto)) return bloquear('contexto_invalido');
  const status = codigoHttp(response);
  if (!status || status < 200 || status >= 300 || response.error) return bloquear('no_se_pudo_verificar_conversacion');
  const body = response.body;
  if (!objetoPlano(body) || body.id !== contexto.conversation_id) return bloquear('conversacion_no_coincide');
  if (body.account_id !== undefined && body.account_id !== contexto.account_id) return bloquear('cuenta_no_coincide');
  if (contexto.inbox_id !== undefined && (!enteroPositivo(contexto.inbox_id) || body.inbox_id !== contexto.inbox_id)) return bloquear('bandeja_no_coincide');
  if (!Array.isArray(body.labels) || body.labels.some((label) => typeof label !== 'string')) return bloquear('control_humano_no_verificable');
  if (body.labels.some((label) => label.trim().toLowerCase() === 'humano')) {
    return { permitido: false, estado: 'control_humano', motivo: 'conversacion_con_humano' };
  }
  return { permitido: true, estado: 'habilitado', motivo: null };
}

/**
 * Evalúa el POST sin repetirlo. Un ID confirma la creación, no entrega/lectura.
 * Errores de transporte, 408 y 5xx quedan inciertos: nunca justifican reenvío ciego.
 * El resultado contiene códigos propios; no propaga texto, URLs o headers del proveedor.
 */
export function evaluarRespuestaEnvio(response, contexto) {
  const desconocido = (motivo) => ({ estado: 'desconocido', chatwoot_message_id: null, motivo });
  if (!contextoValido(contexto)) return desconocido('contexto_invalido');
  const status = codigoHttp(response);
  if (status && status >= 400 && status < 500 && status !== 408) {
    return { estado: 'fallido', chatwoot_message_id: null, motivo: `http_${status}` };
  }
  if (!status || status < 200 || status >= 300 || response.error) return desconocido('envio_no_confirmado');
  const body = response.body;
  if (!objetoPlano(body) || !enteroPositivo(body.id) || body.conversation_id !== contexto.conversation_id) return desconocido('respuesta_sin_identidad_confirmada');
  if (body.account_id !== undefined && body.account_id !== contexto.account_id) return desconocido('cuenta_no_coincide');
  if (![1, 'outgoing'].includes(body.message_type) || body.private !== false) return desconocido('respuesta_no_es_envio_publico');
  if (body.status === 'failed' || body.status === 3 || body.content_attributes?.external_error) {
    return { estado: 'fallido', chatwoot_message_id: body.id, motivo: 'canal_rechazo_envio' };
  }
  if (!Array.isArray(body.attachments) || body.attachments.length !== 1 || body.attachments.some((a) => !objetoPlano(a) || !enteroPositivo(a.id) || !['image', 'video'].includes(a.file_type))) {
    return desconocido('adjunto_no_confirmado');
  }
  if (contexto.formato !== undefined) {
    const expected = { foto: 'image', video: 'video' }[contexto.formato];
    if (!expected || body.attachments.some((a) => a.file_type !== expected)) return desconocido('tipo_adjunto_no_coincide');
  }
  return { estado: 'aceptado', chatwoot_message_id: body.id, motivo: null };
}
