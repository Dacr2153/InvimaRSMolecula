# A3-ECPF — Auditoria de calidad y procesos (Modulo 3 / CMC)

Audita el Modulo 3 de un expediente de registro sanitario: sustancia activa,
validacion de remocion viral, consistencia de lotes comerciales, estabilidad
formal y sistema envase-cierre. Entrega hallazgos trazados al folio.

## Como correrlo

```
PYTHONPATH=src python -m invima_a3.adaptadores.entrada.cli \
    data/fixtures/dossier_corazilimab/modulo3_calidad.md \
    --radicado 20268011234 --salida auditoria.json
```

Modo offline por defecto: lectura determinista del fixture, sin red y sin
consumir credito. `pytest tests/a3` corre la suite completa sobre el mismo
camino.

## Cuatro decisiones que se apartan del borrador de especificacion

**1. Ninguna especificacion vive en el codigo.** El borrador cableaba valores
(`peso molecular = 148210 Da`, `LRV >= 14.2`, `viabilidad MCB >= 92%`). Esos
numeros son propios de una molecula; cablearlos convierte al agente en un
validador de un unico producto sintetico. Aqui la especificacion sale del
expediente (`Especificacion` con su `Traza`) o de una fuente normativa citada a
traves de `EspecificacionesPort`. Cuando no hay ninguna, el hallazgo es
`ESPECIFICACION_NO_DECLARADA`, nunca un silencio tranquilizador.

**2. El agente no emite concepto.** El borrador terminaba en
`"estado_evaluacion": "CONFORMIDAD CONDICIONADA"` y
`"recomendacion_final": "APROBACION CONDICIONADA A..."`. Eso es exactamente lo
que el articulo 7.1 de la Resolucion 2026025611 le prohibe a la IA. La salida de
este agente son hallazgos, conteos y la distancia al limite; el bloque
`decision` sale siempre en `PENDIENTE_DE_LECTURA_HUMANA` con `responsable: null`.

**3. La promesa anterior es verificable, no declarativa.** `auditar_lexico`
recorre el payload completo antes de entregarlo y aborta la corrida con
`SalidaConclusivaError` si aparece vocabulario decisorio ("cumple", "aprobacion",
"rechazo", "conforme", "puntaje"). Una prueba lo ejercita metiendo la palabra
desde el propio dossier.

**4. Se reporta la cobertura, no solo el resultado.** Una auditoria con 95% de
hallazgos dentro de especificacion sobre una cobertura del 30% no dice lo que
parece decir. `resumen.cobertura_verificable` responde que fraccion de lo
auditado pudo contrastarse de verdad contra un limite declarado, y nace como
`Dato` de origen `RECOMENDACION` porque es una lectura del agente.

## Lo que el agente senala y el borrador no miraba

- Un LRV sin virus modelo declarado no es contrastable: la capacidad de
  depuracion depende de si el virus es envuelto, de su tamano y su resistencia.
- Un perfil de glicoformas que no suma ~100% esta incompleto; contrastar cada
  forma por separado sobre un perfil incompleto da una lectura enganosa.
- Una vida util declarada que va mas alla del ultimo punto de muestreo con dato.
- Deriva monotona dentro de limite, y proyeccion lineal al limite cuando el cruce
  cae dentro del periodo declarado (recta de dos puntos, no regresion ICH Q1E).
- Un cambio de componente sin estudio comparativo o sin fecha efectiva.
- Umbral de dispersion entre lotes (CV): criterio operativo del agente, declarado
  como tal en el texto del hallazgo porque no proviene del expediente.

## Estructura

```
domain/modelos.py            Especificacion, Medicion, Hallazgo, contrastar()
domain/modulo3.py            agregado ExpedienteCalidad
domain/servicios/            estadistica, sustancia_activa, inactivacion_viral,
                             consistencia_lotes, estabilidad, envase_cierre,
                             motor_hallazgos (guardia lexica)
puertos/                     ExpedienteCalidadPort, EspecificacionesPort
                             (parser, extractor y log de auditoria se reusan del A1)
adaptadores/salida/          lector determinista de Markdown
adaptadores/entrada/cli.py   un solo verbo: auditar
```

`Dato`, `Traza` y el log de auditoria se reusan del nucleo del A1 via
`domain/valores.py` y `puertos/__init__.py`: si el nucleo se extrae a un paquete
comun, solo cambian esos dos archivos.
