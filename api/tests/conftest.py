import pytest

from apps.core import providers


@pytest.fixture
def use_provider(settings):
    """Switch a provider setting for one test: `use_provider("PAYMENT_PROVIDER", "mock")`.

    Applies the setting override and clears the registry caches, so no chosen
    implementation leaks into another test (SPEC.md §4.3).
    """

    def apply(setting: str, value: str) -> None:
        setattr(settings, setting, value)
        providers.clear_provider_caches()

    yield apply
    providers.clear_provider_caches()
