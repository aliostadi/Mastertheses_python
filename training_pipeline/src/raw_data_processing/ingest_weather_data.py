import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from ..config.settings import DB_URL , start_date_weather, end_date_weather

class WeatherLoader:
    def __init__(self, db_url, lat=49.891, lon=10.887):
        self.db_url = db_url
        self.lat = lat
        self.lon = lon

    def _connect(self):
        return psycopg2.connect(self.db_url)

    def create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS ali_weather_bamberg_hourly (
            timestamp TIMESTAMPTZ PRIMARY KEY,
            temperature_2m DOUBLE PRECISION,
            relative_humidity_2m DOUBLE PRECISION,
            precipitation DOUBLE PRECISION
        );
        """

        conn = self._connect()
        cur = conn.cursor()
        cur.execute(query)
        conn.commit()
        cur.close()
        conn.close()

    def fetch_historical(self, start_date, end_date):
        url = (
            "https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={self.lat}"
            f"&longitude={self.lon}"
            f"&start_date={start_date}"
            f"&end_date={end_date}"
            "&hourly=temperature_2m,relative_humidity_2m,precipitation"
        )

        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        df = pd.DataFrame({
            "timestamp": data["hourly"]["time"],
            "temperature_2m": data["hourly"]["temperature_2m"],
            "relative_humidity_2m": data["hourly"]["relative_humidity_2m"],
            "precipitation": data["hourly"]["precipitation"]
        })

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def insert(self, df):
        conn = self._connect()
        cur = conn.cursor()

        sql = """
        INSERT INTO ali_weather_bamberg_hourly (
            timestamp, temperature_2m, relative_humidity_2m, precipitation
        ) VALUES (%s, %s, %s, %s)
        ON CONFLICT (timestamp) DO NOTHING;
        """

        batch = [
            (
                row.timestamp.to_pydatetime(),
                float(row.temperature_2m),
                float(row.relative_humidity_2m),
                float(row.precipitation)
            )
            for row in df.itertuples(index=False)
        ]

        execute_batch(cur, sql, batch, page_size=500)
        conn.commit()
        cur.close()
        conn.close()

    def run(self, start_date, end_date):
        print("Creating table if not exists...")
        self.create_table()

        print("Fetching historical weather...")
        df = self.fetch_historical(start_date, end_date)

        print(f"Inserting {len(df)} rows...")
        self.insert(df)

        print("Done.")



def main():
    loader = WeatherLoader(DB_URL)
    loader.run(start_date_weather, end_date_weather)
if __name__ == "__main__":
    main()