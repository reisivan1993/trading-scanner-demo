from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

VAULT_SERVICE = "trading-scanner-demo"


def get_secret(key: str) -> str | None:
    """Retrieve a secret, checking Windows Credential Manager first, then env vars.

    Priority:
    1. Windows Credential Manager (via keyring)
    2. Environment variable
    3. None
    """
    # Try keyring (Windows Credential Manager) first
    try:
        import keyring

        value = keyring.get_password(VAULT_SERVICE, key)
        if value:
            logger.debug("Loaded %s from Windows Credential Manager", key)
            return value
    except Exception:
        pass

    # Fall back to environment variable
    value = os.environ.get(key)
    if value:
        logger.debug("Loaded %s from environment variable", key)
        return value

    return None


def require_secret(key: str) -> str:
    """Get a secret or raise if not found anywhere."""
    value = get_secret(key)
    if not value:
        raise EnvironmentError(
            f"{key} not found. Set it via:\n"
            f'  python -c "import keyring; keyring.set_password(\'{VAULT_SERVICE}\', \'{key}\', \'YOUR_KEY\')"\n'
            f"  or set the {key} environment variable."
        )
    return value
