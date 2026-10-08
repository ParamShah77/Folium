# Folium — running the demo

Folium is a web app that judges an investment decision against your whole
portfolio. It names the behavioural bias behind the moment, shows both
futures in rupees over your own horizon, and explains it in English or Hindi.
For how everything works see `FOLIUM_MASTER.md`; for first-time setup, `SETUP.md`. The FastAPI
backend (`backend/`) runs the research models from `src/` behind real
authentication, and the React frontend lives in `frontend/`.

## What must be running

| Service | How it runs on this laptop | Port |
|---|---|---|
| PostgreSQL 18 | Windows service `postgresql-x64-18`, starts automatically | 5432 |
| Memurai (Redis) | Windows service `Memurai`, starts automatically | 6379 |
| Backend API | started by you (below) | 8000 |
| Frontend | started by you (below) | 3000 |

No Docker is needed.

## Start the app

Open two terminals in the project folder.

**Terminal 1, backend:**

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m uvicorn backend.main:app --port 8000 --reload
```

**Terminal 2, frontend:**

```powershell
npm --prefix frontend run dev
```

Then open **http://localhost:3000**. If another app (e.g. ArchonAI) already uses
port 3000, stop it first, or run the frontend with `$env:PORT=3001` and use
that port.

After pulling new code, apply database changes once:

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m alembic -c backend\db\migrations\alembic.ini upgrade head
```

## Demo accounts

These are demo-only credentials, created by `scripts/seed_demo.py`. Both
accounts have a complete portfolio priced live at seed time.

| Account | Email | Password | Portfolio |
|---|---|---|---|
| Ananya (34, salaried) | `ananya.iyer@example.com` | `Folium-Demo-Walkthrough-2026` | 5 stocks, 1 mutual fund, gold, FDs, savings, a car loan, ₹25,000 monthly SIP · 6 seeded analyses |
| Rohan (52, near retirement) | `rohan.mehta@example.com` | `Folium-Demo-Walkthrough-2026` | 2 stocks, gold, FDs, a flat with a home loan, rent received, ₹40,000 monthly SIP, education fees ending 2029, 10-year horizon · 2 analyses |

Logging in as Rohan shows none of Ananya's data, and the reverse is also true.
That is per-account isolation in the database.

The older accounts `ananya.demo@example.com` and `rohan.demo@example.com` are
from before portfolios existed. They still work, but use the two above. To
remove one, log in and use Settings, Your data, Delete my account: it is
anonymised after the 30-day grace period (the audit record stays, unlinked).

To create the demo accounts on a fresh database:

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py scripts\seed_demo.py
```

After changing a model or the explanation text, regenerate their analyses:

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py scripts\seed_demo.py --refresh
```

## Signing up live during the demo

No email service is configured, so sign-up emails go to a **development inbox**
instead of a real mailbox. After registering, the "Check your email" page has
an **Open development inbox** button with the verification link. It exists only
in local development; once `RESEND_API_KEY` is set, real emails are sent and
the inbox disappears.

## Suggested walkthrough (about 6 minutes)

1. **Home page:** "Create your free account", how it works, the four biases,
   and **Security and data privacy** ("Your data stays yours"). Open the
   **Privacy policy** from the footer.
2. **Sign up live:** account, then investor profile (income, EMIs, rent,
   education fees, the five-question risk quiz). Then open the development
   inbox, verify, and log in. Leave **Keep me signed in** unticked: the session
   ends when the browser closes.
3. **Log in as Ananya. Dashboard:** bias pattern, wealth at stake, and a
   portfolio snapshot.
4. **Portfolio:** net worth, liquid assets, monthly surplus, loans, and where
   the money is. Add a stock (live price check) or search a mutual fund by name.
5. **New analysis:** pick a holding (e.g. HDFCBANK), choose **Sell**, and add a
   reason. The side panel shows its share of the portfolio.
6. **Live analysis:** five plain steps complete in real time.
7. **Result:** the recommendation; the position against the whole portfolio;
   both futures over the investor's own horizon, after tax; the pattern found;
   the six-part explanation, which can be switched to **हिंदी**; a
   **downloadable report** (HTML, or PDF in English); what weighed most; what
   helps; and **Verify this record**, which proves the analysis still matches
   the tamper-evident entry saved when it ran.
8. **Settings, then Security:** turn on two-step verification with an
   authenticator app.
9. **Log out:** you're back on the home page. **Log in as Rohan:** none of
   Ananya's data is visible.

## Checks

```powershell
D:\FolioEnv\venv313\Scripts\python.exe scripts\verify_ml_env.py
D:\FolioEnv\venv313\Scripts\python.exe scripts\with_env.py -m pytest backend\tests -q
D:\FolioEnv\venv313\Scripts\python.exe -m pytest tests -q
npm --prefix frontend run build
npm --prefix frontend test
```

## Known model behaviour (what to say if asked)

- **The pattern read now looks at the action.** Bias model v4 sees sell, hold
  or buy more, the market (real NIFTY and India VIX history, 2008 to today) and
  the portfolio. The same holding up 35% in a calm market reads as the
  disposition effect if you sell it, and as rational if you hold or add.
  Full evaluation: `results/reports/BIAS_MODEL_V4.md`.
- **What each pattern needs** (the agreed definitions): herd behaviour needs a
  fearful market or a strong rally; panic loss aversion needs a falling,
  fearful market; the disposition effect needs a calm one. So in a calm market
  only disposition, loss aversion on a deep loser (25%+), or rational are
  possible.
- **Confidence is calibrated.** High is right about 99% of the time, Medium
  about two times in three, Low is close to a coin toss between two patterns
  (the bars show which two).
- **"What weighed most" explains the pattern shown**, with teal for factors that
  pointed toward it and grey for those that pointed away.
- **Gold, property and loans reach the bias model but carry little weight**;
  loans and rent matter mainly through the monthly surplus. They also feed net
  worth and the simulation's share-versus-safe mix.
- **If asked "why not just use the rules?"**: the definitions alone get within
  about a point of the model's accuracy. The model adds calibrated confidence
  and recognises sound reasons (rebalancing, a near goal, cutting a loss) that
  a rule would call bias.
- **Projections run to the investor's own horizon**, 1 to 30 years (Ananya 22,
  Rohan 10). Futures are built from real NIFTY and gold history since 2007;
  typical growth is set to stated long-run rates (shares 11%, gold 9%, FDs
  6.75%). Everything is shown **after tax**: selling pays real capital-gains
  tax and charges, and the money goes into the investor's own FDs, savings and
  gold. Full evaluation: `results/reports/SIMULATOR_V2.md`.
- **Each stock is measured.** At submission the app measures how much the
  stock moves with NIFTY and how jumpy it is on its own over 10 years, so HDFC
  Bank (steady) and Wipro (jumpy, low market link) get different answers. A
  diversified fund usually favours holding more strongly than a single stock.
- **If asked "why does holding not always win?"**: over short horizons, or for
  a jumpy single stock against a portfolio heavy in gold and FDs, the two
  futures are genuinely close. The recommendation then treats it as a toss-up
  and leans on the bias reading.
- **Cause and effect is checked against the truth.** The training data was
  made by written rules, so the true effect of every factor is known; the
  app's estimates (from the data alone) recover it to within about half a
  percentage point, and "more gold" (which by construction does nothing) comes
  out at zero. The card speaks to the investor's own action and situation
  ("When holding a loss in a falling market, about 58% of investors sell") and
  offers the one habit that helps most. Full write-up:
  `results/reports/CAUSAL_V4.md`.
- **Every analysis is sealed in a tamper-evident record.** "Verify this record"
  on a result checks that the investor's record chain is intact and that the
  analysis still matches what was recorded; editing either in the database is
  caught (tests: `backend/tests/test_audit_chain_db.py`). Demo chains started
  in the earlier placeholder format and still verify.
- **Download my data / Delete my account** (Settings, Your data). Deleting
  signs out at once; logging in within 30 days offers "Keep my account";
  after that the account is anonymised (the secure record stays, unlinked).
- **The comment is read.** "In your own words" quotes back what was written:
  feelings (fear, following others, waiting to get back to even, locking in a
  gain) are shown only; a stated need for the money ("college fees in March")
  changes the pattern reading. "Both sides, in numbers" sets out the case for
  holding and for selling; it never changes the recommendation.
- **AI help is off unless the investor turns it on** and the server has
  `AI_HELP=true` plus a `GEMINI_API_KEY`. Without it, simple rules read the
  comment and the two cases are written from the numbers.
- **Gold is valued at the international price**, before Indian import duty and
  GST, so shop prices are higher. The app says so.
