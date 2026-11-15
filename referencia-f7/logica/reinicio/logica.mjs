// Funciones puras: cada export puede embeberse mediante toString sin imports.
export const ACK_REINICIO='Ya borre mi memoria, a partir de ahora comienza una conversación nueva';

export function esComandoBorrar(texto){
  if(typeof texto!=='string')return false;
  const t=texto.normalize('NFKC').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase()
    .replace(/^[\s\p{P}]+|[\s\p{P}]+$/gu,'').replace(/\s+/gu,' ');
  return /^(?:borrar|borra|borrame)(?: (?:(?:mi|la) memoria|el historial|todo))?$/.test(t);
}

export function prepararReactivacion(response,contexto){
  const invalid=motivo=>({ok:false,labels:null,requiere_reactivar:false,motivo});
  if(contexto?.account_id!==1||!Number.isSafeInteger(contexto?.conversation_id)||contexto.conversation_id<=0)return invalid('contexto_invalido');
  const raw=response?.statusCode;
  const status=typeof raw==='number'?raw:typeof raw==='string'&&/^\d{3}$/.test(raw)?Number(raw):null;
  if(!Number.isInteger(status)||status<200||status>=300||response?.error)return invalid('conversacion_no_verificable');
  const b=response?.body;
  if(!b||typeof b!=='object'||Array.isArray(b)||b.id!==contexto.conversation_id||(b.account_id!==undefined&&b.account_id!==1))return invalid('identidad_no_coincide');
  if(!Array.isArray(b.labels)||b.labels.some(l=>typeof l!=='string'))return invalid('labels_no_verificables');
  if(b.can_reply!==true)return invalid('ventana_no_habilitada');
  const labels=b.labels.filter(l=>l.normalize('NFKC').trim().toLowerCase()!=='humano');
  return {ok:true,labels,requiere_reactivar:labels.length!==b.labels.length,motivo:null};
}

export function verificarReactivacion(response,contexto){
  const invalid=motivo=>({ok:false,labels:null,requiere_reactivar:false,motivo});
  if(contexto?.account_id!==1||!Number.isSafeInteger(contexto?.conversation_id)||contexto.conversation_id<=0)return invalid('contexto_invalido');
  const raw=response?.statusCode;
  const status=typeof raw==='number'?raw:typeof raw==='string'&&/^\d{3}$/.test(raw)?Number(raw):null;
  if(!Number.isInteger(status)||status<200||status>=300||response?.error)return invalid('conversacion_no_verificable');
  const b=response?.body;
  if(!b||typeof b!=='object'||Array.isArray(b)||b.id!==contexto.conversation_id||(b.account_id!==undefined&&b.account_id!==1))return invalid('identidad_no_coincide');
  if(!Array.isArray(b.labels)||b.labels.some(l=>typeof l!=='string'))return invalid('labels_no_verificables');
  if(b.can_reply!==true)return invalid('ventana_no_habilitada');
  const humano=b.labels.some(l=>l.normalize('NFKC').trim().toLowerCase()==='humano');
  if(humano)return {ok:false,labels:[...b.labels],requiere_reactivar:true,motivo:'humano_persistente'};
  if(contexto.labels_esperadas!==undefined){
    if(!Array.isArray(contexto.labels_esperadas)||contexto.labels_esperadas.some(l=>typeof l!=='string'))return invalid('labels_esperadas_invalidas');
    const restantes=new Map();
    for(const label of b.labels)restantes.set(label,(restantes.get(label)??0)+1);
    for(const label of contexto.labels_esperadas){
      const cantidad=restantes.get(label)??0;
      if(cantidad===0)return {ok:false,labels:[...b.labels],requiere_reactivar:false,motivo:'labels_no_preservadas'};
      restantes.set(label,cantidad-1);
    }
  }
  return {ok:true,labels:[...b.labels],requiere_reactivar:false,motivo:null};
}

export function evaluarAckReinicio(response,contexto){
  // Literal local necesario para conservar el contrato al embeber solo esta función.
  const ack='Ya borre mi memoria, a partir de ahora comienza una conversación nueva';
  const uncertain=motivo=>({estado:'desconocido',motivo,chatwoot_message_id:null});
  if(contexto?.account_id!==1||!Number.isSafeInteger(contexto?.conversation_id)||contexto.conversation_id<=0)return uncertain('contexto_invalido');
  const raw=response?.statusCode??response?.error?.statusCode??response?.error?.httpCode??response?.error?.response?.status;
  const status=typeof raw==='number'?raw:typeof raw==='string'&&/^\d{3}$/.test(raw)?Number(raw):null;
  if(Number.isInteger(status)&&status>=400&&status<500&&status!==408)return {estado:'fallido',motivo:'http_'+status,chatwoot_message_id:null};
  if(!Number.isInteger(status)||status<200||status>=300||response?.error)return uncertain('confirmacion_no_verificable');
  const b=response?.body;
  if(!b||typeof b!=='object'||Array.isArray(b)||!Number.isSafeInteger(b.id)||b.id<=0||b.conversation_id!==contexto.conversation_id||(b.account_id!==undefined&&b.account_id!==1)||![1,'outgoing'].includes(b.message_type)||b.private!==false||b.content!==ack)return uncertain('respuesta_no_coincide');
  if(b.status===3||b.status==='3'||(typeof b.status==='string'&&b.status.trim().toLowerCase()==='failed')||b.content_attributes?.external_error)return {estado:'fallido',motivo:'canal_rechazo_envio',chatwoot_message_id:null};
  return {estado:'aceptado',motivo:null,chatwoot_message_id:b.id};
}

// Embeber junto a esComandoBorrar; valida evidencia de Chatwoot antes de mutar memoria.
export function verificarComandoPersistido(response,evento,ahoraMs){
  const invalid=motivo=>({ok:false,motivo});
  const id=v=>typeof v==='string'&&/^[1-9]\d{0,31}$/.test(v)?v:Number.isSafeInteger(v)&&v>0?String(v):null;
  const conv=id(evento?.conversation_id),message=id(evento?.message_id);
  if(evento?.account_id!==1||!conv||!message||typeof evento?.telefono!=='string'||!evento.telefono.trim()||evento?.is_audio!==false||!esComandoBorrar(evento?.body?.content))return invalid('evento_invalido');
  if(!Number.isSafeInteger(ahoraMs)||ahoraMs<=0)return invalid('reloj_no_verificable');
  const raw=response?.statusCode;
  const status=typeof raw==='number'?raw:typeof raw==='string'&&/^\d{3}$/.test(raw)?Number(raw):null;
  if(!Number.isInteger(status)||status<200||status>=300||response?.error)return invalid('mensajes_no_verificables');
  const body=response?.body;
  if(!body||typeof body!=='object'||Array.isArray(body)||!Array.isArray(body.payload)||(body.account_id!==undefined&&body.account_id!==1))return invalid('mensajes_no_verificables');
  const coincidencias=body.payload.filter(m=>m&&typeof m==='object'&&!Array.isArray(m)&&id(m.id)===message);
  if(coincidencias.length!==1)return invalid('mensaje_no_unico');
  const m=coincidencias[0];
  if(id(m.conversation_id)!==conv||(m.account_id!==undefined&&m.account_id!==1)||![0,'incoming'].includes(m.message_type)||m.private!==false)return invalid('mensaje_no_coincide');
  if(m.sender?.type!=='contact'||m.sender.phone_number!==evento.telefono)return invalid('contacto_no_coincide');
  if(m.content_type==='audio'||(Array.isArray(m.attachments)&&m.attachments.some(a=>a?.file_type==='audio')))return invalid('mensaje_persistido_audio');
  const normalizar=s=>s.normalize('NFKC').trim().replace(/\s+/gu,' ');
  if(!esComandoBorrar(m.content)||normalizar(m.content)!==normalizar(evento.body.content))return invalid('comando_no_coincide');
  if(typeof m.created_at!=='number'||!Number.isFinite(m.created_at)||m.created_at<=0)return invalid('fecha_no_verificable');
  const edadMs=ahoraMs-m.created_at*1000;
  if(!Number.isFinite(edadMs)||edadMs>600000||edadMs< -60000)return invalid('comando_fuera_de_ventana');
  return {ok:true,motivo:null};
}
