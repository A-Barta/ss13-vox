"""
Pytest configuration and shared fixtures for SS13-VOX tests.
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that's cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_wordlist(temp_dir):
    """Create a sample wordlist file for testing."""
    content = """## Test Category
hello = hello world
goodbye = goodbye world
# This is a comment
_honk = @samples/bikehorn.wav

## Another Category
test
simple
"""
    filepath = temp_dir / "test_wordlist.txt"
    filepath.write_text(content)
    return filepath


@pytest.fixture
def sample_lexicon(temp_dir):
    """Create a sample lexicon file for testing."""
    content = """# Test lexicon
walkers: noun "w ao" 'k er z'
running: verb "r ah" 'n ih ng'
"""
    filepath = temp_dir / "test_lexicon.txt"
    filepath.write_text(content)
    return filepath


@pytest.fixture
def sample_config(temp_dir):
    """Create a sample config YAML for testing."""
    content = """
codebase: vg

phrasefiles:
  - wordlists/test.txt

voices:
  fem: us-clb
  mas: us-rms

paths:
  vg:
    sound: dist/sound
    code: dist/code
    data: dist/data

overrides:
  test_word:
    flags:
      - no-process
"""
    filepath = temp_dir / "test_config.yaml"
    filepath.write_text(content)
    return filepath


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def real_config(project_root):
    """Return path to the real vox_config.yaml if it exists."""
    config_path = project_root / "vox_config.yaml"
    if config_path.exists():
        return config_path
    pytest.skip("vox_config.yaml not found")
