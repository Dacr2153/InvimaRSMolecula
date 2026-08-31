# Hackatón INVIMA — Arquitectura del sistema de agentes

**Reto:** Registro Sanitario de Molécula (innovador) / Registro Sanitario (molécula conocida)
**Pista:** Híbrida (A + B)
**Presupuesto IA:** USD 5 en créditos GCP

---

## 1. Tesis

El Invima señaló el problema en el pie de página de su propia diapositiva:

- **Pista A:** "la mayoría de moléculas nuevas ya fueron aprobadas en 20 a 50 países por
  agencias de referencia (FDA, EMA, Health Canada, Reino Unido)" → *reliance regulatorio*.
- **Pista B:** "existe un vacío de especialistas clínicos en la Comisión Revisora".

El evaluador debe juzgar una molécula sin el subespecialista al lado, mientras la evidencia
que necesita ya existe, es pública, y está en inglés repartida en miles de páginas.

**El sistema no decide. Traduce, estructura, contrasta y cita. El evaluador decide.**

---

## 2. Reparto de pistas

- **PISTA B (autonomía, bajo riesgo)** = la *puerta de entrada*. Tareas conocidas,
  deterministas y auditables: parseo del CTD, verificación de completitud, identificación
  molecular, detección de duplicidad. Uso elegible explícito de las reglas:
  "detección de expedientes incompletos antes del reparto".
- **PISTA A (escalar comprensión humana)** = el *núcleo de valor*. Dossier de evidencia
  comparada contra agencias de referencia. Uso elegible explícito:
  "comparación de un dossier contra decisiones de agencias de referencia" + art. 7.4
  (traducción y verificación de documentos públicos extranjeros).

---

## 3. Pipeline de agentes

### Etapa B — Ingesta (autónoma, bajo riesgo)

| # | Agente | Modelo | Función | Salida |
|---|--------|--------|---------|--------|
| B1 | Recepción | Flash | Parsea el PDF del dossier, clasifica páginas por módulo CTD (M1–M5), construye índice de folios | `indice_ctd.json` |
| B2 | Completitud | Flash | Contrasta contra checklist normativo de requisitos documentales | `faltantes.json` |
| B3 | Identidad molecular | Flash + APIs | Extrae DCI/INN, CAS, código ATC; resuelve contra ChEMBL / PubChem / UniProt | `molecula.json` |
| B4 | Duplicidad | Flash | Detecta trámites conexos o repetidos sobre la misma molécula | `conexos.json` |

Salida de etapa: **semáforo de admisibilidad documental**. No es concepto técnico —
es "faltan los folios X, Y, Z". Verificable a ojo por el funcionario.

### Etapa A — Reliance (apoyo, riesgo medio)

| # | Agente | Modelo | Función | Salida |
|---|--------|--------|---------|--------|
| A1 | Rastreo regulatorio | Flash + APIs | Busca la molécula en OpenFDA, EPAR de EMA, Health Canada, MHRA | `agencias_raw.json` |
| A2 | Extracción de decisiones | Flash | De cada agencia: indicación aprobada, posología, población, contraindicaciones, advertencias, condiciones impuestas | `decisiones.json` |
| A3 | Contraste | **Pro** | Diff dossier ↔ agencias. ¿Misma indicación? ¿Misma dosis? ¿Qué condicionó FDA que aquí no aparece? ¿Señales post-mercado? | `discrepancias.json` |
| A4 | Dossier de evidencia | **Pro** | Redacta en español el informe navegable. Cada afirmación con cita a folio o URL de fuente | `dossier_evidencia.md` |

**Regla dura:** ninguna salida contiene "aprobar", "rechazar", "cumple" ni un puntaje.
Solo evidencia, procedencia y discrepancias señaladas.

### Capa transversal — Trazabilidad

Cada agente escribe a un log append-only: entrada, salida, modelo, versión de prompt,
timestamp. Cada revisión humana (aceptar / corregir / rechazar) se registra con el ítem
afectado. El expediente queda reconstruible de punta a punta.

---

## 4. Humano en el circuito

| Punto | Qué recibe el funcionario | Qué puede hacer |
|-------|---------------------------|-----------------|
| Tras B2 | Lista de folios faltantes | Confirmar, marcar falso positivo, agregar faltantes no detectados |
| Tras B3 | Identificación molecular propuesta | Corregir DCI/ATC; define la ruta (innovador vs conocido) |
| Tras A3 | Mapa de discrepancias, ítem por ítem | Aceptar, corregir, rechazar o marcar "requiere concepto de especialista" |
| Tras A4 | Dossier de evidencia con citas | Editar libremente; el documento final es suyo |
| Decisión | — | **La motivación y la firma del acto son exclusivamente del evaluador** |

Nada avanza de etapa sin visto humano. El sistema no tiene una ruta de "auto-aprobar".

---

## 5. Clasificación de riesgo (obligatoria en la propuesta)

| Criterio | Nivel | Justificación |
|----------|-------|---------------|
| Efecto sobre derechos | Medio | Apoyo a decisión, con validación humana obligatoria |
| Autonomía | Medio | Recomendación sujeta a validación; sin decisión automatizada |
| Datos personales | Bajo | Dossieres técnicos, datos sintéticos; sin datos sensibles ni de NNA |
| Impacto en salud pública | Medio | Indirecto — mediado por la decisión del evaluador |
| Alcance | Medio | Colectivo determinado (trámites de registro sanitario) |
| Reversibilidad | Bajo | Toda salida es revisable y editable antes de la decisión |

**Clasificación final: RIESGO MEDIO** (regla del nivel más alto identificado).
Controles proporcionales: HITL en 4 puntos, trazabilidad total, citación obligatoria
de fuente, prohibición de salidas conclusivas.

---

## 6. Presupuesto (USD 5)

**Desarrollo: costo cero.** Antigravity (gratis) + AI Studio capa gratuita.
Las APIs de OpenFDA, ChEMBL, PubChem, UniProt y EMA son gratuitas: descargar
la data de referencia **una vez** a disco, nunca consultarla dentro del loop.

**Prohibido con este presupuesto:**
- Document AI (cobra por página; un CTD son cientos) → Gemini lee PDF nativo
- Vertex AI Search (cobra por índice almacenado, corre el reloj) → FAISS/Chroma local
- Pasarle el dossier completo a Pro repetidamente

**Reparto:** Flash para todo lo mecánico (B1–B4, A1, A2). Pro solo para A3 y A4,
y alimentado únicamente con las secciones que Flash marcó como relevantes.
Modo batch (50% descuento) para corridas no interactivas.

**Demo:** resultados precalculados en JSON. La presentación lee de ahí — instantánea,
sin red, sin rate limit, sin gasto frente al jurado. Un botón de "corrida en vivo"
para un caso pequeño y controlado.

Alerta de presupuesto en USD 3.

---

## 7. Entregables de gobernanza (35% del puntaje)

- [ ] Evaluación de Impacto Algorítmico preliminar (12 puntos, plantilla Anexo Técnico)
- [ ] Clasificación de riesgo con justificación (§5 de este documento)
- [ ] Declaración de Propiedad Intelectual, Componentes de Terceros y Licencia de Uso
- [ ] Inventario de licencias: modelos, APIs, open source
- [ ] Diseño del aviso al administrado + canal de solicitud de revisión humana
- [ ] Análisis de sesgo: riesgo de sobre-confianza en agencias del norte global;
      mitigación → el sistema muestra la evidencia, no pondera países

---

## 8. Pendientes

- [ ] Confirmar saldo y expiración real del crédito en consola de Billing
- [ ] Conseguir el dataset sintético del Invima
- [ ] Pedir acceso EAP a Co-Scientist al equipo de Google en sitio
- [ ] Instalar Antigravity + Science Skills
