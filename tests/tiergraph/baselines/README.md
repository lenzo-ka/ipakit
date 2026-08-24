# Lane A baseline captures

Regenerate the tiergraph captures and their manifest from the repository root with `PYTHONHASHSEED=0 python scripts/tiergraph_capture.py all`, then authenticate the result with `PYTHONHASHSEED=0 python scripts/tiergraph_capture.py verify`. Regenerate `containment-navigation.json` separately with `PYTHONHASHSEED=0 python scripts/containment_oracle.py generate`.

Small captures are committed in this directory.

Large captures are written under the intentionally untracked captures/ directory and authenticated by MANIFEST.sha256.

Regenerate the phone enumeration only through PYTHONHASHSEED=0 python scripts/sweep.py capture -o captures/sweep-current.json; tiergraph_capture.py sweep invokes that exact command and then captures to_ipa and Form.to_json/from_json round trips over every enumerated spelling.

Verify every present capture with PYTHONHASHSEED=0 python scripts/tiergraph_capture.py verify.

The fresh confusion matrix is regenerated with PYTHONHASHSEED=0 python scripts/confusion.py generate and is never measured through a cache-backed distance model.

Regenerate only the sweep sensitivity proof with `PYTHONHASHSEED=0 python scripts/tiergraph_capture.py perturb-proof`. The command records the clean capture, temporarily changes phone `p` from bilabial to labiodental, captures again, runs the documented failing diff, derives the proof from the captures, and restores `ipa.xml` byte-for-byte.
