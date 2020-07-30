# Trial Factoring No Factor Proof

Most parts of [GIMPS](https://en.wikipedia.org/wiki/Great_Internet_Mersenne_Prime_Search)
have a verifiable component: PRP and LL both have a verifiable residual (See [The Math](https://www.mersenne.org/various/math.php)).

When Trial Factoring (TF) and ECM find a factor that's an easy to verify signal but only
1-2% of TF tests result in a factor found (even less for ECM). Ideally we'd have some
result from TF-NF to check consistency and verify user submitted reports.

Ideally this would
1. Deterministic
2. Fast (and easy) to verify
3. Hard to fake

## Proposed solution - Proof-Numbers

This proposal calls for the storing of "proof-numbers", which satisfies properties 2. and 3. and partially 1.

A proof-number is a number that was tested as a trial factor and was a near miss for divisibility.
Remember that a factor of a potentially Mersenne Prime (2^e+1) has the property that `f = 2 * k * e + 1`
and `2^e+1 == 0 mod f <=> pow(2, e, f) == 1`

### Format

for JSON this is as simple as adding a new field "proof" or "proofk" which is an array of several proof-numbers.
Ideally you should send 2-4 numbers (this leads to better determinism while balancing amount of data stored).

See [Format Notes](#format-notes) for more details


### Verification

To verify a proof compute `pow(2, mp, proof)` and verify this number is sufficiently small.

proof should also have no small prime factors.

More formally
```Python3
proof = 2 * e * proof_k + 1
difficulty = proof / pow(2, e, proof)

# For TF from `2^(bits-1) to 2^bits` for exponent `e`
# Test primeish numbers of the form factor = 2 * e * k + 1
begin_k = (2**(bits-1) - 1) // (2 * e)
end_k = (2**bits-1) // (2 * e)
tests = end_k - begin_k
# About 90% of numbers are removed by prime sieve
tests *= .1

suspicion = difficulty / tests
```

Simplifying 
```
proof = 2 * e * proof_k + 1
difficulty = proof / pow(2, e, proof)
tests = 2 ** (bits-1) // (2 * e) * 0.1
suspicion = difficulty / tests
```

Working this for an example
```
# M59068201 proof_k(75682214388): 29 bits [TF:60:64:mfaktc 0.21 75bit_mul32_gs]
>>> e = 59068201
>>> proof_k = 75682214388
>>> proof = 2 * e * proof_k + 1
8940824503190951977
>>> difficulty = proof / pow(2, e, proof)
21159893697.3
>>> tests = 2 ** (bits-1) // (2 * e) * 0.1
7807392032.1
>>> suspicion = difficulty / tests
2.71
```

Naively we would have expected a number ~3 times smaller, in practice suspicion of < 50 is normal.

TODO(sethtroisi): Add graph of suspicion

## Format Notes

mfaktc has three lines that need to be parsed
```
no factor for M369452273 from 2^70 to 2^71 [mfaktc 0.21 barrett76_mul32_gs]
found 1 factor for M372429797 from 2^70 to 2^71 [mfaktc 0.21 barrett76_mul32_gs]
M372429797 has a factor: 1929094588119120132761 [TF:70:71:mfaktc 0.21 barrett76_mul32_gs]
```
I'd be added one more output line
```
M59068201 proof_k(75682214388): 29 bits [TF:60:64:mfaktc 0.21 75bit_mul32_gs]
or
M59068201 proof(8940824503190951977): 29 bits [TF:60:64:mfaktc 0.21 75bit_mul32_gs]
```
Note that  `88940824503190951977 = 2 * 59068201 *  7568221438 + 1`
