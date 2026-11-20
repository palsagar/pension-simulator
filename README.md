# Pension Simulator

An educational simulator of pay-as-you-go pension systems. You choose a country and a retirement age, and the simulator shows how the population and the pension system's finances develop.

In a pay-as-you-go system, the pensions of today's retirees are paid directly by today's workers. The system depends on the number of contributors per retiree. That number has fallen for decades as people live longer and have fewer children.

The first version covers France, Germany, Italy, and Spain.

## Status

The first version is working: the model, the country data for the four countries, the web service, and the frontend.

The simulator is live at https://pensions.gpuphysics.dev. Each merge to `main` deploys a new version.

## Run it

The project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn --factory pension_simulator.api:create_app --reload
```

The simulator is then at http://127.0.0.1:8000/. The interactive API documentation is at http://127.0.0.1:8000/docs.

To run it in a container instead:

```bash
docker build -t pension-simulator .
docker run --rm -p 8000:8000 pension-simulator
```

- `GET /countries` lists the countries with the default value of every control.
- `POST /simulate` runs one scenario, for example `{"country": "FRA", "retirement_age": 65}`.

## Develop

```bash
uv run pytest              # tests
uv run ruff check .        # linting
uv run ruff format .       # formatting
uv run ty check            # type checks
uv run python scripts/build_country_data.py   # rebuild data/countries from public sources
```

## Documents

- [`docs/model.md`](docs/model.md): the mathematics of the model.
- [`docs/modelling-choices.md`](docs/modelling-choices.md): the assumptions, data sources, and simplifications, and how to read the results.
- [`CONTEXT.md`](CONTEXT.md): the vocabulary used in the project.
- [`docs/adr/`](docs/adr/): the reasons for the less obvious design decisions.

## Architecture

- `src/pension_simulator/` holds the model as a plain Python package built on NumPy: `population.py`, `finance.py`, `ledger.py`, and `simulation.py`, which runs one scenario.
- `src/pension_simulator/api.py` is a thin, stateless FastAPI layer. It also serves the frontend.
- `frontend/` holds the page: static HTML, CSS, and JavaScript with no build step. Alpine.js holds the state of the controls and Observable Plot draws the charts. See [`frontend/README.md`](frontend/README.md).
- `data/countries/` holds one data file per country. `scripts/build_country_data.py` builds them from United Nations, OECD, and European Commission data.

## License

MIT
