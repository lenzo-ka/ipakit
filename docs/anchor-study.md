# XRMB anchor study

**Verdict: the audio-pellet sync gate passed. The table below is the generated result; its per-class recommendations are evidence for the timed sampler and do not estimate a universal phonological alignment rule.**

## Sync gate

22 deduplicated clear stop releases across the first 5 speakers; median signed pellet-release minus waveform-burst difference **-0.013 s** (range **-0.062 to +0.082 s**). Median absolute difference **0.034 s** and 75th percentile **0.041 s** (gate: 75th percentile <= 0.050 s). The signed values expose systematic clock offset separately from detector scatter; the absolute values enforce the gate.

## Headline distributions

- **alveolar-fricative:** median 0.387 of the acoustic segment (IQR 0.090-0.899); 18.2% of targets precede acoustic onset.
- **alveolar-nasal:** median 0.451 of the acoustic segment (IQR 0.285-0.644); 11.2% of targets precede acoustic onset.
- **alveolar-stop:** median 0.434 of the acoustic segment (IQR 0.059-0.844); 19.9% of targets precede acoustic onset.
- **bilabial-nasal:** median 0.645 of the acoustic segment (IQR 0.501-1.030); 1.1% of targets precede acoustic onset.
- **bilabial-stop:** median 0.379 of the acoustic segment (IQR 0.310-0.473); 1.1% of targets precede acoustic onset.
- **vowel:** median 0.605 of the acoustic segment (IQR -0.212-1.268); 30.9% of targets precede acoustic onset.

| group | n | median | Q1 | Q3 | before onset |
|---|---:|---:|---:|---:|---:|
| alveolar-fricative | 308 | 0.387 | 0.090 | 0.899 | 18.2% |
| alveolar-nasal | 268 | 0.451 | 0.285 | 0.644 | 11.2% |
| alveolar-stop | 311 | 0.434 | 0.059 | 0.844 | 19.9% |
| bilabial-nasal | 90 | 0.645 | 0.501 | 1.030 | 1.1% |
| bilabial-stop | 181 | 0.379 | 0.310 | 0.473 | 1.1% |
| vowel | 1473 | 0.605 | -0.212 | 1.268 | 30.9% |

## Uniform-window null comparison

The null chooses a time uniformly from each token's acoustic segment plus the same 60 ms pad on either side. Its median is 0.500 by symmetry. In-segment chance and the pooled null IQR are computed analytically from the observed token durations; IQR is the dispersion measure in both columns.

| class | n | observed in segment | chance | observed IQR | null IQR | assessment |
|---|---:|---:|---:|---:|---:|---|
| alveolar-fricative | 308 | 58.4% | 49.6% | 0.810 | 1.009 | **NON-INFORMATIVE** |
| alveolar-nasal | 268 | 78.0% | 43.3% | 0.358 | 1.154 | **informative** |
| alveolar-stop | 311 | 63.7% | 38.0% | 0.785 | 1.314 | **informative** |
| bilabial-nasal | 90 | 72.2% | 43.7% | 0.529 | 1.144 | **informative** |
| bilabial-stop | 181 | 94.5% | 42.7% | 0.163 | 1.171 | **informative** |
| vowel | 1473 | 36.3% | 42.3% | 1.480 | 1.182 | **NON-INFORMATIVE** |

Vowel and alveolar-fricative are **NON-INFORMATIVE** on the current detectors and are excluded from recommendations: neither is separable from this null, and the vowel detector is more dispersed than it.

## By speaker

| group | n | median | Q1 | Q3 | before onset |
|---|---:|---:|---:|---:|---:|
| JW11 / alveolar-fricative | 6 | 0.349 | 0.129 | 0.540 | 16.7% |
| JW11 / alveolar-nasal | 4 | 0.456 | 0.176 | 0.627 | 25.0% |
| JW11 / alveolar-stop | 6 | 0.362 | 0.176 | 0.717 | 16.7% |
| JW11 / bilabial-nasal | 2 | 0.679 | 0.676 | 0.682 | 0.0% |
| JW11 / bilabial-stop | 3 | 0.563 | 0.513 | 1.121 | 0.0% |
| JW11 / vowel | 33 | 0.671 | 0.106 | 1.138 | 24.2% |
| JW12 / alveolar-fricative | 7 | 0.799 | 0.674 | 0.967 | 0.0% |
| JW12 / alveolar-nasal | 6 | 0.505 | 0.255 | 0.584 | 16.7% |
| JW12 / alveolar-stop | 7 | 0.090 | 0.012 | 0.419 | 28.6% |
| JW12 / bilabial-nasal | 2 | 1.249 | 0.937 | 1.560 | 0.0% |
| JW12 / bilabial-stop | 4 | 0.355 | 0.333 | 0.384 | 0.0% |
| JW12 / vowel | 33 | 0.821 | 0.384 | 1.339 | 15.2% |
| JW13 / alveolar-fricative | 7 | 0.288 | 0.121 | 0.467 | 14.3% |
| JW13 / alveolar-nasal | 6 | 0.598 | 0.434 | 0.826 | 0.0% |
| JW13 / alveolar-stop | 7 | 0.218 | 0.089 | 0.339 | 14.3% |
| JW13 / bilabial-nasal | 2 | 0.934 | 0.875 | 0.993 | 0.0% |
| JW13 / bilabial-stop | 4 | 0.417 | 0.388 | 0.456 | 0.0% |
| JW13 / vowel | 33 | 0.730 | -0.172 | 1.186 | 30.3% |
| JW14 / alveolar-fricative | 4 | 0.381 | 0.353 | 0.573 | 0.0% |
| JW14 / alveolar-nasal | 5 | 0.428 | 0.286 | 0.487 | 0.0% |
| JW14 / alveolar-stop | 5 | 0.982 | 0.044 | 1.070 | 20.0% |
| JW14 / bilabial-nasal | 2 | 0.803 | 0.668 | 0.938 | 0.0% |
| JW14 / bilabial-stop | 4 | 0.384 | 0.363 | 0.418 | 0.0% |
| JW14 / vowel | 33 | 0.646 | -0.404 | 1.193 | 27.3% |
| JW15 / alveolar-fricative | 7 | 0.156 | 0.098 | 0.667 | 14.3% |
| JW15 / alveolar-nasal | 6 | 0.396 | 0.141 | 0.694 | 16.7% |
| JW15 / alveolar-stop | 7 | 0.090 | 0.068 | 0.641 | 0.0% |
| JW15 / bilabial-nasal | 2 | 0.450 | 0.443 | 0.457 | 0.0% |
| JW15 / bilabial-stop | 4 | 0.366 | 0.330 | 0.411 | 0.0% |
| JW15 / vowel | 33 | 0.543 | -0.032 | 1.442 | 27.3% |
| JW16 / alveolar-fricative | 7 | 0.422 | 0.258 | 0.686 | 0.0% |
| JW16 / alveolar-nasal | 6 | 0.288 | 0.134 | 0.498 | 16.7% |
| JW16 / alveolar-stop | 7 | 0.067 | -0.252 | 0.683 | 42.9% |
| JW16 / bilabial-nasal | 2 | 0.776 | 0.772 | 0.780 | 0.0% |
| JW16 / bilabial-stop | 4 | 0.334 | 0.278 | 0.403 | 0.0% |
| JW16 / vowel | 33 | 0.502 | -0.342 | 1.185 | 36.4% |
| JW18 / alveolar-fricative | 1 | -0.210 | -0.210 | -0.210 | 100.0% |
| JW18 / alveolar-nasal | 3 | 0.167 | 0.133 | 0.313 | 0.0% |
| JW18 / alveolar-stop | 2 | 0.116 | 0.090 | 0.141 | 0.0% |
| JW18 / bilabial-stop | 2 | 0.371 | 0.339 | 0.403 | 0.0% |
| JW18 / vowel | 11 | 0.825 | -0.290 | 1.406 | 36.4% |
| JW19 / alveolar-fricative | 7 | 0.128 | 0.052 | 0.962 | 14.3% |
| JW19 / alveolar-nasal | 6 | 0.410 | 0.270 | 0.667 | 16.7% |
| JW19 / alveolar-stop | 6 | 0.609 | 0.561 | 0.657 | 0.0% |
| JW19 / bilabial-nasal | 2 | 0.708 | 0.688 | 0.729 | 0.0% |
| JW19 / bilabial-stop | 4 | 0.319 | 0.298 | 0.367 | 0.0% |
| JW19 / vowel | 33 | 0.717 | -0.070 | 1.169 | 27.3% |
| JW20 / alveolar-fricative | 3 | 0.359 | 0.321 | 0.718 | 0.0% |
| JW20 / alveolar-nasal | 3 | 0.369 | 0.318 | 0.415 | 0.0% |
| JW20 / alveolar-stop | 3 | 0.116 | -0.185 | 0.124 | 33.3% |
| JW20 / bilabial-stop | 2 | 0.527 | 0.479 | 0.576 | 0.0% |
| JW20 / vowel | 11 | 0.719 | -0.221 | 1.042 | 36.4% |
| JW21 / alveolar-fricative | 7 | 0.849 | 0.241 | 0.963 | 14.3% |
| JW21 / alveolar-nasal | 6 | 0.477 | 0.249 | 1.190 | 0.0% |
| JW21 / alveolar-stop | 7 | 0.111 | 0.051 | 0.629 | 14.3% |
| JW21 / bilabial-nasal | 2 | 0.795 | 0.625 | 0.965 | 0.0% |
| JW21 / bilabial-stop | 4 | 0.417 | 0.341 | 0.471 | 0.0% |
| JW21 / vowel | 33 | 0.707 | -0.198 | 1.300 | 33.3% |
| JW24 / alveolar-fricative | 7 | 0.238 | -0.051 | 0.899 | 28.6% |
| JW24 / alveolar-nasal | 6 | 0.445 | 0.375 | 0.560 | 16.7% |
| JW24 / alveolar-stop | 7 | 0.232 | -0.325 | 0.363 | 42.9% |
| JW24 / bilabial-nasal | 2 | 0.545 | 0.504 | 0.586 | 0.0% |
| JW24 / bilabial-stop | 4 | 0.361 | 0.306 | 0.406 | 0.0% |
| JW24 / vowel | 33 | 0.767 | 0.272 | 1.317 | 24.2% |
| JW25 / alveolar-fricative | 7 | 0.553 | 0.365 | 0.690 | 0.0% |
| JW25 / alveolar-nasal | 6 | 0.531 | 0.252 | 0.546 | 0.0% |
| JW25 / alveolar-stop | 7 | 0.130 | -0.143 | 0.297 | 28.6% |
| JW25 / bilabial-nasal | 2 | 1.047 | 0.897 | 1.196 | 0.0% |
| JW25 / bilabial-stop | 4 | 0.359 | 0.316 | 0.484 | 0.0% |
| JW25 / vowel | 26 | 0.785 | -0.063 | 1.280 | 26.9% |
| JW26 / alveolar-fricative | 7 | 0.540 | 0.455 | 0.563 | 0.0% |
| JW26 / alveolar-nasal | 6 | 0.478 | 0.259 | 0.681 | 0.0% |
| JW26 / alveolar-stop | 7 | 0.635 | 0.283 | 0.998 | 28.6% |
| JW26 / bilabial-nasal | 2 | 0.564 | 0.533 | 0.594 | 0.0% |
| JW26 / bilabial-stop | 4 | 0.457 | 0.381 | 0.532 | 0.0% |
| JW26 / vowel | 33 | 0.569 | -0.152 | 0.880 | 30.3% |
| JW27 / alveolar-fricative | 7 | 0.341 | 0.179 | 0.623 | 14.3% |
| JW27 / alveolar-nasal | 6 | 0.492 | 0.293 | 0.712 | 16.7% |
| JW27 / alveolar-stop | 7 | 0.355 | 0.063 | 0.498 | 14.3% |
| JW27 / bilabial-nasal | 2 | 0.226 | 0.166 | 0.287 | 0.0% |
| JW27 / bilabial-stop | 4 | 0.353 | 0.340 | 0.415 | 0.0% |
| JW27 / vowel | 33 | 0.286 | -0.287 | 1.039 | 39.4% |
| JW28 / alveolar-fricative | 7 | 0.510 | -0.386 | 0.979 | 42.9% |
| JW28 / alveolar-nasal | 6 | 0.390 | 0.034 | 0.482 | 33.3% |
| JW28 / alveolar-stop | 7 | 0.749 | 0.226 | 0.890 | 14.3% |
| JW28 / bilabial-nasal | 2 | 0.963 | 0.713 | 1.212 | 0.0% |
| JW28 / bilabial-stop | 4 | 0.452 | 0.365 | 0.832 | 0.0% |
| JW28 / vowel | 33 | 0.874 | -0.256 | 1.454 | 33.3% |
| JW29 / alveolar-fricative | 7 | 0.364 | 0.268 | 0.531 | 0.0% |
| JW29 / alveolar-nasal | 6 | 0.411 | 0.382 | 0.438 | 0.0% |
| JW29 / alveolar-stop | 7 | 0.906 | 0.559 | 1.664 | 0.0% |
| JW29 / bilabial-nasal | 2 | 0.927 | 0.749 | 1.106 | 0.0% |
| JW29 / bilabial-stop | 4 | 0.479 | 0.419 | 1.075 | 0.0% |
| JW29 / vowel | 33 | 0.452 | -0.404 | 0.955 | 39.4% |
| JW30 / alveolar-fricative | 4 | 0.229 | -0.136 | 0.567 | 25.0% |
| JW30 / alveolar-nasal | 3 | 0.629 | -0.525 | 0.938 | 33.3% |
| JW30 / alveolar-stop | 4 | 0.506 | 0.127 | 0.965 | 25.0% |
| JW30 / bilabial-nasal | 2 | 0.228 | 0.071 | 0.386 | 50.0% |
| JW30 / bilabial-stop | 2 | 0.300 | 0.281 | 0.318 | 0.0% |
| JW30 / vowel | 22 | 0.398 | -0.270 | 0.994 | 40.9% |
| JW31 / alveolar-fricative | 7 | 0.457 | 0.056 | 0.873 | 28.6% |
| JW31 / alveolar-nasal | 6 | 0.404 | 0.251 | 0.556 | 16.7% |
| JW31 / alveolar-stop | 7 | 0.515 | 0.197 | 0.816 | 14.3% |
| JW31 / bilabial-nasal | 2 | 0.808 | 0.728 | 0.887 | 0.0% |
| JW31 / bilabial-stop | 4 | 0.425 | 0.392 | 0.439 | 0.0% |
| JW31 / vowel | 33 | 0.329 | -0.418 | 0.815 | 45.5% |
| JW32 / alveolar-fricative | 7 | -0.045 | -0.106 | 0.098 | 57.1% |
| JW32 / alveolar-nasal | 6 | 0.535 | 0.430 | 0.676 | 16.7% |
| JW32 / alveolar-stop | 7 | 0.174 | -0.105 | 0.880 | 42.9% |
| JW32 / bilabial-nasal | 2 | 0.587 | 0.555 | 0.619 | 0.0% |
| JW32 / bilabial-stop | 4 | 0.501 | 0.454 | 0.516 | 0.0% |
| JW32 / vowel | 33 | 0.357 | -0.169 | 0.895 | 30.3% |
| JW33 / alveolar-fricative | 7 | 0.847 | 0.307 | 1.109 | 0.0% |
| JW33 / alveolar-nasal | 6 | 0.461 | 0.294 | 0.565 | 16.7% |
| JW33 / alveolar-stop | 7 | 0.580 | 0.532 | 0.728 | 14.3% |
| JW33 / bilabial-nasal | 2 | 1.086 | 0.942 | 1.229 | 0.0% |
| JW33 / bilabial-stop | 4 | 0.281 | 0.257 | 0.381 | 0.0% |
| JW33 / vowel | 33 | 0.564 | -0.354 | 0.944 | 27.3% |
| JW34 / alveolar-fricative | 7 | 0.437 | 0.317 | 0.939 | 0.0% |
| JW34 / alveolar-nasal | 6 | 0.531 | 0.313 | 0.972 | 0.0% |
| JW34 / alveolar-stop | 7 | 0.330 | 0.049 | 0.973 | 14.3% |
| JW34 / bilabial-nasal | 2 | 0.384 | 0.376 | 0.392 | 0.0% |
| JW34 / bilabial-stop | 4 | 0.519 | 0.399 | 0.637 | 0.0% |
| JW34 / vowel | 22 | 0.821 | -0.072 | 1.314 | 27.3% |
| JW35 / alveolar-fricative | 7 | 0.140 | -0.221 | 1.290 | 42.9% |
| JW35 / alveolar-nasal | 6 | 0.369 | 0.273 | 0.686 | 16.7% |
| JW35 / alveolar-stop | 7 | 0.552 | 0.384 | 0.786 | 14.3% |
| JW35 / bilabial-nasal | 2 | 0.850 | 0.693 | 1.007 | 0.0% |
| JW35 / bilabial-stop | 4 | 0.379 | 0.245 | 0.504 | 0.0% |
| JW35 / vowel | 33 | 0.708 | -0.081 | 1.407 | 27.3% |
| JW36 / alveolar-fricative | 7 | 0.628 | 0.296 | 0.936 | 14.3% |
| JW36 / alveolar-nasal | 6 | 0.413 | 0.284 | 0.545 | 0.0% |
| JW36 / alveolar-stop | 7 | 0.284 | 0.145 | 0.678 | 14.3% |
| JW36 / bilabial-nasal | 2 | 1.169 | 0.902 | 1.436 | 0.0% |
| JW36 / bilabial-stop | 4 | 0.310 | 0.265 | 0.379 | 0.0% |
| JW36 / vowel | 33 | 0.773 | 0.273 | 1.464 | 21.2% |
| JW37 / alveolar-fricative | 7 | -0.048 | -0.173 | 0.600 | 57.1% |
| JW37 / alveolar-nasal | 6 | 0.522 | 0.465 | 0.663 | 0.0% |
| JW37 / alveolar-stop | 7 | 0.505 | 0.182 | 1.060 | 14.3% |
| JW37 / bilabial-nasal | 2 | 0.370 | 0.366 | 0.373 | 0.0% |
| JW37 / bilabial-stop | 4 | 0.477 | 0.391 | 0.686 | 0.0% |
| JW37 / vowel | 33 | 0.697 | -0.245 | 1.104 | 36.4% |
| JW39 / alveolar-fricative | 7 | 0.458 | 0.227 | 0.745 | 0.0% |
| JW39 / alveolar-nasal | 6 | 0.432 | 0.425 | 0.468 | 0.0% |
| JW39 / alveolar-stop | 7 | 0.088 | -0.082 | 0.250 | 42.9% |
| JW39 / bilabial-nasal | 2 | 0.809 | 0.710 | 0.908 | 0.0% |
| JW39 / bilabial-stop | 4 | 0.371 | 0.331 | 0.449 | 0.0% |
| JW39 / vowel | 33 | 0.446 | -0.440 | 1.215 | 39.4% |
| JW40 / alveolar-fricative | 3 | 0.868 | 0.798 | 1.031 | 0.0% |
| JW40 / alveolar-nasal | 3 | 0.452 | 0.447 | 0.517 | 0.0% |
| JW40 / alveolar-stop | 3 | 0.020 | -0.262 | 0.227 | 33.3% |
| JW40 / bilabial-stop | 2 | 0.340 | 0.313 | 0.368 | 0.0% |
| JW40 / vowel | 11 | 0.618 | -0.143 | 1.384 | 36.4% |
| JW41 / alveolar-fricative | 7 | 0.300 | 0.238 | 0.731 | 14.3% |
| JW41 / alveolar-nasal | 6 | 0.413 | 0.363 | 0.442 | 16.7% |
| JW41 / alveolar-stop | 7 | 0.139 | 0.039 | 0.480 | 14.3% |
| JW41 / bilabial-nasal | 2 | 0.303 | 0.298 | 0.309 | 0.0% |
| JW41 / bilabial-stop | 4 | 0.358 | 0.301 | 0.449 | 0.0% |
| JW41 / vowel | 33 | 0.561 | -0.399 | 1.583 | 39.4% |
| JW42 / alveolar-fricative | 7 | 0.603 | 0.525 | 1.145 | 0.0% |
| JW42 / alveolar-nasal | 6 | 0.584 | 0.335 | 0.606 | 16.7% |
| JW42 / alveolar-stop | 7 | 0.587 | 0.161 | 0.632 | 28.6% |
| JW42 / bilabial-nasal | 2 | 0.994 | 0.845 | 1.144 | 0.0% |
| JW42 / bilabial-stop | 4 | 0.361 | 0.331 | 0.390 | 0.0% |
| JW42 / vowel | 33 | 0.528 | -0.289 | 0.982 | 36.4% |
| JW43 / alveolar-fricative | 7 | 0.215 | 0.165 | 0.655 | 14.3% |
| JW43 / alveolar-nasal | 6 | 0.247 | -0.300 | 0.443 | 33.3% |
| JW43 / alveolar-stop | 7 | 0.477 | 0.277 | 0.506 | 14.3% |
| JW43 / bilabial-nasal | 2 | 0.480 | 0.460 | 0.499 | 0.0% |
| JW43 / bilabial-stop | 4 | 0.321 | 0.307 | 0.335 | 0.0% |
| JW43 / vowel | 33 | 0.285 | -0.535 | 0.883 | 45.5% |
| JW44 / alveolar-fricative | 7 | 0.464 | 0.214 | 0.994 | 14.3% |
| JW44 / alveolar-nasal | 6 | 0.468 | 0.225 | 0.570 | 16.7% |
| JW44 / alveolar-stop | 7 | 0.403 | 0.214 | 0.687 | 0.0% |
| JW44 / bilabial-nasal | 2 | 1.068 | 0.841 | 1.295 | 0.0% |
| JW44 / bilabial-stop | 4 | 0.372 | 0.318 | 0.419 | 0.0% |
| JW44 / vowel | 33 | 0.639 | 0.060 | 1.428 | 24.2% |
| JW45 / alveolar-fricative | 7 | 0.067 | 0.036 | 0.106 | 14.3% |
| JW45 / alveolar-nasal | 5 | 0.498 | 0.361 | 0.617 | 20.0% |
| JW45 / alveolar-stop | 6 | 0.773 | 0.288 | 1.348 | 16.7% |
| JW45 / bilabial-nasal | 2 | 0.673 | 0.463 | 0.882 | 0.0% |
| JW45 / bilabial-stop | 4 | 0.287 | 0.260 | 0.324 | 0.0% |
| JW45 / vowel | 33 | 0.516 | -0.001 | 0.986 | 27.3% |
| JW46 / alveolar-fricative | 7 | 0.554 | 0.422 | 0.793 | 14.3% |
| JW46 / alveolar-nasal | 6 | 0.428 | 0.399 | 0.667 | 0.0% |
| JW46 / alveolar-stop | 7 | 0.320 | 0.054 | 0.717 | 28.6% |
| JW46 / bilabial-nasal | 2 | 0.271 | 0.198 | 0.344 | 0.0% |
| JW46 / bilabial-stop | 4 | 0.383 | 0.354 | 0.395 | 0.0% |
| JW46 / vowel | 33 | 0.562 | -0.248 | 1.130 | 39.4% |
| JW48 / alveolar-fricative | 7 | 0.375 | 0.024 | 0.644 | 28.6% |
| JW48 / alveolar-nasal | 6 | 0.491 | 0.226 | 1.285 | 16.7% |
| JW48 / alveolar-stop | 7 | 0.137 | -0.213 | 0.431 | 42.9% |
| JW48 / bilabial-nasal | 2 | 0.781 | 0.625 | 0.938 | 0.0% |
| JW48 / bilabial-stop | 4 | 0.422 | 0.372 | 0.709 | 0.0% |
| JW48 / vowel | 33 | 0.718 | 0.428 | 1.364 | 18.2% |
| JW49 / alveolar-fricative | 4 | 0.674 | 0.206 | 1.167 | 0.0% |
| JW49 / alveolar-nasal | 3 | 0.613 | 0.255 | 0.829 | 33.3% |
| JW49 / alveolar-stop | 4 | 0.584 | 0.391 | 0.812 | 0.0% |
| JW49 / bilabial-nasal | 2 | 0.763 | 0.747 | 0.779 | 0.0% |
| JW49 / bilabial-stop | 2 | 0.360 | 0.360 | 0.360 | 0.0% |
| JW49 / vowel | 22 | 0.829 | 0.269 | 1.269 | 22.7% |
| JW502 / alveolar-fricative | 7 | 0.075 | -0.083 | 0.190 | 28.6% |
| JW502 / alveolar-nasal | 6 | 0.451 | 0.381 | 0.574 | 0.0% |
| JW502 / alveolar-stop | 7 | 0.623 | 0.135 | 1.191 | 14.3% |
| JW502 / bilabial-nasal | 2 | 0.813 | 0.684 | 0.942 | 0.0% |
| JW502 / bilabial-stop | 4 | 0.469 | 0.401 | 0.748 | 0.0% |
| JW502 / vowel | 33 | 0.431 | -0.157 | 1.317 | 30.3% |
| JW51 / alveolar-fricative | 5 | 0.576 | 0.428 | 0.702 | 20.0% |
| JW51 / alveolar-nasal | 5 | 0.654 | 0.632 | 0.662 | 0.0% |
| JW51 / alveolar-stop | 6 | 0.612 | 0.462 | 0.638 | 0.0% |
| JW51 / bilabial-nasal | 2 | 0.705 | 0.673 | 0.737 | 0.0% |
| JW51 / bilabial-stop | 4 | 0.342 | 0.336 | 0.350 | 0.0% |
| JW51 / vowel | 31 | 0.670 | -0.402 | 1.347 | 35.5% |
| JW52 / alveolar-fricative | 7 | 0.686 | 0.368 | 0.753 | 0.0% |
| JW52 / alveolar-nasal | 6 | 0.490 | 0.134 | 0.934 | 0.0% |
| JW52 / alveolar-stop | 7 | 0.209 | -0.219 | 0.886 | 42.9% |
| JW52 / bilabial-nasal | 2 | 0.535 | 0.533 | 0.537 | 0.0% |
| JW52 / bilabial-stop | 4 | 0.439 | 0.379 | 0.504 | 0.0% |
| JW52 / vowel | 33 | 0.634 | 0.035 | 1.099 | 21.2% |
| JW53 / alveolar-fricative | 7 | 0.402 | 0.185 | 0.608 | 0.0% |
| JW53 / alveolar-nasal | 6 | 0.701 | 0.443 | 0.860 | 0.0% |
| JW53 / alveolar-stop | 7 | 0.508 | 0.140 | 0.906 | 14.3% |
| JW53 / bilabial-nasal | 2 | 0.750 | 0.626 | 0.875 | 0.0% |
| JW53 / bilabial-stop | 4 | 0.337 | 0.307 | 0.352 | 0.0% |
| JW53 / vowel | 33 | 0.532 | 0.090 | 1.099 | 21.2% |
| JW54 / alveolar-fricative | 7 | 0.131 | -0.346 | 0.593 | 42.9% |
| JW54 / alveolar-nasal | 6 | 0.682 | 0.579 | 1.207 | 0.0% |
| JW54 / alveolar-stop | 7 | 1.206 | 0.812 | 1.511 | 0.0% |
| JW54 / bilabial-nasal | 2 | 0.811 | 0.516 | 1.105 | 0.0% |
| JW54 / bilabial-stop | 4 | 0.412 | 0.339 | 0.793 | 0.0% |
| JW54 / vowel | 33 | 0.473 | -0.250 | 1.235 | 36.4% |
| JW55 / alveolar-fricative | 7 | 0.818 | 0.159 | 1.133 | 0.0% |
| JW55 / alveolar-nasal | 6 | 0.377 | 0.278 | 0.464 | 0.0% |
| JW55 / alveolar-stop | 7 | 0.632 | 0.312 | 0.821 | 14.3% |
| JW55 / bilabial-nasal | 2 | 0.873 | 0.757 | 0.988 | 0.0% |
| JW55 / bilabial-stop | 4 | 0.415 | 0.220 | 0.542 | 25.0% |
| JW55 / vowel | 33 | 0.616 | -0.011 | 1.334 | 27.3% |
| JW56 / alveolar-fricative | 7 | 0.310 | -0.028 | 0.659 | 28.6% |
| JW56 / alveolar-nasal | 6 | 0.487 | 0.410 | 0.539 | 16.7% |
| JW56 / alveolar-stop | 7 | 0.241 | 0.060 | 0.664 | 14.3% |
| JW56 / bilabial-nasal | 2 | 0.784 | 0.657 | 0.911 | 0.0% |
| JW56 / bilabial-stop | 4 | 0.461 | 0.362 | 0.532 | 0.0% |
| JW56 / vowel | 33 | 0.470 | -0.227 | 1.317 | 33.3% |
| JW57 / alveolar-fricative | 7 | 0.327 | 0.120 | 0.924 | 0.0% |
| JW57 / alveolar-nasal | 6 | 0.321 | 0.267 | 0.359 | 16.7% |
| JW57 / alveolar-stop | 7 | 0.387 | -0.008 | 0.454 | 28.6% |
| JW57 / bilabial-nasal | 2 | 0.950 | 0.771 | 1.129 | 0.0% |
| JW57 / bilabial-stop | 4 | 0.454 | 0.413 | 0.458 | 0.0% |
| JW57 / vowel | 33 | 0.500 | -0.386 | 1.350 | 36.4% |
| JW58 / alveolar-fricative | 7 | 0.972 | 0.092 | 1.259 | 28.6% |
| JW58 / alveolar-nasal | 6 | 0.572 | 0.392 | 0.644 | 16.7% |
| JW58 / alveolar-stop | 7 | 0.181 | -0.172 | 0.463 | 42.9% |
| JW58 / bilabial-nasal | 2 | 1.063 | 0.855 | 1.271 | 0.0% |
| JW58 / bilabial-stop | 4 | 0.241 | 0.018 | 0.355 | 25.0% |
| JW58 / vowel | 33 | 0.475 | -0.300 | 1.366 | 36.4% |
| JW59 / alveolar-fricative | 7 | 0.296 | 0.134 | 0.896 | 28.6% |
| JW59 / alveolar-nasal | 6 | 0.440 | 0.058 | 0.542 | 33.3% |
| JW59 / alveolar-stop | 7 | 0.492 | 0.390 | 0.840 | 0.0% |
| JW59 / bilabial-nasal | 2 | 0.721 | 0.611 | 0.831 | 0.0% |
| JW59 / bilabial-stop | 4 | 0.385 | 0.284 | 0.473 | 0.0% |
| JW59 / vowel | 33 | 0.416 | -0.163 | 0.822 | 30.3% |
| JW60 / alveolar-fricative | 5 | 0.451 | -0.421 | 1.065 | 40.0% |
| JW60 / alveolar-nasal | 6 | 0.589 | 0.249 | 0.747 | 16.7% |
| JW60 / alveolar-stop | 7 | 0.695 | -0.067 | 1.270 | 28.6% |
| JW60 / bilabial-nasal | 2 | 0.747 | 0.679 | 0.815 | 0.0% |
| JW60 / bilabial-stop | 4 | 0.427 | 0.397 | 0.460 | 0.0% |
| JW60 / vowel | 30 | 0.613 | -0.006 | 1.390 | 26.7% |
| JW61 / alveolar-fricative | 7 | 0.454 | 0.290 | 1.099 | 0.0% |
| JW61 / alveolar-nasal | 6 | 0.688 | 0.603 | 1.668 | 0.0% |
| JW61 / alveolar-stop | 7 | 0.729 | 0.026 | 1.240 | 28.6% |
| JW61 / bilabial-nasal | 2 | 1.013 | 0.876 | 1.150 | 0.0% |
| JW61 / bilabial-stop | 4 | 0.277 | 0.245 | 0.344 | 0.0% |
| JW61 / vowel | 33 | 0.508 | -0.190 | 1.294 | 33.3% |
| JW62 / alveolar-fricative | 7 | 0.015 | -0.109 | 0.696 | 42.9% |
| JW62 / alveolar-nasal | 6 | 0.590 | 0.415 | 0.904 | 16.7% |
| JW62 / alveolar-stop | 7 | 0.974 | 0.656 | 1.233 | 14.3% |
| JW62 / bilabial-nasal | 2 | 0.959 | 0.708 | 1.210 | 0.0% |
| JW62 / bilabial-stop | 4 | 0.659 | 0.528 | 1.211 | 0.0% |
| JW62 / vowel | 33 | 0.955 | 0.239 | 1.329 | 24.2% |
| JW63 / alveolar-fricative | 7 | -0.103 | -0.213 | 0.530 | 71.4% |
| JW63 / alveolar-nasal | 6 | 0.446 | 0.321 | 0.539 | 16.7% |
| JW63 / alveolar-stop | 7 | 0.750 | 0.124 | 0.856 | 28.6% |
| JW63 / bilabial-nasal | 2 | 0.836 | 0.696 | 0.977 | 0.0% |
| JW63 / bilabial-stop | 4 | 0.390 | 0.347 | 0.400 | 0.0% |
| JW63 / vowel | 33 | 0.752 | -0.057 | 1.469 | 27.3% |

## By segment duration

| group | n | median | Q1 | Q3 | before onset |
|---|---:|---:|---:|---:|---:|
| alveolar-fricative / short (< 0.110 s) | 143 | 0.330 | 0.058 | 0.716 | 20.3% |
| alveolar-fricative / long (>= 0.110 s) | 165 | 0.471 | 0.131 | 1.033 | 16.4% |
| alveolar-nasal / short (< 0.090 s) | 120 | 0.560 | 0.103 | 0.796 | 23.3% |
| alveolar-nasal / long (>= 0.090 s) | 148 | 0.432 | 0.324 | 0.572 | 1.4% |
| alveolar-stop / short (< 0.070 s) | 136 | 0.505 | 0.119 | 0.931 | 15.4% |
| alveolar-stop / long (>= 0.070 s) | 175 | 0.347 | 0.025 | 0.779 | 23.4% |
| bilabial-nasal / short (< 0.090 s) | 39 | 0.612 | 0.465 | 0.749 | 2.6% |
| bilabial-nasal / long (>= 0.090 s) | 51 | 0.740 | 0.526 | 1.126 | 0.0% |
| bilabial-stop / short (< 0.090 s) | 90 | 0.403 | 0.314 | 0.513 | 2.2% |
| bilabial-stop / long (>= 0.090 s) | 91 | 0.360 | 0.306 | 0.429 | 0.0% |
| vowel / short (< 0.090 s) | 696 | 0.548 | -0.591 | 1.654 | 42.0% |
| vowel / long (>= 0.090 s) | 777 | 0.616 | 0.137 | 1.004 | 21.0% |

The duration split shows rate drift: target fractions change between short and long segments, so the normalized anchor is not perfectly rate-invariant.

## Recommendation

Center-anchoring is supported for bilabial stops, and to a lesser degree the nasals; support is weak for alveolar stops; vowels and alveolar fricatives are UNMEASURED with these detectors. There is no evidence here for one global anchor. The sampler's center default remains reasonable as a default—supported where measurable and uncontradicted elsewhere—but this study does not justify class-specific recommendations for the NON-INFORMATIVE detectors.

## Alignment refusals

Aligned task files: **91**. Refused or missing task files: **5**. Refusals are listed rather than silently dropped.

- `JW18/tp007: alignment failed for transcript 'she is about two or three when can we go home hispanic costumes are quite colorful': Failed to stop utterance processing`
- `JW20/tp007: alignment failed for transcript 'she is about two or three when can we go home hispanic costumes are quite colorful': Failed to stop utterance processing`
- `JW30/tp002: alignment failed for transcript 'nothing this street even special children ship': Failed to set up sub-word alignment`
- `JW40/tp007: missing wav or track`
- `JW49/tp002: missing wav or track`

## Scope and provenance

Targets use kinematics alone inside a 60 ms padded acoustic window: UL-LL distance minima for bilabials, T1-to-`PAL.DAT` clearance minima for alveolars, and T3/T4 speed minima for vowels. Local outer 0.1% observable samples are discarded under the same quantile rationale as `scripts/articulatory.py`; missing sentinels are never interpolated. Anchor fraction is exactly `(t_event - t_onset) / duration`.

This grounds target timing for the measured XRMB English reading tasks and these pellet observables. It does not ground unmeasured places, other languages, spontaneous speech, causal accounts of anticipation, or the acoustic aligner's phone boundaries.

Detector repair is a separate future lane: vowel event detection needs a formant-domain or richer-kinematic approach, and the ±60 ms pad swamps short segments. The same limitation applies to treating the current alveolar-fricative result as a target measurement.

Prompts are task 2 (citation words) and task 7 (sentences), transcribed in `tests/fixtures/xrmb_anchor_prompts.json` from Westbury, Turner & Dembowski (1994), *X-Ray Microbeam Speech Production Database User's Handbook*, Appendix A, pp. 84-85. Handbook PDF: <https://www.ling.uni-potsdam.de/~gafos/fhs_atelier/ubdbman.pdf> (accessed 2026-08-10). Oral-motor tasks were excluded.

The corpus is licensed external data, was read in place, and no corpus content is included here.
