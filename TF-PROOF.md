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

A proof-number is a number that was tested as a trial factor and was a near miss.
Remember that a factor of a Mersenne Prime (MP) has the property that `f = 2 * k * MP + 1`
and `2^MP+1 == 0 mod f <=> pow(2, MP, f) == 1`  


## Notes

mfaktc has three lines that need to be parsed
```
no factor for M369452273 from 2^70 to 2^71 [mfaktc 0.21 barrett76_mul32_gs]
found 1 factor for M372429797 from 2^70 to 2^71 [mfaktc 0.21 barrett76_mul32_gs]
M372429797 has a factor: 1929094588119120132761 [TF:70:71:mfaktc 0.21 barrett76_mul32_gs]
```
I'd be added one more output line
```
M59068201 proof_k(75682214388): 29 bits [TF:60:64:mfaktc 0.21 75bit_mul32_gs]
so
M59068201 proof(8940824503190951977): 29 bits [TF:60:64:mfaktc 0.21 75bit_mul32_gs]
```
Note that  `88940824503190951977 = 2 * 59068201 *  7568221438 + 1`

In plain English. This is a number (or k of a number) that minimizes pow(2, MP, factor).
Here pow(2, 59068201, 8940824503190951977) = 422536362 which is a 29 bit number

the number should also be prime (or have no factors smaller than mfackt's SievePrime)
Here 8940824503190951977 = 30884149 289495575973
