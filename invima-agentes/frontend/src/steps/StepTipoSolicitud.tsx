import { OptionCard } from '../components/OptionCard';
import type { TipoProducto, TipoTramite } from '../api/tipos';

type Props = {
  tramites: TipoTramite[];
  productos: TipoProducto[];
  tramite: string;
  producto: string;
  onTramite: (id: string) => void;
  onProducto: (id: string) => void;
};

export function StepTipoSolicitud({ tramites, productos, tramite, producto, onTramite, onProducto }: Props) {
  return (
    <section className="pane">
      <h1 className="pane__title">Tipo de solicitud</h1>
      <p className="pane__subtitle">
        Selecciona el tipo de trámite y de producto para determinar la ruta regulatoria.
      </p>

      <div className="field-label">Tipo de trámite</div>
      <div className="option-grid option-grid--2 mb-28">
        {tramites.map((t) => (
          <OptionCard
            key={t.id}
            label={t.etiqueta}
            hint={t.descripcion}
            selected={tramite === t.id}
            onSelect={() => onTramite(t.id)}
          />
        ))}
      </div>

      <div className="field-label">Tipo de producto</div>
      <div className="option-grid option-grid--2">
        {productos.map((p) => (
          <OptionCard
            key={p.id}
            label={p.etiqueta}
            hint={p.descripcion}
            selected={producto === p.id}
            onSelect={() => onProducto(p.id)}
          />
        ))}
      </div>
    </section>
  );
}
