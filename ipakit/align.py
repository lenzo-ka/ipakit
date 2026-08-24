"""PocketSphinx forced alignment into timed IPA forms.

``pocketsphinx`` is optional and is imported only when :func:`align` runs.
The conversion half is deliberately dependency-free so recorded decoder
results can guard the model-to-IPA boundary in the core test suite.
"""

from __future__ import annotations

import wave
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _corpus
from ._cmu_graph import BASE_CMUDICT, POCKETSPHINX, CMUDialect
from ._cmu_graph import read as read_cmu
from ._fact_builder import PositionHandle
from .features import IPAFeatures
from .form import Form, FormBuilder
from .mapper import CMUMapper


@dataclass(frozen=True)
class AlignmentFailure:
    """One corpus entry that refused alignment."""

    fileid: str
    message: str


@dataclass(frozen=True)
class AlignmentReport:
    """Batch result: successful IDs and every per-entry refusal."""

    aligned: tuple[str, ...]
    errors: tuple[AlignmentFailure, ...]


def _require_pocketsphinx() -> Any:
    try:
        from pocketsphinx import Decoder
    except ImportError as exc:
        raise ImportError(
            "PocketSphinx alignment requires the optional dependency; "
            "install it with `pip install ipakit[align]`"
        ) from exc
    return Decoder


def _phone_token(phone: str, profile: CMUDialect) -> str:
    """Normalize an acoustic-model phone through CMU declarations."""
    token = phone.upper()
    digit = token[-1:] if token[-1:].isdigit() else ""
    # The ASR profile declares the model's unstressed symbols.  A model that
    # supplies lexical stress is validated through the stress-preserving base
    # profile; both routes read the one cmu.xml inventory.
    read_cmu((token,), BASE_CMUDICT if digit else profile)
    return token


def _form_from_alignment(
    words: Sequence[Mapping[str, Any]],
    *,
    frame_rate: float,
    features: IPAFeatures | None = None,
    profile: CMUDialect = POCKETSPHINX,
) -> Form:
    """Convert recorded word/phone frame spans to a timed IPA form."""
    if frame_rate <= 0:
        raise ValueError(f"invalid decoder frame rate: {frame_rate!r}")
    builder = FormBuilder(features)
    mapper = CMUMapper()
    previous_end = 0
    word_index = 0
    lexical_words = []
    for raw_word in words:
        phones = raw_word.get("phones")
        if isinstance(phones, Sequence) and not isinstance(phones, (str, bytes)):
            normalized = [_phone_token(str(item["phone"]), profile) for item in phones]
            bases = {token.rstrip("0123456789") for token in normalized}
            if bases and bases <= profile.silence:
                continue
        lexical_words.append(raw_word)

    for raw_word in lexical_words:
        label = str(raw_word["word"])
        start = int(raw_word["start"])
        duration = int(raw_word["duration"])
        if start < previous_end:
            raise ValueError(f"alignment word {label!r} overlaps its predecessor")
        if duration < 0:
            raise ValueError(f"alignment word {label!r} has negative duration")
        phones = raw_word.get("phones")
        if not isinstance(phones, Sequence) or isinstance(phones, (str, bytes)):
            raise ValueError(f"alignment word {label!r} has no phone sequence")

        normalized = [_phone_token(str(item["phone"]), profile) for item in phones]
        bases = {token.rstrip("0123456789") for token in normalized}
        if bases and bases <= profile.silence:
            previous_end = start + duration
            continue
        if not normalized:
            raise ValueError(f"alignment word {label!r} has no phones")

        # Wordhood is both a lexical interval and the same untimed boundary
        # unit a house transcription writes. It makes no acoustic-span claim.
        if word_index:
            builder.append_ipa("#", strict=True)

        word = builder.begin(
            "word",
            {"spelling": label, "compatibility-interval": word_index},
            start=(PositionHandle(builder.current_tick, 1) if word_index else None),
        )
        children = []
        phone_end = start
        for raw_phone, token in zip(phones, normalized, strict=True):
            phone_start = int(raw_phone["start"])
            phone_duration = int(raw_phone["duration"])
            if phone_start < phone_end:
                raise ValueError(f"alignment phone {token!r} overlaps its predecessor")
            if phone_duration < 0:
                raise ValueError(f"alignment phone {token!r} has negative duration")
            ipa = mapper.cmu_to_ipa([token], include_extras=False, strict=True)
            (handle,) = builder.append_ipa(ipa, strict=True)
            builder.attach_timing(
                handle, phone_start / frame_rate, phone_duration / frame_rate
            )
            children.append(handle)
            phone_end = phone_start + phone_duration
        if word_index + 1 < len(lexical_words):
            builder.end(word, PositionHandle(builder.current_tick, 0))
        else:
            builder.end(word)
        builder.contain(word, children)
        builder.attach_timing(word, start / frame_rate, duration / frame_rate)
        word_index += 1
        previous_end = start + duration
    return builder.build()


def align(
    wav_path: str | Path,
    text: str,
    *,
    features: IPAFeatures | None = None,
    profile: CMUDialect = POCKETSPHINX,
) -> Form:
    """Force-align a PCM WAV transcript and return a timed IPA form."""
    Decoder = _require_pocketsphinx()
    path = Path(wav_path)
    decoder = Decoder()
    with wave.open(str(path), "rb") as source:
        sample_rate = int(decoder.config["samprate"])
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != sample_rate
            or source.getcomptype() != "NONE"
        ):
            raise ValueError(
                f"{path} must be mono 16-bit PCM at {sample_rate} Hz for the "
                "selected PocketSphinx model"
            )
        audio = source.readframes(source.getnframes())

    given_words = text.split()
    if not given_words:
        raise ValueError("alignment transcript is empty")
    normalized_words = [word.lower() for word in given_words]
    for given, normalized in zip(given_words, normalized_words, strict=True):
        if decoder.lookup_word(normalized) is None:
            raise ValueError(f"transcript word {given!r} is not in the dictionary")
    sentence = " ".join(normalized_words)
    try:
        decoder.set_align_text(sentence)
        decoder.start_utt()
        decoder.process_raw(audio, full_utt=True)
        decoder.end_utt()
        decoder.set_alignment()
        decoder.start_utt()
        decoder.process_raw(audio, full_utt=True)
        decoder.end_utt()
        raw_words = decoder.get_alignment()
    except RuntimeError as exc:
        raise ValueError(f"alignment failed for transcript {text!r}: {exc}") from exc

    lexical = []
    for item in raw_words:
        phone_rows = [
            {"phone": phone.name, "start": phone.start, "duration": phone.duration}
            for phone in item
        ]
        bases = {str(row["phone"]).upper().rstrip("0123456789") for row in phone_rows}
        if bases and bases <= profile.silence:
            continue
        lexical.append(
            {
                "word": item.name,
                "start": item.start,
                "duration": item.duration,
                "phones": phone_rows,
            }
        )
    if len(lexical) != len(given_words):
        raise ValueError(
            f"alignment failed for transcript {text!r}: expected {len(given_words)} "
            f"words, got {len(lexical)}"
        )
    for row, given in zip(lexical, given_words, strict=True):
        row["word"] = given
    frame_rate = float(decoder.config["frate"])
    return _form_from_alignment(
        lexical, frame_rate=frame_rate, features=features, profile=profile
    )


def align_entry(
    corpus: _corpus.Corpus,
    fileid: str,
    *,
    role: str = "aligned",
    source_role: str | None = None,
    text: str | None = None,
) -> Form:
    """Align one corpus WAV and store its timed form under ``role``."""
    entry = corpus.read(fileid)
    if text is None and source_role is not None:
        try:
            text = entry.forms[source_role].to_ipa()
        except KeyError as exc:
            raise ValueError(
                f"entry {fileid!r} has no source role {source_role!r}"
            ) from exc
    if text is None:
        held = entry.meta.get("text")
        if not isinstance(held, str):
            raise ValueError(f"entry {fileid!r} has no text metadata")
        text = held
    wav_path = corpus.asset(fileid, "wav")
    if wav_path is None:
        raise ValueError(f"entry {fileid!r} has no wav asset")
    form = align(wav_path, text)
    corpus.put_form(fileid, role, form)
    return form


def align_corpus(
    corpus: _corpus.Corpus,
    *,
    role: str = "aligned",
    source_role: str | None = None,
) -> AlignmentReport:
    """Align every corpus entry, retaining successes and reporting refusals."""
    aligned = []
    errors = []
    for fileid in corpus.ids():
        try:
            align_entry(corpus, fileid, role=role, source_role=source_role)
        except (ImportError, OSError, RuntimeError, ValueError, wave.Error) as exc:
            errors.append(AlignmentFailure(fileid, str(exc)))
        else:
            aligned.append(fileid)
    return AlignmentReport(tuple(aligned), tuple(errors))


__all__ = [
    "AlignmentFailure",
    "AlignmentReport",
    "align",
    "align_corpus",
    "align_entry",
]
