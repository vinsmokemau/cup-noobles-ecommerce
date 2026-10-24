"""Migration harness: the full round trip and the `migrator` fixture (SPEC.md §4.6)."""

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def applied() -> set[tuple[str, str]]:
    return set(MigrationExecutor(connection).loader.applied_migrations)


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_all_migrations_reversible():
    """Latest state, back to zero, forward again; always leaves the database migrated."""
    latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
    zero = [(app, None) for app in sorted({app for app, _ in latest})]
    try:
        MigrationExecutor(connection).migrate(zero)
        assert applied() == set()
    finally:
        MigrationExecutor(connection).migrate(latest)
    assert set(latest) <= applied()


@pytest.mark.django_db(transaction=True)
def test_migrator_applies_a_migration_forward_and_backward(migrator):
    """The django-test-migrations fixture works, so data migrations can be tested per task."""
    old_state = migrator.apply_initial_migration(("auth", None))
    with pytest.raises(LookupError):
        old_state.apps.get_model("auth", "Group")
    new_state = migrator.apply_tested_migration(("auth", "0001_initial"))
    assert new_state.apps.get_model("auth", "Group").objects.count() == 0
    migrator.reset()


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_p2_v07_round_trip():
    """Empty to latest to zero to latest: every `RunSQL` reverses and no model change is unmigrated."""
    latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
    zero = [(app, None) for app in sorted({app for app, _ in latest})]
    try:
        MigrationExecutor(connection).migrate(zero)
        assert applied() == set()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename <> 'django_migrations'"
            )
            assert cursor.fetchone() == (0,), "a reversed migration left a table behind"
    finally:
        MigrationExecutor(connection).migrate(latest)
    assert set(latest) <= applied()
    call_command("makemigrations", check=True, dry_run=True, verbosity=0)
