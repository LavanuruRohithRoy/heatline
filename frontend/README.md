# Heatline frontend

Vite + React + TypeScript dashboard for the Heatline heat-compliance decision-support demo.

## Local development

```bash
npm install
npm run dev
```

Set `VITE_API_BASE_URL` in `.env` to the FastAPI backend URL. The frontend never triggers a paid request from the public landing page.

## Production build

```bash
npm run build
```
