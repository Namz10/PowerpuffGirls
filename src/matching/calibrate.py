"""Isotonic calibration on out-of-fold probabilities.

A US or India calibrator is kept only when its log-loss on that country's
rows is less than or equal to the global calibrator on those same rows.
France, and any other country, uses the global calibrator. No France threshold.
"""

from __future__ import annotations

import math

import numpy as np
from sklearn.isotonic import IsotonicRegression

LABELED_COUNTRIES = ("US", "India")
_CLIP = 1e-6


def binary_log_loss(labels: list[int], probabilities: list[float]) -> float:
    if not labels or len(labels) != len(probabilities):
        raise ValueError("labels and probabilities are not aligned")
    total = 0.0
    for label, probability in zip(labels, probabilities):
        clipped = min(1.0 - _CLIP, max(_CLIP, float(probability)))
        total += -(label * math.log(clipped) + (1 - label) * math.log(1.0 - clipped))
    return total / len(labels)


def keep_country_calibrator(country_loss: float, global_loss: float) -> bool:
    """Keep the country map only when it ties or beats global on that country's rows."""
    return country_loss <= global_loss


def _fit_isotonic(probabilities: list[float], labels: list[int]) -> IsotonicRegression | None:
    if len(set(labels)) < 2 or len(labels) < 2:
        return None
    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    model.fit(np.asarray(probabilities, dtype=float), np.asarray(labels, dtype=float))
    return model


def _predict(model: IsotonicRegression, probabilities: list[float]) -> list[float]:
    predicted = model.predict(np.asarray(probabilities, dtype=float))
    return [float(value) for value in predicted]


class ProbabilityCalibrator:
    """Global isotonic map plus optional US and India maps."""

    def __init__(self) -> None:
        self.global_model: IsotonicRegression | None = None
        self.country_models: dict[str, IsotonicRegression] = {}
        self.kept_countries: list[str] = []

    def fit(self, probabilities: list[float], labels: list[int], countries: list[str]) -> "ProbabilityCalibrator":
        if not (len(probabilities) == len(labels) == len(countries)):
            raise ValueError("calibration inputs are not aligned")
        self.global_model = _fit_isotonic(probabilities, labels)
        if self.global_model is None:
            raise ValueError("global calibrator needs both classes")
        global_probs = _predict(self.global_model, probabilities)
        self.country_models = {}
        self.kept_countries = []
        for country in LABELED_COUNTRIES:
            indexes = [index for index, value in enumerate(countries) if value == country]
            if not indexes:
                continue
            country_model = _fit_isotonic(
                [probabilities[index] for index in indexes],
                [labels[index] for index in indexes],
            )
            if country_model is None:
                continue
            country_hat = _predict(country_model, [probabilities[index] for index in indexes])
            global_hat = [global_probs[index] for index in indexes]
            country_labels = [labels[index] for index in indexes]
            if keep_country_calibrator(
                binary_log_loss(country_labels, country_hat),
                binary_log_loss(country_labels, global_hat),
            ):
                self.country_models[country] = country_model
                self.kept_countries.append(country)
        return self

    def transform_one(self, probability: float, country: str) -> float:
        if self.global_model is None:
            raise ValueError("calibrator is not fit")
        model = self.country_models.get(country, self.global_model)
        return _predict(model, [probability])[0]

    def choice_name(self) -> str:
        if not self.kept_countries:
            return "global"
        return "global+" + "+".join(self.kept_countries)
