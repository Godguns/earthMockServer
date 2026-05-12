from app.core.config import Settings


def test_cors_origins_supports_comma_separated_env() -> None:
    settings = Settings(
        cors_origins="http://150.158.43.80,http://localhost:5173",
    )

    assert settings.cors_origins == [
        "http://150.158.43.80",
        "http://localhost:5173",
    ]


def test_cors_origins_supports_json_array_env() -> None:
    settings = Settings(
        cors_origins='["http://150.158.43.80", "http://localhost:5173"]',
    )

    assert settings.cors_origins == [
        "http://150.158.43.80",
        "http://localhost:5173",
    ]
