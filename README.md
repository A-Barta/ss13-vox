# SS13-VOX

A fork of [N3X15/ss13-vox](https://github.com/N3X15/ss13-vox) - Text-to-Speech announcement system for Space Station 13, inspired by Half-Life's announcement system.

## Requirements

System packages (install via your distribution's package manager):

- `festival` - Text-to-speech synthesis
- `sox` - Audio processing
- `vorbis-tools` - OGG encoding (oggenc)
- `ffmpeg` - Audio conversion

On Ubuntu/Debian:
```bash
sudo apt install festival sox vorbis-tools ffmpeg
```

You'll also need Festival voices. The nitech_us voices are recommended:
- `nitech_us_clb_arctic_hts` (female)
- `nitech_us_rms_arctic_hts` (male)

## Installation

```bash
# Create and activate a virtual environment
python -m venv vox-venv
source vox-venv/bin/activate

# Install the package
pip install -e .

# For daemon/web UI support
pip install -e ".[daemon]"
```

After installing, deactivate and reactivate the venv (or open a new shell) to ensure the `ss13-vox` command is available.

## Usage

### Generate VOX Audio

```bash
ss13-vox
```

This will:
1. Parse wordlists from `wordlists/`
2. Generate speech audio using Festival TTS
3. Apply audio effects (echo, reverb, compression) via SoX
4. Encode to OGG Vorbis format
5. Output files to `dist/sound/vox_{fem,mas}/`
6. Generate DM code and metadata

### Configuration

Edit `vox_config.yaml` to configure:
- Target codebase (`vg` or `tg`)
- Voice assignments for each sex
- Wordlist files to process
- Phrase overrides and flags

### Build Web UI (Optional)

If you need the browser-based word selector:

```bash
./build_web.sh
```

Requires Node.js and yarn. Compiles CoffeeScript and SCSS to `dist/html/`.

## Wordlist Syntax

Edit files in `wordlists/` to add words:

```
apple                           # Simple word (TTS synthesized)
word_id = phrase to synthesize  # Phrase with custom ID
@samples/path.wav               # External sound effect
&songs/filename.xml             # Song (singing mode)
## Category Name                # Section header
# Comment                       # Comment
```

## Voice Options

| ID | Sex | Notes |
|----|-----|-------|
| `us-clb` | F | Default female, US accent, clear |
| `us-rms` | M | Default male, US accent, DECTalk-like |
| `us-slt` | F | US female, midwestern accent (buggy) |

Configure in `vox_config.yaml` under `voices:`.

## Fixing Pronunciation

If a word is mispronounced, add it to `lexicon.txt` using CMU phoneme notation. See `LEXICON-README.md` for phoneme reference.

## Customizing DM Output

Edit templates in `templates/` (`vglist.jinja` or `tglist.jinja`) to change the generated DM code format.

## Utility Functions

The package includes utility functions accessible via Python:

```python
from ss13vox.utils import organize_file, generate_allstar

# Organize a wordlist file (sort entries alphabetically)
organize_file("wordlists/common.txt")

# Generate the All Star song using VOX TTS
generate_allstar("allstar.mp3")
```

## Development

```bash
# Install dev dependencies
pip install pre-commit

# Run code quality checks
pre-commit run --all-files
```

Pre-commit runs: trailing-whitespace, check-json, flake8, black (79 char limit)
