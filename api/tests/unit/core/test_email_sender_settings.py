import pytest

NAMES = ("DEFAULT_FROM_EMAIL", "EMAIL_REPLY_TO")


def test_dev_defaults_are_a_noreply_sender_and_a_separate_reply_to(
    run_settings, secrets_env
):
    run = run_settings("config.settings.dev", secrets_env, NAMES)

    assert run.returncode == 0, run.stderr
    sender, reply_to = run.values["DEFAULT_FROM_EMAIL"], run.values["EMAIL_REPLY_TO"]
    assert sender.startswith("noreply@")
    assert sender.endswith(".test")
    assert reply_to.endswith(".test")
    assert reply_to != sender


def test_prod_reads_the_sender_and_reply_to_from_the_environment(
    run_settings, prod_env
):
    run = run_settings("config.settings.prod", prod_env, NAMES)

    assert run.returncode == 0, run.stderr
    assert run.values == {
        "DEFAULT_FROM_EMAIL": prod_env["DEFAULT_FROM_EMAIL"],
        "EMAIL_REPLY_TO": prod_env["EMAIL_REPLY_TO"],
    }


@pytest.mark.parametrize("missing", NAMES)
def test_prod_requires_the_sender_and_reply_to(run_settings, prod_env, missing):
    env = {k: v for k, v in prod_env.items() if k != missing}

    run = run_settings("config.settings.prod", env)

    assert run.returncode != 0
    assert missing in run.stderr
