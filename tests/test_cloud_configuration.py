import pytest

from zerowall.settings import Settings


@pytest.fixture
def cloud_env(monkeypatch, tmp_path):
    for name, value in {
        "ZEROWALL_MODE": "hosted",
        "ZEROWALL_STORAGE": "supabase",
        "ZEROWALL_DATA_DIR": str(tmp_path),
        "ZEROWALL_PUBLIC_ORIGIN": "https://council.example",
        "ZEROWALL_DIRECTOR_TOKEN": "private-cloud-test-access-code-32-characters",
        "ZEROWALL_DATABASE_URL": "postgresql://owner:placeholder@db.example:5432/postgres?sslmode=require",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SECRET_KEY": "test-only-server-key",
        "ZEROWALL_PERSISTENT_STORAGE_CONFIRMED": "false",
    }.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_cloud_cache_does_not_claim_to_be_a_persistent_volume(cloud_env):
    settings = Settings()
    assert settings.hosting.hosted
    assert settings.role == "web"
    assert settings.database_url
    assert settings.policy["council_default_models"] == [
        "nvidia/Nemotron-3.5-Super-VL",
        "reflection/beam",
        "deepseek-ai/DeepSeek-V4-Flash-0731",
    ]


@pytest.mark.parametrize(
    "key,value",
    [
        ("ZEROWALL_DATABASE_URL", ""),
        (
            "ZEROWALL_DATABASE_URL",
            "postgresql://owner:placeholder@db.example:6543/postgres?sslmode=require",
        ),
        (
            "ZEROWALL_DATABASE_URL",
            "postgresql://owner:placeholder@db.example:5432/postgres",
        ),
        ("SUPABASE_URL", "http://example.supabase.co"),
        ("SUPABASE_SECRET_KEY", ""),
        ("ZEROWALL_ROLE", "typo"),
        ("ZEROWALL_PUBLIC_ORIGIN", "https://user:password@council.example"),
        ("ZEROWALL_PUBLIC_ORIGIN", "https://council.example/path"),
    ],
)
def test_cloud_configuration_fails_closed_without_local_fallback(cloud_env, key, value):
    cloud_env.setenv(key, value)
    with pytest.raises(ValueError):
        Settings()
