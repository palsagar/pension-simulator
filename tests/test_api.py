from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pension_simulator.api import create_app
from pension_simulator.data import CountryData, load_country, save_country


@pytest.fixture
def client(country: CountryData, tmp_path: Path) -> TestClient:
    save_country(country, tmp_path / "TST.npz")
    return TestClient(create_app(tmp_path))


def test_country_file_round_trip(country: CountryData, tmp_path: Path) -> None:
    save_country(country, tmp_path / "TST.npz")
    loaded = load_country(tmp_path / "TST.npz")
    assert loaded.name == "Testland"
    assert (loaded.survival == country.survival).all()


def test_countries_lists_defaults(client: TestClient) -> None:
    (listed,) = client.get("/countries").json()
    assert listed["code"] == "TST"
    assert listed["end_year"] == 2100
    assert listed["defaults"]["retirement_age"] == 62
    assert listed["defaults"]["fertility"] == pytest.approx(1.6)


def test_defaults_reproduce_the_baseline(client: TestClient) -> None:
    defaults = client.get("/countries").json()[0]["defaults"]
    baseline = client.post("/simulate", json={"country": "TST"}).json()
    explicit = client.post("/simulate", json={"country": "TST", **defaults}).json()
    assert explicit["pension_debt_gdp"] == pytest.approx(baseline["pension_debt_gdp"])


def test_simulate_returns_yearly_series(client: TestClient) -> None:
    body = client.post("/simulate", json={"country": "TST", "retirement_age": 66}).json()
    assert body["years"][0] == 2025 and body["years"][-1] == 2100
    assert len(body["pension_debt_gdp"]) == 76
    assert len(body["population"][0][0]) == 101
    assert body["pensions_gdp"][0] == pytest.approx(0.14)


def test_unknown_country_and_invalid_values_are_rejected(client: TestClient) -> None:
    assert client.post("/simulate", json={"country": "XXX"}).status_code == 404
    assert (
        client.post("/simulate", json={"country": "TST", "retirement_age": 20}).status_code == 422
    )
