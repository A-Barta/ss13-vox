import hashlib
import string
import random
import logging
import collections
import subprocess
from pathlib import Path
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


def generate_speech_from_file(
    input_file: str,
    output_file: str,
    voice_id: str = "us-slt",
    tmp_dir: str = "tmp/speech",
) -> str:
    """
    Generate concatenated speech audio from a text file.

    Reads a text file line by line, generates TTS audio for each line,
    and concatenates them into a single output file.

    Args:
        input_file: Path to text file with one phrase per line
        output_file: Path for the output audio file (e.g., "output.mp3")
        voice_id: Voice ID to use (default: "us-slt")
        tmp_dir: Directory for temporary audio clips

    Returns:
        Path to the output file
    """
    from .voice import VoiceRegistry
    from .runtime import VOXRuntime

    # Initialize runtime
    runtime = VOXRuntime()
    runtime.loadConfig()
    runtime.initialize()
    voice = VoiceRegistry.Get(voice_id)

    # Create temp directory
    tmp_path = Path(tmp_dir)
    tmp_path.mkdir(parents=True, exist_ok=True)

    # Generate audio for each line
    clips: List[Path] = []
    with open(input_file, "r") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue

            # Use MD5 hash as filename for caching
            text_hash = hashlib.md5(text.encode()).hexdigest()
            clip_file = tmp_path / f"{text_hash}.ogg"

            if not clip_file.is_file():
                # Create phrase and generate audio
                p = Phrase()
                p.phrase = text
                p.parsed_phrase = text.split(" ")
                p.wordlen = len(p.parsed_phrase)
                runtime.createSoundFromPhrase(p, voice, str(clip_file))
                logger.info("Generated: %s", text[:50])

            clips.append(clip_file)

    if not clips:
        raise ValueError(f"No lines found in {input_file}")

    # Concatenate all clips using sox
    sox_cmd = ["sox"] + [str(c) for c in clips] + [output_file]
    logger.info("Concatenating %d clips into %s", len(clips), output_file)
    subprocess.run(sox_cmd, check=True)

    return output_file


def generate_allstar(output_file: str = "allstar.mp3") -> str:
    """
    Generate the All Star song using VOX TTS.

    Reads lyrics from wordlists/heynow.txt and generates speech audio.

    Args:
        output_file: Output filename (default: "allstar.mp3")

    Returns:
        Path to the output file
    """
    return generate_speech_from_file(
        input_file="wordlists/heynow.txt",
        output_file=output_file,
        tmp_dir="tmp/allstar",
    )
