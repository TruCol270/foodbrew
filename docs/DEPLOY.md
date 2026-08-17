# Deploying the hosted instance

One Fly Machine, one volume, one password. This is a private instance for one
person, not a multi-user service — see
`docs/superpowers/plans/2026-08-17-m6-hosted-single-instance.md` for why each
choice is what it is.

## What she gets

A URL (`https://<app>.fly.dev`) and a password. Her browser prompts for it; any
username works. Nothing to install.

## First deploy

```bash
# 1. Create the app WITHOUT deploying, and without high availability.
fly launch --no-deploy --ha=false --copy-config

# 2. Create the volume. One volume, one machine, same region as fly.toml.
fly volumes create foodbrew_data --region iad --size 1

# 3. Set the password. Pick something long; she will paste it once and let the
#    browser remember it.
fly secrets set FOODBREW_ACCESS_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
fly secrets list          # confirm it is set; the value is never shown again

# 4. Deploy.
fly deploy --ha=false

# 5. VERIFY ONE MACHINE. `--ha=false` has a community report of starting two
#    anyway, and a second machine means a second volume and a forked database.
fly status
# Expect exactly one machine in the list. If there are two, destroy the extra
# NOW, before she enters any data:
#   fly machine destroy <id> --force

# 6. Raise snapshot retention from the 5-day default.
fly volumes list
fly volumes update <volume-id> --snapshot-retention 30

# 7. Smoke-test the gate. This is what catches a deploy whose secret never got
#    set — without it the instance is a public read/write endpoint. Target
#    /enzymes, not /health: /health is in OPEN_PATHS (src/foodbrew/api/access.py)
#    and answers 200 with no password at all, so it never proves the secret
#    was set correctly.
curl -s -o /dev/null -w '%{http_code}\n' https://<app>.fly.dev/api/v1/enzymes
# Expect: 401 (no credentials offered)

curl -s -o /dev/null -w '%{http_code}\n' -u "founder:<the password>" https://<app>.fly.dev/api/v1/enzymes
# Expect: 200. A 401 here means FOODBREW_ACCESS_PASSWORD never got set, or was
# set to something other than what you just typed.

# /health is a separate, open-path sanity check that the process and the
# database (not the password) are both up:
curl -s -u "founder:<the password>" https://<app>.fly.dev/api/v1/health
# Expect: {"status":"ok","engine_version":"1.0.0","database":"ok"}
```

## Backups

Two independent mechanisms:

1. **Fly volume snapshots** — automatic and free, retention set to 30 days
   above. There is no flyctl command that re-points an already-running
   machine at a different volume — a volume can only be attached when a
   machine is created. Restore with `fly machine clone`, which creates the
   new volume from the snapshot and a new machine in one step, so at no
   point do two volumes named `foodbrew_data` exist at once:

   ```bash
   fly status                                    # note the current machine id
   fly volumes list                              # note the current volume id
   fly volumes snapshots list <volume-id>        # note the snapshot id to restore
   fly machine stop <machine-id>                 # stop writes before restoring
   fly machine clone <machine-id> --from-snapshot <snapshot-id>
   # ^ creates one new machine with one new volume, restored from the
   #   snapshot and attached automatically. Confirm it is healthy
   #   (fly status, then the smoke test in step 7 above) before continuing.
   fly machine destroy <machine-id> --force      # remove the old machine
   fly volumes destroy <volume-id>               # remove the old volume
   fly status && fly volumes list                # confirm exactly one of each
   ```
2. **A daily copy in R2** — `.github/workflows/backup.yml`, 07:17 UTC. It runs
   `VACUUM INTO` inside the machine, pulls the copy down, **verifies
   `PRAGMA integrity_check` and a non-zero row count before uploading**, then
   gzips it to `s3://<bucket>/daily/`.

Required GitHub Actions secrets: `FLY_API_TOKEN`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ENDPOINT`.

Run it by hand any time from the Actions tab (`workflow_dispatch`). **Do that
once immediately after the first deploy** — an untested backup path is not a
backup.

### Restoring from R2

```bash
aws s3 cp s3://<bucket>/daily/foodbrew-<stamp>.db.gz . --endpoint-url <endpoint>
gunzip foodbrew-<stamp>.db.gz
python3 -c "import sqlite3;print(sqlite3.connect('foodbrew-<stamp>.db').execute('PRAGMA integrity_check').fetchone())"
fly ssh sftp shell -a <app>
# inside the sftp shell:
put foodbrew-<stamp>.db /data/foodbrew.db
# exit the shell, then:
fly machine restart <id>
```

The `put` followed by the restart is the expected downtime for this path —
consistent with "one machine means real downtime" above. The app uses
SQLite's default rollback-journal mode, not WAL (no `PRAGMA journal_mode`
anywhere in `src/foodbrew`), so there is no `-wal`/`-shm` sidecar file to
worry about; a request landing mid-`put`, before the restart, is still
possible, which is why this is a manual, watched operation rather than an
automated one.

## Day 2

```bash
fly logs -a <app>                       # live logs
fly ssh console -a <app>                # shell in the machine
fly ssh sftp get /data/foodbrew.db      # pull her database down to inspect
fly status -a <app>                     # machine count and health
fly releases -a <app>                   # deploy history with image refs
fly deploy --image <previous-image-ref>  # roll back
```

## Things that will bite

- **Never `fly scale count 2`**, never add a region, never re-run
  `fly launch` without `--ha=false`. A second machine gets its own new volume
  and the database forks silently — no error, no symptom, two divergent copies.
  `tests/test_fly_config.py` guards the config; nothing can guard a CLI typo.
- **One machine means real downtime on deploy**, and a host incident can mean
  hours. Tell her that upfront so an outage does not read as lost work. This
  is downtime, not data loss — the volume persists across the outage, and two
  independent backups (Fly snapshots + daily R2 copy) exist regardless.
- **A failed migration leaves the app unbootable**, and Fly's smoke check stops
  the rollout but leaves the machine down. Recovery is
  `fly deploy --image <last-good>`, so know the last-good ref before deploying.
  `fly releases` has it.
- **Health is now a database read.** A 503 with a sqlite message in `fly logs`
  means the volume, not the process.
- **Rotating the password:** `fly secrets set FOODBREW_ACCESS_PASSWORD=...`
  restarts the machine. Tell her before you do it, or the app will simply stop
  letting her in.
