"""Deploy the Databricks bundle using local environment variables."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    profile = os.environ.get("databricks_profile", "").strip()
    notify_email = os.environ.get("databricks_email_account", "").strip()
    target = sys.argv[1] if len(sys.argv) > 1 else "dev"

    if not profile:
        raise SystemExit(
            "Set databricks_profile before deploying, e.g.\n"
            "  $env:databricks_profile = 'wyatts_databricks'"
        )

    env = os.environ.copy()
    env["DATABRICKS_CONFIG_PROFILE"] = profile
    env.pop("DATABRICKS_CLUSTER_ID", None)

    cmd = [
        "databricks",
        "bundle",
        "deploy",
        "-t",
        target,
        "--profile",
        profile,
        "--auto-approve",
    ]
    if notify_email:
        cmd.extend(["--var", f"notify_email={notify_email}"])
    subprocess.run(cmd, check=True, env=env)


if __name__ == "__main__":
    main()