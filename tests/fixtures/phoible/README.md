# PHOIBLE parser fixture

The rows in `data/phoible.csv` are excerpted and minimally reduced from
`phoible/dev`'s `data/phoible.csv` (PHOIBLE data, CC BY-SA 3.0; see
<https://github.com/phoible/dev>). The two English inventories intentionally
pin PHOIBLE's doculect-spread semantics; `k͈` pins a positioned parser
refusal.

The rows in `mappings/` are synthetic and authored by ipakit. They retain only
the inventory IDs and factual ISO 639-3 and Glottocode identifiers needed by
the tests. Their `spa` and `uz` source labels match the attributed data excerpt
so the fixture tables join on the same inventories; all other mapping values
are conspicuous fixture markers. PHOIBLE's real mapping tables are not shipped.
They must come from a user-supplied PHOIBLE checkout selected with
`IPAKIT_PHOIBLE`.
