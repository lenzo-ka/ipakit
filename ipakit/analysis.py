"""Analysis mixin for IPAFeatures - describe, natural_class, minimal_pairs."""

from __future__ import annotations

from ._base import IPAFeaturesBase
from ._convert import longest_match
from .constants import MAX_MATCH_LEN, METADATA_ATTRS, SEQ_TIE, TIE_BAR
from .segment import modifier_mode

# The slots a conventional name renders itself, in the order it renders
# them. There is one sentence, not two: "[voice] [modifiers] [place]
# [height backness round] [manner] [airstream]". A consonant states no
# height and no backness, so those slots fall out of its name and it
# reads "[voice] [place] [manner] [airstream]"; a vowel's manner *is*
# the word "vowel", so its name reads "[height] [backness] [round]
# vowel". These are the shape of the sentence, not a claim about
# phonetics; a feature named here is not also read out as a modifier.
#
# No slot goes unread because of the segment's class. A vowel letter
# states no place and no airstream, but a mark can put one on it
# ("a̪", "aʼ"), and a name that dropped it would give two distinct
# units one name -- the failure this whole path exists to avoid. The one
# slot read conditionally is `voiced`, for the reason describe() gives.
_CONSONANT_SLOTS = ("voiced", "place", "manner", "airstream")
_VOWEL_SLOTS = ("height", "backness", "rounded")
_PRIMARY_SLOTS = frozenset(_CONSONANT_SLOTS) | frozenset(_VOWEL_SLOTS)

# Where a modifier falls in the read-out, ahead of the primary
# articulation the way the conventional names do ("voiced velarized
# alveolar lateral approximant", "nasalized open front unrounded vowel").
# This says only *where in the sentence* a modifier goes. Whether it is
# read out at all is the data's call -- a value is read out because it
# declares a `label` -- and so is whether it reaches a consonant or a
# vowel: `channel` declares applies="consonant" because it places the
# airflow channel within a constriction and a vowel has none,
# `rhotacized` applies="vowel" because r-colouring is a vowel property,
# `retroflex` applies="consonant" because it is the consonant tongue
# shape. A labelled feature not named here still reads out, last.
_MODIFIER_READ_ORDER = (
    "palatalized",
    "labialized",
    "velarized",
    "pharyngealized",
    "labio-palatized",
    "syllabic",
    "retroflex",
    "rhotacized",
    "channel",
    "nasalized",
)


class AnalysisMixin(IPAFeaturesBase):
    """Mixin providing phonetic analysis functions."""

    def describe(self, phone: str, with_defaults: bool = True) -> str:
        """Generate human-readable IPA description for a phone.

        Examples:
            >>> ipakit.describe("p")
            'voiceless bilabial plosive'
            >>> ipakit.describe("ɛ")
            'open-mid front unrounded vowel'
            >>> ipakit.describe("t͡ʃ")
            'voiceless sibilant postalveolar affricate'
            >>> ipakit.describe("l")
            'voiced lateral alveolar approximant'
            >>> ipakit.describe("ɫ")
            'voiced velarized lateral alveolar approximant'
            >>> ipakit.describe("ã")
            'nasalized open front unrounded vowel'
            >>> ipakit.describe("ḁ")
            'voiceless open front unrounded vowel'
            >>> ipakit.describe("a̪")
            'dental open front unrounded vowel'
        """
        feats = self.get_features(phone, with_defaults=with_defaults)
        if not feats:
            return f"unknown phone: {phone}"

        manner = feats.get("manner", "")
        if manner == "silence":
            return "silence"
        vowel = manner == "vowel"
        parts = []

        # Voicing. The consonant sentence always says it. The vowel
        # sentence says it only when the segment has arrived at the
        # feature's *declared* default, because that default is the
        # unmarked value of the class that contrasts in voicing -- the
        # obstruents -- and every vowel letter in the inventory declares
        # its own voicing explicitly, which a data guard keeps true. So a
        # vowel that reaches the default was put there by a mark, and
        # that mark is exactly what has to be said: "ḁ" is a voiceless
        # vowel, and read this way it stops sharing a name with "a".
        # Saying it unconditionally would instead put "voiced" in front
        # of every vowel, which no conventional name does.
        voiced = feats.get("voiced")
        if (not vowel or voiced == self._declared_default("voiced")) and (
            label := self._label("voiced", voiced)
        ):
            parts.append(label)

        parts.extend(self._modifiers(feats))

        # Place. A vowel letter states none, but a mark can ("a̪").
        if place := feats.get("place"):
            parts.append(self._display_value("place", place))

        # The slots only a vowel fills.
        if vowel:
            parts.extend(
                word
                for slot in _VOWEL_SLOTS
                if (word := self._slot_word(slot, feats.get(slot))) is not None
            )

        # Manner -- for a vowel, the word is "vowel".
        if manner:
            parts.append(manner)

        # Airstream, when it is not the declared default. A vowel letter
        # states none either, but "aʼ" does.
        if (
            airstream := feats.get("airstream")
        ) and airstream != self._declared_default("airstream"):
            parts.append(airstream)

        return " ".join(parts)

    def _declared_default(self, feature: str) -> str | None:
        """The default the data declares for a feature.

        Read, never repeated. A description that compares against a value
        name it spells out itself -- ``airstream != "pulmonic"`` -- states
        a phonetic fact in Python and goes stale the moment the data
        moves the default, silently and in the direction of saying less.
        """
        feat = self.features.get(feature)
        return feat.default if feat is not None else None

    def _slot_word(self, feature: str, value: str | None) -> str | None:
        """The word a slot contributes to the sentence.

        A feature whose values declare labels reads by label -- `rounded`
        gives "unrounded", not "-". Everything else reads by value,
        through the same display rule the place slot uses.
        """
        if value is None:
            return None
        feat = self.features.get(feature)
        if feat is not None and feat.labels:
            return feat.labels.get(value)
        return self._display_value(feature, value)

    def _display_value(self, feature: str, value: str) -> str:
        """A value as a reader expects to see it.

        Only combining values are translated. Their canonical spelling
        joins components with the combiner (``bilabial^velar``), which is
        machine notation -- the data declares the conventional name
        (``labial-velar``) as an alias for exactly this purpose. Ordinary
        values keep their canonical spelling, since an alias there is a
        synonym rather than a readable form: `plosive` should not print
        as `stop`.
        """
        feat = self.features.get(feature)
        if feat is None or feat.COMBINER not in value:
            return value
        for alias, canonical in feat.value_aliases.items():
            if canonical == value:
                return alias
        return value

    def _label(self, feature: str, value: str | None) -> str | None:
        """The word a description uses for a feature value, or None when
        the data declares none -- the unremarkable side of a binary, or an
        axis position that goes unsaid (``channel=flat``)."""
        if value is None:
            return None
        feat = self.features.get(feature)
        return feat.labels.get(value) if feat is not None else None

    def _modifier_features(self, feats: dict[str, str]) -> list[str]:
        """The modifier features this segment reads out.

        Membership is the data's: a feature is read out because it
        declares a label for some value, and it reaches this segment
        because of its ``applies``. The consonant and vowel lists are
        therefore two views of one declaration and cannot drift apart.
        Everything this module contributes is the position in the
        sentence.

        ``applies`` says where a feature is *expected*, not where it may
        be reported. A segment that states one outside its class -- a
        rhotic mark written on a plosive -- is unusual notation, and
        describing it as though the mark were absent would give two
        distinct units one name, which is the failure this whole
        description path exists to avoid. So an explicitly stated,
        non-default value is always read out.
        """

        def stated(name: str) -> bool:
            feat = self.features.get(name)
            value = feats.get(name)
            return value is not None and feat is not None and value != feat.default

        pool = [
            name
            for name, feat in self.features.items()
            if feat.labels
            and name not in _PRIMARY_SLOTS
            and (self.feature_applies(name, feats) or stated(name))
        ]
        last = len(_MODIFIER_READ_ORDER)
        return sorted(
            pool,
            key=lambda name: (
                _MODIFIER_READ_ORDER.index(name)
                if name in _MODIFIER_READ_ORDER
                else last
            ),
        )

    def _modifiers(self, feats: dict[str, str]) -> list[str]:
        """Modifier labels for a bundle, in read-out order.

        A key the phone does not carry, and a value the data gives no
        label, contribute nothing -- so a phone that has no modifiers
        reads exactly as it did before there were any to report.
        """
        return [
            label
            for feat in self._modifier_features(feats)
            if (label := self._label(feat, feats.get(feat)))
        ]

    def natural_class(
        self,
        phones: list[str],
        with_defaults: bool = True,
        exclude_features: set[str] | None = None,
    ) -> dict[str, str]:
        """Find features shared by all phones in a set (natural class).

        Returns the intersection of features that all phones share.

        Examples:
            >>> ipakit.natural_class(["p", "t", "k"])  # shared features (incl. defaults)
            {'manner': 'plosive', ...'voiced': '-', ...}
            >>> ipakit.natural_class(["i", "e", "ɛ"])
            {'manner': 'vowel', ...'backness': 'front', ...}

        Args:
            phones: List of IPA phone symbols
            with_defaults: Include default feature values
            exclude_features: Features to exclude from result (default: class, href, xsampa)
        """
        if not phones:
            return {}

        exclude = exclude_features or set(METADATA_ATTRS)

        # Get features for all phones
        all_feats = [self.get_features(p, with_defaults=with_defaults) for p in phones]

        # A member that does not resolve cannot be dropped: the shared
        # features of the rest are not the shared features of the set,
        # and reporting them asserts of the unread member something never
        # checked. natural_class(["tʲ", "t"]) claimed both were plain.
        if unresolved := [p for p, f in zip(phones, all_feats, strict=True) if not f]:
            raise ValueError(
                f"cannot resolve {unresolved!r}: a natural class over phones "
                "that could not be read would describe only the rest of them"
            )

        # Find intersection: features present in ALL phones with same value
        shared = {}
        first = all_feats[0]

        for feat, value in first.items():
            if feat in exclude:
                continue
            if all(f.get(feat) == value for f in all_feats[1:]):
                shared[feat] = value

        return shared

    def minimal_pairs(
        self,
        phone: str,
        with_defaults: bool = True,
        max_distance: float = 0.3,
    ) -> list[tuple[str, str, str | None]]:
        """Find phones that differ by approximately one feature (minimal pairs).

        Returns list of (phone, differing_feature, differing_value) tuples,
        sorted by phonetic distance.

        Examples:
            >>> ipakit.minimal_pairs("p")
            [('t', 'place', 'alveolar'), ('ɸ', 'manner', 'fricative'), ...]

        Args:
            phone: The reference phone
            with_defaults: Include default feature values in comparison
            max_distance: Maximum distance to consider (default 0.3 ≈ 1-2 features)
        """
        ref_feats = self.get_features(phone, with_defaults=with_defaults)
        if not ref_feats:
            return []

        results = []
        for candidate in self.phones:
            if candidate == phone:
                continue

            cand_feats = self.get_features(candidate, with_defaults=with_defaults)
            if not cand_feats:
                continue

            # Calculate distance
            dist = self.distance(phone, candidate)
            if dist > max_distance:
                continue

            # Find the differing features
            diffs = []
            for feat in ref_feats:
                if feat in METADATA_ATTRS:
                    continue
                ref_val = ref_feats.get(feat)
                cand_val = cand_feats.get(feat)
                if ref_val != cand_val:
                    diffs.append((feat, cand_val))

            # Only include if there are 1-2 differences
            if 1 <= len(diffs) <= 2:
                # Report the primary difference
                primary_feat, primary_val = diffs[0]
                results.append((candidate, primary_feat, primary_val, dist))

        # Sort by distance, then alphabetically
        results.sort(key=lambda x: (x[3], x[0]))

        # Return without the distance
        return [(p, f, v) for p, f, v, _ in results]

    def nearest_phones(
        self,
        phone: str,
        n: int = 10,
        with_defaults: bool = True,
    ) -> list[tuple[str, float]]:
        """Find the n nearest phones by phonetic distance.

        Returns list of (phone, distance) tuples sorted by distance.
        Neighbours are drawn from the registered inventory; the reference
        may be any resolvable unit, registered or composed, so an
        unregistered affricate gets neighbours like any other input.

        Args:
            phone: The reference phone or composable unit
            n: Maximum number of results
            with_defaults: Include default feature values in comparison

        Raises:
            ValueError: if ``phone`` cannot be resolved at all -- an empty
                result would read as "no neighbours" rather than
                "unsupported input".
        """
        if phone not in self:  # type: ignore[operator]
            raise ValueError(
                f"cannot resolve {phone!r}: not a registered phone and not "
                "a composable tie-barred sequence of known phones"
            )

        distances = []
        for candidate in self.phones:
            if candidate == phone:
                continue
            dist = self.distance(phone, candidate)
            distances.append((candidate, dist))

        distances.sort(key=lambda x: (x[1], x[0]))
        return distances[:n]

    def validate_ipa(
        self,
        ipa: str,
        strict: bool = False,
    ) -> list[dict[str, str]]:
        """Validate an IPA string for well-formedness.

        Default parsing is strict house style, so ASCII stand-ins for IPA
        (``g``, ``:``, ``?``, ``'``, ``!``) are reported as unknown
        symbols, with a note naming the reading ``from_wild`` would give
        them. Validate wild text after importing it, not before.

        Checks for:
        - Unknown symbols (not in phones, diacritics, or suprasegmentals)
        - Orphan diacritics (diacritic without preceding base phone)
        - Malformed tie bars (tie bar without phones on both sides)
        - Stress marks that reach no unit: nothing after them to bind
          (``unbound_stress``), or another stress mark between them and
          the unit that takes the binding (``superseded_stress``)
        - Duplicate diacritics on the same segment

        Returns a list of issue dicts with keys:
        - type: "error" or "warning"
        - code: machine-readable issue code
        - message: human-readable description
        - position: character index in the string
        - symbol: the problematic symbol (if applicable)

        Examples:
            validate_ipa("kæt")     # [] (valid)
            validate_ipa("kæt̪")     # [] (valid - dental diacritic on t)
            validate_ipa("k4t")     # [{"type": "error", "code": "unknown_symbol", ...}]  ('x','y','z' are valid IPA)
            validate_ipa("̃a")       # [{"type": "error", "code": "orphan_diacritic", ...}]

        Args:
            ipa: The IPA string to validate
            strict: If True, treat warnings as errors
        """
        issues: list[dict[str, str]] = []
        ipa = self.expand_ligatures(ipa)

        # Known symbols
        known_phones = set(self.phones)
        known_diacritics = {
            s
            for s, p in self.diacritics.items()
            if p.features.get("class") == "diacritic"
        }
        suprasegmentals = {
            s
            for s, p in self.diacritics.items()
            if p.features.get("class") == "suprasegmental"
        }
        # Stress, length, tone, breaks, separators, and space stand alone (no
        # base phone required). The tie bars are suprasegmentals but checked below.
        standalone = (suprasegmentals | set(self.separators) | {" "}) - {
            TIE_BAR,
            SEQ_TIE,
        }

        i = 0
        last_was_phone = False
        current_segment_diacritics: set[str] = set()

        while i < len(ipa):
            char = ipa[i]

            # Try to match multi-character phones first (affricates, etc.)
            matched_phone, matched_len = longest_match(
                ipa, i, known_phones, MAX_MATCH_LEN, tie_set=known_phones
            )

            if matched_phone:
                # Valid phone found
                last_was_phone = True
                current_segment_diacritics = set()
                i += matched_len
                continue

            # Standalone symbols (stress, length, tone, breaks, separators)
            if char in standalone:
                if (why := self._stress_reaches_no_unit(ipa, i)) is not None:
                    issues.append(
                        {
                            "type": "error",
                            "code": f"{why}_stress",
                            "message": (
                                "Stress mark binds nothing"
                                if why == "unbound"
                                else "Stress mark superseded by a nearer one"
                            ),
                            "position": str(i),
                            "symbol": char,
                        }
                    )
                # These are valid on their own or after phones. A prosodic
                # mark rides on the unit it follows and does not end it --
                # ``parse`` collects it into that unit's modifier run, so
                # "aː͡s" is one unit there and must not read as a tie with
                # nothing on its left here. A break or separator does end
                # the unit, and so does a stress mark: it is written
                # before what it scopes, so ``parse`` stops the modifier
                # run at it and the unit before it is closed.
                if not (
                    char in self.diacritics
                    and char not in self.stress_markers
                    and modifier_mode(self, char) != "structural"
                ):
                    last_was_phone = False
                    current_segment_diacritics = set()
                i += 1
                continue

            # Check for diacritics (modifiers that require a base phone)
            if char in known_diacritics:
                if not last_was_phone:
                    issues.append(
                        {
                            "type": "error",
                            "code": "orphan_diacritic",
                            "message": f"Diacritic '{char}' without preceding base phone",
                            "position": str(i),
                            "symbol": char,
                        }
                    )
                elif char in current_segment_diacritics:
                    issues.append(
                        {
                            "type": "warning",
                            "code": "duplicate_diacritic",
                            "message": f"Duplicate diacritic '{char}' on same segment",
                            "position": str(i),
                            "symbol": char,
                        }
                    )
                else:
                    current_segment_diacritics.add(char)
                i += 1
                continue

            # Check for tie bar (either sense)
            if char in (TIE_BAR, SEQ_TIE):
                # A tie joins the unit before it to the unit after it, so
                # it is malformed unless both sides are there. This is the
                # same condition the parser drops on (see
                # ``IPAFeatures.parse``): a tie that binds nothing carries
                # no juncture and cannot be represented. A well-formed tie
                # never reaches here between registered bases -- the whole
                # composite matched above -- but it does after a diacritic
                # ("t̪͡s"), where the left side is the modified unit.
                _, ahead = longest_match(
                    ipa, i + 1, known_phones, MAX_MATCH_LEN, tie_set=known_phones
                )
                if not last_was_phone or not ahead:
                    issues.append(
                        {
                            "type": "error",
                            "code": "malformed_tie",
                            "message": "Tie bar binds nothing",
                            "position": str(i),
                            "symbol": char,
                        }
                    )
                last_was_phone = False
                i += 1
                continue

            # Unknown symbol. ASCII stand-ins land here by design -- default
            # parsing is strict house style -- so point at the import door
            # rather than leaving the reader to guess what went wrong.
            message = f"Unknown symbol '{char}' (U+{ord(char):04X})"
            if (soft := self.lookalikes.get(char)) is not None:
                message += f"; from_wild() reads it as '{soft}'"
            elif char == "!":
                message += "; write 'ǃ' for the click or 'ꜜ' for downstep"
            issues.append(
                {
                    "type": "error",
                    "code": "unknown_symbol",
                    "message": message,
                    "position": str(i),
                    "symbol": char,
                }
            )
            last_was_phone = False
            i += 1

        # If strict mode, upgrade warnings to errors
        if strict:
            for issue in issues:
                if issue["type"] == "warning":
                    issue["type"] = "error"

        return issues

    def _stress_reaches_no_unit(self, ipa: str, i: int) -> str | None:
        """Why the mark at ``ipa[i]`` reaches no unit's prosody, or None.

        Only stress is asked about: it is the one mark written before
        what it scopes, so it is the one that can be left holding
        nothing. The two answers are the two :meth:`IPAFeatures.segments`
        reports -- nothing follows it, or a nearer mark takes the
        binding -- so the validator and the parser name the same two
        mistakes. Separators and whitespace are transparent: they carry
        no unit, so a stress mark still binds across them.
        """
        if ipa[i] not in self.stress_markers:
            return None
        j = i + 1
        while j < len(ipa) and (ipa[j].isspace() or ipa[j] in self.separators):
            j += 1
        if j >= len(ipa):
            return "unbound"
        return "superseded" if ipa[j] in self.stress_markers else None

    def is_valid_ipa(self, ipa: str) -> bool:
        """Check if an IPA string is valid (no errors).

        Returns True if the string has no validation errors.
        Warnings are allowed.
        """
        issues = self.validate_ipa(ipa)
        return not any(issue["type"] == "error" for issue in issues)
