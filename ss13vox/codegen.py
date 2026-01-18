"""
DM Code Generation for SS13-VOX.

This module generates Dream Maker (DM) code for Space Station 13 servers,
including sound mappings, duration data, and word length information.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import jinja2

from .phrase import EPhraseFlags, Phrase


@dataclass
class Proc:
    """Represents a DM proc with instruction cost tracking."""

    name: str
    lines: list[str] = field(default_factory=list)
    instructions: int = 5  # BASE_COST

    def add_line(self, line: str, cost: int) -> None:
        self.lines.append(line)
        self.instructions += cost


class InitClassBuilder:
    """
    Builds initialization code split across multiple procs.

    DM has a limit on instructions per proc (~65535). This class
    automatically splits initialization code across multiple procs
    to avoid hitting that limit.
    """

    INSTRUCTION_LIMIT = 65535
    SUBPROC_PREFIX = "__init_"

    def __init__(self):
        self.instructions: int = 0
        self._proc_count: int = 0
        self._current_proc: Optional[Proc] = None
        self.procs: dict[str, Proc] = {}

    def _add_proc(self) -> Proc:
        self._proc_count += 1
        proc = Proc(name=f"{self.SUBPROC_PREFIX}{self._proc_count}")
        self.procs[proc.name] = proc
        self._current_proc = proc
        return proc

    def add_instruction(self, instruction: str, cost: int) -> None:
        """Add an instruction, creating a new proc if needed."""
        if (
            self._current_proc is None
            or self._current_proc.instructions + cost > self.INSTRUCTION_LIMIT
        ):
            self._add_proc()

        assert self._current_proc is not None
        self._current_proc.add_line(instruction, cost)
        self.instructions += cost


@dataclass
class CodeGenConfig:
    """Configuration for DM code generation."""

    template_dir: Path = Path("templates")
    output_dir: Path = Path("dist")
    disable_macro: str = "DISABLE_VOX"


class DMCodeGenerator(ABC):
    """Abstract base class for DM code generators."""

    def __init__(self, config: Optional[CodeGenConfig] = None):
        self.config = config or CodeGenConfig()
        self._env: Optional[jinja2.Environment] = None

    @property
    def env(self) -> jinja2.Environment:
        """Lazy-loaded Jinja2 environment."""
        if self._env is None:
            self._env = jinja2.Environment(
                loader=jinja2.FileSystemLoader([str(self.config.template_dir)]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            self._env.add_extension("jinja2.ext.do")
        return self._env

    @abstractmethod
    def generate(
        self,
        phrases: list[Phrase],
        sexes: dict[str, list[Phrase]],
    ) -> str:
        """Generate DM code from phrases."""
        pass

    @abstractmethod
    def get_output_path(self) -> Path:
        """Get the output file path."""
        pass

    def write(
        self,
        phrases: list[Phrase],
        sexes: dict[str, list[Phrase]],
    ) -> Path:
        """Generate and write DM code to file."""
        output_path = self.get_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        content = self.generate(phrases, sexes)
        output_path.write_text(content)

        return output_path


class VGCodeGenerator(DMCodeGenerator):
    """
    Code generator for /vg/station codebase.

    Generates code with instruction batching to avoid DM compiler limits.
    """

    TEMPLATE_NAME = "vglist.jinja"

    def __init__(
        self,
        config: Optional[CodeGenConfig] = None,
        output_filename: str = "code/defines/vox_sounds.dm",
    ):
        super().__init__(config)
        self.output_filename = output_filename

    def get_output_path(self) -> Path:
        return self.config.output_dir / self.output_filename

    def generate(
        self,
        phrases: list[Phrase],
        sexes: dict[str, list[Phrase]],
    ) -> str:
        """Generate VG-style DM code."""
        template = self.env.get_template(self.TEMPLATE_NAME)

        # Filter out NOT_VOX phrases for the main list
        filtered_phrases = [
            p for p in phrases if not p.hasFlag(EPhraseFlags.NOT_VOX)
        ]

        return template.render(
            InitClass=InitClassBuilder,
            SEXES=sexes,
            PHRASES=filtered_phrases,
        )


class TGCodeGenerator(DMCodeGenerator):
    """
    Code generator for /tg/station codebase.

    Generates simpler inline list initialization.
    """

    TEMPLATE_NAME = "tglist.jinja"

    def __init__(
        self,
        config: Optional[CodeGenConfig] = None,
        output_filename: str = "code/modules/mob/living/silicon/ai/vox_sounds.dm",
    ):
        super().__init__(config)
        self.output_filename = output_filename

    def get_output_path(self) -> Path:
        return self.config.output_dir / self.output_filename

    def generate(
        self,
        phrases: list[Phrase],
        sexes: dict[str, list[Phrase]],
    ) -> str:
        """Generate TG-style DM code."""
        template = self.env.get_template(self.TEMPLATE_NAME)

        filtered_phrases = [
            p for p in phrases if not p.hasFlag(EPhraseFlags.NOT_VOX)
        ]

        return template.render(
            SEXES=sexes,
            PHRASES=filtered_phrases,
        )


class PureCodeGenerator(DMCodeGenerator):
    """
    Pure Python code generator without Jinja2 templates.

    Generates the same output as VGCodeGenerator but entirely in Python,
    useful if templates are not available or for debugging.
    """

    def __init__(
        self,
        config: Optional[CodeGenConfig] = None,
        output_filename: str = "code/defines/vox_sounds.dm",
        codebase: str = "vg",
    ):
        super().__init__(config)
        self.output_filename = output_filename
        self.codebase = codebase

    def get_output_path(self) -> Path:
        return self.config.output_dir / self.output_filename

    def generate(
        self,
        phrases: list[Phrase],
        sexes: dict[str, list[Phrase]],
    ) -> str:
        """Generate DM code without templates."""
        if self.codebase == "tg":
            return self._generate_tg(phrases, sexes)
        return self._generate_vg(phrases, sexes)

    def _generate_vg(
        self,
        phrases: list[Phrase],
        sexes: dict[str, list[Phrase]],
    ) -> str:
        """Generate VG-style code."""
        builder = InitClassBuilder()

        # Add sound mappings
        for sex, sex_phrases in sexes.items():
            if not sex_phrases:
                continue

            builder.add_instruction(f'vox_sounds["{sex}"] = list()', cost=11)

            for phrase in sex_phrases:
                if sex not in phrase.files:
                    continue
                file_data = phrase.files[sex]
                builder.add_instruction(
                    f'vox_sounds["{sex}"]["{phrase.id}"] = \'{file_data.filename}\'',
                    cost=16,
                )
                duration_ds = file_data.getDurationInDS()
                builder.add_instruction(
                    f'vox_sound_lengths[\'{file_data.filename}\'] = {duration_ds:0.4g}',
                    cost=13,
                )

        # Add word lengths
        for phrase in phrases:
            if phrase.hasFlag(EPhraseFlags.NOT_VOX):
                continue
            if phrase.wordlen > 1:
                builder.add_instruction(
                    f'vox_wordlen["{phrase.id}"] = {phrase.wordlen}',
                    cost=13,
                )

        # Build output
        lines = [
            "// AUTOMATICALLY @generated, DO NOT EDIT.",
            "// Generated by ss13-vox",
            "",
            "// DEFINES",
            "// * DISABLE_VOX - When defined, VOX sounds will not be loaded.",
            "",
            "var/list/vox_sounds = list()",
            "var/list/vox_wordlen = list()",
            "var/list/vox_sound_lengths = list()",
            "",
            f"// STATS: {builder.instructions} instructions across "
            f"{len(builder.procs)} procs.",
            "",
            "#ifndef DISABLE_VOX",
            "/__vox_sound_meta_init/New()",
        ]

        # Add proc calls
        for proc in builder.procs.values():
            lines.append(f"  src.{proc.name}() // {proc.instructions} instructions")

        # Add proc definitions
        for proc in builder.procs.values():
            lines.append(f"/__vox_sound_meta_init/proc/{proc.name}()")
            for line in proc.lines:
                lines.append(f"  {line}")

        lines.extend([
            "",
            "/var/__vox_sound_meta_init/__vox_sound_meta_instance = new",
            "#endif",
        ])

        return "\n".join(lines)

    def _generate_tg(
        self,
        _phrases: list[Phrase],
        sexes: dict[str, list[Phrase]],
    ) -> str:
        """Generate TG-style code."""
        lines = [
            "// AUTOMATICALLY @generated, DO NOT EDIT.",
            "// Generated by ss13-vox",
            "#ifdef AI_VOX",
            "",
            "GLOBAL_LIST_INIT(vox_sounds, list(",
        ]

        for sex, sex_phrases in sexes.items():
            if not sex_phrases:
                continue

            lines.append(f'  "{sex}" = list(')
            for phrase in sex_phrases:
                if sex not in phrase.files:
                    continue
                filename = phrase.files[sex].filename
                lines.append(f'    "{phrase.id}" = \'{filename}\',')
            lines.append("  ),")

        lines.extend([
            "))",
            "",
            "#endif //AI_VOX",
        ])

        return "\n".join(lines)


def get_generator(
    codebase: str,
    config: Optional[CodeGenConfig] = None,
    use_templates: bool = True,
) -> DMCodeGenerator:
    """
    Factory function to get the appropriate code generator.

    Args:
        codebase: Target codebase ("vg" or "tg")
        config: Optional configuration
        use_templates: If True, use Jinja2 templates; otherwise use pure Python

    Returns:
        Appropriate DMCodeGenerator instance
    """
    if use_templates:
        if codebase == "tg":
            return TGCodeGenerator(config)
        return VGCodeGenerator(config)
    else:
        return PureCodeGenerator(config, codebase=codebase)
