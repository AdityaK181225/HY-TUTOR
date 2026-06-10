# HY-TUTOR: AI-Driven Socratic Study Engine

<p align="center">
  <img src="hytutor_main.png" alt="HY-TUTOR logo" width="160"/>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-PolyForm%20Noncommercial-orange.svg" alt="License: PolyForm Noncommercial 1.0"/></a>
  <a href="https://aistudio.google.com/app/apikey"><img src="https://img.shields.io/badge/Powered%20by-Google%20Gemini-8E75B2.svg" alt="Powered by Google Gemini"/></a>
  <a href="#-status"><img src="https://img.shields.io/badge/status-stable--release-orange.svg" alt="Pre-release"/></a>
</p>




**A free alternative to NotebookLM, built for STEM competitive exam preparation (Competitives , CBSE Classes 11-12)**

&nbsp;

&nbsp;

---

## 🎯 What is HY-TUTOR?

**HY-TUTOR is a Socratic Study Engine** that accelerates syllabus coverage for **STEM competitive exams (JEE, NEET,IAT,Other Competitives, CBSE Classes 11-12)** by intelligently aligning **NCERT textbooks with reference books**. For subjects like Biology, where NCERT content must be followed word-for-word, HY-TUTOR ensures perfect alignment while supplementing with competitive-depth material from reference books—**only for the chapters being studied**.

Unlike traditional coaching lectures—where 1-2 topics can take hours—HY-TUTOR delivers **focused, in-depth understanding** by:

- Processing **NCERT textbook content** directly
- Extracting **only the relevant portions** from reference books linked to specific chapters
- **Stripping out-of-syllabus content** while retaining all essential concepts
- Providing a **NotebookLM-style split-screen learning dashboard** (lesson Markdown on the left, Socratic chat on the right, with a "Similar Problems" semantic-search panel below)

It is designed for **time-constrained students** who want to cover large syllabus portions efficiently without sacrificing depth, as well as **self-learners** who lack access to coaching or tuition but seek a comprehensive understanding.

---

## ✨ Key Features

- **Multi-subject isolation** — Physics, Chemistry, Mathematics, and Biology each get their own workspace, tracker, UI session, and ChromaDB store under `data_library/subject_workspaces/<subject>/`
- **NCERT + Reference Book Alignment** — Intelligently links NCERT content with reference material, focusing only on syllabus-relevant portions
- **Socratic Dialogue Engine** — Adaptive tutoring with pacing shields, prerequisite gating, and a 3-state edge router (`STATE_A`: clear path, `STATE_B`: prerequisite block, `STATE_C`: weak-area review)
- **NotebookLM-style split-screen dashboard** — Lesson Markdown (55%) + Socratic chat (45%) + "Similar Problems" semantic-search panel
- **Multi-file upload** — Every upload slot accepts multiple `.md`/`.txt` files; they are concatenated into one canonical file with `--- filename ---` markers
- **Per-subject ChromaDB** — Semantic "Similar Problems" search with difficulty-tier filters (Easy / Medium / Hard), wired to C5.5 (problems) and C5 (lesson sections)
- **Interactive syllabus review & edit** — Chat with the "Architect" LLM to refine the master syllabus before locking it in
- **Per-chunk navigation** — Previous / Reset / Exit on the learning dashboard, with per-chunk re-compile on demand
- **Real-time pipeline runner** — DAG visualization with per-command status badges, re-run buttons, and a 10-category error-diagnosis engine
- **Recovery panel** — Retry / skip / restart / clear for failed chunks
- **Update checker** — Settings → About tab shows version status with a colored pill badge, plus a one-click "Update & install now" flow
- **Subject metrics sidebar** — Chapters-completed %, weak-area flags, and per-subject isolation
- **Scholarly-ink theme** — NotebookLM-inspired with custom CSS, dynamic accent and background color pickers, and popover-based settings
- **Cross-platform** — Linux and Windows installers with desktop-icon and Start-Menu integration

---

## 🚀 Current Workflow to be followed manually

### For Students:

1. **Reference Book Selection** — Choose 1-2 reference books per subject (e.g., Vinay Kumar for Mathematics)
2. **Content Acquisition** — Download book PDFs from **trusted free sources** (e.g., pdfcoffee)
3. **Format Conversion** — Convert PDFs to Markdown (using tools like [marker-pdf](https://github.com/Uncoded-LLC/marker-pdf))
4. **Content Processing** — Upload the book's table of contents and chapter content files, then follow the detailed [USER_GUIDE.md](USER_GUIDE.md) for the complete step-by-step workflow
5. **AI-Powered Learning** — Access focused, exam-aligned modules via the split-screen dashboard

### Automated Roadmap (Coming Soon):


| Feature                         | Status    | Description                                                                                                                                         |
| ------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **In-App Book Download**        | 🔜 Future | Directly search/download books from pre-configured sources (e.g., pdfcoffee) with pre-chosen options (Vinay Kumar, etc.) and Google search fallback |
| **PDF Parser (OCR Subproject)** | 🔜 Future | Automatically perform OCR on uploaded PDFs, split books into chapters/folders, and convert to Markdown/TXT (eliminating manual cropping)            |
| **Multi-API Support**           | 🔜 Future | Support multiple LLM providers beyond Google Gemini (model-fallback chain already implemented)                                                      |
| **Free Access Guarantee**       | 🔜 Future | Ensure zero-cost usage via optimized API providers and free-tier options                                                                            |
| **Visualization Support**       | 🔜 Future | Add images, diagrams, and graphs window to facilitate visualization in STEM subjects                                                                |


---

## 📋 Table of Contents

- [🤖 AI Use Disclosure](#-ai-use-disclosure)
- [📸 Looks](#-looks)
- [🚀 Quick Start](#-quick-start)
- [🧠 LLM Strategy](#-llm-strategy)
- [🏗 Architecture](#-architecture)
- [📚 Pipeline Commands](#-pipeline-commands)
- [🎨 UI Features in Detail](#-ui-features-in-detail)
- [📝 Changes](#-changes)
- [🐛 Bug Fixes](#-bug-fixes)
- [🩺 Known Bugs (Prevalent)](#-known-bugs-prevalent)
- [🚧 Future Upgrades Planned](#-future-upgrades-planned)
- [🛠 Troubleshooting](#-troubleshooting)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [🙏 Acknowledgements](#-acknowledgements)

---

## 🤖 AI Use Disclosure

This project was developed with **significant assistance from AI tools (large language models)**. With all due respect, we acknowledge the role AI has played:

- **Pipeline debugging** — diagnosing API failures, recovery from JSON-decode errors, race conditions in subprocess orchestration
- **Architectural refactors** — per-chapter folder model, per-subject workspace isolation, per-subject ChromaDB vector store
- **Code generation** — ChromaDB integration, the auto-update + pip-install flow, the `index_active_chunk()` helper, the `read_pdf_text` removal, the multi-file concatenation helper

All **architectural decisions, code review, and final integration** were performed by the human maintainer. AI was an amplifier of the maintainer's intent, not a replacement for it.

---

## 📸 Looks

### 1. System Configuration Mode (multi-file syllabus upload)

![System Configuration Mode — Syllabus Upload](screenshots/01-syllabus-upload.png)

The first screen a new user sees. The Subject Metrics sidebar reports chapters-completed (e.g., `1 / 31`, `3%`). The main panel shows the four mandatory upload slots (CBSE Syllabus Guidelines, NCERT TOC, Reference Book TOC, Exemplar + Question Bank) — each accepting multiple `.md`/`.txt` files. Submitting triggers `command_0_syllabus.py` and transitions to the Syllabus Review state.

### 2. Syllabus Review & Edit (Architect chat)

![Syllabus Review & Edit — Architect Chat](screenshots/02-syllabus-review.png)

The Master Syllabus is rendered as a vertical list of chapter expanders (e.g., `CH_11_01: Sets`, `CH_11_02: Relations and Functions`, `CH_11_03: Trigonometric Functions`) each showing cross-grade prerequisites, atomic chunks with competitive-focus badges, core milestones, and execution-profile flags. Below the chapter list sits the "Architect Modification Chat" — a textarea + send button that calls `command_0_1_editor.py`. A "✅ Confirm Syllabus & Proceed" primary button at the bottom locks the syllabus.

### 3. Pipeline Runner (DAG visualization)

![Pipeline Runner — DAG Compilation](screenshots/03-pipeline-runner.png)

The real-time pipeline runner shows each DAG node with status badges, re-run buttons, and a 10-category error-diagnosis engine. Nodes execute sequentially from Blueprint through Injector, with the Recovery Panel handling any failed chunks.

---

## 🚀 Quick Start

### Requirements

- **Python 3.10+** (3.11 recommended)
- **Google Gemini API key** — [get one free here](https://aistudio.google.com/app/apikey)
- **4 GB+ RAM** and a modern browser
- **No GPU required** — Gemini runs in the cloud

### Linux

```bash
# 1. Clone the repo
git clone https://github.com/AdityaK181225/HY-TUTOR.git
cd HY-TUTOR

# 2. Run the one-shot installer
bash install.sh

# 3. (Optional) Add the desktop icon — appears in your app menu and on your Desktop
bash make_desktop.sh

# 4. Launch
bash launch_engine.sh
```

### Windows (PowerShell)

```powershell
# 1. Clone the repo
git clone https://github.com/AdityaK181225/HY-TUTOR.git
cd HY-TUTOR

# 2. Run the one-shot installer
powershell -ExecutionPolicy Bypass -File .\install.ps1

# 3. (Optional) Add a desktop + Start Menu shortcut
powershell -ExecutionPolicy Bypass -File .\make_desktop.ps1

# 4. Launch
.\launch_engine.bat
```

Your browser will open `http://localhost:8501` automatically.

### What the installer does

1. Detects Python 3.10+ (or guides you to install it)
2. Creates a `.venv/` virtual environment
3. Installs all `requirements.txt` packages
4. Seeds `config/.env` from `config/.env.example`
5. Prompts (masked) for your Gemini API key and saves it to `config/.env`
6. Validates the key format (`^AIza[A-Za-z0-9_-]{30,50}$`)

If you skip the key prompt, the in-app **First-Run Wizard** will collect it when Streamlit first loads.

---

## 🧠 LLM Strategy


| Tier  | Model                        | Role                                                            | Where |
| ----- | ---------------------------- | --------------------------------------------------------------- | ----- |
| Cloud | Google Gemini (`gemini-...`) | Heavy reasoning, content generation, tutoring, syllabus editing | Cloud |


The pipeline uses a **model-fallback chain** in `core_pipeline/utils/inference.py` so that transient 5xx errors or rate limits automatically rotate to the next available model.

---

## 🏗 Architecture

```
HY-TUTOR/
├── config/                          # Environment config (.env)
├── core_pipeline/                   # All pipeline commands (do not edit casually)
│   ├── command_0_syllabus.py        # Syllabus builder (4-source, domain-adaptive)
│   ├── command_0_1_editor.py        # Syllabus editor (LLM-powered, robust JSON parser)
│   ├── command_0_5_router.py        # Edge router (3-state machine: A/B/C)
│   ├── command_1_blueprint.py       # Blueprint generator (chunk planning + per-chunk files)
│   ├── command_2_miner.py           # NCERT verbatim extraction (single-block prompt)
│   ├── command_3_optimizer.py       # Reference manual processing (5000-word windows)
│   ├── command_4_bridge.py          # NCERT ↔ Reference cognitive linking
│   ├── command_5_forge.py           # Unified Lesson synthesis (LaTeX-rich) + index
│   ├── command_5_5_injector.py      # Exemplar problem extraction + ChromaDB indexing
│   ├── command_6_tutor.py           # Socratic dialogue engine
│   ├── command_7_ledger.py          # Session scoring + tracker updates
│   ├── command_8_compile_notes.py   # Per-chapter notes.md compiler (Phase 2)
│   ├── orchestrator.py              # DAG execution engine + archive copy step
│   └── utils/                       # Shared infrastructure
│       ├── paths.py                 # Per-subject SubjectPaths dataclass
│       ├── vector_db.py             # Subject-aware ChromaDB manager
│       ├── genai_client.py          # Gemini API client with model-fallback
│       ├── inference.py             # LLM invocation wrapper
│       ├── embedding_utils.py       # Compressed embedding helpers
│       ├── file_utils.py            # Multi-format text readers
│       ├── recovery.py              # Failed-chunk recovery manager
│       ├── update_checker.py        # Git + pip auto-update
│       ├── usage_tracker.py         # Per-chapter usage metrics
│       └── logging_utils.py
├── interface/                       # Streamlit UI
│   ├── app.py                       # Main app (state machine)
│   ├── assets/custom_style.css      # NotebookLM-inspired theme
│   └── components/                  # Sidebar, chat box, lesson viewer, wizard, …
├── data_library/                    # All data artifacts (per-user state, raw uploads, vector DB)
├── install.sh / install.ps1         # One-shot installers
├── launch_engine.sh / .bat          # Launchers
├── make_desktop.sh / .ps1           # Desktop-icon installers
├── requirements.txt
├── hytutor_main.png                 # Project logo / desktop icon
└── README.md
```

&nbsp;

---

## 📚 Pipeline Commands


| Stage | Command          | Purpose                                                                                  |
| ----- | ---------------- | ---------------------------------------------------------------------------------------- |
| 0     | Syllabus Builder | Synthesizes 4 source TOCs into a domain-adaptive syllabus                                |
| 0.1   | Syllabus Editor  | LLM-powered edits with robust JSON extraction (3-stage parser)                           |
| 0.5   | Edge Router      | 3-state machine: `STATE_A` (clear), `STATE_B` (prereq block), `STATE_C` (weak-area)      |
| 1     | Blueprint        | Plans milestone-aligned atomic chunks + writes per-chunk files                           |
| 2     | Miner            | Verbatim NCERT extraction (one continuous VERBATIM_THEORY + supplementary LATEX_FORMULA) |
| 3     | Optimizer        | Reference manual processing with 5000-word windows                                       |
| 4     | Bridge           | NCERT ↔ Reference cognitive linking, competitive shortcuts                               |
| 5     | Forge            | Unified Lesson Markdown synthesis (LaTeX-rich) + ChromaDB index                          |
| 5.5   | Injector         | Exemplar problem extraction + ChromaDB indexing                                          |
| 6     | Tutor            | Socratic dialogue with pacing shields + tier classification                              |
| 7     | Ledger           | Session scoring, mastery tracking, chapter transitions                                   |
| 8     | Compile-Notes    | Compiles per-chapter `lesson/chunk_*.md` → `notes.md`                                    |


---

## 🎨 UI Features in Detail

### State machine (`interface/app.py`)

```
[no syllabus]  →  System Configuration Mode
        ↓ (Command 0 succeeds)
SYLLABUS_REVIEW  →  Architect chat + ✅ Confirm
        ↓
SELECTION  →  Pick chapter, "Run Pre-Flight Triage"
        ↓
TRIAGED  →  STATE_A (Upload chapter assets) | STATE_B (Prereq override) | STATE_C (Weak-area)
        ↓
PIPELINE_RUNNING  →  DAG runner with per-node re-run
        ↓
LEARNING  →  Split-screen lesson + chat + similar problems
```

### Per-component highlights

- `**sidebar.py**` — Domain switcher, per-subject metrics (chapters completed %, weak-area flags). State is pinned to disk per subject.
- `**chat_box.py**` — Per-chunk chat history, writes to `chapter_cache/active_session_history.json` (per-subject).
- `**lesson_viewer.py**` — Renders `Unified_Lesson.md` with LaTeX, resolves path via `SubjectPaths.chunk_paths()["lesson"]`.
- `**similar_problems.py**` — ChromaDB semantic search with Easy/Medium/Hard filter, attributed to `chapter_id` and `subject` in metadata.
- `**pipeline_runner.py**` — DAG view, status badges, **10-category error diagnosis engine** (rate limit, SSL, missing key, timeouts, missing files, etc.), per-node "🔄 Re-run" with cleanup-then-execute.
- `**recovery_panel.py**` — For failed chunks: retry / skip / restart / clear.
- `**settings_panel.py**` — Popover with tabs: **Appearance** (theme, accent, background), **Update** (version status + Update & install), **About** (project info, vector-DB management).
- `**first_run_wizard.py**` — Runs *before* `st.set_page_config`; collects and validates the Gemini API key in-browser with regex validation.

---

## 📝 Changes

### [v1.$\alpha$.0] — 2026-06-08 — FIRST STABLE RELEASE

- Many bug fixes and patches present in previous dev editions
- Change from single flat active_workspace to dynamic per-subject workspace
- Requirements installer package and setup for Windows and Linux
- API key can now be entered via in-app First-Run Wizard
- Multiple SDK backend wiring completed (slated to become active via Settings tab in future upgrades)
- PDF inputs temporarily removed for optimization (use marker-pdf or similar to convert PDFs to Markdown)

### [v1.$\alpha$.1] — 2026-06-09 — FIRST-RUN WIZARD + LAUNCH FIXES

- **First-run wizard redesigned** — Now shows only once (when `GEMINI_API_KEY` is missing), with a highlighted link to obtain a free key from Google AI Studio. After saving the key, a single click takes the user straight to the main dashboard.
- **Launch engine graceful degradation** — `launch_engine.sh` and `launch_engine.bat` no longer abort when `GEMINI_API_KEY` is empty; they warn and let Streamlit start so the in-app wizard can handle key setup.
- **Sidebar expand button** — Fixed the hamburger icon not rendering when the sidebar is closed (corrected `data-testid` selector in `custom_style.css`).

---

## 🐛 Bug Fixes

> Bug entries the maintainer has fixed in the codebase. Each entry includes the symptom, the root cause, and what the fix was.

### Bug #002 — Launch engine aborts when GEMINI_API_KEY is empty ✅ Fixed (2026-06-09)

**Severity:** High (blocks first launch entirely)
**Area:** `launch_engine.sh`, `launch_engine.bat`

**Symptom:**
After a fresh clone + `install.sh`, running `bash launch_engine.sh` would print a fatal error and exit before Streamlit ever started, even though the in-app First-Run Wizard was designed to collect the key.

**Root cause:**
`launch_engine.sh` and `launch_engine.bat` both performed `exit 1` when `GEMINI_API_KEY` was empty, preventing Streamlit from launching. The in-app wizard never got a chance to run.

**Fix:**
Changed the empty-key check from a fatal exit to a warning. Streamlit now starts regardless, and the First-Run Wizard handles key setup.

---

### Bug #003 — Sidebar expand button not visible when sidebar is closed ✅ Fixed (2026-06-09)

**Severity:** Medium (UI usability)
**Area:** `interface/assets/custom_style.css`

**Symptom:**
When the sidebar was collapsed, the expand button (hamburger icon) was not visible or showed raw `keyboard_double_arrow_right` text instead of the styled hamburger icon.

**Root cause:**
The CSS targeted `button[aria-label="Open sidebar"]` but the actual expand button has `data-testid="stBaseButton-headerNoPadding"` with an empty `aria-label`. The selectors never matched.

**Fix:**
Updated all sidebar-toggle CSS selectors to use the correct `data-testid="stBaseButton-headerNoPadding"` and `data-testid="stExpandSidebarButton"` selectors. Both the open and closed states now render a consistent ink-blue pill with three white hamburger lines.

---

### Bug #000 — Syllabus Editor crashes on chat-style prompts ✅ Fixed (2026-05-06)

**Severity:** Medium (UX crash)
**Area:** `core_pipeline/command_0_1_editor.py`, `interface/app.py`

**Symptom:**
When the user typed a chat-style question (e.g., "hi there do u think the syllabus is good enough?") into the **Architect Modification Chat** textarea and pressed submit, the syllabus editor subprocess crashed with:

```
Command '['python3', 'command_0_1_editor.py', 'Mathematics', '…'] returned non-zero exit status 1.
```

**Root cause:**

1. The Gemini API returned a response that contained prose + attempted JSON (the model treated a chat question as a conversational request rather than a structural modification).
2. `json.loads()` failed on the prose-wrapped response → `JSONDecodeError` → `sys.exit(1)`.
3. The caller in `app.py` passed the un-stripped `st.text_area` value (which could contain a trailing `\n`), compounding the issue.

---

## 🩺 Known Bugs (Prevalent)

> Unfixed bugs identified before the first public release. Each entry includes the symptom, the suspected root cause, and a suggested fix. **Contributors are welcome to pick one of these and submit a PR.**

### Bug #001 — Preset colour swatches in Settings → Appearance don't apply

**Severity:** Low (cosmetic / workflow)
**Status:** Unfixed
**Area:** `interface/components/settings_panel.py`

**Symptom:**
In the **Settings → Appearance** tab, clicking a preset colour swatch (e.g., "Forest Green" under Accent Color, or "Parchment" under Background Color) does not change the dashboard appearance. The colour picker (palette box) doesn't update to reflect the selected preset either.

The palette *does* work when clicked directly — the dashboard updates instantly. Only the one-click preset buttons are broken.

**How to reproduce:**

1. Open the app and click the ⚙️ Settings popover
2. Go to the **Appearance** tab
3. Under **Accent Color**, click any preset swatch (e.g., "Forest Green")
4. Observe: nothing changes — the accent stays "Ink Blue"
5. Click the colour picker (square palette) directly and pick a new colour
6. Observe: the dashboard updates immediately

---

## 🚧 Future Upgrades Planned

> Work that has been identified as needed but is not yet scheduled. Items here are scoped well enough to act on; the order is roughly the maintainer's priority.

### Primary Upgrade Plans

- **🔁 Re-implement PDF intake** — The legacy `read_pdf_text` 3-tier fallback (PyPDF2 / pdfminer.six / empty-string) couldn't handle equation-heavy CBSE PDFs cleanly. A proper re-implementation will use OCR fallback + equation/table preservation (target library: `marker-pdf` or similar) Using the Pdf parser subproject(coming soon). Until then, the in-app banner reads *"📌 PDF intake coming soon"*.
- **📸 Add images, diagrams, and graphs window** — To facilitate visualization in important scenarios of STEM subjects.
- **🔌 Setup AI modals and API key tab in Settings** — Move away from only Gemini-based system to support other providers as well (backend development under progress).
- **📝 Wire `command_8_compile_notes.py` into the orchestrator** — Currently `notes.md` is generated on demand. Hook C8 into the orchestrator so it auto-fires when the last chunk of a chapter is marked `COMPLETED` in the tracker.

### Secondary Upgrade Plans

- **🎨 Fix Bug #001 (preset colour swatches)** — Ensure preset colour swatches in Settings → Appearance apply correctly.
- **🌐 Multi-language syllabus support** — Hindi and regional-language textbook support.
- **📊 Richer progress dashboard** — Charts (mastery over time, weak-area heatmap, study-time per chapter) using Plotly.
- **🔌 Pluggable vector-DB backend** — ChromaDB is hard-coded in `vector_db.py`. A backend abstraction would let users swap in FAISS, Qdrant, or Weaviate without code changes.

### Tertiary Upgrade Plans

- **💾 Offline / cached-mode LLM** — Cache LLM responses per (subject, chapter_id, chunk_index) to avoid re-generating expensive lesson synthesis if the user navigates away and back.
- **🧭 Improved prerequisite graph visualization** — The 3-state router resolves the next chapter but doesn't show *why*. A small graph view would let students see the prerequisite chain at a glance.
- **📚 Expand to higher STEM studies** — Extend beyond Class 11-12 to engineering, medicine, and other advanced subjects.

---

## 🛠 Troubleshooting

- **"ModuleNotFoundError" on launch** — Your `.venv` is missing. Run `bash install.sh` (Linux/macOS) or `.\install.ps1` (Windows).
- **"GEMINI_API_KEY is empty"** — The launch engine now shows a warning and lets Streamlit start. The in-app **First-Run Wizard** will guide you through setting the key on first launch.
- **Streamlit doesn't open a browser** — Manually visit `http://localhost:8501`.
- **Desktop icon doesn't show up on Linux** — Your file manager may need a refresh, or you may need to right-click → "Allow Launching" on the file.
- **Windows: "Running scripts is disabled on this system"** — Prepend `powershell -ExecutionPolicy Bypass` to the command, as shown in the Quick Start above.
- **ChromaDB install fails on Windows** — Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/?q=build+tools) and retry.
- **"No similar problems found" in the Learning Dashboard** — The ChromaDB index is per-subject and per-chunk. Run the full pipeline (C1 → C5.5) for the chapter first; indexing happens at the end of C5.5.
- **Pipeline fails with "rate limit"** — The model-fallback chain in `core_pipeline/utils/inference.py` rotates to the next model automatically. If all models are exhausted, wait 1–2 minutes and click the per-node "🔄 Re-run" button on the failed node.
- `**git pull` failed because of local changes** — The Settings → About "Update & install now" refuses to merge dirty trees. Stash or commit your local changes first.

---

## 🤝 Contributing

We welcome PRs! Here's how to get started:

1. **File an issue first** for any non-trivial change so we can discuss the approach.
2. **Pre-release bug list** — The [🩺 Known Bugs](#-known-bugs-prevalent) section above lists issues that are open for grabs. Pick one and submit a fix; we'll review and merge.
3. **Code style** — Python 3.10+, 4-space indent, LF line endings (enforced by `.editorconfig` + `.gitattributes`), follow the existing patterns in each module.
4. **Test before submitting:**
  ```bash
   python tests/test_imports.py    # 43 import tests
   python tests/test_vector_db.py  # 9 vector-DB tests
  ```
5. **Don't put public docs in `docs/**` — That directory is git-ignored. Anything that should be visible to GitHub visitors must live in this README or in source code.

**Repository etiquette:**

- Reference the relevant section of this README (e.g., "Fixes Bug #001") in the PR description.
- For changes that touch `core_pipeline/`, run a live end-to-end run with a real Gemini key(or any key if the multi api sector has been sorted out) before requesting review.

---

## ✍️ A Note from the Author

Hey! Thank you so much for checking out HY-TUTOR. 🚀

This project was built over a long stretch of late nights, endless cups of coffee, and intense academic workloads. To keep things balanced and focus on other goals, I am temporarily taking a short, much-needed break from active core development.

Because of this, my contributions here will be sporadic for a little while. However, the project is stable, fully functional, and ready to use out of the box! I would be incredibly grateful if the open-source community stepped in to help guide this codebase. If you have ideas, bug fixes, or enhancements aligned with the vision of making learning fast and free, your PRs are warmly welcomed.

Please report any bugs or issues directly via GitHub, and I will check in whenever I can. Thank you for supporting accessible, self-directed learning!
---

## 📄 License

HY-TUTOR is licensed under the **PolyForm Noncommercial License 1.0.0**.

- ✅ **Free for:** Personal study, non-commercial educational use, internal research, open-source contributions, and any use that does not generate revenue.
- ❌ **Requires a separate commercial license for:** Selling the software, hosting it as a paid service, embedding it in a commercial ed-tech product, or using it to provide paid tutoring services.

For commercial licensing inquiries, open a GitHub issue at [AdityaK181225/HY-TUTOR/issues](https://github.com/AdityaK181225/HY-TUTOR/issues) tagged `commercial-license`. The full license text is in [LICENSE](LICENSE).

**Contributions** are accepted under the [Developer Certificate of Origin 1.1](https://developercertificate.org/) with an **Inbound=Outbound** clause (see [CONTRIBUTING.md](CONTRIBUTING.md)). In short: by DCO-signing your commits, you grant the maintainer the right to relicense your contribution under any license terms, current or future, while you retain ownership and the right to use your own code independently. A DCO-checking GitHub App (Probot DCO) blocks PRs that aren't signed.

---

## 🙏 Acknowledgements

- **To My Mother:** My deepest gratitude goes to my mother. Thank you for being my anchor, my constant source of emotional support, and for keeping me fed and functional when everything else was falling apart. This would genuinely not have been possible without you.
- **To My Special Friends:** To my inner circle of close friends who kept me grounded. Thank you for listening to me vent, making me laugh, and reminding me that a life exists outside of this work.
- **To the Board:** I acknowledge the Examination Board for providing the official framework, guidelines, and deadlines that forced me to actually finish this project.
- **To the Severe Lack of Teaching Facilities:** This era of education becoming a business, with a lack of self-learning opportunities, has acted as a great motivation and inspiration for this project. By teaching everything to myself, I successfully became my own mentor, faculty, and emotional support system.
- **To the Corporate Giants and EdTech Conglomerates:** A nod to the massive, multi-billion-dollar educational platforms and IT giants. Thank you for dominating the internet with endless paywalls and marketing, which ultimately inspired me to ignore the noise and just figure things out on my own anyway.
- **To the Non-Contributors:** To the people who did absolutely nothing to help with this project—thank you. Your complete absence ensured that no one messed up my workflow, which turned out to be a brilliant form of accidental assistance.
- **To Everyone Who Adjusted to My Chaos:** Finally, a massive thank you to everyone who tolerated my chaotic schedule over the past few months. Thank you for forgiving my chronic lateness, understanding why I couldn't give you my time, and adjusting your own lives to fit my erratic availability. Your patience did not go unnoticed.

Built with care, an Asus TUF F15, Zorin OS 18.1, and a lot of coffee. ☕
