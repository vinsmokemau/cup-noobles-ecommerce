"""P15-V13 and P15-V14 (T15.5): the offline run. `make test-all-offline` builds and pulls every
image, then runs `make test-all` with the project network internal, and the CI job
`clean-clone-offline` does it from a fresh checkout. These tests read the compose files, the
Makefile and the workflow; the run itself is that CI job, and `p15_v13` in web/e2e/ is the check
made from inside the network."""

import json
import re

import yaml

from tests.architecture.test_e2e_stack import repo_root, services
from tests.architecture.test_suite_config import read_makefile, rule

COMPOSE_FILES = ("docker-compose.yml", "docker-compose.e2e.yml")
OFFLINE_FILE = "docker-compose.offline.yml"
RUNNERS = {
    "e2e": "service:proxy",
    "e2e-api-down": "service:web-api-down",
    "e2e-lighthouse": "service:proxy-prod",
}


def compose(name: str) -> dict:
    return yaml.safe_load((repo_root() / name).read_text(encoding="utf-8"))


def test_p15_v14_the_offline_override_makes_the_project_network_internal():
    offline = compose(OFFLINE_FILE)
    assert offline["networks"] == {"default": {"internal": True}}
    # The override adds no service and no way out. Its one other line gives the api a fixed
    # address for the name P1-V13 connects to, so that test reaches the socket guard without DNS.
    assert offline["services"] == {"api": {"extra_hosts": ["example.com:203.0.113.1"]}}
    assert set(offline) == {"networks", "services"}


def test_p15_v14_every_container_is_on_the_project_network_alone():
    # A service with a network of its own, or the host's, would get around the override.
    for name in COMPOSE_FILES:
        assert "networks" not in compose(name), name
        for service, definition in services(name).items():
            mode = definition.get("network_mode")
            assert mode is None or mode.startswith("service:"), (name, service)
            assert set(definition.get("networks", {"default": None})) == {"default"}, (
                name,
                service,
            )


def test_p15_v14_the_e2e_image_is_pinned_to_the_playwright_version():
    package = json.loads(
        (repo_root() / "web" / "package.json").read_text(encoding="utf-8")
    )
    version = package["devDependencies"]["@playwright/test"]
    dockerfile = (repo_root() / "web" / "Dockerfile.e2e").read_text(encoding="utf-8")
    (image,) = re.findall(r"^FROM (\S+)", dockerfile, re.MULTILINE)
    assert image == f"mcr.microsoft.com/playwright:v{version}-noble"

    # Every runner is that image, on the network of the service it tests, and never started by `up`.
    defined = services("docker-compose.e2e.yml")
    assert {name for name in defined if name.startswith("e2e")} == set(RUNNERS)
    for name, network in RUNNERS.items():
        runner = defined[name]
        assert runner["build"]["dockerfile"] == "Dockerfile.e2e"
        assert runner["network_mode"] == network
        assert runner["profiles"]


def test_p15_v14_test_all_offline_gets_the_images_first_then_runs_test_all_offline():
    makefile = read_makefile()
    found = rule(makefile, "test-all-offline")
    assert found is not None
    recipe = found[1]
    run = recipe.index("$(MAKE) test-all OFFLINE=1")
    # The network steps come first, and the stack is down before the internal network is made.
    assert recipe.index("pull") < recipe.index("build") < run
    assert recipe.index("$(STACK_DOWN)") < run
    # Every image: the profiles of docker-compose.e2e.yml are named, or their images would be
    # built later, when the network is already internal.
    images = re.search(r"^IMAGES_DC := (?:[^\n]*\\\n)*[^\n]*", makefile, re.MULTILINE)
    assert images is not None
    profiles = {
        profile
        for definition in services("docker-compose.e2e.yml").values()
        for profile in definition.get("profiles", [])
    }
    scheduler_off = set(services("docker-compose.e2e.yml")["scheduler"]["profiles"])
    for profile in profiles - scheduler_off:
        assert f"--profile {profile}" in images[0], profile

    clone = rule(makefile, "clean-clone-check")
    assert clone is not None
    assert "git clone" in clone[1]
    assert "$(MAKE) test-all-offline" in clone[1]


def test_p15_v14_offline_puts_the_override_on_every_compose_command():
    makefile = read_makefile()
    branch = re.search(
        r"^ifeq \(\$\(OFFLINE\),1\)\n(?P<on>.*?)^else\n(?P<off>.*?)^endif\n",
        makefile,
        re.MULTILINE | re.DOTALL,
    )
    assert branch is not None
    assert f"OFFLINE_FILE := -f {OFFLINE_FILE}" in branch["on"]
    (offline_dc,) = re.findall(r"^DC\s+:= ([^\n]*)", branch["on"], re.MULTILINE)
    assert "$(OFFLINE_FILE)" in offline_dc
    assert OFFLINE_FILE not in branch["off"]
    (e2e_dc,) = re.findall(r"^E2E_DC := ([^\n]*)", makefile, re.MULTILINE)
    assert "$(OFFLINE_FILE)" in e2e_dc
    # No compose command of the Makefile leaves the two variables out, except the image step,
    # which runs before the network is internal.
    bare = [
        line
        for line in makefile.splitlines()
        if "docker compose" in line
        and not line.lstrip().startswith("#")
        and not re.match(r"^(DC|E2E_DC|IMAGES_DC)\s*:= ", line)
    ]
    assert bare == []


def test_p15_v13_the_offline_run_tells_the_spec_the_network_is_internal():
    makefile = read_makefile()
    branch = re.search(
        r"^ifeq \(\$\(OFFLINE\),1\)\n(?P<on>.*?)^else\n",
        makefile,
        re.MULTILINE | re.DOTALL,
    )
    assert branch is not None
    assert "E2E_OFFLINE  := -e E2E_OFFLINE=1" in branch["on"]
    assert "E2E_RUN     := run --rm -T $(E2E_OFFLINE)" in makefile
    found = rule(makefile, "e2e-all")
    assert found is not None
    assert "$(E2E_RUN) e2e pnpm exec playwright test $(PW_MAIN)" in found[1]
    # The spec runs in a project of PW_MAIN, and skips only without that variable.
    assert "--project=selftest" in makefile
    spec = (repo_root() / "web" / "e2e" / "p15_offline.spec.ts").read_text(
        encoding="utf-8"
    )
    assert "p15_v13 internal network blocks egress" in spec
    assert "!process.env.E2E_OFFLINE" in spec
    config = (repo_root() / "web" / "playwright.config.ts").read_text(encoding="utf-8")
    assert "p15_offline" in config


def test_p15_v14_ci_runs_the_offline_job_from_a_fresh_checkout():
    workflow = yaml.safe_load(
        (repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["clean-clone-offline"]["steps"]
    # Checkout, then the run: nothing is installed on the runner in between.
    assert steps[0]["uses"].startswith("actions/checkout@")
    assert steps[1]["name"] == "p15_v14 clean clone passes test-all offline"
    assert "make test-all-offline" in steps[1]["run"]


def test_g69_only_the_e2e_override_gives_the_database_its_alias():
    # Inside the `e2e` service Playwright has no Docker CLI: it asks the network for `db-e2e`.
    assert services("docker-compose.e2e.yml")["db"]["networks"]["default"][
        "aliases"
    ] == ["db-e2e"]
    assert "networks" not in services("docker-compose.yml")["db"]
    guard = (repo_root() / "web" / "e2e" / "e2e-database.ts").read_text(
        encoding="utf-8"
    )
    assert "E2E_DATABASE_ALIAS = 'db-e2e'" in guard
