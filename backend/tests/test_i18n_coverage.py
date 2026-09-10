"""Guards the contract between the parser's rejection codes and the UI dictionary.

The frontend renders each rejection by looking up `err_<code>`. TypeScript
checks that Kazakh covers every Russian key, but nothing on either side notices
when the backend gains a code the UI has never heard of -- the reader silently
gets untranslated Russian prose. This test closes that gap.
"""

import re
from pathlib import Path

import pytest

from app.parsers.csv_1c import REASON_TEMPLATES

I18N = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n.ts"


@pytest.fixture(scope="module")
def i18n_source() -> str:
    if not I18N.exists():
        pytest.skip(f"frontend dictionary not present at {I18N}")
    return I18N.read_text(encoding="utf-8")


def keys_for(source: str, dictionary: str) -> set[str]:
    """Collect err_* keys declared inside one dictionary literal."""
    start = source.index(dictionary)
    end = source.index("};", start)
    return set(re.findall(r"^\s*(err_\w+):", source[start:end], re.MULTILINE))


def test_russian_dictionary_covers_every_rejection_code(i18n_source: str):
    declared = keys_for(i18n_source, "const ru = {")
    expected = {f"err_{code}" for code in REASON_TEMPLATES}

    assert expected - declared == set(), "codes the UI cannot translate"


def test_kazakh_dictionary_covers_every_rejection_code(i18n_source: str):
    declared = keys_for(i18n_source, "const kk: Record<Key, string> = {")
    expected = {f"err_{code}" for code in REASON_TEMPLATES}

    assert expected - declared == set(), "codes missing a Kazakh translation"


def test_the_ui_declares_no_codes_the_backend_never_emits(i18n_source: str):
    """A stale key is dead weight and usually means a code was renamed."""
    declared = keys_for(i18n_source, "const ru = {")
    expected = {f"err_{code}" for code in REASON_TEMPLATES}

    assert declared - expected == set(), "dictionary entries for unknown codes"


def test_translations_use_only_placeholders_the_backend_supplies(i18n_source: str):
    """A {placeholder} with no matching param renders literally to the reader."""
    for dictionary in ("const ru = {", "const kk: Record<Key, string> = {"):
        start = i18n_source.index(dictionary)
        end = i18n_source.index("};", start)
        body = i18n_source[start:end]

        for code, template in REASON_TEMPLATES.items():
            match = re.search(rf'^\s*err_{code}:\s*"([^"]*)"', body, re.MULTILINE)
            if match is None:
                continue
            backend_params = set(re.findall(r"\{(\w+)\}", template))
            ui_params = set(re.findall(r"\{(\w+)\}", match.group(1)))
            assert ui_params <= backend_params, (
                f"{dictionary.split()[1]} err_{code} uses {ui_params - backend_params}, "
                f"which the backend never sends"
            )
