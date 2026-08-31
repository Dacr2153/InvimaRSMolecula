type PropsCargando = { mensaje?: string };

export function Cargando({ mensaje = 'Cargando…' }: PropsCargando) {
  return (
    <div className="estado-vista" role="status" aria-live="polite">
      <div className="estado-vista__spinner" aria-hidden="true" />
      <div className="estado-vista__texto">{mensaje}</div>
    </div>
  );
}

type PropsError = { titulo?: string; mensaje: string; onReintentar?: () => void };

export function ErrorVista({ titulo = 'No se pudo cargar la información', mensaje, onReintentar }: PropsError) {
  return (
    <div className="estado-vista estado-vista--error" role="alert">
      <div className="estado-vista__titulo">{titulo}</div>
      <div className="estado-vista__texto">{mensaje}</div>
      {onReintentar ? (
        <button type="button" className="btn-secundario" onClick={onReintentar}>
          Reintentar
        </button>
      ) : null}
    </div>
  );
}

export function VistaVacia({ mensaje }: { mensaje: string }) {
  return <div className="estado-vista estado-vista--vacia">{mensaje}</div>;
}
