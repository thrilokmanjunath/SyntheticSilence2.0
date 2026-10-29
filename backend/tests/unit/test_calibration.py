import pytest
from app.services.analysis.calibration import ConformalCalibrator
from app.models.schemas import InsufficiencySignal

def test_calibration_not_fitted():
    calibrator = ConformalCalibrator(alpha=0.1)
    signal = InsufficiencySignal(
        evidence_coverage=1.0,
        semantic_support=1.0,
        contradiction_level=0.0
    )
    signal.retrieval_confidence = 0.8
    signal.uncertainty = 0.5
    
    calibrated_signal = calibrator.calibrate(signal)
    assert calibrated_signal.calibration_status == "NOT_CALIBRATED"

def test_calibration_fitted():
    calibrator = ConformalCalibrator(alpha=0.1)
    calibrator.fit([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    
    signal = InsufficiencySignal(
        evidence_coverage=1.0,
        semantic_support=1.0,
        contradiction_level=0.0
    )
    signal.retrieval_confidence = 0.5
    signal.uncertainty = 0.5
    
    calibrated_signal = calibrator.calibrate(signal)
    assert calibrated_signal.calibration_status == "CALIBRATED_90_PCT"
    assert calibrated_signal.insufficiency_signal == 0.5

def test_raw_score_direction_matches_b8_baseline():
    """Higher density (farther from reference) and higher entropy must both raise the score."""
    def score(density, uncertainty):
        s = InsufficiencySignal(
            evidence_coverage=1.0, semantic_support=0.5, contradiction_level=0.0,
            representation_density=density, retrieval_confidence=1.0 - density, uncertainty=uncertainty,
        )
        return ConformalCalibrator().calibrate(s).insufficiency_signal

    assert score(0.8, 0.5) == pytest.approx((0.8 + 0.5) / 2)
    assert score(0.9, 0.5) > score(0.4, 0.5)
    assert score(0.5, 0.9) > score(0.5, 0.2)


def test_raw_score_handles_missing_components():
    s = InsufficiencySignal(evidence_coverage=0.0, semantic_support=0.0, contradiction_level=0.0)
    assert ConformalCalibrator().calibrate(s).insufficiency_signal is None

    s = InsufficiencySignal(evidence_coverage=0.0, semantic_support=0.0, contradiction_level=0.0, uncertainty=1.0)
    assert ConformalCalibrator().calibrate(s).insufficiency_signal == 1.0


def test_calibration_empty_set():
    calibrator = ConformalCalibrator(alpha=0.1)
    calibrator.fit([])
    assert not calibrator.fitted
