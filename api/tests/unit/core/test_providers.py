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


# Every registry switch: its setting name, the factory that reads it, its implementations.
REGISTRY_SWITCHES = [
    ("PAYMENT_PROVIDER", "payment_provider", "PAYMENT_IMPLS"),
    ("CARRIER_PROVIDER", "carrier", "CARRIER_IMPLS"),
    ("EMAIL_PROVIDER", "email_sender", "EMAIL_IMPLS"),
    ("ERROR_TRACKING", "error_reporter", "ERROR_IMPLS"),
    ("INVOICE_PROVIDER", "invoicer", "INVOICE_IMPLS"),
]


@pytest.mark.parametrize(
    ("setting", "factory", "impls"),
    REGISTRY_SWITCHES,
    ids=[s for s, _, _ in REGISTRY_SWITCHES],
)
def test_p1_v15_unknown_provider_value_rejected(use_provider, setting, factory, impls):
    from django.core.exceptions import ImproperlyConfigured

    from apps.core import providers

    use_provider(setting, "stripe")

    with pytest.raises(ImproperlyConfigured) as error:
        getattr(providers, factory)()

    message = str(error.value)
    assert setting in message
    assert "'stripe'" in message
    for allowed in getattr(providers, impls):
        assert repr(allowed) in message


def test_use_provider_switches_implementation_and_forgets_it(use_provider, monkeypatch):
    from apps.core import providers

    monkeypatch.setitem(providers.EMAIL_IMPLS, "file", "collections.OrderedDict")
    monkeypatch.setitem(providers.EMAIL_IMPLS, "ses", "collections.Counter")

    use_provider("EMAIL_PROVIDER", "file")
    first = providers.email_sender()
    assert type(first).__name__ == "OrderedDict"
    assert providers.email_sender() is first  # chosen once

    use_provider("EMAIL_PROVIDER", "ses")
    assert type(providers.email_sender()).__name__ == "Counter"


def test_registry_has_the_invoice_switch_with_only_the_manual_invoicer():
    from apps.core import providers

    assert providers.INVOICE_IMPLS == {"manual": "apps.invoicing.manual.ManualInvoicer"}
