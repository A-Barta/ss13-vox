"""
Command-line interface for SS13-VOX generation.

This module provides the main CLI entry point for generating TTS audio files.
The generation process is broken into discrete phases:
1. Configuration loading and validation
2. Voice setup and assignment
3. Phrase parsing from wordlists
4. Audio file generation
5. Code generation (DM files)
6. Output file management
"""

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
from dataclasses import dataclass, field

from .consts import (
    PRE_SOX_ARGS,
    RECOMPRESS_ARGS,
    SILENCE_PADDING_DURATION,
    VOX_DATA_VERSION,
)
from .config import load_config, config_to_dict, VoxConfig
from .voice import (
    EVoiceSex,
    SFXVoice,
    USSLTFemale,
    Voice,
    VoiceRegistry,
)
from .pronunciation import DumpLexiconScript, ParseLexiconText, Pronunciation
from .phrase import EPhraseFlags, FileData, ParsePhraseListFrom, Phrase
from .codegen import CodeGenConfig, get_generator
from .exceptions import AudioGenerationError, ConfigError, ValidationError

FORMAT = "%(levelname)s --- %(message)s"
LOGLEVEL = logging.DEBUG

TEMP_DIR = "tmp"
DIST_DIR = "dist"
DATA_DIR = os.path.join(DIST_DIR, "data")


@dataclass
class GenerationContext:
    """Holds shared state during the generation process."""

    args: dict
    station: str = ""
    config: dict = field(default_factory=dict)
    validated_config: VoxConfig | None = None

    # Voice configuration
    voices: list[Voice] = field(default_factory=list)
    all_voices: list[Voice] = field(default_factory=list)
    voice_assignments: dict[EVoiceSex, list[Phrase]] = field(
        default_factory=dict
    )
    configured_voices: dict[str, dict] = field(default_factory=dict)
    default_voice: Voice | None = None
    sfx_voice: SFXVoice | None = None

    # Paths
    preex_sound: str = ""
    nuvox_sound: str = ""
    lexicon_path: str = ""

    # Phrases
    phrases: list[Phrase] = field(default_factory=list)
    phrases_by_id: dict[str, Phrase] = field(default_factory=dict)
    lexicon: dict[str, Pronunciation] = field(default_factory=dict)

    # Output tracking
    sounds_to_keep: set[str] = field(default_factory=set)


logger = logging.getLogger("ss13vox")


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
        stderr_msg = (
            f"\nstderr: {result.stderr}"
            if capture_output and result.stderr
            else ""
        )
        raise AudioGenerationError(
            f"Command failed with code {result.returncode}: "
            f"{' '.join(command)}{stderr_msg}"
        )
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

    # Adjust duration for non-SFX (removes silence padding added by SoX)
    if (
        not phrase.hasFlag(EPhraseFlags.SFX)
        and fdata.duration > SILENCE_PADDING_DURATION
    ):
        fdata.duration -= SILENCE_PADDING_DURATION

    # Verify output files exist
    for command, expected_file in cmds:
        if not os.path.isfile(expected_file):
            raise AudioGenerationError(
                f"Expected output file '{expected_file}' was not created. "
                f"Command may have failed: {' '.join(command)}"
            )

    # Save cache
    with open(cachefile, "w") as f:
        json.dump(fdata.serialize(), f)

    commit_written()


# =============================================================================
# Generation Pipeline Functions
# =============================================================================


def _load_and_validate_config(ctx: GenerationContext) -> None:
    """Load and validate configuration from file."""
    ctx.station = ctx.args["station"]
    ctx.validated_config = load_config(ctx.args["config"])

    # Override codebase if --station is specified and different
    if ctx.station != ctx.validated_config.codebase:
        logger.info(
            f"Using station '{ctx.station}' "
            f"(config default: '{ctx.validated_config.codebase}')"
        )

    # Validate that the requested station exists in paths
    if ctx.station not in ctx.validated_config.paths:
        available = ", ".join(sorted(ctx.validated_config.paths.keys()))
        raise ConfigError(
            f"Station '{ctx.station}' not found in config paths. "
            f"Available: {available}"
        )

    # Convert to dict format for backward compatibility
    ctx.config = config_to_dict(ctx.validated_config, ctx.station)

    # Set sound paths
    ctx.preex_sound = ctx.config["paths"][ctx.station]["sound"]["old-vox"]
    ctx.nuvox_sound = ctx.config["paths"][ctx.station]["sound"]["new-vox"]


def _setup_voices(ctx: GenerationContext) -> None:
    """Configure voices from config settings."""
    ctx.default_voice = VoiceRegistry.Get(USSLTFemale.ID)
    ctx.sfx_voice = SFXVoice()

    for sex_id, voice_id in ctx.config["voices"].items():
        voice = VoiceRegistry.Get(voice_id)
        if not sex_id:
            raise ConfigError(f"Empty sex ID in voice config for '{voice_id}'")

        voice.assigned_sex = sex_id

        if sex_id in ("fem", "mas"):
            sex = EVoiceSex(sex_id)
            if voice.SEX != sex:
                raise ConfigError(
                    f"Voice '{voice_id}' has SEX={voice.SEX.value} but is "
                    f"assigned to '{sex_id}'"
                )
            ctx.voices.append(voice)

        ctx.voice_assignments[voice.SEX] = []
        ctx.all_voices.append(voice)
        ctx.configured_voices[sex_id] = voice.serialize()

    logger.info(
        f"List of all voices found: {[voice.ID for voice in ctx.all_voices]}"
    )
    logger.info(f"List of all voices configured: {ctx.configured_voices}")


def _ensure_directories() -> None:
    """Ensure required directories exist."""
    logger.info(f"Checking that {DATA_DIR} exists")
    if not os.path.exists(DATA_DIR):
        logger.info(f"{DATA_DIR} not found, creating it")
        os.makedirs(DATA_DIR)
        logger.info("Success")
    else:
        logger.info(f"{DATA_DIR} exists, moving on")

    logger.info(f"Checking that {TEMP_DIR} exists")
    if not os.path.exists(TEMP_DIR):
        logger.info(f"{TEMP_DIR} not found, creating it")
        os.makedirs(TEMP_DIR)


def _parse_phrases(ctx: GenerationContext) -> None:
    """Parse phrases from wordlist files and check for duplicates."""
    ctx.lexicon = ParseLexiconText("lexicon.txt")
    max_wordlen = ctx.config["max-wordlen"]
    duplicates = []

    for filename in ctx.config["phrasefiles"]:
        for p in ParsePhraseListFrom(filename):
            p.wordlen = min(max_wordlen, p.wordlen)
            if p.id in ctx.phrases_by_id:
                duplicated = ctx.phrases_by_id[p.id]
                duplicates.append(
                    f"Duplicate phrase '{p.id}' in "
                    f"{p.deffile}:{p.defline} (first seen in "
                    f"{duplicated.deffile}:{duplicated.defline})"
                )
                continue
            ctx.phrases.append(p)
            ctx.phrases_by_id[p.id] = p

    if duplicates:
        raise ValidationError(
            f"Found {len(duplicates)} duplicate phrase(s):\n"
            + "\n".join(f"  - {d}" for d in duplicates)
        )

    ctx.phrases.sort(key=lambda x: x.id)


def _apply_overrides_and_assign_voices(ctx: GenerationContext) -> None:
    """Apply phrase overrides and assign voices to phrases."""
    overrides = ctx.config["overrides"]

    for phrase in ctx.phrases:
        if phrase.id in overrides:
            logger.debug(f"Phrase {phrase} is in overrides")
            phrase.fromOverrides(overrides.get(phrase.id))

        phrase_voices = [ctx.default_voice]

        if "/" in phrase.id:
            # If the ID is a path, treat it as filename
            phrase.filename = f"{phrase.id}.ogg"
            phrase_voices = [ctx.default_voice]
        elif phrase.hasFlag(flag=EPhraseFlags.OLD_VOX):
            phrase.filename = ctx.preex_sound
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
            continue  # Skip voice assignment for OLD_VOX
        elif phrase.hasFlag(EPhraseFlags.SFX):
            phrase.filename = ctx.nuvox_sound
            phrase_voices = [ctx.sfx_voice]
        else:
            # Regular phrase - use new-vox path template
            phrase.filename = ctx.nuvox_sound

        for voice in phrase_voices:
            ctx.voice_assignments[voice.SEX].append(phrase)


def _setup_lexicon(ctx: GenerationContext) -> None:
    """Write lexicon script for Festival TTS."""
    ctx.lexicon_path = os.path.join(TEMP_DIR, "VOXdict.lisp")
    DumpLexiconScript("", list(ctx.lexicon.values()), ctx.lexicon_path)
    logger.info(f"Wrote lexicon script to {ctx.lexicon_path}")


def _generate_audio_files(ctx: GenerationContext) -> None:
    """Generate audio files for all phrases."""
    for voice in ctx.all_voices:
        logger.info(f"ID = {voice.ID}, assigned_sex = {voice.assigned_sex}")
        for phrase in ctx.voice_assignments[voice.SEX]:
            generate_for_word(
                phrase, voice, ctx.sounds_to_keep, ctx.lexicon_path, ctx.args
            )
            for fd in phrase.files.values():
                ctx.sounds_to_keep.add(
                    os.path.abspath(os.path.join(DIST_DIR, fd.filename))
                )


def _build_sexes_dict(ctx: GenerationContext) -> dict[str, list[Phrase]]:
    """Build sexes dict for code generation."""
    sexes: dict[str, list[Phrase]] = {"fem": [], "mas": []}

    for p in ctx.phrases:
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

    return sexes


def _generate_dm_code(
    ctx: GenerationContext, sexes: dict[str, list[Phrase]]
) -> None:
    """Generate DM code files."""
    codegen_config = CodeGenConfig(
        template_dir=pathlib.Path("templates"),
        output_dir=pathlib.Path(DIST_DIR),
    )
    generator = get_generator(ctx.station, codegen_config, use_templates=True)
    vox_sounds_path = generator.write(ctx.phrases, sexes)
    logger.info(f"Wrote DM code to {vox_sounds_path}")
    ctx.sounds_to_keep.add(os.path.abspath(str(vox_sounds_path)))


def _write_vox_data(ctx: GenerationContext) -> None:
    """Generate vox_data.json manifest."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    vox_data_path = os.path.join(DATA_DIR, "vox_data.json")
    with open(vox_data_path, "w") as f:
        data = {
            "version": VOX_DATA_VERSION,
            "compiled": time.time(),
            "voices": ctx.configured_voices,
            "words": collections.OrderedDict(
                {w.id: w.serialize() for w in ctx.phrases if "/" not in w.id}
            ),
        }
        json.dump(data, f, indent=2)

    logger.info(f"Wrote vox_data.json to {vox_data_path}")
    ctx.sounds_to_keep.add(os.path.abspath(vox_data_path))


def _write_manifest(ctx: GenerationContext) -> None:
    """Write manifest of generated files."""
    manifest_path = os.path.join(TEMP_DIR, "written.txt")
    with open(manifest_path, "w") as f:
        for filename in sorted(ctx.sounds_to_keep):
            f.write(f"{filename}\n")
    logger.info(f"Wrote manifest to {manifest_path}")


def _handle_orphan_files(ctx: GenerationContext) -> None:
    """Check for and optionally delete orphan files."""
    orphan_count = 0

    for root, _, files in os.walk(DIST_DIR, topdown=False):
        for name in files:
            filename = os.path.abspath(os.path.join(root, name))
            if filename not in ctx.sounds_to_keep:
                orphan_count += 1
                if ctx.args["delete_orphans"]:
                    logger.warning(f"Removing {filename} (no longer defined)")
                    os.remove(filename)
                else:
                    logger.info(f"Orphan: {filename}")

    if orphan_count > 0:
        if ctx.args["delete_orphans"]:
            logger.info(f"Removed {orphan_count} orphan file(s)")
        else:
            logger.info(
                f"Found {orphan_count} orphan file(s). "
                "Use --delete-orphans to remove them."
            )


# =============================================================================
# Main Entry Point
# =============================================================================


def generate(args: dict) -> None:
    """
    Main generation orchestrator.

    This function coordinates the entire TTS generation pipeline:
    1. Load and validate configuration
    2. Set up voices
    3. Parse phrases from wordlists
    4. Apply overrides and assign voices
    5. Generate audio files
    6. Generate DM code
    7. Write output manifests
    8. Handle orphan files
    """
    ctx = GenerationContext(args=args)

    logger.info("Started voice generation")
    for _k, _v in args.items():
        logger.debug(f"Using argument {_k}={_v}")

    # Phase 1: Configuration
    _load_and_validate_config(ctx)
    _setup_voices(ctx)
    _ensure_directories()

    # Phase 2: Phrase parsing
    _parse_phrases(ctx)
    _apply_overrides_and_assign_voices(ctx)
    _setup_lexicon(ctx)

    # Phase 3: Audio generation
    _generate_audio_files(ctx)

    # Phase 4: Code generation and output
    sexes = _build_sexes_dict(ctx)
    _generate_dm_code(ctx, sexes)
    _write_vox_data(ctx)
    _write_manifest(ctx)

    # Phase 5: Cleanup
    _handle_orphan_files(ctx)

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
