"""
DigitalTwinCalibrator — 数字孪生参数校准引擎 (P4)
===================================================

Sim-to-Real Gap 量化与自动校准。解决"仿真决策"和"真实传感器数据"
之间的鸿沟——这是 MetaCognitiveLoop 的 RealityBridge 输入从
"理想世界自我验证"到"真实世界验证"的关键桥接。

核心能力:
  1. GapMetric: 定义多维度的 Sim-to-Real 差距度量
  2. CalibrationPipeline: 仿真参数 → 实机测试 → 差异分析 → 参数回滚
  3. RealityAnchor: 物理世界锚点（信任根的外延）
  4. AutoCalibrator: 自动检测漂移并触发重新校准

学术来源:
  - SimLifter: 首个专门设计用于弥合 Sim-to-Real 差距的数据集
  - TWICE Dataset: 280GB 数字孪生测试场景，多传感器恶劣条件
  - RoboVerse: 统一仿真平台 + 合成数据集 + 统一基准
  - Real2Sim: 通过机器人交互自动生成仿真就绪资产

集成点:
  - RealityBridge (P1): 提供仿真 vs 实机对比数据
  - FixedPointDetector: 检测校准是否收敛
  - MetaCognitiveLoop: 验证阶段使用 Gap 指标
  - SelfCheckEngine: TrustRoot 中的外部锚点验证
"""
import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# ── Domain Types ─────────────────────────────────────────────────────────────

class GapDimension(str, Enum):
    """Sim-to-Real 差距维度"""
    POSITION = "position"               # 位置误差 (m)
    VELOCITY = "velocity"               # 速度误差 (m/s)
    FORCE = "force"                     # 力/力矩误差 (N / N·m)
    SENSOR_NOISE = "sensor_noise"       # 传感器噪声水平差异
    LATENCY = "latency"                 # 控制延迟差异 (ms)
    TRAJECTORY = "trajectory"           # 轨迹偏离 (综合)
    ENERGY = "energy"                   # 能耗差异 (J)
    COLLISION = "collision"             # 碰撞检测差异 (接触力)
    FRICTION = "friction"               # 摩擦力系数差异
    MASS_DISTRIBUTION = "mass_distribution"  # 质量分布差异


class CalibrationState(str, Enum):
    """校准状态"""
    UNCALIBRATED = "uncalibrated"       # 未校准
    CALIBRATING = "calibrating"         # 校准中
    CALIBRATED = "calibrated"           # 已校准
    DRIFTING = "drifting"               # 漂移中（参数偏离）
    FAILED = "failed"                   # 校准失败


@dataclass
class SensorReading:
    """一次传感器读数。"""
    timestamp: float = field(default_factory=time.time)
    source: str = ""                    # "simulation" / "real"
    values: dict[str, float] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "values": self.values,
            "metadata": self.metadata,
        }


@dataclass
class GapSample:
    """一对仿真-实机的差距样本。"""
    dimension: GapDimension
    sim_value: float
    real_value: float
    absolute_error: float = 0.0
    relative_error: float = 0.0       # |sim - real| / max(|real|, epsilon)
    unit: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        eps = 1e-8
        self.absolute_error = abs(self.sim_value - self.real_value)
        self.relative_error = self.absolute_error / max(abs(self.real_value), eps)

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension.value,
            "sim_value": self.sim_value,
            "real_value": self.real_value,
            "absolute_error": self.absolute_error,
            "relative_error": self.relative_error,
            "unit": self.unit,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class CalibrationReport:
    """一次校准报告。"""
    report_id: str
    state: CalibrationState
    timestamp: float = field(default_factory=time.time)
    dimensions_checked: list[GapDimension] = field(default_factory=list)
    gaps: list[GapSample] = field(default_factory=list)
    total_rmse: float = 0.0            # 综合 RMSE
    worst_dimension: str = ""          # 最差维度
    worst_error: float = 0.0           # 最差误差
    drift_detected: bool = False
    parameters_adjusted: dict[str, tuple[float, float]] = field(
        default_factory=dict
    )  # param_name -> (old_value, new_value)
    convergence_iterations: int = 0
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "state": self.state.value,
            "timestamp": self.timestamp,
            "dimensions_checked": [d.value for d in self.dimensions_checked],
            "gaps": [g.to_dict() for g in self.gaps],
            "total_rmse": self.total_rmse,
            "worst_dimension": self.worst_dimension,
            "worst_error": self.worst_error,
            "drift_detected": self.drift_detected,
            "parameters_adjusted": {
                k: list(v) for k, v in self.parameters_adjusted.items()
            },
            "convergence_iterations": self.convergence_iterations,
            "recommendation": self.recommendation,
        }


# ── RealityAnchor ───────────────────────────────────────────────────────────

@dataclass
class RealityAnchor:
    """物理世界锚点 —— SelfCheck TrustRoot 在物理世界的外延。

    每个锚点是一个可测量的物理量，用于校准仿真参数。
    """
    id: str
    name: str
    dimension: GapDimension
    nominal_value: float            # 标称值（来自物理定律或测量）
    tolerance: float                # 允许误差
    unit: str
    last_measured: float = 0.0      # 最近实测值
    last_simulated: float = 0.0     # 最近仿真值
    measurement_count: int = 0

    @property
    def current_gap(self) -> float:
        """当前仿真-实机差距。"""
        if self.last_measured == 0.0:
            return 0.0
        return abs(self.last_simulated - self.last_measured)

    @property
    def within_tolerance(self) -> bool:
        return self.current_gap <= self.tolerance

    def update(self, sim_value: float, real_value: float):
        self.last_simulated = sim_value
        self.last_measured = real_value
        self.measurement_count += 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "dimension": self.dimension.value,
            "nominal_value": self.nominal_value,
            "tolerance": self.tolerance,
            "unit": self.unit,
            "current_gap": self.current_gap,
            "within_tolerance": self.within_tolerance,
            "measurement_count": self.measurement_count,
        }


# ── DigitalTwinCalibrator ───────────────────────────────────────────────────

class DigitalTwinCalibrator:
    """数字孪生校准器。

    管理仿真参数 → 实机测试 → 差异分析 → 参数回滚的完整循环。

    使用方式:
        calibrator = DigitalTwinCalibrator()
        calibrator.define_anchors([...])
        calibrator.feed_simulation(sim_readings)
        calibrator.feed_real(real_readings)
        report = calibrator.calibrate()
        if report.drift_detected:
            calibrator.apply_correction(report)
    """

    # 默认物理锚点（BottleSumo 擂台场景）
    DEFAULT_ANCHORS = [
        RealityAnchor("A-GRAVITY", "重力加速度", GapDimension.FORCE,
                      9.81, 0.05, "m/s²"),
        RealityAnchor("A-FRICTION", "擂台表面摩擦系数", GapDimension.FRICTION,
                      0.4, 0.05, "μ"),
        RealityAnchor("A-MASS", "机器人总质量", GapDimension.MASS_DISTRIBUTION,
                      3.0, 0.1, "kg"),
        RealityAnchor("A-MOTOR_TORQUE", "电机最大扭矩", GapDimension.FORCE,
                      1.2, 0.1, "N·m"),
        RealityAnchor("A-SENSOR_LATENCY", "传感器延迟", GapDimension.LATENCY,
                      5.0, 2.0, "ms"),
        RealityAnchor("A-POSITION_NOISE", "位置传感器噪声", GapDimension.SENSOR_NOISE,
                      0.01, 0.005, "m"),
        RealityAnchor("A-VEL_MAX", "最大线速度", GapDimension.VELOCITY,
                      1.0, 0.1, "m/s"),
    ]

    def __init__(self, anchors: list[RealityAnchor] | None = None):
        self.anchors: dict[str, RealityAnchor] = {}
        for a in (anchors or self.DEFAULT_ANCHORS):
            self.anchors[a.id] = a

        self._sim_buffer: deque[SensorReading] = deque(maxlen=1000)
        self._real_buffer: deque[SensorReading] = deque(maxlen=1000)
        self._gap_history: list[GapSample] = []
        self._report_history: list[CalibrationReport] = []
        self._report_counter: int = 0
        self._state: CalibrationState = CalibrationState.UNCALIBRATED
        self._drift_detector: dict[str, deque[float]] = {}  # anchor_id -> recent gaps

    # ── Data Feed ────────────────────────────────────────────────────────

    def feed_simulation(self, readings: list[SensorReading]):
        """喂入仿真数据。"""
        self._sim_buffer.extend(readings)

    def feed_real(self, readings: list[SensorReading]):
        """喂入实机数据。"""
        self._real_buffer.extend(readings)
        # 实时更新锚点的测量值
        for reading in readings:
            self._update_anchors_from_reading(reading, source="real")

    def _update_anchors_from_reading(self, reading: SensorReading, source: str):
        """从传感器读数更新锚点值。"""
        for anchor in self.anchors.values():
            # 尝试匹配维度
            dim_key = anchor.dimension.value
            if dim_key in reading.values or anchor.name.lower() in str(reading.values).lower():
                val = reading.values.get(dim_key, 0.0)
                if val != 0.0:
                    if source == "sim":
                        anchor.last_simulated = val
                    else:
                        anchor.last_measured = val

    # ── Gap Computation ──────────────────────────────────────────────────

    def compute_gaps(self) -> list[GapSample]:
        """计算所有维度的 Sim-to-Real 差距。

        使用最近匹配的仿真-实机读数对。
        """
        gaps = []
        sim_list = list(self._sim_buffer)
        real_list = list(self._real_buffer)

        for anchor in self.anchors.values():
            # 找到最近匹配的仿真和实机读数
            sim_val = self._find_latest_value(sim_list, anchor)
            real_val = self._find_latest_value(real_list, anchor)

            if sim_val is not None and real_val is not None:
                gap = GapSample(
                    dimension=anchor.dimension,
                    sim_value=sim_val,
                    real_value=real_val,
                    unit=anchor.unit,
                )
                gaps.append(gap)
                # 更新锚点
                anchor.update(sim_val, real_val)

                # 记录漂移检测
                if anchor.id not in self._drift_detector:
                    self._drift_detector[anchor.id] = deque(maxlen=20)
                self._drift_detector[anchor.id].append(gap.relative_error)

        self._gap_history.extend(gaps)
        return gaps

    def _find_latest_value(
        self, readings: list[SensorReading], anchor: RealityAnchor
    ) -> float | None:
        """在读数列表中查找与锚点匹配的最新值。"""
        for reading in reversed(readings):
            dim_key = anchor.dimension.value
            if dim_key in reading.values:
                return reading.values[dim_key]
            # 也尝试通过锚点名称匹配
            for key, val in reading.values.items():
                if anchor.name.lower() in key.lower():
                    return val
        return None

    # ── Calibration ──────────────────────────────────────────────────────

    def calibrate(self, max_iterations: int = 5) -> CalibrationReport:
        """执行完整的校准循环。

        Returns:
            CalibrationReport with gap analysis and parameter adjustments.
        """
        self._report_counter += 1
        self._state = CalibrationState.CALIBRATING

        # 1. 计算差距
        gaps = self.compute_gaps()
        dimensions_checked = list(set(g.dimension for g in gaps))

        # 2. 计算综合 RMSE
        total_rmse = self._compute_rmse(gaps) if gaps else 0.0

        # 3. 找出最差维度
        worst = max(gaps, key=lambda g: g.relative_error) if gaps else None

        # 4. 检测漂移
        drift_detected = self._detect_drift()

        # 5. 计算参数调整
        adjustments = {}
        if gaps and worst:
            adjustments = self._compute_adjustments(gaps)

        # 6. 判定状态
        if total_rmse < 0.1 and not drift_detected:
            new_state = CalibrationState.CALIBRATED
            recommendation = "仿真参数已校准，差距在可接受范围内。"
        elif drift_detected:
            new_state = CalibrationState.DRIFTING
            recommendation = (
                f"检测到参数漂移！最差维度: {worst.dimension.value if worst else 'N/A'} "
                f"(误差 {worst.relative_error:.3f} 如果 worst else 'N/A')。"
                "建议立即重新校准。"
            )
        else:
            new_state = CalibrationState.CALIBRATING
            recommendation = (
                f"校准进行中。总 RMSE: {total_rmse:.4f}。"
                f"最差维度: {worst.dimension.value if worst else 'N/A'}。"
            )

        self._state = new_state

        report = CalibrationReport(
            report_id=f"CAL-{self._report_counter:04d}",
            state=self._state,
            dimensions_checked=dimensions_checked,
            gaps=gaps,
            total_rmse=total_rmse,
            worst_dimension=worst.dimension.value if worst else "",
            worst_error=worst.relative_error if worst else 0.0,
            drift_detected=drift_detected,
            parameters_adjusted=adjustments,
            convergence_iterations=max_iterations,
            recommendation=recommendation,
        )

        self._report_history.append(report)
        return report

    def _compute_rmse(self, gaps: list[GapSample]) -> float:
        """计算综合 RMSE（所有维度的均方根误差）。"""
        if not gaps:
            return 0.0
        # 使用相对误差避免量纲差异
        squared_errors = [g.relative_error ** 2 for g in gaps]
        return math.sqrt(sum(squared_errors) / len(squared_errors))

    def _detect_drift(self) -> bool:
        """检测参数漂移：使用线性回归斜率检测趋势。

        如果最近 N 个样本的线性回归斜率为正且足够大，判定为漂移。
        """
        for anchor_id, gap_deque in self._drift_detector.items():
            if len(gap_deque) < 5:
                continue
            recent = list(gap_deque)[-5:]
            # 简单线性回归斜率: y = mx + b
            n = len(recent)
            x_mean = (n - 1) / 2.0
            y_mean = sum(recent) / n
            numerator = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            if denominator == 0:
                continue
            slope = numerator / denominator
            # 如果斜率显著为正（误差在加速增长），判定为漂移
            if slope > 0.01:  # slope > 0.01 means error increases ~5% over 5 steps
                return True
        return False

    def _compute_adjustments(
        self, gaps: list[GapSample]
    ) -> dict[str, tuple[float, float]]:
        """计算仿真参数调整量。

        返回: {param_name: (old_value, new_value)}
        """
        adjustments = {}
        for gap in gaps:
            if gap.relative_error < 0.1:
                continue  # 误差足够小，不需要调整

            param_name = f"sim_{gap.dimension.value}"
            old_value = gap.sim_value
            # 调整：向实机值的方向移动 50%（阻尼避免过调）
            new_value = old_value + 0.5 * (gap.real_value - old_value)
            adjustments[param_name] = (old_value, new_value)

        return adjustments

    # ── Anchor Management ────────────────────────────────────────────────

    def define_anchor(self, anchor: RealityAnchor):
        """添加新的物理锚点。"""
        self.anchors[anchor.id] = anchor

    def remove_anchor(self, anchor_id: str) -> bool:
        """移除物理锚点。"""
        if anchor_id in self.anchors:
            del self.anchors[anchor_id]
            return True
        return False

    def get_anchor_status(self) -> list[dict]:
        """获取所有锚点状态。"""
        return [a.to_dict() for a in self.anchors.values()]

    def get_drifting_anchors(self) -> list[RealityAnchor]:
        """获取正在漂移的锚点列表。"""
        return [a for a in self.anchors.values() if not a.within_tolerance]

    # ── Observability ────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """获取运行时可观测状态。"""
        anchor_status = self.get_anchor_status()
        drifting = self.get_drifting_anchors()

        last_report = self._report_history[-1] if self._report_history else None

        return {
            "module": "DigitalTwinCalibrator",
            "state": self._state.value,
            "anchors_total": len(self.anchors),
            "anchors_drifting": len(drifting),
            "anchors_calibrated": sum(1 for a in self.anchors.values() if a.within_tolerance),
            "drifting_anchors": [a.id for a in drifting],
            "last_rmse": last_report.total_rmse if last_report else None,
            "last_worst_dimension": last_report.worst_dimension if last_report else "",
            "report_count": self._report_counter,
            "sim_buffer_size": len(self._sim_buffer),
            "real_buffer_size": len(self._real_buffer),
            "anchor_details": anchor_status,
        }

    def export_report(self, path: str | Path):
        """导出最近一次校准报告。"""
        if not self._report_history:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                self._report_history[-1].to_dict(),
                f, indent=2, ensure_ascii=False,
            )

    @property
    def history(self) -> list[CalibrationReport]:
        return self._report_history

    @property
    def state(self) -> CalibrationState:
        return self._state

    def reset(self):
        self._sim_buffer.clear()
        self._real_buffer.clear()
        self._gap_history.clear()
        self._report_history.clear()
        self._drift_detector.clear()
        self._report_counter = 0
        self._state = CalibrationState.UNCALIBRATED
        for anchor in self.anchors.values():
            anchor.last_measured = 0.0
            anchor.last_simulated = 0.0
            anchor.measurement_count = 0
