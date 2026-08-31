import { tonoDeEstado } from '../formato';

type Props = { estado: string; etiqueta: string; tamano?: 'sm' | 'md' };

export function EstadoBadge({ estado, etiqueta, tamano = 'sm' }: Props) {
  const tono = tonoDeEstado(estado);
  return (
    <span className={`estado-badge estado-badge--${tono} estado-badge--${tamano}`}>{etiqueta || estado}</span>
  );
}
