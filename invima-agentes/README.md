# invima-agentes

Sistema de agentes de IA para el tramite de **Registro Sanitario de Molecula**.
Hackaton INVIMA del Futuro — pista hibrida (A: escalar la comprension humana,
B: habilitar flujos autonomos de bajo riesgo).

> Todos los datos de este repositorio son **sinteticos**. No hay expedientes,
> titulares ni moleculas reales.

---

## El principio que ordena el diseno

El art. 7.1 de la Resolucion 2026025611 prohibe usar IA para sustituir la
decision administrativa. Aqui eso no es una advertencia en la documentacion:
esta impuesto por el codigo.

**1. El modelo solo transcribe.** El LLM vive detras de `ExtractorMetadatosPort`
y su contrato es "texto a estructura". No razona, no concluye, no redacta
motivaciones. Las decisiones que importan — si el pago cuadra, si la molecula
esta en normas, que ruta corresponde, si la indicacion coincide — son funciones
puras en `domain/servicios/`, sin red y sin modelo. Un evaluador puede leerlas.

**2. Ningun dato viaja desnudo.** Todo campo es un `Dato[T]` que carga su origen
(`EXTRAIDO`, `BUSQUEDA`, `RECOMENDACION`, `NO_SUMINISTRADO`) y su trazabilidad
al folio o a la URL. Construir el payload sin declarar la procedencia es
imposible por tipo.

**3. Sin persona no hay enrutamiento.** `EstadoExpediente` no tiene transicion de
`PENDIENTE_VALIDACION_HUMANA` a `ENRUTADO`. Solo la abre una `DecisionHumana`
con nombre y timestamp. El agente carece de la capacidad tecnica de auto-aprobar,
y hay un test que lo comprueba (`tests/dominio/test_estados.py`).

---

## Arquitectura

```
domain/       Entidades, maquina de estados y los cuatro motores de decision.
              Sin I/O, sin red, sin LLM. Aqui esta el valor y aqui estan los tests.
puertos/      Protocols. Lo que el dominio necesita del exterior.
aplicacion/   El caso de uso: nueve pasos, cada uno emitiendo auditoria.
adaptadores/  Docling, Gemini, openFDA, ClinicalTrials.gov, SQLite, CLI.
```

Cambiar de Gemini a otro modelo, o de SQLite a PostgreSQL, es escribir un
adaptador. El nucleo no se entera. Para una entidad publica eso significa no
quedar cautiva de un proveedor.

---

## Agente A1-RCE: Receptor, Clasificador y Enrutador

```
1. Ingesta                Docling local (MIT). Markdown con trazabilidad de folio.
2. Metadatos ASS-RSA-FM113  Gemini Flash, temperature=0, salida contra esquema.
3. Validacion del pago    Motor puro. Si no cuadra, corta aqui.
4. Autovalidacion         CPP/CVL, matriz de agencias, NCT declarados.
5. Reliance               openFDA, EMA, ClinicalTrials.gov. Todo cacheado.
6. Contraste              Indicacion solicitada vs. aprobada afuera.
7. Bypass check           Cruce contra el Manual de Normas Farmacologicas.
8. Enrutamiento           Tabla de decision: EXPRESS o ESTANDAR.
9. Entrega al evaluador   PENDIENTE_VALIDACION_HUMANA. Fin del agente.
```

El paso 3 corta el flujo antes de gastar un token en busquedas: control de costo
y regla de negocio en el mismo punto.

---

## Uso

```bash
uv venv --python 3.12
uv pip install -e '.[dev,fixtures]'

python tools/generar_dossier_sintetico.py

# Corrida offline: sin red, sin costo, deterministica
invima-a1 procesar data/fixtures/dossier_corazilimab --radicado 2026-REG-001

# El expediente queda detenido. Solo un evaluador lo mueve:
invima-a1 decidir 2026-REG-001 --usuario evaluador.perez --sentido aprobar

pytest -q
```

Para una corrida real contra Gemini y fuentes publicas:

```bash
export GEMINI_API_KEY=...
invima-a1 procesar data/fixtures/dossier_corazilimab --no-offline
```

Se corre **una vez** por molecula: despues el cache en `data/cache/` la sirve gratis.

---

## Dossieres sinteticos

| Carpeta | Que ejercita |
|---|---|
| `dossier_corazilimab` | Camino feliz: molecula nueva, pago conforme, ruta EXPRESS |
| `dossier_pago_inconsistente` | El valor no corresponde a la tarifa. Suspende sin buscar nada |
| `dossier_metformina` | Molecula en el Manual. Ruta ESTANDAR |
| `dossier_discrepancia_declarativa` | Declara "no incluida" pero el Manual la registra. Alerta |
| `dossier_indicacion_ampliada` | Pide mas alcance del aprobado por FDA. El contraste lo marca |
| `dossier_inyeccion_prompt` | Trae una instruccion incrustada. Se detecta y no altera la ruta |

---

## Costo

El presupuesto del evento son USD 5. Las decisiones que lo respetan:

- **Docling local** para OCR en vez de un servicio que cobra por pagina.
- **Cache en disco** sobre cada fuente externa: una consulta por molecula, nunca dos.
- **Flash** para toda extraccion. El A1 transcribe; no necesita un modelo de razonamiento.
- **Adaptadores locales** para desarrollo y pruebas: los 61 tests corren sin red y sin costo.
- **Corte temprano** cuando el pago no cuadra.

---

## Licencias de terceros

| Componente | Licencia |
|---|---|
| Docling | MIT |
| pydantic, httpx, typer, rich | MIT |
| openFDA, ClinicalTrials.gov | Dominio publico (datos del gobierno de EE.UU.) |
| Gemini API | Terminos de servicio de Google |
