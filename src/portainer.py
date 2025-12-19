"""
Portainer integration module.
"""

import requests
import sys

class PortainerClient:
    """
    Client for interacting with Portainer webhooks.
    """
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def trigger_webhook(self):
        """
        Trigger the Portainer webhook.
        Raises Exception if the request fails.
        """
        if not self.webhook_url:
            return

        # verify=False is used because Portainer often uses self-signed certs
        requests.post(self.webhook_url, timeout=10, verify=False)
