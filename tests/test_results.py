"""Check that the published findings follow from the recorded AnyLogic runs."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_runs import CHOSEN, MEAN_SERVICE, deviations, fluctuating_rate, load_runs  # noqa: E402


@pytest.fixture(scope="module")
def runs() -> pd.DataFrame:
    return load_runs()


@pytest.fixture(scope="module")
def checked(runs: pd.DataFrame) -> pd.DataFrame:
    return deviations(runs)


def row(runs: pd.DataFrame, config: str, buffers: str) -> pd.Series:
    return runs[(runs["config"] == config) & (runs["buffers"] == buffers)].iloc[0]


def test_twenty_four_runs_two_buffer_settings(runs: pd.DataFrame) -> None:
    assert len(runs) == 24
    assert runs["buffers"].value_counts().to_dict() == {"spec": 12, "big": 12}
    assert runs["config"].nunique() == 12


def test_mean_service_times_follow_the_triangular_distributions() -> None:
    assert MEAN_SERVICE["atm"] == pytest.approx(1.9333, abs=1e-4)
    assert MEAN_SERVICE["teller"] == pytest.approx(6.5)
    assert MEAN_SERVICE["business"] == pytest.approx(13.3333, abs=1e-4)


def test_class_configuration_halts_within_the_first_hour(runs: pd.DataFrame) -> None:
    assert row(runs, "T1a-1", "spec")["stop_min"] == pytest.approx(38.6, abs=0.1)


def test_three_business_tellers_halt_at_101_minutes_and_diverge_without_a_buffer(runs: pd.DataFrame) -> None:
    assert row(runs, "T2-2", "spec")["stop_min"] == pytest.approx(101.0, abs=0.1)
    unbounded = row(runs, "T2-2", "big")
    assert unbounded["util_business"] > 0.999
    assert round(unbounded["lq_business"]) == 1773
    assert round(unbounded["in_system_max"]) == 8907


def test_chosen_configurations_and_their_time_in_the_bank(runs: pd.DataFrame) -> None:
    expected = {"T1a-3": 6.18, "T2-3": 8.00, "T3-2": 7.26, "T4-1": 8.34, "T5-2": 8.43}
    assert set(expected) == set(CHOSEN)
    for config, minutes in expected.items():
        assert row(runs, config, "big")["in_system_mean"] == pytest.approx(minutes, abs=0.005)


def test_chosen_task_4_configuration_is_three_eight_six(runs: pd.DataFrame) -> None:
    chosen = row(runs, "T4-1", "big")
    assert (chosen["n_atm"], chosen["n_teller"], chosen["n_business"]) == (3, 8, 6)


def test_a_fourth_atm_barely_helps_customers(runs: pd.DataFrame) -> None:
    before = row(runs, "T4-1", "big")["in_system_mean"]
    after = row(runs, "T4-2", "big")["in_system_mean"]
    assert 0.03 < (before - after) / before < 0.045


def test_measured_utilisation_matches_offered_load(checked: pd.DataFrame) -> None:
    steady = checked[checked["steady"]]
    assert len(steady) == 14
    assert steady["max_gap"].max() < 0.017
    assert steady[steady["chosen"]]["max_gap"].max() < 0.01


def test_early_stops_are_the_only_large_deviations(checked: pd.DataFrame) -> None:
    large = checked[checked["stable_prediction"] & (checked["max_gap"] > 0.017)]
    assert set(large["run_id"]) == {"R02_T1a2_spec", "R07_T3_1_spec"}
    assert (large["stop_min"] < 2500).all()


def test_fluctuating_arrivals_realise_a_lower_rate_than_the_triangular_mean(runs: pd.DataFrame) -> None:
    low, mode, high = 2.5, 5.5, 12.5
    grid = np.linspace(low, high, 200001)
    density = np.where(
        grid < mode,
        2 * (grid - low) / ((high - low) * (mode - low)),
        2 * (high - grid) / ((high - low) * (high - mode)),
    )
    mean_rate = np.trapezoid(grid * density, grid)
    realised = 1 / np.trapezoid(density / grid, grid)
    assert mean_rate == pytest.approx(6.833, abs=0.001)
    assert realised == pytest.approx(6.181, abs=0.001)
    assert fluctuating_rate() == pytest.approx(realised, abs=1e-8)
    measured = row(runs, "T5-2", "big")
    assert measured["throughput"] / measured["stop_min"] == pytest.approx(6.170, abs=0.001)
