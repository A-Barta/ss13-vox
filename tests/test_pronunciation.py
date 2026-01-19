"""
Tests for ss13vox.pronunciation module.

Tests phoneme validation, lexicon parsing, and LISP generation.
"""

import pytest

from ss13vox.pronunciation import (
    Pronunciation,
    ParseLexiconText,
    DumpLexiconScript,
)
from ss13vox.exceptions import PronunciationError


class TestPronunciation:
    """Tests for Pronunciation class."""

    def test_default_values(self):
        """Test default initialization."""
        p = Pronunciation()
        assert p.name == ""
        assert p.type == "n"
        assert p.syllables == []
        assert p.phoneset == ""

    def test_valid_phonemes(self):
        """Test that valid DMU phonemes are accepted."""
        p = Pronunciation()
        # All these should be in VALID_PHONEMES
        valid = ["aa", "ae", "ah", "b", "ch", "d", "er", "f", "g", "k", "l",
                 "m", "n", "ng", "p", "r", "s", "t", "z", "pau"]
        for phoneme in valid:
            assert phoneme in p.VALID_PHONEMES

    def test_parse_simple_word(self):
        """Test parsing a simple word pronunciation."""
        p = Pronunciation()
        p.parseWord('hello: noun "hh eh" \'l ow\'')

        assert p.name == "hello"
        assert p.type == "noun"
        assert len(p.syllables) == 2
        # First syllable (stressed, double quotes)
        assert p.syllables[0][0] == ["hh", "eh"]
        assert p.syllables[0][1] == 1  # stressed
        # Second syllable (unstressed, single quotes)
        assert p.syllables[1][0] == ["l", "ow"]
        assert p.syllables[1][1] == 0  # unstressed

    def test_parse_verb(self):
        """Test parsing a verb pronunciation."""
        p = Pronunciation()
        p.parseWord('running: verb "r ah" \'n ih ng\'')

        assert p.name == "running"
        assert p.type == "verb"

    def test_invalid_phoneme_raises(self):
        """Test that invalid phonemes raise PronunciationError."""
        p = Pronunciation()
        with pytest.raises(PronunciationError, match="Invalid phoneme"):
            p.parseWord('test: noun "INVALID_PHONEME"')

    def test_phoneset_conversion(self):
        """Test phoneme conversion for different phonesets."""
        p = Pronunciation(phoneset="mrpa")
        # MRPA converts 'ae' to 'a' and 'ih' to 'i'
        p.parseWord('test: noun "ae ih"')

        # After conversion
        assert p.syllables[0][0] == ["a", "i"]

    def test_to_lisp_simple(self):
        """Test LISP output generation."""
        p = Pronunciation()
        p.name = "hello"
        p.type = "noun"
        p.syllables = [
            (["hh", "eh"], 1),
            (["l", "ow"], 0),
        ]

        lisp = p.toLisp()
        assert "(lex.add.entry" in lisp
        assert '"hello"' in lisp
        assert "n" in lisp  # noun -> n
        assert "( ( hh eh ) 1 )" in lisp
        assert "( ( l ow ) 0 )" in lisp

    def test_to_lisp_verb(self):
        """Test LISP output for verb."""
        p = Pronunciation()
        p.name = "run"
        p.type = "verb"
        p.syllables = [(["r", "ah", "n"], 1)]

        lisp = p.toLisp()
        assert "v" in lisp  # verb -> v

    def test_stress_levels(self):
        """Test that stress levels are correctly parsed."""
        p = Pronunciation()
        # Double quotes = stressed (1), single quotes = unstressed (0)
        p.parseWord('monument: noun "m aa" \'n y uw\' \'m ah n t\'')

        assert p.syllables[0][1] == 1  # stressed
        assert p.syllables[1][1] == 0  # unstressed
        assert p.syllables[2][1] == 0  # unstressed

    def test_pause_phoneme(self):
        """Test that 'pau' (pause) phoneme is valid."""
        p = Pronunciation()
        p.parseWord('hesitant: noun "hh eh" \'pau\' "z ih"')

        # Should not raise, pau is valid
        assert any("pau" in syl[0] for syl in p.syllables)


class TestParseLexiconText:
    """Tests for ParseLexiconText function."""

    def test_parse_simple_lexicon(self, sample_lexicon):
        """Test parsing a simple lexicon file."""
        pronunciations = ParseLexiconText(str(sample_lexicon))

        assert "walkers" in pronunciations
        assert "running" in pronunciations
        assert len(pronunciations) == 2

    def test_parse_with_phoneset(self, sample_lexicon):
        """Test parsing with phoneset conversion."""
        pronunciations = ParseLexiconText(str(sample_lexicon), phoneset="mrpa")

        # Should still parse correctly
        assert "walkers" in pronunciations

    def test_comments_ignored(self, temp_dir):
        """Test that comment lines are ignored."""
        content = """# This is a comment
# Another comment
word: noun "w er d"
# Comment after
"""
        filepath = temp_dir / "lexicon.txt"
        filepath.write_text(content)

        pronunciations = ParseLexiconText(str(filepath))
        assert len(pronunciations) == 1
        assert "word" in pronunciations

    def test_empty_lines_ignored(self, temp_dir):
        """Test that empty lines are ignored."""
        content = """
word1: noun "w er d"

word2: verb "t eh s t"

"""
        filepath = temp_dir / "lexicon.txt"
        filepath.write_text(content)

        pronunciations = ParseLexiconText(str(filepath))
        assert len(pronunciations) == 2

    def test_lines_without_colon_ignored(self, temp_dir):
        """Test that lines without colon are ignored."""
        content = """word1: noun "w er d"
this line has no colon
word2: verb "t eh s t"
"""
        filepath = temp_dir / "lexicon.txt"
        filepath.write_text(content)

        pronunciations = ParseLexiconText(str(filepath))
        assert len(pronunciations) == 2


class TestDumpLexiconScript:
    """Tests for DumpLexiconScript function."""

    def test_dump_creates_file(self, temp_dir):
        """Test that DumpLexiconScript creates a file."""
        p = Pronunciation()
        p.name = "test"
        p.type = "noun"
        p.syllables = [(["t", "eh", "s", "t"], 1)]

        output_path = temp_dir / "lexicon.scm"
        DumpLexiconScript("", [p], str(output_path))

        assert output_path.exists()

    def test_dump_includes_voice(self, temp_dir):
        """Test that voice selection is included if specified."""
        p = Pronunciation()
        p.name = "test"
        p.type = "noun"
        p.syllables = [(["t", "eh", "s", "t"], 1)]

        output_path = temp_dir / "lexicon.scm"
        DumpLexiconScript("nitech_us_clb_arctic_hts", [p], str(output_path))

        content = output_path.read_text()
        assert "(voice_nitech_us_clb_arctic_hts)" in content

    def test_dump_no_voice(self, temp_dir):
        """Test that empty voice string doesn't add voice line."""
        p = Pronunciation()
        p.name = "test"
        p.type = "noun"
        p.syllables = [(["t", "eh", "s", "t"], 1)]

        output_path = temp_dir / "lexicon.scm"
        DumpLexiconScript("", [p], str(output_path))

        content = output_path.read_text()
        assert "(voice_" not in content

    def test_dump_sorted_by_name(self, temp_dir):
        """Test that pronunciations are sorted by name."""
        p1 = Pronunciation()
        p1.name = "zebra"
        p1.type = "noun"
        p1.syllables = [(["z"], 1)]

        p2 = Pronunciation()
        p2.name = "apple"
        p2.type = "noun"
        p2.syllables = [(["ae"], 1)]

        output_path = temp_dir / "lexicon.scm"
        DumpLexiconScript("", [p1, p2], str(output_path))

        content = output_path.read_text()
        apple_pos = content.find("apple")
        zebra_pos = content.find("zebra")
        assert apple_pos < zebra_pos  # apple should come first
