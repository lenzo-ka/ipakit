# The tract, drawn

The figures below are redrawn from the declared geometry by `make figures`. They are checked in so a reader gets them without running anything, and so a change to the geometry shows up in a diff as a changed picture rather than as four characters in an XML attribute.

Everything below comes from `ipakit.tract.Head.project` — the same call any renderer would make. The drawing computes no geometry of its own, which is why it is useful as a check: when the projection was wrong, the picture was wrong in a way the numbers were not.

## Drawing one yourself

The renderer is `ipakit.tract_svg` and ships with the package, so `pip install ipakit` is enough to draw. `ipakit.tract` is the model and `ipakit.tract_svg` is the picture; they are two modules because `ipakit.metric` reads the model, and nothing that computes a distance should be able to reach a stylesheet.

Each call returns a whole SVG document as a string — write it to a file, embed it, or hand it to a notebook. The examples below take the first five characters so the page can quote what came back.

```python
import ipakit
from ipakit.tract import head
from ipakit.tract_svg import figure

figure("t")[:5]                      # '<svg '   one phone
figure("tʰ")[:5]                     # '<svg '   a marked unit draws too
figure(None)[:5]                     # '<svg '   the reference drawing, at rest
figure("i", "child")[:5]             # '<svg '   on another declared head
```

In a notebook the object draws itself: evaluate a `Segment` or a `Head` in a cell and the figure appears, because each carries the `_repr_svg_` hook Jupyter looks for.

```python
ipakit.segment("ʃ")._repr_svg_()[:5]     # '<svg '
head("child")._repr_svg_()[:5]           # '<svg '
```

A form is a sequence of segments and has no figure of its own, so iterate and let each segment draw — `display(seg)` for every cell but the last.

```python
[seg.to_ipa() for seg in ipakit.segments("kæt")]   # ['k', 'æ', 't']
```

From a shell:

```bash
ipakit tract draw t -o t.svg             # the bytes `make figures` writes
ipakit tract draw -o reference.svg       # every landmark, at rest
ipakit tract draw --page -o tract.html   # the reference, with aperture and provenance
ipakit tract heads                       # what a figure can be drawn on
```

All of these are one derivation. `tract_svg.drawing()` resolves the posture and `tract_svg.render()` assembles the document; `figure()`, the `_repr_svg_` hooks, the command line, `make figures` and the property tests all pass through both, and `tests/test_tract_figures.py` asserts that every one of them writes the same bytes as `docs/figures/tract-t.svg`. The command and the tests once derived the posture separately, which is two chances to disagree about what the picture is.

### One posture, one figure

`Segment` and `Head` draw themselves. `Form` and `Derivation` deliberately do not, and that is the same rule stated twice: a figure is one posture, a form is a sequence of them and a derivation is a sequence of forms. Either would have to pick one posture — a well-formed picture of something the object is not, which is this repository's characteristic defect — or lay out a strip, which is a different thing that deserves its own document rather than a display hook smuggled in beside this one. A form is iterable, so `for seg in form.segments` gives objects that each draw honestly.

That is also where a filmstrip attaches when one is built: `figure()` is one frame, `page()` is the document that surrounds a frame, and a strip is a composer beside `page()` taking a sequence of `drawing()` results. Nothing above needs to change to add it. One thing a strip has to know: `figure()` inlines a resolved stylesheet with unscoped selectors (`.wall`, `.lip`, …), which is safe today because every figure carries the *same* stylesheet, and stops being safe the moment two figures on one page carry different ones.

## Which head

The figures draw the adult male head. That is a presentation choice, not a claim about the geometry: the properties a drawing has to satisfy — labels that do not collide, a tongue that stays inside the tract, an articulator that reaches its target, a shut mouth that leaks only at the glottis — are checked on **every declared head**, in `tests/test_tract_figures.py`. Drawing all three here would add pictures without adding a check.

What *is* adult-only is the measurement. The X-Ray Microbeam corpus is 48 American English adults, median age 21, so the aperture over arc 0.20-0.40 and the jaw carriage are theirs. The female head takes the same normalized shape against its own tract length, on the evidence in [articulatory-data.md](articulatory-data.md); the child head is hand-placed throughout, because a child's tract is not a scaled adult's and this corpus has nothing to say about one.

## The reference

![The tract at rest, every landmark named](figures/tract-reference.svg)

Every landmark the head declares, at the rest posture. Figures for individual phones name only the landmarks that phone uses, so this one is the key to those. [tract-reference.md](tract-reference.md) has the declared positions and where each number came from.

## How to read it

The head faces **left**: the lips are on the left, the glottis on the right. That matches the orientation of the IPA vowel chart, where front vowels sit left and back vowels right, so a tract figure and a vowel chart can be read side by side without mirroring either.

The **wall** is fixed: palate, teeth, pharyngeal wall. The **articulator** sweeps between fully open, at the midline, and closed against that wall. The shaded band is that sweep and the dashed line inside it is the rest position. A constriction is therefore a place along the tract and a degree of closure — exactly what `arc` and `offset` hold.

The tongue is one body, so a constriction deforms its whole surface rather than marking a point: moving it carries the tip, blade and dorsum along, with a raised-cosine falloff over the span the tongue bounds.

The **velic port** opens when a segment states nasality, read from the `nasality` bridge in `ipa.xml` — the same declaration the metric uses, so the geometry and the distance cannot disagree about what counts as nasal. A lowered velum leaves a gap in the oral roof, because the velum is part of that boundary.

The **vocal folds** are the pair of wedges at the glottis, and the gap between them is the segment's glottal state. Places drawn in amber host a fricative or affricate somewhere in the inventory.

## What the posture cannot say, and what the drawing does about it

The posture is two numbers, `arc` and `offset`, against the nine the [anatomy](tract-anatomy.md) specifies. Most of what a segment states is therefore not in it: from those two numbers alone `t` and `d` are one drawing, `l` and `ɫ` are one drawing, and so are `s` and `ɬ`. The five shipped rule sets make this pointed, because what they emit is exactly what the posture cannot draw — `l̥ ɹ̥ w̥`, `ɫ`, `tʰ t̚ tⁿ tˡ`, `n̩ l̩`.

The answer is an annotation layer rather than a posture that pretends. Voicing is glottal state, not sagittal shape; a release is a phase of the segment, not a form of it; laterality is an axis this plane projects away. Bending `arc` and `offset` to carry any of them would make the geometry mean something other than what it says. Three things now happen instead, and **which of the three is decided by the feature's own declaration in `ipa.xml`, never by a list in the renderer**:

**Drawn as geometry, because the declaration puts it somewhere.**

- **Glottal state.** The folds are declared `aperture="median"` — they close toward each other about the tract axis, not toward a wall — so `offset`, which measures travel from the midline to a wall, was never going to reach them. `phonation` is ordinal on its own axis, `+glottal-aperture`, ascending creaky → modal → breathy → devoiced, and the `<projection>` says `voiced` is that same axis read two ways instead of four. The gap between the folds is a position on that axis: a bundle spelling a phonation sits where that value sits, and one spelling only `voiced` sits at the center of the phonations reading that way, which is as far as the coarse spelling commits. A complete closure *at* the folds overrides both, which is what makes `ʔ` shut. So `t`/`d`, `h`/`ɦ` and `a`/`a̤` are now three different pictures.
- **Secondary articulation.** `velarized` declares `place="velar"`, `palatalized` declares `place="palatal"`, and `IPAFeatures.secondary_places` is that declaration read back — the same one the mode partition and the metric's place table read. A secondary articulation therefore has a place like any other constriction, and it is drawn as one: a dashed ring at that place, at approximant degree, because a secondary constriction that reached the primary's degree would *be* the primary. It is a lesser constriction, so it is drawn lighter. `l` and `ɫ` now differ at the velum, which is where the difference is.

**Annotated, in the strip along the foot of the figure, because the plane cannot hold it.** Each chip's shape says why, and the reason is read off the declaration:

| chip | why | features today |
|---|---|---|
| dashed circle | `axis="+z"` — the axis a mid-sagittal section projects away, which the feature's own `desc` says | `channel`: lateral, sibilant |
| chevron | `mode="release"` — a phase of the segment rather than a posture of it | `release`: aspirated, unreleased, lateral-released |
| square | not in the model at all | `airstream`, `retroflex`, `rounded`, `syllabic`, `tongue-root`, … |

**Left to the caption**, because neither of the above is honest:

- **Airstream direction.** An arrow would make ejective and implosive legible at a glance, and it is the natural schematic — but `ipa.xml` declares `pulmonic ejective implosive velaric` with no direction on any of them. Drawing an arrow means a table in the renderer saying which way each one points, which is the thing this repo removed three times. So a non-pulmonic airstream gets a chip naming itself, and the arrow waits on a declared attribute — an `airstream` value carrying its direction, the way a `place` value carries its `arc`. The one part of the mechanism that *is* declared is already drawn: a click's velar closure comes from `constrictions`, because `airstream="velaric"` is enough to derive it.
- **Grooving and laterality in the channel itself.** The chip says the contrast exists and names it; the shape of the channel is not in this plane and no mark here invents one. A coronal inset would be the faithful answer — see [tract-anatomy.md](tract-anatomy.md) §11.
- **Length, stress and tone.** These belong to the *unit* and never enter a feature bundle at all ([ties.md](ties.md)), so `aː` and `a` state the same features and draw the same picture. That is a fact about where prosody lives, not about the drawing.

With the layer in place, **the drawing separates exactly what the feature bundle separates** — over the registered inventory and over the units the shipped rule sets emit alike. What still shares a picture is named rather than rounded off: a group that shares a picture is a group that states the same features, which is a diphthong against its own first element — a diphthong is a movement between two postures and a figure draws one — or a length or stress contrast, which belongs to the unit and never enters the bundle at all.

`tests/test_tract_figures.py` asserts that in both directions: no two units stating different features share a drawing, and every group that does share one states one bundle. The counts live in those assertions, where they are derived from the inventory and the rule-set corpora each run, rather than in this paragraph, where a corpus that grows would leave them behind.

## Closure, and where it is made

![m](figures/tract-m.svg)
![n](figures/tract-n.svg)
![k](figures/tract-k.svg)
![eng](figures/tract-eng.svg)
![t](figures/tract-t.svg)

`m`, `n` and `k` are all complete closures — `offset` 1.0 — and they differ only in where. The lips meet for `m`, the tongue tip reaches the alveolar ridge for `n`, the dorsum meets the velum for `k`. Note what the velum is doing: open for the two nasals, sealed for `k`. A lowered velum opens the nose; it never closes the mouth, which is why `m` needs its lips shut as well.

`b` and `m` would differ in these figures only in the velic port. That is the whole contrast.

## Degree, and the sibilants

![theta](figures/tract-theta.svg)
![s](figures/tract-s.svg)
![esh](figures/tract-esh.svg)

`θ`, `s` and `ʃ` share a degree of closure and differ in place, the constriction walking back from arc 0.08 through 0.13 to 0.19. That is the front-cavity length difference that separates them acoustically.

What these figures cannot show is the other half of the contrast: `ʃ` and `s` also differ in `channel`, which is the `+z` axis. A mid-sagittal section projects that axis away — the feature's own declaration in `ipa.xml` says so — and no drawing in this plane will ever show grooving or laterality. Both figures carry a dashed-circle chip reading *sibilant*, which says the contrast is there and out of plane; the caption carries which value it takes.

## Vowels

![a](figures/tract-a.svg)
![i](figures/tract-i.svg)
![u](figures/tract-u.svg)

Vowels state backness and height rather than place, so no place is named. The tongue body moves and its whole surface goes with it.

## Silence

![silence](figures/tract-silence.svg)

`␣` is featurally null and has no articulatory position, so it is drawn at the posture the head declares for not speaking: lips together, tongue at rest, jaw closed.

## What the figures are not

They are a projection of a model, not a measurement. Only the aperture over arc 0.20–0.40 is measured, from the X-Ray Microbeam database; the nasal branch, the teeth, the tongue's falloff and the whole child head are hand-placed, and each point in `heads.xml` says which it is. See [articulatory-data.md](articulatory-data.md) for what that corpus can and cannot ground, and [tract-anatomy.md](tract-anatomy.md) for the specification these figures are an incomplete implementation of.

Two limits worth knowing before reading anything into them. The posture still carries only place and degree, so any two phones agreeing on those two resolve to one posture, and everything that separates them in the figure is either the glottis, a secondary constriction, or an annotation that is deliberately not drawn as anatomy. And the geometry is not simulable as it stands — see §11 of the anatomy document.
