// Tipos del contrato de la API (infra/CONTRATO-API.md).
// Ningun endpoint devuelve un concepto: no hay campos de aprobacion ni puntaje.
// El unico sentido de decision lo escribe una persona en POST /decision.

export type TipoTramite = { id: string; etiqueta: string; descripcion: string };
export type TipoProducto = { id: string; etiqueta: string; descripcion: string };
export type Tarifa = { codigo: string; concepto: string; valor: string | number };
export type MetodoPago = { id: string; etiqueta: string };

export type DocumentoRequerido = {
  id: string;
  nombre: string;
  obligatorio: boolean;
  folioDestino?: string;
};

export type ModuloCtd = {
  id: string;
  titulo: string;
  documentos: DocumentoRequerido[];
};

export type Catalogos = {
  tiposTramite: TipoTramite[];
  tiposProducto: TipoProducto[];
  tarifas: Tarifa[];
  metodosPago: MetodoPago[];
  modulosCtd: ModuloCtd[];
};

// Casi todo lo que declara el solicitante es texto, pero la declaracion sobre
// normas farmacologicas es un si/no. Viaja como booleano de verdad y no como
// la cadena "false", que en Python seria un valor verdadero.
export type DatosDeclarados = Record<string, string | boolean>;

export type DocumentoCargado = {
  requeridoId: string;
  nombreArchivo: string;
  tamanoBytes: number;
  sha256: string;
  cargadoEn: string;
};

export type EnlaceEvidencia = {
  id: string;
  url: string;
  titulo: string;
  tipo: 'ENSAYO_CLINICO' | 'AGENCIA_REFERENCIA' | 'PUBLICACION' | 'OTRO';
  referencia: string;
  creadoEn: string;
};

export type EstadoSolicitud = 'BORRADOR' | 'RADICADA' | 'ANULADA';

export type Solicitud = {
  id: string;
  estado: EstadoSolicitud;
  tipoTramite: string | null;
  tipoProducto: string | null;
  datosDeclarados: DatosDeclarados;
  tarifaCodigo: string | null;
  metodoPago: string | null;
  comprobante: string | null;
  valorPagado: string | null;
  fechaPago: string | null;
  radicado: string | null;
  radicadaEn: string | null;
  documentos: DocumentoCargado[];
  enlaces: EnlaceEvidencia[];
};

export type ParchesSolicitud = {
  tipoTramite?: string;
  tipoProducto?: string;
  datosDeclarados?: DatosDeclarados;
  tarifaCodigo?: string;
  metodoPago?: string;
  comprobante?: string;
  valorPagado?: string;
  fechaPago?: string;
};

export type InconsistenciaPago = {
  campo: string;
  esperado: string | number | null;
  encontrado: string | number | null;
  mensaje?: string | null;
};

export type ValidacionPago = {
  verificado: boolean;
  resultado: string;
  inconsistencias: InconsistenciaPago[];
};

export type ResultadoRadicacion = {
  radicado: string;
  fechaRadicacion: string;
  estado: string;
  suspendido: boolean;
  tipoTramite: string;
  tipoProducto: string;
  validacionPago: ValidacionPago | null;
  advertencia: string | null;
};

// ---------- Evaluacion ----------

export type ItemBandeja = {
  radicado: string;
  producto: string;
  principioActivo: string;
  titular: string;
  tramite: string;
  estado: string;
  estadoLabel: string;
  diasEnCola: number;
  rutaRecomendada: string | null;
};

export type DocumentoExpediente = {
  requeridoId: string;
  nombre: string;
  modulo: string;
  nombreArchivo: string;
  tamanoBytes: number;
  sha256: string;
  cargadoEn: string;
};

export type SentidoDecision = 'APROBAR_ENRUTAMIENTO' | 'CORREGIR_Y_APROBAR' | 'DEVOLVER';

export type DecisionHumana = {
  usuario: string;
  sentido: SentidoDecision;
  momento: string;
  observaciones?: string | null;
};

export type EventoExpediente = {
  momento: string;
  tipo: string;
  accion: string;
  resultado: string;
  actor: string;
};

export type ExpedienteDetalle = {
  radicado: string;
  estado: string;
  estadoLabel: string;
  producto: string;
  principioActivo: string;
  titular: string;
  tramite: string;
  fechaRadicacion: string;
  payload: Record<string, unknown>;
  documentos: DocumentoExpediente[];
  decisionHumana: DecisionHumana | null;
  puedeDecidir: boolean;
  eventos: EventoExpediente[];
};

export type RespuestaDecision = {
  estado: string;
  usuarioResponsable: string;
  sentido: SentidoDecision;
  firmaTimestamp: string;
};

export type ItemChecklist = {
  id: string;
  texto: string;
  verificado: boolean;
  origen: string;
  orden: number;
  verificadoPor?: string | null;
  verificadoEn?: string | null;
};

export type FuenteExterna = {
  id: string;
  fuente: string;
  titulo: string;
  tipo: string;
  pais: string;
  fecha: string;
  url: string;
  encontrada: boolean;
  observaciones: string;
  vinculada: boolean;
};

export type ConsultaSugerida = { id: string; pregunta: string };

export type Consulta = {
  id: string;
  pregunta: string;
  respuesta: string;
  cita: string;
  url: string;
  encontrada: boolean;
  momento: string;
};

export type EstadoInforme = 'PENDIENTE' | 'EN_EJECUCION' | 'COMPLETADO' | 'ERROR' | 'OMITIDO';

export type InformeAgente = {
  agente: string;
  nombre: string;
  estado: EstadoInforme;
  iniciadoEn: string | null;
  terminadoEn: string | null;
  duracionMs: number | null;
  modelo: string;
  resumen: Record<string, unknown>;
  payload: Record<string, unknown>;
  error: string;
};
