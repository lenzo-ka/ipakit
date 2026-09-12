# Panphon feature declaration

`panphon.xml` is derived from Panphon 0.22.2's `ipa_all.csv` and
`feature_weights.csv`, distributed under the MIT license. Copyright (c) 2015
Carnegie Mellon University. The complete upstream permission and warranty notice
is preserved in `PANPHON-LICENSE.txt` alongside this artifact.

Project: https://github.com/dmort27/panphon
Distribution release: https://pypi.org/project/panphon/0.22.2/

The original development XML inferred a Git tag URL from the distribution
version. That tag does not exist; only this provenance URL is corrected to the
confirmed project home. Version and original CSV digest receipts are unchanged.

The XML root records the source version, license, both original CSV SHA-256
digests and the artifact names. `scripts/panphon_geometry.py` transcribes the
frozen table deterministically: token keys are normalized to NFD; ternary zero,
feature order and the separately ordered weight columns are preserved. The XML
also records directional mapping limitations. This is a finite source model,
not a claim of complete house correspondence or perceptual validation. No
Panphon Python implementation or runtime dependency is included.

The upstream distribution's README metadata credits the HsSPE data files and
Bruce Hayes's feature spreadsheet as inspirations, and states that subsequent
re-rationalization removed any special relationship to those earlier sources.
The inspected distribution has no separate data-specific license notice for
these CSVs. Its MIT license and original copyright notice are retained here.

Citation supplied by Panphon: David R. Mortensen, Patrick Littell, Akash
Bharadwaj, Kartik Goyal, Chris Dyer, and Lori Levin (2016), “PanPhon: A Resource
for Mapping IPA Segments to Articulatory Feature Vectors,” Proceedings of
COLING 2016, pages 3475–3484.
