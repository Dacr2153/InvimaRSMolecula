# invima-gobernanza

Entregables juridicos y de gobernanza de la propuesta para la Hackaton INVIMA
del Futuro — reto de Registro Sanitario de Molecula.

El codigo vive en [`invima-agentes`](https://github.com/InvimaRSMolecula/invima-agentes).

## Por que este repositorio existe

En la metodologia de evaluacion, Seguridad (15%) y Cumplimiento de requisitos
legales (15%) suman 30% del puntaje, y la Etapa 1 es de admisibilidad: una
propuesta que incumpla las condiciones de supervision humana, trazabilidad o
informacion no llega a puntuarse, por buena que sea tecnicamente.

Estos documentos no son anexos del prototipo. Son parte del entregable.

## Contenido

| Documento | Estado |
|---|---|
| `docs/arquitectura.md` | Listo |
| `docs/clasificacion-riesgo.md` | Pendiente |
| `docs/evaluacion-impacto-algoritmico.md` | Pendiente |
| `docs/declaracion-propiedad-intelectual.md` | Pendiente (requiere firma) |
| `docs/inventario-licencias.md` | Pendiente |
| `docs/aviso-al-administrado.md` | Pendiente |
| `docs/analisis-sesgo.md` | Pendiente |

## Clasificacion preliminar de riesgo

**RIESGO MEDIO**, por la regla del nivel mas alto identificado. La justificacion
criterio por criterio esta en `docs/arquitectura.md`, seccion 5.

La clasificacion como riesgo medio no exime de controles: el sistema incorpora
supervision humana obligatoria en cuatro puntos, trazabilidad append-only,
citacion obligatoria de fuente y prohibicion tecnica de salidas conclusivas.
