// Motor puro: no usa red, credenciales, LLM, reloj ni estado del workflow.
// Los importes salen únicamente de celdas numéricas positivas de las hojas.
export const PRODUCTOS = Object.freeze({
  fundas: 'Fundas a medida',
  'tipo tapizado': 'TIPO TAPIZADO',
  tapiceria: 'TAPICERIA',
  alfombra: 'Termoformadas',
  'funda baul': 'Funda Baúl - Antiderrame',
  'cobertor caja': 'Cobertores de caja ',
  espuma: 'ESPUMAS',
  otros: 'Otros',
  cubrevolante: 'Otros',
});

const ROTULOS = {
  fundas: 'Fundas a medida', 'tipo tapizado': 'Fundas tipo tapizado',
  tapiceria: 'Tapicería', alfombra: 'Alfombra termoformada',
  'funda baul': 'Funda de baúl antiderrame', 'cobertor caja': 'Cobertor de caja',
  espuma: 'Espuma', otros: 'Producto o servicio', cubrevolante: 'Cubrevolante',
};
const ASIENTOS = new Set(['fundas', 'tipo tapizado', 'tapiceria']);
const MEDIOS = ['efectivo', 'transferencia', 'cuotas'];
const REGLA_CUOTAS = 'Autorización expresa de Mateo: cuotas = importe de transferencia. No se usa la columna POSNET.';
const limpiar = value => String(value ?? '').replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
const normal = value => limpiar(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const palabras = value => normal(value).replace(/[^a-z0-9]+/g, ' ').trim();
const objeto = value => !!value && typeof value === 'object' && !Array.isArray(value);
const textoPlano = value => limpiar(value).replace(/[*_`#\[\]<>]/g, '');

export function normalizarEntrada(entrada) {
  const errores = [];
  if (!objeto(entrada)) return { ok: false, entrada: null, errores: ['La solicitud debe ser un objeto.'], hojas: [] };
  const extras = Object.keys(entrada).filter(k => !['consultas', 'modalidad', 'tipo_solicitud', 'metodo_pago'].includes(k));
  if (extras.length) errores.push('La solicitud contiene campos no admitidos.');
  const modalidad = normal(entrada.modalidad);
  const tipo = normal(entrada.tipo_solicitud);
  const metodo_pago = entrada.metodo_pago === undefined ? 'transferencia' : normal(entrada.metodo_pago);
  if (!['transferencia', 'efectivo', 'cuotas', 'debito', 'otro'].includes(metodo_pago)) errores.push('metodo_pago debe ser transferencia, efectivo, cuotas, debito u otro.');
  if (!['caba', 'envio'].includes(modalidad)) errores.push('modalidad debe ser caba o envio.');
  if (!['consulta', 'comparacion', 'combo'].includes(tipo)) errores.push('tipo_solicitud debe ser consulta, comparacion o combo.');
  if (!Array.isArray(entrada.consultas) || entrada.consultas.length < 1 || entrada.consultas.length > 10) {
    errores.push('Se necesitan entre 1 y 10 consultas.');
  }
  const consultas = (Array.isArray(entrada.consultas) ? entrada.consultas.slice(0, 10) : []).map((consulta, index) => {
    if (!objeto(consulta)) { errores.push(`Consulta ${index + 1}: debe ser un objeto.`); return null; }
    if (Object.keys(consulta).some(k => !['producto', 'modelo', 'anio', 'configuracion', 'cantidad'].includes(k))) errores.push(`Consulta ${index + 1}: contiene campos no admitidos.`);
    const producto = normal(consulta.producto);
    if (!Object.hasOwn(PRODUCTOS, producto)) errores.push(`Consulta ${index + 1}: producto no admitido.`);
    const cantidad = consulta.cantidad === undefined ? 1 : consulta.cantidad;
    if (!Number.isInteger(cantidad) || cantidad < 1 || cantidad > 10) errores.push(`Consulta ${index + 1}: cantidad debe ser un entero entre 1 y 10.`);
    const result = { producto, cantidad };
    for (const campo of ['modelo', 'configuracion']) {
      if (consulta[campo] === undefined || consulta[campo] === null || consulta[campo] === '') continue;
      if (typeof consulta[campo] !== 'string' || limpiar(consulta[campo]).length > 160) errores.push(`Consulta ${index + 1}: ${campo} debe ser texto de hasta 160 caracteres.`);
      else if (limpiar(consulta[campo])) result[campo] = limpiar(consulta[campo]);
    }
    if (consulta.anio !== undefined && consulta.anio !== null && consulta.anio !== '') {
      const anio = typeof consulta.anio === 'string' && /^\d{4}$/.test(consulta.anio.trim()) ? Number(consulta.anio) : consulta.anio;
      if (!Number.isInteger(anio) || anio < 1900 || anio > 2100) errores.push(`Consulta ${index + 1}: anio debe ser un año de cuatro dígitos entre 1900 y 2100.`);
      else result.anio = anio;
    }
    return result;
  });
  if (errores.length) return { ok: false, entrada: null, errores, hojas: [] };
  return { ok: true, entrada: { consultas, modalidad, tipo_solicitud: tipo, metodo_pago }, errores: [], hojas: [...new Set(consultas.map(c => PRODUCTOS[c.producto]))] };
}

function centavos(valor) {
  if (typeof valor !== 'number' || !Number.isFinite(valor) || valor <= 0) return null;
  const n = Math.round(valor * 100);
  if (!Number.isSafeInteger(n) || Math.abs(valor * 100 - n) > 0.000001) return null;
  return n;
}

function medio(valor) {
  const v = normal(valor);
  if (/posnet|cuotas/.test(v)) return null;
  if (/\befectivo\b/.test(v)) return 'efectivo';
  if (/\btran(?:sf|f)/.test(v)) return 'transferencia';
  return null;
}

function configuracion(valor) {
  const v = palabras(valor);
  if (/^respaldo$/.test(v)) return 'respaldo';
  if (/^asiento$/.test(v)) return 'asiento';
  const n = v.match(/\b(\d+)\s+(?:plazas|asientos|butacas)\b/);
  if (n) return `${Number(n[1])} plazas`;
  if (/juego completo/.test(v)) return '5 plazas';
  if (/\bbutacon|\bbutacones|3 cuerpos|butaca entera/.test(v)) return 'butaca y butacón';
  if (v === 'delanteras' || v === 'dos asientos' || v === 'dos plazas') return '2 plazas';
  return v;
}

const MARCAS = {
  volkswagen: 'volkswagen', vw: 'volkswagen', renault: 'renault',
  peugeot: 'peugeot', citroen: 'citroen', fiat: 'fiat', ford: 'ford',
  chevrolet: 'chevrolet', audi: 'audi', bmw: 'bmw', nissan: 'nissan',
  jeep: 'jeep', honda: 'honda', toyota: 'toyota', hyundai: 'hyundai', hyunday: 'hyundai',
  mitsubishi: 'mitsubishi', chery: 'chery', cherry: 'chery',
  'mercedes benz': 'mercedes', 'mercedez benz': 'mercedes', mercedes: 'mercedes', mercedez: 'mercedes',
  suzuki: 'suzuki', kia: 'kia', chrysler: 'chrysler', 'land rover': 'land rover',
  dodge: 'dodge', 'alfa romeo': 'alfa romeo', subaru: 'subaru', iveco: 'iveco', ivecco: 'iveco',
  scania: 'scania', mini: 'mini', ram: 'ram', ssangyong: 'ssangyong',
};
const CLAVES_MARCAS = Object.keys(MARCAS).sort((a, b) => b.length - a.length);

function separarMarca(value) {
  const v = normal(value);
  for (const marca of CLAVES_MARCAS) {
    if (v === marca || v.startsWith(`${marca} `)) return { marca: MARCAS[marca], texto: v.slice(marca.length).trim() };
  }
  return { marca: null, texto: v };
}

function letraColumna(index) {
  let result = '';
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) result = String.fromCharCode(65 + (n - 1) % 26) + result;
  return result;
}

function leerHoja(sheet) {
  if (!objeto(sheet) || !Array.isArray(sheet.values) || sheet.values.some(row => !Array.isArray(row))) return null;
  const filas = [];
  let esquema = null;
  let marca = null;
  let tieneEncabezado = false;
  for (let index = 0; index < sheet.values.length; index++) {
    const row = sheet.values[index];
    const primera = palabras(row[0]);
    if (/lista de.*alternativas|^proximos articulos$/.test(primera)) { esquema = null; continue; }
    // Algunas secciones incluyen marca y modelo en su título (SsangYong Musso).
    // El encabezado siguiente establece que este texto es un separador, no tarifa.
    const siguiente = sheet.values[index + 1];
    const marcaSeccion = separarMarca(row[0]).marca;
    if (marcaSeccion && /marca y modelo/.test(palabras(siguiente?.[0])) && !row.slice(1).some(v => typeof v === 'number')) {
      marca = marcaSeccion;
      esquema = null;
      continue;
    }
    const esGrupos = /marca y modelo/.test(primera) || (primera === 'vehiculos' && row.some(c => palabras(c) === 'respaldo'));
    const esPlana = palabras(row[1]) === 'vehiculo modelo' || primera === 'producto servicio';
    if (esGrupos || esPlana) {
      esquema = { modelo: esPlana && primera !== 'producto servicio' ? 1 : 0, agrupado: esGrupos, grupos: {}, columnas: {} };
      let grupo = 'unidad';
      for (let col = 1; col < row.length; col++) {
        if (esGrupos && limpiar(row[col])) grupo = configuracion(row[col]);
        esquema.grupos[col] = { clave: grupo, rotulo: esGrupos ? limpiar(row[col]) : 'Unidad' };
        if (esGrupos && !limpiar(row[col])) esquema.grupos[col].rotulo = esquema.grupos[col - 1]?.rotulo || grupo;
        const m = medio(row[col]);
        if (esPlana && m) esquema.columnas[col] = m;
      }
      if (Object.keys(esquema.columnas).length) tieneEncabezado = true;
      continue;
    }
    // Una marca es separador; nunca se toma como un vehículo sin precio.
    if (esquema?.modelo !== 1 && Object.hasOwn(MARCAS, primera)) { marca = MARCAS[primera]; continue; }
    if (!esquema) continue;
    for (let col = 1; col < row.length; col++) {
      const m = medio(row[col]);
      if (m && esquema.agrupado && !esquema.grupos[col] && esquema.grupos[col - 1]) esquema.grupos[col] = { ...esquema.grupos[col - 1] };
      if (m && esquema.grupos[col]) { esquema.columnas[col] = m; tieneEncabezado = true; }
    }
    const modelo = limpiar(row[esquema.modelo]);
    if (!modelo || medio(modelo)) continue;
    const grupos = {};
    for (const [col, grupo] of Object.entries(esquema.grupos)) {
      if (Number(col) <= esquema.modelo) continue;
      grupos[grupo.clave] ??= { rotulo: grupo.rotulo, precios: {}, columnas: {} };
      const m = esquema.columnas[col];
      if (!m) continue;
      const valor = row[col];
      if (centavos(valor) !== null) grupos[grupo.clave].precios[m] = valor;
      grupos[grupo.clave].columnas[m] = { columna: letraColumna(Number(col)), celda: `${letraColumna(Number(col))}${index + 1}`, valor: valor ?? null };
    }
    filas.push({ modelo, marca: esquema.modelo === 1 ? separarMarca(row[0]).marca : marca, grupos,
      fuente: { sheetId: sheet.sheetId, hoja: sheet.title, fila: index + 1, modelo } });
  }
  return tieneEncabezado ? filas : null;
}

function anoCorto(value) {
  const n = Number(value);
  return String(value).length === 2 ? (n < 40 ? 2000 + n : 1900 + n) : n;
}

function describirModelo(value) {
  const separado = separarMarca(value);
  let texto = separado.texto;
  const rangos = [];
  // Una alternativa o una segunda cláusula de modelo puede tener sus propios
  // años. No se une ese alcance por OR con el rango del modelo solicitado.
  const clausulas = texto.split(/\s*\/\s*/);
  const tieneAnos = /\b(?:19|20)\d{2}\b|\b\d{2}\s*\+/.test(texto);
  let ambiguo = /\balternativas?\b/.test(texto) || (tieneAnos && clausulas.filter(c => /[a-z]/.test(c)).length > 1);
  const fronterasMensuales = [];
  const meses = 'enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre';
  // La API recibe año, no mes: en el año de una frontera mensual se pide confirmar.
  texto = texto.replace(/\bhasta\s+(\d{1,2})\/(\d{2}|(?:19|20)\d{2})\b/g, (_, mes, anio) => {
    if (Number(mes) < 1 || Number(mes) > 12) ambiguo = true;
    const y = anoCorto(anio); rangos.push({ min: 1900, max: y }); fronterasMensuales.push(y); return ' ';
  });
  texto = texto.replace(new RegExp(`\\b(hasta|desde)?\\s*(${meses})\\s+((?:19|20)\\d{2})\\s*(\\+|en adelante)?`, 'g'), (_, direccion, mes, anio, abierto) => {
    const y = Number(anio);
    if (direccion === 'hasta') rangos.push({ min: 1900, max: y });
    else if (direccion === 'desde' || abierto) rangos.push({ min: y, max: 2100 });
    else { rangos.push({ min: y, max: y }); ambiguo = true; }
    fronterasMensuales.push(y); return ' ';
  });
  texto = texto.replace(/\b(\d{1,2})\s*-\s*((?:19|20)\d{2})\s*\+/g, (_, mes, anio) => {
    const y = Number(anio);
    if (Number(mes) < 1 || Number(mes) > 12) ambiguo = true;
    rangos.push({ min: y, max: 2100 }); fronterasMensuales.push(y); return ' ';
  });
  // Las listas con barras son años puntuales, nunca intervalos interpolados.
  texto = texto.replace(/\b(?:19|20)\d{2}(?:\s*\/\s*(?:19|20)\d{2})+\b/g, match => {
    for (const y of match.match(/(?:19|20)\d{2}/g).map(Number)) rangos.push({ min: y, max: y });
    return ' ';
  });
  texto = texto.replace(/\b(?:19|20)\d{2}\s*\/\s*\d\b/g, () => { ambiguo = true; return ' '; });
  // Solo formatos de año presentes explícitamente; no se inventan generaciones.
  texto = texto.replace(/\b((?:19|20)\d{2}|\d{2})\s*(?:-|hasta|al|a)\s*((?:19|20)\d{2}|\d{2})\b/g, (match, desde, hasta, offset, original) => {
    // Renaul 9-11-12-18-19-21 enumera modelos; no años.
    if (/\d\s*[-/]\s*$/.test(original.slice(0, offset)) || /^\s*[-/]\s*\d/.test(original.slice(offset + match.length))) return match;
    const min = anoCorto(desde), max = anoCorto(hasta);
    if (min > max) { ambiguo = true; return ' '; }
    rangos.push({ min, max }); return ' ';
  });
  texto = texto.replace(/\b((?:19|20)\d{2})\s*-\s*actual\b/g, (_, anio) => { rangos.push({ min: Number(anio), max: 2100 }); return ' '; });
  texto = texto.replace(/\bhasta\s+((?:19|20)\d{2})\b/g, (_, anio) => { rangos.push({ min: 1900, max: Number(anio) }); return ' '; });
  texto = texto.replace(/\bdesde\s+((?:19|20)\d{2})\b/g, (_, anio) => { rangos.push({ min: Number(anio), max: 2100 }); return ' '; });
  texto = texto.replace(/\b((?:19|20)\d{2}|\d{2})\s*(?:\+|en adelante)/g, (_, anio) => { rangos.push({ min: anoCorto(anio), max: 2100 }); return ' '; });
  texto = texto.replace(/\+\s*((?:19|20)\d{2}|\d{2})\b/g, (_, anio) => { rangos.push({ min: anoCorto(anio), max: 2100 }); return ' '; });
  texto = texto.replace(/\b(?:19|20)\d{2}\s*-\s*(?=$|\))/g, () => { ambiguo = true; return ' '; });
  // Un número que por sí solo nombra el modelo (Peugeot 2008) no es un año.
  texto = texto.replace(/\b(?:19|20)\d{2}\b/g, (anio, offset, original) => {
    if (!palabras(original.slice(0, offset))) return anio;
    rangos.push({ min: Number(anio), max: Number(anio) }); return ' ';
  });
  return { marca: separado.marca, base: palabras(texto), rangos, ambiguo, fronterasMensuales };
}

const contiene = (texto, consulta) => !!consulta && (` ${texto} `).includes(` ${consulta} `);
function distancia(a, b) {
  let previa = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const actual = [i];
    for (let j = 1; j <= b.length; j++) actual[j] = Math.min(actual[j - 1] + 1, previa[j] + 1, previa[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    previa = actual;
  }
  return previa[b.length];
}

function evidencia(row, grupo) {
  const g = row.grupos[grupo];
  return { ...row.fuente, configuracion: g?.rotulo || grupo, columnas: g?.columnas || {}, regla_cuotas: REGLA_CUOTAS };
}

function opciones(filas) {
  return [...new Map(filas.map(row => [normal(row.modelo), { modelo: row.modelo }])).values()].slice(0, 12);
}

function resolver(consulta, filas, modalidad) {
  const item = { producto: consulta.producto, modelo: consulta.modelo || null, estado: 'requiere_aclaracion', precios: {}, cantidad: consulta.cantidad, fuentes: [] };
  const aclarar = (motivo, posibles = []) => ({ ...item, motivo, ...(posibles.length ? { opciones: posibles } : {}) });
  if (modalidad === 'envio' && (consulta.producto === 'tapiceria' || (consulta.producto === 'otros' && /\b(?:relleno|limpieza|techo|tapizado|tapiceria)\b/.test(palabras(consulta.modelo))))) {
    return { ...item, estado: 'sin_precio', motivo: 'Este servicio se realiza de forma presencial en CABA y no está disponible para envío.' };
  }
  if (consulta.producto !== 'cubrevolante' && !consulta.modelo) return aclarar(consulta.producto === 'otros' ? 'Confirmá el nombre del producto o servicio que querés consultar.' : 'Confirmá la marca y el modelo del vehículo.');
  if (consulta.producto === 'espuma' && !['asiento', 'respaldo'].includes(configuracion(consulta.configuracion))) return aclarar('Confirmá si necesitás espuma de asiento o de respaldo.', [{ configuracion: 'asiento' }, { configuracion: 'respaldo' }]);
  const busqueda = describirModelo(consulta.producto === 'cubrevolante' ? 'CUBRE VOLANTE' : consulta.modelo);
  const anoModelo = busqueda.rangos.length === 1 && busqueda.rangos[0].min === busqueda.rangos[0].max ? busqueda.rangos[0].min : undefined;
  if (consulta.anio && anoModelo && consulta.anio !== anoModelo) return aclarar('El año indicado no coincide con el año escrito en el modelo. Confirmá el año del vehículo.');
  const anio = consulta.anio || anoModelo;
  let candidatas = filas.filter(row => {
    const detalle = describirModelo(row.modelo);
    const marcaFila = detalle.marca || row.marca;
    return (!busqueda.marca || !marcaFila || marcaFila === busqueda.marca) && contiene(detalle.base, busqueda.base);
  });
  if (!candidatas.length) {
    const cercanas = busqueda.base.length >= 3 ? filas.filter(row => {
      const d = describirModelo(row.modelo);
      return (!busqueda.marca || !d.marca || busqueda.marca === d.marca) && d.base.split(' ').some(p => p.length >= 3 && distancia(busqueda.base, p) <= 1);
    }) : [];
    return { ...item, estado: cercanas.length ? 'requiere_aclaracion' : 'no_encontrado', motivo: cercanas.length ? 'No encontré una coincidencia exacta. Confirmá cuál de estas opciones corresponde.' : 'No encontré ese modelo o producto en la lista consultada.', ...(cercanas.length ? { opciones: opciones(cercanas) } : {}) };
  }
  const todasPorModelo = candidatas;
  if (anio) {
    candidatas = candidatas.filter(row => {
      const rangos = describirModelo(row.modelo).rangos;
      return !rangos.length || rangos.some(r => anio >= r.min && anio <= r.max);
    });
    if (!candidatas.length) return aclarar('El año indicado no está cubierto por las variantes publicadas.', opciones(todasPorModelo));
    // Una fila con años que cubre el del cliente es más específica que la fila del
    // mismo nombre sin años (DUSTER frente a DUSTER 2017+). Otros nombres no se descartan.
    const especificas = new Set(candidatas.filter(row => describirModelo(row.modelo).rangos.length).map(row => describirModelo(row.modelo).base));
    if (especificas.size) candidatas = candidatas.filter(row => { const d = describirModelo(row.modelo); return d.rangos.length > 0 || !especificas.has(d.base); });
  }
  const esAsiento = ASIENTOS.has(consulta.producto);
  const grupo = esAsiento ? configuracion(consulta.configuracion || '5 plazas') : consulta.producto === 'espuma' ? configuracion(consulta.configuracion) : 'unidad';
  if (!esAsiento && consulta.producto !== 'espuma' && consulta.configuracion) {
    const detalle = palabras(consulta.configuracion);
    const filtradas = candidatas.filter(row => contiene(palabras(row.modelo), detalle));
    if (!filtradas.length) return aclarar('La configuración indicada necesita confirmación para este producto.', opciones(candidatas));
    candidatas = filtradas;
  }
  if (!candidatas.some(row => Object.hasOwn(row.grupos, grupo))) {
    const disponibles = [...new Set(candidatas.flatMap(row => Object.keys(row.grupos).filter(g => Object.keys(row.grupos[g].precios).length)))];
    return aclarar('Confirmá la configuración entre las opciones disponibles para este modelo.', disponibles.map(configuracion => ({ configuracion })));
  }
  const grupos = new Map();
  for (const row of candidatas) {
    const precios = { ...(row.grupos[grupo]?.precios || {}) };
    if (modalidad === 'envio') delete precios.efectivo;
    // Excepción comercial explícita: cuotas usa la celda de transferencia,
    // incluso en Otros, donde POSNET tiene un importe diferente.
    if (precios.transferencia !== undefined) precios.cuotas = precios.transferencia;
    const key = JSON.stringify([normal(row.modelo), grupo, precios]);
    if (!grupos.has(key)) grupos.set(key, { row, precios, fuentes: [] });
    grupos.get(key).fuentes.push(evidencia(row, grupo));
  }
  item.fuentes = [...grupos.values()].flatMap(g => g.fuentes);
  if (grupos.size !== 1) {
    const conflicto = new Set(candidatas.map(row => normal(row.modelo))).size === 1;
    return aclarar(conflicto ? 'Hay importes distintos publicados para el mismo producto. Hay que confirmar el precio.' : 'Encontré más de una variante. Confirmá cuál corresponde a tu vehículo.', opciones(candidatas));
  }
  const elegido = [...grupos.values()][0];
  const descripcion = describirModelo(elegido.row.modelo);
  if (descripcion.ambiguo) return aclarar('La descripción de años está incompleta o es ambigua. Hay que confirmar la variante.', opciones(candidatas));
  if (descripcion.fronterasMensuales.includes(anio)) return aclarar('Hay más de una variante para ese año. Confirmá el mes o la versión del vehículo.', opciones(candidatas));
  if (!anio && descripcion.rangos.length) return aclarar('Confirmá el año del vehículo para esta variante publicada.', opciones(candidatas));
  const plazasFila = palabras(elegido.row.modelo).match(/\b(\d+)\s+(?:plazas|asientos|butacas)\b/);
  if (esAsiento && grupo === '5 plazas' && plazasFila && Number(plazasFila[1]) !== 5) return aclarar('La cantidad de plazas del modelo no coincide con la configuración de la tarifa. Hay que confirmarla antes de cotizar.', opciones(candidatas));
  const rotulo = elegido.row.grupos[grupo]?.rotulo || grupo;
  const result = { ...item, modelo: elegido.row.modelo, configuracion: rotulo, precios: elegido.precios, fuentes: elegido.fuentes, estado: Object.keys(elegido.precios).length ? 'cotizado' : 'sin_precio' };
  if (result.estado === 'sin_precio') result.motivo = 'La lista no tiene un precio numérico disponible para esta configuración y modalidad.';
  return result;
}

function dinero(value) {
  return '$' + value.toLocaleString('es-AR', { minimumFractionDigits: Number.isInteger(value) ? 0 : 2, maximumFractionDigits: 2 });
}

const CIERRE_COTIZACION = 'Quisieras aprovechar el valor en transferencia o en 3 cuotas sin interes?';

// Sólo presentación: conserva intactos modelo, fuente, rango y precios del resultado.
function modeloLegible(valor) {
  const siglas = new Set(['VW','BMW','BAIC','BYD','JAC','JMC','GWM','DFSK','MG','DS','RAM','GTI','GLI','GLX','GTS','GT','HDI','TDI','TSI','SUV','SW','HRV','CRV','AMG']);
  const enlaces = new Set(['de','del','con','sin','y','a','al','desde','hasta','en','para']);
  return textoPlano(valor).replace(/[\p{L}\p{N}]+/gu, (palabra, posicion) => {
    if (/\d/.test(palabra) || siglas.has(palabra.toUpperCase())) return palabra;
    if (palabra !== palabra.toUpperCase() && palabra !== palabra.toLowerCase()) return palabra;
    const baja = palabra.toLowerCase();
    return posicion > 0 && enlaces.has(baja) ? baja : baja.charAt(0).toUpperCase() + baja.slice(1);
  });
}

function descripcionNatural(item) {
  const modelo = modeloLegible(item.modelo);
  const para = modelo ? ' para ' + modelo : '';
  const cantidad = item.cantidad;
  if (['fundas','tipo tapizado'].includes(item.producto)) {
    const grupo = configuracion(item.configuracion);
    const completo = grupo === '5 plazas';
    const cobertura = /^\d+ plazas$/.test(grupo) ? grupo : modeloLegible(item.configuracion).toLowerCase();
    const juegos = cantidad === 1 ? 'El juego' + (completo ? ' completo' : '') : 'Los ' + cantidad + ' juegos' + (completo ? ' completos' : '');
    return juegos + ' de ' + ROTULOS[item.producto].toLowerCase() + para + (cobertura ? ' (' + cobertura + (cantidad > 1 ? ' cada uno' : '') + ')' : '');
  }
  if (item.producto === 'tapiceria') return (cantidad === 1 ? 'El trabajo de tapicería' : 'Los ' + cantidad + ' trabajos de tapicería') + para + (item.configuracion ? ' (' + modeloLegible(item.configuracion).toLowerCase() + ')' : '');
  const nombres = {
    alfombra: ['La alfombra termoformada', 'Las ' + cantidad + ' alfombras termoformadas'],
    'funda baul': ['La funda de baúl antiderrame', 'Las ' + cantidad + ' fundas de baúl antiderrame'],
    'cobertor caja': ['El cobertor de caja', 'Los ' + cantidad + ' cobertores de caja'],
    cubrevolante: ['El cubrevolante', 'Los ' + cantidad + ' cubrevolantes'],
    espuma: ['La espuma', 'Las ' + cantidad + ' espumas'],
  };
  if (item.producto === 'otros') return cantidad === 1 ? modelo : 'Las ' + cantidad + ' unidades de ' + modelo;
  const nombre = nombres[item.producto]?.[cantidad === 1 ? 0 : 1] || ROTULOS[item.producto];
  const pieza = item.producto === 'espuma' && item.configuracion ? ' de ' + modeloLegible(item.configuracion).toLowerCase() : '';
  return nombre + pieza + (item.producto === 'cubrevolante' ? '' : para);
}

function mensaje(items, totales, aclaraciones, pedido) {
  const metodo = pedido.metodo_pago;
  const rotulo = metodo === 'efectivo' ? ' en efectivo' : metodo === 'cuotas' ? ' en total, en 3 cuotas sin interés' : ' por transferencia';
  const hayCotizados = items.some(item => item.estado === 'cotizado');
  const completa = items.length > 0 && items.every(i => i.estado === 'cotizado' && centavos(i.precios[metodo]) !== null)
    && (pedido.tipo_solicitud !== 'combo' || centavos(totales?.[metodo]) !== null);
  const frases = items.map(item => {
    const titulo = ROTULOS[item.producto] + (item.modelo && item.producto !== 'cubrevolante' ? ' para ' + modeloLegible(item.modelo) : '');
    if (item.estado !== 'cotizado') {
      if (hayCotizados) return titulo + ': pendiente de confirmación.';
      const detalle = (item.opciones || []).map(o => textoPlano(o.modelo || o.configuracion)).filter(Boolean);
      return titulo + '\n' + item.motivo + (detalle.length ? '\nOpciones: ' + detalle.join('; ') + '.' : '');
    }
    const unitario = item.precios[metodo];
    const importe = item.subtotales?.[metodo] ?? unitario;
    const unidad = ['fundas','tipo tapizado'].includes(item.producto) ? 'juego' : item.producto === 'tapiceria' ? 'trabajo' : 'unidad';
    const detalle = item.cantidad > 1 ? (metodo === 'cuotas' ? ' (' : ' en total (') + dinero(unitario) + ' por ' + unidad + ')' : '';
    return descripcionNatural(item) + (item.cantidad > 1 ? ' salen ' : ' sale ') + dinero(importe) + rotulo + detalle + '.';
  });
  let bloques = frases;
  if (completa && pedido.tipo_solicitud === 'combo') {
    const productos = items.map((item, indice) => {
      const descripcion = descripcionNatural(item);
      return indice ? descripcion.replace(/^(El|La|Los|Las) /, palabra => palabra.toLowerCase()) : descripcion;
    });
    const juntos = productos.length > 1 ? productos.slice(0, -1).join(', ') + ' y ' + productos.at(-1) : productos[0];
    const plural = items.length > 1 || items[0].cantidad > 1;
    bloques = [juntos + (plural ? ' salen ' : ' sale ') + dinero(totales[metodo]) + rotulo + '.'];
  } else if (pedido.tipo_solicitud === 'comparacion') {
    bloques = [frases.join(' ')];
  }
  const notas = aclaraciones.filter(a => !items.some(i => i.motivo === a));
  if (notas.length) bloques.push(notas.join('\n'));
  if (completa && metodo === 'transferencia') bloques.push(CIERRE_COTIZACION);
  return bloques.join('\n\n') || null;
}

export function cotizar(entrada, sheets, consultadoEn) {
  const salida = { estado: 'entrada_invalida', items: [], totales: null, mensaje_cotizacion: null, aclaraciones: [], consultado_en: consultadoEn ?? null, pregunta_comercial_incluida: false };
  const validada = normalizarEntrada(entrada);
  if (!validada.ok) return { ...salida, aclaraciones: validada.errores };
  const pedido = validada.entrada;
  salida.metodo_pago = pedido.metodo_pago;
  if (pedido.metodo_pago === 'efectivo' && pedido.modalidad === 'envio') return { ...salida, estado: 'metodo_no_disponible', aclaraciones: ['El efectivo es solo para el taller de CABA. ¿Preferís venir al taller o mantener el envío?'] };
  if (['debito','otro'].includes(pedido.metodo_pago)) return { ...salida, estado: 'metodo_no_confirmado', aclaraciones: ['Ese medio de pago necesita confirmación de Candela.'] };
  if (!Array.isArray(sheets)) return { ...salida, estado: 'error_consulta', aclaraciones: ['No se pudo consultar la lista de precios.'] };
  const datos = new Map();
  for (const titulo of validada.hojas) {
    const coincidencias = sheets.filter(s => objeto(s) && normal(s.title) === normal(titulo));
    if (coincidencias.length !== 1) return { ...salida, estado: 'error_consulta', aclaraciones: ['No se pudo identificar una única hoja de precios para todos los productos solicitados.'] };
    const filas = leerHoja(coincidencias[0]);
    if (!filas) return { ...salida, estado: 'error_consulta', aclaraciones: ['No se pudo interpretar la lista de precios.'] };
    datos.set(titulo, filas);
  }
  const items = pedido.consultas.map(consulta => resolver(consulta, datos.get(PRODUCTOS[consulta.producto]), pedido.modalidad));
  for (const item of items) {
    if (item.estado === 'cotizado' && centavos(item.precios[pedido.metodo_pago]) === null) {
      item.estado = 'sin_precio';
      item.motivo = 'No encontré un valor ' + ({transferencia:'por transferencia',efectivo:'en efectivo',cuotas:'en cuotas'}[pedido.metodo_pago]) + ' confirmado para este producto.';
    }
    if (item.estado !== 'cotizado' || item.cantidad === 1) continue;
    const importes = Object.entries(item.precios).map(([m, valor]) => [m, centavos(valor) * item.cantidad]);
    if (importes.some(([, total]) => !Number.isSafeInteger(total))) return { ...salida, estado: 'error_consulta', aclaraciones: ['El importe no se puede calcular de forma segura.'] };
    item.subtotales = Object.fromEntries(importes.map(([m, total]) => [m, total / 100]));
  }
  const cotizados = items.filter(i => i.estado === 'cotizado').length;
  const estado = cotizados === items.length ? 'cotizado' : cotizados > 0 ? 'parcial' : items.some(i => i.estado === 'requiere_aclaracion') ? 'requiere_aclaracion' : 'no_disponible';
  let totales = null;
  if (pedido.tipo_solicitud === 'combo' && cotizados === items.length) {
    const comunes = MEDIOS.filter(m => items.every(item => centavos(item.precios[m]) !== null));
    const sumas = comunes.map(m => [m, items.reduce((suma, item) => suma + centavos(item.precios[m]) * item.cantidad, 0)]);
    if (sumas.some(([, total]) => !Number.isSafeInteger(total))) return { ...salida, estado: 'error_consulta', aclaraciones: ['El importe no se puede calcular de forma segura.'] };
    if (sumas.length) totales = Object.fromEntries(sumas.map(([m, total]) => [m, total / 100]));
  }
  const aclaraciones = [...new Set(items.map(i => i.motivo).filter(Boolean))];
  return { ...salida, estado, items, totales, aclaraciones, pregunta_comercial_incluida: estado === 'cotizado' && pedido.metodo_pago === 'transferencia', mensaje_cotizacion: mensaje(items, totales, aclaraciones, pedido) };
}
