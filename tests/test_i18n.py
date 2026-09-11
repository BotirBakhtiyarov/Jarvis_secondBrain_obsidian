from orion import i18n


def test_default_language_is_english():
    i18n.set_language("en")
    assert i18n.get_language() == "en"
    assert i18n.t("thinking") == "Thinking…"


def test_set_language_switches_translations():
    i18n.set_language("uz")
    assert i18n.t("thinking") == "O'ylamoqda…"
    assert i18n.t("user_title") == "Siz"


def test_unknown_language_falls_back_to_english():
    i18n.set_language("xx-not-a-language")
    assert i18n.get_language() == "en"
    assert i18n.t("thinking") == "Thinking…"


def test_unknown_key_renders_key_name():
    i18n.set_language("en")
    assert i18n.t("no.such.key") == "no.such.key"


def test_t_formats_with_kwargs():
    i18n.set_language("en")
    assert i18n.t("cost_summary", t="12.3k", c="0.0042") == "Tokens: 12.3k · Cost: $0.0042"


def test_translations_have_identical_keys():
    i18n.set_language("en")
    en_keys = set(i18n.TRANSLATIONS["en"])
    uz_keys = set(i18n.TRANSLATIONS["uz"])
    assert en_keys == uz_keys


def test_detect_language():
    assert i18n.detect_language("This is a plain English sentence.") == "en"
    assert i18n.detect_language("Привет, как дела?") == "ru"
    assert i18n.detect_language("Men bugun o'quv bilan shug'ullandim.") == "uz"
    assert i18n.detect_language("") is None
    assert i18n.detect_language("   ") is None
