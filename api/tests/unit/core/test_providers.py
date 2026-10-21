import pytest

# Provider switches whose Part A value is a mock (§4.3, §4.7).
MOCK_SWITCHES = [
    ("PAYMENT_PROVIDER", "mock"),
    ("CARRIER_PROVIDER", "mock"),
    ("EMAIL_PROVIDER", "file"),
]


@pytest.mark.parametrize(
    ("switch", "mock"), MOCK_SWITCHES, ids=[s for s, _ in MOCK_SWITCHES]
)
def test_p1_v14_prod_rejects_mock(run_settings, prod_env, switch, mock):
    run = run_settings("config.settings.prod", {**prod_env, switch: mock})

    assert run.returncode != 0
    assert "ImproperlyConfigured" in run.stderr
    assert switch in run.stderr


def test_prod_starts_with_real_providers(run_settings, prod_env):
    run = run_settings("config.settings.prod", prod_env, ("PAYMENT_PROVIDER",))

    assert run.returncode == 0, run.stderr
    assert run.values == {"PAYMENT_PROVIDER": "mercadopago"}


def test_prod_requires_every_switch_explicitly(run_settings, prod_env):
    env = {k: v for k, v in prod_env.items() if k != "PAYMENT_PROVIDER"}

    run = run_settings("config.settings.prod", env)

    assert run.returncode != 0
    assert "ImproperlyConfigured" in run.stderr


@pytest.mark.parametrize("module", ["config.settings.dev", "config.settings.test"])
def test_dev_and_test_default_every_switch_to_its_mock(
    run_settings, secrets_env, module
):
    names = (
        "PAYMENT_PROVIDER",
        "CARRIER_PROVIDER",
        "EMAIL_PROVIDER",
        "MEDIA_STORAGE",
        "POSTAL_CODE_DATASET",
        "ERROR_TRACKING",
        "INVOICE_PROVIDER",
    )

    run = run_settings(module, secrets_env, names)

    assert run.returncode == 0, run.stderr
    assert run.values == {
        "PAYMENT_PROVIDER": "mock",
        "CARRIER_PROVIDER": "mock",
        "EMAIL_PROVIDER": "file",
        "MEDIA_STORAGE": "local",
        "POSTAL_CODE_DATASET": "sample",
        "ERROR_TRACKING": "off",
        "INVOICE_PROVIDER": "manual",
    }
