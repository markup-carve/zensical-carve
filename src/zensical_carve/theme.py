"""Hand a few constructs back to Zensical instead of rendering them ourselves.

A whole Carve page rendered straight to HTML looks right and behaves wrong,
which was measured on a real build rather than guessed:

- **the table of contents was empty.** Zensical builds it from Python-Markdown's
  ``toc`` extension, which only sees Markdown headings. Ours were HTML, so the
  sidebar had nothing in it.
- **headings had no permalink.** Same cause: ``toc.permalink`` adds the anchor.
- **code blocks had no syntax colors, no copy button, and an invisible title.**
  Those come from the theme's highlighting pipeline, which only runs on a
  Markdown fenced block.

So this module emits a HYBRID page: headings and code blocks go out as Markdown,
everything else stays as Carve's HTML. Python-Markdown reads a block-level raw
HTML chunk verbatim as long as blank lines separate it, so the two forms coexist
in one file and each construct is handled by whoever handles it best.

What deliberately stays HTML: admonitions, definition lists, tables with
captions, and every inline mark. Carve's ``to_markdown`` renders those too, but
lossily - an admonition becomes a bold paragraph and the container is gone - so
converting the whole page would trade one set of flaws for a worse set.
"""

from __future__ import annotations

import html
import re

__all__ = ["adapt"]

_SECTION_OPEN = re.compile(r"[ \t]*<section\b[^>]*>[ \t]*\n?")
_SECTION_CLOSE = re.compile(r"[ \t]*</section>[ \t]*\n?")
_HEADING = re.compile(
    r"[ \t]*<h(?P<level>[1-6])(?P<attrs>[^>]*)>(?P<text>.*?)</h(?P=level)>[ \t]*",
    re.DOTALL,
)
_CODE = re.compile(
    r"[ \t]*<pre(?P<pre_attrs>[^>]*)>"
    r"<code(?P<code_attrs>[^>]*)>(?P<body>.*?)</code></pre>[ \t]*",
    re.DOTALL,
)
_ATTR = re.compile(r"""(?P<name>[-\w]+)\s*=\s*"(?P<value>[^"]*)\"""")
_TASK_ITEM = re.compile(r"<li>(\s*)<input type=\"checkbox\"")


def _attrs(raw: str) -> dict[str, str]:
    return {m.group("name"): m.group("value") for m in _ATTR.finditer(raw)}


def _heading_id(section_ids: list[str], attrs: dict[str, str]) -> str:
    """Carve puts the id on the section, not on the heading inside it."""
    if "id" in attrs:
        return attrs["id"]
    return section_ids[-1] if section_ids else ""


def _markdown_heading(level: int, text: str, ident: str, classes: str) -> str:
    """A Markdown heading line, with attr_list carrying id and classes."""
    text = " ".join(text.split())
    parts = []
    if ident:
        parts.append(f"#{ident}")
    parts.extend(f".{name}" for name in classes.split())
    suffix = f" {{{' '.join(parts)}}}" if parts else ""
    return f"\n\n{'#' * level} {text}{suffix}\n\n"


def _markdown_code(pre_attrs: dict[str, str], code_attrs: dict[str, str], body: str) -> str:
    """A fenced block, so the theme highlights it and offers a copy button."""
    language = ""
    for name in code_attrs.get("class", "").split():
        if name.startswith("language-"):
            language = name[len("language-") :]
            break

    options = []
    if title := pre_attrs.get("title"):
        options.append(f'title="{title}"')

    source = html.unescape(body)
    # A fence must be longer than any backtick run inside the payload.
    longest = max((len(run) for run in re.findall(r"`+", source)), default=0)
    fence = "`" * max(3, longest + 1)

    head = fence + language
    if options:
        head += " " + " ".join(options)
    return f"\n\n{head}\n{source.strip(chr(10))}\n{fence}\n\n"


def _dedent(chunk: str) -> str:
    """Left-align an HTML chunk that used to sit inside a `<section>`.

    Carve indents by container depth, so dropping the sections leaves the HTML
    four or more spaces in - and Python-Markdown reads a four-space indent as a
    code block, which turned the whole page into one. The indent of the first
    non-blank line is the section depth, and stripping that much from every
    line preserves the relative indentation inside the chunk.
    """
    lines = chunk.split("\n")
    first = next((line for line in lines if line.strip()), "")
    indent = len(first) - len(first.lstrip(" "))
    if not indent:
        return chunk
    return "\n".join(
        line[indent:] if line[:indent].strip() == "" else line.lstrip(" ")
        for line in lines
    )


def adapt(carve_html: str) -> str:
    """Rewrite Carve's HTML into the hybrid page body."""
    out = carve_html
    section_ids: list[str] = []

    def take_section(match: re.Match[str]) -> str:
        section_ids.append(_attrs(match.group(0)).get("id", ""))
        return ""

    # Sections are dropped rather than kept: they carry the heading's id, which
    # moves onto the heading itself, and a Markdown heading cannot live inside
    # a raw HTML block anyway - Python-Markdown would pass it through as text.
    pieces: list[str] = []
    position = 0
    pattern = re.compile(
        "|".join(
            (
                r"(?P<section><section\b[^>]*>)",
                r"(?P<section_end></section>)",
                _HEADING.pattern,
                _CODE.pattern,
            )
        ),
        re.DOTALL,
    )
    for match in pattern.finditer(out):
        pieces.append(out[position : match.start()])
        position = match.end()
        if match.group("section"):
            section_ids.append(_attrs(match.group("section")).get("id", ""))
        elif match.group("section_end"):
            if section_ids:
                section_ids.pop()
        elif match.group("level"):
            attrs = _attrs(match.group("attrs"))
            pieces.append(
                _markdown_heading(
                    int(match.group("level")),
                    match.group("text"),
                    _heading_id(section_ids, attrs),
                    attrs.get("class", ""),
                )
            )
        else:
            pieces.append(
                _markdown_code(
                    _attrs(match.group("pre_attrs")),
                    _attrs(match.group("code_attrs")),
                    match.group("body"),
                )
            )
    pieces.append(out[position:])
    out = "".join(_dedent(piece) if not piece.startswith("\n\n") else piece for piece in pieces)

    # The theme styles a task list by class; without them the bullet marker
    # shows next to the checkbox.
    if _TASK_ITEM.search(out):
        out = _TASK_ITEM.sub(r'<li class="task-list-item">\1<input type="checkbox"', out)
        out = re.sub(
            r"<ul>(\s*<li class=\"task-list-item\")", r'<ul class="task-list">\1', out
        )

    # Collapse the blank-line runs the rewrites introduced, and make sure every
    # raw HTML chunk is still separated from a Markdown line by a blank line.
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip("\n") + "\n"
