import os

import pandas as pd
import streamlit as st

from dotenv import load_dotenv
from influxdb_client import InfluxDBClient


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


# =========================================================
# STREAMLIT CONFIG
# =========================================================

st.set_page_config(
    page_title="IoT Sensor Dashboard",
    page_icon="📡",
    layout="wide"
)


st.title(
    "📡 IoT Sensor Monitoring Dashboard"
)

st.write(
    "ESP32 Bài 1 → MQTT → InfluxDB"
)


# =========================================================
# CHECK TOKEN
# =========================================================

if not INFLUX_TOKEN:

    st.error(
        "INFLUX_TOKEN chưa được cấu hình "
        "trong file .env"
    )

    st.stop()


# =========================================================
# INFLUXDB CLIENT
# =========================================================

@st.cache_resource
def get_influx_client():

    return InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG
    )


client = get_influx_client()

query_api = client.query_api()


# =========================================================
# QUERY RAW DATA
# =========================================================

query = f'''
from(bucket: "{INFLUX_BUCKET}")
    |> range(start: -1h)
    |> filter(fn: (r) =>
        r["_measurement"] == "sensor_raw"
    )
    |> filter(fn: (r) =>
        r["device_id"] == "esp32-bai1"
    )
    |> pivot(
        rowKey: ["_time"],
        columnKey: ["_field"],
        valueColumn: "_value"
    )
'''


try:

    tables = query_api.query_data_frame(
        query=query,
        org=INFLUX_ORG
    )

except Exception as e:

    st.error(
        f"Lỗi khi đọc InfluxDB: {e}"
    )

    st.stop()


# =========================================================
# DATAFRAME
# =========================================================

if isinstance(tables, list):

    if len(tables) == 0:

        st.warning(
            "Chưa có dữ liệu sensor_raw."
        )

        st.stop()

    df = pd.concat(
        tables,
        ignore_index=True
    )

else:

    df = tables


if df.empty:

    st.warning(
        "Chưa có dữ liệu ESP32 Bài 1."
    )

    st.stop()


# =========================================================
# CLEAN
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


# =========================================================
# LATEST DATA
# =========================================================

latest = df.iloc[-1]


temperature = latest.get(
    "temperature",
    None
)

humidity = latest.get(
    "humidity",
    None
)

distance = latest.get(
    "distance_cm",
    None
)

rssi = latest.get(
    "rssi",
    None
)


# =========================================================
# CURRENT VALUES
# =========================================================

st.subheader(
    "📊 Current Sensor Values"
)


col1, col2, col3, col4 = st.columns(4)


with col1:

    if pd.notna(temperature):

        st.metric(
            "🌡️ Temperature",
            f"{temperature:.2f} °C"
        )

    else:

        st.metric(
            "🌡️ Temperature",
            "N/A"
        )


with col2:

    if pd.notna(humidity):

        st.metric(
            "💧 Humidity",
            f"{humidity:.2f} %"
        )

    else:

        st.metric(
            "💧 Humidity",
            "N/A"
        )


with col3:

    if pd.notna(distance):

        st.metric(
            "📏 Distance",
            f"{distance:.2f} cm"
        )

    else:

        st.metric(
            "📏 Distance",
            "N/A"
        )


with col4:

    if pd.notna(rssi):

        st.metric(
            "📶 Wi-Fi RSSI",
            f"{rssi:.0f} dBm"
        )

    else:

        st.metric(
            "📶 Wi-Fi RSSI",
            "N/A"
        )


# =========================================================
# RAW CHART
# =========================================================

st.subheader(
    "📈 Raw Sensor Data"
)


chart_columns = [
    "temperature",
    "humidity",
    "distance_cm",
    "rssi"
]


available_columns = [
    column
    for column in chart_columns
    if column in df.columns
]


if available_columns:

    chart_df = df.set_index(
        "_time"
    )

    st.line_chart(
        chart_df[available_columns]
    )


# =========================================================
# PROCESSED DATA
# =========================================================

st.subheader(
    "🧹 Processed Sensor Data"
)


processed_query = f'''
from(bucket: "{INFLUX_BUCKET}")
    |> range(start: -1h)
    |> filter(fn: (r) =>
        r["_measurement"] == "sensor_processed"
    )
    |> filter(fn: (r) =>
        r["device_id"] == "esp32-bai1"
    )
    |> pivot(
        rowKey: ["_time"],
        columnKey: ["_field"],
        valueColumn: "_value"
    )
'''


try:

    processed_tables = query_api.query_data_frame(
        query=processed_query,
        org=INFLUX_ORG
    )

    if isinstance(
        processed_tables,
        list
    ):

        if len(processed_tables) > 0:

            processed_df = pd.concat(
                processed_tables,
                ignore_index=True
            )

        else:

            processed_df = pd.DataFrame()

    else:

        processed_df = processed_tables


except Exception:

    processed_df = pd.DataFrame()


if not processed_df.empty:

    processed_df["_time"] = pd.to_datetime(
        processed_df["_time"]
    )

    processed_df = processed_df.sort_values(
        "_time"
    )

    processed_columns = [
        "temperature_rolling",
        "humidity_rolling",
        "distance_rolling",
        "rssi_rolling"
    ]

    available_processed = [
        column
        for column in processed_columns
        if column in processed_df.columns
    ]

    if available_processed:

        processed_chart = (
            processed_df
            .set_index("_time")
        )

        st.line_chart(
            processed_chart[
                available_processed
            ]
        )

else:

    st.info(
        "Chưa có sensor_processed. "
        "Hãy chạy preprocess.py."
    )


# =========================================================
# RAW TABLE
# =========================================================

st.subheader(
    "📋 Latest Raw Data"
)


display_columns = [
    "_time",
    "device_id",
    "temperature",
    "humidity",
    "distance_cm",
    "rssi",
    "sequence",
    "uptime_s"
]


available_display_columns = [
    column
    for column in display_columns
    if column in df.columns
]


st.dataframe(
    df[
        available_display_columns
    ].tail(20),
    use_container_width=True
)


# =========================================================
# REFRESH
# =========================================================

if st.button("🔄 Refresh"):

    st.rerun()