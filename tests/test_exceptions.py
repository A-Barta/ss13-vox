"""
Tests for ss13vox.exceptions module.

Tests the exception hierarchy.
"""

import pytest

from ss13vox.exceptions import (
    VoxError,
    ConfigError,
    PronunciationError,
    AudioGenerationError,
    ValidationError,
)


class TestVoxError:
    """Tests for base VoxError exception."""

    def test_is_exception(self):
        """Test that VoxError is an Exception."""
        assert issubclass(VoxError, Exception)

    def test_can_be_raised(self):
        """Test that VoxError can be raised."""
        with pytest.raises(VoxError):
            raise VoxError("Test error")

    def test_message_preserved(self):
        """Test that error message is preserved."""
        try:
            raise VoxError("Test message")
        except VoxError as e:
            assert "Test message" in str(e)

    def test_can_be_caught_as_exception(self):
        """Test that VoxError can be caught as Exception."""
        with pytest.raises(Exception):
            raise VoxError("Test")


class TestConfigError:
    """Tests for ConfigError exception."""

    def test_inherits_from_vox_error(self):
        """Test that ConfigError inherits from VoxError."""
        assert issubclass(ConfigError, VoxError)

    def test_can_be_raised(self):
        """Test that ConfigError can be raised."""
        with pytest.raises(ConfigError):
            raise ConfigError("Config error")

    def test_can_be_caught_as_vox_error(self):
        """Test that ConfigError can be caught as VoxError."""
        with pytest.raises(VoxError):
            raise ConfigError("Config error")

    def test_message_preserved(self):
        """Test that error message is preserved."""
        try:
            raise ConfigError("Missing field: codebase")
        except ConfigError as e:
            assert "Missing field" in str(e)
            assert "codebase" in str(e)


class TestPronunciationError:
    """Tests for PronunciationError exception."""

    def test_inherits_from_vox_error(self):
        """Test that PronunciationError inherits from VoxError."""
        assert issubclass(PronunciationError, VoxError)

    def test_can_be_raised(self):
        """Test that PronunciationError can be raised."""
        with pytest.raises(PronunciationError):
            raise PronunciationError("Invalid phoneme")

    def test_can_be_caught_as_vox_error(self):
        """Test that PronunciationError can be caught as VoxError."""
        with pytest.raises(VoxError):
            raise PronunciationError("Invalid phoneme")

    def test_typical_usage(self):
        """Test typical error message format."""
        phoneme = "XYZ"
        word = "test"
        try:
            raise PronunciationError(
                f"Invalid phoneme '{phoneme}' in lexicon entry '{word}'"
            )
        except PronunciationError as e:
            assert "XYZ" in str(e)
            assert "test" in str(e)


class TestAudioGenerationError:
    """Tests for AudioGenerationError exception."""

    def test_inherits_from_vox_error(self):
        """Test that AudioGenerationError inherits from VoxError."""
        assert issubclass(AudioGenerationError, VoxError)

    def test_can_be_raised(self):
        """Test that AudioGenerationError can be raised."""
        with pytest.raises(AudioGenerationError):
            raise AudioGenerationError("Command failed")

    def test_can_be_caught_as_vox_error(self):
        """Test that AudioGenerationError can be caught as VoxError."""
        with pytest.raises(VoxError):
            raise AudioGenerationError("Command failed")

    def test_typical_usage(self):
        """Test typical error message format."""
        cmd = "festival"
        code = 1
        try:
            raise AudioGenerationError(
                f"Command '{cmd}' failed with exit code {code}"
            )
        except AudioGenerationError as e:
            assert "festival" in str(e)
            assert "1" in str(e)


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_inherits_from_vox_error(self):
        """Test that ValidationError inherits from VoxError."""
        assert issubclass(ValidationError, VoxError)

    def test_can_be_raised(self):
        """Test that ValidationError can be raised."""
        with pytest.raises(ValidationError):
            raise ValidationError("Invalid input")

    def test_can_be_caught_as_vox_error(self):
        """Test that ValidationError can be caught as VoxError."""
        with pytest.raises(VoxError):
            raise ValidationError("Invalid input")

    def test_typical_usage_duration(self):
        """Test typical error for invalid duration."""
        duration = -1.0
        try:
            raise ValidationError(
                f"Invalid audio duration: {duration} (must be positive)"
            )
        except ValidationError as e:
            assert "-1.0" in str(e)
            assert "positive" in str(e)

    def test_typical_usage_duplicate(self):
        """Test typical error for duplicate phrase."""
        phrase_id = "hello"
        try:
            raise ValidationError(f"Duplicate phrase ID: {phrase_id}")
        except ValidationError as e:
            assert "hello" in str(e)
            assert "Duplicate" in str(e)


class TestExceptionHierarchy:
    """Tests for the overall exception hierarchy."""

    def test_all_inherit_from_vox_error(self):
        """Test that all custom exceptions inherit from VoxError."""
        exceptions = [
            ConfigError,
            PronunciationError,
            AudioGenerationError,
            ValidationError,
        ]
        for exc in exceptions:
            assert issubclass(exc, VoxError)

    def test_can_catch_all_with_vox_error(self):
        """Test that all exceptions can be caught with VoxError."""
        exceptions = [
            ConfigError("config"),
            PronunciationError("pronunciation"),
            AudioGenerationError("audio"),
            ValidationError("validation"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except VoxError:
                pass  # Should catch all
            except Exception:
                pytest.fail(f"{type(exc).__name__} not caught by VoxError")

    def test_specific_catch_preferred(self):
        """Test that specific exceptions can be caught specifically."""
        try:
            raise ConfigError("test")
        except ConfigError:
            pass  # Correctly caught
        except VoxError:
            pytest.fail("Should have been caught by ConfigError first")

    def test_exceptions_are_distinct(self):
        """Test that exception types are distinct."""
        exceptions = [
            ConfigError,
            PronunciationError,
            AudioGenerationError,
            ValidationError,
        ]

        # Each should be different
        for i, exc1 in enumerate(exceptions):
            for j, exc2 in enumerate(exceptions):
                if i != j:
                    assert exc1 is not exc2
                    # One should not be subclass of the other (except VoxError)
                    assert not issubclass(exc1, exc2) or exc2 is VoxError
