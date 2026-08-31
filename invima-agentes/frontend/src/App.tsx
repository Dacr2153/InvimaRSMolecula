import { RadicacionApp } from './radicacion/RadicacionApp';
import { BandejaExpedientes } from './evaluacion/BandejaExpedientes';
import { DetalleExpediente } from './evaluacion/DetalleExpediente';
import { useRuta } from './router';

export default function App() {
  const ruta = useRuta();

  if (ruta.vista === 'bandeja') return <BandejaExpedientes />;
  if (ruta.vista === 'expediente') return <DetalleExpediente radicado={ruta.radicado} />;
  return <RadicacionApp />;
}
