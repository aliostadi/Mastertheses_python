import requests
import psycopg2
import csv
import io
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
from ..config.settings import DB_URL, API_KEY, START_TS, END_TS
class ParkingOperationsLoader:
    def __init__(self, db_url, api_key):
        self.db_url = db_url
        self.api_key = api_key

    def _connect(self):
        return psycopg2.connect(self.db_url)

    def fetch_csv(self, start_ts, end_ts):
        body = {
            "query_filter": {"start": start_ts, "end": end_ts},
            "merge_resets": True,
            "additional_columns": [],
            "time_zone_delta_minutes": 0
        }

        headers = {
            "accept": "application/json",
            "X-Api-Key": self.api_key,
            "X-Auth-Token": self.api_key,
            "X-Two-Factor-Token": self.api_key,
            "Content-Type": "application/json"
        }

        url = "https://api.parking-pilot.com/analysis/parking-operations/csv"
        res = requests.post(url, json=body, headers=headers)

        if res.status_code != 200:
            raise RuntimeError(f"API Error: {res.text}")

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
    loader = ParkingOperationsLoader(DB_URL, API_KEY)
    loader.run(START_TS, END_TS)


if __name__ == "__main__":
    main()
