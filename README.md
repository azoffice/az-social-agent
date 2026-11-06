# AZ Social Agent

Posts for AZ Office Automation to **Telegram, Facebook Page and Instagram**
automatically, 4 times a week, at ₹0/month.

Runs on GitHub Actions. No server, no hosting bill, no subscription.

**What it does on each run:** picks the next unposted row from your content
bank → writes an SEO/GEO caption with Gemini (Bangalore areas, Q&A opening,
hashtags, your phone numbers) → posts the image and caption to all three
platforms → marks the row as done so it never repeats.

---

## Setup — do these in order

Total time: about 2 hours, plus waiting for Meta verification.
Do Part 1 and 2 today. Telegram alone will already be live.

---

### PART 0 — Create the repo (10 min)

1. Go to github.com, sign in (create a free account if needed).
2. **New repository** → name it `az-social-agent` → **Private** → Create.
3. Upload every file from this folder, keeping the folder structure:
   - `post.py`
   - `content.csv`
   - `posted.json`
   - `.gitignore`
   - `.github/workflows/post.yml`  ← the folders matter, don't flatten this
   - `images/`

   Easiest way: on the repo page click **Add file → Upload files**, then drag
   the whole folder in. GitHub keeps the structure.

4. Open `content.csv` on GitHub, click the pencil to edit, and
   **replace every `YOUR_GITHUB_USERNAME` with your actual GitHub username.**
   Use Ctrl+H / find-replace. Commit.

5. Make images public. A private repo's `raw.githubusercontent.com` links do
   not work for Facebook and Instagram — they need a public URL.
   **Settings → General → scroll to Danger Zone → Change visibility → Public.**

   This repo contains no passwords (those live in Secrets, which stay private
   even on a public repo), so making it public is safe.

---

### PART 1 — Images (20 min)

Put your photos in the `images/` folder, named `p001.jpg`, `p002.jpg` … to
match the `id` column in `content.csv`.

- **JPEG only.** Instagram rejects PNG and WebP.
- Square 1080×1080, or portrait 1080×1350.
- Under 8 MB each.

Use real photos — your machines on the shop floor, a technician on a service
call, toner stock on the shelf, a machine installed at a customer site. These
beat designed graphics for a service business. Shoot 16 photos on your phone
in one afternoon and you're stocked for a month.

To add images later from your phone: GitHub mobile app → repo → `images` →
Add file → Upload.

---

### PART 2 — Telegram (15 min) ✅ start here, it's the easiest

1. In Telegram, message **@BotFather** → `/newbot` → give it a name and a
   username ending in `bot`. He replies with a token like
   `8123456789:AAH...`. **That is your `TELEGRAM_BOT_TOKEN`.**
2. Open your AZ Office Automation channel → **Administrators → Add Admin** →
   add your bot → give it **Post Messages** permission.
3. Get the channel ID: if your channel has a public link like
   `t.me/azofficeautomation`, your `TELEGRAM_CHAT_ID` is `@azofficeautomation`.
   For a private channel, post any message, forward it to **@userinfobot**,
   and use the numeric ID it gives you (starts with `-100`).

---

### PART 3 — Gemini API key, free (5 min)

1. Go to **aistudio.google.com/apikey**
2. Sign in with `az.officeautomations@gmail.com` → **Create API key**.
3. Copy it. That's `GEMINI_API_KEY`.

Free tier is plenty for 4 posts a week. If the key is missing or the free
quota runs out, the script falls back to a built-in caption template and still
posts — it never fails because of this.

If Google renames the model later, set a repository **variable** (not secret)
named `GEMINI_MODEL` to the current one. Default is `gemini-2.0-flash`.

---

### PART 4 — Facebook + Instagram (this is the painful part, 1–2 hours)

**Prerequisites — fix these first or nothing below works:**
- Your Instagram must be a **Business** account (not Personal, not Creator).
  Instagram app → Settings → Account type → Switch to Business.
- Your Instagram Business account must be **linked to your Facebook Page**.
  Facebook Page → Settings → Linked accounts → Instagram → Connect.

**Steps:**

1. Go to **developers.facebook.com** → Log in → **My Apps → Create App**.
   - Use case: **Other** → Type: **Business** → name it `AZ Social Agent`.

2. In the app dashboard: **Add Product → Instagram → Set up**, and
   **Add Product → Facebook Login for Business → Set up**.

3. Go to **Tools → Graph API Explorer** (top right menu).
   - Select your app in the dropdown.
   - **Add permissions**, tick all of these:
     - `pages_show_list`
     - `pages_read_engagement`
     - `pages_manage_posts`
     - `instagram_basic`
     - `instagram_content_publish`
     - `business_management`
   - Click **Generate Access Token** → approve the popup, selecting your
     Page and Instagram account.

4. **Get your Page ID and a long-lived Page token.** In Graph API Explorer,
   run this in the query box and press Submit:

   ```
   me/accounts
   ```

   You'll get your Page's `id` (that's `FB_PAGE_ID`) and an `access_token`.

   That token expires in about an hour. To get one that does **not** expire:
   first exchange your user token for a long-lived one —

   ```
   oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=YOUR_SHORT_USER_TOKEN
   ```

   (App ID and Secret are in your app's **Settings → Basic**.)

   Then run `me/accounts` **again** using that long-lived user token. The
   Page token it returns now has **no expiry**. That one is `FB_PAGE_TOKEN`.

   ⚠️ If you skip this exchange step, posting will silently stop working
   after about an hour. This is the single most common reason these setups
   break.

5. **Get your Instagram user ID.** In Graph API Explorer run:

   ```
   YOUR_PAGE_ID?fields=instagram_business_account
   ```

   The `id` it returns is `IG_USER_ID`. (This is not your @username and not
   your personal Instagram ID.)

6. **Verify the token works.** Paste this in your browser, replacing the two
   values:

   ```
   https://graph.facebook.com/v21.0/me?access_token=YOUR_PAGE_TOKEN
   ```

   If you see your Page name, you're good.

**Note on App Review:** because you are posting to a Page and Instagram
account that **you own and are an admin of**, you do **not** need Meta App
Review or Business Verification. Review is only needed to post on behalf of
*other people's* accounts. Keep the app in Development mode.

---

### PART 5 — Add the secrets to GitHub (5 min)

Repo → **Settings → Secrets and variables → Actions → New repository secret**.

Add each of these:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from BotFather |
| `TELEGRAM_CHAT_ID` | `@yourchannel` or the `-100…` number |
| `GEMINI_API_KEY` | from Google AI Studio |
| `FB_PAGE_ID` | your Facebook Page ID |
| `FB_PAGE_TOKEN` | the **long-lived, non-expiring** Page token |
| `IG_USER_ID` | your Instagram business account ID |
| `SHEET_CSV_URL` | optional, see Part 7 |

Any platform whose secrets are missing is simply skipped. So you can add
Telegram today and go live, then add Facebook and Instagram next week.

---

### PART 6 — Test it (5 min)

1. Repo → **Actions** tab → if prompted, click **I understand my workflows,
   enable them**.
2. Click **AZ social post** → **Run workflow** → tick **dry_run** → **Run**.
3. Open the run and read the log. You'll see the exact caption it would post,
   and nothing will be published.
4. Happy with it? Run again with **dry_run unticked**. Check your Telegram
   channel, Facebook Page and Instagram.

After that it runs by itself at **10:00 AM IST on Sunday, Monday, Wednesday
and Friday**.

---

### PART 7 — Optional: edit content from your phone via Google Sheets

So you and Sindhu can add posts without touching GitHub.

1. Open `content.csv`, **File → Import** it into a new Google Sheet.
2. **File → Share → Publish to web** → choose the sheet → format
   **Comma-separated values (.csv)** → Publish.
3. Copy that URL into the `SHEET_CSV_URL` GitHub secret.

The script then reads the Sheet instead of the CSV. If the Sheet is ever
unreachable, it falls back to `content.csv` automatically.

Keep `image_url` pointing at your GitHub `images/` folder — Sheets can't host
images for Instagram, and Google Drive share links do **not** work with the
Instagram API.

---

## Content bank columns

| Column | What it does |
|---|---|
| `id` | Unique, e.g. `p017`. Used to track what's been posted. Never reuse. |
| `topic` | What the post is about. Gemini writes the caption from this. |
| `image_url` | Public JPEG URL. Must be public, must be .jpg |
| `platforms` | `telegram,facebook,instagram` — remove any you don't want |
| `caption_override` | Write your own caption here and Gemini is skipped |
| `notes` | Extra facts for the caption: prices, stock, offers |
| `skip` | Put `y` to park a row without deleting it |

Add new rows any time. When every row has been posted once, it starts the
cycle again from the top — so it never goes silent, but top it up monthly so
followers see fresh content.

---

## When something breaks

| Symptom | Cause and fix |
|---|---|
| Posts stopped after an hour or a day | `FB_PAGE_TOKEN` was a short-lived token. Redo Part 4 step 4 properly. |
| Instagram: "media container never finished" | Image isn't a public JPEG, is over 8 MB, or the repo is private. |
| Instagram fails, Facebook works | `IG_USER_ID` is wrong, or the IG account isn't Business and linked to the Page. |
| Telegram works, others don't | Normal while you're mid-setup. Secrets missing = platform skipped. |
| Caption looks generic | Gemini call failed and it used the fallback. Check the log and your `GEMINI_API_KEY`. |
| Same post went out twice | `posted.json` wasn't committed back. Check the workflow has `permissions: contents: write`. |
| Nothing runs at all | Actions tab → enable workflows. GitHub also pauses cron on repos with no activity for 60 days — just open the repo or run it manually. |

Every run emails you if it fails, and the full log is under the Actions tab.

---

## What this does not do

Being straight with you:

- **It does not advertise.** It posts. Reaching people who don't follow you
  costs money on Meta and Google, and no tool changes that.
- **It will not generate copier leads on its own.** Nobody buys a ₹1.3 lakh
  Canon off Instagram. This builds credibility for people who find you
  elsewhere and then check whether you're a real, active business.
- **Your Google Business Profile matters more than all three of these
  platforms combined.** GBP posting has no usable free API, so post there
  manually once a week. 3 minutes. Highest-value thing you can do.

Treat this as the free layer that keeps your presence alive while you fix
IndiaMART listings and Google Business Profile reviews — that's where the
revenue actually is.
