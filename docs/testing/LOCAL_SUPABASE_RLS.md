# Free Local Supabase RLS Validation

This test environment is local and ephemeral. It does not connect to or modify the hosted Janani Supabase project.

## Requirements

- Docker Desktop running
- Python 3.12
- Supabase CLI
- Repository dependencies installed with `pip install -e ".[dev]"`

## Windows PowerShell

```powershell
supabase start --exclude studio,imgproxy,realtime,edge-runtime,logflare,vector,supavisor
supabase db reset --local --no-seed

$StatusLines = supabase status -o env
foreach ($Line in $StatusLines) {
    if ($Line -match '^([^=]+)="?(.*?)"?$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
    }
}

$EnvFile = Join-Path $PWD '.local-supabase-test.env'
New-Item -ItemType File -Path $EnvFile -Force | Out-Null
python scripts/provision_local_supabase_test_users.py --github-env $EnvFile
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
    }
}

pytest tests/integration/test_supabase_staging_rls.py -m staging -q
supabase stop --no-backup
Remove-Item $EnvFile -ErrorAction SilentlyContinue
```

Do not commit `.local-supabase-test.env`. It contains short-lived credentials for the local stack.

## What is validated

- both synthetic access tokens resolve to different users;
- profile and pregnancy rows are owner-isolated;
- consent history is append-only;
- medication, appointment, and attachment rows cannot reference another user's pregnancy;
- internal extraction and audit tables reject direct authenticated writes;
- authenticated audit RPCs derive identity from `auth.uid()`;
- attachment confirmation RPCs enforce ownership;
- private storage paths are owner-scoped;
- account-deletion requests are private and idempotent.

## GitHub Actions

The `local-supabase` CI job performs the same process on an isolated Docker runner. It creates no paid Supabase branch and requires no hosted-project credentials.
