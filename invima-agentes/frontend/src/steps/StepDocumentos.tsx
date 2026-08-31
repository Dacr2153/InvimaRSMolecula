import { CargaDocumento } from '../components/CargaDocumento';
import { DeclaracionNormas } from '../components/DeclaracionNormas';
import { EnlacesEvidencia } from '../components/EnlacesEvidencia';
import { EXTENSIONES_ACEPTADAS } from '../constantes';
import type { DocumentoCargado, EnlaceEvidencia, ModuloCtd } from '../api/tipos';

type Props = {
  solicitudId: string;
  modulos: ModuloCtd[];
  documentos: Record<string, DocumentoCargado>;
  // El comprobante de pago se carga en el paso de pago; aqui se omite para no
  // pedir el mismo archivo dos veces.
  omitirIds?: string[];
  onDocumento: (requeridoId: string, doc: DocumentoCargado | null) => void;
  enlaces: EnlaceEvidencia[];
  onEnlaces: (enlaces: EnlaceEvidencia[]) => void;
  noIncluidaEnNormas: boolean;
  onNoIncluidaEnNormas: (valor: boolean) => void;
};

export function StepDocumentos({
  solicitudId,
  modulos,
  documentos,
  omitirIds = [],
  onDocumento,
  enlaces,
  onEnlaces,
  noIncluidaEnNormas,
  onNoIncluidaEnNormas,
}: Props) {
  const omitidos = new Set(omitirIds);
  const modulosVisibles = modulos
    .map((m) => ({ ...m, documentos: m.documentos.filter((d) => !omitidos.has(d.id)) }))
    .filter((m) => m.documentos.length > 0);
  const todos = modulosVisibles.flatMap((m) => m.documentos);
  const cargados = todos.filter((d) => documentos[d.id]).length;
  const pendientes = todos.length - cargados;
  const obligatoriosFaltantes = todos.filter((d) => d.obligatorio && !documentos[d.id]).length;

  return (
    <section className="pane--wide">
      <h1 className="pane__title">Documentos del expediente</h1>
      <p className="pane__subtitle pane__subtitle--tight">
        Carga los documentos organizados por módulo regulatorio. Formatos admitidos:{' '}
        {EXTENSIONES_ACEPTADAS}. Tamaño máximo: 25 MB por archivo.
      </p>

      <div className="legend">
        <div>
          <span className="legend__dot legend__dot--pending" />
          Pendiente ({pendientes})
        </div>
        <div>
          <span className="legend__dot legend__dot--loaded" />
          Cargado ({cargados})
        </div>
      </div>

      {obligatoriosFaltantes > 0 ? (
        <div className="aviso aviso--warn mb-24">
          Faltan {obligatoriosFaltantes} documento(s) obligatorio(s). El expediente puede radicarse, pero la
          validación de integridad los exigirá.
        </div>
      ) : null}

      {modulosVisibles.map((m) => (
        <div className="doc-group" key={m.id}>
          <div className="doc-group__title">{m.titulo}</div>
          <div className="doc-group__list">
            {m.documentos.map((d) => (
              <CargaDocumento
                key={d.id}
                solicitudId={solicitudId}
                requeridoId={d.id}
                nombre={d.nombre}
                obligatorio={d.obligatorio}
                documento={documentos[d.id] ?? null}
                onDocumento={onDocumento}
              />
            ))}
          </div>
        </div>
      ))}

      <DeclaracionNormas valor={noIncluidaEnNormas} onCambio={onNoIncluidaEnNormas} />

      <EnlacesEvidencia solicitudId={solicitudId} enlaces={enlaces} onCambio={onEnlaces} />
    </section>
  );
}
