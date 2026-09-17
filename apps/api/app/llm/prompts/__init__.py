"""Jinja2 prompt rendering (ai-layer.md §4, binding).

Every top-level (system) template's first line is `{# version: <name>-v<N> #}`; `render_prompt`
exposes that as `RenderedPrompt.version` so it is saved alongside the output it produced
(`prompt_version`). Templates render with `StrictUndefined`: a missing context variable raises
`jinja2.UndefinedError` instead of rendering blank text.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

PROMPTS_DIR = Path(__file__).resolve().parent

_VERSION_RE = re.compile(r"\{#\s*version:\s*(\S+)\s*#\}")

_env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,  # noqa: S701 -- plain-text LLM prompts, not HTML; escaping would corrupt them
)


@dataclass(frozen=True)
class RenderedPrompt:
    text: str
    version: str


def _template_version(filename: str) -> str:
    source = (PROMPTS_DIR / filename).read_text()
    match = _VERSION_RE.search(source)
    if match is None:
        raise ValueError(f"{filename} is missing its `{{# version: ... #}}` header")
    return match.group(1)


def render_prompt(name: str, **context: Any) -> RenderedPrompt:
    """Render `app/llm/prompts/<name>.md.j2`."""
    filename = f"{name}.md.j2"
    template = _env.get_template(filename)
    text = template.render(**context).strip()
    return RenderedPrompt(text=text, version=_template_version(filename))


def user_block(**fields: str) -> str:
    """Wrap user-provided text in `<user_text>` tags (ai-layer.md §4, security-privacy.md S6)."""
    return "\n".join(f"<user_text>\n{value}\n</user_text>" for value in fields.values())


def system_template_names() -> list[str]:
    """Every system-prompt template name: skips `_user.md.j2` files and `_`-prefixed partials."""
    names = []
    for path in sorted(PROMPTS_DIR.glob("*.md.j2")):
        if path.name.startswith("_") or path.name.endswith("_user.md.j2"):
            continue
        names.append(path.name.removesuffix(".md.j2"))
    return names
