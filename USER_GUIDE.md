# HY-TUTOR: User Guide

<div align="center">

  *A comprehensive step-by-step guide for using the AI-Driven Socratic Study Engine*

  [← Back to README](README.md)

</div>

---

## Table of Contents

- [1. Introduction](#1-introduction)
- [2. System Requirements](#2-system-requirements)
- [3. Installation Overview](#3-installation-overview)
- [4. Launching HY-TUTOR](#4-launching-hy-tutor)
  - [4.1 Launch via Desktop Icon (Linux)](#41-launch-via-desktop-icon-linux)
  - [4.2 Launch via Terminal / Command Prompt](#42-launch-via-terminal--command-prompt)
  - [4.3 Accessing the App](#43-accessing-the-app)
- [5. First-Run Setup: API Key Configuration](#5-first-run-setup-api-key-configuration)
- [6. Step-by-Step Usage Workflow](#6-step-by-step-usage-workflow)
  - [Phase A — Setting Up a Subject](#phase-a--setting-up-a-subject)
    - [Step 1: Select a Subject](#step-1-select-a-subject)
    - [Step 2: Upload the 4 Syllabus Source Files](#step-2-upload-the-4-syllabus-source-files)
    - [Step 3: Review & Edit the Syllabus (Optional)](#step-3-review--edit-the-syllabus-optional)
    - [Step 4: Confirm the Syllabus](#step-4-confirm-the-syllabus)
  - [Phase B — Preparing a Chapter for Study](#phase-b--preparing-a-chapter-for-study)
    - [Step 5: Select a Chapter](#step-5-select-a-chapter)
    - [Step 6: Run Pre-Flight Route Triage](#step-6-run-pre-flight-route-triage)
    - [Step 7: Handle Prerequisite Lockout (STATE B)](#step-7-handle-prerequisite-lockout-state-b)
    - [Step 8: Upload Chapter Content Assets](#step-8-upload-chapter-content-assets)
    - [Step 9: Execute the Compilation Pipeline](#step-9-execute-the-compilation-pipeline)
  - [Phase C — The Learning Dashboard](#phase-c--the-learning-dashboard)
    - [Step 10: Split-Screen Learning](#step-10-split-screen-learning)
    - [Step 11: Chunk Navigation](#step-11-chunk-navigation)
    - [Step 12: Similar Problems](#step-12-similar-problems)
    - [Step 13: Recovery Panel](#step-13-recovery-panel)
  - [Phase D — Advanced Features](#phase-d--advanced-features)
    - [Step 14: Settings](#step-14-settings)
    - [Step 15: Switching Subjects](#step-15-switching-subjects)
- [7. Understanding the Pipeline Stages](#7-understanding-the-pipeline-stages)
- [8. Preparing Source Files (Before You Start)](#8-preparing-source-files-before-you-start)
  - [8.1 Acquiring Reference Books](#81-acquiring-reference-books)
  - [8.2 Cropping to a Chapter](#82-cropping-to-a-chapter)
  - [8.3 Converting to Markdown](#83-converting-to-markdown)
- [9. Troubleshooting Common Issues](#9-troubleshooting-common-issues)
- [10. Frequently Asked Questions (FAQ)](#10-frequently-asked-questions-faq)

---

## 1. Introduction

**HY-TUTOR** is an AI-powered Socratic study engine designed for **Class XI/XII STEM subjects** — Physics, Chemistry, Mathematics, and Biology. It compiles raw study materials (CBSE syllabus, NCERT textbooks, reference books, and question banks) into structured, interactive lessons accelerated by Google Gemini AI.

The system runs entirely on your local machine as a **Streamlit web app** (no data leaves your computer except API calls to Google Gemini). It provides a **split-screen learning dashboard** with LaTeX-rich lesson content on one side and a conversational Socratic tutor on the other.

> **Target exams:** JEE (Main & Advanced), NEET, CBSE Board Exams (Class 11 & 12)

---

## 2. System Requirements

| Requirement | Minimum |
|-------------|---------|
| **Python** | 3.10+ (3.11 highly recommended) |
| **RAM** | 4 GB |
| **Storage** | ~500 MB for the app + space for study materials |
| **OS** | Linux (any distro) or Windows 10/11 |
| **Browser** | Modern (Chrome, Firefox, Edge, etc.) |
| **GPU** | Not required — Gemini runs in the cloud |
| **Internet** | Required for API calls to Google Gemini |
| **API Key** | Free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey) |

---

## 3. Installation Overview

If you haven't installed HY-TUTOR yet, here is a quick recap of the installation steps. **Full instructions are in the [README → Quick Start](README.md#-quick-start).**

### Linux

```bash
git clone https://github.com/AdityaK181225/HY-TUTOR.git
cd HY-TUTOR
bash install.sh
bash make_desktop.sh            # Optional: creates desktop icon
```

### Windows (PowerShell)

```powershell
git clone https://github.com/AdityaK181225/HY-TUTOR.git
cd HY-TUTOR
powershell -ExecutionPolicy Bypass -File .\install.ps1
powershell -ExecutionPolicy Bypass -File .\make_desktop.ps1   # Optional: creates desktop + Start Menu shortcuts
```

> **What the installer does:** Creates a Python virtual environment (`.venv/`), installs all dependencies, and prompts you for your Gemini API key. If you skip the key prompt, the app's **First-Run Wizard** will ask for it when you launch.

---

## 4. Launching HY-TUTOR

### 4.1 Launch via Desktop Icon (Linux)

If you ran `bash make_desktop.sh` during installation:

1. Look for the **HY-TUTOR** icon on your desktop (the purple atom-shaped logo).
2. **Double-click** the icon.
3. A terminal window will open, activate the virtual environment, and launch Streamlit.
4. Your default browser will open `http://localhost:8501` automatically.

> **Note:** The desktop icon must be created **after** cloning the repo. If you move the `HY-TUTOR` folder to a new location, re-run `bash make_desktop.sh` to update the icon's paths.

### 4.2 Launch via Terminal / Command Prompt

#### Linux

```bash
cd /path/to/HY-TUTOR
bash launch_engine.sh
```

#### Windows

```powershell
cd C:\path\to\HY-TUTOR
.\launch_engine.bat
```

### 4.3 Accessing the App

- Your browser should open **http://localhost:8501** automatically.
- If it doesn't, manually type `http://localhost:8501` into your browser's address bar.
- Keep the terminal window **open** while using HY-TUTOR — closing it will shut down the app.

---

## 5. First-Run Setup: API Key Configuration

The first time you launch HY-TUTOR (and no API key is detected), the **First-Run Wizard** will greet you:

1. **Get a free API key:**
   - Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Sign in with your Google account
   - Click **"Get API Key"** → **"Create API Key"**
   - Copy the key (it starts with `AIza...`)

2. **Paste the key into the wizard:**
   - The wizard shows a text input field
   - Paste your key
   - Click **"Save API Key"**

3. **Validation:**
   - The app validates the key format automatically
   - On success, you'll be redirected to the main dashboard

> **Troubleshooting:** If the wizard doesn't appear, manually add your key to `config/.env`:
> ```
> GEMINI_API_KEY=AIza...
> ```

---

## 6. Step-by-Step Usage Workflow

### Phase A — Setting Up a Subject

#### Step 1: Select a Subject

Use the **sidebar** on the left of the screen to select your subject:

- **Physics**
- **Chemistry**
- **Mathematics**
- **Biology**

Each subject has its own isolated workspace — progress, uploads, and vector databases are completely separate.

---

#### Step 2: Upload the 4 Syllabus Source Files

After selecting a subject, you'll see the **"System Configuration Mode"** screen with four file upload slots. Each slot accepts multiple `.md` or `.txt` files (they are automatically concatenated into one canonical file).

| Slot | Label | What to Upload | Why It's Needed |
|------|-------|----------------|-----------------|
| 1 | **CBSE Syllabus Guidelines** | The official CBSE syllabus document (`.md`/`.txt`) | Defines scope, boundaries, and mandatory theoretical targets |
| 2 | **NCERT TOC** | **Table of Contents** of the NCERT textbook (`.md`/`.txt`) | Provides the standard academic foundation structure |
| 3 | **Reference Book TOC** | **Table of Contents** of a competitive reference book (e.g., Vinay Kumar for Mathematics, HC Verma for Physics) — `.md`/`.txt` | Adds advanced shortcuts, extensions, and competitive depth |
| 4 | **Exemplar / Question Bank TOC** | **Table of Contents** of the NCERT Exemplar OR a competitive question bank (`.md`/`.txt`) | Maps practice problem structure for later integration |

> **💡 Tip:** For slots 2, 3, and 4, you are uploading **Table of Contents** files — not the full textbook content. The full chapter texts will be uploaded later in Phase B.

**How to get these files:**
- Refer to [Section 8 — Preparing Source Files](#8-preparing-source-files-before-you-start) for detailed instructions on acquiring and converting PDFs to Markdown.
- Use free book-sharing platforms like [PDFCoffee](https://pdfcoffee.com/) to find reference books.
- Convert PDF content to `.md` using tools like [marker-pdf](https://github.com/Uncoded-LLC/marker-pdf).

**Procedure:**

1. Click on each upload slot and select your `.md`/`.txt` files.
2. You can upload **multiple files** per slot — they will be merged.
3. Click **"🔨 Map & Build Master Domain Syllabus"**.
4. Wait for Command 0 to process (this may take 1–2 minutes).
5. On success, you'll be taken to the Syllabus Review screen.

---

#### Step 3: Review & Edit the Syllabus (Optional)

The generated syllabus appears as a list of expandable chapter cards. Each card shows:

- **Cross-Grade Prerequisites** — Topics from earlier grades you should know
- **Atomic Chunks** — The breakdown of the chapter into study milestones
- **Competitive Focus** — JEE/NEET-specific emphasis markers
- **Execution Profile** — Processing flags for the pipeline

**To make changes:** Use the **"Architect Modification Chat"** at the bottom:

1. Type your request (e.g., *"Add more detail to the organic mechanisms chunk"* or *"Reorder chapters to start with Thermodynamics"*).
2. Click **"➤ Submit"**.
3. The LLM-powered editor will process your request and regenerate the syllabus.
4. Review the updated structure.

---

#### Step 4: Confirm the Syllabus

Once you're satisfied with the syllabus:

1. Click the **"✅ Confirm Syllabus & Proceed to Study Dashboard"** button.
2. You'll be taken to the **Study Session Planner**.

---

### Phase B — Preparing a Chapter for Study

#### Step 5: Select a Chapter

In the **Study Session Planner**:

1. A dropdown lists all chapters from your confirmed syllabus.
2. Select the chapter you want to study.
3. Optionally, click **"🔍 Review/Edit Master Syllabus"** to go back and make changes.

---

#### Step 6: Run Pre-Flight Route Triage

Click **"🚀 Run Pre-Flight Route Triage"**. This runs the **Edge Router** (Command 0.5) which analyzes the chapter and determines one of three states:

| State | Meaning | What You'll See |
|-------|---------|-----------------|
| **STATE_A** | Clear path — no prerequisites required | File upload slots for chapter content |
| **STATE_B** | Prerequisite lockout — a prior topic needs to be studied first | A warning with override option |
| **STATE_C** | Weak-area review — revisit previously studied material | File upload slots for chapter content |

---

#### Step 7: Handle Prerequisite Lockout (STATE B)

If you hit **STATE_B**, HY-TUTOR has detected that this chapter depends on a prerequisite topic you haven't marked as completed.

**To override (if you already know the prerequisite):**

1. Read the blocker details shown on screen.
2. Type a brief explanation of your competency in the text area (e.g., *"I studied this in Class 10 and scored 95%"*).
3. Click **"➤ Submit"**.
4. The Edge Router evaluates your response and may allow you to proceed.

**Alternatively**, click **"⬅️ Return to Dashboard"** and select the prerequisite chapter first.

---

#### Step 8: Upload Chapter Content Assets

If you're in **STATE_A** or **STATE_C**, you'll see three upload slots for the selected chapter:

| Slot | Label | What to Upload |
|------|-------|----------------|
| 1 | **Core NCERT Chapter Text** | The **full verbatim text** of the chapter from the NCERT textbook (`.md`/`.txt`) |
| 2 | **Reference Manual Chapter Text** | The **corresponding chapter** from your chosen reference book (`.md`/`.txt`) |
| 3 | **Exemplar / Question Bank** | The **actual problems** from NCERT Exemplar or competitive question bank for this chapter (`.md`/`.txt`) |

> **📌 Note:** Unlike the syllabus setup (where you upload TOCs), here you upload the **full chapter content** — the actual textbook text, reference material, and problems.

**Procedure:**

1. Upload `.md`/`.txt` files into each slot (multiple files per slot supported).
2. Click **"🚀 Upload & Stage Chapter Content"**.
3. The system saves the files and re-checks readiness.
4. Once verified, you'll see a **"🔥 Execute Deep Learning Compilation"** button.

---

#### Step 9: Execute the Compilation Pipeline

Click **"🔥 Execute Deep Learning Compilation"** to start the full processing pipeline.

You'll see the **Pipeline Runner** screen with a DAG (Directed Acyclic Graph) showing each processing stage:

```
Blueprint → Miner → Optimizer → Bridge → Forge → Injector → (handoff to Tutor)
```

**During execution:**

- Each node shows a **status badge** (⏳ Running, ✅ Completed, ❌ Failed).
- You can **re-run any failed node** using the "🔄 Re-run" button.
- The **Recovery Panel** (if shown) lets you retry, skip, or restart failed chunks.

**What each stage does:**

| Stage | Command | What Happens |
|-------|---------|-------------|
| Blueprint | C1 | Plans milestone-aligned atomic chunks for the chapter |
| Miner | C2 | Extracts verbatim NCERT theory with LaTeX formulas |
| Optimizer | C3 | Processes reference book content in 5000-word windows |
| Bridge | C4 | Cognitively links NCERT content with reference material |
| Forge | C5 | Synthesizes a unified LaTeX-rich lesson with ChromaDB indexing |
| Injector | C5.5 | Extracts exemplar problems and indexes them in ChromaDB |
| Tutor | C6 | Socratic dialogue engine (handoff to UI) |

**Estimated time:** 5–15 minutes depending on chapter length and API response times.

---

### Phase C — The Learning Dashboard

#### Step 10: Split-Screen Learning

Once the pipeline completes, you'll enter the **Learning Dashboard** with a split-screen layout:

```
┌──────────────────────────┬──────────────────────────┐
│   📖 Lesson Viewer (55%) │   💬 Socratic Chat (45%) │
│                          │                          │
│  • LaTeX-rich markdown   │  • Ask questions about   │
│  • Formatted lesson      │    the current chunk     │
│  • Equations & formulas  │  • Get Socratic guidance │
│  • Chunk-based content   │  • Conversational tutor  │
│                          │                          │
├──────────────────────────┴──────────────────────────┤
│  🔍 Similar Problems (ChromaDB semantic search)     │
│     [Easy] [Medium] [Hard] — filtered by difficulty │
└─────────────────────────────────────────────────────┘
```

**Left pane (Lesson Viewer):**
- Displays the compiled lesson for the current chunk
- Supports LaTeX math rendering (inline and display equations)
- Scroll through the structured lesson content

**Right pane (Socratic Tutor Chat):**
- Type questions about the current chunk
- The AI responds in a Socratic style — guiding you to find answers
- Chat history is saved per-chunk for the session

---

#### Step 11: Chunk Navigation

Each chapter is split into **atomic chunks** — manageable study units with distinct milestones.

Use the navigation bar at the top of the learning dashboard:

| Button | Action |
|--------|--------|
| **⏪ Previous Chunk** | Go back to the previous chunk (rewinds state and re-compiles) |
| **🔄 Reset Chapter Progress** | Start the chapter from Chunk 0 |
| **🚪 Exit to Dashboard** | Return to the Study Session Planner |

> **💡 Tip:** You can study a chapter across multiple sessions. HY-TUTOR remembers which chunk you were on and resumes from there.

---

#### Step 12: Similar Problems

Below the split-screen view, the **Similar Problems** panel shows practice problems related to your current lesson chunk:

- **Powered by ChromaDB** — semantic vector search finds the most relevant problems
- **Difficulty filters:** Easy, Medium, Hard
- **Source:** Problems come from the NCERT Exemplar / Question Bank you uploaded

> **Note:** If no problems are found, ensure you ran the full pipeline (including Stage 5.5 — Injector) for this chapter. The vector index is built during the final processing stage.

---

#### Step 13: Recovery Panel

If any chunk processing failed during compilation, the **Recovery Panel** appears at the bottom of the learning dashboard with options:

| Option | Action |
|--------|--------|
| **🔄 Retry** | Re-attempt processing the failed chunk |
| **⏭ Skip** | Skip the failed chunk and move to the next one |
| **🔁 Restart** | Clear all chunk state and start processing from the beginning |
| **🗑 Clear** | Remove all error logs and reset the chunk's status |

---

### Phase D — Advanced Features

#### Step 14: Settings

Click the ⚙️ gear icon in the top-right corner of any screen to open **Settings**. It has three tabs:

| Tab | Features |
|-----|----------|
| **🎨 Appearance** | Change theme (light/dark), accent color, background color |
| **🔄 Update** | Check for new versions, one-click "Update & Install Now" |
| **ℹ️ About** | Project info, version, ChromaDB management |

> **Known Issue:** The preset color swatches (e.g., "Forest Green") don't currently apply. Use the custom color picker instead.

#### Step 15: Switching Subjects

To switch to a different subject:

1. Open the sidebar on the left.
2. Use the **subject selector** dropdown.
3. Select your new subject.

Each subject has its own:
- Syllabus and chapter data
- Uploaded files
- ChromaDB vector store
- UI session state and progress tracking

---

## 7. Understanding the Pipeline Stages

The entire pipeline is a **Directed Acyclic Graph (DAG)** that processes your raw files into polished lessons. Here's a quick overview:

```
                    ┌──────────┐
                    │ Command 0│  Syllabus Builder (4-source TOC synthesis)
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │Command 0.1│  Syllabus Editor (LLM-powered modifications)
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │Command 0.5│  Edge Router (3-state triage: A/B/C)
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │Command 1 │  Blueprint Generator (chunk planning)
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
         ┌────▼─────┐ ┌──▼─────┐ ┌──▼────────┐
         │Command 2 │ │Command 3│ │ Command 5.5│
         │  Miner   │ │Optimizer│ │  Injector  │
         └────┬─────┘ └──┬─────┘ └──────┬─────┘
              │          │              │
              └─────┬────┘              │
               ┌────▼─────┐            │
               │Command 4 │            │
               │  Bridge  │            │
               └────┬─────┘            │
                    │                  │
               ┌────▼─────┐            │
               │Command 5 │◄───────────┘
               │  Forge   │
               └────┬─────┘
                    │
               ┌────▼─────┐
               │Command 6 │  Socratic Tutor (handoff to UI)
               └────┬─────┘
                    │
               ┌────▼─────┐
               │Command 7 │  Ledger (session scoring & tracking)
               └──────────┘
```

| Command | File | Purpose |
|---------|------|---------|
| **C0** | `command_0_syllabus.py` | Synthesizes 4 uploaded TOCs into a domain-adaptive master syllabus |
| **C0.1** | `command_0_1_editor.py` | LLM-powered syllabus editing with robust JSON extraction |
| **C0.5** | `command_0_5_router.py` | 3-state edge router: A (clear), B (prereq block), C (weak-area review) |
| **C1** | `command_1_blueprint.py` | Plans atomic chunks aligned to chapter milestones |
| **C2** | `command_2_miner.py` | Extracts verbatim NCERT theory + LaTeX formulas |
| **C3** | `command_3_optimizer.py` | Processes reference manual content in 5000-word windows |
| **C4** | `command_4_bridge.py` | Cognitively links NCERT ↔ Reference material |
| **C5** | `command_5_forge.py` | Synthesizes final unified lesson markdown + ChromaDB index |
| **C5.5** | `command_5_5_injector.py` | Extracts exemplar problems and indexes them in ChromaDB |
| **C6** | `command_6_tutor.py` | Socratic dialogue engine with pacing shields |
| **C7** | `command_7_ledger.py` | Session scoring, mastery tracking, chapter transitions |
| **C8** | `command_8_compile_notes.py` | (Phase 2) Compiles per-chapter notes |

---

## 8. Preparing Source Files (Before You Start)

HY-TUTOR works with `.md` (Markdown) and `.txt` (plain text) files. Since most textbooks are in PDF format, you'll need to convert them first.

### 8.1 Acquiring Reference Books

1. Choose your reference books (e.g., Vinay Kumar for Mathematics, HC Verma for Physics, OP Tandon for Chemistry).
2. Download PDFs from **trusted free sources** such as:
   - [PDFCoffee](https://pdfcoffee.com/)
   - Internet Archive
   - Other open textbook repositories

### 8.2 Cropping to a Chapter

Reference books are often 500+ pages. For faster processing, **crop the PDF to the specific chapter** you want to study:

- Use tools like **Adobe Acrobat**, **PDFsam**, or online PDF splitters
- Extract only the pages for the chapter you're working on (e.g., "Matrices" from a multi-volume Mathematics text)

### 8.3 Converting to Markdown

Convert your cropped chapter PDF to Markdown using OCR tools:

- **[marker-pdf](https://github.com/Uncoded-LLC/marker-pdf)** — Highly recommended (can run via Google Colab for free)
- **Online PDF-to-Markdown converters**
- **Pandoc** — `pandoc input.pdf -o output.md` (basic extraction)

> **Future automation:** The project roadmap includes an integrated OCR engine so this manual step will eventually be eliminated.

Once converted, you should have:
- **Table of Contents files** for syllabus setup (Phase A)
- **Full chapter text files** for chapter processing (Phase B)
- **Problem bank files** for exemplar injection

---

## 9. Troubleshooting Common Issues

| Issue | Likely Cause | Solution |
|-------|-------------|----------|
| **"ModuleNotFoundError" on launch** | Dependencies not installed | Re-run `install.sh` (Linux) or `install.ps1` (Windows) |
| **"GEMINI_API_KEY is empty" warning** | API key not configured | Use the First-Run Wizard on first launch, or manually add it to `config/.env` |
| **Streamlit fails to auto-open browser** | Browser detection issue | Manually navigate to `http://localhost:8501` |
| **ChromaDB installation fails on Windows** | Missing C++ build tools | Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) and retry |
| **"No Similar Problems Found"** | Pipeline didn't reach Stage 5.5 | Run the full pipeline for that chapter |
| **Pipeline node times out** | Large chapter / slow API | Re-run the failed node. Check your internet connection. |
| **Syllabus editor crashes on chat** | Non-JSON response from LLM | Rephrase your request. Use specific, structured commands. |
| **Color swatches don't apply** | Known bug (Bug #001) | Use the custom color picker instead of preset swatches |
| **Desktop icon doesn't work** | Repo was moved after `make_desktop.sh` | Delete the old icon, re-run `bash make_desktop.sh` from the new repo location |

---

## 10. Frequently Asked Questions (FAQ)

**Q: Do I need a GPU?**  
A: No. All AI processing runs on Google Gemini's cloud servers. You only need an internet connection.

**Q: Is my data sent to the cloud?**  
A: Only the text content and chat messages are sent to Google Gemini for processing. No other data leaves your machine.

**Q: Can I use multiple subjects?**  
A: Yes! Each subject has its own isolated workspace, syllabus, uploads, and ChromaDB vector store.

**Q: Can I study the same chapter multiple times?**  
A: Yes. Use the **"🔄 Reset Chapter Progress"** button on the learning dashboard to restart from Chunk 0.

**Q: The app says "STATE_B — Prerequisite Lockout". What do I do?**  
A: Either study the prerequisite chapter first (return to dashboard and select it), or provide a competency override explaining your prior knowledge.

**Q: How long does the pipeline take?**  
A: Typically 5–15 minutes per chapter, depending on chapter length and API response times.

**Q: Can I interrupt the pipeline mid-way?**  
A: Yes. The Pipeline Runner shows each stage's status. You can re-run any failed stage individually.

**Q: How do I update HY-TUBE to the latest version?**  
A: Go to **Settings → Update** tab and click **"Update & Install Now"**. This automatically pulls the latest code and reinstalls dependencies.

**Q: What's the difference between uploading TOC vs full content?**  
A: During **syllabus setup (Phase A)**, you upload **Table of Contents** (structure/outline only). During **chapter preparation (Phase B)**, you upload the **full chapter text** (actual content).

---

## License

HY-TUTOR is licensed under the **PolyForm Noncommercial License 1.0.0**.

- ✅ **Free for:** personal study, non-commercial educational use, internal research, open-source contributions
- ❌ **Requires commercial license for:** selling the software, hosting as a paid service, embedding in commercial products

See the [LICENSE](LICENSE) file for full terms.

---

<div align="center">

  *Happy studying! 🚀*

  [← Back to README](README.md) · [Report a Bug](https://github.com/AdityaK181225/HY-TUTOR/issues)

</div>