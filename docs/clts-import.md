# Importing explicit CLTS tokens

IPAkit imports only the reviewed plain-stop CLTS spellings `p`, `b`, `t`, and
`d` into a complete house Form. The default answer for every unsupported or
unresolved occurrence is a refusal with a per-occurrence report. Preserve mode
retains the complete native source graph and reports the missing house
projection instead.

Input is explicitly segmented. `import_tokens` accepts a list or tuple of raw
spellings; it does not split a string. `import_document` accepts the version 1
input object when timing or source-tone host relations are needed.

```python
from ipakit.clts import import_tokens

result = import_tokens(["p", "b", "t", "d"])
assert result.status == "complete"
assert result.source_tokens() == ("p", "b", "t", "d")
assert result.house_form().to_ipa() == "pbtd"
```

The default `unsupported="error"` policy returns status `refused`, a null
`form`, and diagnostics. It does not return a partial house Form.

```python
from ipakit.clts import CLTSInputError, import_tokens

result = import_tokens(["p", "a"])
assert result.status == "refused"
assert result.graph is None
assert result.report()["diagnostics"][0]["token"] == 1
try:
    result.house_form()
except CLTSInputError as error:
    assert error.code == "house-incomplete"
else:
    raise AssertionError("a refused import produced a house Form")
```

Set `unsupported="preserve"` to keep the native graph when an occurrence has
no reviewed house projection. A preserved result is source-complete and
house-incomplete. Its `house_form()` method refuses rather than dropping the
uncovered occurrences.

The default `projection="explicit-only"` uses only reviewed mapping facts.
`projection="house-convention-v1"` is an explicit opt-in to the existing
foreign-IPA spelling recipe: normalize declared keyboard lookalikes, add the
house tie sense to a source spelling that CLTS treats as one sound, and require
one strict house segment. Each occurrence that needs this assumption is listed
in `report()["changes"]` with its source spelling, house spelling, and convention.
The source claims remain independent in the native graph; a convention change
is never reported as source evidence. A warning or a spelling that does not
strictly produce one house segment remains unsupported.

```python
conventional = import_tokens(["ts"], projection="house-convention-v1")
assert conventional.house_form().to_ipa() == "t͡s"
assert conventional.report()["changes"][0]["convention"] == "house-convention-v1"
```

## Source and canonical emission

`emit_tokens` accepts either an import result or a restored source-profile
`Form`. `spelling="source"` recovers the exact submitted occurrence sequence,
independently of house coverage or convention projection. `spelling="bipa"`
uses the stored or shipped canonical BIPA spelling. If that spelling erases a
source distinction such as a tie sense, the operation refuses until
`allow_loss=True`; the report names every affected occurrence and claim.

```python
from ipakit.clts import emit_tokens

held = import_tokens(["t͜s"], unsupported="preserve")
assert emit_tokens(held, spelling="source").tokens == ("t͜s",)
refused = emit_tokens(held, spelling="bipa")
assert refused.to_data()["error"]["code"] == "loss-not-authorized"
canonical = emit_tokens(held, spelling="bipa", allow_loss=True)
assert canonical.tokens == ("ts",)
assert canonical.report()["losses"][0]["claim"] == "sequential-juncture"
```

## Saved envelopes

`CLTSImport.to_json()` writes a canonical envelope with `form` and `report`.
The `form` value is a native, source-profile TierGraph document. It is not a
house-only Form document. `Form.from_json` and `read_json` admit a verified
document as a source-profile Form: its native JSON and source identity remain
authoritative, while house-only views refuse if any source occurrence is
uncovered. Use `house_form()` only on a result whose status is `complete` when
an ordinary Form without source history is specifically wanted.

```python
import json

from ipakit import Form
from ipakit.clts import import_tokens

result = import_tokens(["p"])
form = Form.from_json(json.dumps(result.to_data()["form"]))
assert form.to_ipa() == "p"
assert Form.from_json(form.to_json()) == form
```

On a preserved import, full-graph JSON and DOT remain available because they
retain the source/profile facts. House rendering, conversion, measurement,
rewriting, syllabification, and gesture paths refuse and name every uncovered
occurrence. Form-to-Form operations that rebuild from house units refuse every
source-profile Form, including a fully covered one, unless the operation can
preserve its authoritative source facts and relationships.

The compact envelope has a fixed graph cost: measured from the shipped
library, empty, one-token, and fifty-token `p` imports are 20,545, 23,142, and
149,602 bytes. That is about 20.5 KB empty plus about 2.6 KB per token. The
layout favors a complete inspectable native graph over a compact transport.

The shipped [JSON Schema](../ipakit/data/clts/import-result.schema.json)
describes complete, empty, refused, preserved, and error envelopes. A result
report carries schema id `ipakit-clts-import-result` and version 1. An error
from `CLTSInputError.to_data()` instead contains only `error` and a null `form`;
it is for logging and `load_import` refuses it.

## Reloading and crossing builds

`load_import` is a same-provenance reader. It checks the report's fingerprints,
reconstructs the input document, repeats the import with the implied strict or
preserve policy, and requires the canonical envelope to match. A refused
envelope has no graph, so its reload verifies the report's internal consistency
by repeating the refusal.

Across builds, retain the source document and import it again under the chosen
policy instead of passing an older envelope to `load_import`:

```python
from ipakit.clts import import_document, import_tokens

saved = import_tokens(["p", "a"], unsupported="preserve")
fresh = import_document(saved.source_document(), unsupported="preserve")
assert fresh.source_document() == saved.source_document()
```

Editing that document and importing it again creates a new source revision and
recomputes resolution, projection, and canonical spellings. Source-profile
Forms refuse generic `dataclasses.replace` and Form-to-Form rebuilding so an
edit cannot retain stale source facts or cached derivations.

Provenance equality establishes that the same shipped snapshot, mapping, and
profile produced the saved result. It does not widen the reviewed import
domain or assert phonetic equivalence outside it.
