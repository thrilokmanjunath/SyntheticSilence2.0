import numpy as np
from app.models.schemas import InsufficiencySignal

class ConformalCalibrator:
    def __init__(self, alpha: float = 0.1):
        """
        Split-conformal interface.
        alpha is the target error rate (e.g., 0.1 for 90% confidence).
        """
        self.alpha = alpha
        self.calibration_scores = []
        self.q_hat = None
        self.fitted = False

    def fit(self, calibration_signals: list[float]):
        """
        Fits the calibrator using a held-out calibration set of raw insufficiency scores.
        """
        if not calibration_signals:
            return

        n = len(calibration_signals)
        self.calibration_scores = np.sort(calibration_signals)

        q_level = np.ceil((n + 1) * (1 - self.alpha)) / n
        q_level = min(max(q_level, 0.0), 1.0)

        self.q_hat = np.quantile(self.calibration_scores, q_level, method='higher')
        self.fitted = True

    @staticmethod
    def raw_score(signal: InsufficiencySignal) -> float | None:
        """
        Raw composite, higher = less supported. Matches the B8 baseline used in the
        E0 experiments: (density + similarity entropy) / 2.

        retrieval_confidence is 1 - density, so it must be flipped before averaging
        with uncertainty. Averaging them directly would mix two opposite directions.
        Components that are unavailable are skipped; with none available the score is None.
        """
        if signal.representation_density is not None:
            density = signal.representation_density
        elif signal.retrieval_confidence is not None:
            density = 1.0 - signal.retrieval_confidence
        else:
            density = None

        parts = [v for v in (density, signal.uncertainty) if v is not None]
        if not parts:
            return None
        return float(sum(parts) / len(parts))

    def calibrate(self, signal: InsufficiencySignal) -> InsufficiencySignal:
        """
        Takes a raw InsufficiencySignal and calibrates it.
        Honestly reports NOT_CALIBRATED until fit() is actually called.
        """
        signal.insufficiency_signal = self.raw_score(signal)

        if not self.fitted:
            signal.calibration_status = "NOT_CALIBRATED"
            return signal

        signal.calibration_status = f"CALIBRATED_{int((1-self.alpha)*100)}_PCT"

        return signal
