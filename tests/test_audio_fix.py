from companion.audio_fix import u_law_encoding


def test_u_law_stays_in_byte_range() -> None:
    values = [u_law_encoding(s) for s in range(-32768, 32768, 3)]
    assert min(values) >= 0
    assert max(values) <= 255


def test_u_law_full_scale_negative_does_not_wrap() -> None:
    assert u_law_encoding(-32768) == 255
