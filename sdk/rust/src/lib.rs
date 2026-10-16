//! Leitor sem dependências do protocolo racional v0; não implementa o motor Python.

#[derive(Debug, PartialEq, Eq)]
pub struct Fraction { pub numerator: i64, pub denominator: i64 }

fn canonical_integer(text: &str, allow_zero: bool, negative: bool) -> Option<i64> {
    let digits = if negative { text.strip_prefix('-')? } else { text };
    if digits.is_empty() || !digits.bytes().all(|x| x.is_ascii_digit()) { return None; }
    if digits.len() > 1 && digits.starts_with('0') { return None; }
    if !allow_zero && digits == "0" { return None; }
    if negative && digits == "0" { return None; }
    text.parse::<i64>().ok()
}

fn gcd(mut a: u64, mut b: u64) -> u64 {
    while b != 0 { let t = a % b; a = b; b = t; }
    a
}

pub fn parse_fraction(source: &str) -> Option<Fraction> {
    let (n, d) = match source.split_once('/') {
        Some((n, d)) => (n, Some(d)),
        None => (source, None),
    };
    let negative = n.starts_with('-');
    let numerator = canonical_integer(n, d.is_none(), negative)?;
    let denominator = match d {
        None => 1,
        Some(text) => {
            let value = canonical_integer(text, false, false)?;
            if value < 2 || gcd(numerator.unsigned_abs(), value as u64) != 1 { return None; }
            value
        }
    };
    Some(Fraction { numerator, denominator })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn protocol_fixtures() {
        assert_eq!(parse_fraction("-3/4"), Some(Fraction { numerator: -3, denominator: 4 }));
        assert_eq!(parse_fraction("0"), Some(Fraction { numerator: 0, denominator: 1 }));
        for invalid in ["00", "-0", "+1", "2/4", "3/1", "1/0", " 1", "1/02"] {
            assert_eq!(parse_fraction(invalid), None);
        }
    }
}

pub mod client;
