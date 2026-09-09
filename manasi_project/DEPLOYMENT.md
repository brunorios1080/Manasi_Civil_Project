# Dashboard deployment

Public URL: https://manasi-stormwater-study.vercel.app

Vercel project: `manasi-stormwater-study`, in `brunos-projects-623482a2`.
Published September 9, 2026, from `../vercel-dashboard`.

The deployment is a static copy of `stormwater_dashboard.html`. The allowlist
in `../vercel-dashboard/.vercelignore` uploads only `index.html` and `vercel.json`.

To publish updated results, run from `/Users/bruno/Desktop/manasi`:

```sh
cp manasi_project/stormwater_dashboard.html vercel-dashboard/index.html
npm exec --cache /private/tmp/manasi-vercel-npm --yes --package vercel -- vercel deploy --cwd vercel-dashboard --prod --yes
```

Verified the public URL in a fresh browser session: HTTP 200, chart rendering,
rainfall selection, full-drainage toggle, and mobile layout at 390 pixels wide.
The default case shows 63.1% peak reduction; the 100 mm case shows 162.526 m³
overflow. No JavaScript errors were reported.
