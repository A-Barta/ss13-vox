from enum import Flag
import sys
import os

import logging
import argparse
import multiprocessing

from yaml import safe_load
from yaml import YAMLError

from ss13vox.voice import EVoiceSex, SFXVoice, USSLTFemale, Voice, VoiceRegistry
from ss13vox.pronunciation import ParseLexiconText
from ss13vox.phrase import EPhraseFlags, FileData, ParsePhraseListFrom, Phrase

FORMAT = "%(levelname)s --- %(message)s"
# LOGLEVEL = logging.INFO
LOGLEVEL = logging.DEBUG

logging.basicConfig(format=FORMAT, level=LOGLEVEL)
logger = logging.getLogger("AB Main")

TEMP_DIR = "tmp"
DIST_DIR = "dist"
DATA_DIR = os.path.join(DIST_DIR, "data")
voices = []
vox_sounds_path = ""
configFile = "config.yml"
pathConfigFile = "paths.yml"


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


def main(args):
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
    # vox_sounds_path = config["paths"][station]["vox_sounds"]["path"]
    # templatefile = config["paths"][station]["vox_sounds"]["template"]
    # vox_data_path = config["paths"][station]["vox_data"]

    voice_assignments = {}
    all_voices = []
    default_voice: Voice = VoiceRegistry.Get(USSLTFemale.ID)
    default_voice.assigned_sex
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

    logger.info(f"List of all voices found: {[voice.ID for voice in all_voices]}")
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

    # soundsToKeep = set()
    # for sound in OTHERSOUNDS:
    #     soundsToKeep.add(os.path.join(DIST_DIR, sound + ".ogg"))

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
        for voice in phrase_voices:
            voice_assignments[voice.SEX].append(phrase)

    for voice in all_voices:
        logger.info(f"ID = {voice.ID}, ass_sex = {voice.assigned_sex}")
    #     DumpLexiconScript(
    #         voice.FESTIVAL_VOICE_ID, lexicon.values(), "tmp/VOXdict.lisp"
    #     )
        for phrase in voice_assignments[voice.SEX]:
            logger.warning(f"{phrase}")
    #         GenerateForWord(phrase, voice, soundsToKeep, args)
    #         sexes = set()
    #         for vk, fd in phrase.files.items():
    #             soundsToKeep.add(
    #                 os.path.abspath(os.path.join(DIST_DIR, fd.filename))
    #             )

    # jenv = jinja2.Environment(
    #     loader=jinja2.FileSystemLoader(["./templates"])
    # )
    # jenv.add_extension("jinja2.ext.do")  # {% do ... %}
    # templ = jenv.get_template(templatefile)
    # with log.info("Writing sound list to %s...", vox_sounds_path):
    #     os_utils.ensureDirExists(os.path.dirname(vox_sounds_path))
    #     assetcache = {}
    #     sound2id = {}
    #     with open(vox_sounds_path, "w") as f:
    #         sexes = {
    #             "fem": [],
    #             "mas": [],
    #             "default": [],
    #             # 'sfx': [],
    #         }
    #         for p in phrases:
    #             for k in p.files.keys():
    #                 assetcache[p.getAssetKey(k)] = p.files[k].filename
    #                 sound2id[p.files[k].filename] = p.getAssetKey(k)
    #             if p.hasFlag(EPhraseFlags.NOT_VOX):
    #                 continue
    #             for k in p.files.keys():
    #                 if p.hasFlag(EPhraseFlags.SFX):
    #                     for sid in ("fem", "mas"):
    #                         if p not in sexes[sid]:
    #                             sexes[sid].append(p)
    #                 else:
    #                     sexes[k].append(p)
    #         f.write(
    #             templ.render(
    #                 InitClass=InitClass,
    #                 SEXES=sexes,
    #                 ASSETCACHE=assetcache,
    #                 SOUND2ID=sound2id,
    #                 PHRASES=[
    #                     p
    #                     for p in phrases
    #                     if not p.hasFlag(EPhraseFlags.NOT_VOX)
    #                 ],
    #             )
    #         )
    # soundsToKeep.add(os.path.abspath(vox_sounds_path))

    # os_utils.ensureDirExists(DATA_DIR)
    # with open(os.path.join(DATA_DIR, "vox_data.json"), "w") as f:
    #     data = {
    #         "version": 2,
    #         "compiled": time.time(),
    #         "voices": configured_voices,
    #         "words": collections.OrderedDict(
    #             {w.id: w.serialize() for w in phrases if "/" not in w.id}
    #         ),
    #     }
    #     json.dump(data, f, indent=2)
    # soundsToKeep.add(
    #     os.path.abspath(os.path.join(DATA_DIR, "vox_data.json"))
    # )

    # with open("tmp/written.txt", "w") as f:
    #     for filename in sorted(soundsToKeep):
    #         f.write(f"{filename}\n")

    # for root, _, files in os.walk(DIST_DIR, topdown=False):
    #     for name in files:
    #         filename = os.path.abspath(os.path.join(root, name))
    #         if filename not in soundsToKeep:
    #             log.warning(
    #                 "Removing {0} (no longer defined)".format(filename)
    #             )
    #             os.remove(filename)

    ####


if __name__ == "__main__":
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
        default="abconfig.yml",
        help="The configuration file to use, defaults to 'abconfig.yml",
    )
    args = vars(parser.parse_args())  # I prefer dictionaries

    main(args)
