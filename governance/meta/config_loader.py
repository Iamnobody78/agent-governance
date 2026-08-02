"""
ConfigLoader — YAML-based configuration for meta modules
==========================================================
Reads governance/meta/meta_modules_config.yaml and exposes structured
config objects for FixedPointDetector, GodelianBoundary, and MetaCognitiveLoop.

Supports:
  - Default values (no external dependency on pyyaml — uses manual YAML parser)
  - Runtime reloading
  - Environment variable overrides
"""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Config Data Structures ───────────────────────────────────────────────────

@dataclass
class FPDConfig:
    """FixedPointDetector configuration."""
    epsilon: float = 0.01
    patience: int = 3
    window_size: int = 5
    oscillation_threshold: float = 0.001
    divergence_factor: float = 2.0
    suspicion_perturbation_rounds: int = 5
    max_suspicion_triggers: int = 10
    perturbation_epsilon_greedy_boost: float = 0.3
    perturbation_noise_sigma: float = 0.05
    perturbation_annealing_gamma: float = 0.95


@dataclass
class GBConfig:
    """GodelianBoundary configuration."""
    self_ref_threshold: float = 0.25
    undecidable_threshold: float = 0.60
    max_delegations: int = 10
    compress_to_abdl: bool = True


@dataclass
class MCLConfig:
    """MetaCognitiveLoop configuration."""
    decision_buffer_size: int = 1000
    cycle_history_size: int = 50
    max_bold_strategies: int = 3
    max_conservative_strategies: int = 5
    bold_risk_threshold: float = 0.6
    require_godelian_check: bool = True
    max_self_check_failures: int = 3


@dataclass
class MetaConfig:
    """Aggregated configuration for all meta modules."""
    fpd: FPDConfig = field(default_factory=FPDConfig)
    gb: GBConfig = field(default_factory=GBConfig)
    mcl: MCLConfig = field(default_factory=MCLConfig)
    source: str = "defaults"


# ── Lightweight YAML Parser ──────────────────────────────────────────────────

class SimpleYAMLLoader:
    """Minimal YAML loader that avoids pyyaml dependency.

    Handles nested dicts, lists, floats, ints, bools, and strings.
    Designed for the specific structure of meta_modules_config.yaml.
    """

    @classmethod
    def load(cls, path: str | Path) -> dict:
        """Load a simple YAML file into a nested dict."""
        with open(path, encoding="utf-8") as f:
            content = f.read()
        return cls._parse(content)

    @classmethod
    def _parse(cls, content: str) -> dict:
        """Parse YAML content into a nested dict."""
        result = {}
        stack: list[dict] = [result]
        path: list[str] = []
        last_indent = -1

        for line in content.splitlines():
            stripped = line.rstrip()
            if not stripped or stripped.startswith("#") or stripped.startswith("---"):
                continue

            indent = len(line) - len(line.lstrip())
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip() if value else ""

            # Track nesting
            if indent < last_indent:
                # Pop back to correct level
                levels_to_pop = (last_indent - indent) // 2 + 1
                for _ in range(levels_to_pop):
                    if len(stack) > 1:
                        stack.pop()
                        if path:
                            path.pop()
                # Also pop path entries
                while len(stack) <= len(path):
                    path.pop()
            elif indent == last_indent and path:
                # Same level, sibling key
                path[-1] = key
            elif indent > last_indent:
                # Child
                if path:
                    parent_key = path[-1]
                else:
                    parent_key = key
                if parent_key not in stack[-1]:
                    stack[-1][parent_key] = {}

                stack.append(stack[-1][parent_key])
                path.append(key)

            last_indent = indent

            # Parse value
            if value:
                stack[-1][key] = cls._parse_value(value)
            elif not value:
                # Section header — will be filled by children
                if key and key not in stack[-1]:
                    stack[-1][key] = {}

        return result

    @staticmethod
    def _parse_value(value: str):
        """Parse a scalar YAML value."""
        # Boolean
        if value.lower() in ("true", "yes", "on"):
            return True
        if value.lower() in ("false", "no", "off"):
            return False
        # Null
        if value.lower() in ("null", "~", ""):
            return None
        # Integer
        try:
            return int(value)
        except ValueError:
            pass
        # Float
        try:
            return float(value)
        except ValueError:
            pass
        # String (strip quotes)
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
        return value


# ── Config Loader ────────────────────────────────────────────────────────────

class ConfigLoader:
    """Load meta module configuration from YAML with env-var overrides.

    Priority: env var > YAML file > defaults

    Usage:
        loader = ConfigLoader()
        config = loader.load()  # defaults only
        config = loader.load("path/to/config.yaml")  # from file
    """

    DEFAULT_CONFIG_PATH = str(
        Path(__file__).parent / "meta_modules_config.yaml"
    )

    # Environment variable overrides
    ENV_OVERRIDES = {
        "META_FPD_EPSILON": ("fpd", "epsilon", float),
        "META_FPD_PATIENCE": ("fpd", "patience", int),
        "META_GB_SELF_REF_THRESHOLD": ("gb", "self_ref_threshold", float),
        "META_GB_UNDECIDABLE_THRESHOLD": ("gb", "undecidable_threshold", float),
        "META_MCL_BUFFER_SIZE": ("mcl", "decision_buffer_size", int),
    }

    def load(self, config_path: str | None = None) -> MetaConfig:
        """Load configuration.

        Args:
            config_path: Path to YAML config file. None = use defaults.

        Returns:
            MetaConfig with all values populated.
        """
        config = MetaConfig()

        if config_path is None:
            config_path = self.DEFAULT_CONFIG_PATH

        if Path(config_path).exists():
            try:
                raw = SimpleYAMLLoader.load(config_path)
                self._apply_raw(config, raw)
                config.source = config_path
            except Exception:
                config.source = f"defaults (failed to load {config_path})"
        else:
            config.source = "defaults (no config file)"

        # Apply environment variable overrides
        self._apply_env_overrides(config)

        return config

    def _apply_raw(self, config: MetaConfig, raw: dict):
        """Apply parsed YAML to config dataclass."""
        # FPD
        fpd = raw.get("fixed_point_detector", {})
        if fpd:
            config.fpd.epsilon = fpd.get("epsilon", config.fpd.epsilon)
            config.fpd.patience = fpd.get("patience", config.fpd.patience)
            config.fpd.window_size = fpd.get("window_size", config.fpd.window_size)
            config.fpd.oscillation_threshold = fpd.get(
                "oscillation_threshold", config.fpd.oscillation_threshold
            )
            config.fpd.divergence_factor = fpd.get(
                "divergence_factor", config.fpd.divergence_factor
            )
            suspicion = fpd.get("suspicion", {})
            if suspicion:
                config.fpd.suspicion_perturbation_rounds = suspicion.get(
                    "perturbation_rounds", config.fpd.suspicion_perturbation_rounds
                )
                config.fpd.max_suspicion_triggers = suspicion.get(
                    "max_suspicion_triggers", config.fpd.max_suspicion_triggers
                )
            perturbation = fpd.get("perturbation", {})
            if perturbation:
                config.fpd.perturbation_epsilon_greedy_boost = perturbation.get(
                    "epsilon_greedy_boost", config.fpd.perturbation_epsilon_greedy_boost
                )
                config.fpd.perturbation_noise_sigma = perturbation.get(
                    "noise_sigma", config.fpd.perturbation_noise_sigma
                )
                config.fpd.perturbation_annealing_gamma = perturbation.get(
                    "annealing_gamma", config.fpd.perturbation_annealing_gamma
                )

        # GB
        gb = raw.get("godelian_boundary", {})
        if gb:
            config.gb.self_ref_threshold = gb.get(
                "self_ref_threshold", config.gb.self_ref_threshold
            )
            config.gb.undecidable_threshold = gb.get(
                "undecidable_threshold", config.gb.undecidable_threshold
            )
            ext = gb.get("external_tracking", {})
            if ext:
                config.gb.max_delegations = ext.get(
                    "max_delegations", config.gb.max_delegations
                )
                config.gb.compress_to_abdl = ext.get(
                    "compress_to_abdl", config.gb.compress_to_abdl
                )

        # MCL
        mcl = raw.get("meta_cognitive_loop", {})
        if mcl:
            config.mcl.decision_buffer_size = mcl.get(
                "decision_buffer_size", config.mcl.decision_buffer_size
            )
            config.mcl.cycle_history_size = mcl.get(
                "cycle_history_size", config.mcl.cycle_history_size
            )
            strat = mcl.get("strategy", {})
            if strat:
                config.mcl.max_bold_strategies = strat.get(
                    "max_bold_strategies", config.mcl.max_bold_strategies
                )
                config.mcl.max_conservative_strategies = strat.get(
                    "max_conservative_strategies", config.mcl.max_conservative_strategies
                )
                config.mcl.bold_risk_threshold = strat.get(
                    "bold_risk_threshold", config.mcl.bold_risk_threshold
                )
            verify = mcl.get("verification", {})
            if verify:
                config.mcl.require_godelian_check = verify.get(
                    "require_godelian_check", config.mcl.require_godelian_check
                )
                config.mcl.max_self_check_failures = verify.get(
                    "max_self_check_failures", config.mcl.max_self_check_failures
                )

    def _apply_env_overrides(self, config: MetaConfig):
        """Apply environment variable overrides."""
        for env_var, (section, field, converter) in self.ENV_OVERRIDES.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    converted = converter(value)
                    section_obj = getattr(config, section)
                    setattr(section_obj, field, converted)
                except (ValueError, TypeError):
                    pass  # Ignore invalid env values

    def reload(self, config_path: str) -> MetaConfig:
        """Reload configuration from file."""
        return self.load(config_path)
