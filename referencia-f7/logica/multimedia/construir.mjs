import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as sql from './sql.mjs';

const base = path.dirname(fileURLToPath(import.meta.url));
const source = name => fs.readFileSync(path.join(base,name),'utf8').replace(/^export /gm,'');

/** Genera únicamente datos de workflow; no realiza llamadas ni cambia la instancia. */
export function construirWorkflow() {
  const seleccion=source('seleccion.mjs');
  const entrega=source('entrega.mjs');
  const catalogo=JSON.parse(fs.readFileSync(path.join(base,'catalogo.json'),'utf8'));
  const nodes=[],connections={};
  const creds={pg:{postgres:{id:'xUzf8N4tUBZ8OH2Z',name:'Postgres account'}},cw:{httpHeaderAuth:{id:'EppfgYwuOOf4NkuN',name:'Chatwoot productivo (F7)'}},drive:{googleDriveOAuth2Api:{id:'jZ3KFY76r3SH4kqS',name:'Google Drive account'}}};
  const add=(name,type,version,parameters,x,y,extra={})=>{
    const id='f7-mm-'+String(nodes.length+1).padStart(3,'0');
    const n={id,name,type:'n8n-nodes-base.'+type,typeVersion:version,position:[x,y],parameters,...extra};nodes.push(n);return n;
  };
  const link=(a,b,out=0)=>{connections[a]??={main:[]};connections[a].main[out]??=[];connections[a].main[out].push({node:b,type:'main',index:0});};
  const code=(name,body,x,y)=>add(name,'code',2,{mode:'runOnceForAllItems',jsCode:body},x,y);
  const iff=(name,expr,x,y)=>add(name,'if',2.2,{conditions:{options:{caseSensitive:true,leftValue:'',typeValidation:'strict',version:2},conditions:[{id:name.toLowerCase().replaceAll(' ','-'),leftValue:'={{ '+expr+' }}',rightValue:'',operator:{type:'boolean',operation:'true',singleValue:true}}],combinator:'and'},options:{}},x,y);
  const pg=(name,query,params,x,y,retry=false)=>add(name,'postgres',2.6,{operation:'executeQuery',query,options:params?{queryReplacement:'={{ '+params+' }}'}:{}},x,y,{credentials:creds.pg,onError:'continueErrorOutput',alwaysOutputData:true,retryOnFail:retry,...(retry?{maxTries:2,waitBetweenTries:1000}:{})});
  const planRef="$('Planificar contenido').first().json";
  const ctx=planRef+'.contexto';
  const asset="$('Enviar de a una pieza').item.json";
  const scope=`[${ctx}.account_id,${ctx}.conversation_id,String($execution.id)]`;
  const assetParams=`[${ctx}.account_id,${ctx}.conversation_id,${ctx}.solicitud_id,${asset}.asset_id,${asset}.version,String($execution.id)]`;
  const identity=`const pieza=${asset}; const ident={asset_id:pieza.asset_id,version:pieza.version,indice:pieza.indice};`;
  const itemResult=(estado,motivo,extras='')=>`${identity}\nreturn [{json:{...ident,estado:${JSON.stringify(estado)},motivo:${JSON.stringify(motivo)},${extras}}}];`;
  const httpOptions={timeout:60000,response:{response:{fullResponse:true,neverError:true,responseFormat:'json'}},redirect:{redirect:{followRedirects:false}}};

  add('Recibir pedido multimedia','executeWorkflowTrigger',1.1,{inputSource:'workflowInputs',workflowInputs:{values:[{name:'solicitudes',type:'array'},{name:'account_id',type:'number'},{name:'conversation_id',type:'number'},{name:'solicitud_id',type:'string'},{name:'modo',type:'string'}]}},0,220,{notes:'El caller fija destino, solicitud_id estable y modo. Solo solicitudes es parámetro del modelo. Nunca exponer modo ni IDs de conversación con $fromAI.'});
  add('Probar seleccion sin enviar','manualTrigger',1,{},0,600);
  code('Ejemplo seguro',`return [{json:{modo:'simular',solicitudes:['fundas','tipo tapizado','alfombra','cubrevolante'].map(producto=>({producto,contenido:'presentacion'}))}}];`,250,600);
  code('Planificar contenido',`${seleccion}\nconst catalogo=${JSON.stringify(catalogo)};\nconst inputs=$input.all();\nconst plan=inputs.length===1?planificarSeleccion(inputs[0].json,catalogo):{ok:false,estado:'entrada_invalida',contexto:null,plan:[],solicitudes:[],errores:[{motivo:'se_requiere_un_solo_pedido'}],faltantes:[]};\nreturn [{json:{...plan,inicio_ms:Date.now()}}];`,500,220);
  iff('Corresponde enviar',`${planRef}.ok === true && ${ctx}?.modo === 'enviar' && ${planRef}.plan.length > 0`,750,220);
  code('Responder sin envio',`${seleccion}\nconst plan=$input.first().json;\nconst resultados=plan.contexto?.modo==='simular'?(plan.plan||[]).map(p=>({asset_id:p.asset_id,version:p.version,estado:'simulado'})):[];\nreturn [{json:resumirResultados(plan,resultados)}];`,1000,600);
  pg('Preparar registro aislado',sql.schema,null,1000,160);
  pg('Reservar conversacion',sql.acquireLock,scope,1250,160);
  iff('Conversacion reservada',"$json.acquired === true",1500,160);
  pg('Registrar solicitud',sql.registerRequest,`[${ctx}.account_id,${ctx}.conversation_id,${ctx}.solicitud_id,String($execution.id),JSON.stringify({solicitudes:${planRef}.solicitudes,plan:${planRef}.plan,catalogo_version:${planRef}.catalogo_version})]`,1750,160);
  iff('Solicitud compatible',"$json.compatible === true",2000,160);
  code('Preparar piezas',`const p=${planRef};return p.plan.map((asset,indice)=>({json:{...asset,indice},pairedItem:{item:0}}));`,2250,160);
  add('Enviar de a una pieza','splitInBatches',3,{batchSize:1,options:{reset:false}},2500,160,{notes:'Salida 0 termina el lote; salida 1 procesa una pieza. Se espera resultado persistido antes de continuar.'});
  iff('Tiempo disponible',`Date.now()-${planRef}.inicio_ms < 390000`,2750,340);
  pg('Reservar pieza',sql.claimAsset,assetParams,3000,340);
  iff('Pieza reservada',"$json.acquired === true",3250,340);
  code('Resolver repeticion',`${identity}\nconst r=$input.first().json;let estado=r.estado==='aceptado'?'omitido':r.estado==='fallido'?'fallido':'desconocido';const rawId=r.chatwoot_message_id;const numero=typeof rawId==='number'?rawId:typeof rawId==='string'&&/^[0-9]+$/.test(rawId)?Number(rawId):null;const messageId=Number.isSafeInteger(numero)&&numero>0?numero:null;\nreturn [{json:{...ident,estado,chatwoot_message_id:messageId,motivo:estado==='omitido'?'ya_aceptado_en_esta_solicitud':estado==='fallido'?'rechazo_anterior_no_reintentar':'intento_anterior_sin_conciliar',detener_lote:estado==='desconocido'}}];`,3500,700);
  add('Descargar pieza de Drive','googleDrive',3,{resource:'file',operation:'download',fileId:{__rl:true,value:`={{ ${asset}.fuente.id }}`,mode:'id'},options:{binaryPropertyName:'data'}},3500,260,{credentials:creds.drive,onError:'continueErrorOutput',retryOnFail:true,maxTries:2,waitBetweenTries:1000});
  add('Calcular hash del archivo','crypto',1,{action:'hash',binaryData:true,binaryPropertyName:'data',type:'SHA256',dataPropertyName:'sha256_actual',encoding:'hex'},3750,260,{onError:'continueErrorOutput'});
  code('Validar archivo',`${identity}\nconst input=$input.first();let valido=false;let motivo='archivo_invalido';\ntry{const b=await this.helpers.getBinaryDataBuffer(0,'data');const max=pieza.formato==='foto'?5*1024*1024:16*1024*1024;const mime=pieza.mime;const magic=mime==='image/jpeg'?(b[0]===255&&b[1]===216&&b[2]===255):mime==='image/png'?(b[0]===137&&b[1]===80&&b[2]===78&&b[3]===71):mime==='video/mp4'?(b.subarray(4,8).toString()==='ftyp'):false;valido=input.json.sha256_actual===pieza.sha256&&b.length===pieza.bytes&&b.length>0&&b.length<=max&&magic;if(valido){input.binary.data.mimeType=mime;input.binary.data.fileName=pieza.nombre_archivo;}}catch{motivo='archivo_no_legible';}\nreturn [{json:{...ident,valido,motivo:valido?null:motivo},binary:valido?input.binary:undefined}];`,4000,260);
  iff('Archivo correcto',"$json.valido === true",4250,260);
  add('Verificar conversacion actual','httpRequest',4.2,{method:'GET',url:`=https://chatwoot.teotec.org/api/v1/accounts/1/conversations/{{ ${ctx}.conversation_id }}`,authentication:'genericCredentialType',genericAuthType:'httpHeaderAuth',options:httpOptions},4500,180,{credentials:creds.cw,onError:'continueErrorOutput',retryOnFail:true,maxTries:2,waitBetweenTries:1000});
  code('Evaluar control humano',`${entrega}\n${identity}\nlet r=evaluarConversacion($input.first().json,${ctx});if(r.permitido&&Date.now()-${planRef}.inicio_ms>=390000)r={permitido:false,estado:'fallido',motivo:'presupuesto_de_tiempo_agotado'};\nreturn [{json:{...ident,...r}}];`,4750,180);
  iff('Bot puede continuar',"$json.permitido === true",5000,180);
  pg('Marcar inicio envio',sql.markSending,assetParams,5250,100);
  iff('Puede iniciar envio',"$json.enabled === true",5500,100);
  code('Recuperar archivo validado',`const validado=$('Validar archivo').item;return [{json:validado.json,binary:validado.binary}];`,5750,100);
  iff('Tiempo antes del POST',`Date.now()-${planRef}.inicio_ms < 390000`,5750,340);
  code('Detener sin iniciar POST',itemResult('fallido','presupuesto_de_tiempo_agotado_sin_post',"estado_db:'fallido',detener_lote:true"),6000,600);
  add('Enviar adjunto por Chatwoot','httpRequest',4.2,{method:'POST',url:`=https://chatwoot.teotec.org/api/v1/accounts/1/conversations/{{ ${ctx}.conversation_id }}/messages`,authentication:'genericCredentialType',genericAuthType:'httpHeaderAuth',sendBody:true,contentType:'multipart-form-data',bodyParameters:{parameters:[{name:'message_type',value:'outgoing'},{name:'private',value:'false'},{parameterType:'formBinaryData',name:'attachments[]',inputDataFieldName:'data'}]},options:httpOptions},6000,100,{credentials:creds.cw,onError:'continueErrorOutput',retryOnFail:false,notes:'Sin retry del POST: un timeout puede haber creado el mensaje. Los fallos se registran por pieza; no se vuelve a enviar por suposición.'});
  code('Evaluar resultado Chatwoot',`${entrega}\n${identity}\nconst r=evaluarRespuestaEnvio($input.first().json,{...${ctx},formato:pieza.formato});return [{json:{...ident,...r,estado_db:r.estado,detener_lote:r.estado==='desconocido'}}];`,6250,100);

  code('Fallo previo al envio',itemResult('fallido','descarga_o_integridad_invalida',"estado_db:'fallo_previo',detener_lote:false"),4500,600);
  code('Detener por control',`${identity}\nconst gate=$input.first().json;return [{json:{...ident,estado:gate.estado==='control_humano'?'control_humano':'fallido',motivo:gate.motivo||'control_no_verificable',estado_db:'fallo_previo',detener_lote:true}}];`,5250,500);
  code('Detener por persistencia',itemResult('desconocido','registro_persistente_no_confirmado',"detener_lote:true"),5500,850);
  code('Detener por tiempo',itemResult('fallido','presupuesto_de_tiempo_agotado',"detener_lote:true"),3000,850);
  code('Resultado para registrar',`return [{json:$input.first().json}];`,6500,340);
  const resultado="$('Resultado para registrar').item.json";
  pg('Registrar resultado de pieza',sql.recordResult,`[...${assetParams},${resultado}.estado_db,${resultado}.chatwoot_message_id??null,${resultado}.motivo??null]`,6750,340,true);
  code('Comprobar registro',`const r=${resultado};const confirmado=$input.first().json.recorded===true;return [{json:{...r,registro_confirmado:confirmado,detener_lote:r.detener_lote||!confirmado,advertencia:confirmado?null:'no_se_pudo_confirmar_registro_no_reintentar'}}];`,7000,340);
  code('Resultado pieza',`return [{json:$input.first().json}];`,7250,340);
  iff('Continuar lote',"$json.detener_lote !== true",7500,340);
  add('Pausa entre piezas','wait',1.1,{resume:'timeInterval',amount:2,unit:'seconds'},7750,180);

  code('Resumir envios',`${seleccion}\nconst p=${planRef};return [{json:resumirResultados(p,$input.all().map(i=>i.json))}];`,2750,-180);
  code('Resumir interrupcion',`${seleccion}\nconst p=${planRef};const actual=$input.first().json;const resultados=[];for(let i=0;i<actual.indice;i++){try{resultados.push(...$('Resultado pieza').all(0,i).map(r=>r.json));}catch{}}resultados.push(actual);for(const a of p.plan.slice(actual.indice+1)){resultados.push({asset_id:a.asset_id,version:a.version,estado:actual.estado==='control_humano'?'control_humano':'fallido',motivo:'lote_detenido_sin_intentar_envio'});}const resumen=resumirResultados(p,resultados);resumen.lote_detenido=true;resumen.advertencias=resultados.filter(r=>r.advertencia).map(r=>({asset_id:r.asset_id,motivo:r.advertencia}));return [{json:resumen}];`,7750,600);
  code('Error inicial',`${seleccion}\nconst p=${planRef};const resultados=p.plan.map(a=>({asset_id:a.asset_id,version:a.version,estado:'fallido',motivo:'registro_o_exclusion_no_disponible'}));return [{json:resumirResultados(p,resultados)}];`,2000,-500);
  code('Solicitud ya ocupada',`${seleccion}\nconst p=${planRef};const resumen=resumirResultados(p,p.plan.map(a=>({asset_id:a.asset_id,version:a.version,estado:'fallido',motivo:'conversacion_ocupada_o_solicitud_incompatible'})));return [{json:resumen}];`,2000,850);
  code('Respuesta antes de liberar',`return [{json:$input.first().json}];`,8100,-180);
  pg('Liberar conversacion',sql.releaseLock,scope,8350,-180,true);
  code('Devolver resultado',`const resumen=$('Respuesta antes de liberar').first().json;const liberado=$input.first().json.released===true;return [{json:{...resumen,...(!liberado?{aviso_registro:'No se confirmó la liberación del bloqueo propio; no forzar reenvío.'}:{})}}];`,8600,-180);

  link('Recibir pedido multimedia','Planificar contenido');link('Probar seleccion sin enviar','Ejemplo seguro');link('Ejemplo seguro','Planificar contenido');link('Planificar contenido','Corresponde enviar');
  link('Corresponde enviar','Preparar registro aislado');link('Corresponde enviar','Responder sin envio',1);
  link('Preparar registro aislado','Reservar conversacion');link('Preparar registro aislado','Error inicial',1);
  link('Reservar conversacion','Conversacion reservada');link('Reservar conversacion','Error inicial',1);
  link('Conversacion reservada','Registrar solicitud');link('Conversacion reservada','Solicitud ya ocupada',1);
  link('Registrar solicitud','Solicitud compatible');link('Registrar solicitud','Error inicial',1);
  link('Solicitud compatible','Preparar piezas');link('Solicitud compatible','Solicitud ya ocupada',1);
  link('Preparar piezas','Enviar de a una pieza');link('Enviar de a una pieza','Resumir envios',0);link('Enviar de a una pieza','Tiempo disponible',1);
  link('Tiempo disponible','Reservar pieza');link('Tiempo disponible','Detener por tiempo',1);
  link('Reservar pieza','Pieza reservada');link('Reservar pieza','Detener por persistencia',1);
  link('Pieza reservada','Descargar pieza de Drive');link('Pieza reservada','Resolver repeticion',1);
  link('Descargar pieza de Drive','Calcular hash del archivo');link('Descargar pieza de Drive','Fallo previo al envio',1);
  link('Calcular hash del archivo','Recuperar binario tras hash');link('Recuperar binario tras hash','Validar archivo');link('Calcular hash del archivo','Fallo previo al envio',1);
  link('Validar archivo','Archivo correcto');link('Archivo correcto','Verificar conversacion actual');link('Archivo correcto','Fallo previo al envio',1);
  link('Verificar conversacion actual','Evaluar control humano');link('Verificar conversacion actual','Evaluar control humano',1);
  link('Evaluar control humano','Bot puede continuar');link('Bot puede continuar','Marcar inicio envio');link('Bot puede continuar','Detener por control',1);
  link('Marcar inicio envio','Puede iniciar envio');link('Marcar inicio envio','Detener por persistencia',1);
  link('Puede iniciar envio','Recuperar archivo validado');link('Puede iniciar envio','Detener por persistencia',1);
  link('Recuperar archivo validado','Tiempo antes del POST');link('Tiempo antes del POST','Enviar adjunto por Chatwoot');link('Tiempo antes del POST','Detener sin iniciar POST',1);link('Enviar adjunto por Chatwoot','Evaluar resultado Chatwoot');link('Enviar adjunto por Chatwoot','Evaluar resultado Chatwoot',1);
  for(const n of ['Evaluar resultado Chatwoot','Fallo previo al envio','Detener por control','Detener sin iniciar POST'])link(n,'Resultado para registrar');
  link('Resultado para registrar','Registrar resultado de pieza');link('Registrar resultado de pieza','Comprobar registro');link('Registrar resultado de pieza','Comprobar registro',1);
  for(const n of ['Comprobar registro','Resolver repeticion','Detener por persistencia','Detener por tiempo'])link(n,'Resultado pieza');
  link('Resultado pieza','Continuar lote');link('Continuar lote','Pausa entre piezas');link('Continuar lote','Resumir interrupcion',1);link('Pausa entre piezas','Enviar de a una pieza');
  for(const n of ['Resumir envios','Resumir interrupcion','Error inicial','Solicitud ya ocupada'])link(n,'Respuesta antes de liberar');
  link('Respuesta antes de liberar','Liberar conversacion');link('Liberar conversacion','Devolver resultado');link('Liberar conversacion','Devolver resultado',1);

  const note=(name,content,x,y,width,color=5)=>add(name,'stickyNote',1,{content,height:200,width,color},x,y);
  note('Contrato de la herramienta','### 1 · Una llamada, varios productos\nSolo `solicitudes` pertenece al modelo. El caller fija conversación, solicitud_id estable y modo. El botón manual simula sin DB, Drive ni Chatwoot. Nuevo flujo aislado: todavía no conectado al agente principal.',-40,-120,920);
  note('Exclusion e historial','### 2 · Registro aislado\nTres tablas `f7_multimedia_*`, creadas si faltan. Lease 900 s > timeout 480 s. Misma solicitud_id con otro contenido se rechaza. No se modifica el estado comercial anterior.',1000,-150,1250);
  note('Seleccion de archivos','### 3 · Catálogo cerrado y una pieza por vez\nFuentes permitidas de Drive, versión y SHA-256 fijados. Orden por solicitud y luego catálogo. Reservar, descargar, verificar bytes y hash. Un medio faltante nunca se sustituye por otro producto.',2800,-90,1500);
  note('Permiso para enviar','### 4 · Control humano y destino\nGET de la conversación antes de cada POST. Fallo de verificación o etiqueta humano detiene el lote. Persiste `enviando` ANTES del POST. No hay reintento automático del POST.',4500,-200,1700);
  note('Resultado verificable','### 5 · Resultado por archivo\nAceptado por Chatwoot no equivale a entregado/leído. Fallos 5xx, timeout o respuestas inconsistentes quedan inciertos. Se detiene lo pendiente y se preserva lo ya enviado. La conciliación de inciertos es explícita.',6500,-180,1400);
  note('Antes de habilitar','### Pendiente de runtime\nVerificar acceso OAuth a los medios y ejecución Postgres/Chatwoot. Mateo realiza activación y prueba real. No ejecutar modo enviar con clientes para probar. Errores inesperados conservan el estado y el lock vence; revisar ejecuciones.',8100,120,850,3);
  const recuperarBinario=code('Recuperar binario tras hash',`const hash=$input.first();const descarga=$('Descargar pieza de Drive').item;return [{json:hash.json,binary:descarga.binary,pairedItem:{item:0}}];`,3875,-450);
  recuperarBinario.id='f7-mm-recuperar-binario-hash';
  return {name:'F7 · Enviar multimedia · v1',nodes,connections,settings:{executionOrder:'v1',timezone:'America/Argentina/Buenos_Aires',executionTimeout:480,saveDataErrorExecution:'all',saveDataSuccessExecution:'all',saveManualExecutions:true,callerPolicy:'workflowsFromSameOwner'}};
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const target=path.resolve(base,'../../workflows/inactivos/herramienta-multimedia-v1.json');
  const wf=construirWorkflow();
  if(fs.existsSync(target)){const prev=JSON.parse(fs.readFileSync(target,'utf8'));if(prev.id){wf.id=prev.id;wf.active=prev.active;wf.createdAt=prev.createdAt;wf.updatedAt=prev.updatedAt;wf.versionId=prev.versionId;}}
  fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,JSON.stringify(wf,null,2)+'\n','utf8');
  console.log(JSON.stringify({archivo:target,nodos:wf.nodes.length,conexiones:Object.keys(wf.connections).length}));
}
