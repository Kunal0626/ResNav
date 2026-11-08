# Deploying this

Two parts: **why the shape is what it is** (the research), and **the runbook**
for putting it live. The decision taken was the VM option -- the SPA on
Vercel, everything else on one Always Free machine -- because it is the only
one that keeps the triggers and stored procedures the project is about.

Researched 2026-11-07, re-checked 2026-11-08. Free tiers move quickly, so
check the pricing pages before acting on any of it.

## The constraint that decides everything

This project's substance is in the database: ten triggers, five stored
routines, seventeen foreign keys and twenty-two `CHECK` constraints. The
application deliberately cannot do the allocation itself — that was the whole
point of Phase 4.

So the usual advice for "free Postgres/MySQL" does not apply here. The
question is not *where can I get a free SQL database*, it is **where can I get
a database that runs triggers and stored procedures**.

That single question eliminates most of the free tier.

### TiDB Cloud Starter — the obvious answer, and the wrong one

TiDB Serverless/Starter is the most-recommended free MySQL-compatible
database in 2026. It cannot run this project. PingCAP's own compatibility
page lists as unsupported:

- stored procedures and functions
- **triggers**
- events and user-defined functions
- foreign key constraints (version-dependent)

Deploying here would mean moving every invariant back into Python — which is
precisely the architecture this project exists to argue against, and would
delete the oversell protection Phase 6 demonstrated. "MySQL-compatible" means
the wire protocol and most of the syntax, not the server-side programmability.

This is worth knowing for its own sake: *compatible* is a claim about an
interface, and the thing you depend on may live outside it.

### What else disappeared in 2026

| Provider | Status |
|---|---|
| **Aiven** | MySQL free tier **retired**; new MySQL services cannot be created on the free plan. Cheapest MySQL is the ~$5/month Developer tier. Free *PostgreSQL* remains. |
| **PlanetScale** | Hobby/free tier **removed**, and has not returned. Entry point is paid. |
| **PythonAnywhere** | MySQL moved behind a paid plan for new free accounts in January 2026. |
| **Railway** | No permanent free tier; trial credit only. MySQL is available and counts against the same allowance. |
| **Fly.io** | Sources conflict on whether a free tier exists for new users; a card is required either way. |
| **Koyeb** | Free tier does not sleep, which is its real advantage, but the free managed database is PostgreSQL. |

## The realistic options

**1. Frontend on Vercel, free, no caveats.** The SPA is a static build; Vercel's
free tier covers it comfortably and `frontend/vercel.json` is already
committed. This half is genuinely free and genuinely easy.

**2. API and MySQL on one small VM — the honest recommendation.**
Oracle Cloud's Always Free tier (or any ~$5/month VPS) runs
`docker compose up` exactly as tested in Phase 8: real MySQL, every trigger
and procedure intact, nothing about the project compromised to fit a
platform. The cost is that you administer it — updates, backups, TLS.

**3. API on Render's free tier + MySQL somewhere paid.** Render still has a
no-card free web service, but it **sleeps after 15 minutes** of inactivity,
so the first request after idle takes tens of seconds. For a portfolio link
someone opens once, that reads as a broken site. Bandwidth was also cut to
5 GB in April 2026. And it solves only the API: the database still needs a
home, which is a ~$5/month Aiven Developer plan or similar.

**4. Don't deploy; record a demo instead.** A GIF or short screen capture in
the README, plus `make docker` working from a clean clone, costs nothing and
never goes down the week before an interview. Your brief already names this
as an acceptable fallback, and for a database-centric project it loses very
little: the interesting part is the schema and the concurrency proof, both of
which a reader runs locally in two commands.

## Recommendation

**Option 4 now, option 2 if you want a live link.** Deploying is not a
technical blocker — Phase 8 proved the stack runs from nothing on MySQL 8.4 —
it is a question of whether a URL is worth the running cost and the
maintenance. Nothing in the README depends on a deployment existing, and a
sleeping free-tier link is worse than no link.

If a live URL is wanted, the VM route is the only one that keeps the project
intact. Everything else either sleeps, costs money, or quietly removes the
triggers.

## Sources

- [TiDB MySQL compatibility](https://docs.pingcap.com/tidbcloud/mysql-compatibility) — the unsupported-features list
- [Aiven: the MySQL free tier is retired](https://aiven.io/free-mysql-database)
- [PlanetScale alternatives after hobby tier removal](https://www.dbpro.app/blog/planetscale-alternatives)
- [Platforms with a real free tier for developers in 2026](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026) — vendor source, weigh accordingly
- [State of Free Hosting 2026](https://snapdeploy.dev/state-of-free-hosting)
- [Free database hosting (community-maintained list)](https://gist.github.com/bmaupin/0ce79806467804fdbbf8761970511b8c)

---

# The runbook

## What is tested and what is not

Everything in `deploy/` was brought up and exercised on an Apple Silicon Mac
before being written down: Caddy issued a certificate, the SPA loaded over
HTTPS, `/api/health` answered through the proxy, and a `POST .../allocate`
moved exactly 400 units out of `StockLevels` through TLS. Apple Silicon is
arm64, the same architecture as Oracle's Ampere instances, so the images are
known to build there.

**The Oracle-specific steps below have not been run** -- creating the account
needs a card and an identity, which is yours to do. They come from Oracle's
documentation, not from a machine I had. Treat the firewall step especially
as the one most likely to bite; it is the usual reason a new Oracle VM
appears dead.

## 1. The machine

Two things to get right before clicking anything, because one is permanent
and the other quietly breaks the deploy:

**The home region is chosen once, at signup, and cannot be changed.** Always
Free resources only exist in it. Pick one you are near -- `ap-mumbai-1` or
`ap-hyderabad-1` from India.

**Do not fall back to the `VM.Standard.E2.1.Micro` shape.** It is also Always
Free and it is the default the console offers, but it has 1 GB of RAM. This
stack is MySQL 8.4 plus gunicorn with scikit-learn imported, plus nginx and
Caddy; it will not fit, and the failure mode is the OOM killer taking out
mysqld mid-request rather than an honest refusal to start. If A1 capacity is
unavailable, retry or change availability domain -- do not downgrade.

Oracle Cloud -> Compute -> Instances -> Create.

- **Shape:** `VM.Standard.A1.Flex` (Ampere, arm64). Always Free covers up to
  4 OCPU / 24 GB across your A1 instances; 1 OCPU / 6 GB is plenty here.
- **Image:** Ubuntu 22.04 or 24.04.
- **Networking:** assign a public IPv4. Save the SSH key it offers -- there
  is no second chance.

If capacity errors appear ("Out of host capacity"), that is normal for A1 in
busy regions. Retry, or pick a different availability domain.

## 2. Open the ports -- both firewalls

This is the step people miss. Oracle filters traffic in **two** places and
you must open both.

**a. The cloud side.** VCN -> Security Lists -> the subnet's default list ->
Add Ingress Rules. Source `0.0.0.0/0`, TCP, destination ports **80** and
**443**.

**b. The machine side.** Oracle's Ubuntu images ship with iptables rules that
drop everything except SSH:

```
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

On an Oracle Linux image it is firewalld instead:

```
sudo firewall-cmd --permanent --add-service=http --add-service=https && sudo firewall-cmd --reload
```

Do not skip (b) because (a) looks done. A half-open path presents as Caddy
retrying the ACME challenge forever with no obvious cause.

## 3. A hostname

Caddy needs a name to get a certificate for; a bare IP cannot have one from
Let's Encrypt. A free subdomain is enough -- [DuckDNS](https://www.duckdns.org)
gives you `something.duckdns.org` pointed at your IP in about a minute.
`duckdns.org` is on the Public Suffix List, which matters: it means Let's
Encrypt counts your subdomain separately for rate limits rather than
lumping it in with every other user of the parent domain. `nip.io` and
`sslip.io` are not, so they run into shared rate limits.

Point it at the VM's public IP and confirm it resolves before starting the
stack, or the first certificate attempt fails and backs off.

## 4. Bring it up

```
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER && newgrp docker
git clone https://github.com/Kunal0626/ResNav.git resnav && cd resnav
cp .env.example .env
```

Edit `.env`:

- `DRA_MYSQL_PASSWORD` and `DRA_MYSQL_ROOT_PASSWORD` -- generate them, do not
  reuse anything (`openssl rand -base64 24`)
- `SECRET_KEY` -- likewise
- `RESNAV_DOMAIN` -- the DuckDNS name from step 3
- `CORS_ORIGINS` -- the Vercel origin from step 5, exactly, no trailing slash

Then:

```
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

First boot applies the schema, routines and seed, which takes a minute or
two. `docker compose ps` should show db, api and web healthy and caddy
running. The whole app is then live at `https://<your-domain>` -- the VM
serves a complete copy, which is worth checking before involving Vercel.

## The demo deployment

While nothing hosts the API, `frontend/vercel.json` builds with
`npm run build:demo`, which sets `VITE_DEMO_MODE=true` so the SPA answers
from the snapshot in `frontend/public/demo` instead of calling a backend
that does not exist. `tools/snapshot_demo.py` regenerates that snapshot
from a running stack; re-run it after changing the seed or the demo drifts
from the database.

Note that `vercel.json` rejects unknown keys anywhere in the file, nested
ones included -- a `"comment"` key had been sitting in the rewrites block
since Phase 8 and would have failed any deploy, which nothing caught
because nothing had ever deployed. The rewrite it described sends every
path that is not `assets/`, `demo/`, `favicon.svg` or `robots.txt` to the
SPA shell, so client-side routes survive a page refresh.

Once a real backend exists, put `buildCommand` back to `npm run build` and
set `VITE_API_BASE_URL` as described below.

## 5. The SPA on Vercel

From the repository root:

```
npx vercel --cwd frontend
```

Set one environment variable in the Vercel project, for all environments:

```
VITE_API_BASE_URL = https://<your-domain>
```

Redeploy after setting it -- Vite inlines environment variables at build
time, so a variable added after a build does not reach the bundle.

Then put the Vercel origin into `CORS_ORIGINS` in `.env` on the VM and
`docker compose ... up -d api` to pick it up. Without this the browser
blocks every call with a CORS error while `curl` keeps working, which is a
confusing way to lose an evening.

## 6. Keeping the demo honest (optional)

The API is public and writable, so a visitor can allocate stock until there
is none left. A nightly reseed keeps it presentable:

The seed is four ordered files, not one, and `docker/mysql-init.sh` already
knows the order -- so the reset is to drop the schema and re-run that same
script rather than to pipe any single file:

```
0 3 * * * cd ~/resnav && docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml exec -T db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE \`$MYSQL_DATABASE\`; CREATE DATABASE \`$MYSQL_DATABASE\`;"' && docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml exec -T db sh /docker-entrypoint-initdb.d/10-resnav.sh
```

Run locally, that restored 17 tables, 9 views, 10 triggers, 5 routines and
the full 108150 units of stock, and cleared the allocations back to zero.
The API needs no restart: it opens a connection per request, so it rides
through the database being dropped underneath it.

## Teardown

```
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml down -v
```

`-v` drops the database volume too, which is what you want if you are
rebuilding from the seed and not what you want otherwise.
