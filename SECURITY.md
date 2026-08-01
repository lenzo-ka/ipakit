# Security policy

## Supported versions

The latest released version is the one that receives fixes. ipakit supports Python 3.11, 3.12 and 3.13, and has **zero runtime dependencies** — all phonetic data ships as XML inside the package — so it carries no third-party supply chain of its own at run time.

## Reporting a vulnerability

Please report privately, not in a public issue.

Use GitHub's **Report a vulnerability** button under the repository's *Security* tab, which opens a private advisory visible only to the maintainer. If that is unavailable to you, open a normal issue saying only that you have a security report and asking for a private channel — **without** the details.

Please include what you would put in any defect report: the exact input, the call or command, what happened, and what you expected. A reproducer is worth more than a description.

You can expect an acknowledgement within a week. There is no bounty.

## What is in scope

ipakit is a library that parses text and computes over declared data. The realiztic risk is a caller feeding it input it does not control. In scope:

- **Untrusted transcription text** that makes ipakit hang, consume unbounded memory, or crash the interpreter — catastrophic backtracking in tokenization, unbounded recursion in composition or in the rewrite engine, and the like. Callers legitimately run `distance`, `tokenize` and `validate_ipa` over out-of-vocabulary text; that is a supported use, so a denial of service there is a real bug.
- **Anything that escapes the process.** ipakit reads data files and writes nothing outside what a caller asks for; a path that executes code, writes outside its target, or opens a network connection is a vulnerability regardless of how it is reached.
- **The release pipeline** — `.github/workflows/publish.yml`, which publishes to PyPI via Trusted Publishing (OIDC) with no long-lived tokens, and the derived-artifact generators in `scripts/`.

## What is not in scope

- **A wrong phonetic answer is not a vulnerability.** A distance you disagree with, a derivation that is wrong for your variety, a feature bundle that misdescribes a sound — these are the project's central concern and its most valued kind of report, but they are ordinary issues. See [CONTRIBUTING.md](CONTRIBUTING.md); challenges are explicitly welcome.
- **Untrusted data files are not a trust boundary.** `load_ipa_features(xml_path=...)` and the phoneset and rule-file loaders accept a caller-supplied path, and the XML is read with the standard library's `xml.etree.ElementTree`, which expands internal entities. A hostile XML file can therefore exhaust memory by entity expansion, and a hostile rule file states rules that will be applied. **A data file is configuration, not input: load only ones you trust.** If you have a use case that genuinely requires parsing untrusted XML here, open an issue — that is a feature request for a hardened loader, and a reasonable one, rather than a report against the current design.
- Findings from an automated scanner with no demonstrated impact on this library.
