// Cliente HTTP tipado. Toda respuesta de error del backend viaja en {detail}.
import type {
  Catalogos,
  Consulta,
  ConsultaSugerida,
  DocumentoCargado,
  EnlaceEvidencia,
  ExpedienteDetalle,
  FuenteExterna,
  InformeAgente,
  ItemBandeja,
  ItemChecklist,
  ParchesSolicitud,
  RespuestaDecision,
  ResultadoRadicacion,
  SentidoDecision,
  Solicitud,
} from './tipos';

export const BASE_URL: string = import.meta.env.VITE_API_URL ?? '/api';

export class ErrorApi extends Error {
  readonly estadoHttp: number;
  constructor(mensaje: string, estadoHttp: number) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.estadoHttp = estadoHttp;
  }
}

async function leerDetalle(res: Response): Promise<string> {
  try {
    const cuerpo: unknown = await res.json();
    if (cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo) {
      const detalle = (cuerpo as { detail: unknown }).detail;
      if (typeof detalle === 'string') return detalle;
      return JSON.stringify(detalle);
    }
  } catch {
    // el cuerpo no era JSON; se cae al mensaje generico
  }
  return `El servidor respondió ${res.status} ${res.statusText}`.trim();
}

type Opciones = {
  metodo?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  cuerpo?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
};

async function pedir<T>(ruta: string, opciones: Opciones = {}): Promise<T> {
  const { metodo = 'GET', cuerpo, formData, signal } = opciones;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${ruta}`, {
      method: metodo,
      signal,
      headers: formData ? undefined : cuerpo !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: formData ?? (cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined),
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new ErrorApi('No se pudo contactar el servidor. Verifica la conexión.', 0);
  }

  if (!res.ok) throw new ErrorApi(await leerDetalle(res), res.status);
  if (res.status === 204) return undefined as T;

  const texto = await res.text();
  if (!texto) return undefined as T;
  return JSON.parse(texto) as T;
}

// ---------- Catalogos ----------

export const obtenerCatalogos = (signal?: AbortSignal) => pedir<Catalogos>('/catalogos', { signal });

// ---------- Radicacion ----------

export const crearSolicitud = (solicitanteNit?: string) =>
  pedir<Solicitud>('/solicitudes', { metodo: 'POST', cuerpo: solicitanteNit ? { solicitanteNit } : {} });

export const obtenerSolicitud = (id: string, signal?: AbortSignal) =>
  pedir<Solicitud>(`/solicitudes/${encodeURIComponent(id)}`, { signal });

export const parcharSolicitud = (id: string, parches: ParchesSolicitud) =>
  pedir<Solicitud>(`/solicitudes/${encodeURIComponent(id)}`, { metodo: 'PATCH', cuerpo: parches });

export function subirDocumento(
  id: string,
  requeridoId: string,
  archivo: File,
  alProgresar?: (porcentaje: number) => void,
): Promise<DocumentoCargado> {
  // XMLHttpRequest en vez de fetch: es la unica forma de leer progreso de subida.
  return new Promise((resolver, rechazar) => {
    const xhr = new XMLHttpRequest();
    const url = `${BASE_URL}/solicitudes/${encodeURIComponent(id)}/documentos/${encodeURIComponent(requeridoId)}`;
    xhr.open('POST', url);

    xhr.upload.onprogress = (ev) => {
      if (alProgresar && ev.lengthComputable) {
        alProgresar(Math.round((ev.loaded / ev.total) * 100));
      }
    };
    xhr.onerror = () => rechazar(new ErrorApi('No se pudo contactar el servidor durante la carga.', 0));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolver(JSON.parse(xhr.responseText) as DocumentoCargado);
        } catch {
          rechazar(new ErrorApi('El servidor devolvió una respuesta ilegible.', xhr.status));
        }
        return;
      }
      let mensaje = `El servidor respondió ${xhr.status}`;
      try {
        const cuerpo: unknown = JSON.parse(xhr.responseText);
        if (cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo) {
          const detalle = (cuerpo as { detail: unknown }).detail;
          mensaje = typeof detalle === 'string' ? detalle : JSON.stringify(detalle);
        }
      } catch {
        // sin cuerpo util
      }
      rechazar(new ErrorApi(mensaje, xhr.status));
    };

    const fd = new FormData();
    fd.append('file', archivo, archivo.name);
    xhr.send(fd);
  });
}

export const eliminarDocumento = (id: string, requeridoId: string) =>
  pedir<void>(`/solicitudes/${encodeURIComponent(id)}/documentos/${encodeURIComponent(requeridoId)}`, {
    metodo: 'DELETE',
  });

export const radicarSolicitud = (id: string) =>
  pedir<ResultadoRadicacion>(`/solicitudes/${encodeURIComponent(id)}/radicar`, { metodo: 'POST' });

export const agregarEnlace = (id: string, url: string, titulo = '') =>
  pedir<EnlaceEvidencia>(`/solicitudes/${encodeURIComponent(id)}/enlaces`, {
    metodo: 'POST',
    cuerpo: { url, titulo },
  });

export const eliminarEnlace = (id: string, enlaceId: string) =>
  pedir<void>(
    `/solicitudes/${encodeURIComponent(id)}/enlaces/${encodeURIComponent(enlaceId)}`,
    { metodo: 'DELETE' },
  );

// ---------- Evaluacion ----------

export const listarExpedientes = (signal?: AbortSignal) => pedir<ItemBandeja[]>('/expedientes', { signal });

export const obtenerExpediente = (radicado: string, signal?: AbortSignal) =>
  pedir<ExpedienteDetalle>(`/expedientes/${encodeURIComponent(radicado)}`, { signal });

export const registrarDecision = (
  radicado: string,
  datos: { usuario: string; sentido: SentidoDecision; observaciones?: string; camposCorregidos?: Record<string, string> },
) => pedir<RespuestaDecision>(`/expedientes/${encodeURIComponent(radicado)}/decision`, { metodo: 'POST', cuerpo: datos });

export const obtenerChecklist = (radicado: string, signal?: AbortSignal) =>
  pedir<ItemChecklist[]>(`/expedientes/${encodeURIComponent(radicado)}/checklist`, { signal });

export const crearItemChecklist = (radicado: string, texto: string) =>
  pedir<ItemChecklist>(`/expedientes/${encodeURIComponent(radicado)}/checklist`, { metodo: 'POST', cuerpo: { texto } });

export const marcarItemChecklist = (radicado: string, id: string, verificado: boolean, usuario: string) =>
  pedir<ItemChecklist>(`/expedientes/${encodeURIComponent(radicado)}/checklist/${encodeURIComponent(id)}`, {
    metodo: 'PATCH',
    cuerpo: { verificado, usuario },
  });

export const eliminarItemChecklist = (radicado: string, id: string) =>
  pedir<void>(`/expedientes/${encodeURIComponent(radicado)}/checklist/${encodeURIComponent(id)}`, { metodo: 'DELETE' });

export const obtenerFuentes = (radicado: string, signal?: AbortSignal) =>
  pedir<FuenteExterna[]>(`/expedientes/${encodeURIComponent(radicado)}/fuentes`, { signal });

export const vincularFuente = (radicado: string, id: string, vinculada: boolean, usuario: string) =>
  pedir<FuenteExterna>(`/expedientes/${encodeURIComponent(radicado)}/fuentes/${encodeURIComponent(id)}/vinculo`, {
    metodo: 'POST',
    cuerpo: { vinculada, usuario },
  });

export const obtenerConsultasSugeridas = (signal?: AbortSignal) =>
  pedir<ConsultaSugerida[]>('/consultas/sugeridas', { signal });

export const obtenerConsultas = (radicado: string, signal?: AbortSignal) =>
  pedir<Consulta[]>(`/expedientes/${encodeURIComponent(radicado)}/consultas`, { signal });

export const crearConsulta = (radicado: string, pregunta: string, usuario?: string) =>
  pedir<Consulta>(`/expedientes/${encodeURIComponent(radicado)}/consultas`, {
    metodo: 'POST',
    cuerpo: usuario ? { pregunta, usuario } : { pregunta },
  });

export const obtenerInformesAgentes = (radicado: string, signal?: AbortSignal) =>
  pedir<InformeAgente[]>(`/expedientes/${encodeURIComponent(radicado)}/agentes`, { signal });
