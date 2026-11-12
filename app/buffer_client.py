
import httpx


BUFFER_TOKEN_URL = "https://auth.buffer.com/token"
BUFFER_API_URL = "https://api.buffer.com"


class BufferAPIError(Exception):
    """Raised when Buffer returns an unexpected API response."""

def buffer_graphql_request(access_token, query, variables=None):
    """Send an authenticated GraphQL request to Buffer."""

    payload = {"query": query}

    if variables is not None:
        payload["variables"] = variables

    try:
        response = httpx.post(
            BUFFER_API_URL,
            json=payload,
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
            "Buffer API request failed."
        ) from exc

    if not isinstance(result, dict):
        raise BufferAPIError("Buffer returned an invalid response.")

    if result.get("errors"):
        raise BufferAPIError("Buffer returned a GraphQL error.")

    if "data" not in result:
        raise BufferAPIError("Buffer response contains no data.")

    return result["data"]

def create_buffer_post(
    access_token,
    channel_id,
    text,
    due_at,
    image_url=None,
    channel_service=None,
):
    """Create a Buffer post scheduled for a specific UTC time."""

    if not channel_id:
        raise ValueError("A Buffer channel ID is required.")

    if not text or not text.strip():
        raise ValueError("Post text cannot be empty.")

    if not due_at:
        raise ValueError("A scheduled publication time is required.")

    service = (channel_service or "").lower()

    if service == "instagram" and not image_url:
        raise ValueError("Instagram posts require a product image.")

    assets = []

    if image_url:
        if not image_url.startswith("https://"):
            raise ValueError(
                "The product image must use a public HTTPS URL."
            )

        assets.append({
            "image": {
                "url": image_url,
            }
        })

    post_input = {
        "text": text.strip(),
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "customScheduled",
        "dueAt": due_at,
        "assets": assets,
        "needsApproval": False,
    }

    if service == "instagram":
        post_input["metadata"] = {
            "instagram": {
                "type": "post",
                "shouldShareToFeed": True,
            }
        }

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
        createPost(input: $input) {
            ... on PostActionSuccess {
                post {
                    id
                    text
                    dueAt
                }
            }
            ... on MutationError {
                message
            }
        }
    }
    """

    variables = {
        "input": post_input,
    }

    data = buffer_graphql_request(
        access_token,
        mutation,
        variables,
    )

    result = data.get("createPost")

    if not isinstance(result, dict):
        raise BufferAPIError(
            "Buffer returned an invalid post creation response."
        )

    if result.get("message"):
        raise BufferAPIError(result["message"])

    post = result.get("post")

    if not isinstance(post, dict) or not post.get("id"):
        raise BufferAPIError(
            "Buffer did not confirm that the post was created."
        )

    return post

def delete_buffer_post(access_token, post_id):
    """Delete a scheduled post from Buffer."""

    if not post_id:
        raise ValueError("A Buffer post ID is required.")

    mutation = """
    mutation DeletePost($input: DeletePostInput!) {
        deletePost(input: $input) {
            ... on DeletePostSuccess {
                id
            }
            ... on MutationError {
                message
            }
        }
    }
    """

    variables = {
        "input": {
            "id": post_id,
        }
    }

    data = buffer_graphql_request(
        access_token,
        mutation,
        variables,
    )

    result = data.get("deletePost")

    if not isinstance(result, dict):
        raise BufferAPIError(
            "Buffer returned an invalid post deletion response."
        )

    if result.get("message"):
        raise BufferAPIError(result["message"])

    deleted_id = result.get("id")

    if deleted_id != post_id:
        raise BufferAPIError(
            "Buffer did not confirm post deletion."
        )

    return deleted_id


def get_buffer_post(access_token, post_id):
    """Retrieve the current status and publication details of a Buffer post."""

    if not access_token:
        raise ValueError("A Buffer access token is required.")

    if not post_id:
        raise ValueError("A Buffer post ID is required.")

    query = """
    query GetPost($input: PostInput!) {
        post(input: $input) {
            id
            status
            sentAt
            dueAt
            externalLink
            channelId
            channelService
            error {
                message
                supportUrl
            }
        }
    }
    """

    variables = {
        "input": {
            "id": post_id,
        }
    }

    data = buffer_graphql_request(
        access_token,
        query,
        variables,
    )

    post = data.get("post")

    if not isinstance(post, dict):
        raise BufferAPIError(
            "Buffer returned an invalid post lookup response."
        )

    if post.get("id") != post_id:
        raise BufferAPIError(
            "Buffer returned an unexpected post ID."
        )

    if not post.get("status"):
        raise BufferAPIError(
            "Buffer returned a post without a status."
        )

    return post

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

def refresh_access_token(refresh_token, config):
    """Exchange a Buffer refresh token for a new token pair."""

    if not refresh_token:
        raise ValueError("A refresh token is required.")

    payload = {
        "client_id": config["BUFFER_CLIENT_ID"],
        "client_secret": config["BUFFER_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
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
            "Buffer token refresh failed."
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
            "Buffer returned an incomplete refreshed token response."
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

def get_buffer_organizations(access_token):
    """Retrieve organizations belonging to the Buffer account."""

    query = """
    query GetOrganizations {
        account {
            organizations {
                id
                name
                channelCount
            }
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
            "Could not retrieve Buffer organizations."
        ) from exc

    if not isinstance(result, dict) or result.get("errors"):
        raise BufferAPIError(
            "Buffer returned an organization lookup error."
        )

    organizations = (
        result.get("data", {})
        .get("account", {})
        .get("organizations")
    )

    if not isinstance(organizations, list):
        raise BufferAPIError(
            "Buffer returned an invalid organizations response."
        )

    return organizations


def get_buffer_channels(access_token, organization_id):
    """Retrieve social media channels for a Buffer organization."""

    if not organization_id:
        raise ValueError("An organization ID is required.")

    query = """
    query GetChannels($organizationId: OrganizationId!) {
        channels(input: { organizationId: $organizationId }) {
            id
            name
            displayName
            service
            isQueuePaused
            isDisconnected
            isLocked
        }
    }
    """

    try:
        response = httpx.post(
            BUFFER_API_URL,
            json={
                "query": query,
                "variables": {
                    "organizationId": organization_id,
                },
            },
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
            "Could not retrieve Buffer channels."
        ) from exc

    if not isinstance(result, dict) or result.get("errors"):
        raise BufferAPIError(
            "Buffer returned a channel lookup error."
        )

    channels = result.get("data", {}).get("channels")

    if not isinstance(channels, list):
        raise BufferAPIError(
            "Buffer returned an invalid channels response."
        )

    return channels
