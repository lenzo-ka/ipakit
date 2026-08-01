"""Constants for IPA feature handling."""

from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_IPA_FEATS = DATA_DIR / "ipa.xml"
PHONEMAPS_DIR = DATA_DIR / "phonemaps"
DEFAULT_CMU_MAP = PHONEMAPS_DIR / "cmu.xml"
DEFAULT_LOOKALIKES = PHONEMAPS_DIR / "lookalikes.xml"
DEFAULT_CONFUSION = DATA_DIR / "confusion.json"

# Attributes stored on phones/diacritics that are structural metadata, NOT
# phonetic features. These are excluded from natural-class intersection and
# from validation of declared feature values.
#   name   - the symbol itself (stripped during load, but guard anyway)
#   class  - structural element type (phone/diacritic/suprasegmental)
#   href   - Wikipedia article slug for the symbol
#   xsampa - X-SAMPA encoding of the symbol
METADATA_ATTRS = frozenset({"name", "class", "href", "xsampa"})

# The two tie characters used to sit here as bare strings, and they are a
# phonetic fact ipa.xml already states: it declares a `tie` feature whose
# values are `simultaneous` and `sequential`, and declares the
# suprasegmental that carries each. They are read from that declaration
# now -- `IPAFeatures.tie_bar`, `.seq_tie` and `.tie_bars`, in the shape
# of `.stress_markers`. The read cannot live here: `features` imports this
# module, so a name here could only be spelled out, which is the smuggling
# itself.

# The element class `<zeros>` declares, and the `class` value its members
# carry -- the singular-of-the-section rule `<classes>` states and
# `IPAFeatures._load` follows. Here rather than in either reader because
# `features` routes the section and `form` reads a unit's class off it; a
# second spelling of the word in one of them is how those two would drift.
ZERO_CLASS = "zero"

# Root element of a supplemental inventory file. Its own tag rather than
# `<ipa>` so that handing a whole inventory where a supplement is wanted --
# or the reverse -- is refused at load rather than half-merged. What a
# supplement may declare is not listed here: it is the element sections
# `<classes>` already names, read off the loaded inventory. See
# docs/supplements.md.
SUPPLEMENT_ROOT = "supplement"

# Sentinel used by hierarchy building for a phone that lacks the splitting
# feature. Chosen to never collide with a real feature value.
MISSING_FEATURE_VALUE = "_none"

# Longest-match window, in characters, for `_convert.longest_match`: the
# longest prefix it will consider as one key. The floor is the longest
# registered spelling, which is a tie-bar composite (`t͡ʃ`, base + tie +
# base) rather than a single letter, and that is the whole requirement.
# It is not what bounds a tie chain: `IPAFeatures.parse` grows a chain
# past the window a juncture at a time, so a chain of any length reads as
# one unit. Two justifications used to sit here saying otherwise, one of
# them arithmetic that does not come to 11.
#
# Wider than the floor so a longer registered spelling does not need an
# edit here. Measured over the whole unit corpus and over tie chains up to
# seven constituents, every window from the floor upward tokenizes and
# segments identically, so the slack costs a few scan steps and changes
# no answer. `tests/test_tokenization.py` derives the floor and pins the
# chain claim.
MAX_MATCH_LEN = 11

# Display/formatting constants
DEFAULT_SHORT_NAME_LEN = 3  # Default length for auto-generated short names
MAX_EXAMPLE_PHONES = 5  # Max example phones to show in listings

# Classes an `applies` declaration may name besides a declared manner
# value. Each is a predicate over data already in the file, not a list of
# values restated here: `consonant` is `IPAFeatures.consonant_manners`,
# the complement of vowel and silence, and `nucleus` is
# `IPAFeatures.is_nucleus`, vowel-or-syllabic.
DERIVED_CLASSES = frozenset({"consonant", "nucleus"})
