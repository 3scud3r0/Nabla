/** Canonical signed-int64 fractions; BigInt avoids JSON number precision loss. */
export function parseFraction(source: string): { numerator: bigint, denominator: bigint } {
  if (typeof source !== 'string' || source.length > 42 || !/^-?(0|[1-9][0-9]*)(\/[1-9][0-9]*)?$/.test(source))
    throw new Error('Invalid canonical fraction');
  const parts = source.split('/');
  const n = BigInt(parts[0]); const d = parts.length === 2 ? BigInt(parts[1]) : 1n;
  if (source.startsWith('-0') || n < -(1n << 63n) || n >= (1n << 63n) || d < 1n || d >= (1n << 63n))
    throw new Error('Fraction outside int64 or noncanonical');
  let a = n < 0n ? -n : n; let b = d;
  while (b !== 0n) { const next = a % b; a = b; b = next; }
  if (parts.length === 2 && (d === 1n || n === 0n || a !== 1n)) throw new Error('Non-reduced fraction');
  return { numerator: n, denominator: d };
}
