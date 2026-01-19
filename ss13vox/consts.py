"""Constants for SS13-VOX audio processing.

This module contains all magic numbers and configuration constants used
throughout the audio generation pipeline.
"""

# =============================================================================
# Audio Duration Constants
# =============================================================================

# SoX adds silence padding to the end of audio files. This constant represents
# the duration of that padding in seconds, which must be subtracted from the
# reported duration to get the actual speech duration.
SILENCE_PADDING_DURATION = 10.0

# =============================================================================
# SoX Effect Parameters
# =============================================================================

# Chorus effect parameters - adds harmonics to make voice sound less monotone
# See: https://sox.sourceforge.net/sox.html (chorus effect)
SOX_CHORUS_GAIN_IN = "0.7"  # Input gain (0-1)
SOX_CHORUS_GAIN_OUT = "0.9"  # Output gain (0-1)
SOX_CHORUS_DELAY_MS = "55"  # Delay in milliseconds
SOX_CHORUS_DECAY = "0.4"  # Decay factor
SOX_CHORUS_SPEED = "0.25"  # Modulation speed in Hz
SOX_CHORUS_DEPTH = "2"  # Modulation depth in ms
SOX_CHORUS_SHAPE = "-t"  # Triangle wave modulation

# Phaser effect parameters - adds digital/spacey quality
# See: https://sox.sourceforge.net/sox.html (phaser effect)
SOX_PHASER_GAIN_IN = "0.9"  # Input gain
SOX_PHASER_GAIN_OUT = "0.85"  # Output gain
SOX_PHASER_DELAY_MS = "4"  # Base delay in ms
SOX_PHASER_DECAY = "0.23"  # Decay factor
SOX_PHASER_SPEED = "1.3"  # Modulation speed in Hz
SOX_PHASER_SHAPE = "-s"  # Sinusoidal modulation

# Echo effect parameters - adds hallway/reverb quality
# See: https://sox.sourceforge.net/sox.html (echos effect)
SOX_ECHO_GAIN_IN = "0.3"  # Input gain
SOX_ECHO_GAIN_OUT = "0.5"  # Output gain
SOX_ECHO_DELAY_1_MS = "100"  # First echo delay in ms
SOX_ECHO_DECAY_1 = "0.25"  # First echo decay
SOX_ECHO_DELAY_2_MS = "10"  # Second echo delay in ms
SOX_ECHO_DECAY_2 = "0.25"  # Second echo decay

# =============================================================================
# FFmpeg Recompression Arguments
# =============================================================================

# Direct from TG's PR (https://github.com/tgstation/tgstation/pull/36492)
# May bump up quality and rate slightly...
RECOMPRESS_ARGS = [
    # Audio Codec
    "-c:a",
    "libvorbis",
    # Force to mono (should already be, since festival outputs mono...)
    "-ac",
    "1",
    # Sampling rate in Hz. TG uses 16kHz.
    "-ar",
    "16000",
    # Audio quality [0,9]. TG uses 0.
    "-q:a",
    "0",
    # Playback speed
    "-speed",
    "0",
    # Number of threads to use.
    # This works OK on my laptop, but you may need fewer
    # Now specified in -j.
    # '-threads', '8',
    # Force overwrite
    "-y",
]

# Have to do the trimming seperately.
PRE_SOX_ARGS = "trim 0 -0.1"  # Trim off last 0.2s.
