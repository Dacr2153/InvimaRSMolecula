# Agente A2-VICR: Validador de Integridad y Clasificador Regulatorio

Valida la documentacion juridica del Modulo 1 y clasifica el producto. **No
reparte expedientes**: prepara el dictamen y lo entrega al Coordinador de Grupos.

## Que hace, y que deliberadamente no hace

El A2 aporta dos cosas que el A1 no mira:

1. **Validacion legal del Modulo 1** — apostilla y traductor del poder especial,
   vigencia del certificado de existencia, vigencia y correspondencia de los
   certificados de BPM, y coherencia del NIT entre los tres documentos.
2. **Clasificacion taxonomica** — dimension del producto (sintesis quimica,
   biologico o vacuna) y ruta de estudio del Decreto 1782 de 2014.

**No** vuelve a determinar el estatus frente al Manual de Normas Farmacologicas
ni la ruta EXPRESS/ESTANDAR. Eso ya lo hacen `motor_normativo.py` y
`enrutador.py` en el A1, con pruebas. El A2 los hereda del payload y los publica
bajo `heredado_del_a1` para que el coordinador vea todo junto. Dos
implementaciones de la misma regla es lo que este agente evita.

## Coordinacion con el A1

```
invima-a1 procesar <dossier> --radicado R-001    ->  PENDIENTE_VALIDACION_HUMANA
invima-a2 dictaminar R-001                       ->  PENDIENTE_VALIDACION_COORDINADOR
                                                     o RETENIDO_POR_ALERTA_CRITICA
```

Tres reglas sostienen el encaje:

- **El A2 consume el payload del A1**, detras de `ExpedienteA1Port`. No vuelve a
  parsear el dossier ni a extraer el ASS-RSA-FM113. El A1 puede correr en otra
  maquina o ser reemplazado sin que el A2 se entere.
- **El corte temprano del A1 se respeta aguas abajo.** Si el A1 suspendio por
  inconsistencia de pago, el A2 se niega a correr con `ExpedienteNoValidableError`.
  Un tramite que no puede repartirse no justifica extraer sus documentos legales.
- **Mismo radicado, mismo log.** El A2 escribe a `data/auditoria.jsonl` con actor
  `AGENTE_A2_VICR`. El expediente se reconstruye leyendo un solo archivo.

El nucleo (`Dato[T]`, `Traza`, `DecisionHumana`, `sanitizador`, `normalizacion`)
se reusa de `invima_a1`, nunca se redefine.

## Las mismas invariantes, en la etapa siguiente

**Procedencia obligatoria.** Que la apostilla este presente no es un booleano
suelto: es un `Dato[bool]` que apunta al folio donde se leyo el sello.

**Sin persona no hay reparto.** `EstadoDictamen` no tiene transicion automatica a
`REPARTIDO`. Ni siquiera desde `RETENIDO_POR_ALERTA_CRITICA`: levantar una
retencion es una decision firmada del coordinador.

**Barrera de salida conclusiva.** `dto.py` recorre el payload y falla con
`SalidaConclusivaError` si un valor contiene vocabulario decisorio ("aprobado",
"cumple", "procedente"). Las alertas SI pueden decir "no acredita apostilla":
describir un hallazgo no es calificar un tramite.

## Por que no se compara byte a byte

La especificacion original pedia que los nombres de titular, fabricante e
importador coincidieran exactamente entre documentos. La misma planta aparece
como `CellGenix Biologics S.A.`, `CELLGENIX BIOLOGICS SA` y
`Cellgenix Biologics, S.A.` en tres certificados emitidos por tres autoridades.
Comparar byte a byte produce falsos positivos en masa y entrena al evaluador a
ignorar las alertas.

`razon_social.py` aplica el mismo criterio que el A1 uso para las DCI en
`normalizacion.py`: se compara la forma canonica. El digito de verificacion del
NIT si se conserva, porque dos NIT que solo difieren en el son dos contribuyentes
distintos.

## Severidad y su unico efecto tecnico

Una alerta `CRITICA` impide que el agente recomiende repartir el expediente. No
lo rechaza ni lo devuelve: lo retiene y pone los hallazgos a la vista. Rechazar
seria decidir.

## Dossieres sinteticos

`tools/generar_anexo_legal.py` agrega un `modulo1_legal.md` a cada dossier. Los
defectos se reparten a proposito, uno por carpeta: un validador que solo ve
documentacion conforme no demuestra nada.

| Carpeta | Que ejercita |
|---|---|
| `dossier_corazilimab` | Camino feliz. Biologico en CHO con M4 y M5 -> Expediente Completo |
| `dossier_metformina` | Sintesis quimica. Razon social con distinta forma societaria entre BPM y matriz: no debe alertar |
| `dossier_pago_inconsistente` | El A1 lo suspende. El A2 se niega a correr |
| `dossier_discrepancia_declarativa` | CCB de 46 dias -> `CCB_VENCIDA` |
| `dossier_indicacion_ampliada` | Poder sin apostilla ni traductor. Con producto de referencia -> Comparabilidad |
| `dossier_inyeccion_prompt` | NIT discrepante, BPM vencida, BPM ajeno a la matriz e instruccion incrustada en el poder |
