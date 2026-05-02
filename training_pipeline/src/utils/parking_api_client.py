"""
Parking Pilot API Authentication Client
Handles only authentication - returns token for use by other modules
"""

import requests
import logging

logger = logging.getLogger(__name__)


class ParkingAPIClient:
    """Simple client for Parking Pilot API authentication only"""
    
    def __init__(self, username, password, api_base_url="https://api.parking-pilot.com"):
        """
        Initialize API client
        
        Args:
            username: Parking Pilot API username (e.g., "FutureIOT_MOBI")
            password: Parking Pilot API password
            api_base_url: Base URL of the API
        """
        self.username = username
        self.password = password
        self.api_base_url = api_base_url
        self.token = None
        
    def get_token(self):
        """
        Authenticate with API and get token
        
        Makes POST request to https://api.parking-pilot.com/auth?remember=false
        with username/password, extracts and returns token
        
        Returns:
            str: Token if successful, None otherwise
        """
        try:
            auth_url = f"{self.api_base_url}/auth?remember=false"
            
            print(f"[AUTH] Requesting token from: {auth_url}")
            
            # Send credentials as JSON
            response = requests.post(
                auth_url,
                json={
                    "username": self.username,
                    "password": self.password
                },
                timeout=10
            )
            
            print(f"[AUTH] Response status: {response.status_code}")
            
            if response.status_code == 200:
                # Response format: { "token": "e31d4df211aa7451c959b6372f6f755b" }
                data = response.json()
                self.token = data.get('token')
                
                if self.token:
                    print(f"[AUTH] ✅ Got token: {self.token[:20]}...")
                    return self.token
                else:
                    print(f"[AUTH] ❌ No token in response: {data}")
                    return None
            else:
                print(f"[AUTH] ❌ Auth failed {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"[AUTH] ❌ Error: {str(e)}")
            return None


# Example usage:
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Get token with credentials
    client = ParkingAPIClient(
        username="FutureIOT_MOBI",
        password="Mob!2018"
    )
    
    token = client.get_token()
    if token:
        print(f"\n✅ Got token: {token}\n")
        print("Now use this token in data ingestion phase:")
        print(f"  headers = {{'Authorization': 'Bearer {token}'}}")

