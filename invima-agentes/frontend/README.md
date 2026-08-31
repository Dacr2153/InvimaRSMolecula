# Radicación — Flujo Solicitante (frontend)

Implementación del diseño `Radicacion - Flujo Solicitante.dc.html` (Claude Design handoff)
en React + TypeScript + Vite. Solo UI: el estado vive en el cliente y los catálogos
están en `src/data.ts`, listos para reemplazarse por llamadas al backend.

## Correr con un solo comando

```bash
docker compose up --build
```

Luego abrir http://localhost:8080

Para detener: `docker compose down`

## Desarrollo local (sin Docker)

```bash
npm install
npm run dev     # http://localhost:5173
```

## Estructura

```
src/
  App.tsx                 estado del wizard (paso, selecciones, documentos)
  data.ts                 catálogos: trámites, productos, campos, módulos CTD, tarifas
  styles.css              tokens de diseño (colores, tipografías) + estilos
  components/             Sidebar, Topbar, OptionCard
  steps/                  las 5 pantallas del flujo
```

## Los 5 pasos

1. **Tipo de solicitud** — trámite (nuevo/renovación/modificación/ampliación) y tipo de producto.
2. **Datos del expediente** — campos generales del producto y responsables (solo lectura por ahora).
3. **Documentos** — módulos 1 a 5 del CTD, PGR y anexos; clic en una fila alterna PENDIENTE/CARGADO.
4. **Pago** — tarifa 3-07-1, método de pago y zona de comprobante.
5. **Confirmación** — número de radicado, estado y próximos pasos.

La barra lateral permite volver a cualquier paso ya alcanzado; los pasos no alcanzados
quedan deshabilitados.

## Pendiente para la integración con backend

- `src/data.ts` → endpoints de catálogos.
- Paso 2: convertir los campos en inputs reales con validación.
- Paso 3: carga real de archivos (multipart) en lugar del toggle simulado.
- Paso 4: pasarela de pago y subida del comprobante.
- Paso 5: número de radicado y fecha devueltos por el servidor.
