"""
One-time helper: turns your downloaded OAuth client_secret.json into a
refresh token you can store as the GitHub secret YT_REFRESH_TOKEN.

Run locally ONCE:
    pip install google-auth-oauthlib
    python auth/get_token.py /path/to/client_secret.json
Then copy the three printed values into your GitHub repo secrets.
"""
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main(secret_path: str):
    flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    print("\n=== Add these to GitHub repo Settings → Secrets → Actions ===")
    print("YT_CLIENT_ID     =", creds.client_id)
    print("YT_CLIENT_SECRET =", creds.client_secret)
    print("YT_REFRESH_TOKEN =", creds.refresh_token)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python auth/get_token.py /path/to/client_secret.json")
        sys.exit(1)
    main(sys.argv[1])
