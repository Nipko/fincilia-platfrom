/** Fecha civil de un instante en la zona de la fuente, nunca en UTC implícito. */
export function isoDateInTimeZone(timeZone: string, instant = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(instant);
  const value = new Map(parts.map((part) => [part.type, part.value]));
  return `${value.get('year')}-${value.get('month')}-${value.get('day')}`;
}
