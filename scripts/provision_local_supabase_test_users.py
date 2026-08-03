from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path

import httpx


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def _create_user(
    client: httpx.Client,
    *,
    api_url: str,
    service_role_key: str,
    anon_key: str,
    label: str,
) -> tuple[str, str]:
    suffix = secrets.token_hex(6)
    email = f"janani-{label}-{suffix}@synthetic.local"
    password = f"Synthetic-{secrets.token_urlsafe(18)}-9!"

    admin_headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    create_response = client.post(
        f"{api_url}/auth/v1/admin/users",
        headers=admin_headers,
        json={
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"synthetic": True, "test_label": label},
        },
    )
    create_response.raise_for_status()
    user_id = create_response.json()["id"]

    sign_in_response = client.post(
        f"{api_url}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"email": email, "password": password},
    )
    sign_in_response.raise_for_status()
    access_token = sign_in_response.json()["access_token"]
    return user_id, access_token


def _append_github_env(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create two ephemeral synthetic users in a local Supabase stack."
    )
    parser.add_argument("--github-env", type=Path, required=True)
    args = parser.parse_args()

    api_url = _required_env("API_URL").rstrip("/")
    anon_key = _required_env("ANON_KEY")
    service_role_key = _required_env("SERVICE_ROLE_KEY")

    with httpx.Client(timeout=20) as client:
        user_a_id, user_a_token = _create_user(
            client,
            api_url=api_url,
            service_role_key=service_role_key,
            anon_key=anon_key,
            label="a",
        )
        user_b_id, user_b_token = _create_user(
            client,
            api_url=api_url,
            service_role_key=service_role_key,
            anon_key=anon_key,
            label="b",
        )

    _append_github_env(
        args.github_env,
        {
            "JANANI_STAGING_SUPABASE_URL": api_url,
            "JANANI_STAGING_SUPABASE_PUBLISHABLE_KEY": anon_key,
            "JANANI_STAGING_SUPABASE_SERVICE_ROLE_KEY": service_role_key,
            "JANANI_STAGING_USER_A_ID": user_a_id,
            "JANANI_STAGING_USER_A_TOKEN": user_a_token,
            "JANANI_STAGING_USER_B_ID": user_b_id,
            "JANANI_STAGING_USER_B_TOKEN": user_b_token,
        },
    )


if __name__ == "__main__":
    main()
