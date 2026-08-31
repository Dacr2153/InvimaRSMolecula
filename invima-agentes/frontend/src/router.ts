import { useEffect, useState } from 'react';

export type Ruta =
  | { vista: 'radicacion' }
  | { vista: 'bandeja' }
  | { vista: 'expediente'; radicado: string };

export function analizarHash(hash: string): Ruta {
  const limpio = hash.replace(/^#\/?/, '');
  const partes = limpio.split('/').filter(Boolean);
  if (partes[0] === 'evaluacion') {
    if (partes[1]) return { vista: 'expediente', radicado: decodeURIComponent(partes[1]) };
    return { vista: 'bandeja' };
  }
  return { vista: 'radicacion' };
}

export function navegar(destino: string): void {
  window.location.hash = destino;
}

export function useRuta(): Ruta {
  const [ruta, setRuta] = useState<Ruta>(() => analizarHash(window.location.hash));

  useEffect(() => {
    const alCambiar = () => setRuta(analizarHash(window.location.hash));
    window.addEventListener('hashchange', alCambiar);
    if (!window.location.hash) window.location.replace('#/radicacion');
    return () => window.removeEventListener('hashchange', alCambiar);
  }, []);

  return ruta;
}
