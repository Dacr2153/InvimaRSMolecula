// Constantes de la interfaz. Los catalogos de negocio vienen del API.

export const STEP_LABELS = [
  'Tipo de solicitud',
  'Datos del expediente',
  'Documentos',
  'Pago',
  'Confirmación',
];

export const SOLICITANTE = { nombre: 'Farma Andina S.A.S.', iniciales: 'FA' };

export type CampoExpediente = {
  id: string;
  label: string;
  required: boolean;
  fullWidth?: boolean;
  placeholder?: string;
};

// Estructura del formulario del paso 2. Los valores los escribe el usuario y
// viajan completos en datosDeclarados.
export const CAMPOS_EXPEDIENTE: CampoExpediente[] = [
  { id: 'nombre', label: 'Nombre del producto', required: true, placeholder: 'Amoxiplex 500 mg' },
  { id: 'principioActivo', label: 'Principio activo', required: true, placeholder: 'Amoxicilina' },
  { id: 'concentracion', label: 'Concentración', required: true, placeholder: '500 mg' },
  { id: 'formaFarmaceutica', label: 'Forma farmacéutica', required: true, placeholder: 'Cápsula' },
  { id: 'titular', label: 'Titular', required: true, placeholder: 'Farma Andina S.A.S.' },
  { id: 'solicitante', label: 'Solicitante', required: true, placeholder: 'Farma Andina S.A.S.' },
  { id: 'fabricante', label: 'Fabricante(s)', required: true, placeholder: 'Laboratorios Vitalis S.A.' },
  { id: 'importador', label: 'Importador', required: false, placeholder: 'No aplica' },
  {
    id: 'condicionesAlmacenamiento',
    label: 'Condiciones de almacenamiento',
    required: false,
    fullWidth: true,
    placeholder: 'Conservar entre 15°C y 30°C, proteger de la luz',
  },
];

export const EXTENSIONES_ACEPTADAS = '.md,.pdf,.txt';
export const TAMANO_MAX_BYTES = 25 * 1024 * 1024;

// Identificador del requerido con el que se sube el comprobante de pago.
export const REQUERIDO_COMPROBANTE = 'pago-comprobante';
