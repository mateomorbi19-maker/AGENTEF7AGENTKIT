/**
 * Selección determinística de multimedia F7. No hace I/O ni decide qué quiso
 * decir un cliente: recibe pedidos estructurados del agente y contexto fijado
 * por el flujo llamador. Se inserta también en un nodo Code de n8n.
 */
const PRODUCTOS = ['fundas', 'tipo tapizado', 'alfombra', 'cubrevolante'];
const CONTENIDOS = ['presentacion', 'disenos', 'colores', 'calidad', 'comparacion'];
const FORMATOS = ['auto', 'foto', 'video'];
const ESTADOS_RESULTADO = ['aceptado', 'fallido', 'desconocido', 'omitido', 'control_humano', 'simulado'];
const MAX_SOLICITUDES = 16;
const MAX_PIEZAS = 20;

function objeto(valor) {
  return valor !== null && typeof valor === 'object' && !Array.isArray(valor)
    && Object.prototype.toString.call(valor) === '[object Object]';
}

function etiqueta(valor) {
  return typeof valor === 'string'
    ? valor.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ')
    : null;
}

function identificador(valor, max = 160) {
  return typeof valor === 'string' && valor.length > 0 && valor.length <= max && /^[A-Za-z0-9:_-]+$/.test(valor);
}

function camposValidos(valor, permitidos, ruta, errores) {
  if (!objeto(valor)) {
    errores.push({ campo: ruta, motivo: 'objeto_requerido' });
    return false;
  }
  const keys = Reflect.ownKeys(valor);
  if (keys.some(key => typeof key !== 'string' || !permitidos.includes(key))) {
    // No devolver el nombre arbitrario recibido: podría contener instrucciones o datos privados.
    errores.push({ campo: ruta, motivo: 'campo_no_permitido' });
    return false;
  }
  return true;
}

export function normalizarEntrada(input, _catalogo) {
  const errores = [];
  if (!camposValidos(input, ['account_id', 'conversation_id', 'solicitud_id', 'modo', 'solicitudes'], 'entrada', errores)) {
    return { ok: false, entrada: null, errores };
  }
  const modo = input.modo === undefined ? 'simular' : input.modo;
  const account_id = input.account_id === undefined ? 1 : input.account_id;
  const conversation_id = input.conversation_id === undefined ? null : input.conversation_id;
  const solicitud_id = input.solicitud_id === undefined ? null : input.solicitud_id;
  if (!['simular', 'enviar'].includes(modo)) errores.push({ campo: 'modo', motivo: 'valor_no_permitido' });
  if (account_id !== 1) errores.push({ campo: 'account_id', motivo: 'cuenta_no_permitida' });
  if ((conversation_id !== null || modo === 'enviar') && (!Number.isSafeInteger(conversation_id) || conversation_id <= 0)) {
    errores.push({ campo: 'conversation_id', motivo: 'entero_positivo_requerido' });
  }
  if ((solicitud_id !== null || modo === 'enviar') && !identificador(solicitud_id)) {
    errores.push({ campo: 'solicitud_id', motivo: 'identificador_requerido' });
  }
  if (!Array.isArray(input.solicitudes) || input.solicitudes.length < 1 || input.solicitudes.length > MAX_SOLICITUDES) {
    errores.push({ campo: 'solicitudes', motivo: 'cantidad_fuera_de_limite' });
    return { ok: false, entrada: null, errores };
  }
  const solicitudes = [];
  for (let index = 0; index < input.solicitudes.length; index++) {
    const solicitud = input.solicitudes[index];
    const campo = `solicitudes[${index}]`;
    if (!camposValidos(solicitud, ['producto', 'contenido', 'disenos', 'formato', 'reenvio_solicitado'], campo, errores)) continue;
    const producto = etiqueta(solicitud.producto);
    const contenido = etiqueta(solicitud.contenido);
    const formato = solicitud.formato === undefined ? 'auto' : etiqueta(solicitud.formato);
    const reenvio_solicitado = solicitud.reenvio_solicitado === undefined ? false : solicitud.reenvio_solicitado;
    if (!PRODUCTOS.includes(producto)) errores.push({ campo: `${campo}.producto`, motivo: 'producto_no_permitido' });
    if (!CONTENIDOS.includes(contenido)) errores.push({ campo: `${campo}.contenido`, motivo: 'contenido_no_permitido' });
    if (!FORMATOS.includes(formato)) errores.push({ campo: `${campo}.formato`, motivo: 'formato_no_permitido' });
    if (typeof reenvio_solicitado !== 'boolean') errores.push({ campo: `${campo}.reenvio_solicitado`, motivo: 'booleano_requerido' });
    let disenos;
    if (solicitud.disenos !== undefined) {
      if (contenido !== 'disenos' || !Array.isArray(solicitud.disenos) || solicitud.disenos.length < 1 || solicitud.disenos.length > 10) {
        errores.push({ campo: `${campo}.disenos`, motivo: 'filtro_de_disenos_invalido' });
      } else {
        disenos = solicitud.disenos.map(etiqueta);
        if (disenos.some(diseno => diseno === null || diseno.length < 1 || diseno.length > 60 || !/^[a-z0-9][a-z0-9 -]*$/.test(diseno))) {
          errores.push({ campo: `${campo}.disenos`, motivo: 'nombre_de_diseno_invalido' });
        } else disenos = [...new Set(disenos)];
      }
    }
    solicitudes.push({ producto, contenido, ...(disenos === undefined ? {} : { disenos }), formato, reenvio_solicitado });
  }
  const comparaciones = solicitudes.filter(solicitud => solicitud.contenido === 'comparacion');
  if (comparaciones.length && (
    comparaciones.some(solicitud => !['fundas', 'tipo tapizado'].includes(solicitud.producto))
    || !['fundas', 'tipo tapizado'].every(producto => comparaciones.some(solicitud => solicitud.producto === producto))
  )) errores.push({ campo: 'solicitudes', motivo: 'comparacion_requiere_ambas_fundas' });
  return errores.length
    ? { ok: false, entrada: null, errores }
    : { ok: true, entrada: { account_id, conversation_id, solicitud_id, modo, solicitudes }, errores: [] };
}

function validarCatalogo(catalogo) {
  const errores = [];
  if (!objeto(catalogo) || typeof catalogo.version !== 'string' || !catalogo.version.length
      || !Array.isArray(catalogo.assets) || !Array.isArray(catalogo.rutas)
      || catalogo.assets.length > 200 || catalogo.rutas.length > 200) {
    return [{ campo: 'catalogo', motivo: 'estructura_invalida' }];
  }
  const ids = new Set();
  for (const asset of catalogo.assets) {
    if (!objeto(asset) || !identificador(asset.id) || typeof asset.version !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$/.test(asset.version)
        || ids.has(asset.id) || typeof asset.habilitado !== 'boolean'
        || !Array.isArray(asset.productos_visibles) || asset.productos_visibles.some(p => !PRODUCTOS.includes(p))
        || !['foto', 'video'].includes(asset.formato)
        || !Number.isFinite(asset.orden) || asset.orden < 0) {
      errores.push({ campo: 'catalogo.assets', motivo: 'asset_invalido' });
      continue;
    }
    ids.add(asset.id);
    // Una pieza deshabilitada puede carecer de fuente: representa una falta conocida.
    if (asset.habilitado && (!objeto(asset.fuente) || asset.fuente.tipo !== 'drive' || !identificador(asset.fuente.id)
        || typeof asset.titulo !== 'string' || asset.titulo.length > 180
        || typeof asset.nombre_archivo !== 'string' || !asset.nombre_archivo.length || asset.nombre_archivo.length > 180
        || /[/\\\r\n]/.test(asset.nombre_archivo)
        || typeof asset.mime !== 'string' || !(asset.formato === 'foto' ? /^image\// : /^video\//).test(asset.mime)
        || typeof asset.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(asset.sha256)
        || !Number.isSafeInteger(asset.bytes) || asset.bytes <= 0)) {
      errores.push({ campo: 'catalogo.assets', motivo: 'fuente_o_metadata_invalida' });
    }
  }
  const rutas = new Set();
  for (const ruta of catalogo.rutas) {
    if (!objeto(ruta) || !PRODUCTOS.includes(ruta.producto) || !CONTENIDOS.includes(ruta.contenido)
        || (ruta.contenido === 'disenos' && (typeof ruta.diseno !== 'string' || etiqueta(ruta.diseno) !== ruta.diseno || !ruta.diseno.length))
        || (ruta.contenido !== 'disenos' && ruta.diseno !== undefined && ruta.diseno !== null)
        || !Array.isArray(ruta.opciones) || ruta.opciones.length > 20) {
      errores.push({ campo: 'catalogo.rutas', motivo: 'ruta_invalida' });
      continue;
    }
    const clave = JSON.stringify([ruta.producto, ruta.contenido, ruta.diseno ?? null]);
    if (rutas.has(clave)) errores.push({ campo: 'catalogo.rutas', motivo: 'ruta_duplicada' });
    rutas.add(clave);
    const opciones = new Set();
    for (const opcion of ruta.opciones) {
      if (!objeto(opcion) || !identificador(opcion.id) || opciones.has(opcion.id)
          || !Number.isFinite(opcion.prioridad) || !Array.isArray(opcion.asset_ids)
          || !opcion.asset_ids.length || opcion.asset_ids.length > MAX_PIEZAS
          || opcion.asset_ids.some(id => !ids.has(id))) {
        errores.push({ campo: 'catalogo.opciones', motivo: 'opcion_invalida' });
      } else opciones.add(opcion.id);
    }
  }
  return errores;
}

function formatoAdmitido(asset, solicitud) {
  return solicitud.formato === 'auto' || solicitud.formato === asset.formato;
}

function assetAdmitido(asset, solicitud, solicitudes, diseno) {
  if (!asset.habilitado || !formatoAdmitido(asset, solicitud)) return false;
  // Nombrar dos productos en cualquier parte de la llamada no habilita a mostrar
  // todo de ambos. Cada producto visible necesita una solicitud del mismo uso.
  return asset.productos_visibles.every(producto => solicitudes.some(otra =>
    otra.producto === producto && otra.contenido === solicitud.contenido && formatoAdmitido(asset, otra)
    && (solicitud.contenido !== 'disenos' || !otra.disenos || otra.disenos.includes(diseno))
  ));
}

export function planificarSeleccion(input, catalogo) {
  const normalizacion = normalizarEntrada(input, catalogo);
  const salida = { ok: false, estado: 'entrada_invalida', contexto: null, catalogo_version: catalogo?.version ?? null, solicitudes: [], plan: [], faltantes: [], errores: normalizacion.errores };
  if (!normalizacion.ok) return salida;
  const { solicitudes, ...contexto } = normalizacion.entrada;
  salida.contexto = contexto;
  salida.solicitudes = solicitudes;
  const errores = validarCatalogo(catalogo);
  if (errores.length) return { ...salida, estado: 'catalogo_invalido', errores };
  const assets = new Map(catalogo.assets.map(asset => [asset.id, asset]));
  const seleccionados = new Map();
  for (let solicitud_indice = 0; solicitud_indice < solicitudes.length; solicitud_indice++) {
    const solicitud = solicitudes[solicitud_indice];
    const rutas = catalogo.rutas.filter(ruta => ruta.producto === solicitud.producto && ruta.contenido === solicitud.contenido);
    const disenos = solicitud.contenido === 'disenos'
      ? (solicitud.disenos ?? rutas.map(ruta => ruta.diseno)) : [null];
    const objetivos = disenos.length ? disenos : [null];
    for (const diseno of objetivos) {
      const ruta = rutas.find(ruta => (ruta.diseno ?? null) === diseno);
      const opciones = [...(ruta?.opciones ?? [])].sort((a, b) => a.prioridad - b.prioridad || a.id.localeCompare(b.id));
      const opcion = opciones.find(opcion => opcion.asset_ids.every(id => assetAdmitido(assets.get(id), solicitud, solicitudes, diseno)));
      if (!opcion) {
        salida.faltantes.push({ solicitud_indice, producto: solicitud.producto, contenido: solicitud.contenido, diseno,
          motivo: ruta ? 'sin_material_compatible' : 'sin_material_especifico' });
        continue;
      }
      for (const id of opcion.asset_ids) {
        const asset = assets.get(id);
        const anterior = seleccionados.get(id);
        if (anterior) {
          if (!anterior.solicitud_indices.includes(solicitud_indice)) anterior.solicitud_indices.push(solicitud_indice);
          anterior.reenvio_solicitado ||= solicitud.reenvio_solicitado;
        } else {
          seleccionados.set(id, { asset_id: asset.id, version: asset.version, titulo: asset.titulo,
            nombre_archivo: asset.nombre_archivo, mime: asset.mime, sha256: asset.sha256, bytes: asset.bytes,
            formato: asset.formato, fuente: { tipo: asset.fuente.tipo, id: asset.fuente.id }, orden: asset.orden,
            productos_visibles: [...asset.productos_visibles], solicitud_indices: [solicitud_indice],
            reenvio_solicitado: solicitud.reenvio_solicitado });
        }
      }
    }
  }
  if (seleccionados.size > MAX_PIEZAS) {
    return { ...salida, estado: 'entrada_invalida', plan: [], faltantes: [], errores: [{ campo: 'solicitudes', motivo: 'demasiadas_piezas' }] };
  }
  salida.plan = [...seleccionados.values()]
    .sort((a, b) => a.solicitud_indices[0] - b.solicitud_indices[0] || a.orden - b.orden || a.asset_id.localeCompare(b.asset_id))
    .map((asset, i) => ({ ...asset, posicion: i + 1 }));
  salida.ok = true;
  salida.estado = salida.faltantes.length ? (salida.plan.length ? 'parcial' : 'sin_material') : 'listo';
  return salida;
}

function resolverEstado(estados, faltantes) {
  if (!estados.length) return faltantes ? 'sin_material' : 'sin_resultados';
  if (faltantes) return 'parcial';
  const unicos = [...new Set(estados)];
  if (unicos.length === 1) return unicos[0];
  if (unicos.every(estado => ['aceptado', 'omitido'].includes(estado))) return 'aceptado';
  return 'parcial';
}

export function resumirResultados(plan, resultados) {
  const salida = { ok: false, estado: plan?.estado ?? 'entrada_invalida', solicitud_id: plan?.contexto?.solicitud_id ?? null,
    modo: plan?.contexto?.modo ?? 'simular', entrega_confirmada: false, aceptados: [], omitidos: [], fallidos: [],
    desconocidos: [], control_humano: [], simulados: [], faltantes: plan?.faltantes ?? [], errores: plan?.errores ?? [], solicitudes: [] };
  if (!plan?.ok || !Array.isArray(plan.plan)) return salida;
  const buckets = { aceptado: 'aceptados', omitido: 'omitidos', fallido: 'fallidos', desconocido: 'desconocidos', control_humano: 'control_humano', simulado: 'simulados' };
  const items = [];
  for (const asset of plan.plan) {
    const matches = (Array.isArray(resultados) ? resultados : []).filter(r => objeto(r) && r.asset_id === asset.asset_id && r.version === asset.version);
    let estado = 'desconocido';
    let motivo = 'resultado_ausente';
    let chatwoot_message_id = null;
    if (matches.length) {
      const firmas = new Set(matches.map(r => JSON.stringify([r.estado, r.chatwoot_message_id ?? r.message_id ?? null])));
      const primero = matches[0];
      const msg = primero.chatwoot_message_id ?? primero.message_id ?? null;
      if (firmas.size > 1) motivo = 'resultados_contradictorios';
      else if (!ESTADOS_RESULTADO.includes(primero.estado)) motivo = 'estado_no_reconocido';
      else if (salida.modo === 'simular' && primero.estado !== 'simulado') motivo = 'resultado_incompatible_con_simulacion';
      else if (salida.modo === 'enviar' && primero.estado === 'simulado') motivo = 'simulacion_en_modo_enviar';
      else if (primero.estado === 'aceptado' && (!Number.isSafeInteger(msg) || msg <= 0)) motivo = 'aceptacion_sin_identificador';
      else {
        estado = primero.estado;
        motivo = typeof primero.motivo === 'string' && /^[a-z0-9_:-]{1,120}$/.test(primero.motivo) ? primero.motivo : null;
        chatwoot_message_id = Number.isSafeInteger(msg) && msg > 0 ? msg : null;
      }
    }
    const item = { asset_id: asset.asset_id, version: asset.version, estado, motivo, chatwoot_message_id, solicitud_indices: [...asset.solicitud_indices] };
    salida[buckets[estado]].push(item);
    items.push(item);
  }
  salida.estado = resolverEstado(items.map(item => item.estado), salida.faltantes.length);
  salida.ok = ['aceptado', 'omitido', 'simulado'].includes(salida.estado);
  salida.solicitudes = plan.solicitudes.map((solicitud, solicitud_indice) => {
    const propios = items.filter(item => item.solicitud_indices.includes(solicitud_indice));
    const faltantes = salida.faltantes.filter(f => f.solicitud_indice === solicitud_indice);
    return { solicitud_indice, producto: solicitud.producto, contenido: solicitud.contenido,
      estado: resolverEstado(propios.map(item => item.estado), faltantes.length),
      asset_ids: propios.map(item => item.asset_id), faltantes };
  });
  return salida;
}
