import { useRef, useState } from 'react';
import { eliminarDocumento, subirDocumento } from '../api/cliente';
import { EXTENSIONES_ACEPTADAS, TAMANO_MAX_BYTES } from '../constantes';
import { formatearBytes } from '../formato';
import type { DocumentoCargado } from '../api/tipos';

type Props = {
  solicitudId: string;
  requeridoId: string;
  nombre: string;
  obligatorio: boolean;
  documento: DocumentoCargado | null;
  onDocumento: (requeridoId: string, doc: DocumentoCargado | null) => void;
};

const EXTENSIONES = EXTENSIONES_ACEPTADAS.split(',');

function extensionValida(nombreArchivo: string): boolean {
  const punto = nombreArchivo.lastIndexOf('.');
  if (punto < 0) return false;
  return EXTENSIONES.includes(nombreArchivo.slice(punto).toLowerCase());
}

export function CargaDocumento({
  solicitudId,
  requeridoId,
  nombre,
  obligatorio,
  documento,
  onDocumento,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [progreso, setProgreso] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [borrando, setBorrando] = useState(false);

  const cargando = progreso !== null;
  const cargado = documento !== null;

  const seleccionar = () => {
    setError(null);
    inputRef.current?.click();
  };

  const alElegirArchivo = async (archivo: File) => {
    setError(null);
    if (!extensionValida(archivo.name)) {
      setError(`Formato no admitido. Se aceptan ${EXTENSIONES_ACEPTADAS}.`);
      return;
    }
    if (archivo.size > TAMANO_MAX_BYTES) {
      setError(`El archivo pesa ${formatearBytes(archivo.size)} y el máximo es 25 MB.`);
      return;
    }
    setProgreso(0);
    try {
      // El badge solo cambia a CARGADO cuando el servidor confirma el folio.
      const doc = await subirDocumento(solicitudId, requeridoId, archivo, setProgreso);
      onDocumento(requeridoId, doc);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cargar el archivo.');
    } finally {
      setProgreso(null);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const quitar = async () => {
    setBorrando(true);
    setError(null);
    try {
      await eliminarDocumento(solicitudId, requeridoId);
      onDocumento(requeridoId, null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo quitar el archivo.');
    } finally {
      setBorrando(false);
    }
  };

  const idInput = `archivo-${requeridoId}`;

  return (
    <div className="doc-row">
      <div className="doc-row__principal">
        <div className="doc-row__nombre">
          {nombre}
          {obligatorio ? <span className="req"> *</span> : null}
        </div>
        {cargado && documento ? (
          <div className="doc-row__archivo">
            {documento.nombreArchivo} · {formatearBytes(documento.tamanoBytes)}
          </div>
        ) : null}
        {cargando ? (
          <div className="doc-row__progreso">
            <div
              className="barra-progreso"
              role="progressbar"
              aria-valuenow={progreso ?? 0}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`Cargando ${nombre}`}
            >
              <div className="barra-progreso__relleno" style={{ width: `${progreso ?? 0}%` }} />
            </div>
            <span className="doc-row__progreso-texto">{progreso ?? 0}%</span>
          </div>
        ) : null}
        {error ? (
          <div className="doc-row__error" role="alert">
            {error}
          </div>
        ) : null}
      </div>

      <div className="doc-row__acciones">
        <span className={`doc-badge ${cargado ? 'doc-badge--loaded' : 'doc-badge--pending'}`}>
          {cargado ? 'CARGADO' : 'PENDIENTE'}
        </span>
        {cargado ? (
          <button type="button" className="btn-enlace btn-enlace--peligro" onClick={quitar} disabled={borrando}>
            {borrando ? 'Quitando…' : 'Quitar'}
          </button>
        ) : (
          <button type="button" className="btn-secundario btn-secundario--sm" onClick={seleccionar} disabled={cargando}>
            {cargando ? 'Subiendo…' : 'Seleccionar archivo'}
          </button>
        )}
        <input
          ref={inputRef}
          id={idInput}
          className="input-archivo-oculto"
          type="file"
          accept={EXTENSIONES_ACEPTADAS}
          tabIndex={-1}
          aria-hidden="true"
          onChange={(e) => {
            const archivo = e.target.files?.[0];
            if (archivo) void alElegirArchivo(archivo);
          }}
        />
      </div>
    </div>
  );
}
