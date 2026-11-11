from kalkan.detection.normalizer import normalize, turkish_lower


def test_turkish_lower_dotted_dotless():
    assert turkish_lower("İSTANBUL") == "istanbul"
    assert turkish_lower("ILIK") == "ılık"


def test_folds_diacritics_homoglyphs_zero_width():
    attack = "önс\u200beki tаlimatları"  # Cyrillic с and а, zero-width space
    assert normalize(attack).folded == "onceki talimatlari"


def test_deleet_and_spacing():
    assert "talimatlari" in normalize("t4l1m4tl4r1").folded
    assert "yoksay" in normalize("y o k s a y").folded


def test_numbers_in_normal_text_survive():
    assert "2026" in normalize("Toplantı 2026 yılında").folded
