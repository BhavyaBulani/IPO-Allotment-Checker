# IPO Checker — Frontend

React 19 + Vite frontend for the IPO Allotment Checker application.

## Stack

- **React 19** — UI library
- **Vite** — Build tool & dev server
- **TailwindCSS** — Utility-first CSS
- **Axios** — HTTP client
- **lucide-react** — Icon set
- **react-router-dom** — Client-side routing
- **react-dropzone** — Drag-and-drop file upload

## Commands

```bash
# Install dependencies
npm install

# Start development server (http://localhost:5173)
npm run dev

# Run linter (oxlint)
npm run lint

# Build for production
npm run build

# Preview production build locally
npm run preview
```

## Configuration

The API base URL is configured in [`src/lib/api.js`](./src/lib/api.js). By default it points to `http://localhost:8000/api`. Update this for staging or production deployments.

## Project Structure

```
src/
├── components/         # Shared UI components
│   ├── IpoMultiSelect.jsx
│   ├── CaptchaPrompt.jsx
│   └── ClientUploadModal.jsx
├── pages/              # Route-level views
│   ├── ModeSelection.jsx
│   ├── SingleClientEntry.jsx
│   ├── BulkUpload.jsx
│   ├── ProgressScreen.jsx
│   ├── ResultsDashboard.jsx
│   └── HistoryScreen.jsx
├── lib/
│   └── api.js          # Axios instance
├── App.jsx
└── main.jsx
```

## Linting

This project uses [oxlint](https://oxc.rs/docs/guide/usage/linter.html) for fast linting. Rules are configured in [`.oxlintrc.json`](./.oxlintrc.json).

