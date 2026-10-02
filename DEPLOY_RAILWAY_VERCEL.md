# Railway + Vercel deployment

## Current deployment setup

A Railway project and service have been created for the signed-in Railway account:

- Project: `parser-cc`
- Service: `parser-cc-bot`
- Public backend URL: `https://parser-cc-bot-production.up.railway.app`
- Persistent Railway volume: `/data`

The backend has not been deployed yet. Before deploying, set the bot token and a contact email in Railway Variables. Keep the token only in Railway; do not place it in this repository, Vercel, or chat.

## Architecture

- The project root runs the Telegram bot, FastAPI API, and SQLite database on Railway.
- Railway stores `parser.db` on its persistent `/data` volume.
- The `vercel` folder serves the Mini App. `vercel/vercel.json` proxies `/api/*` to the Railway backend, so private app data is not cached and browser requests stay same-origin.

## Before the first Railway deployment

Open the [Railway project](https://railway.com/project/1ed78ca8-84a5-41ea-804f-48387b8021d0), select the `parser-cc-bot` service, then its **Variables** tab. Add:

- `BOT_TOKEN` — token from BotFather.
- `CONTACT_EMAIL` — an address you use for service contact; this will be included in requests to OpenStreetMap's Nominatim service.
- `DB_PATH` — already set to `/data/parser.db`.
- `DEFAULT_LIMIT` — already set to `70`.
- `WEBAPP_URL` — already set to `https://parser-cc-miniapp.vercel.app`.

Optional free keys (recommended):

- `GEOAPIFY_API_KEY` — free Geoapify key, backup source when Overpass is busy.
- `GEMINI_API_KEY` — free Google AI Studio key for script generation (falls back to templates without it).

Trial/brand settings have working defaults: `TRIAL_SEARCHES=1`, `TRIAL_LEADS=10`, `JOIN_URL=https://t.me/m/KXcCg7quZGFh`, `CONTACT_USERNAME=SUN9ISE`.

Leave `ADMIN_IDS` empty until you get your numeric Telegram ID from `/id`. Railway provides the `PORT` variable automatically. The `/data` volume is already attached; volumes are mounted at runtime and persist data across deployments.

When the variables are ready, deploy from PowerShell:

```powershell
cd C:\Users\MakeMyCry\Desktop\parser_cc
railway up
```

The Railway service must run one replica: Telegram long polling should have only one bot process, and Railway volumes are not compatible with multiple replicas.

## Vercel deployment

The active `vercel/vercel.json` already routes requests to the Railway URL above. Deploy from PowerShell:

```powershell
cd C:\Users\MakeMyCry\Desktop\parser_cc\vercel
vercel --prod
```

The current production URL is `https://parser-cc-miniapp.vercel.app`; it is already stored in Railway's `WEBAPP_URL` variable. If you change the production domain later, update that variable and redeploy Railway.

## Owner setup

After Railway is online, send `/id` to the bot and copy the numeric Telegram ID it returns. In Railway Variables set `ADMIN_IDS` to that one ID, then redeploy. The configured owner is the only administrator; ordinary users can be approved without receiving admin access.

Once the owner ID and `WEBAPP_URL` are set, use `/start` and open the Mini App. Confirm the health endpoint at `https://parser-cc-bot-production.up.railway.app/healthz` returns `{"status":"ok"}`.

## Ongoing deploys

From `C:\Users\MakeMyCry\Desktop\parser_cc`, run `railway up` after backend changes. From `C:\Users\MakeMyCry\Desktop\parser_cc\vercel`, run `vercel --prod` after Mini App changes. Keep the railway volume attached at `/data`; do not delete it if you want to preserve users, leads, and limits.
