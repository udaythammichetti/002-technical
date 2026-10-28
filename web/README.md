# Signal Desk UI

React + Vite front end for [Signal Desk](../README.md) (Volume · Technical · Lab · Chart · Spurts).

## Scripts

```bash
npm install
npm run dev      # http://127.0.0.1:5173 — proxies /api → :8797
npm run build    # writes dist/ for the Python server
npm run preview  # preview production build
npm run lint
```

Start `python -u server.py` (or `./launch.sh`) in the repo root so `/api` has a backend.

## Stack

- React 19 + Zustand
- Vite 8
- Oxlint

See the root [README](../README.md) for desks, Book universes, and API notes.
