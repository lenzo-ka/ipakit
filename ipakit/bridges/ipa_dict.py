"""Thin, language-scoped reader for open-dict-data/ipa-dict wordlists.

ipa-dict is a community-compiled collection of broadly phonemic wordlists.
Conventions and quality vary between languages (and sometimes within one
file), so this door makes no cross-language or narrow-phonetic claim.  It
reads every pronunciation through ipakit's explicit wild-input path and
reports, rather than drops, lines which that path cannot read completely.

The upstream data stays in its own checkout.  Point :class:`IPADictReader` at
one language file, or use :meth:`IPADictReader.from_environment` with
``IPAKIT_IPA_DICT`` naming either a checkout or a language file.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..features import IPAFeatures
from ..form import Form

DEFAULT_ENV_VAR = "IPAKIT_IPA_DICT"


@dataclass(frozen=True)
class IPADictProvenance:
    """Identity of one language file and, when visible, its checkout commit."""

    language: str
    file: str
    version: str


@dataclass(frozen=True)
class IPADictPronunciation:
    """One source spelling and its strict house reading."""

    written: str
    form: Form


@dataclass(frozen=True)
class IPADictEntry:
    """One wordlist line, retaining all comma-separated variants for echo."""

    word: str
    pronunciations: tuple[IPADictPronunciation, ...]
    line_number: int
    separator: str = "\t"


@dataclass(frozen=True)
class IPADictRefusal:
    """One source line which could not be read completely."""

    line_number: int
    line: str
    word: str | None
    reason: str


@dataclass(frozen=True)
class IPADictReadReport:
    """All complete entries and every refused source line."""

    provenance: IPADictProvenance
    entries: tuple[IPADictEntry, ...]
    refusals: tuple[IPADictRefusal, ...]

    @property
    def accepted(self) -> bool:
        """Whether every content line was accepted."""

        return not self.refusals


class IPADictReader:
    """Read one ipa-dict language file without broadening its provenance."""

    def __init__(
        self,
        language_file: str | os.PathLike[str],
        *,
        language: str | None = None,
        features: IPAFeatures | None = None,
    ) -> None:
        self.path = Path(language_file)
        self.language = language or self.path.stem
        if not self.language:
            raise ValueError("ipa-dict language code must not be empty")
        self.features = features or IPAFeatures()

    @classmethod
    def from_environment(
        cls,
        language: str,
        *,
        env_var: str = DEFAULT_ENV_VAR,
        environ: Mapping[str, str] | None = None,
        features: IPAFeatures | None = None,
    ) -> IPADictReader | None:
        """Resolve a language file, returning ``None`` when data is unconfigured.

        The environment value may name the file itself or an ipa-dict checkout;
        both the current ``data/<language>.txt`` and legacy root layout are
        recognized.  A configured but missing language remains a loud error at
        :meth:`read`, rather than looking like an absent configuration.
        """

        environment = os.environ if environ is None else environ
        value = environment.get(env_var)
        if not value:
            return None
        configured = Path(value).expanduser()
        if configured.is_file():
            return cls(configured, language=language, features=features)
        candidates = (
            configured / "data" / f"{language}.txt",
            configured / f"{language}.txt",
        )
        path = next(
            (candidate for candidate in candidates if candidate.is_file()),
            candidates[0],
        )
        return cls(path, language=language, features=features)

    def read(self) -> IPADictReadReport:
        """Read the file, accepting only lines whose every variant parses."""

        if not self.path.is_file():
            raise ValueError(f"ipa-dict language file {self.path} is not a file")
        entries: list[IPADictEntry] = []
        refusals: list[IPADictRefusal] = []
        try:
            stream = self.path.open(encoding="utf-8-sig")
        except OSError as exc:
            raise ValueError(
                f"cannot open ipa-dict language file {self.path}: {exc}"
            ) from exc
        try:
            with stream:
                for line_number, raw in enumerate(stream, 1):
                    line = raw.rstrip("\r\n")
                    if not line or line.startswith("#"):
                        continue
                    word: str | None = None
                    try:
                        entry = self.read_line(line, line_number=line_number)
                        word = entry.word
                    except (UnicodeError, ValueError) as exc:
                        if "\t" in line:
                            word = line.split("\t", 1)[0] or None
                        refusals.append(
                            IPADictRefusal(line_number, line, word, str(exc))
                        )
                    else:
                        entries.append(entry)
        except (OSError, UnicodeError) as exc:
            raise ValueError(
                f"cannot read ipa-dict language file {self.path}: {exc}"
            ) from exc
        return IPADictReadReport(self.provenance, tuple(entries), tuple(refusals))

    def read_line(self, line: str, *, line_number: int = 1) -> IPADictEntry:
        """Read one ``word<TAB>/pron/, /variant/`` source line."""

        if "\t" not in line:
            raise ValueError("expected word<TAB>/pronunciation/")
        word, field = line.split("\t", 1)
        if not word:
            raise ValueError("expected a non-empty word before the tab")
        written = _variants(field)
        pronunciations: list[IPADictPronunciation] = []
        for variant_number, source in enumerate(written, 1):
            if not source.strip():
                raise ValueError(f"variant {variant_number} is empty")
            try:
                form = self.features.read(source, strict=True, wild=True)
            except ValueError as exc:
                raise ValueError(
                    f"variant {variant_number} {source!r} is not readable IPA: {exc}"
                ) from exc
            if not form.units:
                raise ValueError(f"variant {variant_number} is empty")
            pronunciations.append(IPADictPronunciation(source, form))
        return IPADictEntry(word, tuple(pronunciations), line_number)

    def emit_line(self, entry: IPADictEntry) -> str:
        """Echo an accepted entry in ipa-dict's slash-delimited syntax."""

        variants = ", ".join(f"/{pron.written}/" for pron in entry.pronunciations)
        return entry.word + entry.separator + variants

    @property
    def provenance(self) -> IPADictProvenance:
        """Describe only this language file, using a commit when derivable."""

        commit = _checkout_commit(self.path)
        identity = str(self.path.resolve())
        return IPADictProvenance(self.language, identity, commit or identity)


def _variants(field: str) -> tuple[str, ...]:
    parts = field.split(",")
    variants: list[str] = []
    for part in parts:
        token = part.strip()
        if len(token) < 2 or not token.startswith("/") or not token.endswith("/"):
            raise ValueError(f"expected slash-delimited pronunciation, got {token!r}")
        variants.append(token[1:-1])
    if not variants:
        raise ValueError("expected one or more pronunciations")
    return tuple(variants)


def _checkout_commit(source: Path) -> str | None:
    for directory in (source.resolve().parent, *source.resolve().parents):
        marker = directory / ".git"
        if not marker.exists():
            continue
        git_dir = marker
        if marker.is_file():
            try:
                declaration = marker.read_text(encoding="utf-8").strip()
            except OSError:
                return None
            if not declaration.startswith("gitdir: "):
                return None
            git_dir = (directory / declaration[8:]).resolve()
        try:
            head = (git_dir / "HEAD").read_text(encoding="ascii").strip()
        except OSError:
            return None
        if not head.startswith("ref: "):
            return head or None
        ref = head[5:]
        try:
            return (git_dir / ref).read_text(encoding="ascii").strip() or None
        except OSError:
            try:
                packed = (git_dir / "packed-refs").read_text(encoding="ascii")
            except OSError:
                return None
            for row in packed.splitlines():
                if row and not row.startswith(("#", "^")):
                    commit, name = row.split(" ", 1)
                    if name == ref:
                        return commit
            return None
    return None
