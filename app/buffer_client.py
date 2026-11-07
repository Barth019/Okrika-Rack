
import httpx


BUFFER_TOKEN_URL = "https://auth.buffer.com/token"
BUFFER_API_URL = "https://api.buffer.com"


class BufferAPIError(Exception):
    """Raised when Buffer returns an unexpected API response."""


def exchange_authorization_code(code, code_verifier, config):
    """Exchange an OAuth authorization code for Buffer tokens."""

    payload = {
        "client_id": config["BUFFER_CLIENT_ID"],
        "client_secret": config["BUFFER_CLIENT_SECRET"],
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config["BUFFER_REDIRECT_URI"],
        "code_verifier": code_verifier,
    }

    try:
        response = httpx.post(
            BUFFER_TOKEN_URL,
            data=payload,
            headers={"Accept": "application/json"},
            timeout=20.0,
        )
        response.raise_for_status()
        tokens = response.json()

    except (httpx.HTTPError, ValueError) as exc:
        raise BufferAPIError(
            "Buffer token exchange failed."
        ) from exc

    required_fields = [
        "access_token",
        "refresh_token",
        "expires_in",
    ]

    if not isinstance(tokens, dict) or any(
        not tokens.get(field) for field in required_fields
    ):
        raise BufferAPIError(
            "Buffer returned an incomplete token response."
        )

    try:
        tokens["expires_in"] = int(tokens["expires_in"])
    except (TypeError, ValueError) as exc:
        raise BufferAPIError(
            "Buffer returned an invalid token expiry."
        ) from exc

    if tokens["expires_in"] <= 0:
        raise BufferAPIError(
            "Buffer returned an invalid token expiry."
        )

    return tokens


def get_buffer_account(access_token):
    """Retrieve the authenticated Buffer account."""

    query = """
    query GetAccount {
        account {
            id
            email
        }
    }
    """

    try:
        response = httpx.post(
            BUFFER_API_URL,
            json={"query": query},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )
        response.raise_for_status()
        result = response.json()

    except (httpx.HTTPError, ValueError) as exc:
        raise BufferAPIError(
            "Could not retrieve the Buffer account."
        ) from exc

    if not isinstance(result, dict) or result.get("errors"):
        raise BufferAPIError(
            "Buffer returned an account lookup error."
        )

    account = result.get("data", {}).get("account")

    if not isinstance(account, dict):
        raise BufferAPIError(
            "Buffer returned an invalid account response."
        )

    if not account.get("id") or not account.get("email"):
        raise BufferAPIError(
            "Buffer account information is incomplete."
        )

    return account
