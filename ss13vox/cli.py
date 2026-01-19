"""
Command-line interface for SS13-VOX generation.
"""

import sys
import os
import json
import hashlib
import logging
import argparse
import pathlib
import subprocess
import multiprocessing
import time
import collections

from yaml import safe_load
from yaml import YAMLError

from .consts import PRE_SOX_ARGS, RECOMPRESS_ARGS
from .voice import (
    EVoiceSex,
    SFXVoice,
    USSLTFemale,
    Voice,
    VoiceRegistry,
)
from .pronunciation import DumpLexiconScript, ParseLexiconText
from .phrase import EPhraseFlags, FileData, ParsePhraseListFrom, Phrase
from .codegen import CodeGenConfig, get_generator

FORMAT = "%(levelname)s --- %(message)s"
LOGLEVEL = logging.DEBUG

TEMP_DIR = "tmp"
DIST_DIR = "dist"
DATA_DIR = os.path.join(DIST_DIR, "data")

logger = logging.getLogger("ss13vox")


def loadYaml(filename):
    try:
        with open(filename) as stream:
            try:
                parsed_yaml = safe_load(stream)
                config = parsed_yaml
            except YAMLError:
                logger.error(f"Invalid config in {filename}")
                sys.exit(15)
    except OSError:
        logger.error(f"File not found: {filename}")
        sys.exit(10)
    return config


def md5sum(filename: str) -> str:
    md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(128 * md5.block_size), b""):
            md5.update(chunk)
    return md5.hexdigest()


def run_cmd(
    command: list[str],
    echo: bool = False,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    """Run a command, optionally echoing it and capturing output."""
    if echo:
        logger.debug(f"Running: {' '.join(command)}")
    result = subprocess.run(
        command,
        capture_output=capture_output,
        text=capture_output,
    )
    if result.returncode != 0:
        logger.error(
            f"Command failed with code {result.returncode}: {command}"
        )
        if capture_output and result.stderr:
            logger.error(f"stderr: {result.stderr}")
        sys.exit(1)
    return result


def generate_for_word(
    phrase: Phrase,
    voice: Voice,
    written_files: set,
    lexicon_path: str,
    args: dict,
) -> None:
    """Generate audio file for a single phrase."""
    if phrase.hasFlag(EPhraseFlags.OLD_VOX):
        logger.info(f"Skipping {phrase.id}.ogg (Marked as OLD_VOX)")
        return

    filename = phrase.getFinalFilename(voice.assigned_sex)
    sox_args = voice.genSoxArgs(args)

    # Build cache key from all inputs that affect output
    cache_key = json.dumps(phrase.serialize())
    cache_key += "".join(sox_args) + PRE_SOX_ARGS + "".join(RECOMPRESS_ARGS)
    cache_key += voice.fast_serialize()
    cache_key += filename

    oggfile = os.path.abspath(os.path.join(DIST_DIR, filename))
    cachebase = os.path.abspath(
        os.path.join("cache", phrase.id.replace(os.sep, "_").replace(".", ""))
    )
    checkfile = cachebase + voice.ID + ".dat"
    cachefile = cachebase + voice.ID + ".json"

    fdata = FileData()
    fdata.voice = voice.ID
    fdata.filename = os.path.relpath(oggfile, DIST_DIR)

    def commit_written():
        nonlocal phrase, voice, oggfile, written_files, fdata
        if voice.ID == SFXVoice.ID:
            # Both masculine and feminine voicepacks link to SFX
            for sex in ["fem", "mas"]:
                phrase.files[sex] = fdata
        else:
            phrase.files[voice.assigned_sex] = fdata
        written_files.add(os.path.abspath(oggfile))

    # Ensure output directories exist
    for path in [os.path.dirname(oggfile), os.path.dirname(cachefile)]:
        if not os.path.isdir(path):
            os.makedirs(path)

    # Check cache - skip if already generated with same inputs
    if os.path.isfile(oggfile) and os.path.isfile(cachefile):
        old_cache_key = ""
        if os.path.isfile(checkfile):
            with open(checkfile, "r") as f:
                old_cache_key = f.read()
        if old_cache_key == cache_key:
            with open(cachefile, "r") as f:
                fdata.deserialize(json.load(f))
            logger.info(f"Skipping {filename} for {voice.ID} (exists)")
            commit_written()
            return

    logger.info(f"Generating {filename} for {voice.ID} ({phrase.phrase!r})")

    # Build text2wave command
    if phrase.hasFlag(EPhraseFlags.SFX):
        text2wave = ["ffmpeg", "-i", phrase.phrase, f"{TEMP_DIR}/VOX-word.wav"]
    else:
        phrasefile = os.path.join(TEMP_DIR, "VOX-word.txt")
        text2wave = ["text2wave"]
        # Set voice
        text2wave += ["-eval", f"(voice_{voice.FESTIVAL_VOICE_ID})"]
        # Load lexicon
        if os.path.isfile(lexicon_path):
            text2wave += ["-eval", lexicon_path]
        if phrase.hasFlag(EPhraseFlags.SING):
            text2wave += ["-mode", "singing", phrase.phrase]
        else:
            with open(phrasefile, "w") as f:
                f.write(phrase.phrase + "\n")
            text2wave += [phrasefile]
        text2wave += ["-o", f"{TEMP_DIR}/VOX-word.wav"]

    # Write cache key
    with open(checkfile, "w") as f:
        f.write(cache_key)

    # Clean up temp files
    for fn in (
        f"{TEMP_DIR}/VOX-word.wav",
        f"{TEMP_DIR}/VOX-soxpre-word.wav",
        f"{TEMP_DIR}/VOX-sox-word.wav",
        f"{TEMP_DIR}/VOX-encoded.ogg",
    ):
        if os.path.isfile(fn):
            os.remove(fn)

    # Build command pipeline
    cmds = []
    cmds.append((text2wave, f"{TEMP_DIR}/VOX-word.wav"))

    # Only skip SoX pre-processing if BOTH flags are set
    skip_sox_pre = phrase.hasFlag(EPhraseFlags.NO_PROCESS) and phrase.hasFlag(
        EPhraseFlags.NO_TRIM
    )
    if not skip_sox_pre:
        cmds.append(
            (
                [
                    "sox",
                    f"{TEMP_DIR}/VOX-word.wav",
                    f"{TEMP_DIR}/VOX-soxpre-word.wav",
                ]
                + PRE_SOX_ARGS.split(" "),
                f"{TEMP_DIR}/VOX-soxpre-word.wav",
            )
        )

    if not phrase.hasFlag(EPhraseFlags.NO_PROCESS):
        cmds.append(
            (
                ["sox", cmds[-1][1], f"{TEMP_DIR}/VOX-sox-word.wav"]
                + sox_args,
                f"{TEMP_DIR}/VOX-sox-word.wav",
            )
        )

    cmds.append(
        (
            ["oggenc", cmds[-1][1], "-o", f"{TEMP_DIR}/VOX-encoded.ogg"],
            f"{TEMP_DIR}/VOX-encoded.ogg",
        )
    )

    cmds.append(
        (
            ["ffmpeg", "-i", f"{TEMP_DIR}/VOX-encoded.ogg"]
            + RECOMPRESS_ARGS
            + ["-threads", str(args["threads"])]
            + [oggfile],
            oggfile,
        )
    )

    # Execute pipeline
    for command, _ in cmds:
        run_cmd(command, echo=args["echo"])

    # Get audio metadata with ffprobe
    probe_cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        oggfile,
    ]
    result = run_cmd(probe_cmd, echo=args["echo"], capture_output=True)
    fdata.fromJSON(json.loads(result.stdout))
    fdata.checksum = md5sum(oggfile)

    # Adjust duration for non-SFX (removes silence padding)
    if not phrase.hasFlag(EPhraseFlags.SFX) and fdata.duration > 10.0:
        fdata.duration -= 10.0

    # Verify output files exist
    for command, expected_file in cmds:
        if not os.path.isfile(expected_file):
            logger.error(
                f"File '{expected_file}' doesn't exist, "
                f"command '{command}' probably failed!"
            )
            sys.exit(1)

    # Save cache
    with open(cachefile, "w") as f:
        json.dump(fdata.serialize(), f)

    commit_written()


def generate(args: dict) -> None:
    """Main generation logic."""
    voices = []

    logger.info("Started voice generation")
    for _k, _v in args.items():
        logger.debug(f"Using argument {_k}={_v}")
    logger.debug(
        f"Paths:\n  temporary folder = {TEMP_DIR}\n"
        f"  distribution folder = {DIST_DIR}\n"
        f"  voices = {voices}\n"
    )

    # get config
    config = loadYaml(args["config"])

    # configure
    station = args["station"]
    preexSound = config["paths"][station]["sound"]["old-vox"]
    nuvoxSound = config["paths"][station]["sound"]["new-vox"]

    voice_assignments = {}
    all_voices = []
    default_voice: Voice = VoiceRegistry.Get(USSLTFemale.ID)
    # This should default to config['voices']['default']
    sfx_voice: SFXVoice = SFXVoice()
    configured_voices: dict[str, dict] = {}

    for sexID, voiceid in config["voices"].items():
        voice = VoiceRegistry.Get(voiceid)
        assert sexID != ""
        voice.assigned_sex = sexID
        if sexID in ("fem", "mas"):
            sex = EVoiceSex(sexID)
            assert voice.SEX == sex
            voices.append(voice)
        elif sexID == "default":
            pass
            # default_voice = voice
        voice_assignments[voice.SEX] = []
        all_voices.append(voice)
        configured_voices[sexID] = voice.serialize()

    logger.info(
        f"List of all voices found: {[voice.ID for voice in all_voices]}"
    )
    logger.info(f"List of all voices configured: {configured_voices}")

    logger.info(f"Checking that {DATA_DIR} exists")
    if not os.path.exists(DATA_DIR):
        logger.info(f"{DATA_DIR} not found, creating it")
        os.makedirs(DATA_DIR)
        logger.info("Success")
    else:
        logger.info(f"{DATA_DIR} exists, moving on")

    lexicon = ParseLexiconText("lexicon.txt")

    phrases: list[Phrase] = []
    phrasesByID = {}
    broked = False
    max_wordlen = config["max-wordlen"]
    for filename in config["phrasefiles"]:
        for p in ParsePhraseListFrom(filename):
            p.wordlen = min(max_wordlen, p.wordlen)
            if p.id in phrasesByID:
                duplicated = phrasesByID[p.id]
                logger.info(
                    f"Duplicate phrase with ID {p.id} "
                    f"in file {p.deffile} on line {p.defline}! "
                    f"First instance in file {duplicated.deffile} "
                    f"on line {duplicated.defline}."
                )
                broked = True
                continue
            phrases += [p]
            phrasesByID[p.id] = p
        if broked:
            sys.exit(1)

    phrases.sort(key=lambda x: x.id)

    overrides = config["overrides"]
    for phrase in phrases:
        if phrase.id in overrides:
            logger.debug(f"Phrase {phrase} is in ovverrides")
            phrase.fromOverrides(overrides.get(phrase.id))
        phrase_voices = [default_voice]
        if "/" in phrase.id:
            # if the ID is a path, treat it as filename
            phrase.filename = f"{phrase.id}.ogg"
            phrase_voices = [default_voice]
        elif phrase.hasFlag(flag=EPhraseFlags.OLD_VOX):
            phrase.filename = preexSound
            for voice in ("fem", "mas"):
                phrase.files[voice] = FileData()
                phrase.files[voice].filename = phrase.filename
                phrase.files[voice].checksum = ""
                if phrase.override_duration:
                    phrase.files[voice].duration = phrase.override_duration
                else:
                    phrase.files[voice].duration = -1
                if phrase.override_size:
                    phrase.files[voice].size = phrase.override_size
                else:
                    phrase.files[voice].size = -1
            # add to soundsToKeep
            continue
        elif phrase.hasFlag(EPhraseFlags.SFX):
            phrase.filename = nuvoxSound
            phrase_voices = [sfx_voice]
        else:
            # Regular phrase - use new-vox path template
            phrase.filename = nuvoxSound
        for voice in phrase_voices:
            voice_assignments[voice.SEX].append(phrase)

    logger.info(f"Checking that {TEMP_DIR} exists")
    if not os.path.exists(TEMP_DIR):
        logger.info(f"{TEMP_DIR} not found, creating it")
        os.makedirs(TEMP_DIR)

    lexicon_path = os.path.join(TEMP_DIR, "VOXdict.lisp")
    DumpLexiconScript("", list(lexicon.values()), lexicon_path)
    logger.info(f"Wrote lexicon script to {lexicon_path}")

    sounds_to_keep: set[str] = set()

    for voice in all_voices:
        logger.info(f"ID = {voice.ID}, assigned_sex = {voice.assigned_sex}")
        for phrase in voice_assignments[voice.SEX]:
            generate_for_word(
                phrase, voice, sounds_to_keep, lexicon_path, args
            )
            for fd in phrase.files.values():
                sounds_to_keep.add(
                    os.path.abspath(os.path.join(DIST_DIR, fd.filename))
                )

    # Build sexes dict for code generation
    sexes: dict[str, list[Phrase]] = {
        "fem": [],
        "mas": [],
    }
    for p in phrases:
        if p.hasFlag(EPhraseFlags.NOT_VOX):
            continue
        for k in p.files.keys():
            if p.hasFlag(EPhraseFlags.SFX):
                # SFX phrases go to both fem and mas
                for sid in ("fem", "mas"):
                    if p not in sexes[sid]:
                        sexes[sid].append(p)
            else:
                if k in sexes:
                    sexes[k].append(p)

    # Generate DM code
    codegen_config = CodeGenConfig(
        template_dir=pathlib.Path("templates"),
        output_dir=pathlib.Path(DIST_DIR),
    )
    generator = get_generator(station, codegen_config, use_templates=True)
    vox_sounds_path = generator.write(phrases, sexes)
    logger.info(f"Wrote DM code to {vox_sounds_path}")
    sounds_to_keep.add(os.path.abspath(str(vox_sounds_path)))

    # Generate vox_data.json
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    vox_data_path = os.path.join(DATA_DIR, "vox_data.json")
    with open(vox_data_path, "w") as f:
        data = {
            "version": 2,
            "compiled": time.time(),
            "voices": configured_voices,
            "words": collections.OrderedDict(
                {w.id: w.serialize() for w in phrases if "/" not in w.id}
            ),
        }
        json.dump(data, f, indent=2)
    logger.info(f"Wrote vox_data.json to {vox_data_path}")
    sounds_to_keep.add(os.path.abspath(vox_data_path))

    # Write manifest of generated files
    manifest_path = os.path.join(TEMP_DIR, "written.txt")
    with open(manifest_path, "w") as f:
        for filename in sorted(sounds_to_keep):
            f.write(f"{filename}\n")
    logger.info(f"Wrote manifest to {manifest_path}")

    # Check for orphan files
    orphan_count = 0
    for root, _, files in os.walk(DIST_DIR, topdown=False):
        for name in files:
            filename = os.path.abspath(os.path.join(root, name))
            if filename not in sounds_to_keep:
                orphan_count += 1
                if args["delete_orphans"]:
                    logger.warning(f"Removing {filename} (no longer defined)")
                    os.remove(filename)
                else:
                    logger.info(f"Orphan: {filename}")
    if orphan_count > 0:
        if args["delete_orphans"]:
            logger.info(f"Removed {orphan_count} orphan file(s)")
        else:
            logger.info(
                f"Found {orphan_count} orphan file(s). "
                "Use --delete-orphans to remove them."
            )

    logger.info("Generation complete")


def parse_args() -> dict:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generation script for ss13-vox."
    )
    parser.add_argument(
        "--threads",
        "-j",
        type=int,
        default=multiprocessing.cpu_count(),
        help="How many threads to use in ffmpeg.",
    )
    parser.add_argument(
        "--echo",
        "-e",
        action="store_true",
        default=False,
        help="Echo external commands to console.",
    )
    parser.add_argument(
        "--station",
        "-s",
        type=str,
        default="vg",
        help="The station, defaults to 'vg'.",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="vox_config.yaml",
        help="The configuration file to use, defaults to 'vox_config.yaml",
    )
    parser.add_argument(
        "--delete-orphans",
        action="store_true",
        default=False,
        help="Delete orphan files that are no longer defined in wordlists.",
    )
    return vars(parser.parse_args())


def main() -> None:
    """Entry point for the CLI."""
    logging.basicConfig(format=FORMAT, level=LOGLEVEL)
    args = parse_args()
    generate(args)


if __name__ == "__main__":
    main()
