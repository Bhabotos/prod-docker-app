"""Static guarantees about migration files: additive, BMI schema only."""
import re
from pathlib import Path

VERSIONS = sorted((Path(__file__).resolve().parents[2] / "db_migrations" / "versions").glob("*.py"))


def test_there_is_at_least_one_migration():
    assert VERSIONS


def test_migrations_only_touch_the_bmi_schema_and_never_drop_outside_downgrade():
    for path in VERSIONS:
        src = path.read_text()
        upgrade, _, downgrade = src.partition("def downgrade")
        assert "public" not in re.sub(r'""".*?"""', "", src, flags=re.S), f"{path.name} mentions the public schema"
        assert "op.execute" not in src, f"{path.name}: raw SQL is not allowed; use schema-qualified op.* calls"
        for forbidden in ("drop_table", "drop_column", "alter_column", "drop_constraint", "drop_index", "rename_table", "DROP "):
            assert forbidden not in upgrade, f"{path.name}: upgrade() must be additive, found {forbidden}"
        creates = re.findall(r"op\.create_table\(", upgrade)
        assert len(creates) == len(re.findall(r"schema=S\b", upgrade)), f"{path.name}: every create_table needs schema=S"
        assert 'S = "bmi"' in src
        for dropped in re.findall(r'op\.drop_table\("(\w+)", schema=(\w+)\)', downgrade):
            assert dropped[1] == "S", f"{path.name}: downgrade must qualify the schema"
