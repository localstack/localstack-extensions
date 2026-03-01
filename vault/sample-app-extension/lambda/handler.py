"""
Sample Lambda function for Vault Lambda Extension integration.

This function reads secrets written by the Vault Lambda Extension to /tmp/secrets/.
The extension handles authentication with Vault via IAM auth and fetches secrets
during Lambda initialization.

For more details on the Vault Lambda Extension, see:
https://github.com/hashicorp/vault-lambda-extension
"""

import json
import os


def handler(event, context):
    """
    Lambda handler that reads secrets from the Vault Lambda Extension.

    The extension writes secrets to files specified by VAULT_SECRET_FILE_* env vars.
    This handler reads from those files.
    """

    result = {
        "message": "Vault Lambda Extension integration",
        "success": False,
        "secrets": {},
        "env": {
            "VAULT_ADDR": os.environ.get("VAULT_ADDR", "not set"),
            "VAULT_AUTH_PROVIDER": os.environ.get("VAULT_AUTH_PROVIDER", "not set"),
            "VAULT_AUTH_ROLE": os.environ.get("VAULT_AUTH_ROLE", "not set"),
            "VAULT_SECRET_PATH_MYAPP": os.environ.get("VAULT_SECRET_PATH_MYAPP", "not set"),
            "VAULT_SECRET_FILE_MYAPP": os.environ.get("VAULT_SECRET_FILE_MYAPP", "not set"),
        },
    }

    # Path where Vault Lambda Extension writes secrets
    secret_file = os.environ.get("VAULT_SECRET_FILE_MYAPP", "/tmp/secrets/myapp")

    if not os.path.exists(secret_file):
        result["message"] = f"Secret file not found: {secret_file}"
        result["error"] = "EXTENSION_NOT_RUNNING"
        result["hint"] = "Ensure the Vault Lambda Extension layer is attached and configured correctly"
        return result

    try:
        with open(secret_file, "r") as f:
            secrets = json.load(f)

        # Extract the actual secret data from Vault's response format
        # The extension writes the full Vault response, which has data nested
        secret_data = secrets.get("data", {}).get("data", {})
        if not secret_data:
            # Fallback if the structure is different
            secret_data = secrets.get("data", secrets)

        result["success"] = True
        result["secrets"] = {
            "source": "vault-lambda-extension",
            "keys_found": list(secret_data.keys()) if isinstance(secret_data, dict) else [],
            "count": len(secret_data) if isinstance(secret_data, dict) else 0,
        }
        result["message"] = f"Successfully loaded {len(secret_data)} secrets via Vault Lambda Extension"
        return result

    except json.JSONDecodeError as e:
        result["message"] = f"Failed to parse secrets file: {e}"
        result["error"] = "PARSE_ERROR"
        return result

    except Exception as e:
        result["message"] = f"Error reading secrets: {e}"
        result["error"] = type(e).__name__
        return result
