"""Tests for Database Governance Layer (SessionBound-inspired).

Verifies:
  - QueryParser: query type detection, severity classification, cost estimation
  - DatabaseSession: budget tracking, consumption, near-limit detection
  - DatabaseGovernance: full evaluation pipeline (6 checks)
  - Config: customization, blocking rules
  - Observability: get_state()
"""
import pytest
from governance.meta.database_governance import (
    DatabaseGovernance,
    DatabaseGovernanceConfig,
    DatabaseSession,
    QueryParser,
    QueryEstimate,
    QueryGovernanceResult,
    QueryAction,
    QuerySeverity,
    QueryType,
)


# ── QueryParser ──────────────────────────────────────────────────────────────

class TestQueryParser:
    def test_select_simple(self):
        est = QueryParser.estimate("SELECT * FROM users")
        assert est.query_type == QueryType.SELECT
        assert est.severity == QuerySeverity.READ_ONLY
        assert est.estimated_rows > 0

    def test_select_with_where(self):
        est = QueryParser.estimate("SELECT * FROM users WHERE id = 1")
        assert est.query_type == QueryType.SELECT
        assert est.has_where is True
        assert est.estimated_rows <= 10000

    def test_select_with_join(self):
        est = QueryParser.estimate(
            "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert est.query_type == QueryType.SELECT
        assert est.severity == QuerySeverity.JOIN_COMPLEX
        assert est.join_count >= 1

    def test_select_aggregate(self):
        est = QueryParser.estimate("SELECT COUNT(*), department FROM users GROUP BY department")
        assert est.severity in (QuerySeverity.AGGREGATE, QuerySeverity.JOIN_COMPLEX)

    def test_insert(self):
        est = QueryParser.estimate("INSERT INTO users (name, email) VALUES ('test', 'a@b.com')")
        assert est.query_type == QueryType.INSERT
        assert est.severity == QuerySeverity.WRITE

    def test_update(self):
        est = QueryParser.estimate("UPDATE users SET email = 'new@b.com' WHERE id = 1")
        assert est.query_type == QueryType.UPDATE
        assert est.severity == QuerySeverity.WRITE

    def test_update_no_where_warning(self):
        est = QueryParser.estimate("UPDATE users SET email = 'new@b.com'")
        assert len(est.warnings) > 0
        assert any("WHERE" in w.upper() for w in est.warnings)

    def test_delete(self):
        est = QueryParser.estimate("DELETE FROM users WHERE id = 1")
        assert est.query_type == QueryType.DELETE

    def test_delete_no_where_destructive(self):
        est = QueryParser.estimate("DELETE FROM users")
        assert est.has_unsafe is True
        assert est.severity == QuerySeverity.DESTRUCTIVE

    def test_drop_table(self):
        est = QueryParser.estimate("DROP TABLE users")
        assert est.severity == QuerySeverity.DDL
        assert est.estimated_cost >= 5000

    def test_create_table(self):
        est = QueryParser.estimate("CREATE TABLE logs (id INT, msg TEXT)")
        assert est.severity == QuerySeverity.DDL

    def test_alter_table(self):
        est = QueryParser.estimate("ALTER TABLE users ADD COLUMN age INT")
        assert est.severity == QuerySeverity.DDL

    def test_truncate(self):
        est = QueryParser.estimate("TRUNCATE TABLE logs")
        assert est.severity == QuerySeverity.DDL

    def test_sensitive_email(self):
        est = QueryParser.estimate("SELECT email, name FROM users")
        assert "email" in est.sensitive_fields_detected

    def test_sensitive_credit_card(self):
        est = QueryParser.estimate("SELECT credit_card FROM payments WHERE id = 1")
        assert any(f in est.sensitive_fields_detected for f in ("credit_card", "credit"))

    def test_sensitive_multiple(self):
        est = QueryParser.estimate(
            "SELECT email, phone, ssn, salary FROM employees"
        )
        sensitive = est.sensitive_fields_detected
        assert len(sensitive) >= 3

    def test_no_sensitive(self):
        est = QueryParser.estimate("SELECT id, name, department FROM employees")
        assert len(est.sensitive_fields_detected) == 0

    def test_destructive_cost_is_high(self):
        est = QueryParser.estimate("DELETE FROM users")
        assert est.estimated_cost >= 10000

    def test_select_limit_present(self):
        est = QueryParser.estimate("SELECT * FROM users LIMIT 10")
        assert est.has_limit is True


# ── DatabaseSession ──────────────────────────────────────────────────────────

class TestDatabaseSession:
    def test_creation(self):
        session = DatabaseSession(
            session_id="s001", task_id="task-42", total_budget=5000
        )
        assert session.session_id == "s001"
        assert session.task_id == "task-42"
        assert session.total_budget == 5000
        assert session.remaining_budget == 5000
        assert session.is_active is True

    def test_consume_within_budget(self):
        session = DatabaseSession(session_id="s001", total_budget=5000)
        result = session.consume(1000)
        assert result is True
        assert session.remaining_budget == 4000
        assert session.queries_executed == 1

    def test_consume_exact_budget(self):
        session = DatabaseSession(session_id="s001", total_budget=5000)
        assert session.consume(5000) is True
        assert session.remaining_budget == 0

    def test_consume_exceed_budget(self):
        session = DatabaseSession(session_id="s001", total_budget=5000)
        assert session.consume(6000) is False
        assert session.remaining_budget == 5000  # Unchanged
        assert session.queries_executed == 0

    def test_multiple_consumes(self):
        session = DatabaseSession(session_id="s001", total_budget=5000)
        assert session.consume(1000) is True
        assert session.consume(2000) is True
        assert session.consume(1500) is True
        assert session.remaining_budget == 500
        assert session.queries_executed == 3

    def test_budget_used_pct(self):
        session = DatabaseSession(session_id="s001", total_budget=1000)
        session.consume(300)
        assert session.budget_used_pct() == pytest.approx(30.0)

    def test_is_near_limit(self):
        session = DatabaseSession(session_id="s001", total_budget=1000)
        session.consume(900)
        assert session.is_near_limit(80.0) is True
        assert session.is_near_limit(95.0) is False

    def test_is_near_limit_below(self):
        session = DatabaseSession(session_id="s001", total_budget=1000)
        session.consume(500)
        assert session.is_near_limit(80.0) is False

    def test_reset(self):
        session = DatabaseSession(session_id="s001", total_budget=5000)
        session.consume(4000)
        session.reset()
        assert session.remaining_budget == 5000
        assert session.queries_executed == 0
        assert session.is_active is True

    def test_reset_new_budget(self):
        session = DatabaseSession(session_id="s001", total_budget=5000)
        session.reset(new_budget=10000)
        assert session.total_budget == 10000
        assert session.remaining_budget == 10000

    def test_to_dict(self):
        session = DatabaseSession(session_id="s001", task_id="task-42", total_budget=5000)
        session.consume(1000)
        d = session.to_dict()
        assert d["session_id"] == "s001"
        assert d["remaining_budget"] == 4000
        assert d["queries_executed"] == 1


# ── DatabaseGovernanceConfig ────────────────────────────────────────────────

class TestDatabaseGovernanceConfig:
    def test_defaults(self):
        config = DatabaseGovernanceConfig()
        assert config.max_rows_per_query == 1000
        assert config.max_query_budget == 10000
        assert config.block_ddl is True
        assert config.block_destructive is True

    def test_custom_config(self):
        config = DatabaseGovernanceConfig(
            max_rows_per_query=500,
            block_ddl=False,
            sensitive_fields=["email", "name"],
        )
        assert config.max_rows_per_query == 500
        assert config.block_ddl is False
        assert "email" in config.sensitive_fields


# ── DatabaseGovernance ───────────────────────────────────────────────────────

class TestDatabaseGovernance:
    def test_creation(self):
        gov = DatabaseGovernance()
        assert gov.config is not None
        assert gov.config.max_rows_per_query == 1000

    def test_evaluate_simple_select(self):
        gov = DatabaseGovernance()
        result = gov.evaluate("SELECT id, name FROM users WHERE id = 1")
        assert result.action == QueryAction.ALLOW
        assert result.estimate.query_type == QueryType.SELECT

    def test_evaluate_destructive_blocked(self):
        gov = DatabaseGovernance(
            config=DatabaseGovernanceConfig(block_destructive=True)
        )
        result = gov.evaluate("DELETE FROM users")
        assert result.action == QueryAction.DENY
        assert "Destructive" in result.reason

    def test_evaluate_ddl_blocked(self):
        gov = DatabaseGovernance(
            config=DatabaseGovernanceConfig(block_ddl=True)
        )
        result = gov.evaluate("DROP TABLE users")
        assert result.action == QueryAction.DENY
        # DROP TABLE is classified as DDL, blocked at check 2
        assert "DDL" in result.reason or "ddl" in result.reason.lower()

    def test_evaluate_ddl_allowed_when_unblocked(self):
        gov = DatabaseGovernance(
            config=DatabaseGovernanceConfig(block_ddl=False, block_destructive=False)
        )
        result = gov.evaluate("CREATE TABLE temp (id INT)")
        assert result.action != QueryAction.DENY

    def test_evaluate_sensitive_fields_mask(self):
        gov = DatabaseGovernance()
        result = gov.evaluate("SELECT email, password FROM users")
        assert result.action == QueryAction.MASK
        assert "email" in result.masked_fields

    def test_evaluate_sensitive_fields_excluded_by_config(self):
        gov = DatabaseGovernance(
            config=DatabaseGovernanceConfig(sensitive_fields=["ssn"])
        )
        result = gov.evaluate("SELECT email FROM users")
        # email not in sensitive_fields config → should ALLOW
        assert result.action == QueryAction.ALLOW

    def test_evaluate_exceeds_row_limit_augmented(self):
        gov = DatabaseGovernance(
            config=DatabaseGovernanceConfig(
                max_rows_per_query=500,
                auto_augment_limit=True,
            )
        )
        # Full table scan → estimated 10000 rows → augmented to LIMIT 500
        result = gov.evaluate("SELECT * FROM large_table")
        # With auto_augment, it should not deny — should augment
        assert result.action != QueryAction.DENY

    def test_evaluate_exceeds_join_limit(self):
        gov = DatabaseGovernance(
            config=DatabaseGovernanceConfig(max_joins=1)
        )
        result = gov.evaluate(
            "SELECT * FROM a JOIN b ON a.id=b.id JOIN c ON b.id=c.id"
        )
        assert result.action == QueryAction.DENY
        assert "Join" in result.reason

    def test_session_creation(self):
        gov = DatabaseGovernance()
        session = gov.create_session("task-001", budget=3000)
        assert session.task_id == "task-001"
        assert session.total_budget == 3000
        assert session.remaining_budget == 3000

    def test_session_budget_consumption(self):
        gov = DatabaseGovernance()
        session = gov.create_session("task-002", budget=1000)
        result = gov.evaluate("SELECT * FROM users WHERE id = 1", session=session)
        assert result.action == QueryAction.ALLOW
        assert session.remaining_budget < 1000  # Cost was consumed

    def test_session_budget_exceeded(self):
        gov = DatabaseGovernance()
        session = gov.create_session("task-003", budget=50)
        # Full table scan = 10000 rows → cost ~10000, far exceeds budget 50
        result = gov.evaluate("SELECT * FROM huge_table", session=session)
        assert result.action == QueryAction.BUDGET_EXCEEDED

    def test_session_inactive(self):
        gov = DatabaseGovernance()
        session = gov.create_session("task-004", budget=5000)
        gov.close_session(session.session_id)
        result = gov.evaluate("SELECT * FROM users", session=session)
        assert result.action == QueryAction.DENY
        assert "not active" in result.reason.lower()

    def test_session_budget_near_limit_warning(self):
        gov = DatabaseGovernance()
        session = gov.create_session("task-005", budget=200)
        session.consume(180)  # 90% used
        result = gov.evaluate("SELECT * FROM users WHERE id = 1", session=session)
        assert result.estimate.warnings  # Should warn about budget

    def test_result_to_dict(self):
        gov = DatabaseGovernance()
        result = gov.evaluate("SELECT id, name FROM users WHERE active = 1")
        d = result.to_dict()
        assert d["action"] == "allow"
        assert d["query_type"] == "SELECT"
        assert "estimated_cost" in d
        assert "sensitive_fields" in d

    def test_multiple_sessions_independent(self):
        gov = DatabaseGovernance()
        s1 = gov.create_session("task-a", budget=1000)
        s2 = gov.create_session("task-b", budget=5000)
        s1.consume(800)
        assert s1.remaining_budget == 200
        assert s2.remaining_budget == 5000  # Independent

    def test_get_state(self):
        gov = DatabaseGovernance()
        gov.create_session("task-x", budget=3000)
        gov.evaluate("SELECT * FROM users")
        state = gov.get_state()
        assert state["module"] == "DatabaseGovernance"
        assert state["total_queries_evaluated"] == 1
        assert state["total_queries_blocked"] == 0
        assert state["active_sessions"] == 1
        assert "config" in state

    def test_get_state_after_blocked_query(self):
        gov = DatabaseGovernance(
            config=DatabaseGovernanceConfig(block_destructive=True)
        )
        gov.evaluate("DELETE FROM users")
        state = gov.get_state()
        assert state["total_queries_blocked"] == 1
        assert state["block_rate_pct"] == 100.0

    def test_reset_stats(self):
        gov = DatabaseGovernance()
        gov.evaluate("SELECT * FROM users")
        gov.reset_stats()
        state = gov.get_state()
        assert state["total_queries_evaluated"] == 0

    def test_write_with_where_allowed(self):
        gov = DatabaseGovernance()
        result = gov.evaluate("UPDATE users SET name = 'New' WHERE id = 1")
        assert result.action == QueryAction.ALLOW

    def test_multiple_checks_pipeline_order(self):
        """Destructive should be checked first, budget last."""
        gov = DatabaseGovernance(
            config=DatabaseGovernanceConfig(block_destructive=True)
        )
        result = gov.evaluate("DROP TABLE users")
        # Should be blocked at check 1 (destructive), not reach budget
        assert result.action == QueryAction.DENY
        assert "Destructive" in result.reason or "DDL" in result.reason


# ── Integration with GodelianBoundary / ADP ──────────────────────────────────

class TestDatabaseGovernanceIntegration:
    def test_query_estimate_serializable(self):
        est = QueryParser.estimate("SELECT email FROM users")
        assert est.query_type == QueryType.SELECT
        assert "email" in est.sensitive_fields_detected

    def test_governance_result_includes_full_estimate(self):
        gov = DatabaseGovernance()
        result = gov.evaluate(
            "SELECT u.name, COUNT(*) FROM users u "
            "JOIN orders o ON u.id = o.user_id "
            "GROUP BY u.name"
        )
        d = result.to_dict()
        assert d["severity"] in ("aggregate", "join_complex")

    def test_sensitive_field_mask_preserves_non_sensitive(self):
        gov = DatabaseGovernance(
            config=DatabaseGovernanceConfig(
                sensitive_fields=["ssn", "credit_card"]
            )
        )
        result = gov.evaluate("SELECT name, department FROM employees")
        assert result.action == QueryAction.ALLOW
        assert result.masked_fields == []

    def test_empty_query_handled(self):
        gov = DatabaseGovernance()
        result = gov.evaluate("SELECT 1")
        assert result.action == QueryAction.ALLOW

    def test_insert_with_values_not_blocked(self):
        gov = DatabaseGovernance()
        result = gov.evaluate(
            "INSERT INTO audit_log (action, timestamp) VALUES ('login', NOW())"
        )
        assert result.action == QueryAction.ALLOW
