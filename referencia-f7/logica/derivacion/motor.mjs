// Funciones puras compartidas por el workflow y sus pruebas. Sin red ni secretos.
export const DESTINO_ID = 3; // Mateo confirmó: Candela usa la cuenta Melanie (05/11/2026).
export const MOTIVOS = ['avance_compra','pago','turno','persona','posventa','revision_especial'];
export const ACK = 'La conversación quedó asignada a Candela para continuar con tu consulta.';
const ERROR_PASE = 'No pude completar el pase a Candela.';
function plano(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
function positivo(v) { return Number.isSafeInteger(v) && v > 0; }
function httpStatus(r) {
 const n=Number(r?.statusCode??r?.error?.statusCode??r?.error?.httpCode??r?.error?.response?.status);
 return Number.isInteger(n)&&n>=100&&n<=599?n:null;
}
export function resultado(estado,verificacion=null,motivo=null,envio={estado:'no_corresponde'}) {
 const pausado=verificacion?.verificada===true?verificacion.bot_pausado:null;
 const asignado=verificacion?.verificada===true&&pausado===true&&verificacion.abierta===true&&verificacion.assignee_id===DESTINO_ID;
 return {estado,bot_pausado:pausado,asignacion_confirmada:asignado,
  destino:asignado?{id:DESTINO_ID,nombre:'Candela',cuenta_chatwoot:'Melanie'}:null,
  envio,motivo,requiere_revision:['fallido','parcial','desconocido','pendiente_asignacion'].includes(estado),continuacion_obligatoria:''};
}
export function validarEntrada(raw) {
 if(!plano(raw)||!MOTIVOS.includes(raw.motivo)||!['simular','enviar'].includes(raw.modo))return {ok:false};
 if(Object.keys(raw).some(k=>!['motivo','modo','account_id','conversation_id','solicitud_id'].includes(k)))return {ok:false};
 if(raw.modo==='simular')return {ok:true,motivo:raw.motivo,contexto:{modo:'simular'}};
 if(raw.account_id!==1||!positivo(raw.conversation_id)||typeof raw.solicitud_id!=='string')return {ok:false};
 if(!/^cw:1:[1-9]\d*:[1-9]\d{0,31}:derivacion-v1$/.test(raw.solicitud_id)||!raw.solicitud_id.startsWith(`cw:1:${raw.conversation_id}:`))return {ok:false};
 return {ok:true,motivo:raw.motivo,contexto:{modo:'enviar',account_id:1,conversation_id:raw.conversation_id,solicitud_id:raw.solicitud_id}};
}
export function leerConversacion(response,contexto) {
 const invalid=motivo=>({verificada:false,motivo});
 if(contexto?.account_id!==1||!positivo(contexto?.conversation_id))return invalid('contexto_invalido');
 const status=httpStatus(response),b=response?.body;
 if(!status||status<200||status>=300||response?.error)return invalid('conversacion_no_verificable');
 if(!plano(b)||b.id!==contexto.conversation_id||(b.account_id!==undefined&&b.account_id!==1))return invalid('identidad_no_coincide');
 if(!Array.isArray(b.labels)||b.labels.some(l=>typeof l!=='string'))return invalid('labels_no_verificables');
 const assignee=b.meta?.assignee?.id??b.assignee_id??null;
 if(assignee!==null&&!positivo(assignee))return invalid('asignacion_no_verificable');
 if(!['open','pending','resolved','snoozed'].includes(b.status))return invalid('estado_no_verificable');
 return {verificada:true,bot_pausado:b.labels.some(l=>l.trim().toLowerCase()==='humano'),labels:[...b.labels],
  abierta:b.status==='open',status:b.status,can_reply:b.can_reply===true,assignee_id:assignee,motivo:null};
}
export function evaluarInicio(response,contexto) {
 const v=leerConversacion(response,contexto);
 if(!v.verificada)return {continuar:false,resultado:{...resultado('fallido',null,v.motivo),continuacion_obligatoria:ERROR_PASE}};
 if(v.bot_pausado)return {continuar:false,resultado:resultado('control_humano',v,'conversacion_ya_tomada')};
 return {continuar:true,verificacion:v,labels:[...new Set([...v.labels,'humano'])]};
}
export function evaluarEtapa(response,contexto,etapa,labelsIniciales=[]) {
 const v=leerConversacion(response,contexto);
 if(!v.verificada)return {continuar:false,resultado:resultado('desconocido',null,v.motivo)};
 if(!v.bot_pausado)return {continuar:false,resultado:resultado('fallido',v,'pausa_no_confirmada')};
 if(!labelsIniciales.every(l=>v.labels.includes(l)))return {continuar:false,resultado:resultado('parcial',v,'etiquetas_originales_no_confirmadas')};
 if(etapa!=='pausa'&&!v.abierta)return {continuar:false,resultado:resultado('parcial',v,'apertura_no_confirmada')};
 if(etapa==='asignacion'&&v.assignee_id!==DESTINO_ID)return {continuar:false,resultado:resultado('pendiente_asignacion',v,'destino_no_confirmado')};
 return {continuar:true,verificacion:v};
}
export function decidirConfirmacion(response,contexto,labelsIniciales,inicioMs,ahoraMs) {
 const etapa=evaluarEtapa(response,contexto,'asignacion',labelsIniciales);
 if(!etapa.continuar)return {enviar_ack:false,resultado:etapa.resultado};
 const v=etapa.verificacion;
 const tiempo=Number.isFinite(inicioMs)&&Number.isFinite(ahoraMs)&&ahoraMs>=inicioMs&&ahoraMs-inicioMs<=140000;
 const enviar_ack=v.can_reply&&tiempo;
 return {enviar_ack,verificacion:v,resultado:resultado('derivado',v,enviar_ack?null:!v.can_reply?'ventana_no_habilitada':'tiempo_agotado',
  {estado:'no_corresponde',motivo:enviar_ack?null:!v.can_reply?'ventana_no_habilitada':'tiempo_agotado'})};
}
export function evaluarAck(response,contexto) {
 const uncertain=motivo=>({estado:'desconocido',motivo,chatwoot_message_id:null});
 if(contexto?.account_id!==1||!positivo(contexto?.conversation_id))return uncertain('contexto_invalido');
 const status=httpStatus(response);
 if(status>=400&&status<500&&status!==408)return {estado:'fallido',motivo:`http_${status}`,chatwoot_message_id:null};
 if(!status||status<200||status>=300||response?.error)return uncertain('confirmacion_no_verificable');
 const b=response?.body;
 if(!plano(b)||!positivo(b.id)||b.conversation_id!==contexto.conversation_id||(b.account_id!==undefined&&b.account_id!==1)||![1,'outgoing'].includes(b.message_type)||b.private!==false||b.content!==ACK)return uncertain('respuesta_no_coincide');
 if(b.status==='failed'||b.status===3||b.content_attributes?.external_error)return {estado:'fallido',motivo:'canal_rechazo_envio',chatwoot_message_id:b.id};
 return {estado:'aceptado',motivo:null,chatwoot_message_id:b.id};
}
export function resolverRepeticion(row) {
 if(row?.compatible!==true)return {...resultado('entrada_invalida',null,'solicitud_incompatible'),repetido:true};
 if(row.estado==='finalizado'&&plano(row.resultado))return {...row.resultado,repetido:true,verificacion:'ejecucion_original',
  envio:row.resultado.envio?.estado==='aceptado'?{...row.resultado.envio,estado:'omitido'}:row.resultado.envio,continuacion_obligatoria:''};
 return {...resultado('desconocido',null,'solicitud_en_curso_o_incierta',{estado:row.estado==='enviando'?'desconocido':'no_corresponde'}),repetido:true};
}
