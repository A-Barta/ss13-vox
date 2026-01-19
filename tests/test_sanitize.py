"""
Tests for ss13vox.sanitize module.

Tests input sanitization and LISP injection prevention.
"""

import pytest

from ss13vox.sanitize import (
    sanitize_tts_input,
    SanitizationError,
    SAFE_PATTERN,
    DANGEROUS_PATTERNS,
)


class TestSanitizeTTSInput:
    """Tests for sanitize_tts_input function."""

    def test_normal_text_unchanged(self):
        """Normal text should pass through unchanged."""
        assert sanitize_tts_input("Hello world") == "Hello world"
        assert sanitize_tts_input("Test 123") == "Test 123"
        assert sanitize_tts_input("Simple phrase") == "Simple phrase"

    def test_allowed_punctuation(self):
        """Allowed punctuation should pass through."""
        assert sanitize_tts_input("Hello, world!") == "Hello, world!"
        assert sanitize_tts_input("What?") == "What?"
        assert sanitize_tts_input("Stop.") == "Stop."
        assert sanitize_tts_input("It's fine") == "It's fine"

    def test_uppercase_preserved(self):
        """Case should be preserved."""
        assert sanitize_tts_input("HELLO World") == "HELLO World"

    def test_numbers_allowed(self):
        """Numbers should be allowed."""
        assert sanitize_tts_input("Level 5 alert") == "Level 5 alert"
        assert sanitize_tts_input("Code 2319") == "Code 2319"

    # LISP Injection Prevention Tests

    def test_parentheses_removed(self):
        """Parentheses should be removed (LISP injection)."""
        result = sanitize_tts_input("Hello (world)")
        assert "(" not in result
        assert ")" not in result

    def test_semicolon_removed(self):
        """Semicolons should be removed (LISP comment)."""
        result = sanitize_tts_input("Hello; world")
        assert ";" not in result

    def test_backtick_removed(self):
        """Backticks should be removed (LISP quote)."""
        result = sanitize_tts_input("Hello `world`")
        assert "`" not in result

    def test_dollar_sign_removed(self):
        """Dollar signs should be removed (variable expansion)."""
        result = sanitize_tts_input("$100 dollars")
        assert "$" not in result

    def test_backslash_removed(self):
        """Backslashes should be removed (escape sequences)."""
        result = sanitize_tts_input("Hello\\nworld")
        assert "\\" not in result

    def test_pipe_removed(self):
        """Pipes should be removed (command chaining)."""
        result = sanitize_tts_input("Hello | world")
        assert "|" not in result

    def test_ampersand_removed(self):
        """Ampersands should be removed (command chaining)."""
        result = sanitize_tts_input("Hello & world")
        assert "&" not in result

    def test_angle_brackets_removed(self):
        """Angle brackets should be removed (redirection)."""
        result = sanitize_tts_input("Hello <world>")
        assert "<" not in result
        assert ">" not in result

    def test_complex_injection_attempt(self):
        """Complex injection attempts should be sanitized or rejected."""
        # Injection without path separators (those are rejected)
        malicious = "(eval (read-line))"
        result = sanitize_tts_input(malicious)
        assert "(" not in result
        assert ")" not in result
        # Result should be "eval read-line" with dangerous chars stripped
        assert "eval" in result.lower() or result == ""

    def test_injection_with_path_rejected(self):
        """Injection attempts with path separators should be rejected."""
        malicious = "(system 'rm -rf /')"
        # Forward slash is not in safe pattern, so this should raise
        with pytest.raises(SanitizationError):
            sanitize_tts_input(malicious)

    def test_lisp_eval_injection(self):
        """LISP eval injection should be blocked."""
        malicious = "hello (eval (read))"
        result = sanitize_tts_input(malicious)
        assert "(" not in result
        assert ")" not in result

    # Length Validation Tests

    def test_max_length_enforced(self):
        """Text exceeding max_length should raise error."""
        with pytest.raises(SanitizationError, match="exceeds maximum"):
            sanitize_tts_input("x" * 1000, max_length=500)

    def test_max_length_exact(self):
        """Text at exactly max_length should pass."""
        text = "x" * 100
        result = sanitize_tts_input(text, max_length=100)
        assert result == text

    def test_max_length_one_over(self):
        """Text one character over max_length should fail."""
        with pytest.raises(SanitizationError):
            sanitize_tts_input("x" * 101, max_length=100)

    def test_default_max_length(self):
        """Very long text should fail with default max_length."""
        # Default is typically a reasonable limit
        long_text = "word " * 10000
        with pytest.raises(SanitizationError):
            sanitize_tts_input(long_text)

    # Edge Cases

    def test_empty_string_raises(self):
        """Empty string should raise SanitizationError."""
        with pytest.raises(SanitizationError, match="Empty"):
            sanitize_tts_input("")

    def test_whitespace_only_raises(self):
        """Whitespace-only string should raise after sanitization."""
        with pytest.raises(SanitizationError):
            sanitize_tts_input("   ")

    def test_multiple_spaces_collapsed(self):
        """Multiple spaces should be collapsed to single space."""
        result = sanitize_tts_input("hello  world")
        assert result == "hello world"

    def test_newlines_removed(self):
        """Newlines should be removed or converted."""
        result = sanitize_tts_input("hello\nworld")
        assert "\n" not in result

    def test_tabs_removed(self):
        """Tabs should be removed or converted."""
        result = sanitize_tts_input("hello\tworld")
        assert "\t" not in result

    def test_unicode_handling(self):
        """Unicode characters should be handled safely."""
        # Depending on implementation, may be stripped or kept
        result = sanitize_tts_input("Hello")
        # Should not raise an error at minimum
        assert isinstance(result, str)


class TestSafePattern:
    """Tests for SAFE_PATTERN regex."""

    def test_lowercase_letters_match(self):
        """All lowercase letters should match."""
        for c in "abcdefghijklmnopqrstuvwxyz":
            assert SAFE_PATTERN.match(c)

    def test_uppercase_letters_match(self):
        """All uppercase letters should match."""
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert SAFE_PATTERN.match(c)

    def test_digits_match(self):
        """All digits should match."""
        for c in "0123456789":
            assert SAFE_PATTERN.match(c)

    def test_space_matches(self):
        """Space should match (in context)."""
        assert SAFE_PATTERN.match("a b")

    def test_basic_punctuation_matches(self):
        """Basic punctuation should match."""
        assert SAFE_PATTERN.match("Hello, world!")
        assert SAFE_PATTERN.match("What?")
        assert SAFE_PATTERN.match("It's fine.")

    def test_dangerous_chars_rejected(self):
        """Dangerous characters should NOT match."""
        dangerous = "()`;$\\|&<>{}"
        for c in dangerous:
            assert not SAFE_PATTERN.match(c)


class TestDangerousPatterns:
    """Tests for DANGEROUS_PATTERNS list."""

    def test_parentheses_dangerous(self):
        """Parentheses should be in dangerous patterns."""
        patterns_str = " ".join(DANGEROUS_PATTERNS)
        assert "(" in patterns_str or "\\(" in patterns_str
        assert ")" in patterns_str or "\\)" in patterns_str

    def test_semicolon_dangerous(self):
        """Semicolon should be in dangerous patterns."""
        assert any(";" in p for p in DANGEROUS_PATTERNS)

    def test_backtick_dangerous(self):
        """Backtick should be in dangerous patterns."""
        assert any("`" in p for p in DANGEROUS_PATTERNS)


class TestSanitizationError:
    """Tests for SanitizationError exception."""

    def test_inherits_from_exception(self):
        """SanitizationError should be an Exception."""
        assert issubclass(SanitizationError, Exception)

    def test_message_preserved(self):
        """Error message should be preserved."""
        try:
            raise SanitizationError("Test message")
        except SanitizationError as e:
            assert "Test message" in str(e)
