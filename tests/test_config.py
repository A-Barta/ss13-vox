"""
Tests for ss13vox.config module.

Tests Pydantic configuration validation.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from ss13vox.config import (
    VoxConfig,
    VoiceConfig,
    StationPathsConfig,
    SoundPathConfig,
    VoxSoundsConfig,
    PhraseOverride,
    load_config,
    config_to_dict,
)


class TestVoiceConfig:
    """Tests for VoiceConfig model."""

    def test_valid_config(self):
        """Test valid voice configuration."""
        config = VoiceConfig(fem="us-clb", mas="us-rms")
        assert config.fem == "us-clb"
        assert config.mas == "us-rms"

    def test_default_values(self):
        """Test default voice values."""
        config = VoiceConfig()
        assert config.fem == "us-clb"
        assert config.mas == "us-rms"
        assert config.default == "us-clb"
        assert config.sfx == "sfx"

    def test_empty_voice_rejected(self):
        """Test that empty voice ID is rejected."""
        with pytest.raises(PydanticValidationError):
            VoiceConfig(fem="")


class TestSoundPathConfig:
    """Tests for SoundPathConfig model."""

    def test_valid_config(self):
        """Test valid sound path configuration."""
        config = SoundPathConfig(
            **{"old-vox": "sound/vox", "new-vox": "sound/vox_new"}
        )
        assert config.old_vox == "sound/vox"
        assert config.new_vox == "sound/vox_new"


class TestVoxSoundsConfig:
    """Tests for VoxSoundsConfig model."""

    def test_valid_config(self):
        """Test valid vox sounds configuration."""
        config = VoxSoundsConfig(path="code/vox.dm", template="vglist.jinja")
        assert config.path == "code/vox.dm"
        assert config.template == "vglist.jinja"


class TestStationPathsConfig:
    """Tests for StationPathsConfig model."""

    def test_valid_config(self):
        """Test valid paths configuration."""
        config = StationPathsConfig(
            vox_data="data/vox_data.json",
            vox_sounds=VoxSoundsConfig(
                path="code/vox.dm", template="tg.jinja"
            ),
            sound=SoundPathConfig(
                **{"old-vox": "sound/old", "new-vox": "sound/new"}
            ),
        )
        assert config.vox_data == "data/vox_data.json"


class TestPhraseOverride:
    """Tests for PhraseOverride model."""

    def test_valid_flags(self):
        """Test valid override flags."""
        override = PhraseOverride(flags=["no-process", "no-trim"])
        assert "no-process" in override.flags
        assert "no-trim" in override.flags

    def test_invalid_flag_rejected(self):
        """Test that invalid flags are rejected."""
        with pytest.raises(PydanticValidationError):
            PhraseOverride(flags=["invalid-flag"])

    def test_valid_word_count(self):
        """Test valid word count override."""
        override = PhraseOverride(**{"word-count": 5})
        assert override.word_count == 5

    def test_duration_override(self):
        """Test duration override."""
        override = PhraseOverride(duration=2.5)
        assert override.duration == 2.5

    def test_empty_flags_allowed(self):
        """Test that empty flags list is allowed."""
        override = PhraseOverride(flags=[])
        assert override.flags == []

    def test_default_flags(self):
        """Test default empty flags."""
        override = PhraseOverride()
        assert override.flags == []


class TestVoxConfig:
    """Tests for main VoxConfig model."""

    @pytest.fixture
    def valid_paths(self):
        """Create valid paths config for testing."""
        return {
            "vg": StationPathsConfig(
                vox_data="data/vox_data.json",
                vox_sounds=VoxSoundsConfig(
                    path="code/vox.dm", template="vglist.jinja"
                ),
                sound=SoundPathConfig(
                    **{"old-vox": "sound/vox", "new-vox": "sound/vox_new"}
                ),
            ),
            "tg": StationPathsConfig(
                vox_data="data/vox_data.json",
                vox_sounds=VoxSoundsConfig(
                    path="code/vox.dm", template="tglist.jinja"
                ),
                sound=SoundPathConfig(
                    **{"old-vox": "sound/vox", "new-vox": "sound/vox_new"}
                ),
            ),
        }

    def test_minimal_valid_config(self, valid_paths):
        """Test minimal valid configuration."""
        config = VoxConfig(
            codebase="vg",
            phrasefiles=["wordlists/test.txt"],
            paths=valid_paths,
        )
        assert config.codebase == "vg"
        assert len(config.phrasefiles) == 1

    def test_default_codebase(self, valid_paths):
        """Test default codebase value."""
        config = VoxConfig(phrasefiles=["test.txt"], paths=valid_paths)
        assert config.codebase == "vg"

    def test_empty_codebase_rejected(self, valid_paths):
        """Test that empty codebase is rejected."""
        with pytest.raises(PydanticValidationError):
            VoxConfig(codebase="", phrasefiles=["test.txt"], paths=valid_paths)

    def test_phrasefiles_explicit_empty_rejected(self, valid_paths):
        """Test that explicitly empty phrasefiles is rejected."""
        with pytest.raises(PydanticValidationError):
            VoxConfig(codebase="vg", phrasefiles=[], paths=valid_paths)

    def test_max_wordlen_validation(self, valid_paths):
        """Test max-wordlen validation."""
        # Valid value
        config = VoxConfig(
            **{"max-wordlen": 50}, phrasefiles=["test.txt"], paths=valid_paths
        )
        assert config.max_wordlen == 50

        # Too small
        with pytest.raises(PydanticValidationError):
            VoxConfig(
                **{"max-wordlen": 0},
                phrasefiles=["test.txt"],
                paths=valid_paths,
            )

        # Too large
        with pytest.raises(PydanticValidationError):
            VoxConfig(
                **{"max-wordlen": 101},
                phrasefiles=["test.txt"],
                paths=valid_paths,
            )

    def test_default_voices(self, valid_paths):
        """Test default voice configuration."""
        config = VoxConfig(phrasefiles=["test.txt"], paths=valid_paths)
        assert config.voices.fem == "us-clb"
        assert config.voices.mas == "us-rms"

    def test_custom_voices(self, valid_paths):
        """Test custom voice configuration."""
        config = VoxConfig(
            voices=VoiceConfig(fem="us-slt", mas="scot-awb"),
            phrasefiles=["test.txt"],
            paths=valid_paths,
        )
        assert config.voices.fem == "us-slt"
        assert config.voices.mas == "scot-awb"

    def test_overrides(self, valid_paths):
        """Test phrase overrides."""
        config = VoxConfig(
            overrides={
                "test_word": PhraseOverride(flags=["no-process"]),
            },
            phrasefiles=["test.txt"],
            paths=valid_paths,
        )
        assert "test_word" in config.overrides
        assert "no-process" in config.overrides["test_word"].flags

    def test_codebase_must_be_in_paths(self):
        """Test that codebase must exist in paths."""
        with pytest.raises(PydanticValidationError):
            VoxConfig(codebase="nonexistent", phrasefiles=["test.txt"])


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, project_root):
        """Test loading a valid config file."""
        config_path = project_root / "vox_config.yaml"
        if not config_path.exists():
            pytest.skip("vox_config.yaml not found")

        config = load_config(config_path)
        assert config.codebase in ["vg", "tg"]

    def test_load_nonexistent_file(self, temp_dir):
        """Test loading nonexistent file raises error."""
        from ss13vox.exceptions import ConfigError

        with pytest.raises(ConfigError):
            load_config(temp_dir / "nonexistent.yaml")

    def test_load_invalid_yaml(self, temp_dir):
        """Test loading invalid YAML raises error."""
        filepath = temp_dir / "invalid.yaml"
        filepath.write_text("invalid: yaml: content: [")

        with pytest.raises(Exception):  # YAML parse error
            load_config(filepath)


class TestConfigToDict:
    """Tests for config_to_dict function."""

    def test_converts_to_dict(self, project_root):
        """Test that config is converted to dict format."""
        config_path = project_root / "vox_config.yaml"
        if not config_path.exists():
            pytest.skip("vox_config.yaml not found")

        config = load_config(config_path)
        result = config_to_dict(config, config.codebase)

        assert isinstance(result, dict)
        assert "codebase" in result
        assert "voices" in result
