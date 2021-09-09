# GMP-ECM GPU Optimizer

Try to optimize B1/B2 bounds when B1 is run on GPU at a non-trivial speedup.

Given a B1 speedup compute optimal B1/B2 params.

B1 speedup = 1x     corresponds to CPU case.
B1 speedup = 40x    corresponds to GPU + 1 core
B1 speedup = 40/8x, corresponds to GPU + 8 CPU cores

## GPU timing

I calculate my GPU's B1 speed with

```
$ echo "(2^499-1)/20959" | ./ecm -cgbn 1e5 0
...
Computing 1792 Step 1 took 19ms of CPU time / 4786ms of GPU time

$ echo "(2^499-1)/20959" | ./ecm -cgbn 2e5 0
...
Computing 1792 Step 1 took 17ms of CPU time / 8911ms of GPU time
```
Here my 1080ti computes B1 for 256-512 bit inputs in `4786/1000/1e5/1792` = `2.67e-8` B1/curve/second

## CPU timing

To find my CPU's B1 timing I run the same without `-cgbn`

```
$ echo "(2^499-1)/20959" | ./ecm -param 3 1e5 0
Step 1 took 107ms

$ echo "(2^499-1)/20959" | ./ecm -param 3 1e6 0
Step 1 took 1075ms

$ echo "(2^499-1)/20959" | ./ecm -param 3 1e7 0
Step 1 took 10764ms
```

Again nice and linear. `1075/1000/1e6` = `1.08e-6` B1/curve/second

This makes each CPU core ~40x slower than my GPU.

# Methodology

1. For each t<X> (factor size)
  1. Binary search for new optimal B1
    1. For a given B1, bisect for B2 that matches the given B1/B2 ratio
      1. It's hard to predict B2 timing so we simply measure it experimentally.
        * B1 << B2 so B1 largly doesn't affect B2 timings.
        * time(B2) ~ B2 ^ 0.685, which we can use to interpolate between B2 values
    2. time for t<X> = curves(B1, B2) * timing(B1, B2)
