<div align="center">

<img src="src/assets/gopalan-logo.png" alt="Gopalan AI logo" width="110" />

# Gopalan AI

## Cattle Scoring &amp; Breed Selection

### Score your cattle, pick the right breed, and check its health — from a single photo. 📷✨

Smart, AI-powered livestock evaluation for Indian farmers.
Built to support the **Rashtriya Gokul Mission** 🇮🇳

<br/>

### 🔗 [**Live Website → gopalanai.netlify.app**](https://gopalanai.netlify.app/)

</div>

> [!WARNING]
> ### 🚧 Under maintenance: version 2 in progress
>
> **Version 2** adds a new AI pipeline, an API and a database. They are built and tested, and live in
> this repository ([`ml/`](ml), [`api/`](api), [`supabase/`](supabase)).
> The **live website is still version 1** and doesn't use the new AI yet. A completely
> **new website** will connect everything in the **next version**.
> See [What's new in v2](#-whats-new-in-v2) and the [Roadmap](#%EF%B8%8F-roadmap).

---

## 📖 Overview

**Gopalan AI** is a web platform for **Cattle Scoring &amp; Breed Selection** — helping farmers evaluate
their cattle and buffalo using nothing more than a smartphone photo. By placing a printed **ArUco marker**
next to the animal, the AI can measure it in real-world units, score its **body condition**,
identify its **breed**, and point the farmer to relevant **health guidance** — all in one place.

<div align="center">
<img src="src/assets/animals/cattle.jpg" alt="Cattle" width="45%" />
<img src="src/assets/animals/water-buffalo.jpg" alt="Buffalo" width="45%" />
</div>

---

## ❗ The Problem

Evaluating livestock the traditional way is **slow, manual, and inconsistent**:

- **Human error & bias** — body condition scoring depends on who is looking, so two people give two answers.
- **No standard tool** — farmers in rural areas rarely have access to trained classifiers or vets.
- **Hard to measure** — accurate body measurements normally need physical tools and expertise.
- **Missed health issues** — problems are often caught late, hurting the animal and the farmer's income.

For a national programme like the **Rashtriya Gokul Mission** — which depends on identifying elite
breeding stock and conserving indigenous breeds — inconsistent, subjective data is a real obstacle.

---

## 💡 Our Solution

Turn any smartphone into an objective evaluation tool using **computer vision + an ArUco marker for scale**.

<div align="center">
<img src="src/assets/animals/aruco-marker.jpg" alt="ArUco marker" width="30%" />
&nbsp;&nbsp;
<img src="src/assets/animals/measure-points.jpg" alt="Body measurement points" width="45%" />
</div>

- The **ArUco marker** is a printed black-and-white square of known size. Placed beside the animal, it
  lets the AI convert pixels into real centimetres — so measurements are accurate.
- The AI then **detects the animal**, **measures its body**, and produces a **standardized, objective
  body condition score** plus a **breed identification** — removing human bias.

---

## ⚙️ How It Works

<div align="center">
<img src="src/assets/animals/upload-interface.jpg" alt="Upload interface" width="70%" />
</div>

| Step | Action |
|:---:|---|
| **1** | 📷 **Take a photo** — a clear, side-on photo of your cow or buffalo in good light. |
| **2** | 🎯 **Add the ArUco marker** — place the printed marker beside the animal for real-world scale. |
| **3** | ⚡ **Upload & analyze** — the AI detects the animal and measures its body. |
| **4** | 📊 **Get your results** — breed, body measurements, and a clear body condition score. |

<div align="center">
<img src="src/assets/animals/score.png" alt="Scoring result" width="60%" />
</div>

---

## 🆕 What's new in v2

Version 2 rebuilds the "brain" behind the website. The goal is a **semi-automatic** scoring system: the AI does
the measuring and scoring, and a human reviewer checks it. This replaces today's fully manual body
condition scoring in programmes like the Rashtriya Gokul Mission.

| Part | What it does | Docs |
|---|---|---|
| 🧠 **ML** | Finds the cow or buffalo in a photo, outlines it and **places the body points automatically** (no more clicking 12 points by hand). Reads the ArUco marker for centimetres. Computes a **BCS v2 score (beta)**. | [`ml/README.md`](ml/README.md) |
| 🐄 **Breed model** | Recognises **16 Indian breeds** (8 cattle, 8 buffalo), or answers "unsure" with its top 3 guesses | [Model on Hugging Face](https://huggingface.co/thearyansingh/cattle-breed-classifier) |
| ⚙️ **API** | FastAPI service: analyse photos, recalculate when the user drags a point, save animals and history, reviewer queue, training-data export | [`api/README.md`](api/README.md) |
| 🗄️ **Database** | Supabase: accounts, animals, analyses, reviews and private photo storage, with security rules enforced by the database | [`supabase/README.md`](supabase/README.md) |
| ✅ **CI** | Every change is checked automatically: website lint and build, plus the ML and API test suites | [Workflow](.github/workflows/ci.yml) |

**Key results**

| | |
|---|---|
| Animal found in test photos (cattle and buffalo) | **48 / 48** |
| Head/tail direction correct on side-view photos | **32 / 32** |
| Breed: exact / correct breed in top 3 (508 unseen photos) | **72% / 90%** (cattle 83%, buffalo 62%) |
| Breed with "unsure" option | answers 79% of photos, **81.5% correct** |
| Old analyzer's BCS bugs fixed | **8 / 8** |
| Analysis time (CPU) / re-score after dragging a point | ~2.5 s / ~2 ms |

**Privacy by design:** trying an analysis needs no account. Photos are stored **only with the user's
consent**, with GPS and other hidden photo data removed. Users can only ever see their own data.

**Honest limits:** the BCS score is **beta**. It's calibrated on photo measurements, not yet on
expert-scored animals. Reviewer corrections collected by the system are meant to train a learned BCS model
later. The breed model was trained on web photos, and the buffalo folders of the source data are noisy.

---

## ✨ Features

- 🧠 **AI Body Condition Scoring** — consistent scores from photos (v2: automatic body points, 1–5 in 0.25 steps, beta).
- 📏 **Real-world Measurement** — ArUco-marker sizing: body length, depth, leg length, rump and hip width.
- 🐄 **Breed Guide** — detailed profiles of 8 cattle and 8 buffalo indigenous breeds.
- 🩺 **Health & Disease Support** — symptoms, causes, treatment, prevention, and emergency steps.
- 📸 **Photography Guide** — how to capture analysis-ready photos with an ArUco marker.
- ❓ **Help & FAQ** — plain-language answers for farmers.
- 📱 **Mobile-first & fast** — designed for real field conditions and low-end phones.

---

## 🌍 Impact

- **Standardization** — removes observer bias so every animal is scored the same way.
- **Accessibility** — puts expert-level evaluation in any farmer's hand, anywhere.
- **Better breeding** — reliable data helps identify strong breeding animals, supporting the
  Rashtriya Gokul Mission's genetic-improvement goals.
- **Healthier herds** — early health guidance means fewer preventable losses and stronger livelihoods.

---

## 🐮 Breeds Covered

**Cattle:** Gir · Sahiwal · Ongole · Hallikar · Rathi · Red Sindhi · Kankrej · Malnad Gidda
**Buffalo:** Murrah · Nili-Ravi · Surti · Jafarabadi · Mehsana · Bhadawari · Toda · Nagpuri

<div align="center">
<img src="src/assets/animals/gir.jpg" alt="Gir" width="30%" />
<img src="src/assets/animals/sahiwal.jpg" alt="Sahiwal" width="30%" />
<img src="src/assets/animals/murrah-buffalo.jpg" alt="Murrah" width="30%" />
</div>

---

## 🛠️ Tech Stack

**Website (v1, live)**
- **[Vite](https://vitejs.dev/)** + **[React 18](https://react.dev/)** + **TypeScript**
- **[Tailwind CSS](https://tailwindcss.com/)** with **[shadcn/ui](https://ui.shadcn.com/)** components
- **[React Router](https://reactrouter.com/)** with route-level code splitting
- Scroll-reveal & count-up animations, fully responsive
- Analyze page embeds the original **Hugging Face Gradio** analyzer (to be replaced by the v2 API)

**AI and backend (v2)**
- **Python 3.12**, **PyTorch / torchvision** (Mask R-CNN), **OpenCV** (ArUco), **ONNX Runtime**
- Breed model: **ConvNeXt-Tiny** fine-tuned with **timm** on Kaggle GPUs
- **FastAPI** + **Supabase** (Postgres, Auth, Storage) with row-level security
- **GitHub Actions** CI; models published on **Hugging Face**

---

## 🗺️ Pages

| Route | Page |
|---|---|
| `/` | Home — problem, solution, how it works, features |
| `/analyze` | Upload a photo and run the AI analysis |
| `/animal-guide` | Breed encyclopedia (clickable breed cards) |
| `/breeds/:slug` | Individual breed detail pages |
| `/medical-support` | Health checker — pick animal, find condition, get guidance |
| `/guide` | Step-by-step photography guide |
| `/help` | FAQ & help |
| `/about` | Mission, vision, values, and feedback form |

---

## 🚀 Getting Started

```bash
# Install dependencies
npm install

# Start the development server
npm run dev

# Build for production
npm run build

# Preview the production build
npm run preview
```

**Run the v2 API locally** (Python 3.12):

```bash
cd ml && python -m venv .venv && .venv\Scripts\activate   # macOS/Linux: source .venv/bin/activate
pip install -r ../api/requirements.txt
cd ../api && uvicorn app.main:app --port 8000             # then open http://127.0.0.1:8000/docs
```

Full setup (models, Supabase, settings) is in [`api/README.md`](api/README.md).

### ✅ Automatic checks

Every pull request and every push to `main` runs the [CI workflow](.github/workflows/ci.yml) on GitHub Actions:

| Job | What it checks |
|---|---|
| Website | `npm ci`, `npm run lint`, `npm run build` |
| ML | Python 3.12, installs `ml/requirements-train.txt`, runs the `ml/` test suite |
| API | Python 3.12, installs `api/requirements.txt`, runs the `api/` test suite (stand-in models, fake Supabase) |

A green ✓ on the pull request means all checks passed. The ML tools are described in [`ml/README.md`](ml/README.md), the API in [`api/README.md`](api/README.md).

---

## 📁 Project Structure

```
src/                 # Website (v1)
├── assets/          # Images and videos (breed photos, hero videos, logo)
│   └── animals/     # Cattle & buffalo photos, ArUco marker, measurement guides
├── components/      # Shared sections & UI (Navbar, Hero, Footer, HeroDecor, ...)
│   └── ui/          # Reusable primitives (button, card, tabs, ...)
├── data/            # Shared breed data
├── hooks/           # Shared React hooks
├── lib/             # Utilities
└── pages/           # Route pages (Home, Analyze, Animal Guide, Medical Support, ...)

ml/                  # v2 AI: detection, body points, measurements, BCS, breed training (Kaggle notebook)
api/                 # v2 FastAPI service (analysis, saving, review) + Dockerfile + scripts
supabase/            # v2 database migrations and security self-check
.github/workflows/   # CI: website, ML and API checks
```

---

## 🌐 Deployment

🚀 **Live at [gopalanai.netlify.app](https://gopalanai.netlify.app/)** — deployed on **Netlify**.

The project is set up for continuous deployment: it's connected to this GitHub repo, so **every push
to `main` triggers an automatic rebuild and redeploy** — no manual steps.

**Netlify configuration**

| Setting | Value |
|---|---|
| Build command | `npm run build` |
| Publish directory | `dist` |
| SPA redirects | handled by `netlify.toml` (all routes → `index.html`) |

**Deploy your own copy**

1. Fork/clone this repo.
2. On [Netlify](https://netlify.com), choose **Add new site → Import an existing project** and pick the repo.
3. Netlify auto-detects the settings above — click **Deploy**.

Any static host that serves `dist/` with an SPA fallback (Vercel, GitHub Pages, Cloudflare Pages, etc.) also works.

The **v2 API** isn't hosted online yet. It runs locally for now, and deployment to Google Cloud Run is
planned ([#24](https://github.com/AryanSinghh07/Cattle-Scoring-and-Breed-Selection/issues/24)).

---

## 🗺️ Roadmap

| Version | Status | What |
|---|---|---|
| **v1** | ✅ Live | Website: breed guide, health support, photo guide, embedded analyzer |
| **v2** | ✅ Done | AI pipeline (automatic body points, BCS v2 beta, 16-breed model), API, Supabase database with security rules, reviewer workflow, CI |
| **v3** | 🚧 Next | **New website**: redesigned, mobile-first, Hindi + English, camera flow with draggable points, results, my animals and history, reviewer screen. Connected to the v2 API. API hosted online. |
| Later | 📋 Planned | Learned BCS model trained on reviewer-confirmed scores; more breeds; offline support |

---

## 📄 License

Released under the **[MIT License](LICENSE)** — © 2026 Aryan Singh.

---

<div align="center">

**Made for the farmers of India** 🇮🇳

</div>
