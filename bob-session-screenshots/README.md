# IBM Bob Task Session Summaries

This directory contains exported IBM Bob task session summaries for the **BugSleuth** project, submitted as part of the **IBM TechXchange 2026 Pre-conference Dev Day Hackathon** by Team **BobBuilders**.

These are a required hackathon deliverable. They document how IBM Bob was used as the primary development tool throughout the entire project.

---

## How to Export a Bob Task Session Summary

Bob can export a session summary as either **Markdown** or **JSON**:

### Option A — Export as Markdown (`.md`)

1. Open the task in IBM Bob
2. Click the **"..."** menu at the top of the task panel
3. Select **"Export"** → **"Export as Markdown"**
4. Save the file into this directory with a descriptive name
   - e.g. `01-architecture-design.md`

### Option B — Export as JSON (`.json`)

1. Open the task in IBM Bob
2. Click the **"..."** menu at the top of the task panel
3. Select **"Export"** → **"Export as JSON"**
4. Save the file into this directory with a descriptive name
   - e.g. `01-architecture-design.json`

Either format is accepted. **Markdown is easier for judges to read directly on GitHub.**

---

## Sessions to Document

Export a summary for each major Bob session used on this project:

| # | Session | Suggested filename |
|---|---|---|
| 1 | Architecture design and system planning | `01-architecture-design.md` |
| 2 | Investigators module development | `02-investigators.md` |
| 3 | Tribunal (Prosecutor / Defense / Judge) | `03-tribunal.md` |
| 4 | Frontend (HTML / CSS / JavaScript) | `04-frontend.md` |
| 5 | Test suite (unit, integration, API) | `05-tests.md` |
| 6 | Debugging and bug-fix sessions | `06-debugging.md` |
| 7 | GitHub repo and documentation setup | `07-repo-setup.md` |

---

## After Adding Files — Push to GitHub

```powershell
git add bob-session-screenshots/
git commit -m "Add Bob session summary exports"
git push
```

---

*See the project [README](../README.md) for full details on how IBM Bob was used throughout the project.*
