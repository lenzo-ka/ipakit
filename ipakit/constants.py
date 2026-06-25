"""Constants for IPA feature handling."""

from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_IPA_FEATS = DATA_DIR / "ipa.xml"
PHONEMAPS_DIR = DATA_DIR / "phonemaps"
DEFAULT_CMU_MAP = PHONEMAPS_DIR / "cmu.xml"
DEFAULT_LOOKALIKES = PHONEMAPS_DIR / "lookalikes.xml"

TIE_BAR = "\u0361"  # ͡

STRESS_MARKERS = {"ˈ": 1, "ˌ": 2}
STRESS_TO_MARKER = {v: k for k, v in STRESS_MARKERS.items()}

# Display/formatting constants
DEFAULT_SHORT_NAME_LEN = 3  # Default length for auto-generated short names
MAX_EXAMPLE_PHONES = 5  # Max example phones to show in listings
