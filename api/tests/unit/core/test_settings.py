import pytest

ARGON2 = "django.contrib.auth.hashers.Argon2PasswordHasher"
MD5 = "django.contrib.auth.hashers.MD5PasswordHasher"


def test_p1_v16_prod_forces_dev_tools_off(run_settings, prod_env):
    run = run_settings(
        "config.settings.prod",
        {**prod_env, "DEV_TOOLS_ENABLED": "true"},
        ("DEV_TOOLS_ENABLED",),
    )

    assert run.returncode == 0, run.stderr
    assert run.values == {"DEV_TOOLS_ENABLED": False}


def test_p1_v18_prod_hasher_is_argon2(run_settings, prod_env, secrets_env):
    prod = run_settings("config.settings.prod", prod_env, ("PASSWORD_HASHERS",))
    test = run_settings("config.settings.test", secrets_env, ("PASSWORD_HASHERS",))

    assert prod.returncode == 0, prod.stderr
    assert prod.values["PASSWORD_HASHERS"][0] == ARGON2
    assert test.returncode == 0, test.stderr
    assert test.values["PASSWORD_HASHERS"][0] == MD5


def test_prod_security_settings(run_settings, prod_env):
    names = (
        "DEBUG",
        "SECURE_HSTS_SECONDS",
        "SECURE_SSL_REDIRECT",
        "SESSION_COOKIE_SECURE",
        "CSRF_COOKIE_SECURE",
        "SESSION_COOKIE_SAMESITE",
        "SECURE_PROXY_SSL_HEADER",
        "ALLOWED_HOSTS",
        "CSRF_TRUSTED_ORIGINS",
    )

    run = run_settings("config.settings.prod", prod_env, names)

    assert run.returncode == 0, run.stderr
    values = run.values
    assert values["DEBUG"] is False
    assert values["SECURE_HSTS_SECONDS"] > 0
    assert values["SECURE_SSL_REDIRECT"] is True
    assert values["SESSION_COOKIE_SECURE"] is True
    assert values["CSRF_COOKIE_SECURE"] is True
    assert values["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert values["SECURE_PROXY_SSL_HEADER"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert values["ALLOWED_HOSTS"] == ["cupnoobles.example"]
    assert values["CSRF_TRUSTED_ORIGINS"] == ["https://cupnoobles.example"]


@pytest.mark.parametrize("missing", ["ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS"])
def test_prod_requires_hosts_and_origins(run_settings, prod_env, missing):
    env = {k: v for k, v in prod_env.items() if k != missing}

    run = run_settings("config.settings.prod", env)

    assert run.returncode != 0
    assert missing in run.stderr


@pytest.mark.parametrize(
    "module", ["config.settings.dev", "config.settings.test", "config.settings.prod"]
)
@pytest.mark.parametrize("missing", ["SECRET_KEY", "DATABASE_URL"])
def test_secrets_come_only_from_the_environment(
    run_settings, prod_env, module, missing
):
    env = {k: v for k, v in prod_env.items() if k != missing}

    run = run_settings(module, env)

    assert run.returncode != 0
    assert missing in run.stderr


@pytest.mark.parametrize("module", ["config.settings.dev", "config.settings.test"])
def test_dev_tools_are_on_in_dev_and_test(run_settings, secrets_env, module):
    run = run_settings(module, secrets_env, ("DEV_TOOLS_ENABLED",))

    assert run.returncode == 0, run.stderr
    assert run.values == {"DEV_TOOLS_ENABLED": True}
