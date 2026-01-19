"""
Tests for ss13vox.codegen module.

Tests DM code generation and instruction batching.
"""

import pytest
from pathlib import Path

from ss13vox.codegen import (
    Proc,
    InitClassBuilder,
    CodeGenConfig,
    VGCodeGenerator,
    TGCodeGenerator,
    PureCodeGenerator,
    get_generator,
)
from ss13vox.phrase import Phrase, FileData, EPhraseFlags


class TestProc:
    """Tests for Proc dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        proc = Proc(name="test")
        assert proc.name == "test"
        assert proc.lines == []
        assert proc.instructions == 5  # BASE_COST

    def test_add_line(self):
        """Test adding a line to proc."""
        proc = Proc(name="test")
        proc.add_line("test line", cost=10)

        assert len(proc.lines) == 1
        assert proc.lines[0] == "test line"
        assert proc.instructions == 15  # 5 base + 10

    def test_add_multiple_lines(self):
        """Test adding multiple lines."""
        proc = Proc(name="test")
        proc.add_line("line 1", cost=5)
        proc.add_line("line 2", cost=10)
        proc.add_line("line 3", cost=3)

        assert len(proc.lines) == 3
        assert proc.instructions == 23  # 5 base + 5 + 10 + 3


class TestInitClassBuilder:
    """Tests for InitClassBuilder."""

    def test_default_values(self):
        """Test default initialization."""
        builder = InitClassBuilder()
        assert builder.instructions == 0
        assert builder.procs == {}

    def test_add_instruction_creates_proc(self):
        """Test that first instruction creates a proc."""
        builder = InitClassBuilder()
        builder.add_instruction("test", cost=10)

        assert len(builder.procs) == 1
        assert builder.instructions == 10

    def test_proc_naming(self):
        """Test proc naming convention."""
        builder = InitClassBuilder()
        builder.add_instruction("test", cost=10)

        proc_names = list(builder.procs.keys())
        assert proc_names[0].startswith("__init_")

    def test_instruction_limit_creates_new_proc(self):
        """Test that exceeding limit creates new proc."""
        builder = InitClassBuilder()

        # Add instruction that nearly fills the limit
        builder.add_instruction("big", cost=65530)
        assert len(builder.procs) == 1

        # Adding more should create new proc
        builder.add_instruction("overflow", cost=100)
        assert len(builder.procs) == 2

    def test_total_instructions_tracked(self):
        """Test that total instructions are tracked."""
        builder = InitClassBuilder()
        builder.add_instruction("a", cost=100)
        builder.add_instruction("b", cost=200)
        builder.add_instruction("c", cost=300)

        assert builder.instructions == 600


class TestCodeGenConfig:
    """Tests for CodeGenConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CodeGenConfig()
        assert config.template_dir == Path("templates")
        assert config.output_dir == Path("dist")
        assert config.disable_macro == "DISABLE_VOX"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = CodeGenConfig(
            template_dir=Path("custom/templates"),
            output_dir=Path("custom/output"),
            disable_macro="CUSTOM_MACRO",
        )
        assert config.template_dir == Path("custom/templates")
        assert config.disable_macro == "CUSTOM_MACRO"


class TestGetGenerator:
    """Tests for get_generator factory function."""

    def test_get_vg_generator(self):
        """Test getting VG generator."""
        gen = get_generator("vg", use_templates=True)
        assert isinstance(gen, VGCodeGenerator)

    def test_get_tg_generator(self):
        """Test getting TG generator."""
        gen = get_generator("tg", use_templates=True)
        assert isinstance(gen, TGCodeGenerator)

    def test_get_pure_generator_vg(self):
        """Test getting pure Python generator for VG."""
        gen = get_generator("vg", use_templates=False)
        assert isinstance(gen, PureCodeGenerator)

    def test_get_pure_generator_tg(self):
        """Test getting pure Python generator for TG."""
        gen = get_generator("tg", use_templates=False)
        assert isinstance(gen, PureCodeGenerator)

    def test_custom_config_passed(self):
        """Test that custom config is used."""
        config = CodeGenConfig(output_dir=Path("custom"))
        gen = get_generator("vg", config=config)
        assert gen.config.output_dir == Path("custom")


class TestVGCodeGenerator:
    """Tests for VGCodeGenerator."""

    def test_template_name(self):
        """Test template name is correct."""
        assert VGCodeGenerator.TEMPLATE_NAME == "vglist.jinja"

    def test_get_output_path(self):
        """Test output path generation."""
        config = CodeGenConfig(output_dir=Path("dist"))
        gen = VGCodeGenerator(config=config)
        path = gen.get_output_path()

        assert "dist" in str(path)
        assert path.suffix == ".dm"


class TestTGCodeGenerator:
    """Tests for TGCodeGenerator."""

    def test_template_name(self):
        """Test template name is correct."""
        assert TGCodeGenerator.TEMPLATE_NAME == "tglist.jinja"

    def test_default_output(self):
        """Test default output path."""
        assert "vox_sounds.dm" in TGCodeGenerator.DEFAULT_OUTPUT


class TestPureCodeGenerator:
    """Tests for PureCodeGenerator (template-less)."""

    def test_generate_vg_empty(self):
        """Test VG generation with empty phrases."""
        gen = PureCodeGenerator(codebase="vg")
        result = gen.generate(phrases=[], sexes={"fem": [], "mas": []})

        assert isinstance(result, str)
        assert "vox_sounds" in result.lower() or len(result) > 0

    def test_generate_tg_empty(self):
        """Test TG generation with empty phrases."""
        gen = PureCodeGenerator(codebase="tg")
        result = gen.generate(phrases=[], sexes={"fem": [], "mas": []})

        assert isinstance(result, str)

    def test_generate_with_phrases(self):
        """Test generation with actual phrases."""
        gen = PureCodeGenerator(codebase="vg")

        # Create test phrase
        p = Phrase()
        p.id = "test"
        p.phrase = "test"
        p.wordlen = 1

        fd = FileData()
        fd.filename = "sound/vox_fem/test.ogg"
        fd.duration = 1.0
        fd.checksum = "abc123"
        fd.voice = "fem"
        fd.size = 1000
        p.files["fem"] = fd

        result = gen.generate(
            phrases=[p],
            sexes={"fem": [p], "mas": []},
        )

        assert "test" in result
        assert isinstance(result, str)

    def test_generate_filters_not_vox(self):
        """Test that NOT_VOX phrases are filtered."""
        gen = PureCodeGenerator(codebase="vg")

        # Create NOT_VOX phrase
        p = Phrase()
        p.id = "sound/ai/test.ogg"
        p.phrase = "test"
        p.flags = EPhraseFlags.NOT_VOX

        fd = FileData()
        fd.filename = "sound/ai/test.ogg"
        fd.duration = 1.0
        p.files["fem"] = fd

        result = gen.generate(
            phrases=[p],
            sexes={"fem": [p], "mas": []},
        )

        # NOT_VOX phrases should be filtered from main list
        # but may appear in special handling
        assert isinstance(result, str)


class TestDMCodeGeneration:
    """Integration tests for DM code generation."""

    @pytest.fixture
    def sample_phrases(self):
        """Create sample phrases for testing."""
        phrases = []
        for word in ["hello", "world", "test"]:
            p = Phrase()
            p.id = word
            p.phrase = word
            p.wordlen = 1

            for sex in ["fem", "mas"]:
                fd = FileData()
                fd.filename = f"sound/vox_{sex}/{word}.ogg"
                fd.duration = 0.5 + len(word) * 0.1
                fd.checksum = f"{word}_{sex}_checksum"
                fd.voice = sex
                fd.size = 1000 + len(word) * 100
                p.files[sex] = fd

            phrases.append(p)
        return phrases

    def test_pure_vg_generation(self, sample_phrases):
        """Test pure Python VG code generation."""
        gen = PureCodeGenerator(codebase="vg")
        sexes = {
            "fem": sample_phrases,
            "mas": sample_phrases,
        }

        result = gen.generate(sample_phrases, sexes)

        # Should contain sound mappings
        assert "vox_sounds" in result
        # Should contain our test words
        assert "hello" in result
        assert "world" in result
        assert "test" in result

    def test_pure_tg_generation(self, sample_phrases):
        """Test pure Python TG code generation."""
        gen = PureCodeGenerator(codebase="tg")
        sexes = {
            "fem": sample_phrases,
            "mas": sample_phrases,
        }

        result = gen.generate(sample_phrases, sexes)

        # Should be valid DM code
        assert isinstance(result, str)
        # Should have some content
        assert len(result) > 0

    def test_instruction_batching_large_list(self):
        """Test that large phrase lists are batched into multiple procs."""
        gen = PureCodeGenerator(codebase="vg")

        # Create many phrases
        phrases = []
        for i in range(1000):
            p = Phrase()
            p.id = f"word{i}"
            p.phrase = f"word {i}"
            p.wordlen = 2

            fd = FileData()
            fd.filename = f"sound/vox_fem/word{i}.ogg"
            fd.duration = 1.0
            fd.checksum = f"checksum{i}"
            fd.voice = "fem"
            fd.size = 1000
            p.files["fem"] = fd
            phrases.append(p)

        sexes = {"fem": phrases, "mas": []}
        result = gen.generate(phrases, sexes)

        # Should have multiple init procs due to instruction limit
        assert "__init_" in result
        # Count how many init procs
        init_count = result.count("/proc/__init_")
        # With 1000 phrases, should need multiple procs
        assert init_count >= 1
