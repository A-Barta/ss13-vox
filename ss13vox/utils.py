import hashlib
import string
import random
import logging
import collections
from typing import Dict, List

from .phrase import Phrase, EPhraseFlags, ParsePhraseListFrom

logger = logging.getLogger(__name__)


def md5sum(filename):
    md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(128 * md5.block_size), b""):
            md5.update(chunk)
    return md5.hexdigest()


def generate_preshared_key():
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for x in range(64))


def generate_random_string(charlen=16):
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for x in range(charlen))


def organize_file(filename: str, sort_sections: bool = False) -> str:
    """
    Organize a wordlist file by category and sort entries alphabetically.

    Reads a wordlist file, groups phrases by their category or flags,
    sorts them, and writes out a cleaned version with .sorted extension.

    Args:
        filename: Path to the wordlist file to organize
        sort_sections: If True, also sort the section headers alphabetically

    Returns:
        Path to the output file (filename + ".sorted")
    """
    phrases: Dict[str, List[Phrase]] = collections.OrderedDict()
    phrases_by_id: Dict[str, Phrase] = {}

    for p in ParsePhraseListFrom(filename):
        if p.id.lower() in phrases_by_id:
            logger.warning("Skipping duplicate %s...", p.id)
            continue

        # Determine which section this phrase belongs to
        if p.hasFlag(EPhraseFlags.SFX):
            assign_to = EPhraseFlags.SFX.name
        elif p.hasFlag(EPhraseFlags.OLD_VOX):
            assign_to = EPhraseFlags.OLD_VOX.name
        else:
            assign_to = p.category or ""

        phrases_by_id[p.id.lower()] = p
        if assign_to not in phrases:
            phrases[assign_to] = []
        phrases[assign_to].append(p)

    # Optionally sort section headers
    if sort_sections:
        sorted_phrases = collections.OrderedDict()
        for k in sorted(phrases.keys()):
            sorted_phrases[k] = phrases[k]
        phrases = sorted_phrases

    # Write sorted output
    output_file = filename + ".sorted"
    with open(output_file, "w") as w:
        divider_len = max([len(x) for x in phrases.keys() if x], default=4) + 4
        divider = "#" * divider_len

        for section, section_phrases in phrases.items():
            if section != "":
                w.write(f"\n{divider}\n## {section}\n{divider}\n\n")

            for phrase in sorted(section_phrases, key=lambda x: x.id):
                # Write any comments that preceded this phrase
                for comm in phrase.comments_before:
                    comm = comm.rstrip()
                    w.write(f"#{comm}\n")

                key = phrase.id
                new_key = key.lower() if "/" not in key else key
                value = phrase.phrase

                if phrase.hasFlag(EPhraseFlags.SFX):
                    w.write(f"{new_key} = @{value}\n")
                elif key != value:
                    w.write(f"{new_key} = {value}\n")
                else:
                    w.write(f"{new_key}\n")

    logger.info("Wrote organized wordlist to %s", output_file)
    return output_file


def organize_wordlists() -> None:
    """Organize all standard wordlist files."""
    organize_file("wordlists/common.txt")
    organize_file("wordlists/common-clean.txt")
    organize_file("wordlists/profanity.txt")
    organize_file("wordlists/vg/announcements.txt")
    organize_file("wordlists/vg/antags.txt", sort_sections=True)
    organize_file("wordlists/vg/chemistry.txt")
    organize_file("wordlists/vg/mining.txt")
    organize_file("wordlists/vg/misc.txt", sort_sections=True)
