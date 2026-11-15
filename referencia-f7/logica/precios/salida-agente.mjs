// El presupuesto completo y su evidencia quedan en el registro de la herramienta.
// Tras enviarlo, el LLM recibe el estado; el mensaje ya incluye la pregunta comercial.
export function resumirParaAgente(resultado,envio,pedido) {
 const limpio=v=>String(v??'').replace(/[*_`#<>]/g,'').replace(/[\r\n\t]+/g,' ').trim();
 const items=(resultado.items??[]).map(i=>({producto:i.producto,modelo:i.modelo,estado:i.estado,cantidad:i.cantidad,configuracion:i.configuracion,
  ...(i.motivo?{motivo:i.motivo}:{}),...(i.opciones?{opciones:i.opciones}:{}),
  medios_disponibles:Object.keys(i.precios??{}),
 }));
 let continuacion='';
 const aceptado=['aceptado','omitido'].includes(envio?.estado);
 const pendiente=items.find(i=>i.estado==='requiere_aclaracion');
 if(envio?.estado==='control_humano')continuacion='';
 else if(['desconocido','fallido'].includes(envio?.estado))continuacion='No pude confirmar el envío de la cotización. Esa parte necesita revisión del equipo.';
 else if(pendiente){
  const opciones=(pendiente.opciones??[]).map(o=>limpio(o.modelo??o.configuracion)).filter(Boolean);
  const conflicto=/importes distintos|contradic|inconsisten|no coincide/.test(pendiente.motivo??'');
  continuacion=opciones.length>1&&!conflicto?`Para ${limpio(pendiente.producto)}, ¿cuál de estas opciones corresponde a tu vehículo: ${opciones.join(' o ')}?`:limpio(pendiente.motivo)+(opciones.length===1&&!conflicto?` Opción publicada: ${opciones[0]}.`:'');
 } else if(aceptado&&resultado.estado==='cotizado') {
  // La herramienta ya mandó presupuesto y pregunta exacta en un único mensaje.
  continuacion='';
 } else if(resultado.estado==='error_consulta')continuacion='Ahora no pude consultar el precio. Esa parte necesita revisión del equipo.';
 else {
  const sinPrecio=items.find(i=>['sin_precio','no_encontrado'].includes(i.estado));
  continuacion=sinPrecio?limpio(sinPrecio.motivo):limpio((resultado.aclaraciones??[])[0]);
 }
 return {estado:resultado.estado,items,envio,consultado_en:resultado.consultado_en,
  metodo_pago:resultado.metodo_pago,pregunta_comercial_incluida:resultado.pregunta_comercial_incluida===true,
  ...(resultado.estado==='metodo_no_confirmado'?{requiere_derivacion:'revision_especial'}:{}),
  cotizacion_enviada:aceptado,continuacion_obligatoria:continuacion,
  instrucciones:'Consultar cuánto sale con un medio de pago no es confirmar una compra. Si pide comprar, pagar, reservar, una persona o posventa, priorizá derivar_humano. Con metodo_no_confirmado invocá derivar_humano con revision_especial sin prometer tarifa ni aceptación. Con metodo_no_disponible copiá continuacion_obligatoria. Con cotización aceptada u omitida y continuación vacía no repitas presupuesto ni agregues otra elección de pago: la herramienta ya dio el valor solicitado. Si hay otra duda factual explícita, podés responderla brevemente. Las aclaraciones y errores conservan su continuación literal. No agregues importes ni cambies rangos de año. Control humano o bot pausado exige silencio.'};
}
