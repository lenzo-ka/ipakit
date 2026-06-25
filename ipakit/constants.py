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

TIE_BAR = "\u0361"  # ͡

# Display/formatting constants
DEFAULT_SHORT_NAME_LEN = 3  # Default length for auto-generated short names
MAX_EXAMPLE_PHONES = 5  # Max example phones to show in listings
