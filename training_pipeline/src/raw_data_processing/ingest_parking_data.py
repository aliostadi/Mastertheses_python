import requests
import psycopg2
import csv
import io
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
from ..config.settings import DB_URL, PARKING_API_USERNAME, PARKING_API_PASSWORD, START_TS, END_TS
from ..utils.parking_api_client import ParkingAPIClient
class ParkingOperationsLoader:
    def __init__(self, db_url, api_username, api_password):
        self.db_url = db_url
        self.api_username = api_username
        self.api_password = api_password
        self.api_token = None

    def _connect(self):
        return psycopg2.connect(self.db_url)

    def _get_api_token(self):
        """Get API token using credentials"""
        if self.api_token:
            return self.api_token
        
        print(f"[DEBUG] Authenticating with API...")
        print(f"[DEBUG] Username: {self.api_username}")
        
        client = ParkingAPIClient(self.api_username, self.api_password)
        token = client.get_token()
        
        if not token:
            print(f"[ERROR] Failed to authenticate with Parking Pilot API")
            print(f"[ERROR] Please check credentials in src/config/settings.py")
            raise RuntimeError("Failed to authenticate with Parking Pilot API")
        
        print(f"[DEBUG] Got token: {token[:20]}...")
        self.api_token = token
        return token

    def fetch_csv(self, start_ts, end_ts):
        # Get token dynamically
        token = self._get_api_token()
        
        print(f"[FETCH] Using token: {token[:20]}..." if token else "[FETCH] No token!")
        
        body = {
            "query_filter": {"start": start_ts, "end": end_ts},
            "merge_resets": True,
            "additional_columns": [],
            "time_zone_delta_minutes": 0
        }

        # Use X-Auth-Token header (works for this API)
        headers = {
            "accept": "application/json",
            "X-Auth-Token": token,
            "Content-Type": "application/json"
        }
        
        print(f"[FETCH] Using X-Auth-Token header")

        url = "https://api.parking-pilot.com/analysis/parking-operations/csv"
        print(f"[FETCH] POST to: {url}")
        res = requests.post(url, json=body, headers=headers)

        print(f"[FETCH] Response status: {res.status_code}")
        
        if res.status_code != 200:
            print(f"[FETCH] Error response: {res.text}")
            raise RuntimeError(f"API Error: {res.status_code} - {res.text}")

        return res.text

    def create_table(self, suffix):
        query = f"""
        CREATE TABLE IF NOT EXISTS ali_parking_operations_{suffix} (
            parking_lot_id INT NOT NULL,
            parking_space_id INT NOT NULL,
            arrival_unix_seconds BIGINT NOT NULL,
            departure_unix_seconds BIGINT NOT NULL,
            arrival_unix_seconds_humanreadable TIMESTAMPTZ NOT NULL,
            departure_unix_seconds_humanreadable TIMESTAMPTZ NOT NULL,
            xml_id INT NOT NULL,
            PRIMARY KEY(parking_lot_id, parking_space_id, arrival_unix_seconds)
        );
        """

        conn = self._connect()
        cur = conn.cursor()
        cur.execute(query)
        conn.commit()
        cur.close()
        conn.close()

    def insert_csv_rows(self, csv_text, suffix):
        conn = self._connect()
        cur = conn.cursor()

        reader = csv.reader(io.StringIO(csv_text), delimiter=";")
        next(reader, None)

        insert_sql = f"""
        INSERT INTO ali_parking_operations_{suffix} (
            parking_lot_id, parking_space_id, arrival_unix_seconds, departure_unix_seconds,
            arrival_unix_seconds_humanreadable, departure_unix_seconds_humanreadable, xml_id
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING;
        """

        batch = []
        for row in reader:
            if len(row) < 5:
                continue

            lot_id, space_id = int(row[0]), int(row[1])
            arr, dep = int(row[2]), int(row[3])
            if arr >= dep:
                continue

            batch.append((
                lot_id, space_id, arr, dep,
                datetime.utcfromtimestamp(arr),
                datetime.utcfromtimestamp(dep),
                int(row[4])
            ))

            if len(batch) > 1000:
                cur.executemany(insert_sql, batch)
                batch.clear()

        if batch:
            cur.executemany(insert_sql, batch)

        conn.commit()
        cur.close()
        conn.close()

    def run(self, start_ts, end_ts):
        suffix = datetime.now(timezone.utc).strftime("%Y_%m_%d")
        print("Fetching data…")
        csv_data = self.fetch_csv(start_ts, end_ts)
        print("Creating table…")
        self.create_table(suffix)
        print("Inserting rows…")
        self.insert_csv_rows(csv_data, suffix)
        print("Done.")




def main():
    loader = ParkingOperationsLoader(DB_URL, PARKING_API_USERNAME, PARKING_API_PASSWORD)
    loader.run(START_TS, END_TS)


if __name__ == "__main__":
    main()
