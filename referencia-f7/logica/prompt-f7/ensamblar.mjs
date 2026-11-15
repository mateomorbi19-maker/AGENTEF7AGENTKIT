import fs from 'node:fs';

export const FASE_A_BLOQUES={
  inicio:['base','recorrido','conocimiento','inicio','errores','decision'],
  multimedia:['base','recorrido','conocimiento','multimedia','errores','decision'],
  cotizacion:['base','recorrido','conocimiento','cotizacion','errores','decision'],
  candela:['base','recorrido','conocimiento','candela','errores','decision'],
  objeciones:['base','recorrido','conocimiento','objeciones','errores','decision'],
  seguimiento:['base','recorrido','conocimiento','seguimiento','errores','decision'],
};

export function clasificarFase(texto){
  const t=String(texto??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  if(/\b(alias|comprobante|sene|pagado|pague|reintegro|reclamo|candela|humano|persona|alguien|operador|turno)\b|quiero (?:comprar|encargar|reservar)|(?:pagar|abonar) (?:ahora|ya)\b|quien.*(?:ver|revisar|confirmar|atender)|no llego|pedido.*(?:estado|seguimiento)/.test(t))return 'candela';
  if(/\b(efectivo|transferencia|tarjeta|credito|debito|cuotas?)\b/.test(t)&&/\b(cuanto|precio\w*|valor|sale|salen|cuesta|cuestan|menos|descuento)\b/.test(t))return 'cotizacion';
  if(/\bdescuento\b|quiero pagar/.test(t))return 'candela';
  if(/\b(caro|cara|costoso|desconfio)\b|sin senar|sin sena|antes de senar|ver.*persona/.test(t))return 'objeciones';
  if(/\b(foto\w*|video\w*|catalogo|disenos?|colores?|comparacion|diferencia\w*|mostra\w*|muestr\w*)\b/.test(t))return 'multimedia';
  if(/\b(precio\w*|valor|cuanto|cuotas?|transferencia|efectivo|tarjeta|credito|debito|pago\w*|total)\b/.test(t))return 'cotizacion';
  if(/^(hola|buenas|buen(?:os)? dias?|buenas tardes|buenas noches|quiero (?:info|informacion))[!?.\s]*$/.test(t.trim()))return 'inicio';
  return 'seguimiento';
}

export function leerBloques(){
  const documento=fs.readFileSync(new URL('../../prompts/SYSTEM_PROMPT_F7_V1.md',import.meta.url),'utf8');
  const partes=documento.split(/<!-- BLOQUE ([a-z_]+) -->/);
  const bloques={};
  for(let i=1;i<partes.length;i+=2){
    if(Object.hasOwn(bloques,partes[i]))throw new Error(`Bloque duplicado: ${partes[i]}`);
    bloques[partes[i]]=partes[i+1].trim();
  }
  for(const key of new Set(Object.values(FASE_A_BLOQUES).flat())){
    if(!bloques[key])throw new Error(`Falta bloque de prompt: ${key}`);
  }
  return bloques;
}

export function leerMetadatosCatalogo(){
  const catalogo=JSON.parse(fs.readFileSync(new URL('../multimedia/catalogo.json',import.meta.url),'utf8'));
  return Object.fromEntries(catalogo.assets.filter(a=>a.habilitado).map(a=>[a.id,{
    version:a.version,titulo:a.titulo,productos:a.productos_visibles,formato:a.formato,
    contenidos:[...new Set(catalogo.rutas.filter(r=>r.opciones.some(o=>o.asset_ids.includes(a.id))).map(r=>r.contenido))],
  }]));
}

export function resumirMultimedia(registros,metadatos){
  if(!Array.isArray(registros))return [];
  const usados=new Set();
  return registros.slice(0,60).flatMap(r=>{
    if(!r||typeof r.asset_id!=='string'||!Object.hasOwn(metadatos,r.asset_id))return [];
    const meta=metadatos[r.asset_id];
    if(r.version!==meta.version||usados.has(r.asset_id))return [];
    const aceptado=r.aceptado===true,incierto=r.hay_envio_incierto===true;
    if(!aceptado&&!incierto)return [];
    usados.add(r.asset_id);
    return [{pieza:r.asset_id,titulo:meta.titulo,productos:meta.productos,contenidos:meta.contenidos,formato:meta.formato,
      aceptado_por_chatwoot:aceptado,hay_envio_incierto:incierto}];
  });
}

export function ensamblarPrompt(entrada,bloques,fechaActual,metadatos={}){
  const fase=clasificarFase(entrada.texto);
  const usados=FASE_A_BLOQUES[fase];
  const fecha=typeof fechaActual==='string'&&Number.isFinite(Date.parse(fechaActual))?fechaActual:'fecha no disponible';
  const contexto=[
    'CONTEXTO OPERATIVO SUMINISTRADO POR EL WORKFLOW',
    `Fecha actual en America/Argentina/Buenos_Aires: ${fecha}`,
    'CAPACIDADES OPERATIVAS',
    '- herramienta_disponible: enviar_multimedia',
    '- herramienta_precio_disponible: buscar_precio',
    '- derivacion_efectiva_disponible: true (derivar_humano; solo el resultado confirma pausa, asignación y aviso)',
    '- medidas_por_vehiculo_verificadas_disponibles: false',
    `Modalidad humana: ${['caba','envio'].includes(entrada.modalidad_confirmada)?entrada.modalidad_confirmada:'sin_confirmar'}.`,
    '- fuente_oficial_de_precios: https://docs.google.com/spreadsheets/d/1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU/edit (solo buscar_precio ejecuta la consulta)',
    'MULTIMEDIA REGISTRADA (datos internos, no copiar):',
    JSON.stringify(resumirMultimedia(entrada.multimedia_registrada,metadatos)),
    'Aceptado no significa visto. No repitas sin pedido; no reintentes inciertos. Registro vacío no borra el historial.',
    entrada.saludo_inicial_enviado===true?'- El flujo ya envió su saludo inicial en este turno. No agregues otro saludo.':'- No reinicies el saludo: continuá según el historial y el mensaje actual.',
    `Fase orientativa: ${fase}; manda el pedido actual y los datos del historial.`,
  ].join('\n');
  const accionFinal=fase==='candela'
    ?'Gestión de compra/pago o persona: derivar_humano AHORA; consulta de precio por medio: buscar_precio.'
    :fase==='cotizacion'
      ?'Precio pendiente + modelo/modalidad conocidos: buscar_precio AHORA, omitiendo anio si falta.'
      :'Conservá lo respondido y no agregues requisitos; la última pregunta del bot no obliga al cliente.';
  return {prompt_version:'f7-brief-2026-11-05.v9.4-medios-pago-total',fase_detectada:fase,bloques_usados:usados,
    prompt_ensamblado:usados.filter(k=>k!=='decision').map(k=>bloques[k]).join('\n\n')+'\n\n'+contexto+'\n\n'+bloques.decision+'\nACCIÓN FINAL: '+accionFinal};
}

export function generarCodigoEnsamblador(){
  const bloques=leerBloques();
  return `const BLOQUES=${JSON.stringify(bloques)};\nconst FASE_A_BLOQUES=${JSON.stringify(FASE_A_BLOQUES)};\nconst METADATOS_MULTIMEDIA=${JSON.stringify(leerMetadatosCatalogo())};\n${clasificarFase.toString()}\n${resumirMultimedia.toString()}\n${ensamblarPrompt.toString()}\nconst entrada=$input.first().json;\nconst resultado=ensamblarPrompt(entrada,BLOQUES,$now.setZone('America/Argentina/Buenos_Aires').toISO(),METADATOS_MULTIMEDIA);\nreturn [{json:{...entrada,...resultado}}];`;
}
