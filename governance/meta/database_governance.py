"""
Database Governance Layer
=========================

SessionBound-inspired lightweight database governance for AI agent
database access. Provides query complexity limits, row limits, sensitive
field masking, and budget-aware session management.

SessionBound Reference: https://github.com/SessionBound/sessionbound
  "Turn Enterprise Task Approval into Budgeted Database Sessions"

Architecture:
    AI Agent proposes database query
        → DatabaseGovernance.evaluate(query, session_budget)
            → QueryParser: estimates cost (rows, joins, complexity)
            → QueryGuard: checks complexity limit, row limit
            → SensitiveFieldMask: masks PII/sensitive columns
            → SessionBudget: tracks remaining budget, enforces quota
        → ALLOW (pass through) / DENY (block) / MASK (modify) / WARN (log + allow)

Usage:
    governance = DatabaseGovernance(
        max_rows_per_query=1000,
        max_query_budget=10000,
        sensitive_fields=["email", "phone", "ssn", "credit_card"],
    )
    session = governance.create_session(task_id="task-001", budget=5000)
    result = governance.evaluate("SELECT * FROM users", session)
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ── Enums ────────────────────────────────────────────────────────────────────

class QueryAction(str, Enum):
    """Actions a database governance check can produce."""
    ALLOW = "allow"         # Query is safe, execute as-is
    DENY = "deny"           # Query is too expensive/dangerous, block
    MASK = "mask"           # Query allowed but results must be masked
    AUGMENT = "augment"     # Add LIMIT / safety clauses to query
    BUDGET_EXCEEDED = "budget_exceeded"  # Query budget exhausted


class QuerySeverity(str, Enum):
    """Severity classification of a database query."""
    READ_ONLY = "read_only"           # SELECT with basic conditions
    AGGREGATE = "aggregate"           # SELECT with GROUP BY, HAVING, aggregates
    JOIN_COMPLEX = "join_complex"     # SELECT with multiple JOINs
    WRITE = "write"                   # INSERT, UPDATE, DELETE
    DDL = "ddl"                       # CREATE, ALTER, DROP, TRUNCATE
    DESTRUCTIVE = "destructive"       # DROP TABLE, DELETE without WHERE, etc.


class QueryType(str, Enum):
    """Type of SQL query."""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    OTHER = "OTHER"


# ── Session Budget ───────────────────────────────────────────────────────────

@dataclass
class DatabaseSession:
    """A budgeted database session — SessionBound concept.

    Each session has:
      - A total budget (e.g., 10000 "query units")
      - Automatic depletion on each query
      - Warnings/alerts when approaching budget limit
    """
    session_id: str
    task_id: str = ""
    total_budget: int = 10000
    remaining_budget: int = field(default=-1)  # -1 = unset, sync in __post_init__
    queries_executed: int = 0
    queries_blocked: int = 0
    rows_returned_total: int = 0
    is_active: bool = True

    def __post_init__(self):
        if self.remaining_budget < 0:
            self.remaining_budget = self.total_budget

    def consume(self, cost: int) -> bool:
        """Consume budget units. Returns False if budget exceeded."""
        if cost > self.remaining_budget:
            return False
        self.remaining_budget -= cost
        self.queries_executed += 1
        return True

    def budget_used_pct(self) -> float:
        """Percentage of budget consumed."""
        if self.total_budget == 0:
            return 100.0
        return 100.0 * (self.total_budget - self.remaining_budget) / self.total_budget

    def is_near_limit(self, threshold_pct: float = 80.0) -> bool:
        """Check if approaching budget limit."""
        return self.budget_used_pct() >= threshold_pct

    def reset(self, new_budget: int | None = None):
        """Reset session with optional new budget."""
        if new_budget is not None:
            self.total_budget = new_budget
        self.remaining_budget = self.total_budget
        self.queries_executed = 0
        self.queries_blocked = 0
        self.rows_returned_total = 0
        self.is_active = True

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "total_budget": self.total_budget,
            "remaining_budget": self.remaining_budget,
            "budget_used_pct": round(self.budget_used_pct(), 1),
            "queries_executed": self.queries_executed,
            "queries_blocked": self.queries_blocked,
            "rows_returned_total": self.rows_returned_total,
            "is_active": self.is_active,
            "near_limit": self.is_near_limit(),
        }


# ── Query Estimation ─────────────────────────────────────────────────────────

@dataclass
class QueryEstimate:
    """Estimated cost and characteristics of a SQL query."""
    query_type: QueryType = QueryType.SELECT
    severity: QuerySeverity = QuerySeverity.READ_ONLY
    estimated_rows: int = 0
    estimated_cost: int = 0       # Abstract "query units"
    table_count: int = 1
    join_count: int = 0
    has_where: bool = False
    has_limit: bool = False
    has_unsafe: bool = False      # DROP, TRUNCATE, DELETE without WHERE
    sensitive_fields_detected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class QueryParser:
    """Lightweight SQL query parser for cost estimation.

    Not a full SQL parser — uses keyword detection for governance-relevant
    features. Production deployments should integrate a real SQL parser
    (e.g., sqlparse, sqlglot) for accurate analysis.
    """

    DESTRUCTIVE_KEYWORDS = {"drop", "truncate", "delete from"}
    DDL_KEYWORDS = {"create table", "alter table", "drop table", "truncate table"}
    WRITE_KEYWORDS = {"insert into", "update ", "delete "}
    AGGREGATE_KEYWORDS = {"group by", "having", "count(", "sum(", "avg(",
                          "min(", "max(", "distinct"}

    _SENSITIVE_PATTERNS: list[tuple[str, str]] = [
        ("email", "email"),
        ("phone", "phone"),
        ("ssn", "ssn"),
        ("password", "password"),
        ("credit_card", "credit_card"),
        ("credit", "credit"),
        ("salary", "salary"),
        ("address", "address"),
        ("social_security", "social_security"),
        ("passport", "passport"),
        ("token", "token"),
        ("secret", "secret"),
    ]

    @classmethod
    def estimate(cls, query: str) -> QueryEstimate:
        """Parse a SQL query and estimate its cost/complexity."""
        q = query.strip().lower()

        # ── Determine query type ──────────────────────────────────────
        _type_map = [
            (QueryType.TRUNCATE, "truncate"),
            (QueryType.DROP, "drop "),
            (QueryType.ALTER, "alter "),
            (QueryType.CREATE, "create "),
            (QueryType.DELETE, "delete "),
            (QueryType.UPDATE, "update "),
            (QueryType.INSERT, "insert "),
            (QueryType.SELECT, "select "),
        ]
        query_type = QueryType.OTHER
        for t, prefix in _type_map:
            if q.startswith(prefix):
                query_type = t
                break

        # ── Determine severity ────────────────────────────────────────
        is_destructive = any(kw in q for kw in cls.DESTRUCTIVE_KEYWORDS) and (
            query_type not in (QueryType.DROP, QueryType.TRUNCATE)
        )
        is_ddl = any(kw in q for kw in cls.DDL_KEYWORDS)
        is_write = any(kw in q for kw in cls.WRITE_KEYWORDS) and not is_ddl
        is_aggregate = any(kw in q for kw in cls.AGGREGATE_KEYWORDS)

        if is_ddl:
            severity = QuerySeverity.DDL
        elif is_destructive:
            severity = QuerySeverity.DESTRUCTIVE
        elif is_write:
            severity = QuerySeverity.WRITE
        elif "join" in q:
            severity = QuerySeverity.JOIN_COMPLEX
        elif is_aggregate:
            severity = QuerySeverity.AGGREGATE
        else:
            severity = QuerySeverity.READ_ONLY

        # ── Estimate cost ─────────────────────────────────────────────
        estimated_rows = 100  # Default for small tables
        if "where" not in q and query_type == QueryType.SELECT:
            estimated_rows = 10000  # Full table scan risk
        if "join" in q:
            estimated_rows *= 2  # Joins amplify row count

        cost = estimated_rows
        if is_aggregate:
            cost *= 2
        if is_write:
            cost *= 3
        if is_ddl:
            cost *= 50       # DDL is very expensive
        elif is_destructive:
            cost = 99999  # Effectively infinite

        # ── Detect sensitive fields ───────────────────────────────────
        sensitive = []
        for name, pattern in cls._SENSITIVE_PATTERNS:
            if pattern in q:
                sensitive.append(name)

        # ── Warnings ──────────────────────────────────────────────────
        warnings = []
        if not q.lower().startswith("select") and "where" not in q:
            warnings.append("Write operation without WHERE clause — may affect all rows")
        if estimated_rows > 5000:
            warnings.append(f"Estimated {estimated_rows} rows — consider adding LIMIT")
        if is_destructive:
            warnings.append("DESTRUCTIVE OPERATION DETECTED")

        # ── Count tables and joins ────────────────────────────────────
        table_count = q.count(" from ") + (1 if q.count(" join ") > 0 else 0)
        join_count = q.count(" join ")

        return QueryEstimate(
            query_type=query_type,
            severity=severity,
            estimated_rows=estimated_rows,
            estimated_cost=cost,
            table_count=table_count,
            join_count=join_count,
            has_where="where" in q,
            has_limit="limit" in q,
            has_unsafe=is_destructive or is_ddl,
            sensitive_fields_detected=sensitive,
            warnings=warnings,
        )


# ── Query Result ─────────────────────────────────────────────────────────────

@dataclass
class QueryGovernanceResult:
    """Result of database governance evaluation."""
    query: str
    estimate: QueryEstimate
    action: QueryAction
    reason: str
    session_state: dict | None = None
    modified_query: str | None = None
    masked_fields: list[str] = field(default_factory=list)
    cost_consumed: int = 0

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "severity": self.estimate.severity.value,
            "query_type": self.estimate.query_type.value,
            "estimated_cost": self.estimate.estimated_cost,
            "estimated_rows": self.estimate.estimated_rows,
            "sensitive_fields": self.estimate.sensitive_fields_detected,
            "warnings": self.estimate.warnings,
            "modified_query": self.modified_query,
            "masked_fields": self.masked_fields,
            "cost_consumed": self.cost_consumed,
        }


# ── Database Governance ──────────────────────────────────────────────────────

@dataclass
class DatabaseGovernanceConfig:
    """Configuration for DatabaseGovernance."""
    max_rows_per_query: int = 1000
    max_query_budget: int = 10000
    max_joins: int = 5
    sensitive_fields: list[str] = field(default_factory=lambda: [
        "email", "phone", "ssn", "password", "credit_card",
        "salary", "address", "token", "secret",
    ])
    block_ddl: bool = True
    block_destructive: bool = True
    auto_augment_limit: bool = True   # Auto-add LIMIT to queries without one
    warn_budget_pct: float = 80.0     # Warn when budget used exceeds this %


class DatabaseGovernance:
    """SessionBound-inspired database governance engine.

    Evaluates SQL queries against:
      - Complexity limits (rows, joins, query cost)
      - Session budget (remaining query units)
      - Sensitive field masking
      - Destructive operation blocking

    Example:
        gov = DatabaseGovernance(
            max_rows_per_query=500,
            block_destructive=True,
        )
        session = gov.create_session("task-approval-42", budget=5000)
        result = gov.evaluate("SELECT name, email FROM users", session)
        if result.action == QueryAction.ALLOW:
            execute_query(result.query)
    """

    def __init__(self, config: DatabaseGovernanceConfig | None = None):
        self.config = config or DatabaseGovernanceConfig()
        self._sessions: dict[str, DatabaseSession] = {}
        self._total_queries_evaluated: int = 0
        self._total_queries_blocked: int = 0
        self._total_budget_consumed: int = 0

    # ── Session Management ─────────────────────────────────────────────

    def create_session(
        self, task_id: str, budget: int | None = None
    ) -> DatabaseSession:
        """Create a new budgeted database session."""
        session_id = f"db-session-{len(self._sessions) + 1:04d}"
        session = DatabaseSession(
            session_id=session_id,
            task_id=task_id,
            total_budget=budget or self.config.max_query_budget,
            remaining_budget=budget or self.config.max_query_budget,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> DatabaseSession | None:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if session:
            session.is_active = False

    # ── Query Evaluation ───────────────────────────────────────────────

    def evaluate(
        self,
        query: str,
        session: DatabaseSession | None = None,
    ) -> QueryGovernanceResult:
        """Evaluate a SQL query and return governance decision.

        Pipeline:
          1. Parse query → estimate cost, severity, sensitive fields
          2. Check destructive/DDL operations
          3. Check complexity limits (rows, joins)
          4. Check session budget
          5. Check sensitive fields → mask if needed
          6. Augment query with LIMIT if missing

        Args:
            query: Raw SQL query string
            session: Optional session for budget tracking

        Returns:
            QueryGovernanceResult with ALLOW/DENY/MASK/AUGMENT action
        """
        self._total_queries_evaluated += 1
        estimate = QueryParser.estimate(query)

        # ── Check 1: Destructive operations ─────────────────────────
        if self.config.block_destructive and estimate.has_unsafe:
            self._total_queries_blocked += 1
            if session:
                session.queries_blocked += 1
            return QueryGovernanceResult(
                query=query,
                estimate=estimate,
                action=QueryAction.DENY,
                reason=f"Destructive operation blocked: {estimate.severity.value}",
            )

        # ── Check 2: DDL operations ─────────────────────────────────
        if self.config.block_ddl and estimate.severity == QuerySeverity.DDL:
            self._total_queries_blocked += 1
            if session:
                session.queries_blocked += 1
            return QueryGovernanceResult(
                query=query,
                estimate=estimate,
                action=QueryAction.DENY,
                reason=f"DDL operation blocked: {estimate.severity.value}",
            )

        # ── Check 3: Row limit ──────────────────────────────────────
        if estimate.estimated_rows > self.config.max_rows_per_query:
            if self.config.auto_augment_limit:
                # Augment query with safety LIMIT
                augmented = self._augment_limit(query, self.config.max_rows_per_query)
                estimate.estimated_rows = self.config.max_rows_per_query
                estimate.warnings.append(
                    f"Query augmented with LIMIT {self.config.max_rows_per_query}"
                )
                # Continue with augmented query
                query = augmented
            else:
                self._total_queries_blocked += 1
                if session:
                    session.queries_blocked += 1
                return QueryGovernanceResult(
                    query=query,
                    estimate=estimate,
                    action=QueryAction.DENY,
                    reason=f"Row limit exceeded: estimated {estimate.estimated_rows} > max {self.config.max_rows_per_query}",
                )

        # ── Check 4: Join limit ─────────────────────────────────────
        if estimate.join_count > self.config.max_joins:
            self._total_queries_blocked += 1
            if session:
                session.queries_blocked += 1
            return QueryGovernanceResult(
                query=query,
                estimate=estimate,
                action=QueryAction.DENY,
                reason=f"Join limit exceeded: {estimate.join_count} > max {self.config.max_joins}",
            )

        # ── Check 5: Session budget ─────────────────────────────────
        cost = estimate.estimated_cost
        if session:
            if not session.is_active:
                return QueryGovernanceResult(
                    query=query,
                    estimate=estimate,
                    action=QueryAction.DENY,
                    reason="Session is not active",
                    session_state=session.to_dict(),
                )

            if session.is_near_limit(self.config.warn_budget_pct):
                estimate.warnings.append(
                    f"Budget nearing limit: {session.budget_used_pct():.0f}% used"
                )

            if not session.consume(cost):
                self._total_queries_blocked += 1
                session.queries_blocked += 1
                return QueryGovernanceResult(
                    query=query,
                    estimate=estimate,
                    action=QueryAction.BUDGET_EXCEEDED,
                    reason=f"Session budget exceeded: cost {cost} > remaining {session.remaining_budget}",
                    session_state=session.to_dict(),
                )

            session.rows_returned_total += estimate.estimated_rows
            self._total_budget_consumed += cost

        # ── Check 6: Sensitive fields ───────────────────────────────
        masked = []
        for field in estimate.sensitive_fields_detected:
            if field in self.config.sensitive_fields:
                masked.append(field)

        if masked:
            return QueryGovernanceResult(
                query=query,
                estimate=estimate,
                action=QueryAction.MASK,
                reason=f"Sensitive fields detected: {', '.join(masked)}",
                masked_fields=masked,
                cost_consumed=cost,
                session_state=session.to_dict() if session else None,
            )

        # ── All checks passed ───────────────────────────────────────
        result = QueryGovernanceResult(
            query=query,
            estimate=estimate,
            action=QueryAction.ALLOW,
            reason="Query passed all governance checks",
            cost_consumed=cost,
            session_state=session.to_dict() if session else None,
        )
        # If query was augmented, record it
        if query != result.query:
            result.modified_query = query
        return result

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _augment_limit(query: str, limit: int) -> str:
        """Add LIMIT clause to a SELECT query if not present."""
        q = query.rstrip(";").rstrip()
        if "limit" in q.lower():
            return q
        return f"{q} LIMIT {limit}"

    # ── Observability ──────────────────────────────────────────────────

    def get_state(self) -> dict:
        """Get observability state."""
        sessions_state = {
            sid: s.to_dict() for sid, s in self._sessions.items()
        }
        return {
            "module": "DatabaseGovernance",
            "total_queries_evaluated": self._total_queries_evaluated,
            "total_queries_blocked": self._total_queries_blocked,
            "block_rate_pct": round(
                100.0 * self._total_queries_blocked / max(self._total_queries_evaluated, 1), 1
            ),
            "total_budget_consumed": self._total_budget_consumed,
            "active_sessions": sum(1 for s in self._sessions.values() if s.is_active),
            "total_sessions": len(self._sessions),
            "sessions": sessions_state,
            "config": {
                "max_rows_per_query": self.config.max_rows_per_query,
                "max_query_budget": self.config.max_query_budget,
                "max_joins": self.config.max_joins,
                "block_ddl": self.config.block_ddl,
                "block_destructive": self.config.block_destructive,
                "auto_augment_limit": self.config.auto_augment_limit,
            },
        }

    def reset_stats(self):
        """Reset statistics counters."""
        self._total_queries_evaluated = 0
        self._total_queries_blocked = 0
        self._total_budget_consumed = 0
