"""Input sanitization for Festival TTS to prevent LISP injection attacks."""

import re

# Whitelist approach - only allow safe characters for TTS
# Allows: letters, numbers, spaces, basic punctuation
SAFE_PATTERN = re.compile(r"^[a-zA-Z0-9\s\.,!\?'\"-]+$")

# Blacklist of dangerous patterns that could be used for LISP injection
# Festival's TTS engine interprets LISP, so these are dangerous
DANGEROUS_PATTERNS = [
    r"\(",  # LISP parentheses - function calls
    r"\)",  # LISP parentheses - function calls
    r";",  # Comment/command separator
    r"`",  # Backtick - can be used for evaluation
    r"\$",  # Variable expansion
    r"\\",  # Escape sequences
    r"\|",  # Pipe - potential command chaining
    r"&",  # Background execution
    r"<",  # Redirection
    r">",  # Redirection
]


class SanitizationError(ValueError):
    """Raised when input fails sanitization checks."""

    pass


def sanitize_tts_input(
    text: str,
    max_length: int = 500,
    strip_dangerous: bool = True,
) -> str:
    """
    Sanitize text input for Festival TTS.

    Args:
        text: The input text to sanitize
        max_length: Maximum allowed length (default 500 characters)
        strip_dangerous: If True, remove dangerous characters.
                        If False, raise an error when found.

    Returns:
        Sanitized text safe for Festival TTS

    Raises:
        SanitizationError: If text is empty, too long, or contains
                          invalid characters (when strip_dangerous=False)
    """
    if not text:
        raise SanitizationError("Empty text input")

    if not isinstance(text, str):
        raise SanitizationError(f"Expected string, got {type(text).__name__}")

    # Check length before processing
    if len(text) > max_length:
        raise SanitizationError(
            f"Text exceeds maximum length of {max_length} characters "
            f"(got {len(text)})"
        )

    # Remove or reject dangerous patterns
    sanitized = text
    for pattern in DANGEROUS_PATTERNS:
        if strip_dangerous:
            sanitized = re.sub(pattern, "", sanitized)
        elif re.search(pattern, sanitized):
            raise SanitizationError(
                f"Text contains dangerous character matching pattern: {pattern}"
            )

    # Normalize whitespace (collapse multiple spaces, strip edges)
    sanitized = " ".join(sanitized.split())

    # Final validation against whitelist
    if not SAFE_PATTERN.match(sanitized):
        # Find the offending characters for a helpful error message
        unsafe_chars = set()
        for char in sanitized:
            if not re.match(r"[a-zA-Z0-9\s\.,!\?'\"-]", char):
                unsafe_chars.add(repr(char))
        if unsafe_chars:
            raise SanitizationError(
                f"Text contains invalid characters: {', '.join(sorted(unsafe_chars))}"
            )
        raise SanitizationError("Text contains invalid characters")

    if not sanitized:
        raise SanitizationError("Text is empty after sanitization")

    return sanitized
