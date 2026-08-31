// Utilidades de formato compartidas por las dos pantallas.

export function formatearBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

export function formatearFecha(iso: string | null | undefined): string {
  if (!iso) return '—';
  // Una fecha sin hora (YYYY-MM-DD) se interpreta como UTC y se corre un dia
  // hacia atras en Colombia; se formatea a mano para evitarlo.
  const soloFecha = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (soloFecha) return `${soloFecha[3]}/${soloFecha[2]}/${soloFecha[1]}`;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function formatearFechaHora(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('es-CO', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatearMoneda(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—';
  const n = typeof valor === 'number' ? valor : Number(valor);
  if (Number.isNaN(n)) return String(valor);
  return `$ ${n.toLocaleString('es-CO', { maximumFractionDigits: 0 })} COP`;
}

export function abreviarSha(sha: string | null | undefined): string {
  if (!sha) return '—';
  return sha.length <= 16 ? sha : `${sha.slice(0, 12)}…${sha.slice(-4)}`;
}

// El mockup pintaba un SLA en dias RESTANTES, donde pocos dias era lo urgente.
// El backend devuelve dias TRANSCURRIDOS desde la radicacion, asi que la escala
// va al reves: un expediente recien radicado esta al dia, y uno que lleva
// semanas en la cola es el que hay que mirar.
//
// Los cortes no son un SLA: nadie asumio ese compromiso. Son una ayuda visual
// para ordenar la cola por antiguedad.
export function colorDiasEnCola(dias: number): string {
  if (dias >= 15) return '#F42F63';
  if (dias >= 8) return '#B37C00';
  return '#068460';
}

// El backend puede devolver estados nuevos; se clasifican por palabra clave
// en vez de mantener un mapa cerrado que se rompa con el primer estado nuevo.
export type TonoEstado = 'info' | 'warn' | 'ok' | 'danger' | 'neutral';

export function tonoDeEstado(estado: string): TonoEstado {
  const e = (estado || '').toUpperCase();
  if (e.includes('SUSPENDIDO') || e.includes('PENDIENTE_INFO')) return 'warn';
  if (e.includes('DEVUELT') || e.includes('RECHAZ') || e.includes('ANULAD')) return 'danger';
  if (e.includes('APROBAD') || e.includes('ENRUTAD')) return 'ok';
  if (e.includes('PENDIENTE') || e.includes('EVALUACION')) return 'info';
  return 'neutral';
}
