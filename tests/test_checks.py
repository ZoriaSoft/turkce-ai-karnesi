"""Unit tests for deterministic checks."""

import pytest

from turkce_karne.checks import evaluate_check, extract_json, task_score_value
from turkce_karne.model import CheckResult


def chk(t, resp, **spec):
    spec.setdefault("type", t)
    return evaluate_check(spec, resp)


# ---- contains / not_contains ----------------------------------------------


def test_contains_case_and_turkish_norm():
    r = chk("contains", "Bugün MARKETE DE gittim.", terms=["markete de"])
    assert r.passed


def test_contains_punctuation_insensitive():
    r = chk("contains", "Sayın Müdür, dilekçemi sunarım.", terms=["Sayın"])
    assert r.passed


def test_contains_missing_reports_detail():
    r = chk("contains", "hello", terms=["world"])
    assert not r.passed and r.detail["missing"] == ["world"]


def test_not_contains():
    assert chk("not_contains", "clean text", terms=["bad"]).passed
    assert not chk("not_contains", "this is bad", terms=["bad"]).passed


def test_contains_regex_mode():
    r = chk("contains", "the rate is 30%", terms=[r"\d+%"], mode="regex")
    assert r.passed


def test_turkish_dotted_i_normalization():
    # "I" should fold to dotless ı (Istanbul -> ıstanbul)
    r = chk("contains", "Istanbul'da yaşıyorum", terms=["ıstanbul"])
    assert r.passed
    r2 = chk("contains", "İSTANBUL büyük", terms=["istanbul"])
    assert r2.passed


# ---- word_order -----------------------------------------------------------


def test_word_order():
    r = chk(
        "word_order",
        "Kurum adı\nSayın Yetkili,\nMetin\nAli Veli",
        terms=["Sayın", "Ali Veli"],
    )
    assert r.passed
    r2 = chk(
        "word_order",
        "Ali Veli\nSayın Yetkili",
        terms=["Sayın", "Ali Veli"],
    )
    assert not r2.passed


# ---- answer_in ------------------------------------------------------------


def test_answer_in_last_line():
    resp = "Hesaplayalım: 2+2=4.\nCevap: 4"
    assert chk("answer_in", resp, answers=["Cevap: 4"]).passed
    assert not chk("answer_in", "Cevap: 5", answers=["Cevap: 4"]).passed


def test_answer_in_regex():
    resp = "açıklama\nCevap: 44 saat"
    assert chk("answer_in", resp, answers=[r"re:Cevap:\s*44\b"]).passed


def test_answer_in_line_first():
    resp = "B\nikinci satır"
    assert chk("answer_in", resp, answers=["B"], line="first").passed


# ---- line structure --------------------------------------------------------


def test_every_line_matches():
    resp = "1. bir\n2. iki\n3. üç"
    assert chk(
        "every_line_matches", resp, pattern=r"^\d\.\s", count=3
    ).passed
    bad = "1. bir\nmadde"
    r = chk("every_line_matches", bad, pattern=r"^\d\.\s")
    assert not r.passed and "bad_lines" in r.detail


def test_only_lines_with_prefix():
    assert chk(
        "only_lines_with_prefix",
        "- a\n- b\n- c",
        prefix="- ",
        count=3,
    ).passed
    assert not chk(
        "only_lines_with_prefix", "- a\nb", prefix="- "
    ).passed
    assert not chk(
        "only_lines_with_prefix", "", prefix="- "
    ).passed


# ---- count ----------------------------------------------------------------


def test_count_words():
    assert chk("count", "bir iki üç dört beş", unit="words", eq=5).passed
    assert chk("count", "kısa", unit="words", min=1, max=3).passed
    r = chk("count", "çok " * 30 + "fazla", unit="words", max=10)
    assert not r.passed


def test_count_sentences():
    t = "Bir cümle. İkinci cümle! Üçüncü?"
    assert chk("count", t, unit="sentences", eq=3).passed


def test_count_lines():
    assert chk("count", "a\nb\nc", unit="lines", eq=3).passed


# ---- boundaries / regex ----------------------------------------------------


def test_starts_ends_with():
    assert chk("starts_with", "Konu: Talep", value="Konu:").passed
    assert not chk("starts_with", "Merhaba", value="Konu:").passed
    assert chk("ends_with", "Saygılarımla.", value="Saygılarımla").passed


def test_regex_check():
    assert chk("regex", "Fatura No: ABC-12", pattern=r"ABC-\d+").passed
    r = chk("regex", "Fatura No: XYZ", pattern=r"ABC-\d+")
    assert not r.passed and r.detail["pattern"]


def test_regex_last_line_scope():
    resp = "önce uzun açıklama\nCevap: 42"
    assert chk(
        "regex", resp, pattern=r"^Cevap:\s*\d+$", scope="last_line"
    ).passed


# ---- json_fields -----------------------------------------------------------


def test_extract_json_fenced():
    resp = 'İşte veriler:\n```json\n{"a": 1, "b": {"c": 2}}\n```'
    assert extract_json(resp) == {"a": 1, "b": {"c": 2}}


def test_extract_json_prose():
    resp = 'Sonuç: {"x": 10} bitti.'
    assert extract_json(resp) == {"x": 10}


def test_extract_json_nested_braces_in_strings():
    resp = '{"a": "metin {iç} süslü", "b": 1}'
    assert extract_json(resp) == {"a": "metin {iç} süslü", "b": 1}


def test_json_fields_match():
    resp = '{"satici_unvan": "YILDIZ", "tutar": 869, "tarih": "12.10.2026"}'
    expected = {"satici_unvan": "Yıldız", "tutar": 869, "tarih": "2026-10-12"}
    r = chk("json_fields", resp, expected=expected)
    assert r.passed and r.fraction == 1.0


def test_json_fields_partial_credit():
    resp = '{"a": 1, "b": 2}'
    r = chk("json_fields", resp, expected={"a": 1, "b": 2, "c": 3})
    assert not r.passed and 0.6 < r.fraction < 0.7


def test_json_fields_required_subset():
    resp = '{"id": 5, "name": "x", "extra": 9}'
    r = chk(
        "json_fields",
        resp,
        expected={"id": 5, "name": "x"},
        required=["id", "name"],
    )
    assert r.passed


def test_json_fields_no_json():
    r = chk("json_fields", "düz metin", expected={"a": 1})
    assert not r.passed and r.detail["error"] == "no_json"


def test_json_fields_number_normalization():
    resp = '{"fiyat": "1.234,56", "oran": "%8"}'
    r = chk(
        "json_fields", resp, expected={"fiyat": 1234.56, "oran": 8}
    )
    assert r.passed


def test_json_fields_strict_rejects_extra_keys():
    resp = '{"a": 1, "b": 2, "yorum": "ekstra alan"}'
    r = chk("json_fields", resp, expected={"a": 1, "b": 2}, strict=True)
    assert not r.passed
    assert r.detail["extra"] == ["yorum"]
    assert r.fraction == 1.0  # all expected fields still matched


def test_json_fields_strict_passes_exact_keys():
    resp = '{"a": 1, "b": 2}'
    r = chk("json_fields", resp, expected={"a": 1, "b": 2}, strict=True)
    assert r.passed


def test_json_fields_strict_tolerates_nested_wrapper():
    # fields found under a wrapper object are alias-matched, not "extra"
    resp = '{"belge": {"tutar": 5, "tarih": "2026-10-12"}}'
    r = chk(
        "json_fields",
        resp,
        expected={"tutar": 5, "tarih": "2026-10-12"},
        strict=True,
    )
    assert r.passed


def test_json_fields_non_strict_ignores_extra():
    resp = '{"a": 1, "ek": "serbest"}'
    r = chk("json_fields", resp, expected={"a": 1})
    assert r.passed



# ---- turkish_share / no_refusal -------------------------------------------


def test_turkish_share():
    tr = "Bu metin Türkçe yazılmıştır ve içinde çok sayıda Türkçe kelime var."
    en = "This sentence is written entirely in English words only."
    assert chk("turkish_share", tr, min=0.5).passed
    assert not chk("turkish_share", en, min=0.5).passed


def test_no_refusal():
    assert chk("no_refusal", "İşte cevap.").passed
    assert not chk(
        "no_refusal", "Üzgünüm ama yardımcı olamam."
    ).passed


# ---- scoring ---------------------------------------------------------------


def test_task_score_value():
    rs = [CheckResult("a", True), CheckResult("b", False, fraction=0.5)]
    assert task_score_value(rs) == pytest.approx(0.75)
    assert task_score_value([]) == 0.0


# ---- written_form ----------------------------------------------------------


def test_written_form_passes():
    r = chk(
        "written_form",
        "Her şeyi tek başıma yaptım.",
        correct=["her şeyi"],
        incorrect=["herşey"],
    )
    assert r.passed and r.fraction == 1.0


def test_written_form_fails_when_error_kept():
    r = chk(
        "written_form",
        "Herşeyi tek başıma yaptım.",
        correct=["her şeyi"],
        incorrect=["herşey"],
    )
    assert not r.passed and r.fraction == 0.0


def test_written_form_partial_credit():
    r = chk(
        "written_form",
        "Markete de gittim, arabada bekliyordu.",
        correct=["markete de", "arabada"],
        incorrect=["marketede", "araba da "],
    )
    # 2 correct found, 0 incorrect -> passes
    assert r.passed
    r2 = chk(
        "written_form",
        "Markete de gittim, araba da bekliyordu.",
        correct=["markete de", "arabada"],
        incorrect=["marketede"],
    )
    # 1/2 correct found -> fraction 0.5, fails
    assert not r2.passed and r2.fraction == 0.5


def test_written_form_requires_correct():
    from turkce_karne.errors import CheckSpecError

    try:
        chk("written_form", "x")
    except CheckSpecError:
        pass
    else:
        raise AssertionError("expected CheckSpecError")

# ---- spelling_rules --------------------------------------------------------


def test_spelling_clean_text_passes():
    r = chk(
        "spelling_rules",
        "Bugünkü toplantıda her şey yolunda gitti; sen de geldin mi?",
    )
    assert r.passed and r.fraction == 1.0


def test_spelling_mi_attached():
    r = chk("spelling_rules", "Yarınki sınava geliyormusun?")
    assert not r.passed
    assert any("attached" in v for v in r.detail["violations"])


def test_spelling_mi_harmony_wrong_vowel():
    r = chk("spelling_rules", "Akşam mi geliyorsun?")
    assert not r.passed
    assert any("harmony" in v for v in r.detail["violations"])


def test_spelling_mi_harmony_skips_foreign():
    r = chk("spelling_rules", "Bu nota mi sesi değil, email mi geldi?")
    # 'email mi' is fine and 'nota mi' is solfège — zero violations
    assert r.passed


def test_spelling_ki_separate():
    r = chk("spelling_rules", "Bugün ki işler dün ki işlerden ağır.")
    assert not r.passed and len(r.detail["violations"]) == 2


def test_spelling_compound_traps():
    r = chk("spelling_rules", "Yanlız kaldı, herşeyi kendi yaptı.")
    assert not r.passed
    assert len(r.detail["violations"]) == 2
    # partial credit: 2 violations -> fraction 0.5
    assert r.fraction == 0.5


def test_spelling_does_not_flag_morphology():
    # accusative/possessive endings and evidential suffix are legal
    r = chk("spelling_rules", "Arabamı sattım, gelmişsin demişler.")
    assert r.passed


def test_spelling_rules_subset_and_allow():
    r = chk(
        "spelling_rules",
        "Akşam mi geldi, evde ki eşya duruyor.",
        rules=["mi_harmony"],
    )
    assert not r.passed and len(r.detail["violations"]) == 1
    r2 = chk(
        "spelling_rules",
        "Akşam mi geldi?",
        rules=["mi_harmony"],
        allow=["akşam"],
    )
    assert r2.passed


def test_spelling_rules_bad_rule_name():
    from turkce_karne.errors import CheckSpecError

    try:
        chk("spelling_rules", "x", rules=["nope"])
    except CheckSpecError:
        pass
    else:
        raise AssertionError("expected CheckSpecError")
