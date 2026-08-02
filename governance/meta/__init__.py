"""Meta-governance module: complete P0-P4 meta-governance suite."""
from governance.meta.meta_theory_consistency import ConsistencyChecker
from governance.meta.monotonic_constraint import MonotonicConstraint
from governance.meta.fixed_point_detector import (
    ConvergenceReport, ConvergenceState, EvolutionConvergenceGuard,
    FixedPointDetector, StateSnapshot,
)
from governance.meta.godelian_boundary import (
    GodelianBoundary, GodelianVerdict, Proposition, BoundaryReport,
    PropositionGenerator, RealityBridgeRouter,
)
from governance.meta.meta_cognitive_loop import (
    DecisionLog, FailurePattern, GapReport, LoopPhase, LoopTrace,
    MetaCognitiveLoop, SelfCheckBenchmark, Strategy, StrategyType,
)
from governance.meta.self_check_engine import (
    SelfCheckEngine, SelfCheckReport, ContradictionNode,
    CompletenessGap, TrustRoot, TrustRootType, GapSeverity as SelfCheckGapSeverity,
)
from governance.meta.digital_twin_calibrator import (
    DigitalTwinCalibrator, CalibrationReport, CalibrationState,
    GapDimension, GapSample, RealityAnchor, SensorReading,
)
from governance.meta.config_loader import (
    ConfigLoader, MetaConfig, FPDConfig, GBConfig, MCLConfig,
)
from governance.meta.adp_taxonomy import (
    ADPClassification, AutonomyLevel, DecisionType, RiskLevel,
    Reversibility, map_to_adp,
)
from governance.meta.reality_bridge import (
    ExtendedRealityBridgeRouter, TaGHookRegistry, TaGHook, TaGHookType,
    TaGHookAction, TaGHookResult, TaGRoutingResult,
)

__all__ = [
    # P0
    "ConsistencyChecker", "MonotonicConstraint",
    # Phase 1
    "FixedPointDetector", "ConvergenceState", "ConvergenceReport",
    "StateSnapshot", "EvolutionConvergenceGuard",
    # Phase 2
    "GodelianBoundary", "GodelianVerdict", "Proposition",
    "BoundaryReport", "PropositionGenerator", "RealityBridgeRouter",
    # ADP
    "ADPClassification", "AutonomyLevel", "DecisionType", "RiskLevel",
    "Reversibility", "map_to_adp",
    # RealityBridge + TaG
    "ExtendedRealityBridgeRouter", "TaGHookRegistry", "TaGHook",
    "TaGHookType", "TaGHookAction", "TaGHookResult", "TaGRoutingResult",
    # Phase 3
    "MetaCognitiveLoop", "DecisionLog", "FailurePattern", "GapReport",
    "LoopPhase", "LoopTrace", "SelfCheckBenchmark", "Strategy", "StrategyType",
    # P3
    "SelfCheckEngine", "SelfCheckReport", "ContradictionNode",
    "CompletenessGap", "TrustRoot", "TrustRootType", "SelfCheckGapSeverity",
    # P4
    "DigitalTwinCalibrator", "CalibrationReport", "CalibrationState",
    "GapDimension", "GapSample", "RealityAnchor", "SensorReading",
    # Config
    "ConfigLoader", "MetaConfig", "FPDConfig", "GBConfig", "MCLConfig",
]
