"""
Tests for ss13vox.voice module.

Tests voice registry, SoX argument generation, and voice configuration.
"""

import pytest

from ss13vox.voice import (
    EVoiceSex,
    Voice,
    VoiceRegistry,
    USRMSMale,
    USCLBFemale,
    USSLTFemale,
    ScotAWBMale,
    SFXVoice,
)
from ss13vox.consts import (
    SOX_CHORUS_GAIN_IN,
    SOX_PHASER_GAIN_IN,
    SOX_ECHO_GAIN_IN,
    SOX_BASS_GAIN_DB,
    SOX_HIGHPASS_FREQ_HZ,
    SOX_COMPAND_ATTACK_DECAY,
    VOICE_PITCH_SHIFT_MALE,
    VOICE_STRETCH_STANDARD,
)
from ss13vox.exceptions import ValidationError


class TestEVoiceSex:
    """Tests for EVoiceSex enum."""

    def test_masculine_value(self):
        """Test masculine sex value."""
        assert EVoiceSex.MASCULINE.value == "mas"

    def test_feminine_value(self):
        """Test feminine sex value."""
        assert EVoiceSex.FEMININE.value == "fem"

    def test_sfx_value(self):
        """Test SFX sex value."""
        assert EVoiceSex.SFX.value == "sfx"


class TestVoice:
    """Tests for base Voice class."""

    def test_default_values(self):
        """Test default initialization."""
        v = Voice()
        assert v.assigned_sex == ""
        assert v.chorus is True
        assert v.phaser is True

    def test_gen_sox_args_includes_chorus(self):
        """Test that chorus effect is included by default."""
        v = Voice()
        args = v.genSoxArgs(None)

        assert "chorus" in args
        assert SOX_CHORUS_GAIN_IN in args

    def test_gen_sox_args_includes_phaser(self):
        """Test that phaser effect is included by default."""
        v = Voice()
        args = v.genSoxArgs(None)

        assert "phaser" in args
        assert SOX_PHASER_GAIN_IN in args

    def test_gen_sox_args_includes_bass(self):
        """Test that bass attenuation is included."""
        v = Voice()
        args = v.genSoxArgs(None)

        assert "bass" in args
        assert SOX_BASS_GAIN_DB in args

    def test_gen_sox_args_includes_highpass(self):
        """Test that highpass filter is included."""
        v = Voice()
        args = v.genSoxArgs(None)

        assert "highpass" in args
        assert SOX_HIGHPASS_FREQ_HZ in args

    def test_gen_sox_args_includes_compand(self):
        """Test that compressor is included."""
        v = Voice()
        args = v.genSoxArgs(None)

        assert "compand" in args
        assert SOX_COMPAND_ATTACK_DECAY in args

    def test_gen_sox_args_includes_echos(self):
        """Test that echo effect is included."""
        v = Voice()
        args = v.genSoxArgs(None)

        assert "echos" in args
        assert SOX_ECHO_GAIN_IN in args

    def test_gen_sox_args_includes_norm(self):
        """Test that normalization is included."""
        v = Voice()
        args = v.genSoxArgs(None)

        assert "norm" in args

    def test_gen_sox_args_no_chorus(self):
        """Test disabling chorus effect."""
        v = Voice()
        v.chorus = False
        args = v.genSoxArgs(None)

        assert "chorus" not in args

    def test_gen_sox_args_no_phaser(self):
        """Test disabling phaser effect."""
        v = Voice()
        v.phaser = False
        args = v.genSoxArgs(None)

        assert "phaser" not in args

    def test_serialize(self):
        """Test voice serialization."""
        v = USCLBFemale()
        serialized = v.serialize()

        assert serialized["id"] == "us-clb"
        assert serialized["sex"] == "fem"
        assert "festvox_id" in serialized

    def test_fast_serialize(self):
        """Test fast serialization for caching."""
        v = USCLBFemale()
        result = v.fast_serialize()

        assert isinstance(result, str)
        assert "us-clb" in result
        assert "fem" in result

    def test_fast_serialize_validation_none_id(self):
        """Test that None ID raises ValidationError."""
        v = Voice()
        v.ID = None
        with pytest.raises(ValidationError, match="Voice ID cannot be None"):
            v.fast_serialize()

    def test_fast_serialize_validation_none_sex(self):
        """Test that None SEX raises ValidationError."""
        v = Voice()
        v.ID = "test"
        v.SEX = None
        with pytest.raises(ValidationError, match="invalid SEX value"):
            v.fast_serialize()


class TestUSRMSMale:
    """Tests for US RMS Male voice."""

    def test_class_attributes(self):
        """Test class attributes."""
        assert USRMSMale.ID == "us-rms"
        assert USRMSMale.SEX == EVoiceSex.MASCULINE
        assert "rms" in USRMSMale.FESTIVAL_VOICE_ID.lower()

    def test_gen_sox_args_includes_pitch(self):
        """Test that pitch shift is included."""
        v = USRMSMale()
        args = v.genSoxArgs(None)

        assert "pitch" in args
        assert VOICE_PITCH_SHIFT_MALE in args

    def test_gen_sox_args_includes_stretch(self):
        """Test that stretch is included."""
        v = USRMSMale()
        args = v.genSoxArgs(None)

        assert "stretch" in args
        assert VOICE_STRETCH_STANDARD in args

    def test_gen_sox_args_order(self):
        """Test that pitch/stretch come before base effects."""
        v = USRMSMale()
        args = v.genSoxArgs(None)

        pitch_idx = args.index("pitch")
        chorus_idx = args.index("chorus")
        assert pitch_idx < chorus_idx


class TestUSCLBFemale:
    """Tests for US CLB Female voice."""

    def test_class_attributes(self):
        """Test class attributes."""
        assert USCLBFemale.ID == "us-clb"
        assert USCLBFemale.SEX == EVoiceSex.FEMININE
        assert "clb" in USCLBFemale.FESTIVAL_VOICE_ID.lower()

    def test_gen_sox_args_includes_stretch(self):
        """Test that stretch is included."""
        v = USCLBFemale()
        args = v.genSoxArgs(None)

        assert "stretch" in args
        assert VOICE_STRETCH_STANDARD in args

    def test_gen_sox_args_no_pitch(self):
        """Test that pitch shift is NOT included for female."""
        v = USCLBFemale()
        args = v.genSoxArgs(None)

        # Should not have pitch adjustment
        assert "pitch" not in args or VOICE_PITCH_SHIFT_MALE not in args


class TestUSSLTFemale:
    """Tests for US SLT Female voice."""

    def test_class_attributes(self):
        """Test class attributes."""
        assert USSLTFemale.ID == "us-slt"
        assert USSLTFemale.SEX == EVoiceSex.FEMININE
        assert "slt" in USSLTFemale.FESTIVAL_VOICE_ID.lower()

    def test_gen_sox_args_includes_stretch(self):
        """Test that stretch is included."""
        v = USSLTFemale()
        args = v.genSoxArgs(None)

        assert "stretch" in args


class TestScotAWBMale:
    """Tests for Scottish AWB Male voice."""

    def test_class_attributes(self):
        """Test class attributes."""
        assert ScotAWBMale.ID == "scot-awb"
        assert ScotAWBMale.SEX == EVoiceSex.MASCULINE
        assert "awb" in ScotAWBMale.FESTIVAL_VOICE_ID.lower()


class TestSFXVoice:
    """Tests for SFX voice."""

    def test_class_attributes(self):
        """Test class attributes."""
        assert SFXVoice.ID == "sfx"
        assert SFXVoice.SEX == EVoiceSex.SFX
        assert SFXVoice.FESTIVAL_VOICE_ID == ""

    def test_no_chorus_or_phaser(self):
        """Test that SFX voice has no chorus/phaser by default."""
        v = SFXVoice()
        assert v.chorus is False
        assert v.phaser is False

    def test_assigned_sex(self):
        """Test that assigned_sex is set correctly."""
        v = SFXVoice()
        assert v.assigned_sex == "sfx"

    def test_gen_sox_args_minimal(self):
        """Test that SFX voice has minimal processing."""
        v = SFXVoice()
        args = v.genSoxArgs(None)

        # Should still have echos and compand
        assert "echos" in args
        assert "compand" in args
        # But NOT chorus or phaser
        assert "chorus" not in args
        assert "phaser" not in args


class TestVoiceRegistry:
    """Tests for VoiceRegistry."""

    def test_all_voices_registered(self):
        """Test that all voices are registered."""
        assert "us-rms" in VoiceRegistry.ALL
        assert "us-clb" in VoiceRegistry.ALL
        assert "us-slt" in VoiceRegistry.ALL
        assert "scot-awb" in VoiceRegistry.ALL
        assert "sfx" in VoiceRegistry.ALL

    def test_get_returns_instance(self):
        """Test that Get returns a voice instance."""
        voice = VoiceRegistry.Get("us-clb")
        assert isinstance(voice, USCLBFemale)

    def test_get_male_voice(self):
        """Test getting a male voice."""
        voice = VoiceRegistry.Get("us-rms")
        assert isinstance(voice, USRMSMale)
        assert voice.SEX == EVoiceSex.MASCULINE

    def test_get_sfx_voice(self):
        """Test getting the SFX voice."""
        voice = VoiceRegistry.Get("sfx")
        assert isinstance(voice, SFXVoice)

    def test_get_invalid_voice_raises(self):
        """Test that getting invalid voice raises KeyError."""
        with pytest.raises(KeyError):
            VoiceRegistry.Get("nonexistent-voice")

    def test_register_custom_voice(self):
        """Test registering a custom voice."""
        class TestVoice(Voice):
            ID = "test-voice"
            SEX = EVoiceSex.MASCULINE
            FESTIVAL_VOICE_ID = "test_voice"

        VoiceRegistry.Register(TestVoice)
        assert "test-voice" in VoiceRegistry.ALL

        # Cleanup
        del VoiceRegistry.ALL["test-voice"]
