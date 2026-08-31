-- Datos de catalogo. Todo sintetico, como el resto del repositorio.
-- Las tarifas replican data/referencia/tarifas.csv, que es lo que lee el motor
-- de validacion transaccional del A1.

BEGIN;

INSERT INTO tipos_tramite (id, etiqueta, descripcion, orden) VALUES
    ('nuevo',        'Registro nuevo', 'Producto sin registro previo', 1),
    ('renovacion',   'Renovación',     'Registro vigente por vencer', 2),
    ('modificacion', 'Modificación',   'Cambios sobre registro vigente', 3),
    ('ampliacion',   'Ampliación',     'Nueva presentación o indicación', 4)
ON CONFLICT (id) DO UPDATE SET etiqueta = EXCLUDED.etiqueta,
                               descripcion = EXCLUDED.descripcion;

INSERT INTO tipos_producto (id, etiqueta, descripcion, orden) VALUES
    ('sintesis',        'Síntesis química', 'Molécula de origen químico', 1),
    ('biologico',       'Biológico',        'Derivado de organismos vivos', 2),
    ('biotecnologico',  'Biotecnológico',   'Obtenido por biotecnología', 3),
    ('vacuna',          'Vacuna',           'Producto inmunobiológico', 4)
ON CONFLICT (id) DO UPDATE SET etiqueta = EXCLUDED.etiqueta,
                               descripcion = EXCLUDED.descripcion;

INSERT INTO tarifas (codigo, concepto, valor) VALUES
    ('1004', 'Evaluación farmacológica de medicamento nuevo (molécula nueva)', 14850000.00),
    ('1005', 'Evaluación farmacológica de medicamento conocido',                7420000.00),
    ('1012', 'Registro sanitario medicamento de síntesis química',              9350000.00),
    ('1020', 'Registro sanitario de producto biológico',                       18600000.00)
ON CONFLICT (codigo) DO UPDATE SET concepto = EXCLUDED.concepto,
                                   valor = EXCLUDED.valor;

INSERT INTO metodos_pago (id, etiqueta, orden) VALUES
    ('pse',           'PSE', 1),
    ('tarjeta',       'Tarjeta de crédito', 2),
    ('consignacion',  'Consignación bancaria', 3)
ON CONFLICT (id) DO UPDATE SET etiqueta = EXCLUDED.etiqueta;

INSERT INTO modulos_ctd (id, titulo, orden) VALUES
    ('m1',  'Módulo 1 · Administrativo / legal', 1),
    ('m2',  'Módulo 2 · Resúmenes expertos',     2),
    ('m3',  'Módulo 3 · Calidad',                3),
    ('m4',  'Módulo 4 · Información preclínica', 4),
    ('m5',  'Módulo 5 · Información clínica',    5),
    ('pgr', 'Plan de Gestión de Riesgos',        6),
    ('anx', 'Anexos',                            7)
ON CONFLICT (id) DO UPDATE SET titulo = EXCLUDED.titulo, orden = EXCLUDED.orden;

-- folio_destino conecta la casilla del checklist con el nombre de archivo que
-- espera el parser del A1 dentro de la carpeta del dossier. Los que van en NULL
-- se archivan pero todavia no alimentan a ningun agente.
INSERT INTO documentos_requeridos (id, modulo_id, nombre, obligatorio, orden, folio_destino) VALUES
    ('m1-formulario',  'm1', 'Formulario de solicitud',                              TRUE,  1, 'modulo1_fm113'),
    ('m1-poder',       'm1', 'Poder debidamente otorgado',                           TRUE,  2, NULL),
    ('m1-certexist',   'm1', 'Certificado de existencia y representación legal',     TRUE,  3, 'modulo1_legal'),
    ('m1-bpm',         'm1', 'Certificado de Buenas Prácticas de Manufactura',       TRUE,  4, NULL),
    ('m2-calidad',     'm2', 'Resumen experto de calidad',                           TRUE,  1, NULL),
    ('m2-preclinico',  'm2', 'Resumen experto preclínico',                           FALSE, 2, NULL),
    ('m2-clinico',     'm2', 'Resumen experto clínico',                              TRUE,  3, NULL),
    ('m3-especif',     'm3', 'Especificaciones del producto terminado',              TRUE,  1, 'modulo3_calidad'),
    ('m3-metodos',     'm3', 'Métodos analíticos validados',                         TRUE,  2, NULL),
    ('m3-estabilidad', 'm3', 'Estudios de estabilidad',                              TRUE,  3, NULL),
    ('m4-toxico',      'm4', 'Estudios toxicológicos',                               FALSE, 1, NULL),
    ('m5-eficacia',    'm5', 'Estudios clínicos de eficacia y seguridad',            TRUE,  1, NULL),
    ('pgr-plan',       'pgr','Plan de Gestión de Riesgos',                           TRUE,  1, NULL),
    ('anx-etiqueta',   'anx','Etiqueta propuesta',                                   TRUE,  1, NULL),
    ('anx-ipp',        'anx','Inserto / Información para prescribir',                TRUE,  2, NULL),
    -- El comprobante se adjunta en el paso de pago, no en el checklist documental.
    -- Vive igual en el catalogo porque es un folio mas del expediente: se archiva
    -- con su SHA-256 y el evaluador tiene que poder verlo.
    ('pago-comprobante','m1', 'Comprobante de pago',                                 TRUE,  5, NULL)
ON CONFLICT (id) DO UPDATE SET nombre = EXCLUDED.nombre,
                               obligatorio = EXCLUDED.obligatorio,
                               folio_destino = EXCLUDED.folio_destino;

-- Solicitante de demostracion. Sintetico.
INSERT INTO solicitantes (id, razon_social, nit, correo) VALUES
    ('11111111-1111-4111-8111-111111111111', 'Farma Andina S.A.S.', '900.123.456-7',
     'regulatorio@farmaandina.example')
ON CONFLICT (nit) DO NOTHING;

COMMIT;
