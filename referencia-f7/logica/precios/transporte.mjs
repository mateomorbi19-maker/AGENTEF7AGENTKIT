// Funciones puras incorporadas en n8n; ninguna accede a secretos ni a la red.
export const SHEET_ID = '1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU';
export const HOJAS = {
 'Fundas a medida':877828453,'TIPO TAPIZADO':613213257,'TAPICERIA':972378170,
 'Termoformadas':0,'Funda Baúl - Antiderrame':941782890,
 'Cobertores de caja ':2002506112,'ESPUMAS':1953604758,'Otros':59879218,
};
export function validarContexto(raw) {
 if(raw?.modo==='simular')return {ok:true,contexto:{modo:'simular'}};
 if(raw?.modo!=='enviar'||raw.account_id!==1||!Number.isSafeInteger(raw.conversation_id)||raw.conversation_id<1)return {ok:false};
 const prefix=`cw:1:${raw.conversation_id}:`;
 if(typeof raw.solicitud_id!=='string'||!raw.solicitud_id.startsWith(prefix)||!/^cw:1:[1-9]\d*:[1-9]\d{0,31}:precios-v1$/.test(raw.solicitud_id))return {ok:false};
 return {ok:true,contexto:{modo:'enviar',account_id:1,conversation_id:raw.conversation_id,solicitud_id:raw.solicitud_id}};
}
export function prepararRangos(titulos,metadata) {
 if(metadata?.spreadsheetId!==SHEET_ID||!Array.isArray(metadata.sheets))throw new Error('metadata_invalida');
 if(!Array.isArray(titulos)||!titulos.length||titulos.length>8)throw new Error('hojas_invalidas');
 return [...new Set(titulos)].map(title=>{
   if(!Object.hasOwn(HOJAS,title))throw new Error('hoja_no_permitida');
   const p=metadata.sheets.find(s=>s.properties?.sheetId===HOJAS[title])?.properties;
   if(!p||p.title!==title)throw new Error('estructura_de_hojas_cambio');
   const {rowCount:r,columnCount:c}=p.gridProperties??{};
   if(!Number.isSafeInteger(r)||r<1||!Number.isSafeInteger(c)||c<1||c>60||r*c>100000)throw new Error('dimensiones_fuera_de_limite');
   let col='',n=c;while(n){n--;col=String.fromCharCode(65+n%26)+col;n=Math.floor(n/26);}
   return {title,sheetId:p.sheetId,range:`'${title.replaceAll("'","''")}'!A1:${col}${r}`};
 });
}
export function leerValores(body,rangos) {
 if(body?.spreadsheetId!==SHEET_ID||!Array.isArray(body.valueRanges)||body.valueRanges.length!==rangos.length)throw new Error('lectura_incompleta');
 return rangos.map((r,i)=>{
   const v=body.valueRanges[i];
   // Google puede omitir comillas cuando el título no las necesita.
   const title=String(v?.range??'').split('!').slice(0,-1).join('!').replace(/^'|'$/g,'').replaceAll("''","'");
   if(title!==r.title||!Array.isArray(v.values)||v.values.some(row=>!Array.isArray(row)))throw new Error('rango_o_valores_invalidos');
   return {...r,values:v.values};
 });
}
export function evaluarEnvioTexto(response,contexto,contenido) {
 const incierto=motivo=>({estado:'desconocido',motivo,chatwoot_message_id:null});
 const status=Number(response?.statusCode??response?.error?.statusCode??response?.error?.httpCode);
 if(status>=400&&status<500&&status!==408)return {estado:'fallido',motivo:`http_${status}`,chatwoot_message_id:null};
 if(!Number.isInteger(status)||status<200||status>=300||response?.error)return incierto('envio_no_confirmado');
 const b=response.body;
 if(contexto?.account_id!==1||!Number.isSafeInteger(b?.id)||b.id<=0||b.conversation_id!==contexto.conversation_id||![1,'outgoing'].includes(b.message_type)||b.private!==false||b.content!==contenido)return incierto('respuesta_no_coincide');
 if(b.account_id!==undefined&&b.account_id!==1)return incierto('cuenta_no_coincide');
 if(b.status==='failed'||b.status===3||b.content_attributes?.external_error)return {estado:'fallido',motivo:'canal_rechazo_envio',chatwoot_message_id:b.id};
 return {estado:'aceptado',motivo:null,chatwoot_message_id:b.id};
}
