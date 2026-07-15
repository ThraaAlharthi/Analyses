"""Check that our Sentinel Hub credentials authenticate against CDSE."""
import os
from dotenv import load_dotenv
from sentinelhub import SHConfig

load_dotenv()

config = SHConfig()
config.sh_client_id = os.getenv("SH_CLIENT_ID")
config.sh_client_secret = os.getenv("SH_CLIENT_SECRET")
# These two URLs are CDSE-specific. The commercial Sentinel Hub uses
# different ones, and mixing them up fails with an unhelpful error.
config.sh_base_url = "https://sh.dataspace.copernicus.eu"
config.sh_token_url = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
    "/protocol/openid-connect/token"
)

if not config.sh_client_id or not config.sh_client_secret:
    raise SystemExit("No credentials found -- check .env has SH_CLIENT_ID and SH_CLIENT_SECRET")

print("client id loaded :", config.sh_client_id[:8] + "..." )
print("secret loaded    :", "yes" if config.sh_client_secret else "no")

# Ask for a token. This is the actual proof.
from sentinelhub import SentinelHubSession
session = SentinelHubSession(config=config)
token = session.token
print("\nAUTH OK - token acquired, expires in", int(token["expires_in"]), "seconds")
