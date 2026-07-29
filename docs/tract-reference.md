# The tract, in detail

The reference drawing and the numbers behind it. [tract-figures.md](tract-figures.md) is the shorter read — what the drawing shows, with worked examples — and leaves this detail here.

![The tract at rest, every landmark named](figures/tract-reference.svg)

Every landmark the head declares, at the rest posture. A figure for a single phone names only the landmarks that phone uses, so this is the key to those.

Every landmark below is declared in `ipa.xml` and read by `ipakit.tract.landmarks`, so this table and the figures cannot disagree.

### Places

| place | arc | articulator | frication |
|---|---|---|---|
| `bilabial` | 0.00 | lower-lip | yes |
| `labiodental` | 0.03 | lower-lip | yes |
| `dental` | 0.08 | tongue-tip | yes |
| `alveolar` | 0.13 | tongue-tip | yes |
| `postalveolar` | 0.19 | tongue-blade | yes |
| `alveolo-palatal` | 0.24 | tongue-blade | yes |
| `palatal` | 0.32 | tongue-front | yes |
| `velar` | 0.45 | tongue-dorsum | yes |
| `uvular` | 0.56 | tongue-dorsum | yes |
| `pharyngeal` | 0.74 | tongue-root | yes |
| `epiglottal` | 0.87 | epiglottis | yes |
| `glottal` | 1.00 | vocal-folds | yes |

The two combining places, `bilabial^velar` and `bilabial^palatal`, declare no arc: their position is their components' rather than a point of their own, so they are not drawn.

### Articulators

| articulator | arc | closes |
|---|---|---|
| `lower-lip` | 0.00 | toward the wall |
| `tongue-tip` | 0.13 | toward the wall |
| `tongue-blade` | 0.19 | toward the wall |
| `tongue-front` | 0.32 | toward the wall |
| `tongue-dorsum` | 0.45 | toward the wall |
| `tongue-root` | 0.74 | toward the wall |
| `epiglottis` | 0.87 | toward the wall |
| `vocal-folds` | 1.00 | toward the tract axis |

The glottis closes toward the tract axis rather than toward a wall — the folds meet each other — which `offset` does not model, so it is drawn centred and its degree of closure is not shown.

### The adult midline

| arc | aperture | provenance |
|---|---|---|
| 0.00 | 0.160 | extrapolated |
| 0.13 | 0.170 | extrapolated |
| 0.24 | 0.180 | measured |
| 0.32 | 0.160 | measured |
| 0.40 | 0.130 | measured |
| 0.45 | 0.130 | extrapolated |
| 0.56 | 0.123 | extrapolated |
| 0.74 | 0.108 | extrapolated |
| 0.87 | 0.094 | extrapolated |
| 1.00 | 0.079 | extrapolated |

`adult-female` takes the same shape against its own peak; the child head is hand-placed throughout.

## Provenance

*Measured* is the aperture taken from the X-Ray Microbeam database over 48 speakers. That corpus has no upper wall forward of arc 0.11 and none behind arc 0.44, so everything outside that span is extrapolated, and the nasal branch, both dentitions, the tongue's falloff and the child head are hand-placed throughout. Each point in `heads.xml` states which it is.

The one measured relation beyond the aperture is the jaw's: `heads.xml` declares a carriage profile, the fraction of what sits at each arc that the mandible carries, 0.66 at the lips falling to 0.013 by arc 0.60. The mandible constricts nothing — it is what the lower lip, the lower teeth and the tongue's anterior attachment ride on, so its position sets how open that part of the tract can be.

See [articulatory-data.md](articulatory-data.md) for what that corpus can and cannot ground, and [tract-anatomy.md](tract-anatomy.md) for the specification these figures partially implement.
