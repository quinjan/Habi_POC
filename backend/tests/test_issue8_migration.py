from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.tests.db import postgres_test_database_url, reset_postgres_test_database


def test_issue_8_migration_converts_legacy_purchase_line_and_provider_category(monkeypatch):
    database_url = postgres_test_database_url()
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    monkeypatch.setenv("HABI_DATABASE_URL", database_url)
    config = Config("backend/alembic.ini")

    try:
        command.upgrade(config, "20260710_0007")
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO project_workspaces (
                        id, project_name, project_type, location, completion_year,
                        floor_area, trade_scopes, client_or_owner, notes
                    ) VALUES (
                        1, 'Legacy Project', 'Residential', 'Makati', 2025,
                        NULL, '[]', NULL, NULL
                    );
                    INSERT INTO taxonomy_nodes (
                        id, project_workspace_id, parent_id, name, normalized_name
                    ) VALUES
                        (1, 1, NULL, 'Plumbing', 'plumbing'),
                        (2, 1, 1, 'Pipes', 'pipes');
                    INSERT INTO memory_records (
                        id, project_workspace_id, record_type, display_name,
                        normalized_name, taxonomy_node_id, status
                    ) VALUES
                        (1, 1, 'material', 'PVC pipe', 'pvc pipe', 2, 'active'),
                        (2, 1, 'provider', 'ABC Trading', 'abc trading', 2, 'active'),
                        (3, 1, 'purchase_line', 'PVC pipe', 'pvc pipe', 2, 'active');
                    INSERT INTO materials (id, memory_record_id) VALUES (1, 1);
                    INSERT INTO providers (id, memory_record_id) VALUES (1, 2);
                    INSERT INTO purchase_lines (
                        id, project_workspace_id, memory_record_id, item_memory_record_id,
                        provider_memory_record_id, item_or_service_name, line_type,
                        provider_name, provider_type, provider_role, quantity, unit,
                        unit_state, price, currency, price_state, purchase_date,
                        date_state, category_path
                    ) VALUES (
                        1, 1, 3, 1, 2, 'PVC pipe', 'material', 'ABC Trading',
                        'external', 'material_supplier', '20', 'pcs', 'known',
                        '1500', 'PHP', 'known', '2025-07-12', 'known',
                        'Plumbing / Pipes'
                    );
                    SELECT setval('taxonomy_nodes_id_seq', 2, true);
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.begin() as connection:
            contractor_assigned = connection.scalar(
                text("SELECT contractor_assigned FROM project_workspaces WHERE id = 1")
            )
            concept_link = connection.execute(
                text(
                    "SELECT purchase_line_id, concept_memory_record_id, concept_type "
                    "FROM purchase_line_concept_links"
                )
            ).one()
            provider_category = connection.execute(
                text(
                    """
                    SELECT parent.name, child.name
                    FROM memory_records AS provider
                    JOIN taxonomy_nodes AS child ON child.id = provider.taxonomy_node_id
                    JOIN taxonomy_nodes AS parent ON parent.id = child.parent_id
                    WHERE provider.id = 2
                    """
                )
            ).one()
            purchase_line_columns = {
                column["name"] for column in inspect(connection).get_columns("purchase_lines")
            }
            table_names = set(inspect(connection).get_table_names())
            taxonomy_decision_columns = {
                column["name"]
                for column in inspect(connection).get_columns("taxonomy_decisions")
            }

        assert contractor_assigned == "Internal"
        assert tuple(concept_link) == (1, 1, "material")
        assert tuple(provider_category) == ("Providers", "General")
        assert "provider_state" in purchase_line_columns
        assert "item_memory_record_id" not in purchase_line_columns
        assert "category_path" not in purchase_line_columns
        assert "taxonomy_gates" in table_names
        assert {
            "taxonomy_gate_id",
            "candidate_id",
            "accepted_source",
            "superseded",
            "superseded_at",
        } <= taxonomy_decision_columns
    finally:
        engine.dispose()
        reset_postgres_test_database(database_url)
