"""
Tests for DigitalTwinCalibrator (P4-3)
=======================================
Sim-to-Real gap quantification, calibration pipeline, drift detection,
RealityAnchor management, and integration with existing meta modules.
"""
import json
import tempfile
import time
from pathlib import Path

import pytest

from governance.meta.digital_twin_calibrator import (
    CalibrationReport,
    CalibrationState,
    DigitalTwinCalibrator,
    GapDimension,
    GapSample,
    RealityAnchor,
    SensorReading,
)


# ── RealityAnchor Tests ───────────────────────────────────────────────────

class TestRealityAnchor:
    def test_basic_anchor(self):
        a = RealityAnchor(
            id="A1", name="重力", dimension=GapDimension.FORCE,
            nominal_value=9.81, tolerance=0.05, unit="m/s²",
        )
        assert a.id == "A1"
        assert a.nominal_value == 9.81
        assert a.current_gap == 0.0

    def test_anchor_update(self):
        a = RealityAnchor(
            id="A1", name="重力", dimension=GapDimension.FORCE,
            nominal_value=9.81, tolerance=0.5, unit="m/s²",
        )
        a.update(sim_value=10.0, real_value=9.81)
        assert a.measurement_count == 1
        assert abs(a.current_gap - 0.19) < 0.01
        assert a.within_tolerance is True

    def test_anchor_out_of_tolerance(self):
        a = RealityAnchor(
            id="A1", name="摩擦", dimension=GapDimension.FRICTION,
            nominal_value=0.4, tolerance=0.01, unit="μ",
        )
        a.update(sim_value=0.4, real_value=0.25)
        assert a.current_gap == pytest.approx(0.15)
        assert a.within_tolerance is False

    def test_anchor_serialization(self):
        a = RealityAnchor(
            id="A1", name="测试", dimension=GapDimension.POSITION,
            nominal_value=1.0, tolerance=0.1, unit="m",
        )
        a.update(1.0, 0.95)
        d = a.to_dict()
        assert d["id"] == "A1"
        assert d["dimension"] == "position"
        assert d["measurement_count"] == 1
        assert d["within_tolerance"] == (d["current_gap"] <= d["tolerance"])


# ── SensorReading Tests ──────────────────────────────────────────────────

class TestSensorReading:
    def test_basic_reading(self):
        r = SensorReading(
            source="simulation",
            values={"position": 0.5, "velocity": 0.3},
        )
        assert r.source == "simulation"
        assert r.values["position"] == 0.5

    def test_reading_serialization(self):
        r = SensorReading(
            source="real", values={"force": 9.8},
            metadata={"sensor": "imu"},
        )
        d = r.to_dict()
        assert d["source"] == "real"
        assert d["values"] == {"force": 9.8}


# ── GapSample Tests ──────────────────────────────────────────────────────

class TestGapSample:
    def test_gap_computation(self):
        g = GapSample(
            dimension=GapDimension.POSITION,
            sim_value=0.5, real_value=0.45, unit="m",
        )
        assert abs(g.absolute_error - 0.05) < 1e-9
        assert abs(g.relative_error - 0.1111) < 0.001

    def test_gap_zero_real_value(self):
        """当实机值为 0 时不会除零。"""
        g = GapSample(
            dimension=GapDimension.VELOCITY,
            sim_value=0.1, real_value=0.0, unit="m/s",
        )
        assert g.absolute_error == 0.1
        # relative_error = 0.1 / 1e-8 = 1e7 (bounded by eps, not inf)
        assert g.relative_error <= 1e7

    def test_gap_serialization(self):
        g = GapSample(
            dimension=GapDimension.FORCE,
            sim_value=10.0, real_value=9.5, unit="N",
        )
        d = g.to_dict()
        assert d["dimension"] == "force"
        assert d["sim_value"] == 10.0
        assert "absolute_error" in d


# ── CalibrationReport Tests ──────────────────────────────────────────────

class TestCalibrationReport:
    def test_basic_report(self):
        report = CalibrationReport(
            report_id="CAL-0001",
            state=CalibrationState.CALIBRATED,
            total_rmse=0.05,
            recommendation="All good",
        )
        assert report.state == CalibrationState.CALIBRATED
        assert report.total_rmse == 0.05

    def test_report_serialization(self):
        gap = GapSample(
            dimension=GapDimension.POSITION,
            sim_value=1.0, real_value=0.9, unit="m",
        )
        report = CalibrationReport(
            report_id="CAL-0001",
            state=CalibrationState.CALIBRATING,
            gaps=[gap],
            total_rmse=0.1,
            worst_dimension="position",
            worst_error=0.1,
            drift_detected=False,
            parameters_adjusted={"sim_position": (1.0, 0.95)},
        )
        d = report.to_dict()
        assert d["report_id"] == "CAL-0001"
        assert len(d["gaps"]) == 1
        assert d["parameters_adjusted"]["sim_position"] == [1.0, 0.95]


# ── DigitalTwinCalibrator Core Tests ─────────────────────────────────────

class TestCalibratorInit:
    def test_default_initialization(self):
        c = DigitalTwinCalibrator()
        assert len(c.anchors) == 7
        assert c.state == CalibrationState.UNCALIBRATED

    def test_custom_anchors(self):
        anchors = [
            RealityAnchor("A1", "Test", GapDimension.POSITION, 1.0, 0.1, "m"),
        ]
        c = DigitalTwinCalibrator(anchors=anchors)
        assert len(c.anchors) == 1


class TestCalibratorDataFeed:
    def test_feed_simulation(self):
        c = DigitalTwinCalibrator()
        readings = [
            SensorReading(source="simulation", values={"gravity": 9.8}),
            SensorReading(source="simulation", values={"friction": 0.4}),
        ]
        c.feed_simulation(readings)
        assert len(c._sim_buffer) == 2

    def test_feed_real(self):
        c = DigitalTwinCalibrator()
        readings = [
            SensorReading(source="real", values={"gravity": 9.9}),
        ]
        c.feed_real(readings)
        assert len(c._real_buffer) == 1

    def test_feed_updates_anchors(self):
        c = DigitalTwinCalibrator()
        sim_readings = [
            SensorReading(source="simulation", values={"force": 9.7, "velocity": 0.5}),
        ]
        real_readings = [
            SensorReading(source="real", values={"force": 9.82, "velocity": 0.48}),
        ]
        c.feed_simulation(sim_readings)
        c.feed_real(real_readings)

        # Gravity anchor should be updated
        gravity = c.anchors.get("A-GRAVITY")
        if gravity:
            assert gravity.last_simulated != 0.0 or gravity.last_measured != 0.0


# ── Gap Computation Tests ────────────────────────────────────────────────

class TestGapComputation:
    def test_compute_gaps_no_data(self):
        c = DigitalTwinCalibrator()
        gaps = c.compute_gaps()
        assert gaps == []

    def test_compute_gaps_with_data(self):
        c = DigitalTwinCalibrator()
        # Feed matching sim and real data
        sim_readings = [
            SensorReading(source="simulation", values={
                "force": 9.7, "velocity": 0.5, "friction": 0.38,
                "position": 0.0, "mass_distribution": 3.0,
            }),
        ]
        real_readings = [
            SensorReading(source="real", values={
                "force": 9.82, "velocity": 0.48, "friction": 0.42,
                "position": 0.01, "mass_distribution": 3.05,
            }),
        ]
        c.feed_simulation(sim_readings)
        c.feed_real(real_readings)
        gaps = c.compute_gaps()
        # Should have gaps for matching dimensions
        assert len(gaps) > 0
        for g in gaps:
            assert g.dimension in GapDimension

    def test_gaps_with_large_discrepancy(self):
        """大差距应被正确捕获。"""
        c = DigitalTwinCalibrator()
        sim_readings = [
            SensorReading(source="simulation", values={"force": 5.0}),
        ]
        real_readings = [
            SensorReading(source="real", values={"force": 10.0}),
        ]
        c.feed_simulation(sim_readings)
        c.feed_real(real_readings)
        gaps = c.compute_gaps()
        force_gaps = [g for g in gaps if g.dimension == GapDimension.FORCE]
        if force_gaps:
            assert force_gaps[0].relative_error > 0.4  # large gap

    def test_rmse_computation(self):
        c = DigitalTwinCalibrator()
        gaps = [
            GapSample(GapDimension.POSITION, 1.0, 0.9, unit="m"),
            GapSample(GapDimension.POSITION, 2.0, 1.8, unit="m"),
        ]
        rmse = c._compute_rmse(gaps)
        # Both have relative_error ≈ 0.1, RMSE should be ~0.1
        assert 0.09 < rmse < 0.12


# ── Calibration Pipeline Tests ────────────────────────────────────────────

class TestCalibrationPipeline:
    def test_calibrate_no_data(self):
        c = DigitalTwinCalibrator()
        report = c.calibrate()
        assert report.state == CalibrationState.CALIBRATED  # no gaps = calibrated
        assert report.total_rmse == 0.0

    def test_calibrate_with_data(self):
        c = DigitalTwinCalibrator()
        # Simulate well-aligned data (small gaps)
        sim_readings = [
            SensorReading(source="simulation", values={
                "force": 9.8, "velocity": 0.5, "friction": 0.4, "position": 0.0,
            }),
        ]
        real_readings = [
            SensorReading(source="real", values={
                "force": 9.82, "velocity": 0.49, "friction": 0.41, "position": 0.005,
            }),
        ]
        c.feed_simulation(sim_readings)
        c.feed_real(real_readings)
        report = c.calibrate()
        assert report.state in (
            CalibrationState.CALIBRATED,
            CalibrationState.CALIBRATING,
        )
        assert report.total_rmse >= 0.0

    def test_calibrate_increments_counter(self):
        c = DigitalTwinCalibrator()
        c.calibrate()
        c.calibrate()
        assert c._report_counter == 2
        assert len(c.history) == 2

    def test_calibrate_returns_dimensions_checked(self):
        c = DigitalTwinCalibrator()
        sim_readings = [
            SensorReading(source="simulation", values={"force": 9.8}),
        ]
        real_readings = [
            SensorReading(source="real", values={"force": 9.82}),
        ]
        c.feed_simulation(sim_readings)
        c.feed_real(real_readings)
        report = c.calibrate()
        assert len(report.dimensions_checked) >= 1

    def test_parameter_adjustments_made(self):
        """大差距应产生参数调整。"""
        c = DigitalTwinCalibrator()
        sim_readings = [
            SensorReading(source="simulation", values={
                "force": 5.0, "velocity": 0.3, "friction": 0.2,
            }),
        ]
        real_readings = [
            SensorReading(source="real", values={
                "force": 10.0, "velocity": 0.6, "friction": 0.4,
            }),
        ]
        c.feed_simulation(sim_readings)
        c.feed_real(real_readings)
        report = c.calibrate()
        # Large gaps should generate adjustments
        assert len(report.parameters_adjusted) > 0


# ── Drift Detection Tests ────────────────────────────────────────────────

class TestDriftDetection:
    def test_no_drift_with_stable_data(self):
        c = DigitalTwinCalibrator()
        for _ in range(10):
            sim_readings = [SensorReading(source="simulation", values={"force": 9.8})]
            real_readings = [SensorReading(source="real", values={"force": 9.82})]
            c.feed_simulation(sim_readings)
            c.feed_real(real_readings)
            c.compute_gaps()
        report = c.calibrate()
        assert report.drift_detected is False

    def test_drift_detected_with_increasing_error(self):
        c = DigitalTwinCalibrator()
        # Simulate increasing real value (drift), enough iterations for clear trend
        for i in range(15):
            sim_readings = [SensorReading(source="simulation", values={"force": 9.8})]
            real_value = 9.8 + i * 0.5  # increasing gap
            real_readings = [SensorReading(source="real", values={"force": real_value})]
            c.feed_simulation(sim_readings)
            c.feed_real(real_readings)
            c.compute_gaps()

        report = c.calibrate()
        assert report.drift_detected is True


# ── Anchor Management Tests ──────────────────────────────────────────────

class TestAnchorManagement:
    def test_define_anchor(self):
        c = DigitalTwinCalibrator()
        before = len(c.anchors)
        c.define_anchor(RealityAnchor(
            "A-NEW", "新锚点", GapDimension.POSITION, 0.0, 0.1, "m",
        ))
        assert len(c.anchors) == before + 1

    def test_remove_anchor(self):
        c = DigitalTwinCalibrator()
        result = c.remove_anchor("A-GRAVITY")
        assert result is True
        assert "A-GRAVITY" not in c.anchors

    def test_remove_nonexistent_anchor(self):
        c = DigitalTwinCalibrator()
        result = c.remove_anchor("NONEXISTENT")
        assert result is False

    def test_get_anchor_status(self):
        c = DigitalTwinCalibrator()
        status = c.get_anchor_status()
        assert len(status) == 7
        for s in status:
            assert "id" in s
            assert "dimension" in s
            assert "current_gap" in s

    def test_get_drifting_anchors(self):
        c = DigitalTwinCalibrator()
        # Make one anchor drift
        gravity = c.anchors["A-GRAVITY"]
        gravity.update(sim_value=9.81, real_value=15.0)  # huge gap > tolerance
        drifting = c.get_drifting_anchors()
        assert len(drifting) >= 1
        assert any(a.id == "A-GRAVITY" for a in drifting)


# ── Observability Tests ──────────────────────────────────────────────────

class TestCalibratorObservability:
    def test_get_state(self):
        c = DigitalTwinCalibrator()
        state = c.get_state()
        assert state["module"] == "DigitalTwinCalibrator"
        assert state["state"] == "uncalibrated"
        assert state["anchors_total"] == 7

    def test_get_state_after_calibration(self):
        c = DigitalTwinCalibrator()
        sim_readings = [SensorReading(source="simulation", values={"force": 9.8})]
        real_readings = [SensorReading(source="real", values={"force": 9.82})]
        c.feed_simulation(sim_readings)
        c.feed_real(real_readings)
        c.calibrate()

        state = c.get_state()
        assert state["last_rmse"] is not None
        assert "anchor_details" in state

    def test_export_report(self):
        c = DigitalTwinCalibrator()
        sim_readings = [SensorReading(source="simulation", values={"force": 9.8})]
        real_readings = [SensorReading(source="real", values={"force": 9.82})]
        c.feed_simulation(sim_readings)
        c.feed_real(real_readings)
        c.calibrate()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        c.export_report(path)
        saved = Path(path)
        assert saved.stat().st_size > 0

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["report_id"] == "CAL-0001"
        Path(path).unlink()

    def test_reset(self):
        c = DigitalTwinCalibrator()
        sim_readings = [SensorReading(source="simulation", values={"force": 9.8})]
        real_readings = [SensorReading(source="real", values={"force": 9.82})]
        c.feed_simulation(sim_readings)
        c.feed_real(real_readings)
        c.calibrate()
        c.reset()

        assert c.state == CalibrationState.UNCALIBRATED
        assert len(c._sim_buffer) == 0
        assert len(c._real_buffer) == 0
        assert c._report_counter == 0
        for anchor in c.anchors.values():
            assert anchor.measurement_count == 0


# ── Integration Tests ────────────────────────────────────────────────────

class TestCalibratorIntegration:
    def test_full_calibration_workflow(self):
        """完整校准工作流: 喂数据 → 计算差距 → 校准 → 检测漂移。"""
        c = DigitalTwinCalibrator()

        # Step 1: Initial calibration
        sim = [SensorReading(source="simulation", values={
            "force": 9.8, "velocity": 0.5, "friction": 0.4,
            "position": 0.0,
        })]
        real = [SensorReading(source="real", values={
            "force": 9.82, "velocity": 0.49, "friction": 0.41,
            "position": 0.005,
        })]
        c.feed_simulation(sim)
        c.feed_real(real)
        report1 = c.calibrate()
        assert report1.state == CalibrationState.CALIBRATED  # small gaps

        # Step 2: Introduce drift (with enough iterations for clear trend)
        for i in range(15):
            sim_drift = [SensorReading(
                source="simulation", values={"force": 9.8, "velocity": 0.5}
            )]
            real_drift = [SensorReading(
                source="real", values={"force": 9.8 + i * 0.5, "velocity": 0.5 + i * 0.05}
            )]
            c.feed_simulation(sim_drift)
            c.feed_real(real_drift)
            c.compute_gaps()

        report2 = c.calibrate()
        assert report2.drift_detected is True
        assert len(report2.parameters_adjusted) > 0  # adjustments triggered

    def test_sim_to_real_gap_quantification(self):
        """量化仿真-实机差距并验证报告完整性。"""
        c = DigitalTwinCalibrator()
        sim = [SensorReading(source="simulation", values={
            "force": 10.0, "velocity": 0.5, "friction": 0.4, "position": 0.0,
        })]
        real = [SensorReading(source="real", values={
            "force": 9.0, "velocity": 0.55, "friction": 0.35, "position": 0.02,
        })]
        c.feed_simulation(sim)
        c.feed_real(real)
        report = c.calibrate()

        # Report completeness checks
        assert report.report_id is not None
        assert report.total_rmse > 0
        assert report.worst_dimension != ""
        assert report.recommendation != ""
        assert len(report.dimensions_checked) >= 1

    def test_multiple_calibration_cycles_convergence(self):
        """多轮校准应逐步减小差距。"""
        c = DigitalTwinCalibrator()

        rmses = []
        for cycle in range(5):
            # Sim values approach real values over cycles
            sim_val = 9.0 + cycle * 0.2
            real_val = 9.81
            sim = [SensorReading(source="simulation", values={"force": sim_val})]
            real = [SensorReading(source="real", values={"force": real_val})]
            c.feed_simulation(sim)
            c.feed_real(real)
            report = c.calibrate()
            rmses.append(report.total_rmse)

        # RMSE should decrease or stay low
        assert rmses[-1] <= rmses[0] * 1.1, (
            f"RMSE should not grow significantly: {rmses}"
        )


# ── Edge Cases ────────────────────────────────────────────────────────────

class TestCalibratorEdgeCases:
    def test_empty_buffers(self):
        c = DigitalTwinCalibrator()
        report = c.calibrate()
        assert report.state == CalibrationState.CALIBRATED
        assert report.gaps == []

    def test_only_simulation_data(self):
        c = DigitalTwinCalibrator()
        c.feed_simulation([SensorReading(source="simulation", values={"force": 9.8})])
        gaps = c.compute_gaps()
        assert gaps == []  # no real data to compare against

    def test_only_real_data(self):
        c = DigitalTwinCalibrator()
        c.feed_real([SensorReading(source="real", values={"force": 9.82})])
        gaps = c.compute_gaps()
        assert gaps == []  # no sim data to compare against

    def test_all_dimensions_in_report(self):
        """校准报告应涵盖所有有数据的维度。"""
        c = DigitalTwinCalibrator()
        sim = [SensorReading(source="simulation", values={
            "force": 9.8, "velocity": 0.5, "friction": 0.4,
            "position": 0.0, "mass_distribution": 3.0,
        })]
        real = [SensorReading(source="real", values={
            "force": 9.82, "velocity": 0.49, "friction": 0.41,
            "position": 0.005, "mass_distribution": 3.05,
        })]
        c.feed_simulation(sim)
        c.feed_real(real)
        report = c.calibrate()
        # At least force, velocity, friction should be covered
        dims = [d.value for d in report.dimensions_checked]
        assert "force" in dims
        assert len(report.dimensions_checked) >= 3

    def test_export_without_calibration(self):
        c = DigitalTwinCalibrator()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        c.export_report(path)
        # No calibration → no report → file stays as NamedTemporaryFile created it
        assert Path(path).stat().st_size == 0
        Path(path).unlink(missing_ok=True)
