"""FMF (Flipper Music Format) formatting and validation utilities.

Important: Flipper Zero's Music Player uses a line-based key/value format (FMF v0),
not the legacy single-line `BPM=...:DURATION=...:OCTAVE=...:` format that appears in
some online examples.

We still accept the legacy format as input and normalize it to the v0 format on write.
"""

import re
from typing import Tuple, Optional


_LEGACY_HEADER_RE = re.compile(r"BPM=(\d+):DURATION=(\d+):OCTAVE=(\d+):")


def normalize_fmf(song_data: str) -> str:
    """
    Normalize song data into the Flipper Music Player's FMF v0 format.

    Supported inputs:
    - FMF v0 (line-based): "Filetype: ...\\nVersion: 0\\nBPM: ...\\nDuration: ...\\nOctave: ...\\nNotes: ..."
    - Legacy (single-line): "BPM=120:DURATION=4:OCTAVE=4: 4C 4D 4E"
    """
    if not song_data:
        return ""
    s = song_data.strip()

    # If it already looks like FMF v0, keep as-is (but we'll ensure required headers exist).
    if re.search(r"(?mi)^Notes\\s*:", s) or re.search(r"(?mi)^Filetype\\s*:", s):
        # Ensure Filetype/Version headers exist (Music Player files include these).
        has_filetype = bool(re.search(r"(?mi)^Filetype\\s*:", s))
        has_version = bool(re.search(r"(?mi)^Version\\s*:", s))
        if has_filetype and has_version:
            return s + ("\n" if not s.endswith("\n") else "")
        lines = s.splitlines()
        out: list[str] = []
        if not has_filetype:
            out.append("Filetype: Flipper Music Format")
        if not has_version:
            out.append("Version: 0")
        out.extend(lines)
        normalized = "\n".join(out).strip() + "\n"
        return normalized

    # Legacy: BPM=...:DURATION=...:OCTAVE=...: <notes...>
    m = _LEGACY_HEADER_RE.search(s)
    if m:
        bpm, duration, octave = m.group(1), m.group(2), m.group(3)
        notes_section = s[m.end() :].strip()
        tokens = [t for t in re.split(r"[\s,]+", notes_section) if t.strip()]
        notes = ", ".join(tokens)
        return (
            "Filetype: Flipper Music Format\n"
            "Version: 0\n"
            f"BPM: {bpm}\n"
            f"Duration: {duration}\n"
            f"Octave: {octave}\n"
            f"Notes: {notes}\n"
        )

    # Unknown: return trimmed input so validator can produce a meaningful error.
    return s + ("\n" if not s.endswith("\n") else "")


def validate_fmf_format(song_data: str) -> Tuple[bool, Optional[str]]:
    """
    Validate FMF format syntax.
    
    Args:
        song_data: Song data in FMF format
        
    Returns:
        (is_valid, error_message) tuple
    """
    normalized = normalize_fmf(song_data)
    if not normalized or not normalized.strip():
        return False, "Song data is empty"

    # FMF v0 required fields
    def find_int(key: str) -> Optional[int]:
        m2 = re.search(rf"(?mi)^{re.escape(key)}\s*:\s*(\d+)\s*$", normalized)
        return int(m2.group(1)) if m2 else None

    bpm = find_int("BPM")
    duration = find_int("Duration")
    octave = find_int("Octave")
    notes_match = re.search(r"(?mi)^Notes\s*:\s*(.+)\s*$", normalized)

    if bpm is None:
        return False, "Missing BPM header line (expected: 'BPM: <number>')"
    if duration is None:
        return False, "Missing Duration header line (expected: 'Duration: <number>')"
    if octave is None:
        return False, "Missing Octave header line (expected: 'Octave: <number>')"
    if not notes_match or not notes_match.group(1).strip():
        return False, "Missing Notes line (expected: 'Notes: <comma-separated notes>')"

    # Validate notes (comma-separated). Examples from device:
    # - E6, P, 4P, F#, B4
    notes_str = notes_match.group(1).strip()
    tokens = [t.strip() for t in notes_str.split(",") if t.strip()]
    if not tokens:
        return False, "No notes found after 'Notes:'"

    # token: optional duration prefix, note letter or P, optional accidental, optional octave suffix, optional dot
    token_re = re.compile(r"^(\d+)?([A-GP])([#b])?(\d+)?(\.)?$")
    for tok in tokens:
        if not token_re.match(tok):
            return (
                False,
                f"Invalid note token: '{tok}'. Expected forms like 'E6', 'F#', 'B4', '4P', '8A#5'.",
            )

    return True, None


def get_fmf_format_specification() -> str:
    """
    Get detailed FMF format specification.
    
    Returns:
        Detailed format specification string
    """
    spec = """FMF (Flipper Music Format) Specification (Flipper Music Player)
==========================================

FMF is a simple line-based key/value format used by Flipper Zero's Music Player app.

FILE FORMAT (FMF v0)
-------------------
An FMF file is plain text with these header lines:

  Filetype: Flipper Music Format
  Version: 0
  BPM: <bpm>
  Duration: <duration>
  Octave: <octave>
  Notes: <notes>

Where:
  - BPM: Beats per minute (tempo), typically 60-200
  - Duration: Default note duration (1=whole, 2=half, 4=quarter, 8=eighth, 16=sixteenth)
  - Octave: Default octave (3-7, where 4 is middle C)
  - Notes: Comma-separated note tokens

NOTE FORMAT
-----------
Notes are comma-separated. Each token is:

  [DURATION]<NOTE>[ACCIDENTAL][OCTAVE]

Where:
  - DURATION: optional duration override (1, 2, 4, 8, 16)
  - NOTE: A, B, C, D, E, F, G or P (pause)
  - ACCIDENTAL: optional '#' (sharp) or 'b' (flat)
  - OCTAVE: optional octave override (3-7)

Examples from a known-good device file:
  E6, P, 4P, F#, B4, 8A#5

NOTES
-----
- Notes are separated by commas (spaces after commas are allowed)
- Rests use 'P'
- Sharps use '#' and flats use 'b'
- When a note has no explicit duration, it uses the file's Duration header
- When a note has no explicit octave, it uses the file's Octave header

COMPLETE EXAMPLE
----------------
Filetype: Flipper Music Format
Version: 0
BPM: 120
Duration: 4
Octave: 4
Notes: 4C, 4C, 8C, 4D, 4E, 4C, 4E, 4D

TIPS
----
- Start with simple melodies using default octave/duration
- Use rests (P) for pauses between phrases
- Adjust BPM to match the song's natural tempo
- Test with short melodies first

Legacy compatibility:
---------------------
This project will also accept the legacy single-line format:

  BPM=120:DURATION=4:OCTAVE=4: 4C 4D 4E

...and will normalize it to the FMF v0 format when saving to the device."""
    
    return spec

