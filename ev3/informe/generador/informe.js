const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
        BorderStyle, Footer, PageNumber, HeadingLevel, LevelFormat, ImageRun, PageBreak } = require('docx');

const FIG = process.argv[3];
const FONT = 'Arial';
const W = 9360;                                   // ancho útil (carta vertical, margen 1")
const NAVY = '1F3864', GREY = '595959';

/* ---------- helpers ---------- */
function runs(str, base = {}) {
  return str.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)/).filter(Boolean).map(t => {
    if (t.startsWith('**')) return new TextRun({ text: t.slice(2, -2), font: FONT, bold: true, ...base });
    if (t.startsWith('*') && t.endsWith('*') && t.length > 2) return new TextRun({ text: t.slice(1, -1), font: FONT, italics: true, ...base });
    if (t.startsWith('`')) return new TextRun({ text: t.slice(1, -1), font: 'Courier New', ...base, size: (base.size || 22) - 2 });
    return new TextRun({ text: t, font: FONT, ...base });
  });
}
const P = (s, o = {}) => new Paragraph({ children: runs(s, o.run), spacing: { after: 120, line: 276 }, alignment: o.align, ...o.p });
const H1 = (s, first) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: !!first, children: [new TextRun({ text: s, font: FONT })] });
const H2 = s => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: s, font: FONT })] });
const bullets = items => items.map(s => new Paragraph({ numbering: { reference: 'bul', level: 0 }, children: runs(s), spacing: { after: 60, line: 276 } }));
const thin = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF' };
const B = { top: thin, bottom: thin, left: thin, right: thin };

function table(headers, rows, widths, o = {}) {
  const sz = o.size || 19;
  const mk = (t, i, head) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA }, borders: B,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    shading: head ? { type: ShadingType.CLEAR, color: 'auto', fill: NAVY } : (o.fills && o.fills(i, t)) ? { type: ShadingType.CLEAR, color: 'auto', fill: o.fills(i, t) } : undefined,
    children: String(t).split('\n').map(line => new Paragraph({
      children: runs(line, head ? { size: sz, bold: true, color: 'FFFFFF' } : { size: sz }),
      alignment: (o.center || []).includes(i) ? AlignmentType.CENTER : AlignmentType.LEFT })),
  });
  return new Table({ width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, cantSplit: true, children: headers.map((h, i) => mk(h, i, true)) }),
           ...rows.map(r => new TableRow({ cantSplit: true, children: r.map((c, i) => mk(c, i, false)) }))] });
}
const gap = (n = 120) => new Paragraph({ spacing: { after: n }, children: [] });

function placeholder(title, detail) {
  const c = new TableCell({
    width: { size: W, type: WidthType.DXA },
    borders: { top: { style: BorderStyle.SINGLE, size: 8, color: 'E0A800' }, bottom: { style: BorderStyle.SINGLE, size: 8, color: 'E0A800' },
               left: { style: BorderStyle.SINGLE, size: 8, color: 'E0A800' }, right: { style: BorderStyle.SINGLE, size: 8, color: 'E0A800' } },
    shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'FFF4CC' }, margins: { top: 90, bottom: 90, left: 140, right: 140 },
    children: [new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: 'COMPLETAR · ' + title, font: FONT, bold: true, size: 20, color: '7A5A00' })] }),
               new Paragraph({ children: runs(detail, { size: 19, color: '5A4300' }) })],
  });
  return [new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ cantSplit: true, children: [c] })] }), gap(160)];
}

function code(lines) {
  return lines.map((l, i) => new Paragraph({
    keepLines: true, keepNext: i < lines.length - 1,
    shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'F3F3F1' }, spacing: { after: 0, line: 252 },
    indent: { left: 120, right: 120 },
    border: i === 0 ? { top: { style: BorderStyle.SINGLE, size: 4, color: 'D0D0CC', space: 4 } } : i === lines.length - 1 ? { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'D0D0CC', space: 4 } } : undefined,
    children: [new TextRun({ text: l === '' ? ' ' : l, font: 'Courier New', size: 17 })] })).concat([gap(140)]);
}

function pngSize(file) { const b = fs.readFileSync(file); return [b.readUInt32BE(16), b.readUInt32BE(20)]; }
function figure(file, widthIn, caption) {
  const fp = path.join(FIG, file), [w, h] = pngSize(fp), pw = Math.round(widthIn * 96), ph = Math.round(pw * h / w);
  return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80, after: 60 }, keepNext: true,
            children: [new ImageRun({ type: 'png', data: fs.readFileSync(fp), transformation: { width: pw, height: ph },
              altText: { title: caption, description: caption, name: file } })] }),
          new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: caption, font: FONT, size: 18, italics: true, color: GREY })] })];
}

/* ---------- contenido ---------- */
const C = [];
const add = (...x) => x.flat().forEach(e => C.push(e));

// Portada
add(
  new Paragraph({ spacing: { before: 900, after: 0 }, children: [new TextRun({ text: 'Duoc UC · Escuela de Informática y Telecomunicaciones', font: FONT, size: 22, color: GREY })] }),
  new Paragraph({ spacing: { before: 700, after: 120 }, children: [new TextRun({ text: 'Informe técnico parcial', font: FONT, size: 60, bold: true, color: NAVY })] }),
  new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: 'Evaluación Parcial N°3 · Explotación de datos NoSQL para el análisis organizacional', font: FONT, size: 28, color: NAVY })] }),
  new Paragraph({ spacing: { after: 600 }, children: [new TextRun({ text: 'Caso QuickTrack (Forma B)', font: FONT, size: 28, color: GREY })] }),
  table(['Dato', 'Detalle'], [
    ['Asignatura', 'BDY0101 · Base de Datos No Relacionales'],
    ['Integrantes', 'Alvaro Uribe · pregunta táctica\nNicolas Mansilla · pregunta ______\nGenesis Montero · pregunta ______'],
    ['Docente', 'German Barrientos'],
    ['Repositorio', 'https://github.com/Unknumb/quicktrack-nosql-ev2'],
    ['Fecha de entrega', '[dd/mm/aaaa]'],
  ], [2200, 7160], { size: 21 }),
  gap(300),
  new Paragraph({ children: runs('**Cómo leer este documento.** Las secciones completas corresponden a la pregunta **táctica** (Alvaro Uribe). Los recuadros amarillos **COMPLETAR** son los espacios para las otras dos preguntas del equipo. Antes de entregar, borren los recuadros y los textos entre corchetes, y exporten el documento a PDF.', { size: 20, color: GREY }) }),
);

// 1 ---------------------------------------------------------------------------------------
add(H1('1. Objetivos del proyecto', true), H2('1.1 Contexto y problema'),
  P('QuickTrack es una empresa de logística que ofrece servicios de entrega express a nivel nacional. En el último año implementó un sistema digital que registra, en una base de datos NoSQL, las órdenes de entrega, el seguimiento de paquetes, las valoraciones de los clientes, los tiempos de entrega y las rutas utilizadas.'),
  P('La gerencia busca analizar esos datos para **optimizar las rutas de entrega**, **identificar zonas críticas**, **medir la satisfacción del cliente** y **comprender los factores que afectan el cumplimiento de plazos**. El problema no es la falta de datos, sino que almacenarlos no basta: hay que decidir qué campos son útiles, cómo transformarlos y cómo presentarlos para que apoyen decisiones.'),
  H2('1.2 Objetivo general'),
  P('Aplicar técnicas de extracción, transformación y visualización de datos provenientes de una base de datos NoSQL en la nube, para generar un informe técnico y un dashboard que sustenten la toma de decisiones en el área logística y de atención al cliente de QuickTrack.'),
  H2('1.3 Objetivos específicos'),
  ...bullets([
    'Extraer los datos desde **Azure Cosmos DB for NoSQL** con **Azure Data Factory**, consultando al menos tres colecciones.',
    'Transformar los datos (aplanamiento, conversión de tipos, limpieza y campos derivados) y justificar cada decisión de selección de atributos con el marco **RICE**.',
    'Integrar los datos transformados en una herramienta de visualización y construir dashboards interactivos con indicadores clave (KPI).',
    'Responder tres preguntas de negocio de distinto tipo (táctica, estratégica y operacional) que apoyen decisiones logísticas.',
  ]),
  H2('1.4 Preguntas de negocio del equipo'),
  P('La actividad 3.1.1 clasifica los requerimientos de información según la decisión que respaldan: **tácticos** (procesos internos, seguimiento de indicadores), **estratégicos** (tendencias, comportamiento de clientes, optimización global) y **operacionales** (procesos diarios, alertas, disponibilidad inmediata). Cada integrante desarrolló una pregunta, con su tabla RICE y su dashboard.'),
  table(['Tipo', 'Pregunta', 'Responsable'], [
    ['Táctica', '¿Qué zonas de reparto y tramos de distancia concentran la mayor tasa de cancelación y el mayor ingreso perdido, y la distancia de la ruta explica esas cancelaciones, para decidir en qué rutas intervenir primero?', 'Alvaro Uribe'],
    ['[Estratégica / confirmar]', '[Completar con la pregunta del compañero/a]', '[Nicolas Mansilla o Genesis Montero]'],
    ['[Operacional / confirmar]', '[Completar con la pregunta del compañero/a]', '[Nicolas Mansilla o Genesis Montero]'],
  ], [1900, 5460, 2000]),
  gap(),
  H2('1.5 Alcance'),
  P('El enunciado menciona la identificación de zonas críticas de **retraso**. Al perfilar los datos se comprobó que no es posible medir retraso con ellos (sección 4.3 y sección 10). Por eso la pregunta táctica se construyó sobre **cancelación e ingreso perdido**, que sí tienen señal medible.'),
);

// 2 ---------------------------------------------------------------------------------------
add(H1('2. Descripción de la necesidad cubierta'), H2('2.1 Pregunta táctica: qué decisión respalda'),
  P('El requerimiento es **táctico**: lo usa la jefatura de operaciones para decidir **en qué zonas y rutas intervenir primero**, con un horizonte de semanas o meses. No busca una tendencia histórica (estratégico) ni una alerta del día (operacional).'),
  P('El análisis responde dos cosas: **dónde se concentran las cancelaciones y cuánto dinero se deja de facturar**, y si la **distancia** de la ruta explica ese comportamiento. Esta segunda parte pone a prueba una hipótesis habitual: "las rutas largas cancelan más".'),
  P('Siguiendo el análisis de requerimientos de la actividad 3.1.1, el requerimiento se precisó respondiendo tres preguntas, antes de extraer o transformar ningún dato:'),
  table(['Pregunta guía', 'Respuesta para la pregunta táctica'], [
    ['¿Qué decisión hay que respaldar?', 'En qué zonas y rutas intervenir primero para reducir cancelaciones y pérdida de ingresos, con un horizonte de semanas o meses.'],
    ['¿Qué datos tenemos hoy?', 'Cinco colecciones en Cosmos DB (`clientes`, `rutas`, `ordenes_entrega`, `seguimiento`, `valoraciones`), de las cuales esta pregunta usa tres: `ordenes_entrega` (estado, total, ruta), `rutas` (zona, distancia) y `seguimiento` (historial de eventos, solo para perfilar su calidad).'],
    ['¿Qué patrón buscamos?', 'Zonas y tramos de distancia donde se concentran la cancelación y el ingreso perdido, y si la cancelación aumenta a medida que la ruta es más larga.'],
  ], [2800, 6560], { size: 19 }),
  gap(),
  H2('2.2 Resultado principal'),
  P('Sobre las 100 órdenes de la muestra, 23 fueron canceladas (**23,0 %**) y el ingreso perdido asciende a **$2.672.017**.'),
  table(['Zona', 'Órdenes', '% cancelación', 'Ingreso perdido', '¿Zona crítica?'], [
    ['Centro', '17', '47,1 %', '$1.111.187', 'Sí'],
    ['Norte', '22', '36,4 %', '$810.247', 'Sí'],
    ['Sur', '13', '23,1 %', '$314.579', 'Marginal (supera el promedio por 0,08 puntos)'],
    ['Poniente', '22', '9,1 %', '$231.836', 'No'],
    ['Oriente', '26', '7,7 %', '$204.169', 'No'],
  ], [1500, 1200, 1700, 1900, 3060], { center: [1, 2, 3] }),
  gap(),
  ...bullets([
    '**Centro y Norte concentran 16 de las 23 cancelaciones** (70 %) y el 72 % del ingreso perdido.',
    '**La distancia no explica la cancelación.** Por tramo de distancia, la cancelación es 28,6 % (corta, menos de 500 km), 17,6 % (media), 31,0 % (larga) y 15,2 % (muy larga, 1.500 km o más). No hay patrón creciente.',
  ]),
  H2('2.3 Decisión que respalda'),
  P('El resultado sugiere **priorizar la revisión operativa de Centro y Norte** y **no justificar la intervención por "ruta larga"**, porque la distancia no discrimina. Los datos disponibles no incluyen el motivo de cancelación, por lo que la causa dentro de cada zona queda como la siguiente pregunta a investigar. Con solo 100 órdenes, estas cifras deben leerse como una señal para priorizar, no como una conclusión definitiva.'),
  H2('2.4 Alineación con el objetivo del caso'),
  P('La pregunta se alinea con dos objetivos de la gerencia: **identificar zonas críticas de reparto** y **optimizar las rutas de entrega**.'),
  H2('2.5 Resumen del proceso de punta a punta (caso integrador)'),
  P('Siguiendo el formato del caso integrador de la actividad 3.1.1, la tabla resume cómo se aplicó cada etapa a esta pregunta. El detalle de cada etapa está en las secciones 3 a 8.'),
  table(['1. Requerimiento', '2. Selección (RICE)', '3. Transformación', '4. Limpieza', '5. Carga'], [[
    '**Táctico:** ¿qué zonas y tramos de distancia concentran la cancelación y el ingreso perdido, y la distancia lo explica?',
    '**Conserva:** `total`, `ruta_id`, `zona`, `estado` y `distancia_km` (solo por tramos).\n**Descarta:** tiempo de ciclo, último evento del historial, ciudades, `fecha_envio` y `medio_pago`.',
    'Aplana `historial` con `JOIN … IN` (100 documentos pasan a 302 filas). Deriva `cancelada`, `ingreso_perdido` y `tramo_distancia`.',
    '0 duplicados, 0 nulos y 0 órdenes huérfanas. Se normaliza el texto de zona y estado.',
    'Transformación en Python, CSV sin decimales como archivo intermedio, y modelo semántico y dashboard en Power BI.',
  ]], [1750, 2250, 2000, 1750, 1610], { size: 17 }),
  gap(80),
  P('**Resultado:** Centro y Norte concentran 16 de las 23 cancelaciones y el 72 % del ingreso perdido, y la distancia de la ruta no explica la cancelación. Con este resultado, la jefatura de operaciones decide en qué zonas revisar primero la operación.'),
  ...placeholder('Necesidad cubierta por las otras preguntas', 'Para cada pregunta (estratégica y operacional): qué decisión respalda, quién la usa, las tres preguntas guía (decisión, datos, patrón), el resultado principal y cómo se alinea con el objetivo del caso. Agreguen también su propia fila de la tabla del caso integrador (sección 2.5), con las mismas cinco etapas.'),
);

// 3 ---------------------------------------------------------------------------------------
add(H1('3. Proceso de extracción de datos'), H2('3.1 Fuente de datos'),
  P('Los datos se extrajeron desde **Azure Cosmos DB for NoSQL**, la misma API usada en el LAB 3.1.2, con **Azure Data Factory (ADF)** como herramienta de extracción. El enunciado permite Azure Data Factory cuando se trabaja en un entorno 100 % cloud.'),
  table(['Elemento', 'Configuración'], [
    ['Servicio', 'Azure Cosmos DB for NoSQL'],
    ['Modo de capacidad', 'Serverless (se paga por consulta; adecuado para 500 documentos pequeños)'],
    ['Región', 'Brazil South (Cosmos DB, Blob Storage y Integration Runtime de ADF)'],
    ['Base de datos', '`quicktrack`'],
    ['Contenedores', '`clientes`, `rutas`, `ordenes_entrega`, `seguimiento`, `valoraciones` (100 documentos cada uno)'],
    ['Destino de la extracción', 'Azure Blob Storage, contenedor `salida-etl`'],
  ], [2600, 6760]),
  gap(),
  H2('3.2 Carga de los datos de QuickTrack en Cosmos DB'),
  P('Los cinco archivos JSON del anexo Forma B (en formato MongoDB) se cargaron con el script `cargar_cosmos.py`, que usa el SDK `azure-cosmos`. Cosmos DB for NoSQL exige que cada documento tenga un campo `id` de tipo texto, mientras que los datos originales traen `_id`; el script copia `_id` en `id` y conserva `_id` para trazabilidad. La carga es idempotente (`upsert`), por lo que puede repetirse sin duplicar documentos.'),
  table(['Contenedor', 'Documentos', 'Clave de partición'], [
    ['clientes', '100', '/pais'], ['rutas', '100', '/zona'], ['ordenes_entrega', '100', '/ruta_id'],
    ['seguimiento', '100', '/orden_id'], ['valoraciones', '100', '/orden_id'],
  ], [3600, 2200, 3560], { center: [1] }),
  P('Cada contenedor se verificó con un conteo (`SELECT VALUE COUNT(1) FROM c`) que devolvió 100 documentos. Con este volumen la clave de partición no condiciona el rendimiento; se eligió el campo por el que cada colección se filtra o se cruza con más frecuencia.', { p: { spacing: { before: 120, after: 120 } } }),
  H2('3.3 Pipeline de Azure Data Factory'),
  table(['Componente', 'Nombre', 'Función'], [
    ['Linked service (origen)', '`LS_CosmosDB_QuickTrack`', 'Conexión a Cosmos DB, base `quicktrack`'],
    ['Linked service (destino)', '`LS_Storage_Analitica`', 'Conexión a Blob Storage'],
    ['Datasets de origen', '`DS_Cosmos_Ordenes`, `DS_Cosmos_Rutas`, `DS_Cosmos_Seguimiento`', 'Contenedores `ordenes_entrega`, `rutas`, `seguimiento`'],
    ['Datasets de destino', '`DS_Blob_OrdenesPlanas`, `DS_Blob_Rutas`, `DS_Blob_SeguimientoEventos`', 'JSON en `salida-etl`'],
    ['Pipeline', '`PL_ETL_QuickTrack_Tactico`', '3 actividades *Copy data* en paralelo'],
  ], [2300, 3700, 3360]),
  gap(),
  H2('3.4 Consultas de extracción'),
  P('En cada actividad *Copy data* la opción *Use query* se configuró en *Query*, de modo que el filtrado y la proyección ocurren **en el origen**, antes de mover los datos por la red.'),
  ...code([
    '-- Copiar_Ordenes  (100 filas)',
    'SELECT c.id, c.cliente_id, c.ruta_id, c.fecha_envio, c.estado, c.medio_pago, c.total',
    'FROM c',
    '',
    '-- Copiar_Rutas  (100 filas)',
    'SELECT c.id, c.zona, c.ciudad_origen, c.ciudad_destino, c.distancia_km',
    'FROM c',
    '',
    '-- Copiar_Seguimiento_Eventos  (302 filas: aplana el arreglo historial)',
    'SELECT s.orden_id, h.estado AS estado_evento, h.fecha AS fecha_evento',
    'FROM s',
    'JOIN h IN s.historial',
  ]),
  ...bullets([
    '**Proyección:** se extraen solo los campos necesarios, no el documento completo.',
    '**Aplanamiento de una estructura anidada:** `JOIN h IN s.historial` convierte el arreglo `historial` en una fila por evento. Los 100 documentos de `seguimiento` producen 302 filas.',
    '**Tres colecciones consultadas:** `ordenes_entrega`, `rutas` y `seguimiento`.',
  ]),
  gap(60),
  H2('3.5 Resultados de la ejecución'),
  P('El pipeline se ejecutó con *Add trigger → Trigger now*. Las tres actividades terminaron en estado **Correcto** y las filas leídas coinciden con las escritas:'),
  table(['Actividad', 'Filas leídas', 'Filas escritas', 'Duración', 'Estado'], [
    ['`Copiar_Ordenes`', '100', '100', '14 s', 'Correcto'],
    ['`Copiar_Rutas`', '100', '100', '15 s', 'Correcto'],
    ['`Copiar_Seguimiento_Eventos`', '302', '302', '13 s', 'Correcto'],
  ], [3500, 1500, 1600, 1300, 1460], { center: [1, 2, 3, 4] }),
  gap(),
  ...figure('fig_adf_ordenes.png', 6.0, 'Figura 1. Monitor de ADF: actividad Copiar_Ordenes (100 filas leídas y escritas).'),
  ...figure('fig_adf_rutas.png', 6.0, 'Figura 2. Monitor de ADF: actividad Copiar_Rutas (100 filas leídas y escritas).'),
  ...figure('fig_adf_seguimiento.png', 6.0, 'Figura 3. Monitor de ADF: actividad Copiar_Seguimiento_Eventos (302 filas, tras aplanar el historial).'),
  ...placeholder('Extracción de las otras preguntas', 'Agreguen las consultas SQL de cada compañero/a (por ejemplo, sobre `clientes` o `valoraciones`), con su actividad *Copy data*, su captura de Monitor y los conteos de filas. Si amplían el pipeline, actualicen la tabla de la sección 3.3.'),
);

// 4 ---------------------------------------------------------------------------------------
add(H1('4. Transformación y documentación del proceso'), H2('4.1 Selección de atributos con RICE'),
  P('Antes de transformar se decidió qué campos conservar con el marco **RICE** (Reach, Impact, Confidence, Effort): `Puntaje = (R × I × C) ÷ E`. Regla de decisión: **≥ 1 conservar · entre 0,5 y 1 evaluar · < 0,5 descartar**. Las cifras de evidencia se midieron sobre los datos; Impact y Confidence son criterio razonado, justificado con esa evidencia.'),
  table(['Atributo', 'R', 'I', 'C', 'E', 'Puntaje', 'Decisión', 'Evidencia'], [
    ['`ordenes.total`', '1,0', '3', '1,0', '1', '3,00', 'Conservar', '100/100, numérico, sin nulos. Base del ingreso perdido.'],
    ['`ordenes.ruta_id`', '1,0', '2', '1,0', '1', '2,00', 'Conservar', '100/100 órdenes con ruta válida (0 huérfanas). Clave de cruce.'],
    ['`ruta.zona`', '1,0', '3', '0,8', '1', '2,40', 'Conservar', '5 valores limpios. C = 0,8: la zona no coincide con la geografía origen→destino.'],
    ['`ordenes.estado`', '1,0', '3', '0,7', '1', '2,10', 'Conservar', '4 valores, sin nulos. C = 0,7: coincide con el último evento del historial en solo 19/100 órdenes.'],
    ['`ruta.distancia_km`', '1,0', '2', '0,4', '1', '0,80', 'Evaluar', 'Se usa solo por tramos. Un mismo par origen→destino aparece con 114 a 1.946 km.'],
    ['`historial[].fecha` (tiempo de ciclo)', '1,0', '3', '0,3', '3', '0,30', 'Descartar', 'Brecha de 2 días en 202/202 pares: no distingue zonas.'],
    ['`historial[].estado` (último evento)', '1,0', '2', '0,3', '2', '0,30', 'Descartar', '8 órdenes "Cancelado" con evento "Entregado".'],
    ['`ciudad_origen` / `ciudad_destino`', '1,0', '1', '0,4', '1', '0,40', 'Descartar', '24 pares únicos en 100 rutas; 23 repetidos en más de una zona.'],
    ['`ordenes.fecha_envio`', '1,0', '0,5', '0,5', '1', '0,25', 'Descartar', 'No es dimensión de esta pregunta; 88/100 envíos anteriores al registro del cliente.'],
    ['`ordenes.medio_pago`', '1,0', '0,25', '1,0', '1', '0,25', 'Descartar', 'Dato limpio, pero no responde esta pregunta.'],
  ], [1900, 480, 480, 480, 480, 800, 1050, 3690], { size: 16, center: [1, 2, 3, 4, 5, 6],
    fills: (i, t) => i === 6 ? ({ Conservar: 'E2F0D9', Evaluar: 'FFF2CC', Descartar: 'F2DCDB' })[t] : undefined }),
  gap(),
  H2('4.2 Transformaciones aplicadas'),
  P('Los tipos de transformación siguen la clasificación vista en la actividad 3.1.1. Cada una se justifica por su utilidad para el objetivo del análisis.'),
  table(['#', 'Tipo', 'Qué se hizo', 'Por qué', 'Dónde'], [
    ['1', 'Proyección', 'Se extraen solo los campos que RICE conserva, más las claves de cruce.', 'Reduce volumen y evita transformar campos sin valor.', 'ADF'],
    ['2', 'Aplanamiento', '`JOIN h IN s.historial`: 100 documentos pasan a 302 filas, una por evento.', 'El historial es un arreglo anidado; se necesita una fila por evento para medir la brecha entre eventos.', 'ADF'],
    ['3', 'Conversión de tipos', '`total` y `distancia_km` a numérico; fechas a fecha-hora.', 'Permite sumar el ingreso perdido y calcular diferencias de fechas.', 'Python'],
    ['4', 'Normalización de texto', '`strip()` y mayúscula inicial en zona y ciudades; `strip()` en estado.', 'Evita que "Centro " y "Centro" cuenten como zonas distintas.', 'Python'],
    ['5', 'Limpieza', 'Se eliminan duplicados por `id`; se revisan nulos e integridad referencial.', 'Evita KPI sesgados por registros repetidos o huérfanos.', 'Python'],
    ['6', 'Campos derivados', '`cancelada` (0/1), `ingreso_perdido` y `tramo_distancia` (4 tramos).', 'Son la base aditiva de los cuatro KPI.', 'Python'],
    ['7', 'Consolidación', 'Se une `ordenes` con `rutas` en una tabla plana (1 fila por orden).', 'El dashboard necesita zona y distancia junto a cada orden.', 'Python'],
    ['8', 'Adaptación a Power BI', 'Montos en centavos enteros (`total_centavos`, `ingreso_perdido_centavos`) y `distancia_km` redondeada, en un CSV aparte para Power BI.', 'Con configuración regional chilena (es-CL), Power BI lee el punto decimal como separador de miles y multiplicaba los montos (ver 4.3).', 'Python'],
  ], [360, 1500, 3000, 3300, 1200], { size: 18, center: [0] }),
  gap(),
  ...code([
    'f["cancelada"] = (f["estado"] == "Cancelado").astype(int)',
    'f["ingreso_perdido"] = f["total"].where(f["cancelada"] == 1, 0.0)',
    '# tramos: corta, media, larga, muy larga',
    'f["tramo_distancia"] = pd.cut(f["distancia_km"], [0, 500, 1000, 1500, float("inf")],',
    '                             labels=TRAMOS, right=False)',
    '# CSV para Power BI: montos en centavos enteros (sin decimales)',
    'pbi["total_centavos"] = (pbi.pop("total") * 100).round().astype("int64")',
    'pbi["ingreso_perdido_centavos"] = (pbi.pop("ingreso_perdido") * 100).round().astype("int64")',
  ]),
  H2('4.3 Evidencia de calidad de los datos'),
  P('El script `transformar_tactico.py` genera `calidad_datos.txt` con la mayoría de estas verificaciones, que justifican varias decisiones de la tabla RICE. La última surgió al cargar los datos en Power BI:'),
  table(['Verificación', 'Resultado', 'Decisión'], [
    ['Duplicados por `id` (órdenes y rutas)', '0', 'Sin acción'],
    ['Nulos en `id`, `ruta_id`, `estado`, `total`', '0', 'Sin acción'],
    ['Órdenes sin ruta válida / sin seguimiento', '0 / 0', 'Se integran las 100 órdenes'],
    ['Brecha entre eventos consecutivos del historial', '2 días en 202 de 202 pares', 'Tiempo de ciclo descartado: no distingue zonas'],
    ['Órdenes "Cancelado" cuyo historial llega a "Entregado"', '8', 'Se usa el estado de la orden como fuente'],
    ['Estado de la orden = último evento del historial', '19 de 100', 'Se usa el estado de la orden como fuente'],
    ['Pares origen→destino en `rutas`', '24 únicos en 100 rutas; 23 en más de una zona y con diferencias de distancia > 200 km', 'Distancia solo por tramos; sin etiqueta de ruta'],
    ['Lectura del CSV en Power BI con configuración es-CL', 'La suma de `ingreso_perdido` daba 236.146.506 en vez de 2.672.017: el punto decimal se leyó como separador de miles', 'CSV sin decimales: montos en centavos enteros; `Ingreso Perdido` = suma ÷ 100'],
  ], [3700, 2700, 2960], { size: 18 }),
  gap(),
  H2('4.4 ETL frente a ELT'),
  P('En ETL la transformación ocurre **fuera del motor NoSQL**, antes de cargar; en ELT ocurre **dentro del motor** o con herramientas sobre él, después de cargar. El flujo de este proyecto es **mixto**, con predominio de ETL:'),
  table(['Etapa', 'Dónde se transforma', 'Estilo', 'Qué se hace'], [
    ['Extracción con ADF', 'Dentro de Cosmos DB, mediante consultas SQL', 'ELT', 'Proyección de campos y aplanamiento del historial (`JOIN … IN`). El PPT describe este caso como ELT: los datos se transforman con consultas SQL de Cosmos.'],
    ['Transformación en Python', 'Fuera del motor, con pandas', 'ETL', 'Limpieza, conversión de tipos, unión de colecciones y campos derivados, antes de cargar el resultado en el dashboard. Es el ejemplo ETL del PPT: un script Python con pandas que limpia y luego carga.'],
  ], [1900, 2300, 900, 4260], { size: 18, center: [2] }),
  gap(80),
  P('Se combinaron porque cada paso conviene en un lugar distinto: la proyección y el aplanamiento en el origen reducen los datos que viajan por la red, y la limpieza y los campos derivados se hacen en Python para tener control total de las reglas y poder documentarlas. El volumen es pequeño (500 documentos), por lo que cualquiera de los dos estilos habría sido suficiente.'),
  ...placeholder('Transformaciones de las otras preguntas', 'Para cada pregunta: su tabla RICE completa (puede ser una tabla por integrante), las transformaciones aplicadas con su justificación, y la evidencia de calidad de los campos que usan.'),
);

// 5 ---------------------------------------------------------------------------------------
add(H1('5. Selección e integración en la herramienta de visualización'), H2('5.1 Herramienta elegida y justificación'),
  P('Para esta pregunta se usó **Power BI en su versión en línea (Power BI Service)**, con la cuenta institucional de Duoc UC. Se trabajó desde el navegador porque Power BI Desktop no está disponible en macOS.'),
  table(['Característica técnica', 'Cómo responde al requerimiento de análisis'], [
    ['1. Modelo semántico y medidas DAX con contexto de filtro', 'Los KPI se definen una vez como medidas y se recalculan según los filtros activos. Por ejemplo, `Zonas Criticas` usa `ALL`, `FILTER` y `SUMX` para comparar cada zona con el promedio global.'],
    ['2. Interactividad entre visuales', 'Las segmentaciones de zona y de tramo filtran a la vez las tarjetas, los gráficos y la matriz, lo que permite explorar combinaciones, por ejemplo solo Centro.'],
    ['3. Formato condicional por regla', 'El color de las columnas del gráfico ① depende de la medida `Zona Critica` (azul si la zona supera el promedio, gris si no), y la matriz ② usa un degradado de un solo tono según el % de cancelación.'],
    ['4. Validación de las medidas en la propia herramienta', 'La vista de consultas DAX permite ejecutar consultas contra el modelo y contrastar cada medida con los valores calculados en la transformación (sección 8.2).'],
  ], [3000, 6360], { size: 19 }),
  gap(60),
  P('**Limitación:** la tabla se cargó desde un archivo, por lo que los datos no se actualizan solos: para refrescarlos hay que volver a cargar el CSV. La mejora natural, conectar Power BI a Azure Blob Storage con actualización programada, se describe en la sección 8.3.'),
  H2('5.2 Método de conexión y proceso de carga'),
  P('Se usó un **archivo intermedio**: los tres JSON que deja ADF en Blob Storage se descargan, se transforman con Python y producen `out/powerbi/tactico_ordenes.csv`. Ese CSV se cargó en Power BI con *Crear → Cargar un archivo*, lo que generó el modelo semántico con la tabla `tactico_ordenes`.'),
  ...bullets([
    '**1.** Transformar los datos de ADF con Python y generar el CSV para Power BI.',
    '**2.** Cargar el CSV en Power BI Service (tabla `tactico_ordenes`, 100 filas).',
    '**3.** Crear las 8 medidas DAX en la vista de modelo (sección 6.2) y darles formato.',
    '**4.** Crear el informe: título, 2 segmentaciones, 4 tarjetas, 3 gráficos y 1 matriz.',
  ]),
  ...code([
    '# JSON de ADF -> out/powerbi/tactico_ordenes.csv',
    'python transformar_tactico.py --entrada ./adf_salida',
  ]),
  P('**Decisión de integración:** el CSV para Power BI no lleva decimales. Con la configuración regional chilena, Power BI interpretaba el punto decimal como separador de miles y el ingreso perdido sumaba 236.146.506 en lugar de 2.672.017. Por eso los montos se entregan en centavos enteros y la medida `Ingreso Perdido` divide por 100.'),
  H2('5.3 Integridad de la carga'),
  table(['Origen', 'Registros extraídos', 'Resultado en el modelo'], [
    ['`ordenes_entrega`', '100', '100 filas en `tactico_ordenes`: el 100 % de las órdenes llega al dashboard (las órdenes por zona suman 17 + 22 + 13 + 22 + 26 = 100)'],
    ['`rutas`', '100 (64 usadas por alguna orden)', 'Zona y distancia unidas a cada orden; 0 órdenes sin ruta'],
    ['`seguimiento` (aplanado)', '302 eventos', 'Resumido por orden para el perfilado de calidad; no entra al modelo (RICE)'],
  ], [2600, 2800, 3960], { size: 19 }),
  gap(),
  ...placeholder('Herramienta de las otras preguntas', 'Si sus dashboards usan otra herramienta (Tableau Public, Looker Studio u otra) o Power BI Desktop, indiquen cuál y justifíquenla con cuatro características técnicas, igual que en la tabla de la sección 5.1. Expliquen también cómo conectaron los datos.'),
);

// 6 ---------------------------------------------------------------------------------------
add(H1('6. Modelo de datos del dashboard'), H2('6.1 Tabla del modelo'),
  P('El modelo es **una sola tabla plana**, `tactico_ordenes`, con **una fila por orden**. Se aplanó antes de cargar para que la herramienta de visualización no tenga que resolver relaciones ni listas anidadas, y para que todos los KPI salgan de columnas aditivas (`cancelada` e `ingreso_perdido_centavos`).'),
  table(['Campo', 'Tipo', 'Origen', 'Descripción'], [
    ['`orden_id`', 'Texto', '`ordenes_entrega.id`', 'Identificador de la orden'],
    ['`estado`', 'Texto', '`ordenes_entrega.estado`', 'En preparación, En tránsito, Entregado o Cancelado'],
    ['`cancelada`', 'Entero (0/1)', 'Derivado de `estado`', '1 si la orden está cancelada'],
    ['`total_centavos`', 'Entero', '`ordenes_entrega.total` × 100', 'Valor de la orden, en centavos de peso'],
    ['`ingreso_perdido_centavos`', 'Entero', 'Derivado de `total` y `cancelada`', '`total_centavos` si la orden está cancelada; 0 en otro caso'],
    ['`ruta_id`', 'Texto', '`ordenes_entrega.ruta_id`', 'Clave de la ruta (permite revisar rutas puntuales)'],
    ['`zona`', 'Texto', '`rutas.zona`', 'Norte, Centro, Sur, Oriente o Poniente'],
    ['`distancia_km`', 'Entero', '`rutas.distancia_km`, redondeada', 'Distancia declarada de la ruta, en km enteros'],
    ['`tramo_distancia`', 'Texto ordenado', 'Derivado de `distancia_km`', 'Corta (<500), media (500-999), larga (1.000-1.499), muy larga (≥1.500 km); el prefijo numérico mantiene el orden'],
  ], [2300, 1300, 2700, 3060], { size: 18 }),
  gap(),
  H2('6.2 Medidas DAX'),
  P('Los KPI y los gráficos se calculan con **8 medidas DAX** definidas sobre esa tabla. Cada una usa a las anteriores por nombre, por lo que el orden de creación importa.'),
  table(['Medida', 'Fórmula DAX', 'Uso'], [
    ['`Ordenes`', '`COUNTROWS ( tactico_ordenes )`', 'Número de órdenes'],
    ['`Canceladas`', '`SUM ( tactico_ordenes[cancelada] )`', 'Órdenes canceladas'],
    ['`Pct Cancelacion`', '`DIVIDE ( [Canceladas], [Ordenes] )`', 'KPI 1; gráficos ①, ② y ④'],
    ['`Ingreso Perdido`', '`SUM ( tactico_ordenes[ingreso_perdido_centavos] ) / 100`', 'KPI 2; gráfico ③'],
    ['`Pct Cancelacion Global`', '`CALCULATE ( [Pct Cancelacion], ALL ( tactico_ordenes ) )`', 'Línea de promedio global'],
    ['`Zona Critica`', '`IF ( [Pct Cancelacion] > [Pct Cancelacion Global], 1, 0 )`', 'Color del gráfico ①'],
    ['`Zonas Criticas`', '`SUMX ( VALUES ( tactico_ordenes[zona] ), [Zona Critica] )`', 'KPI 3'],
    ['`Pct Ingreso Perdido Zonas Criticas`', '`DIVIDE ( CALCULATE ( [Ingreso Perdido], FILTER ( VALUES ( tactico_ordenes[zona] ), [Zona Critica] = 1 ) ), CALCULATE ( [Ingreso Perdido], ALL ( tactico_ordenes ) ) )`', 'KPI 4'],
  ], [2400, 4960, 2000], { size: 16 }),
  gap(),
  ...figure('fig_pbi_modelo.png', 6.0, 'Figura 4. Vista de modelo de Power BI: la tabla tactico_ordenes con sus 9 columnas y las 8 medidas.'),
  ...placeholder('Modelo de datos de las otras preguntas', 'Describan la tabla o tablas que usa cada dashboard: campos, tipos, origen y cómo se relacionan, y las medidas o cálculos de sus KPI. Expliquen por qué estructuraron el modelo de esa manera.'),
);

// 7 ---------------------------------------------------------------------------------------
add(H1('7. Diseño del dashboard y visualizaciones'),
  P('La Figura 5 muestra el dashboard final de la pregunta táctica, construido en Power BI: el título y la pregunta arriba, una línea de lectura para el jefe de operaciones, dos segmentaciones (zona y tramo de distancia), cuatro tarjetas de KPI y cuatro visuales de análisis.'),
  ...figure('fig_pbi_dashboard.png', 6.5, 'Figura 5. Dashboard táctico de QuickTrack en Power BI, sin filtros aplicados.'),
  H2('7.1 Elementos visuales y justificación'),
  table(['Elemento', 'Tipo de visual', 'Pregunta que responde', 'Por qué ese tipo'], [
    ['4 tarjetas KPI', 'Tarjeta', '¿Cuán grave es el problema?', 'Un número aislado se lee mejor como tarjeta que como gráfico de una sola barra.'],
    ['① Cancelación por zona vs. global', 'Columnas con línea de promedio', '¿Qué zonas superan el promedio global?', 'Compara pocas categorías contra un umbral. Azul: zonas críticas; gris: el resto.'],
    ['② % de cancelación por zona y tramo', 'Matriz con degradado de color', '¿Dónde se concentra el problema?', 'Cruza dos variables categóricas y agrega totales; el degradado de un solo tono muestra la intensidad.'],
    ['③ Ingreso perdido por zona', 'Barras horizontales ordenadas', '¿Dónde se pierde más dinero?', 'Pasa de porcentaje a pesos; el orden descendente facilita priorizar.'],
    ['④ Cancelación por tramo vs. global', 'Columnas con línea de promedio, en orden de distancia', '¿La distancia explica la cancelación?', 'Si hubiera relación, las columnas crecerían de izquierda a derecha.'],
    ['Segmentaciones de zona y tramo', 'Segmentación de datos (mosaico)', '¿Y si miro solo esta combinación?', 'Un único conjunto de filtros afecta a todo el dashboard.'],
    ['Título y línea de lectura', 'Cuadros de texto', '¿Qué debe concluir el lector?', 'Entregan la pregunta y la conclusión principal junto a los datos.'],
  ], [1900, 2000, 2400, 3060], { size: 17 }),
  gap(),
  H2('7.2 Decisiones de diseño'),
  ...bullets([
    '**Énfasis, no arcoíris:** las zonas críticas van en azul y el resto en gris, para que la mirada vaya directo al problema.',
    '**Un umbral común:** la línea del promedio global (23,0 %) aparece en los gráficos ① y ④, para comparar cada columna contra la misma referencia.',
    '**Un solo tono en la matriz:** el degradado azul indica intensidad sin sugerir categorías.',
    '**Orden con sentido:** los tramos de distancia van de corto a largo, no por valor, para poder evaluar la hipótesis de la distancia.',
    '**Un solo eje por gráfico:** no se mezclan porcentajes y pesos en el mismo eje.',
    '**Lectura explícita:** el dashboard declara que su conclusión corresponde a los datos sin filtrar. Las limitaciones del análisis se documentan en la sección 10, no en el dashboard.',
  ]),
  H2('7.3 Interactividad verificada'),
  P('Con el filtro **Centro** (Figura 6) las tarjetas muestran 47,1 % de cancelación y $1.111.187 de ingreso perdido, 1 zona crítica y 41,6 % en el último KPI. La matriz deja solo la fila de Centro (57,1 % en el tramo largo y 40,0 % en el muy largo). Esas cifras coinciden con el resumen de la transformación. Las segmentaciones ofrecen solo los tramos que existen para la zona elegida: en Centro, el largo y el muy largo.'),
  P('El último KPI divide por el ingreso perdido **total** de las 100 órdenes, no por el de la selección. Por eso con Centro muestra 41,6 % ($1.111.187 de $2.672.017) y sin filtros, 83,7 %.'),
  ...figure('fig_pbi_filtro_centro.png', 6.5, 'Figura 6. Dashboard con la zona Centro seleccionada.'),
  ...placeholder('Dashboards de las otras preguntas', 'Capturas de cada dashboard con la descripción de sus elementos visuales y de las decisiones de diseño (tabla equivalente a la sección 7.1).'),
);

// 8 ---------------------------------------------------------------------------------------
add(H1('8. Implementación de KPI'), H2('8.1 KPI de la pregunta táctica'),
  table(['KPI', 'Definición', 'Medida DAX', 'Valor', 'Decisión que apoya'], [
    ['% de cancelación', 'Órdenes canceladas ÷ órdenes totales', '`Pct Cancelacion`', '23,0 %', 'Medir la gravedad global y compararla por zona o tramo'],
    ['Ingreso perdido', 'Suma del `total` de las órdenes canceladas, en pesos', '`Ingreso Perdido`', '$2.672.017', 'Priorizar según el impacto económico'],
    ['Zonas críticas', 'Número de zonas con % de cancelación mayor al promedio global', '`Zonas Criticas`', '3 (Centro, Norte y Sur, esta última marginal)', 'Definir el foco de la revisión de rutas'],
    ['% del ingreso perdido en zonas críticas', 'Ingreso perdido de las zonas críticas ÷ ingreso perdido total', '`Pct Ingreso Perdido Zonas Criticas`', '83,7 %', 'Medir cuánto del problema cubre intervenir esas zonas'],
  ], [1700, 2500, 1900, 1400, 1860], { size: 17 }),
  gap(),
  H2('8.2 Origen de los datos, cálculo y verificación'),
  P('Los KPI se calculan en Power BI con las medidas de la sección 6.2, sobre la tabla `tactico_ordenes`, que proviene del CSV generado al transformar los datos extraídos desde Cosmos DB con ADF. Son **dinámicos**: las tarjetas y los gráficos cambian al filtrar por zona o tramo. Dos cálculos ignoran los filtros a propósito (usan `ALL`): el promedio global (23,0 %) y el denominador del último KPI (el ingreso perdido total).'),
  P('**Verificación:** la consulta de la Figura 7 evalúa las medidas por zona en la vista de consultas DAX y reproduce los valores de la sección 2.2 (por ejemplo, Centro: 17 órdenes, 8 canceladas, 47 % de cancelación y $1.111.187,21 de ingreso perdido). La consulta global de las cuatro medidas devolvió 0,23 · 2.672.017,35 · 3 · 0,84, que coincide con las tarjetas del dashboard.'),
  ...figure('fig_pbi_dax.png', 6.0, 'Figura 7. Vista de consultas DAX: medidas evaluadas por zona (los porcentajes se muestran sin formato, por ejemplo 0,47).'),
  H2('8.3 Automatización'),
  P('Cada eslabón del flujo puede automatizarse:'),
  ...bullets([
    '**Extracción:** ADF permite programar el pipeline con un *trigger* de tipo *Schedule* (por ejemplo, diario).',
    '**Transformación:** `transformar_tactico.py` regenera el CSV para Power BI con un solo comando.',
    '**KPI y dashboard:** las medidas DAX se recalculan solas al aplicar filtros.',
  ]),
  P('**Estado actual, para no sobredeclarar:** el pipeline se ejecutó con *Trigger now* y el CSV se cargó a Power BI manualmente; no hay actualización programada ni en tiempo real. La mejora recomendada es dejar el CSV en Azure Blob Storage o SharePoint y conectar el modelo desde ahí, con actualización programada en Power BI Service.'),
  ...placeholder('Evidencia del trigger programado y KPI de las otras preguntas', 'Si programan el trigger de ADF o la actualización del modelo, peguen aquí la captura de la ejecución programada y actualicen el estado de esta sección. Agreguen la tabla de KPI de cada compañero/a (nombre, definición, medida o cálculo, valor y decisión que apoya).'),
);

// 9 ---------------------------------------------------------------------------------------
add(H1('9. Diagrama de arquitectura del flujo de datos'),
  ...figure('fig_arquitectura.png', 6.5, 'Figura 8. Arquitectura del flujo: Cosmos DB → Azure Data Factory → Blob Storage → Python → Power BI.'),
  ...bullets([
    '**Extract:** `cargar_cosmos.py` carga los JSON del anexo en Cosmos DB (una sola vez). El pipeline de ADF ejecuta tres consultas SQL en el origen y deja tres archivos JSON en Blob Storage.',
    '**Transform:** ocurre en dos lugares. El aplanamiento y la proyección se ejecutan dentro de Cosmos DB, en las consultas de ADF. `transformar_tactico.py` limpia, convierte tipos, une las colecciones y calcula los campos derivados, y produce `tactico_ordenes.csv`.',
    '**Load / visualización:** el CSV para Power BI (`out/powerbi/tactico_ordenes.csv`) se carga en Power BI Service, donde se define el modelo semántico `tactico_ordenes`, con sus 8 medidas DAX, y el dashboard.',
  ]),
  ...placeholder('Arquitectura de las otras preguntas', 'Si el flujo de datos de su pregunta difiere (otras colecciones, otra herramienta de visualización), agreguen su diagrama o actualicen la Figura 8.'),
);

// 10 --------------------------------------------------------------------------------------
add(H1('10. Conclusiones, limitaciones y recomendaciones'), H2('10.1 Conclusiones de la pregunta táctica'),
  ...bullets([
    'La cancelación se concentra en **Centro (47,1 %) y Norte (36,4 %)**, que suman 16 de las 23 cancelaciones y el 72 % del ingreso perdido.',
    'La **distancia de la ruta no explica** la cancelación: los tramos no muestran un patrón creciente.',
    'El proceso Cosmos DB → ADF → Blob → Python → Power BI funcionó de punta a punta, con las filas verificadas en cada etapa (100, 100 y 302 en ADF; 100 órdenes en el modelo).',
    'Se detectó y resolvió un problema de integración: la configuración regional chilena de Power BI leía el punto decimal como separador de miles. Los montos se entregan ahora en centavos enteros.',
  ]),
  H2('10.2 Limitaciones'),
  ...bullets([
    '**Muestra pequeña:** 100 órdenes. Las celdas de zona × tramo tienen entre 1 y 10 órdenes, por lo que son una señal y no una conclusión.',
    '**Retraso no medible:** el historial de seguimiento tiene siempre 2 días entre eventos, así que el tiempo de ciclo no distingue zonas. El enunciado pide zonas críticas de retraso; con estos datos no puede responderse.',
    '**Distancia poco confiable:** el mismo par origen→destino aparece con distancias de 114 a 1.946 km y en varias zonas.',
    '**Estados inconsistentes:** el estado de la orden coincide con el último evento del historial solo en 19 de 100 órdenes.',
    '**Zona Sur** supera el promedio global por solo 0,08 puntos, por lo que se presenta como marginal.',
  ]),
  H2('10.3 Recomendaciones'),
  ...bullets([
    'Revisar la operación de **Centro y Norte** como primera prioridad.',
    '**Registrar el motivo de cancelación**: los datos actuales no permiten saber por qué se cancela.',
    'Corregir el registro de **distancias y fechas de seguimiento** para poder medir retraso y evaluar la hipótesis de las rutas largas con datos confiables.',
    'Conectar Power BI a Azure Blob Storage o SharePoint con **actualización programada**, en lugar de cargar el CSV a mano.',
    'Repetir el análisis con un volumen mayor de órdenes.',
  ]),
  ...placeholder('Conclusiones del equipo', 'Conclusiones de las otras dos preguntas y una conclusión general del equipo: qué aprendió la gerencia de QuickTrack al combinar las tres miradas.'),
);

// Anexo -----------------------------------------------------------------------------------
add(H1('Anexo. Archivos del repositorio y reproducción', true),
  table(['Archivo', 'Función'], [
    ['`cargar_cosmos.py`', 'Carga las 5 colecciones en Cosmos DB (copia `_id` en `id`)'],
    ['`adf_salida/*.json`', 'Salida del pipeline de ADF (3 archivos)'],
    ['`transformar_tactico.py`', 'Limpieza, integración y campos derivados; genera los CSV (`out/powerbi/tactico_ordenes.csv`, sin decimales, es el que se carga en Power BI) y `out/calidad_datos.txt`'],
    ['`paquete_powerbi/`', 'CSV, `medidas.dax` (las 8 medidas) y guía para reconstruir el dashboard en Power BI Desktop'],
    ['`evidencias/`, `informe/` y `PREGUNTA_TACTICA.md`', 'Capturas de ADF y de Power BI, este informe y el documento de trabajo'],
  ], [3400, 5960], { size: 18 }),
  gap(),
  P('**Reproducción** (requiere Python 3 con `pandas` y `azure-cosmos`):', { p: { keepNext: true } }),
  ...code([
    '# credenciales: no subir al repositorio',
    'export COSMOS_ENDPOINT="https://<cuenta>.documents.azure.com:443/"',
    'export COSMOS_KEY="<clave primaria>"',
    'python cargar_cosmos.py --datos <carpeta_json_anexo>',
    '# ejecutar el pipeline en ADF y bajar los 3 JSON a ./adf_salida',
    'python transformar_tactico.py --entrada ./adf_salida',
    '# Power BI: Crear > Cargar un archivo > out/powerbi/tactico_ordenes.csv',
    '# luego crear las 8 medidas de paquete_powerbi/medidas.dax',
  ]),
);

C.pop();   // quita el espaciador final: evita una página vacía al cierre
/* ---------- documento ---------- */
const doc = new Document({
  creator: 'Equipo QuickTrack', title: 'Informe técnico parcial · EP3 · QuickTrack',
  numbering: { config: [{ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 32, bold: true, color: NAVY }, paragraph: { spacing: { before: 120, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 25, bold: true, color: '2A4E8C' }, paragraph: { spacing: { before: 240, after: 100 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1300, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: 'QuickTrack · EP3 · BDY0101 · Informe técnico parcial · Página ', font: FONT, size: 16, color: '7F7F7F' }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: '7F7F7F' })] })] }) },
    children: C,
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(process.argv[2], b); console.log('OK', process.argv[2], (b.length / 1e6).toFixed(2), 'MB'); });
