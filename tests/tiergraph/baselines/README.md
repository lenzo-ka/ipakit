# Lane A baseline captures

Run every capture from the repository root with PYTHONHASHSEED=0 python scripts/tiergraph_capture.py all.

Small captures are committed in this directory.

Large captures are written under the intentionally untracked captures/ directory and authenticated by MANIFEST.sha256.

Regenerate the phone enumeration only through PYTHONHASHSEED=0 python scripts/sweep.py capture -o captures/sweep-current.json; tiergraph_capture.py sweep invokes that exact command and then captures to_ipa and Form.to_json/from_json round trips over every enumerated spelling.

Verify every present capture with PYTHONHASHSEED=0 python scripts/tiergraph_capture.py verify.

The fresh confusion matrix is regenerated with PYTHONHASHSEED=0 python scripts/confusion.py generate and is never measured through a cache-backed distance model.

For a sweep sensitivity proof, capture a clean baseline, temporarily perturb one declared IPA feature value, capture again, run PYTHONHASHSEED=0 python scripts/sweep.py diff captures/sweep-before-perturbation.json captures/sweep-after-perturbation.json --require-monotone, read the mover count from its output rather than its exit status, and revert the perturbation.
