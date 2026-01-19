"""
Tests for ss13vox.phrase module.

Tests phrase parsing, flags, file data, and serialization.
"""

import pytest

from ss13vox.phrase import (
    EPhraseFlags,
    FileData,
    Phrase,
    ParsePhraseListFrom,
    _fixChars,
)
from ss13vox.exceptions import ValidationError


class TestEPhraseFlags:
    """Tests for EPhraseFlags enum."""

    def test_flag_values(self):
        """Verify flag values are powers of 2 for bitwise operations."""
        assert EPhraseFlags.NONE == 0
        assert EPhraseFlags.OLD_VOX == 1
        assert EPhraseFlags.SFX == 2
        assert EPhraseFlags.NOT_VOX == 4
        assert EPhraseFlags.NO_PROCESS == 8
        assert EPhraseFlags.NO_TRIM == 16
        assert EPhraseFlags.SING == 32

    def test_flag_combination(self):
        """Test combining multiple flags."""
        combined = EPhraseFlags.SFX | EPhraseFlags.NO_PROCESS
        assert combined & EPhraseFlags.SFX == EPhraseFlags.SFX
        assert combined & EPhraseFlags.NO_PROCESS == EPhraseFlags.NO_PROCESS
        assert combined & EPhraseFlags.NO_TRIM == EPhraseFlags.NONE


class TestFixChars:
    """Tests for _fixChars helper function."""

    def test_valid_chars_unchanged(self):
        """Valid characters should pass through unchanged."""
        assert _fixChars("hello_world") == "hello_world"
        assert _fixChars("Test123") == "Test123"
        assert _fixChars("file.ogg") == "file.ogg"

    def test_invalid_chars_replaced(self):
        """Invalid characters should be replaced with underscore."""
        assert _fixChars("hello world") == "hello_world"
        assert _fixChars("test@file") == "test_file"
        assert _fixChars("name#1") == "name_1"

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert _fixChars("") == ""


class TestFileData:
    """Tests for FileData class."""

    def test_default_values(self):
        """Test default initialization values."""
        fd = FileData()
        assert fd.filename == ""
        assert fd.voice == ""
        assert fd.checksum == ""
        assert fd.duration == 0.0
        assert fd.size == 0

    def test_from_json(self):
        """Test parsing from ffprobe JSON output."""
        fd = FileData()
        json_data = {
            "format": {
                "size": "12345",
                "duration": "2.5",
            }
        }
        fd.fromJSON(json_data)
        assert fd.size == 12345
        assert fd.duration == 2.5

    def test_from_json_invalid_duration(self):
        """Test that zero/negative duration raises ValidationError."""
        fd = FileData()
        json_data = {
            "format": {
                "size": "100",
                "duration": "0.0",
            }
        }
        with pytest.raises(ValidationError, match="Invalid audio duration"):
            fd.fromJSON(json_data)

    def test_serialize_deserialize(self):
        """Test round-trip serialization."""
        fd = FileData()
        fd.filename = "test.ogg"
        fd.voice = "fem"
        fd.checksum = "abc123"
        fd.duration = 1.5
        fd.size = 1000

        serialized = fd.serialize()
        assert serialized["filename"] == "test.ogg"
        assert serialized["voice"] == "fem"
        assert serialized["checksum"] == "abc123"
        assert serialized["duration"] == 1.5
        assert serialized["size"] == 1000

        fd2 = FileData()
        fd2.deserialize(serialized)
        assert fd2.filename == fd.filename
        assert fd2.voice == fd.voice
        assert fd2.checksum == fd.checksum
        assert fd2.duration == fd.duration
        assert fd2.size == fd.size

    def test_to_byond(self):
        """Test BYOND list format output."""
        fd = FileData()
        fd.filename = "test.ogg"
        fd.checksum = "abc123"
        fd.duration = 1.5
        fd.voice = "fem"
        fd.size = 1000

        byond = fd.toBYOND()
        assert '"filename" = "test.ogg"' in byond
        assert '"checksum" = "abc123"' in byond
        assert '"duration" = 15' in byond  # 1.5 * 10 = 15 deciseconds
        assert '"voice" = "fem"' in byond
        assert '"size" = 1000' in byond

    def test_get_duration_in_ds(self):
        """Test conversion to deciseconds."""
        fd = FileData()
        fd.duration = 2.5
        assert fd.getDurationInDS() == 25.0

        fd.duration = -1.0
        assert fd.getDurationInDS() == -1.0


class TestPhrase:
    """Tests for Phrase class."""

    def test_default_values(self):
        """Test default initialization."""
        p = Phrase()
        assert p.id == ""
        assert p.wordlen == 0
        assert p.phrase == ""
        assert p.parsed_phrase is None
        assert p.filename == ""
        assert p.flags == EPhraseFlags.NONE

    def test_parse_simple_phrase(self):
        """Test parsing a simple text phrase."""
        p = Phrase()
        p.id = "hello"
        p.parsePhrase("hello world")

        assert p.phrase == "hello world"
        assert p.parsed_phrase == ["hello", "world"]
        assert p.wordlen == 2
        assert not p.hasFlag(EPhraseFlags.SFX)

    def test_parse_sfx_phrase(self):
        """Test parsing an SFX phrase (starts with @)."""
        p = Phrase()
        p.id = "_honk"
        p.parsePhrase("@samples/bikehorn.wav")

        assert p.phrase == "samples/bikehorn.wav"
        assert p.hasFlag(EPhraseFlags.SFX)

    def test_parse_singing_phrase(self):
        """Test parsing a singing phrase (starts with &)."""
        p = Phrase()
        p.id = "song"
        p.parsePhrase("&songs/test.xml")

        assert p.phrase == "songs/test.xml"
        assert p.hasFlag(EPhraseFlags.SING)

    def test_parse_not_vox_phrase(self):
        """Test parsing a non-VOX phrase (contains /)."""
        p = Phrase()
        p.id = "sound/ai/announcement.ogg"
        p.parsePhrase("test announcement")

        assert p.hasFlag(EPhraseFlags.NOT_VOX)

    def test_has_flag(self):
        """Test hasFlag helper method."""
        p = Phrase()
        p.flags = EPhraseFlags.SFX | EPhraseFlags.NO_PROCESS

        assert p.hasFlag(EPhraseFlags.SFX)
        assert p.hasFlag(EPhraseFlags.NO_PROCESS)
        assert not p.hasFlag(EPhraseFlags.NO_TRIM)
        assert not p.hasFlag(EPhraseFlags.OLD_VOX)

    def test_get_final_filename(self):
        """Test final filename generation with formatting."""
        p = Phrase()
        p.id = "test"
        p.filename = "sound/vox_{SEX}/{ID}.ogg"

        assert p.getFinalFilename("fem", silent=True) == "sound/vox_fem/test.ogg"
        assert p.getFinalFilename("mas", silent=True) == "sound/vox_mas/test.ogg"

    def test_get_final_filename_windows_reserved(self):
        """Test that Windows reserved names are handled."""
        p = Phrase()
        p.id = "CON"
        p.filename = "sound/{ID}.ogg"

        result = p.getFinalFilename("fem", silent=True)
        assert "C_ON" in result  # CON -> C_ON

    def test_get_final_filename_invalid_chars(self):
        """Test that invalid characters are fixed."""
        p = Phrase()
        p.id = "test file"
        p.filename = "sound/{ID}.ogg"

        result = p.getFinalFilename("fem", silent=True)
        assert " " not in result
        assert "test_file" in result

    def test_get_asset_key(self):
        """Test asset key generation."""
        p = Phrase()
        p.id = "hello"

        assert p.getAssetKey("fem") == "fem.hello.ogg"
        assert p.getAssetKey("mas") == "mas.hello.ogg"

    def test_serialize(self):
        """Test phrase serialization."""
        p = Phrase()
        p.id = "test"
        p.parsePhrase("hello world")
        p.wordlen = 2
        p.flags = EPhraseFlags.NO_PROCESS

        serialized = p.serialize()
        assert serialized["wordlen"] == 2
        assert serialized["phrase"] == ["hello", "world"]
        assert "no-process" in serialized["flags"]

    def test_serialize_sfx(self):
        """Test SFX phrase serialization includes input-filename."""
        p = Phrase()
        p.id = "_honk"
        p.parsePhrase("@samples/bikehorn.wav")

        serialized = p.serialize()
        assert "input-filename" in serialized
        assert serialized["input-filename"] == "samples/bikehorn.wav"

    def test_from_overrides(self):
        """Test applying overrides to phrase."""
        p = Phrase()
        p.wordlen = 1

        overrides = {
            "word-count": 5,
            "flags": ["no-process", "no-trim"],
            "duration": 2.5,
            "size": 1000,
        }
        p.fromOverrides(overrides)

        assert p.wordlen == 5
        assert p.hasFlag(EPhraseFlags.NO_PROCESS)
        assert p.hasFlag(EPhraseFlags.NO_TRIM)
        assert p.override_duration == 2.5
        assert p.override_size == 1000


class TestParsePhraseListFrom:
    """Tests for ParsePhraseListFrom function."""

    def test_parse_simple_wordlist(self, sample_wordlist):
        """Test parsing a simple wordlist file."""
        phrases = ParsePhraseListFrom(str(sample_wordlist))

        assert len(phrases) == 5
        ids = [p.id for p in phrases]
        assert "hello" in ids
        assert "goodbye" in ids
        assert "_honk" in ids
        assert "test" in ids
        assert "simple" in ids

    def test_parse_categories(self, sample_wordlist):
        """Test that categories are assigned correctly."""
        phrases = ParsePhraseListFrom(str(sample_wordlist))

        hello = next(p for p in phrases if p.id == "hello")
        assert hello.category == "Test Category"

        test = next(p for p in phrases if p.id == "test")
        assert test.category == "Another Category"

    def test_parse_sfx_detection(self, sample_wordlist):
        """Test that SFX phrases are detected."""
        phrases = ParsePhraseListFrom(str(sample_wordlist))

        honk = next(p for p in phrases if p.id == "_honk")
        assert honk.hasFlag(EPhraseFlags.SFX)

    def test_parse_definition_location(self, sample_wordlist):
        """Test that definition file/line are recorded."""
        phrases = ParsePhraseListFrom(str(sample_wordlist))

        hello = next(p for p in phrases if p.id == "hello")
        assert hello.deffile == str(sample_wordlist)
        assert hello.defline > 0

    def test_parse_simple_words(self, sample_wordlist):
        """Test parsing words without = (word becomes both ID and phrase)."""
        phrases = ParsePhraseListFrom(str(sample_wordlist))

        test = next(p for p in phrases if p.id == "test")
        assert test.phrase == "test"
        assert test.parsed_phrase == ["test"]

    def test_parse_empty_lines_ignored(self, temp_dir):
        """Test that empty lines reset comment accumulation."""
        content = """# comment 1

# comment 2
word = test
"""
        filepath = temp_dir / "test.txt"
        filepath.write_text(content)

        phrases = ParsePhraseListFrom(str(filepath))
        assert len(phrases) == 1
        # Only comment 2 should be attached (empty line resets)
        assert len(phrases[0].comments_before) == 1
