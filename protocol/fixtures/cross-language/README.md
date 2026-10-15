# Canonical rational protocol profile v1

`rational-v1.json` is the normative bounded signed-int64 rational profile.
Numerators range from -2^63 through 2^63-1; denominators from 1 through 2^63-1.
Integers have no slash. Fractions are reduced, denominator greater than one,
nonzero numerator. ASCII decimal digits only, no whitespace, leading zero,
positive sign or negative zero. Transport values are strings, never JSON floats.

`tests/network/test_interop.py` compiles and executes independent C/C++ readers,
executes Python and TypeScript readers and invokes Cargo when available.
Unavailable toolchains cause explicit skips, not conformance claims.
The Rust HTTP client is a bounded loopback transport profile, not a complete
remote TLS scientific client. Scientific receipts still require independent
semantic verification. This profile does not freeze the entire SDK API/ABI.
