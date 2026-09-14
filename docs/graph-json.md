# Native graph JSON

Form persists its complete native TierGraph: typed event facts, ordered
relationships, clock coordinates, optional start + duration timing, and explicit
profile and restoring inventory bindings.

```python
import ipakit
import tiergraph

form = ipakit.read("kæt")
document = form.to_json()
restored = ipakit.read_json(document)
assert isinstance(restored, ipakit.Form)
assert restored.to_ipa() == "kæt"
assert restored.to_json() == document
assert tiergraph.to_data(restored.graph) == tiergraph.to_data(form.graph)
```

JSON is compact by default. `to_json(pretty=True)` changes indentation through
the same native codec. `to_dict()` exposes native JSON data. There is one current
Form format; older linear documents are refused. Regenerate stored Forms with
the current constructors.

## Graph reading and Form admission

`form.graph` is the authoritative `tiergraph.Graph`. `read_graph_json(document)`
returns a structurally validated native Graph, including other profiles;
`write_graph_json(graph, pretty=False)` writes the same native format.

`Form.from_json(document, features=inventory)` additionally validates the current
Form constructor profile and reconstructs its views from graph facts. The
inventory must match the persisted loaded declaration identity. Custom inventory
and supplement bindings require that matching inventory, including for empty
Forms. This operation does not convert phonesets. Layouts outside the understood
Form profile are refused and remain readable through the native Graph reader.

The profile retains source spelling, construction identities, typed Segment
values, custom JSON, phantom events and source relation order. Unknown opaque
objects and conflicting profile/projection facts refuse admission. Null, false,
integer, float and absent facts remain distinct. Linguistic assertions and
external provider/alignment truth remain supplied caller claims.

## Commands

```bash
ipakit convert to-json "kæt" -o form.json
ipakit convert to-json "kæt" --pretty
ipakit convert to-json "kæt" | ipakit convert from-json -
ipakit graph-json --from-file form.json --validate
ipakit graph-json --from-file form.json --pretty
ipakit tiergraph --from-json form.json -o form.dot
```

`graph-json` accepts literal native JSON, `-` for stdin, or `--from-file PATH`.
It validates and writes canonical compact JSON; `--validate` succeeds silently.
`convert from-json` additionally validates Form admission and emits IPA.

## Graph presentation

Profile metadata and recursive values have independent structural axes.
Full-graph DOT uses the native generic renderer to retain these concerns and
their links, with no artificial phonetic span or audio timing. Combined score
and auxiliary lanes remain a separate renderer enhancement.
