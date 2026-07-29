# Vocal tract anatomy: contours, articulators, constraints

*Specification, not implemented. The current model (`ipakit/tract.py`) carries a tract midline and a constriction point per phone — enough to place a segment in space, not enough to draw a tract or move an articulator. This document specifies the geometry that a renderer, an animator, or a derived-anchor pipeline would need: every contour, every joint, every attachment, and the constraints that relate them.*

## 1. Scope

The model is **mid-sagittal**: a single plane through the midline of the head. Lateral structure (tongue grooving, lateral airflow for `l`, bilateral clicks) is out of scope and must be noted where it matters rather than silently misrepresented.

The model is **kinematic**, not biomechanical: it specifies where structures are and how they may move, not the muscles that move them or the forces involved.

Everything is **normalized** to a head's own dimensions, so one geometry serves any head shape (§8).

## 2. Reference frame

A right-handed 2D frame fixed to the **skull**, so that mobile structures move within it:

| | |
|---|---|
| origin | the anterior nasal spine (the bony point at the base of the nasal aperture) — a standard cephalometric landmark, fixed, and near enough to the tract to keep coordinates small |
| **+x** | posterior (toward the back of the head) |
| **+y** | superior (toward the top of the head) |
| units | fractions of the head's own vertical facial height, so geometries scale |

The tract-space axes used by distance (`+x` lips→glottis, `+y` jaw→palate) are a *derived* frame that follows the airway, not this fixed one. The two coincide only over the oral run; the pharynx bends.

## 3. Fixed contours

These belong to the skull and do not move. They are the passive half of every constriction.

| contour | extent | notes |
|---|---|---|
| **upper lip** | vermilion border to the labial sulcus | mobile in aperture and protrusion (§4.4) but anchored on the maxilla |
| **maxillary teeth** | incisal edge of the upper incisors, then the arch line | the incisal edge is the labiodental target |
| **alveolar ridge** | from behind the upper incisors to the start of the palatal dome | the ridge crest is the alveolar target; its posterior slope is the postalveolar target |
| **hard palate** | alveolar ridge to the hard/soft palate junction | a concave dome; the palatal target lies at its highest point |
| **soft palate (velum)** | hard palate junction to the uvular tip | **mobile** (§4.3); its lowered contour is the roof of the oral tract, its raised contour closes the nasopharynx |
| **posterior pharyngeal wall** | nasopharynx down to the laryngopharynx | roughly vertical; the pharyngeal and epiglottal targets lie on it |
| **nasal cavity** | above the hard palate, from the velopharyngeal port to the nostrils | fixed volume; couples to the tract only when the port is open |
| **laryngeal vestibule** | above the vocal folds to the aryepiglottic folds | its lower bound is the glottis |

The **tract outline** is the union of the upper boundary (upper lip → teeth → alveolar ridge → hard palate → velum → posterior pharyngeal wall → laryngeal vestibule) and the lower boundary (lower lip → lower teeth → tongue surface → epiglottis → laryngeal vestibule). Only the upper boundary is fixed; the lower is articulator-dependent, which is why the airway must be derived rather than declared (§6).

## 4. Mobile articulators

Each is specified by what it is, its degrees of freedom, what it attaches to, and what it carries.

### 4.1 Mandible

| | |
|---|---|
| joint | temporomandibular, a condyle posterior and superior to the tooth row |
| degrees of freedom | **rotation** about the condyle (opening); **translation** (protrusion), significant only at wide openings |
| carries | mandibular teeth, **lower lip**, and the anterior attachment of the tongue |
| constraint | rotation is bounded; the closed position (teeth in occlusion) is one limit |

The mandible is a **carrier**: opening it lowers the lower lip and the tongue's anterior attachment together. This is why jaw position, tongue height, and lip aperture are not independent, and why a model that treats them as independent will produce impossible postures.

### 4.2 Tongue

| | |
|---|---|
| regions | root (pharyngeal), dorsum (body), blade (lamina), tip (apex) |
| attachments | mandible at the symphysis (genioglossus origin), hyoid bone posteriorly |
| degrees of freedom | body position (2: front↔back, high↔low), tip position relative to the body (2: raised↔lowered, advanced↔retracted); optionally a root parameter for pharyngeal constriction |
| constraint | **volume conservation** — the tongue is effectively incompressible, so advancing the tip retracts the root, and raising the body narrows one region while widening another |
| constraint | the tip's reach is bounded relative to the body; the body's position is bounded by the jaw that carries it |

The tongue surface forms the lower boundary of the oral tract and the anterior boundary of the pharynx. It is one continuous curve, not independent points, and that continuity is what makes coarticulation geometric rather than stipulated.

**Out of plane**: tongue grooving (central vs lateral airflow) is not representable mid-sagittally. Laterals and lateral clicks need an annotation, not a contour.

### 4.3 Velum

| | |
|---|---|
| attachment | posterior edge of the hard palate |
| degrees of freedom | one: raised ↔ lowered |
| set points | **raised** — velopharyngeal port closed, airflow oral; **lowered** — port open, nasal cavity coupled |
| carries | the uvula at its free end |

The port aperture is the gap between the velum's free edge and the posterior pharyngeal wall. It is continuous in reality, and the two set points are the ends of that range: a nasalized vowel sits between them.

### 4.4 Lips

| | |
|---|---|
| upper lip | anchored on the maxilla |
| lower lip | carried by the mandible |
| degrees of freedom | **aperture** (the gap between the vermilion borders) and **protrusion** (forward displacement of both) |
| constraint | aperture ≥ 0; jaw opening contributes to aperture through the lower lip |

Protrusion **lengthens the tract**, which is the acoustic consequence of rounding; ipakit currently encodes rounding as a feature (`rounded`) and does not model protrusion as geometry.

### 4.5 Larynx and glottis

| | |
|---|---|
| degrees of freedom | vertical position (raise ↔ lower); glottal aperture |
| effect of height | **lowering lengthens the tract**, raising shortens it |
| glottal aperture | the gap between the vocal folds: closed (glottal stop), narrow (voicing), open (voiceless, breath) |

Larynx height is the source of vocal-tract-length variation *within* a speaker; head shape accounts for variation *between* speakers (§8).

### 4.6 Epiglottis

| | |
|---|---|
| attachment | base of the tongue, above the larynx |
| degrees of freedom | one: upright ↔ retracted |
| role | the epiglottal constriction target; passively displaced by tongue-root retraction |

## 5. Constraint and dependency graph

What determines what. An implementation must respect this order, because downstream quantities are meaningless if computed from a posture that violates an upstream constraint.

```
jaw rotation ──┬──> lower teeth position
               ├──> lower lip position ────┐
               └──> tongue anterior attach ─┤
                                            │
tongue body + tip parameters ───────────────┼──> tongue surface curve
                                            │
larynx height ──────────────────────────────┼──> tract length, glottis position
                                            │
velum position ─────────────────────────────┼──> velopharyngeal port aperture
                                            │
lip aperture + protrusion ──────────────────┘
                                            │
                                            v
                         tract outline (upper fixed + lower derived)
                                            │
                                            v
                    airway centerline, aperture function along it
                                            │
                                            v
                     constriction location, degree, articulator
```

**Invariants an implementation must not violate:**

1. **Tongue volume is conserved.** Any parameterization that lets the tongue expand or vanish is wrong.
2. **The jaw carries what it carries.** Lower lip and tongue attachment move with it; they are not free.
3. **Reach is bounded.** The tip cannot reach arbitrarily far from the body; the body cannot leave the space the jaw allows.
4. **No self-intersection.** The tongue surface may touch the upper boundary (a closure) but not cross it.
5. **Apertures are non-negative.** Closure is zero, not negative.
6. **The nasal branch couples only through the port.** A raised velum decouples it entirely.

## 6. Derived quantities

None of these are declared; all follow from the posture.

| quantity | derivation |
|---|---|
| **tract outline** | upper fixed boundary + lower articulator-dependent boundary |
| **airway centerline** | the medial axis between the boundaries — what `ipakit/tract.py` currently *declares* as `midline` |
| **aperture function** | boundary-to-boundary distance along the centerline — what `diameter` currently approximates |
| **constriction location** | the centerline position of minimum aperture — what `arc` currently declares |
| **constriction degree** | normalized minimum aperture — what `offset` currently declares |
| **active articulator** | which mobile structure forms the constriction at that location — what the place table currently declares as a default |

That correspondence is the point: **the current model's hand-placed anchors are what this geometry would compute.** Building the anatomy makes them derivable, and removes the "schematic, not measurements" caveat that `docs/distance.md` carries today.

## 7. Postures

A **posture** is a complete assignment of the mobile parameters — roughly nine numbers: jaw rotation, jaw protrusion, tongue body (2), tongue tip (2), velum, lip aperture, lip protrusion, larynx height, glottal aperture.

**Rest** is the posture with the jaw closed, lips lightly together, tongue neutral against the palate, velum lowered for nasal breathing, larynx neutral, glottis open. It is where an utterance begins and ends. The current model records rest as a point and three labels; under this specification it is a full parameter vector.

A phone's target is a *constriction* specification (articulator, location, degree). Solving for the posture that achieves it is inverse kinematics, and is underdetermined — several postures reach the same constriction. That indeterminacy is real, not a modelling defect: it is what makes motor equivalence possible, and a renderer resolves it with a cost function (least movement from the previous posture, typically), which is also what produces plausible coarticulation.

## 8. Head shapes

A head shape supplies the fixed contours and the joint locations; postures are expressed in normalized parameters that any head can interpret. Known proportional differences a shipped set should reflect:

- A child's tract is shorter overall and **proportionally** shorter in the pharynx; the larynx sits higher and the oral/pharyngeal ratio differs from an adult's.
- An adult female tract is shorter than an adult male's, again more so in the pharynx than in the oral cavity.

These are proportions, not scalings: uniform scaling of an adult tract does not produce a child's.

## 9. Data shape

Declared per head, in `data/heads.xml` or a successor:

- **Fixed contours** as control-point curves: upper lip, maxillary teeth, alveolar ridge, hard palate, velum (in both set positions), posterior pharyngeal wall, nasal cavity, laryngeal vestibule.
- **Joints and landmarks**: condyle position, symphysis (tongue anterior attachment), hyoid, hard/soft palate junction, velopharyngeal port location, glottis position.
- **Bounds**: jaw rotation range, tongue reach envelope, lip aperture range, larynx travel.
- **Rest posture** as a full parameter vector.

Phones stay head-independent: they declare constriction targets, never postures.

## 10. Figures

[tract-figures.md](tract-figures.md) draws the declared geometry — a labelled reference at rest and eight phones — regenerated by `make figures` and checked in. The drawing goes through `Head.project` and computes nothing of its own, which is what made it useful as a check: a projection defect showed up there as a wall crossing itself while the numbers looked ordinary.

## 11. Open questions

- **Tongue parameterization.** A body arc plus a tip offset (three to four parameters) covers the attested inventory and keeps inverse kinematics tractable; a free spline is more faithful and much harder to constrain. The arc is probably right, but the choice should be tested against the awkward cases — retroflexes, and the tongue-root distinction in ATR systems.
- **Where lateral information lives.** Mid-sagittal geometry cannot represent grooving. An annotation on the segment is the pragmatic answer; a second (coronal) plane is the faithful one.
- **Whether anchors become derived.** Deriving `arc` and `offset` from geometry would remove hand-placed numbers, but makes every distance depend on the anatomy model being right. Deriving them and *checking* them against the current hand-placed values is the safer sequence.
- **The velic seam is not closed, so this geometry cannot be simulated as it stands.** The nasal branch and the oral roof are declared independently and do not meet: on the adult male head the oral roof at the port sits at (0.627, 0.746) and the branch's floor ends at (0.680, 0.677), a gap of **0.087** — wider than the branch's own cross-section there, 0.072. The gap is present whatever the velum is doing, including for an oral segment whose port is nominally sealed, because the velum's raised position reaches the branch's *midline* rather than a surface that closes against the roof. Drawn, this is invisible: the filled shapes overlap. Given to a wave solver it is a hole no parameter controls, and the tract would leak at the seam. Closing it in the *drawing* is cosmetic. It matters only if the sagittal outline is taken to be the acoustic model, and it should not be: a waveguide synthesiser does not need a watertight outline, it needs area functions and a junction. Pink Trombone (Neil Thapen, 2017, MIT) is the worked example — 44 oral sections and 28 nasal ones as 1D area arrays, meeting at a three-port scattering junction where exactly three areas sum, `A[noseStart] + A[noseStart+1] + noseA[0]`, with the velum not a flap but a single number, `noseDiameter[0]`, moving between 0.01 closed and 0.4 open.

Read that way this model is closer than it looks. `diameter` along `arc` already is an aperture function; the nasal branch already carries its own; and `velic_aperture` already yields the coupling number from the nasality bridge. What is missing is the **junction declared as such** — an arc at which the oral and nasal apertures meet, so the three can be sampled together. The 2D seam can stay open, because in that reading it was never a boundary. Still prior to acoustic use is the pharyngeal geometry noted in [docs/articulatory-data.md](articulatory-data.md), which no instrument here measures.
- **Sources.** The contours here are described qualitatively. Turning them into numbers wants a specific published mid-sagittal reference, cited in the data, rather than composite recollection. One is now in hand for part of the geometry: [docs/articulatory-data.md](articulatory-data.md) measures the palate, the tongue-to-palate aperture, the mandibular hinge and the jaw-to-tongue carrier relation against the X-Ray Microbeam database, and `heads.xml` now carries the measured aperture over arc 0.20-0.40. It also says plainly what that instrument cannot see: no velum, no larynx, nothing behind arc 0.44, and nothing off the mid-sagittal plane.

## Related

- [docs/gestural-model.md](gestural-model.md) — segments as gesture sets; a gesture is what this geometry executes
- [docs/distance.md](distance.md) — the current model, whose anchors this specification would derive
- [docs/articulatory-data.md](articulatory-data.md) — measured articulatory data for the part of this geometry an instrument can see, and what it grounds
