// Funciones puras: se insertan en expresiones/Code de n8n y se prueban sin red.
export function normalizeEvent(input) {
  const b = input.body || {};
  const conv = b.conversation || {};
  const current = (conv.messages || []).find(m => String(m.id) === String(b.id)) || {};
  const sender = b.sender || current.sender || conv.meta?.sender || {};
  const phone = sender.phone_number || conv.meta?.sender?.phone_number || current.sender?.phone_number || '';
  const account = b.account?.id ?? sender.account?.id ?? conv.account_id;
  const conversation = conv.id ?? current.conversation_id;
  const attachments = Array.isArray(b.attachments) ? b.attachments : (current.attachments || []);
  const audio = attachments.find(a => a.file_type === 'audio');
  const labels = conv.labels || [];
  const human = labels.some(l => (typeof l === 'string' ? l : l.title || l.name) === 'humano');
  const incoming = b.message_type === 'incoming' || b.message_type === 0;
  const contact = !sender.type || sender.type.toLowerCase() === 'contact';
  const text = typeof b.content === 'string' ? b.content : '';
  // Solo la bandeja de WhatsApp de F7 (id 1): la cuenta también tiene la bandeja «Test Bot API».
  const inbox = b.inbox?.id ?? conv.inbox_id;
  const accept = b.event === 'message_created' && incoming && !b.private && contact && !human
    && Number(account) === 1 && (inbox == null || Number(inbox) === 1) && Boolean(phone && conversation && b.id)
    && Boolean(text.trim() || audio?.data_url);
  const normalizedSender = { ...sender, phone_number: phone, account: { ...sender.account, id: account } };
  const message = { ...current, id: b.id, conversation_id: conversation, sender: normalizedSender, attachments };
  return { body: { ...b, content: text, message_type: incoming ? 'incoming' : b.message_type,
    sender: normalizedSender, attachments,
    conversation: { ...conv, id: conversation, labels, meta: { ...conv.meta, sender: normalizedSender }, messages: [message] } },
    accept, telefono: String(phone), account_id: Number(account), conversation_id: String(conversation || ''),
    message_id: String(b.id || ''), audio_url: audio?.data_url || '', is_audio: Boolean(audio),
    buffer_key: `f7:unificado:v1:${account}:${conversation}:buffer`,
    lock_key: `f7:unificado:v1:${account}:${conversation}:lock` };
}

export function splitResponse(value) {
  // Mantener líneas hasta quitar las marcas de listas; aplanarlas antes deja
  // numeraciones como mensajes sueltos al dividir por puntos.
  let text = String(value ?? '').replace(/\\r\\n|\\n|\\r/g, '\n').replace(/\r\n?/g, '\n');
  // Una línea en blanco separa mensajes (p. ej. un link al final de un párrafo);
  // un salto simple no. Se marca antes de limpiar Markdown, que puede dejar líneas vacías.
  text = text.replace(/\n(?:[\t ]*\n)+/g, '\n\n');
  const tokens = [];
  const protect = s => { const key = `\uE000${tokens.length}\uE001`; tokens.push(s); return key; };

  // Leer el cierre balanceado del enlace conserva paréntesis dentro del destino.
  const links = /!?\[([^\]\n]*)\]\(/g;
  let match, cursor = 0, plain = '';
  while ((match = links.exec(text))) {
    let end = links.lastIndex, depth = 1;
    for (; end < text.length && depth; end++) {
      if (text[end] === '(') depth++;
      if (text[end] === ')') depth--;
    }
    if (depth) continue;
    const target = text.slice(links.lastIndex, end - 1).trim();
    const destination = target.match(/^(?:<((?:https?:\/\/|www\.|mailto:)[^<>\s]+)>|((?:https?:\/\/|www\.|mailto:)[^\s]+?))(?:\s+(?:"[^"]*"|'[^']*'))?$/i);
    if (!destination) continue;
    plain += text.slice(cursor, match.index) + match[1] + ' ' + protect(destination[1] || destination[2]);
    cursor = end; links.lastIndex = end;
  }
  text = plain + text.slice(cursor);

  // Proteger antes de limpiar Markdown: _, *, ?, #, &, = y puntos pueden ser
  // parte del enlace. Solo se separan sus delimitadores externos de énfasis.
  text = text.replace(/(?:https?:\/\/|www\.)[^\s<>"`]+|[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, (s, offset, whole) => {
    let leading = '';
    const emailMarker = s.includes('@') && s.match(/^_{1,3}/)?.[0];
    if (emailMarker && whole.slice(offset + s.length).startsWith(emailMarker)) {
      leading = emailMarker; s = s.slice(emailMarker.length);
    }
    let trailing = s.match(/[.!?,;:]+$/)?.[0] || '';
    if (trailing) s = s.slice(0, -trailing.length);
    const marker = whole.slice(0, offset).match(/(\*{1,3}|_{1,3})$/)?.[0];
    if (marker && s.endsWith(marker)) { s = s.slice(0, -marker.length); trailing = marker + trailing; }
    return leading + protect(s) + trailing;
  }).replace(/\d+(?:\.\d+)+/g, protect).replace(/\b(?:av|avda)\.(?=\s)/gi, protect);

  text = text
    .replace(/^[\t ]*(?:`{3,}|~{3,})(?:[a-z\d_+-]+)?[\t ]*(?:\n|$)/gmi, '\n')
    .replace(/^[\t ]*(?:={2,}|-{2,}|\*{3,}|_{3,})[\t ]*$/gm, '')
    .replace(/^[\t ]*#{1,6}[\t ]+(.+?)(?:[\t ]+#+)?[\t ]*$/gm, '$1')
    .replace(/^[\t ]*(?:[-+*•◦▪‣]|\d{1,9}[.)])[\t ]+(?:\[[ xX]\][\t ]+)?/gm, '')
    .replace(/<([\uE000]\d+[\uE001])>/g, '$1')
    .replace(/\*|`/g, '')
    .replace(/(^|[^\p{L}\p{N}_])_{1,3}([^\n]+?)_{1,3}(?=$|[^\p{L}\p{N}_])/gu, '$1$2')
    .replace(/~~([^\n]+?)~~/g, '$1')
    // Conservar la limpieza previa y el contrato JSON de los nodos siguientes.
    .replace(/\\"/g, '').replace(/"/g, '').replace(/¿/g, '').replace(//g, '.').replace(/\s+/g, ' ').trim();
  if (!text) return [];
  return text.split('.').map(s => s.replace(/\uE000(\d+)\uE001/g, (_, i) => tokens[Number(i)]).trim()).filter(Boolean);
}

export function bufferSnapshot(raw, now) {
  const rows = Array.isArray(raw) ? raw.map(r => typeof r === 'string' ? JSON.parse(r) : r) : [];
  if (!rows.length) return { count: 0, ready: false, wait_seconds: 0 };
  const last = Math.max(...rows.map(r => Number(r.received_at)));
  if (!Number.isFinite(last)) throw new Error('Buffer con timestamp inválido');
  const remaining = 15000 - (Number(now) - last);
  return { count: rows.length, ready: remaining <= 0, wait_seconds: Math.max(0, Math.ceil(remaining / 1000)) };
}
