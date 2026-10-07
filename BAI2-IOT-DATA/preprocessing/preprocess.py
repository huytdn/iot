import os

import numpy as np
import pandas as pd

from dotenv import load_dotenv
from sklearn.preprocessing import StandardScaler

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


# =========================================================
# LOAD ENV
# =========================================================

load_dotenv()


# =========================================================
# CONFIG
# =========================================================

INFLUX_URL = os.getenv(
    "INFLUX_URL",
    "http://localhost:8086"
)

INFLUX_TOKEN = os.getenv(
    "INFLUX_TOKEN"
)

INFLUX_ORG = os.getenv(
    "INFLUX_ORG",
    "iot-lab"
)

INFLUX_BUCKET = os.getenv(
    "INFLUX_BUCKET",
    "sensor-data"
)


if not INFLUX_TOKEN:
    raise RuntimeError(
        "INFLUX_TOKEN chưa được cấu hình"
    )


# =========================================================
# INFLUXDB
# =========================================================

client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG
)

query_api = client.query_api()

write_api = client.write_api(
    write_options=SYNCHRONOUS
)


# =========================================================
# 1. READ SENSOR_RAW
# =========================================================

print("[1] Reading sensor_raw...")


query = f'''
from(bucket: "{INFLUX_BUCKET}")
    |> range(start: -1h)
    |> filter(fn: (r) =>
        r["_measurement"] == "sensor_raw"
    )
    |> filter(fn: (r) =>
        r["_field"] == "temperature"
        or r["_field"] == "humidity"
        or r["_field"] == "distance_cm"
        or r["_field"] == "rssi"
    )
    |> pivot(
        rowKey: ["_time"],
        columnKey: ["_field"],
        valueColumn: "_value"
    )
'''


tables = query_api.query_data_frame(
    query=query,
    org=INFLUX_ORG
)


if isinstance(tables, list):

    if len(tables) == 0:

        print("Không có dữ liệu.")

        client.close()

        exit()

    df = pd.concat(
        tables,
        ignore_index=True
    )

else:

    df = tables


if df.empty:

    print("Không có dữ liệu.")

    client.close()

    exit()


# =========================================================
# 2. CLEAN DATAFRAME
# =========================================================

df = df.drop(
    columns=[
        "_start",
        "_stop",
        "result",
        "table"
    ],
    errors="ignore"
)


df["_time"] = pd.to_datetime(
    df["_time"]
)


df = df.sort_values(
    "_time"
)


df = df.set_index(
    "_time"
)


# Chỉ giữ sensor thật
sensor_columns = [
    "temperature",
    "humidity",
    "distance_cm",
    "rssi"
]


for column in sensor_columns:

    if column not in df.columns:

        df[column] = np.nan


df = df[sensor_columns]


print(
    f"Loaded {len(df)} records"
)


# =========================================================
# 3. MISSING VALUES
# =========================================================

print("[2] Handling missing values...")


df[sensor_columns] = (
    df[sensor_columns]
    .interpolate(method="linear")
    .ffill()
    .bfill()
)


# =========================================================
# 4. IQR OUTLIER
# =========================================================

print("[3] Detecting IQR outliers...")


def remove_iqr_outliers(
    dataframe,
    column
):

    Q1 = dataframe[column].quantile(0.25)

    Q3 = dataframe[column].quantile(0.75)

    IQR = Q3 - Q1

    lower = Q1 - 1.5 * IQR

    upper = Q3 + 1.5 * IQR

    mask = (
        (dataframe[column] >= lower)
        &
        (dataframe[column] <= upper)
    )

    return dataframe[mask]


before_outlier = len(df)


for column in sensor_columns:

    if df[column].nunique() > 1:

        df = remove_iqr_outliers(
            df,
            column
        )


after_outlier = len(df)


print(
    f"Removed "
    f"{before_outlier - after_outlier} "
    f"outlier records"
)


# =========================================================
# 5. RESAMPLING
# =========================================================

print("[4] Resampling to 10 seconds...")


df = (
    df
    .resample("10s")
    .mean()
)


# =========================================================
# 6. ROLLING MEAN
# =========================================================

print("[5] Calculating rolling mean...")


df["temperature_rolling"] = (
    df["temperature"]
    .rolling(window=3)
    .mean()
)


df["humidity_rolling"] = (
    df["humidity"]
    .rolling(window=3)
    .mean()
)


df["distance_rolling"] = (
    df["distance_cm"]
    .rolling(window=3)
    .mean()
)


df["rssi_rolling"] = (
    df["rssi"]
    .rolling(window=3)
    .mean()
)


# =========================================================
# 7. DELTA
# =========================================================

print("[6] Calculating delta...")


df["temperature_delta"] = (
    df["temperature"]
    .diff()
)


df["humidity_delta"] = (
    df["humidity"]
    .diff()
)


df["distance_delta"] = (
    df["distance_cm"]
    .diff()
)


df["rssi_delta"] = (
    df["rssi"]
    .diff()
)


# =========================================================
# 8. STANDARDIZATION
# =========================================================

print("[7] Standardizing data...")


scaler_columns = [
    "temperature",
    "humidity",
    "distance_cm",
    "rssi"
]


# Xóa dòng NaN trước khi scale
df = df.dropna(
    subset=scaler_columns
)


scaler = StandardScaler()


scaled_values = scaler.fit_transform(
    df[scaler_columns]
)


df["temperature_scaled"] = (
    scaled_values[:, 0]
)

df["humidity_scaled"] = (
    scaled_values[:, 1]
)

df["distance_scaled"] = (
    scaled_values[:, 2]
)

df["rssi_scaled"] = (
    scaled_values[:, 3]
)


# =========================================================
# 9. REMOVE NaN
# =========================================================

df = df.dropna()


# =========================================================
# 10. SAVE SENSOR_PROCESSED
# =========================================================

print("[8] Saving sensor_processed...")


for timestamp, row in df.iterrows():

    point = (
        Point("sensor_processed")

        .tag(
            "device_id",
            "esp32-bai1"
        )

        .tag(
            "location",
            "room01"
        )

        # Raw values
        .field(
            "temperature",
            float(row["temperature"])
        )

        .field(
            "humidity",
            float(row["humidity"])
        )

        .field(
            "distance_cm",
            float(row["distance_cm"])
        )

        .field(
            "rssi",
            float(row["rssi"])
        )

        # Rolling mean
        .field(
            "temperature_rolling",
            float(row["temperature_rolling"])
        )

        .field(
            "humidity_rolling",
            float(row["humidity_rolling"])
        )

        .field(
            "distance_rolling",
            float(row["distance_rolling"])
        )

        .field(
            "rssi_rolling",
            float(row["rssi_rolling"])
        )

        # Delta
        .field(
            "temperature_delta",
            float(row["temperature_delta"])
        )

        .field(
            "humidity_delta",
            float(row["humidity_delta"])
        )

        .field(
            "distance_delta",
            float(row["distance_delta"])
        )

        .field(
            "rssi_delta",
            float(row["rssi_delta"])
        )

        # Standardized
        .field(
            "temperature_scaled",
            float(row["temperature_scaled"])
        )

        .field(
            "humidity_scaled",
            float(row["humidity_scaled"])
        )

        .field(
            "distance_scaled",
            float(row["distance_scaled"])
        )

        .field(
            "rssi_scaled",
            float(row["rssi_scaled"])
        )
    )


    write_api.write(
        bucket=INFLUX_BUCKET,
        org=INFLUX_ORG,
        record=point
    )


print(
    f"[DONE] Saved {len(df)} processed records"
)


# =========================================================
# CLOSE
# =========================================================

client.close()

print("Preprocessing completed.")