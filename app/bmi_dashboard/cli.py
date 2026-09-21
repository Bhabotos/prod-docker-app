"""Helper for the server operator:  python -m bmi_dashboard.cli hash-password

Prompts for the password (never as a command-line argument, so it does not end
up in shell history or process listings) and prints the value for
DASHBOARD_PASSWORD_HASH, plus a fresh SESSION_SECRET suggestion.
"""
import getpass
import secrets
import sys

from bmi_dashboard.security import hash_password

MIN_LENGTH = 12


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"hash-password", "hash-password-stdin"}:
        print("usage: python -m bmi_dashboard.cli hash-password | hash-password-stdin", file=sys.stderr)
        return 2
    if argv[1] == "hash-password-stdin":  # for CI / scripts
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Dashboard password: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1
    if len(password) < MIN_LENGTH:
        print(f"Use at least {MIN_LENGTH} characters.", file=sys.stderr)
        return 1
    print(f"DASHBOARD_PASSWORD_HASH={hash_password(password)}")
    if argv[1] == "hash-password":
        print(f"SESSION_SECRET={secrets.token_urlsafe(48)}   # suggestion; any random 32+ chars")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
