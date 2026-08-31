BEGIN;

INSERT INTO evaluadores (usuario, nombre, grupo) VALUES
    ('evaluador.perez', 'Ana María Pérez',  'FARMACOLOGIA'),
    ('evaluador.ruiz',  'Carlos Ruiz Mora', 'CALIDAD')
ON CONFLICT (usuario) DO UPDATE SET nombre = EXCLUDED.nombre;

INSERT INTO checklist_plantilla (id, texto, orden) VALUES
    ('p1', 'Concentración declarada coincide en todos los módulos', 1),
    ('p2', 'Estudios de estabilidad cubren condiciones de almacenamiento propuestas', 2),
    ('p3', 'Método analítico validado según farmacopea vigente', 3),
    ('p4', 'Evidencia clínica suficiente para la indicación solicitada', 4),
    ('p5', 'Información de fabricante coincide entre módulo 1 y módulo 3', 5),
    ('p6', 'Etiqueta e inserto consistentes con la indicación aprobada', 6)
ON CONFLICT (id) DO UPDATE SET texto = EXCLUDED.texto, orden = EXCLUDED.orden;

-- Corpus de consulta. Cada entrada lleva su cita: la pestana recupera y cita,
-- no redacta criterio propio.
INSERT INTO corpus_normativo (id, pregunta, respuesta, cita, etiquetas, sugerida, orden) VALUES
    ('c1',
     '¿Qué se debe validar en un método analítico?',
     'La validación debe cubrir especificidad, linealidad, exactitud, precisión (repetibilidad y precisión intermedia), límite de detección, límite de cuantificación, intervalo y robustez. El alcance exigible depende del tipo de ensayo: identificación, impurezas o valoración.',
     'ICH Q2(R2) — Validation of Analytical Procedures, tabla de características por tipo de ensayo',
     'metodo analitico validacion farmacopea', TRUE, 1),
    ('c2',
     '¿Qué evidencia de estabilidad se requiere?',
     'Se requieren estudios en condiciones de largo plazo y acelerada, sobre al menos tres lotes primarios, con los mismos métodos analíticos validados del producto terminado. Los datos deben sustentar el período de vida útil y las condiciones de almacenamiento declaradas en la etiqueta.',
     'ICH Q1A(R2) — Stability Testing of New Drug Substances and Products, secciones 2.1.7 y 2.2.7',
     'estabilidad vida util almacenamiento lotes', TRUE, 2),
    ('c3',
     '¿Cómo se documenta la trazabilidad de lote?',
     'Mediante el registro del número de lote, la fecha y el sitio de fabricación, el tamaño de lote, y los resultados de control de calidad asociados a ese lote. La consistencia entre lotes se demuestra con los datos de al menos tres lotes consecutivos a escala de producción.',
     'ICH Q7 — Good Manufacturing Practice for APIs, sección 6; y Módulo 3.2.P.3.5 del CTD',
     'lote trazabilidad consistencia fabricacion', TRUE, 3),
    ('c4',
     '¿Qué exige el Módulo 3 sobre la sustancia activa?',
     'Debe declararse nomenclatura y estructura, propiedades fisicoquímicas, el fabricante, la descripción del proceso de manufactura y sus controles, la caracterización con elucidación de estructura e impurezas, las especificaciones con sus procedimientos analíticos, y los estudios de estabilidad de la sustancia.',
     'CTD Módulo 3.2.S — Drug Substance',
     'sustancia activa modulo 3 caracterizacion impurezas', FALSE, 4),
    ('c5',
     '¿Qué se exige sobre el sistema envase-cierre?',
     'Debe describirse cada componente en contacto con el producto, su material de construcción y sus especificaciones, junto con la evidencia de idoneidad: protección, compatibilidad, seguridad de los materiales y desempeño funcional del sistema.',
     'CTD Módulo 3.2.P.7 — Container Closure System',
     'envase cierre compatibilidad materiales', FALSE, 5),
    ('c6',
     '¿Qué evidencia de remoción viral se exige a un producto biológico?',
     'Estudios de validación de la capacidad de los pasos del proceso para inactivar o remover virus, expresados como factor de reducción logarítmica por paso y acumulado, usando virus modelo relevantes y de distintas familias.',
     'ICH Q5A(R2) — Viral Safety Evaluation of Biotechnology Products Derived from Cell Lines of Human or Animal Origin',
     'viral remocion inactivacion biologico LRV', FALSE, 6)
ON CONFLICT (id) DO UPDATE SET respuesta = EXCLUDED.respuesta, cita = EXCLUDED.cita;

COMMIT;
