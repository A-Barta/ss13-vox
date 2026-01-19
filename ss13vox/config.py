"""Configuration validation for SS13-VOX.

This module provides Pydantic models for validating the vox_config.yaml
configuration file, ensuring all required fields are present and valid.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .exceptions import ConfigError


class VoiceConfig(BaseModel):
    """Voice configuration mapping sex IDs to voice IDs."""

    fem: str = "us-clb"
    mas: str = "us-rms"
    default: str = "us-clb"
    sfx: str = "sfx"

    @field_validator("*", mode="before")
    @classmethod
    def voice_must_be_string(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError(f"Voice ID must be a string, got {type(v).__name__}")
        if not v:
            raise ValueError("Voice ID cannot be empty")
        return v


class VoxSoundsConfig(BaseModel):
    """Configuration for DM code generation output."""

    path: str
    template: str


class SoundPathConfig(BaseModel):
    """Configuration for sound file paths."""

    old_vox: str = Field(alias="old-vox")
    new_vox: str = Field(alias="new-vox")

    model_config = {"populate_by_name": True}


class StationPathsConfig(BaseModel):
    """Path configuration for a specific station/codebase."""

    vox_data: str
    vox_sounds: VoxSoundsConfig
    sound: SoundPathConfig


class PhraseOverride(BaseModel):
    """Override configuration for a specific phrase."""

    flags: list[str] = Field(default_factory=list)
    duration: float | None = None
    word_count: int | None = Field(default=None, alias="word-count")

    model_config = {"populate_by_name": True}

    @field_validator("flags", mode="before")
    @classmethod
    def validate_flags(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError(f"flags must be a list, got {type(v).__name__}")
        valid_flags = {"old-vox", "no-process", "no-trim", "sfx", "sing", "not-vox"}
        for flag in v:
            if flag not in valid_flags:
                raise ValueError(
                    f"Invalid flag '{flag}'. Valid flags: {', '.join(sorted(valid_flags))}"
                )
        return v


class VoxConfig(BaseModel):
    """Main configuration model for SS13-VOX."""

    codebase: str = "vg"
    max_wordlen: int = Field(default=30, alias="max-wordlen")
    voices: VoiceConfig = Field(default_factory=VoiceConfig)
    phrasefiles: list[str] = Field(default_factory=list)
    overrides: dict[str, PhraseOverride] = Field(default_factory=dict)
    paths: dict[str, StationPathsConfig] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator("codebase")
    @classmethod
    def validate_codebase(cls, v: str) -> str:
        if not v:
            raise ValueError("codebase cannot be empty")
        return v

    @field_validator("max_wordlen")
    @classmethod
    def validate_max_wordlen(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"max-wordlen must be positive, got {v}")
        if v > 100:
            raise ValueError(f"max-wordlen too large: {v} (max 100)")
        return v

    @field_validator("phrasefiles")
    @classmethod
    def validate_phrasefiles(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("phrasefiles cannot be empty - at least one wordlist required")
        for path in v:
            if not path:
                raise ValueError("phrasefile path cannot be empty")
        return v

    @model_validator(mode="after")
    def validate_paths_for_codebase(self) -> "VoxConfig":
        if self.codebase not in self.paths:
            available = ", ".join(sorted(self.paths.keys())) if self.paths else "none"
            raise ValueError(
                f"codebase '{self.codebase}' not found in paths. "
                f"Available: {available}"
            )
        return self

    @field_validator("overrides", mode="before")
    @classmethod
    def parse_overrides(cls, v: Any) -> dict[str, PhraseOverride]:
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError(f"overrides must be a dict, got {type(v).__name__}")
        result = {}
        for phrase_id, override_data in v.items():
            if override_data is None:
                continue
            try:
                result[phrase_id] = PhraseOverride.model_validate(override_data)
            except Exception as e:
                raise ValueError(f"Invalid override for phrase '{phrase_id}': {e}") from e
        return result


def load_config(path: str | Path) -> VoxConfig:
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the configuration file (typically vox_config.yaml)

    Returns:
        Validated VoxConfig instance

    Raises:
        ConfigError: If the file cannot be read or validation fails
    """
    from yaml import safe_load, YAMLError

    path = Path(path)

    try:
        with open(path) as f:
            data = safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")
    except OSError as e:
        raise ConfigError(f"Cannot read config file {path}: {e}")
    except YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}")

    if data is None:
        raise ConfigError(f"Config file is empty: {path}")

    try:
        return VoxConfig.model_validate(data)
    except Exception as e:
        raise ConfigError(f"Invalid configuration in {path}: {e}") from e


def config_to_dict(config: VoxConfig, station: str) -> dict[str, Any]:
    """Convert VoxConfig to the dict format expected by existing code.

    This provides backward compatibility with existing code that expects
    the raw dict format from yaml.safe_load().

    Args:
        config: Validated VoxConfig instance
        station: Station/codebase to use (e.g., 'vg', 'tg')

    Returns:
        Dict in the format expected by generate() and other functions
    """
    return {
        "codebase": config.codebase,
        "max-wordlen": config.max_wordlen,
        "voices": {
            "fem": config.voices.fem,
            "mas": config.voices.mas,
            "default": config.voices.default,
            "sfx": config.voices.sfx,
        },
        "phrasefiles": config.phrasefiles,
        "overrides": {
            phrase_id: {
                "flags": override.flags,
                **({"duration": override.duration} if override.duration is not None else {}),
                **({"word-count": override.word_count} if override.word_count is not None else {}),
            }
            for phrase_id, override in config.overrides.items()
        },
        "paths": {
            name: {
                "vox_data": paths.vox_data,
                "vox_sounds": {
                    "path": paths.vox_sounds.path,
                    "template": paths.vox_sounds.template,
                },
                "sound": {
                    "old-vox": paths.sound.old_vox,
                    "new-vox": paths.sound.new_vox,
                },
            }
            for name, paths in config.paths.items()
        },
    }
