-- Expediente de demostracion con el trabajo de los agentes ya hecho.
--
-- Por que existe este archivo: el unico expediente que la demo puede producir
-- hoy corre con INVIMA_OFFLINE y `AgenciaSinRed`, que deliberadamente no inventa
-- aprobaciones. Resultado: el evaluador abre la pestana de Fuentes y ve cuatro
-- filas con `encontrada = false`. Es el comportamiento correcto del sistema,
-- pero no muestra el caso que importa: que ve una persona cuando el reliance SI
-- devolvio algo y hay que decidir sobre un hallazgo.
--
-- Este radicado es ese caso. Reproduce, fila por fila, lo que el A1 habria
-- escrito con red: las consultas que hizo, la URL de cada una, lo que encontro
-- en cada agencia y el contraste contra lo que se pide en Colombia. Nada aqui
-- es una decision: el expediente queda en PENDIENTE_VALIDACION_HUMANA y sale de
-- ahi por el mismo camino que cualquier otro, con una DecisionHumana firmada.
--
-- La molecula es Bosentan, que SI esta en el Manual (7.4.0.0.N33). Eso hace de
-- este expediente el complemento exacto del de Corazilimab: rama de molecula
-- conocida, ruta ESTANDAR, cuatro grupos en paralelo.
--
-- Tres cosas quedan sembradas a proposito para que el evaluador tenga que
-- trabajar y no solo firmar:
--
--   1. Discrepancia declarativa. El solicitante marco "no incluida en normas" y
--      el cruce contra el Manual arroja coincidencia. El Manual manda, pero la
--      contradiccion queda visible.
--   2. Contraste MAS_AMPLIA contra FDA. Se pide poblacion pediatrica desde los
--      3 anos y FDA solo aprobo adultos. Esto es exactamente lo que el art. 7.1
--      reserva a una persona: el agente lo senala, no lo resuelve.
--   3. Un NCT declarado que no existe en el registro publico.
--
-- Los items de checklist con origen 'AGENTE' se siembran aqui porque el
-- servicio de radicacion todavia solo copia la plantilla. Son la simulacion de
-- lo que el A3 debe escribir cuando quede conectado a la API.
--
-- El consecutivo va por debajo de BASE_CONSECUTIVO (14832) a proposito. El
-- numero de radicado es un orden de llegada y `_reservar_radicado` toma el
-- maximo mas uno: sembrar 014800 deja el expediente en la bandeja sin mover el
-- contador de las radicaciones reales, y sin poder chocar con una de ellas.
--
-- Datos sinteticos. El nombre de la molecula y las URL de consulta son reales;
-- los titulares, comprobantes, numeros de CPP y NCT no lo son.

BEGIN;

-- ------------------------------------------------------------- la solicitud --

INSERT INTO solicitudes (
    id, solicitante_id, estado, tipo_tramite, tipo_producto, datos_declarados,
    tarifa_codigo, metodo_pago, comprobante, valor_pagado, fecha_pago,
    radicado, radicada_en
) VALUES (
    '22222222-2222-4222-8222-222222222222',
    '11111111-1111-4111-8111-111111111111',
    'RADICADA', 'nuevo', 'sintesis',
    $decl${
      "nombre": "BOSENVIA 125 mg TABLETA RECUBIERTA",
      "principioActivo": "Bosentán",
      "concentracion": "125 mg",
      "formaFarmaceutica": "Tableta recubierta",
      "titular": "PULMOCARE PHARMA LTD.",
      "solicitante": "Farma Andina S.A.S.",
      "fabricante": "Synthron Fine Chemicals (Cork, Irlanda)",
      "fabricanteProductoTerminado": "Tabletec Manufacturing S.p.A. (Parma, Italia)",
      "importador": "Farma Andina S.A.S.",
      "nit": "900.123.456-7",
      "paisOrigen": "Reino Unido",
      "viaAdministracion": "Oral",
      "indicacion": "Hipertensión arterial pulmonar (Grupo 1 OMS) en adultos y en pacientes pediátricos desde los 3 años",
      "moleculaNoIncluidaNormas": true,
      "correo": "regulatorio@farmaandina.example",
      "telefono": "57 601 322 9040",
      "direccion": "Calle 100 No. 19-54, Oficina 401, Bogotá D.C.",
      "observaciones": "El solicitante declara molécula no incluida en normas farmacológicas."
    }$decl$::jsonb,
    '1005', 'pse', 'BAN-8839202', 7420000.00, '2026-08-21',
    '2026SM-014800', '2026-08-24T14:31:00-05:00'
) ON CONFLICT (id) DO UPDATE SET
    estado = EXCLUDED.estado,
    datos_declarados = EXCLUDED.datos_declarados,
    radicado = EXCLUDED.radicado;

-- Los folios. Son los PDF de data/demo con su SHA-256 real: el evaluador tiene
-- que poder abrir el mismo byte que se radico, no una referencia sin respaldo.
INSERT INTO documentos_cargados
    (solicitud_id, requerido_id, nombre_archivo, ruta_relativa, tamano_bytes, tipo_mime, sha256)
VALUES
 ('22222222-2222-4222-8222-222222222222','m1-formulario','ASS-RSA-FM113.pdf','demo/m1-formulario.pdf',1045630,'application/pdf','943e7e03897a4a41f8b799143b8e3798e12a4040a23dad660a6369f48f4b96dd'),
 ('22222222-2222-4222-8222-222222222222','m1-poder','poder-otorgado.pdf','demo/m1-poder.pdf',916436,'application/pdf','5ed2d70e1c5a4a0c6d531c44d2eff4ae0e80abd092f6b4ea4db79afc4d641f11'),
 ('22222222-2222-4222-8222-222222222222','m1-certexist','certificado-existencia.pdf','demo/m1-certexist.pdf',598642,'application/pdf','ab2f7a4aa89aaff516d0a1e6325e497bbbb97c09e71e065aa5090344c6311fad'),
 ('22222222-2222-4222-8222-222222222222','m1-bpm','cpp-mhra-bpm.pdf','demo/m1-bpm.pdf',643685,'application/pdf','159a47b99319ffc2bdb3c1a8e3790896cb3640fff86660998eaa23eb7928a9da'),
 ('22222222-2222-4222-8222-222222222222','pago-comprobante','comprobante-pse.pdf','demo/pago-comprobante.pdf',2026,'application/pdf','495f906bddd7739e7f809bd65a5dd31d6aa685c24eb7091625f030532e63ab5d'),
 ('22222222-2222-4222-8222-222222222222','m2-calidad','resumen-calidad.pdf','demo/m2-calidad.pdf',821287,'application/pdf','e3e7957542305f7bedf0c4712345d351441f070f906a435b80c1e0accf71a48b'),
 ('22222222-2222-4222-8222-222222222222','m2-preclinico','resumen-preclinico.pdf','demo/m2-preclinico.pdf',821287,'application/pdf','e3e7957542305f7bedf0c4712345d351441f070f906a435b80c1e0accf71a48b'),
 ('22222222-2222-4222-8222-222222222222','m2-clinico','resumen-clinico.pdf','demo/m2-clinico.pdf',821287,'application/pdf','e3e7957542305f7bedf0c4712345d351441f070f906a435b80c1e0accf71a48b'),
 ('22222222-2222-4222-8222-222222222222','m3-especif','especificaciones-pt.pdf','demo/m3-especif.pdf',836111,'application/pdf','9074cf152ccae73d357919201e5fe3343a46ad585e554f1a608a84126f75a0de'),
 ('22222222-2222-4222-8222-222222222222','m3-metodos','metodos-analiticos.pdf','demo/m3-metodos.pdf',836111,'application/pdf','9074cf152ccae73d357919201e5fe3343a46ad585e554f1a608a84126f75a0de'),
 ('22222222-2222-4222-8222-222222222222','m3-estabilidad','estudios-estabilidad.pdf','demo/m3-estabilidad.pdf',836111,'application/pdf','9074cf152ccae73d357919201e5fe3343a46ad585e554f1a608a84126f75a0de'),
 ('22222222-2222-4222-8222-222222222222','m4-toxico','estudios-toxicologicos.pdf','demo/m4-toxico.pdf',779631,'application/pdf','98b4945700ef7b945b7ccb54858ae6d406c695127c0dc282ef6026df1e9a0466'),
 ('22222222-2222-4222-8222-222222222222','m5-eficacia','eficacia-seguridad.pdf','demo/m5-eficacia.pdf',1334870,'application/pdf','e9c3911a491389507d0158817f2c60644ca67dc66ac875ece13858f1349fd018'),
 ('22222222-2222-4222-8222-222222222222','pgr-plan','plan-gestion-riesgos.pdf','demo/pgr-plan.pdf',2096,'application/pdf','8223b5a86625ebc1a77b9c24343e7179a34f627ce63958fd3b430f820738c834'),
 ('22222222-2222-4222-8222-222222222222','anx-etiqueta','etiqueta-propuesta.pdf','demo/anx-etiqueta.pdf',2042,'application/pdf','822b36d62a747db4c8ec46584c2389d2f0785715aa89e354826bd5bfe47f6d55'),
 ('22222222-2222-4222-8222-222222222222','anx-ipp','inserto-ipp.pdf','demo/anx-ipp.pdf',2082,'application/pdf','746892edda0c0296d5e066fcdc94095b30784e9529201573cbbb6da5c2847d48')
ON CONFLICT (solicitud_id, requerido_id) DO NOTHING;

COMMIT;

BEGIN;

-- --------------------------------------------------------------- el payload --
--
-- Forma exacta del DTO del A1 (`aplicacion/dto.py`). Cada campo es un Dato[T]
-- que carga su origen y su trazabilidad: EXTRAIDO viene del folio, BUSQUEDA de
-- una fuente externa citada con URL, RECOMENDACION es logica determinista del
-- agente. Los valores van sin tildes porque asi salen del extractor.
--
-- `eventos` no se escribe a mano: se copia del auditoria_log del propio payload,
-- para que la linea de tiempo del evaluador y la bitacora del agente no puedan
-- divergir.

INSERT INTO expedientes
    (radicado, solicitud_id, fecha_radicacion, estado, payload, eventos, carpeta_dossier)
SELECT
    '2026SM-014800',
    '22222222-2222-4222-8222-222222222222',
    DATE '2026-08-24',
    'PENDIENTE_VALIDACION_HUMANA',
    p.payload,
    p.payload -> 'seguridad_y_trazabilidad' -> 'auditoria_log',
    '/datos/dossieres/2026SM-014800'
FROM (SELECT $pl${
  "radicacion": {
    "numero_radicado": "2026SM-014800",
    "fecha_radicacion": "2026-08-24",
    "estado": "PENDIENTE_VALIDACION_HUMANA",
    "pago": {
      "comprobante_numero": {"valor": "BAN-8839202", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > Comprobante de pago > Pagina 1 > Campo Numero", "modulo": "Modulo 1", "seccion": "Comprobante de pago", "pagina": 1, "campo": "Numero", "url": null}},
      "codigo_tarifa": {"valor": "1005", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > Comprobante de pago > Pagina 1 > Campo Codigo de tarifa", "modulo": "Modulo 1", "seccion": "Comprobante de pago", "pagina": 1, "campo": "Codigo de tarifa", "url": null}},
      "valor_pagado": {"valor": "7420000.00", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > Comprobante de pago > Pagina 1 > Campo Valor", "modulo": "Modulo 1", "seccion": "Comprobante de pago", "pagina": 1, "campo": "Valor", "url": null}},
      "verificado": true,
      "resultado_validacion": "Pago verificado: comprobante, tarifa y valor coinciden",
      "inconsistencias": []
    }
  },
  "solicitante": {
    "nombre_titular": {"valor": "PULMOCARE PHARMA LTD.", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Titular > Pagina 1 > Campo Razon social", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Titular", "pagina": 1, "campo": "Razon social", "url": null}},
    "representante_colombia": {"valor": "Farma Andina S.A.S.", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Representante > Pagina 1 > Campo Razon social", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Representante", "pagina": 1, "campo": "Razon social", "url": null}},
    "nit_representante": {"valor": "900.123.456-7", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Representante > Pagina 1 > Campo NIT", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Representante", "pagina": 1, "campo": "NIT", "url": null}}
  },
  "producto": {
    "nombre": {"valor": "BOSENVIA", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Producto > Pagina 2 > Campo Nombre", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Producto", "pagina": 2, "campo": "Nombre", "url": null}},
    "principio_activo": {"valor": "Bosentan", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Producto > Pagina 2 > Campo Principio activo", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Producto", "pagina": 2, "campo": "Principio activo", "url": null}},
    "concentracion": {"valor": "125 mg", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Producto > Pagina 2 > Campo Concentracion", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Producto", "pagina": 2, "campo": "Concentracion", "url": null}},
    "forma_farmaceutica": {"valor": "Tableta recubierta", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Producto > Pagina 2 > Campo Forma farmaceutica", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Producto", "pagina": 2, "campo": "Forma farmaceutica", "url": null}},
    "indicacion_solicitada": {"valor": "Hipertension arterial pulmonar (Grupo 1 OMS) en adultos y en pacientes pediatricos desde los 3 anos", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Producto > Pagina 3 > Campo Indicacion solicitada", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Producto", "pagina": 3, "campo": "Indicacion solicitada", "url": null}}
  },
  "tramite": {
    "tipo_tramite": {"valor": "Registro Sanitario de Molecula", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Tramite > Pagina 1 > Campo Tipo", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Tramite", "pagina": 1, "campo": "Tipo", "url": null}},
    "modalidad": {"valor": "Importar y Vender", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Tramite > Pagina 1 > Campo Modalidad", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Tramite", "pagina": 1, "campo": "Modalidad", "url": null}},
    "ruta_estudio": {"valor": "Evaluacion farmacologica de medicamento conocido", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Tramite > Pagina 1 > Campo Ruta de estudio", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Tramite", "pagina": 1, "campo": "Ruta de estudio", "url": null}}
  },
  "validaciones_internacionales": {
    "certificado": {
      "tipo": {"valor": "CPP", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > Certificado BPM/CPP > Pagina 1 > Campo Tipo", "modulo": "Modulo 1", "seccion": "Certificado BPM/CPP", "pagina": 1, "campo": "Tipo", "url": null}},
      "numero": {"valor": "CPP-UK-2026-00733", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > Certificado BPM/CPP > Pagina 1 > Campo Numero", "modulo": "Modulo 1", "seccion": "Certificado BPM/CPP", "pagina": 1, "campo": "Numero", "url": null}},
      "pais_emisor": {"valor": "United Kingdom", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > Certificado BPM/CPP > Pagina 1 > Campo Pais emisor", "modulo": "Modulo 1", "seccion": "Certificado BPM/CPP", "pagina": 1, "campo": "Pais emisor", "url": null}},
      "autoridad_emisora": {"valor": "MHRA", "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > Certificado BPM/CPP > Pagina 1 > Campo Autoridad emisora", "modulo": "Modulo 1", "seccion": "Certificado BPM/CPP", "pagina": 1, "campo": "Autoridad emisora", "url": null}}
    },
    "reporte_coincidencia_internacional": {
      "molecula_identificada": "Bosentan",
      "agencias_verificadas_en_fuente": ["FDA", "EMA"],
      "aprobaciones_declaradas_no_verificadas": ["MHRA"],
      "contrastes": [
        {
          "agencia": "FDA",
          "indicacion_solicitada": "Hipertension arterial pulmonar (Grupo 1 OMS) en adultos y en pacientes pediatricos desde los 3 anos",
          "indicacion_aprobada": "Hipertension arterial pulmonar (Grupo 1 OMS) en adultos, para mejorar la capacidad de ejercicio y disminuir el empeoramiento clinico",
          "clase_contraste": "MAS_AMPLIA",
          "observacion": "Lo solicitado para Colombia incluye poblacion pediatrica desde los 3 anos; la etiqueta recuperada de FDA se limita a adultos. La diferencia de alcance no la resuelve el agente.",
          "fuente": "openFDA > drug/label > openfda.generic_name=bosentan"
        },
        {
          "agencia": "EMA",
          "indicacion_solicitada": "Hipertension arterial pulmonar (Grupo 1 OMS) en adultos y en pacientes pediatricos desde los 3 anos",
          "indicacion_aprobada": "Hipertension arterial pulmonar (Grupo 1 OMS) en adultos y en pacientes pediatricos a partir de 1 ano de edad",
          "clase_contraste": "MAS_RESTRINGIDA",
          "observacion": "Lo solicitado es un subconjunto de lo aprobado por EMA: la agencia cubre desde 1 ano y aqui se piden 3 anos en adelante.",
          "fuente": "EMA > Medicines > Busqueda por principio activo"
        },
        {
          "agencia": "MHRA",
          "indicacion_solicitada": "Hipertension arterial pulmonar (Grupo 1 OMS) en adultos y en pacientes pediatricos desde los 3 anos",
          "indicacion_aprobada": "Aprobacion declarada en el CPP-UK-2026-00733",
          "clase_contraste": "COINCIDENTE",
          "observacion": "Declarada por el solicitante en el CPP. La matriz de agencias del agente no tiene adaptador para MHRA: la fuente no se consulto y el dato no se da por verificado.",
          "fuente": "Modulo 1 > Certificado BPM/CPP > Pagina 1"
        }
      ]
    }
  },
  "evaluacion_normativa": {
    "estatus_molecula": {"valor": "MOLECULA CONOCIDA", "origen": "BUSQUEDA", "trazabilidad": {"descripcion": "Manual de Normas Farmacologicas de Colombia (2024)", "modulo": null, "seccion": null, "pagina": null, "campo": null, "url": null}},
    "check_declarativo_no_incluida": {"valor": true, "origen": "EXTRAIDO", "trazabilidad": {"descripcion": "Modulo 1 > ASS-RSA-FM113 > Declaracion normativa > Pagina 3 > Campo Molecula no incluida en normas farmacologicas", "modulo": "Modulo 1", "seccion": "ASS-RSA-FM113 > Declaracion normativa", "pagina": 3, "campo": "Molecula no incluida en normas farmacologicas", "url": null}},
    "verificacion_manual_normas": {"valor": "Encontrada en el Manual de Normas Farmacologicas (7.4.0.0.N33)", "origen": "BUSQUEDA", "trazabilidad": {"descripcion": "Manual de Normas Farmacologicas de Colombia (2024)", "modulo": null, "seccion": null, "pagina": null, "campo": null, "url": null}},
    "coincidencias_manual": [
      {"dci": "Bosentan", "norma": "7.4.0.0.N33", "indicacion": "Hipertension arterial pulmonar"}
    ],
    "discrepancia_declarativa": {
      "declarado_por_solicitante": "Molecula NO incluida en normas farmacologicas",
      "hallado_en_manual": "Registrada en 7.4.0.0.N33",
      "mensaje": "El solicitante declaro que la molecula no esta incluida en normas farmacologicas, pero el cruce contra el Manual arroja coincidencia. Requiere verificacion del evaluador."
    }
  },
  "enrutamiento": {
    "ruta_recomendada": {"valor": "ESTANDAR", "origen": "RECOMENDACION", "trazabilidad": {"descripcion": "Motor de enrutamiento del A1 (logica determinista)", "modulo": null, "seccion": null, "pagina": null, "campo": null, "url": null}},
    "destino_primario": {"valor": "Grupo de Evaluacion Farmacologica", "origen": "RECOMENDACION", "trazabilidad": {"descripcion": "Motor de enrutamiento del A1 (logica determinista)", "modulo": null, "seccion": null, "pagina": null, "campo": null, "url": null}},
    "destinos_paralelos": ["Grupo de Evaluacion de Calidad", "Grupo de Evaluacion Legal", "Grupo de Farmacovigilancia"],
    "prioridad": {"valor": "NORMAL", "origen": "RECOMENDACION", "trazabilidad": {"descripcion": "Motor de enrutamiento del A1 (logica determinista)", "modulo": null, "seccion": null, "pagina": null, "campo": null, "url": null}},
    "razon": "Molecula incluida en el Manual de Normas Farmacologicas. No requiere concepto previo de Sala; procede evaluacion concurrente por grupos."
  },
  "supervision_humana": {
    "estado": "PENDIENTE DE VALIDACION MANUAL",
    "advertencia": "Este documento es un insumo de apoyo. No constituye concepto tecnico ni decision administrativa (art. 7.1, Resolucion 2026025611).",
    "checklist_evaluador": {
      "datos_extraidos_validados": false,
      "busqueda_internacional_confirmada": false,
      "enrutamiento_aprobado": false
    },
    "usuario_responsable": null,
    "sentido_decision": null,
    "firma_timestamp": null,
    "campos_corregidos": []
  },
  "seguridad_y_trazabilidad": {
    "separacion_epistemologica": {
      "EXTRAIDO": "Transcrito literalmente de un documento del expediente",
      "BUSQUEDA": "Recuperado de una fuente publica externa y citado con su URL",
      "RECOMENDACION": "Producido por logica determinista del agente; sugerencia, no decision",
      "NO_SUMINISTRADO": "Campo buscado y ausente en el expediente; no se infiere"
    },
    "modelo_utilizado": "google/gemini-3.6-flash (temperature=0.0)",
    "defensa_prompt_injection": "El contenido del dossier se procesa como dato delimitado, nunca como instruccion.",
    "contenido_sospechoso_detectado": [],
    "auditoria_log": [
      {"timestamp": "2026-08-24T19:31:02.104000+00:00", "tipo": "CAMBIO_ESTADO", "radicado": "2026SM-014800", "accion": "RECIBIDO -> INGESTADO", "resultado": "16 folios archivados con SHA-256", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:02.510000+00:00", "tipo": "PASO_INICIADO", "radicado": "2026SM-014800", "accion": "Ingesta del Modulo 1", "resultado": "", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:09.882000+00:00", "tipo": "PASO_COMPLETADO", "radicado": "2026SM-014800", "accion": "Ingesta del Modulo 1", "resultado": "4 folios convertidos a Markdown con trazabilidad de pagina", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:10.004000+00:00", "tipo": "LLAMADA_MODELO", "radicado": "2026SM-014800", "accion": "Extraccion de metadatos ASS-RSA-FM113", "resultado": "18 campos transcritos contra esquema", "actor": "SISTEMA", "detalles": {"modelo": "google/gemini-3.6-flash", "temperature": 0.0}},
      {"timestamp": "2026-08-24T19:31:14.331000+00:00", "tipo": "CAMBIO_ESTADO", "radicado": "2026SM-014800", "accion": "INGESTADO -> METADATOS_EXTRAIDOS", "resultado": "", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:14.402000+00:00", "tipo": "PASO_COMPLETADO", "radicado": "2026SM-014800", "accion": "Validacion transaccional del pago", "resultado": "Comprobante BAN-8839202 conciliado: tarifa 1005 por 7.420.000 COP", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:14.418000+00:00", "tipo": "CAMBIO_ESTADO", "radicado": "2026SM-014800", "accion": "METADATOS_EXTRAIDOS -> PAGO_VALIDADO", "resultado": "", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:15.019000+00:00", "tipo": "PASO_INICIADO", "radicado": "2026SM-014800", "accion": "Reliance regulatorio", "resultado": "", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:16.774000+00:00", "tipo": "CONSULTA_EXTERNA", "radicado": "2026SM-014800", "accion": "Consulta a FDA", "resultado": "Encontrada: 1 etiqueta con coincidencia exacta de principio activo", "actor": "SISTEMA", "detalles": {"url": "https://api.fda.gov/drug/label.json?search=openfda.generic_name:%22bosentan%22&limit=10"}},
      {"timestamp": "2026-08-24T19:31:18.230000+00:00", "tipo": "CONSULTA_EXTERNA", "radicado": "2026SM-014800", "accion": "Consulta a EMA", "resultado": "Encontrada: producto autorizado por procedimiento centralizado", "actor": "SISTEMA", "detalles": {"url": "https://www.ema.europa.eu/en/search?search_api_fulltext=Bosentan"}},
      {"timestamp": "2026-08-24T19:31:18.244000+00:00", "tipo": "ALERTA", "radicado": "2026SM-014800", "accion": "Agencia sin adaptador", "resultado": "MHRA declarada en el CPP y no consultada: no hay puerto de salida para esa agencia", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:19.640000+00:00", "tipo": "CONSULTA_EXTERNA", "radicado": "2026SM-014800", "accion": "Verificacion de ensayo clinico NCT01204333", "resultado": "COMPLETED (resultados disponibles: True)", "actor": "SISTEMA", "detalles": {"url": "https://clinicaltrials.gov/study/NCT01204333"}},
      {"timestamp": "2026-08-24T19:31:20.905000+00:00", "tipo": "CONSULTA_EXTERNA", "radicado": "2026SM-014800", "accion": "Verificacion de ensayo clinico NCT03288148", "resultado": "No encontrado en el registro publico", "actor": "SISTEMA", "detalles": {"url": "https://clinicaltrials.gov/study/NCT03288148"}},
      {"timestamp": "2026-08-24T19:31:20.933000+00:00", "tipo": "CAMBIO_ESTADO", "radicado": "2026SM-014800", "accion": "PAGO_VALIDADO -> RELIANCE_COMPLETADO", "resultado": "", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:21.087000+00:00", "tipo": "PASO_COMPLETADO", "radicado": "2026SM-014800", "accion": "Contraste de indicaciones", "resultado": "3 contrastes: 1 MAS_AMPLIA (FDA), 1 MAS_RESTRINGIDA (EMA), 1 declarado sin verificar (MHRA)", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:21.402000+00:00", "tipo": "ALERTA", "radicado": "2026SM-014800", "accion": "Bypass check", "resultado": "El solicitante declaro que la molecula no esta incluida en normas farmacologicas, pero el cruce contra el Manual arroja coincidencia. Requiere verificacion del evaluador.", "actor": "SISTEMA", "detalles": {"norma": "7.4.0.0.N33"}},
      {"timestamp": "2026-08-24T19:31:21.418000+00:00", "tipo": "CAMBIO_ESTADO", "radicado": "2026SM-014800", "accion": "RELIANCE_COMPLETADO -> NORMAS_EVALUADAS", "resultado": "", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:21.560000+00:00", "tipo": "PASO_COMPLETADO", "radicado": "2026SM-014800", "accion": "Enrutamiento", "resultado": "ESTANDAR hacia Grupo de Evaluacion Farmacologica, con tres grupos en paralelo", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:21.575000+00:00", "tipo": "CAMBIO_ESTADO", "radicado": "2026SM-014800", "accion": "NORMAS_EVALUADAS -> RUTA_RECOMENDADA", "resultado": "", "actor": "SISTEMA", "detalles": {}},
      {"timestamp": "2026-08-24T19:31:21.590000+00:00", "tipo": "CAMBIO_ESTADO", "radicado": "2026SM-014800", "accion": "RUTA_RECOMENDADA -> PENDIENTE_VALIDACION_HUMANA", "resultado": "El agente se detiene aqui. La transicion a ENRUTADO exige una DecisionHumana firmada (art. 7.1).", "actor": "SISTEMA", "detalles": {}}
    ]
  }
}$pl$::jsonb AS payload) AS p
ON CONFLICT (radicado) DO UPDATE SET
    payload = EXCLUDED.payload,
    eventos = EXCLUDED.eventos,
    estado  = EXCLUDED.estado;

COMMIT;

BEGIN;

-- ------------------------------------------------------- fuentes que consulto --
--
-- Estas filas son exactamente las que `servicios/fuentes.py::extraer_fuentes`
-- deriva del payload de arriba: cruza los eventos CONSULTA_EXTERNA (que aportan
-- la fuente, la URL y si se encontro) con los contrastes (que aportan el titulo
-- y la observacion). Se siembran explicitamente porque la radicacion las escribe
-- al correr el A1 y este expediente no pasa por ahi.
--
-- La columna `fecha` es la unica que no sale del extractor todavia: openFDA
-- devuelve `effective_time` y ClinicalTrials.gov la fecha de finalizacion, y
-- ninguna de las dos se esta mapeando. Queda poblada aqui para mostrar la
-- pestana completa, y es trabajo pendiente en `extraer_fuentes`.
--
-- Ninguna queda vinculada. Vincular es un acto del evaluador: el agente propone,
-- la persona incorpora.

INSERT INTO fuentes_externas
    (radicado, fuente, titulo, tipo, pais, fecha, url, encontrada, observaciones)
VALUES
 ('2026SM-014800', 'FDA',
  'Hipertension arterial pulmonar (Grupo 1 OMS) en adultos, para mejorar la capacidad de ejercicio y disminuir el empeoramiento clinico',
  'Aprobación sanitaria', 'Estados Unidos', '2025-11-14',
  'https://api.fda.gov/drug/label.json?search=openfda.generic_name:%22bosentan%22&limit=10',
  TRUE,
  'Encontrada: 1 etiqueta con coincidencia exacta de principio activo Lo solicitado para Colombia incluye poblacion pediatrica desde los 3 anos; la etiqueta recuperada de FDA se limita a adultos. La diferencia de alcance no la resuelve el agente.'),

 ('2026SM-014800', 'EMA',
  'Hipertension arterial pulmonar (Grupo 1 OMS) en adultos y en pacientes pediatricos a partir de 1 ano de edad',
  'Aprobación sanitaria', 'Unión Europea', '2026-02-03',
  'https://www.ema.europa.eu/en/search?search_api_fulltext=Bosentan',
  TRUE,
  'Encontrada: producto autorizado por procedimiento centralizado Lo solicitado es un subconjunto de lo aprobado por EMA: la agencia cubre desde 1 ano y aqui se piden 3 anos en adelante.'),

 ('2026SM-014800', 'ClinicalTrials.gov', 'NCT01204333',
  'Ensayo clínico registrado', 'Estados Unidos', '2024-06-30',
  'https://clinicaltrials.gov/study/NCT01204333',
  TRUE,
  'COMPLETED (resultados disponibles: True)'),

 -- El NCT que el solicitante declaro y el registro publico no conoce. No se
 -- concluye que sea falso: se muestra que no se encontro, con el enlace para
 -- que el evaluador lo compruebe.
 ('2026SM-014800', 'ClinicalTrials.gov', 'NCT03288148',
  'Ensayo clínico registrado', 'Estados Unidos', '',
  'https://clinicaltrials.gov/study/NCT03288148',
  FALSE,
  'No encontrado en el registro publico'),

 -- Declarada en el CPP, sin adaptador de salida. Sin URL y sin verificar: el
 -- agente no fabrica un hallazgo por una agencia que no consulto.
 ('2026SM-014800', 'MHRA', 'Aprobacion declarada en el CPP-UK-2026-00733',
  'Aprobación sanitaria', 'Reino Unido', '', '',
  FALSE,
  'Aprobación declarada por el solicitante y no verificada en la fuente. Declarada por el solicitante en el CPP. La matriz de agencias del agente no tiene adaptador para MHRA: la fuente no se consulto y el dato no se da por verificado.')
ON CONFLICT (radicado, fuente, titulo) DO UPDATE SET
    tipo = EXCLUDED.tipo,
    pais = EXCLUDED.pais,
    fecha = EXCLUDED.fecha,
    url = EXCLUDED.url,
    encontrada = EXCLUDED.encontrada,
    observaciones = EXCLUDED.observaciones;

-- ------------------------------------------------------------------ checklist --
--
-- Los seis de plantilla, como los copia la radicacion, mas tres que salen de los
-- hallazgos de este expediente. Esos tres van con origen 'AGENTE': hoy nadie los
-- escribe (el A3 no esta cableado a la API), y son la simulacion de lo que debe
-- poblarse cuando lo este. Ninguno viene marcado: verificar es del evaluador.

INSERT INTO checklist_items (radicado, texto, origen, orden)
SELECT '2026SM-014800', texto, 'PLANTILLA', orden FROM checklist_plantilla
 WHERE NOT EXISTS (SELECT 1 FROM checklist_items WHERE radicado = '2026SM-014800');

INSERT INTO checklist_items (radicado, texto, origen, orden)
SELECT '2026SM-014800', v.texto, 'AGENTE', v.orden
  FROM (VALUES
    ('Resolver la discrepancia declarativa: el solicitante marcó "no incluida en normas farmacológicas" y el cruce contra el Manual arroja 7.4.0.0.N33', 10),
    ('Decidir sobre el alcance pediátrico: se solicita desde los 3 años y la etiqueta de FDA se limita a adultos (contraste MAS_AMPLIA)', 11),
    ('Pedir soporte del ensayo NCT03288148: el número declarado no aparece en ClinicalTrials.gov', 12)
  ) AS v(texto, orden)
 WHERE NOT EXISTS (
     SELECT 1 FROM checklist_items WHERE radicado = '2026SM-014800' AND origen = 'AGENTE'
 );

-- ------------------------------------------------------------------ consultas --
--
-- Consultas ya hechas sobre el expediente. Las dos primeras recuperan del corpus
-- con su cita — el texto se toma de `corpus_normativo` en vez de copiarse, para
-- que la respuesta guardada no pueda apartarse de la fuente. La tercera es una
-- pregunta sin coincidencia: se guarda como no encontrada. Un "no se encontro"
-- es preferible a una cita inventada sobre norma farmacologica.

INSERT INTO consultas (radicado, usuario, pregunta, respuesta, cita, url, encontrada, momento)
SELECT '2026SM-014800', 'evaluador.perez', c.pregunta, c.respuesta, c.cita, c.url, TRUE,
       TIMESTAMPTZ '2026-08-25 09:12:00-05'
  FROM corpus_normativo c WHERE c.id = 'c2'
   AND NOT EXISTS (SELECT 1 FROM consultas WHERE radicado = '2026SM-014800');

INSERT INTO consultas (radicado, usuario, pregunta, respuesta, cita, url, encontrada, momento)
SELECT '2026SM-014800', 'evaluador.perez', c.pregunta, c.respuesta, c.cita, c.url, TRUE,
       TIMESTAMPTZ '2026-08-25 09:20:00-05'
  FROM corpus_normativo c WHERE c.id = 'c4'
   AND NOT EXISTS (
       SELECT 1 FROM consultas WHERE radicado = '2026SM-014800' AND encontrada AND momento > TIMESTAMPTZ '2026-08-25 09:15:00-05'
   );

INSERT INTO consultas (radicado, usuario, pregunta, respuesta, cita, url, encontrada, momento)
SELECT '2026SM-014800', 'evaluador.perez',
       '¿Qué evidencia clínica se exige para extender una indicación a población pediátrica?',
       'No se encontró una entrada del corpus normativo que responda esta pregunta.',
       '', '', FALSE, TIMESTAMPTZ '2026-08-25 09:34:00-05'
 WHERE NOT EXISTS (SELECT 1 FROM consultas WHERE radicado = '2026SM-014800' AND NOT encontrada);

-- ------------------------------------------------------------------- bitacora --
--
-- La tabla es append-only por trigger: no admite ON CONFLICT ni correccion. Por
-- eso la idempotencia se resuelve antes de insertar, preguntando si el radicado
-- ya dejo huella.

INSERT INTO eventos_auditoria (momento, radicado, tipo, accion, resultado, actor, detalles)
SELECT v.momento, '2026SM-014800', v.tipo, v.accion, v.resultado, v.actor, v.detalles::jsonb
  FROM (VALUES
    (TIMESTAMPTZ '2026-08-24 14:31:02-05', 'CAMBIO_ESTADO', 'RECIBIDO -> INGESTADO', '16 folios archivados con SHA-256', 'SISTEMA', '{}'),
    (TIMESTAMPTZ '2026-08-24 14:31:14-05', 'PASO_COMPLETADO', 'Validacion transaccional del pago', 'Comprobante BAN-8839202 conciliado: tarifa 1005 por 7.420.000 COP', 'SISTEMA', '{}'),
    (TIMESTAMPTZ '2026-08-24 14:31:16-05', 'CONSULTA_EXTERNA', 'Consulta a FDA', 'Encontrada: 1 etiqueta con coincidencia exacta de principio activo', 'SISTEMA', '{"url": "https://api.fda.gov/drug/label.json?search=openfda.generic_name:%22bosentan%22&limit=10"}'),
    (TIMESTAMPTZ '2026-08-24 14:31:18-05', 'CONSULTA_EXTERNA', 'Consulta a EMA', 'Encontrada: producto autorizado por procedimiento centralizado', 'SISTEMA', '{"url": "https://www.ema.europa.eu/en/search?search_api_fulltext=Bosentan"}'),
    (TIMESTAMPTZ '2026-08-24 14:31:20-05', 'CONSULTA_EXTERNA', 'Verificacion de ensayo clinico NCT03288148', 'No encontrado en el registro publico', 'SISTEMA', '{"url": "https://clinicaltrials.gov/study/NCT03288148"}'),
    (TIMESTAMPTZ '2026-08-24 14:31:21-05', 'ALERTA', 'Bypass check', 'Declaro molecula no incluida y el Manual arroja 7.4.0.0.N33. Requiere verificacion del evaluador.', 'SISTEMA', '{"norma": "7.4.0.0.N33"}'),
    (TIMESTAMPTZ '2026-08-24 14:31:21-05', 'CAMBIO_ESTADO', 'RUTA_RECOMENDADA -> PENDIENTE_VALIDACION_HUMANA', 'El agente se detiene aqui. La transicion a ENRUTADO exige una DecisionHumana firmada (art. 7.1).', 'SISTEMA', '{}'),
    (TIMESTAMPTZ '2026-08-25 09:34:00-05', 'CONSULTA_DOSSIER', 'Consulta del evaluador al corpus normativo', 'Sin coincidencia para la pregunta sobre extension pediatrica de la indicacion', 'evaluador.perez', '{}')
  ) AS v(momento, tipo, accion, resultado, actor, detalles)
 WHERE NOT EXISTS (SELECT 1 FROM eventos_auditoria WHERE radicado = '2026SM-014800');

COMMIT;
