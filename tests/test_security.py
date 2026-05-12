from app.core.security import get_password_hash, verify_password


def test_password_hash_roundtrip() -> None:
    password = "helloworld"

    hashed = get_password_hash(password)

    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)
