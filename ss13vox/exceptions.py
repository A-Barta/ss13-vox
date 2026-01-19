"""Custom exceptions for SS13-VOX.

This module defines a hierarchy of exceptions for clean error handling
throughout the codebase, replacing sys.exit() calls and bare assertions.
"""


class VoxError(Exception):
    """Base exception for all SS13-VOX errors.

    All custom exceptions in this package inherit from VoxError,
    allowing callers to catch all VOX-related errors with a single
    except clause if desired.
    """

    pass


class ConfigError(VoxError):
    """Configuration file errors.

    Raised when:
    - Config file not found
    - Invalid YAML syntax
    - Missing required config keys
    - Invalid config values
    """

    pass


class PronunciationError(VoxError):
    """Lexicon and phoneme errors.

    Raised when:
    - Invalid phoneme in lexicon entry
    - Malformed pronunciation definition
    """

    pass


class AudioGenerationError(VoxError):
    """Audio synthesis and processing failures.

    Raised when:
    - External command (text2wave, sox, ffmpeg, oggenc) fails
    - Expected output file not created
    - Audio metadata extraction fails
    """

    pass


class ValidationError(VoxError):
    """Input validation failures.

    Raised when:
    - Invalid duration value
    - Duplicate phrase IDs
    - Invalid voice configuration
    - Missing required data
    """

    pass
