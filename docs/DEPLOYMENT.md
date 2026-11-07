# Deploying this

**Nothing is deployed.** No hosting account has been created, no provider
configured and nothing paid for. This is the research, so the decision can be
made with the trade-offs visible. Researched 2026-11-07; free tiers move
quickly, so check the pricing pages before acting on any of it.

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
