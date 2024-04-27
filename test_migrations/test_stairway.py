import pytest

from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.script import Script, ScriptDirectory
from db_utils import alembic_config_from_url
from config import settings

# Получаем revision миграций
def get_revisions():
    config = alembic_config_from_url()

    revisions_dir = ScriptDirectory.from_config(config)

    revisions = list(revisions_dir.walk_revisions("base", "heads"))
    revisions.reverse()
    return revisions

# Тестирование работы upgrade и downgrade
@pytest.mark.parametrize("revision", get_revisions())
def test_migrations_stairway(alembic_config: Config, revision: Script):
    upgrade(alembic_config, revision.revision)

    downgrade(alembic_config, revision.down_revision or "-1")
    upgrade(alembic_config, revision.revision)
