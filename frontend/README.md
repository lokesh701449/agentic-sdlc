# Agentic SDLC System — Frontend Dashboard

A modern, responsive dark-themed dashboard built with **Next.js**, **TypeScript**, and **Tailwind CSS** to visualize and manage the end-to-end execution of the Agentic SDLC pipeline in real-time.

---

## Technical Stack

- **Framework**: Next.js 15+ (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Data Fetching & State**: TanStack React Query (configured for 3s active polling) & Axios
- **Icons**: Lucide React

---

## Folder Structure

```text
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx         # Dark theme layout with Sidebar navigation
│   │   ├── page.tsx           # Dashboard Homepage: active workflow tracker
│   │   ├── providers.tsx      # TanStack QueryClient provider wrapper
│   │   ├── history/
│   │   │   └── page.tsx       # Workflow History table and tracking deep links
│   │   └── monitoring/
│   │       └── page.tsx       # KPI cards and average agent duration bars
│   ├── components/
│   │   ├── Sidebar.tsx        # Left side panel navigation link
│   │   └── FileViewer.tsx     # Modal viewer displaying raw generated code
│   └── utils/
│       └── api.ts             # Base Axios instance targeting backend API
├── package.json
└── README.md
```

---

## API Integration Details

The dashboard integrates with the FastAPI backend through the following endpoints:

1. **`POST /workflow`**: Trigger new SDLC task planning (processed in background task).
2. **`POST /workflow/{id}/approve`**: Approve planning outputs and run Coding/Testing/Monitoring in background task.
3. **`POST /workflow/{id}/reject`**: Cancel the active workflow.
4. **`GET /workflows`**: Retrieve all past workflow records from SQLite.
5. **`GET /workflow/{id}`**: Retrieve execution status for a specific workflow.
6. **`GET /workflow/{id}/tasks`**: Retrieve generated plan tasks list.
7. **`GET /workflow/{id}/metrics`**: Retrieve agent execution timing metrics and test suites.
8. **`GET /workflow/{id}/files`**: Retrieve generated file names and compilation paths.
9. **`GET /file-content`**: Retrieve source code content of a generated module (safely protected from path traversals).

---

## Getting Started

### 1. Requirements

Ensure you have **Node.js (v18+)** and **npm** installed.

### 2. Install Dependencies

Navigate to the `frontend/` directory and install the packages:

```bash
cd frontend
npm install
```

### 3. Configure API Address

By default, the frontend points to the FastAPI API running on `http://127.0.0.1:8000`. You can configure a custom API URL using environment variables:

Create a `.env.local` inside `frontend/` with:
```env
NEXT_PUBLIC_API_URL=http://your-fastapi-server-url
```

### 4. Run Development Server

Start the Next.js development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser to view the dashboard.

---

## Screenshots

*(Screenshots will be uploaded here once captured during deployment testing)*
- **Dashboard Homepage**: Triggers a requirement description, prompts for user approval, and renders dynamic timeline stages.
- **Workflow History**: Paginated listing of past workflow outputs stored in SQLite.
- **System Monitoring**: Renders success rates, agent performance KPIs, and graphical execution time comparisons.
- **File Inspector**: Renders generated Python code in a custom, modal text viewer.
