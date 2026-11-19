# Pension Simulator

An educational simulator of pay-as-you-go pension systems. You choose a country and a retirement age, and the simulator shows how the population and the pension system's finances develop.

In a pay-as-you-go system, the pensions of today's retirees are paid directly by today's workers. The system depends on the number of contributors per retiree. That number has fallen for decades as people live longer and have fewer children.

The first version covers France, Germany, Italy, and Spain.

## Status

Design phase. The model and vocabulary are written down, and the code is not yet written.

## Documents

- [`docs/model.md`](docs/model.md): the mathematics of the model.
- [`CONTEXT.md`](CONTEXT.md): the vocabulary used in the project.
- [`docs/adr/`](docs/adr/): the reasons for the less obvious design decisions.

## Planned architecture

- A plain Python package that holds the model, built on NumPy.
- A thin, stateless FastAPI layer with two endpoints: `GET /countries` and `POST /simulate`.
- One data file per country, built by an offline script from United Nations and OECD data.
- A web frontend, added in a later phase.

## License

MIT
