# A4-ECEF — Auditoria de evidencia cientifica y clinica (Modulos 4, 5 y 7)

Audita la evidencia no clinica (farmacocinetica, toxicologia de dosis repetidas,
toxicologia reproductiva), el ensayo clinico pivotal, la inmunogenicidad y el
informe periodico de beneficio-riesgo. Cruza el organo blanco animal contra las
senales poscomercializacion y coteja esas senales contra el plan de gestion de
riesgos del solicitante.

## Como correrlo

```
PYTHONPATH=src python -m invima_a4.adaptadores.entrada.cli \
    data/fixtures/dossier_corazilimab/modulo45_evidencia.md \
    --radicado 20268011234 --salida evidencia.json
```

Offline por defecto. `pytest tests/a4` corre la suite sobre el mismo camino.

## La decision central: el agente no construye el balance

El borrador de especificacion terminaba en `"clasificacion_balance": "FAVORABLE
CONDICIONADO"` y `"recomendacion_regulatoria": "APROBACION CONDICIONADA"` con
cinco condiciones. Ponderar beneficio contra riesgo **es** el acto de juicio que
define a la Comision Revisora; un agente que lo hace no la asiste, la sustituye,
y el articulo 7.1 de la Resolucion 2026025611 lo prohibe.

Lo que si es mecanizable es **ordenar la mesa**: los beneficios que el
expediente declara con su contraste y su folio, los riesgos con su frecuencia y
la mitigacion que el propio solicitante propone, aparte lo que quedo sin dato, y
cada hallazgo grave traducido en una pregunta concreta que el evaluador tiene
que responder. La suma no la hace el agente. `insumos_para_el_balance` tiene
exactamente cinco claves y ninguna es un veredicto.

La `guardia lexica` del nucleo recorre el payload y aborta la corrida con
`SalidaConclusivaError` si aparece vocabulario decisorio. En este agente esa
barrera importa mas que en ningun otro: es el que mas cerca tiene la tentacion
de concluir.

## Lo que el agente verifica y el borrador daba por bueno

**Los numeros del expediente contra si mismos.** Un valor derivado -- una tasa
por 1000 pacientes-ano, un porcentaje de incidencia, una diferencia entre
brazos, un margen de seguridad, la suma de los brazos -- se recalcula desde sus
componentes. Sobre el fixture eso destapa que **las tres tasas del informe
periodico estan declaradas diez veces por debajo** de lo que dan sus propios
casos y su propia exposicion, y que la incidencia general declarada solo se
reproduce dividiendo por pacientes-ano en vez de por pacientes: el informe
presenta como proporcion de personas lo que es una tasa por tiempo de
exposicion. El agente reporta los dos numeros y el factor entre ellos; no
corrige el declarado.

**El alfa preespecificado.** Sin el no hay contra que juzgar un valor p, y el
agente **no asume 0.05**: asumirlo es escribirle el protocolo al solicitante.

**El control de multiplicidad.** Varios desenlaces secundarios declarados
significativos sin describir como se controlo la multiplicidad es un hallazgo,
no un detalle: con cada contraste adicional crece la probabilidad de al menos un
falso positivo.

**Un valor p no significativo no demuestra ausencia de efecto.** El expediente
lee "p = 0.15" como "sin diferencia entre brazos" y "p = 0.52" como "sin impacto
en la eficacia". Sin intervalo de confianza no se sabe que magnitud de
diferencia sigue siendo compatible con los datos, que es justo lo que el
evaluador necesita.

**Otros:** NOAEL por debajo del LOAEL; organo blanco sin reversibilidad
declarada (un hallazgo asi no distingue alteracion transitoria de dano
establecido); malformaciones descritas sin frecuencia por grupo de dosis (sin
ella no hay relacion dosis-respuesta que leer); neutralizantes que no pueden
superar en numero a los anti-farmaco; muertes con investigacion abierta tratadas
como incertidumbre y no como dato cerrado.

## Dos cosas que el agente se niega a hacer

**No asigna la categoria de riesgo en embarazo.** El borrador ordenaba
"asignar categoria (A, B, C, D, X)". Es un juicio toxicologico con consecuencia
directa de etiqueta. El agente extrae la que el expediente declara y, si no
esta, lo reporta ausente.

**No afirma relacion causal entre el hallazgo animal y la senal humana.** El
borrador escribia "CORRELACION DIRECTA". El agente reporta que el organo blanco
no clinico y el sistema afectado por la senal **son el mismo**, dice que la
coincidencia se determino por termino sobre una tabla de sinonimos declarada en
el codigo, y deja el juicio al evaluador. El mismo cuidado gobierna el cotejo
contra el plan de gestion de riesgos: el hallazgo dice "no se hallo mencion",
que la busqueda fue lexica, y que corresponde confirmarla en el documento antes
de requerirla al solicitante.

## Estructura

```
domain/servicios/preclinico.py            PK, toxicologia, reproductiva
domain/servicios/ensayo_pivotal.py        PICO, aritmetica de brazos, alfa,
                                          multiplicidad, poblaciones de analisis
domain/servicios/inmunogenicidad.py       ADA/NAb y lectura de la no significancia
domain/servicios/farmacovigilancia.py     PBRER, tasas, denominador alterno
domain/servicios/cruce_toxico_clinico.py  organo blanco <-> senal <-> PGR
domain/servicios/balance.py               insumos y preguntas abiertas
puertos/expediente_evidencia.py           un solo puerto propio
adaptadores/entrada/cli.py                un solo verbo: evaluar
```

El nucleo compartido (`invima_nucleo`) aporta `Medicion`, `Especificacion`,
`Hallazgo`, `contrastar`, el recalculo aritmetico, la guardia lexica y la
lectura de Markdown. El A3 usa el mismo nucleo, y `Dato`/`Traza`/log de
auditoria siguen viniendo del A1.
