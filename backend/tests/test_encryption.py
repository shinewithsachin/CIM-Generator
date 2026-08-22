import encryption


def test_bytes_round_trip() -> None:
    original = b"confidential financial data \x00\xff"
    token = encryption.encrypt_bytes(original)
    assert token != original
    assert encryption.decrypt_bytes(token) == original


def test_text_round_trip() -> None:
    original = "sk-super-secret-api-key"
    token = encryption.encrypt_text(original)
    assert token != original
    assert encryption.decrypt_text(token) == original


def test_empty_text_round_trip() -> None:
    assert encryption.encrypt_text("") == ""
    assert encryption.decrypt_text("") == ""


def test_decrypt_invalid_token_returns_empty_string() -> None:
    assert encryption.decrypt_text("not-a-real-token") == ""
