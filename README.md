# Tax & Group News Brief — automatic Telegram digest, twice a day

This is a small robot that:
1. Reads Google News (and any RSS feeds you add) for your list of topics.
2. Removes duplicate stories.
3. Summarises what's new using free AI.
4. Sends it to you on Telegram at ~9:00 AM and ~9:00 PM every day.
5. Runs entirely on GitHub's free servers — nothing runs on your own laptop or phone, and it costs ₹0/month.

No prior coding experience needed to set this up. Just follow the steps below in order. It should take about 30–45 minutes the first time.

---

## Part A — Things you need to create (all free, no credit card)

You will create **3 accounts/keys** in total. Do these first, and keep the three values somewhere safe (a Notes app or a text file) — you'll paste them into GitHub in Part C.

### A1. A GitHub account (to host and run the robot)
1. Go to https://github.com and click **Sign up**. Use your personal email (not your Tata email, so you always control it).
2. Verify your email when GitHub asks.

### A2. A Telegram bot (this is how the news reaches your phone)
1. Install Telegram on your phone if you don't have it, and open it.
2. Search for the user **@BotFather** (this is Telegram's official bot-creation bot — it has a blue checkmark).
3. Send it the message: `/newbot`
4. It will ask for a name (anything, e.g. `Bhushan Tax Brief`) and a username (must end in `bot`, e.g. `bhushan_tax_brief_bot`).
5. BotFather will reply with a message containing a long code that looks like `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`. **This is your `TELEGRAM_TOKEN`.** Copy it and save it.
6. Now search for your own new bot by the username you just gave it, open a chat with it, and send it any message, e.g. `hi`. (This step is required — a bot cannot message you until you've messaged it first.)
7. Open this link in your browser, replacing `<TOKEN>` with the code from step 5:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
8. You'll see some text appear with `"chat":{"id":123456789,...`. That number is **your `TELEGRAM_CHAT_ID`.** Copy it and save it.

### A3. A free Gemini API key (this is the "AI" that writes the summaries)
1. Go to https://aistudio.google.com/apikey
2. Sign in with any Google account.
3. Click **Create API key**. No credit card is asked for on the free tier.
4. Copy the long string it gives you. **This is your `GEMINI_API_KEY`.** Save it.

You now have all three: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`.

---

## Part B — Upload this project to GitHub

1. On https://github.com, click the **+** icon (top right) → **New repository**.
2. Name it e.g. `tax-brief`. Keep it **Public** (this keeps your GitHub Actions minutes fully free and unlimited; nothing sensitive is stored in this repo — see the note at the bottom).
3. Click **Create repository**. Leave the resulting page open.
4. On the new repo's page, click **uploading an existing file** (a blue link in the middle of the page).
5. Drag and drop **the entire contents** of the folder you downloaded from this chat (all files and folders: `.github`, `brief`, `feeds.yaml`, `requirements.txt`, `state.json`, `README.md`, `.gitignore`) into the browser window.
   - Make sure the `.github` folder itself is uploaded (some drag-and-drop tools hide folders starting with a dot — if it doesn't appear, use **git** instead, or a tool like GitHub Desktop, to push the folder).
6. Scroll down, click **Commit changes**.

---

## Part C — Give the robot your 3 secret codes

Secrets are stored encrypted by GitHub and are never shown in logs.

1. In your new repo, click **Settings** (top menu of the repo, not your account settings).
2. In the left sidebar: **Secrets and variables** → **Actions**.
3. Click **New repository secret** three times, once for each of these:
   - Name: `TELEGRAM_TOKEN` → Value: (paste the token from A2.5)
   - Name: `TELEGRAM_CHAT_ID` → Value: (paste the number from A2.8)
   - Name: `GEMINI_API_KEY` → Value: (paste the key from A3.4)
4. Each time, click **Add secret**.

---

## Part D — Turn it on and test it

1. In your repo, click the **Actions** tab at the top.
2. If GitHub shows a banner asking to enable workflows, click **I understand my workflows, go ahead and enable them**.
3. On the left, click **tax-news-brief**.
4. Click the **Run workflow** button (top right, small dropdown) → **Run workflow** (green button).
5. Wait about 30–60 seconds, refresh the page. You'll see a run appear with a yellow dot (running) then a green tick (success) or red cross (failed).
6. Check your Telegram — you should get a message from your bot within a minute of the green tick.
7. If it's a red cross, click into the run, click the **brief** job, and read the red-highlighted line — it will usually say exactly what's wrong (most common: a secret was pasted with an extra space, or a typo in `feeds.yaml`).

That's it — it will now run automatically every day at approximately **9:00 AM and 9:00 PM IST**, with no further action needed from you.

---

## Part E — Customising your topics (the only file you'll ever need to touch again)

Open **`feeds.yaml`** in your repo (click on it, then the pencil ✏️ icon to edit, then **Commit changes** when done).

- Each `- name:` block is one topic — it becomes one section of your Telegram message.
- Each line under `queries:` is one search phrase, in plain Google-search style. Use quotes for exact phrases.
- `priority: 1` = always shown in full. `priority: 2` = trimmed to top 5 if the day is very busy.
- To add a topic: copy-paste an existing block and change the name/queries.
- To remove a topic: delete its block.
- No coding needed — this file is just structured text.

Every time you save a change here, the *next* scheduled run (or a manual **Run workflow**) will pick it up automatically.

---

## How the timing actually works (so gaps never happen)

The robot remembers, in a file called `state.json`, the exact time of its last successful run. Each run only fetches news published *after* that time — not a fixed "last 12 hours". So:
- If a run is a few minutes late (GitHub sometimes delays cron jobs slightly), you still get every story, none skipped.
- If a run fails entirely, the next run automatically covers the wider gap.

You never need to touch `state.json` — the robot updates it by itself after every successful send.

---

## Cost & limits — why this stays free

- **GitHub Actions**: free and unlimited on public repos. Each run takes about 30–60 seconds, twice a day.
- **Telegram Bot API**: completely free, no message limits for this volume.
- **Gemini API free tier**: <cite index="6-1">Google's Gemini free tier offers roughly 1,500 requests/day, well above the 10–16 calls/day this robot makes</cite> (one call per topic, twice a day). No credit card needed, no expiry.

**One thing to know:** on the Gemini free tier, <cite index="6-1">Google states it may use free-tier requests to help improve its models</cite>. That's fine for public news headlines (which is all this sends), but never repurpose this same API key or repo to summarise confidential Tata documents — keep those on a paid/enterprise key instead.

---

## If something breaks later

- The robot is set up to message you on Telegram itself if a run fails ("⚠️ Tax brief run failed: ..."), so you'll know without checking GitHub.
- To see run history any time: repo → **Actions** tab → **tax-news-brief**.
- To pause it temporarily: **Actions** tab → **tax-news-brief** → **···** menu (top right) → **Disable workflow**.
