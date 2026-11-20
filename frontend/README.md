# Pension Simulator front end

One static page. Alpine.js holds the state of the controls, calls the service, and hands the
result to Observable Plot. There is no build step and no request to a third party: the three
libraries and the two font families are in this folder.

## How it is served

`create_app` in `src/pension_simulator/api.py` mounts this folder at `/`, after the API routes.
Run `uv run uvicorn --factory pension_simulator.api:create_app --reload` and open
http://127.0.0.1:8000/. The Dockerfile copies the folder into the image.

If the API lives on another origin, set `window.PENSION_API_BASE = "https://..."` in a script
tag before `app.js`, and allow that origin with CORS on the service.

## Files

| File | Content |
|---|---|
| `index.html` | The markup, with Alpine directives. |
| `styles.css` | The design tokens (custom properties on `.ps`, light and dark) and every component. |
| `app.js` | State, requests, headline figures, and the six charts. |
| `vendor/` | Alpine.js 3.17.5 (MIT), D3 7.9.2 (ISC), Observable Plot 0.6.19 (ISC). |
| `fonts/` | Fraunces and IBM Plex Sans, Latin subset (SIL Open Font License). |

## How it behaves

- On load it calls `GET /countries`, then `POST /simulate` with the country alone for the baseline.
- Every control is live. A change sends `POST /simulate` with the country and only the values
  that differ from the defaults. Requests are limited to one per animation frame, and only one
  request is under way at a time. A change made during a request waits and goes out when that
  request returns. Each answer is drawn, so the charts follow a slider during a drag on a slow
  connection. A request with no answer after 10 seconds is given up and reported as failed. The
  charts keep the previous result until the new one arrives.
- If the service cannot be reached, the last result stays and a quiet message appears.
- The scenario is kept in the address, for example `?country=ITA&age=70&rule=cut_pensions&to=2100`,
  so a visitor can share what they see.
- Below 900 px the controls become a sheet at the bottom of the screen. The retirement age
  slider stays visible while the visitor scrolls the charts.
- The theme follows the system setting until the visitor uses the switch.

## Things to know

- **Axis scaling** is in `fitScale` in `app.js`. The y domain is the data range plus 6% of air on
  each side, so a curve spans about 88% of the plot for every country and scenario. Ticks are
  round values inside the domain. Zero joins the domain when the data come close to it, and
  always for pension debt. A chart that does not start at zero says so above its axis.
- **"Below working age"** in the pyramid ends at age 20 (`WORKING_AGE_FROM` in `app.js`, taken
  from `FIRST_AGE` in `ledger.py`). The population model itself has no lower bound.
- **Default positions.** Germany and Spain have default retirement ages off the three-month
  grid (66.17 and 66.67). The slider shows the exact default and returns to it when the thumb
  is back on the marker. The same holds for the other sliders.
- **Payload.** `/simulate` returns the whole population table, about 100 kB of JSON per call.
  This is fine on one machine. Turn on gzip (`GZipMiddleware`) before deploying.
- The "How this works" section links to `docs/model.md` and `docs/modelling-choices.md` on GitHub. Change
  it in `index.html` if the repository moves.
