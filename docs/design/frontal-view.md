# D1 frontal-view report

The frontal drawing is a second projection of the same `Posture` and
`Trajectory` as the mid-sagittal drawing. Shape lives on `Head`; the renderer
projects and strokes. It introduces no phone lookup, view-only posture, or
change to the metric.

## Parameter-set diff and consumption

The version-1 track parameter list grows in place from
`reading, rest, constrictions, velic, glottal, secondary, unmodelled` to that
same ordered list followed by `aperture_width, protrusion`. Both additions are
normalized scalars, declared on the `rounded` values in `ipa.xml`, serialized
on every frame, and blended with the same weighted-scalar rule as `velic`.

| Parameter | Sagittal consumption | Frontal consumption | Sufficiency verdict |
|---|---|---|---|
| reading, rest | primary pose and jaw carriage | jaw opening and bilabial seal | shared state |
| constrictions | tongue surface and closures | retained; tongue pose is read through the primary pose in D1 | no frontal side channel |
| velic | velum and nasal port | not visible through the face mask | intentionally projection-specific |
| glottal | vocal folds | occluded by the face | intentionally projection-specific |
| secondary | secondary sagittal constriction | retained but occluded in D1 | later skin-off read |
| unmodelled | honest annotation | retained, not drawn | diagnostic, not a pose coordinate |
| aperture_width | sagittal geometry unchanged | transverse mouth/lip/interior width | gap exposed by H1 and now modeled |
| protrusion | sagittal geometry unchanged | lip-body thickening/pucker contribution | gap exposed by H1 and now modeled |

No value is computed from a symbol in either projection. A projection may
legitimately not see a value (the face hides the glottis); the H1 failure would
be a value invented only inside that projection, and there is none.

## Animation-rig sufficiency checklist

Rig vocabulary is used here only to test span, not to parameterize the model.

| Checklist item | Verdict | Coordinate or honest gap |
|---|---|---|
| corner pull | expressible | increase `aperture_width` at fixed protrusion |
| pucker | expressible | reduce `aperture_width`, increase `protrusion` |
| funnel | gap | needs independent inner-aperture versus outer-lip eversion; a genuinely new lip-shape DOF for the H2 deformation basis, not an H1 renderer constant |
| upper-lip raise | gap | independent upper-lip vertical control; facial-expression/gesture phasing belongs H5+, after the basis supplies the DOF |

## Grounding

| Contour group | Source |
|---|---|
| face/mouth transverse scale | Mouth span 1.0291 times the interpupillary proxy measured from Z-Anatomy 5.2.0 (CC BY-SA 4.0), derived from BodyParts3D (CC BY-SA 2.1 Japan); measurement procedure and limits are in `ipakit-assets/proportions.md` |
| upper/lower dental arches | 0.4785/0.5156 of skeletal bizygomatic width from the same measured plates and provenance |
| adult vermilion | Farkas et al., “Anthropometric proportions in the upper lip-lower lip-chin area of the lower face in young white adults,” *American Journal of Orthodontics* 86 (1984), 52–60: male 8.0/9.3 mm at 54.5 mm mouth width; female 8.7/9.4 mm at 50.2 mm |
| child vermilion ratio | Farkas, *Anthropometry of the Head and Face*, 2nd ed. (1994), age 4–5 norms: upper/lower vermilion ratio 110.6% |
| nose | light, hand-placed mask following `talking-heads/nasal-design.md`; no unsupported internal nasal detail |
| tongue/chin mask | existing head tongue basis and explicitly hand-placed mask; no claim that Z-Anatomy supplies soft tissue |

The exact provenance is repeated beside each declaration in `heads.xml`.

## Occlusion and outputs

The renderer paints the static face behind the mouth, then mouth interiors by
descending declared `arc`: tongue (0.32), dental arches (0.08), and lips
(0.00). `Head.frontal_mouth` separates the declared lip parting line into an
upper and lower curve under posture aperture height and width, then reuses
those exact points to close both vermilion bodies and the aperture polygon.
The two curves retain the same corner objects, so the opening cannot become
narrower than the lips or expose face between either lip and its boundary.
The aperture clips the carried rigid teeth and tongue. At a bilabial
seal the aperture and every interior path are omitted, while their posture
coordinates remain intact. Mandibular teeth, tongue, lower lip, chin, and
lower-face mass share jaw carriage.

The reference still is `docs/figures/frontal-reference.svg`; the small phone
set is `frontal-{a,i,m,u}.svg`. The pinned measured-time player is
`docs/figures/two-pane-timed.html`; both panes are zipped from one frame list,
receive identical rest holds, and share one scrubber.

## Gates and visual verdict

- Pure-posture equality: every declared head × reference, m, a, i, u, t, k.
- Occlusion: a shut /m/ emits no aperture, tongue, or teeth; an open /a/
  emits all three. The optional `rsvg-convert` pixel checks cover the raster
  boundary when installed.
- Lip boundary: four geometry cases (closed /m/, mid /i/, open /a/, rounded
  /u/) pin exact shared edge and corner objects, and one /a/ raster case pins
  zero face-colored pixels inside the parting-line polygon: five new pin
  cases. The existing /m/ raster occlusion cases still pin zero leaks.
- Scoped CSS: every frontal paint class has the `f-` prefix and the two-pane
  page emits the frontal vocabulary once.
- References and timed player: regenerated bytes are pinned by tests.
- Metric: `scripts/sweep.py diff` reports 9,450 → 9,450 units, zero feature,
  description, and distance movers; `confusion.json` is byte-identical.
- Visual inspection after rasterization: the mouth reads as a mouth, with a
  continuous dark aperture, vermilion bodies, visible carried dentition and
tongue when open, and no interior leak when shut. The surrounding mask is
deliberately schematic; the mouth, not the static furniture, is the floor.

The face outline remains deliberately schematic. Rounding its visible temple
vertices would require new sourced contour samples rather than a free
interpolation of the six declared landmarks, so that proportion note remains
a follow-up rather than being mixed into the mouth-boundary fix.

`PYTHONHASHSEED=0 make check`: green — 4,389 passed (2,656 existing warning
instances), plus formatting, lint, typing and consolidation parity.
