"""Engine rulings a built page depends on, asserted as rulings not goldens.

`constraints-ci.txt` sat at carve-lang 0.1.4 while 0.1.5, 0.1.6 and 0.1.7
published. The unconstrained daily run in `scheduled.yml` - the one whose whole
job is to meet a new engine first - was green every one of those days, and four
boundary shapes rendered differently the whole time. All 94 tests pass on 0.1.4
and on 0.1.7.

The suite was not careless about shape changes; it was careless about this kind.
`test_zensical_carve.py` already covers the prerender matcher against exactly
the failure that bit in 0.1.2, down to
`test_extra_attributes_on_the_block_do_not_hide_it` and
`test_a_diagram_on_an_unexpected_tag_is_reported_not_silent`. Measured across
0.1.4 and 0.1.7, that path is clean: a mermaid block comes out byte-identical
and `tests/e2e_build.py` builds a real Zensical site on both. What nothing
covered was an ordinary document construct.

Measured per release, so the claim is dated rather than vague:

    engine  cross-reference   ::: note"Title   body-rows=1,1      fence body
    0.1.1   link              prose            leaked, 1 tbody    stray newline
    0.1.4   link              prose            leaked, 1 tbody    stray newline
    0.1.5   link              prose            leaked, 1 tbody    stray newline
    0.1.6   link              prose            leaked, 1 tbody    empty
    0.1.7   literal text      container        consumed, 2 tbody  empty

Three moved in 0.1.7 and one in 0.1.6, so every assertion below needs
carve-lang >= 0.1.7, which `constraints-ci.txt` guarantees. Run against an older
engine they go red on purpose: that is a statement about the engine, and
`test_engine_floor` is the file that speaks for the floor.

Each assertion is a DIRECTION - a link or not a link, an attribute leaked or
consumed, a count of bodies - rather than a byte string. A golden would pin
whatever the engine currently says, including a reading that later turns out
wrong; a direction is a claim this package can hold the engine to.
"""

from __future__ import annotations

import carve


def _version() -> str:
    return getattr(carve, "__version__", "unknown")


def test_something_renders_at_all():
    """A discriminator, for the same reason test_engine_floor carries one.

    An engine that rendered nothing would satisfy every negative assertion
    below without rendering a single construct.
    """
    html = carve.to_html("# T\n\nBody.\n")
    assert "<h1" in html and "Body" in html


def test_a_cross_reference_differing_only_in_case_stays_literal():
    source = (
        "{#Getting-Started}\n# Getting Started\n\n"
        "See </#getting-started> and </#Getting-Started>.\n"
    )
    html = carve.to_html(source)
    assert "&lt;/#getting-started&gt;" in html, (
        f"carve-lang {_version()} resolved a cross-reference whose target "
        f"differs only in case: {html.strip()}"
    )
    # The matching spelling still resolves, so the assertion above is not
    # satisfied by cross-references having stopped working altogether.
    assert '<a href="#Getting-Started">' in html


def test_explicit_table_body_counts_are_consumed_not_published():
    source = "{header-rows=1 body-rows=1,1}\n| H | G |\n| a | b |\n| c | d |\n"
    html = carve.to_html(source)
    assert "body-rows=" not in html, (
        f"carve-lang {_version()} published the row-count metadata as an HTML "
        f"attribute on the table: {html.strip()}"
    )
    assert html.count("<tbody>") == 2, (
        f"carve-lang {_version()} assembled {html.count('<tbody>')} table "
        "bodies where the metadata names two"
    )


def test_a_named_container_opens_even_with_an_unseparated_metadata_slot():
    html = carve.to_html('::: note"Title\nBody.\n:::\n')
    assert "admonition" in html
    assert "::: note" not in html, (
        f"carve-lang {_version()} rendered the container opener as prose: "
        f"{html.strip()}"
    )


def test_a_fence_that_is_a_description_body_has_an_empty_payload():
    html = carve.to_html(":: t\n: ```\ncode\n```\n")
    assert "<pre><code></code></pre>" in html, (
        f"carve-lang {_version()} gave the empty fence payload content: "
        f"{html.strip()}"
    )


def test_a_mermaid_block_still_reaches_the_prerender_matcher_shape():
    """The path that broke in 0.1.2, kept under measurement rather than memory.

    The matcher's own behavior is covered by test_zensical_carve; what this adds
    is the engine end of the contract - the block still carries a `class` the
    matcher keys on, whatever else the engine has started writing beside it.
    """
    html = carve.to_html("``` mermaid\ngraph TD; A-->B;\n```\n", extensions=["fenced-render"])
    assert '<pre class="mermaid"' in html, (
        f"carve-lang {_version()} no longer emits a class-bearing <pre> for a "
        f"mermaid fence, so build-time prerendering would silently fall back: "
        f"{html.strip()}"
    )
