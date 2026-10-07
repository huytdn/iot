import json
import os

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


# =========================================================
# LOAD ENV
# =========================================================

load_dotenv()


# =========================================================
# MQTT CONFIG
# =========================================================

MQTT_BROKER = os.getenv(
    "MQTT_BROKER",
    "localhost"
)

MQTT_PORT = int(
    os.getenv(
        "MQTT_PORT",
        "1883"
    )
)

MQTT_TOPIC = os.getenv(
    "MQTT_TOPIC",
    "iot/lab01/room01/sensor"
)


# Chỉ nhận dữ liệu từ ESP32 Bài 1
ALLOWED_DEVICE_ID = "esp32-bai1"


# =========================================================
# INFLUXDB CONFIG
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
        "INFLUX_TOKEN chưa được cấu hình trong .env"
    )


# =========================================================
# INFLUXDB CLIENT
# =========================================================

influx_client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG
)

write_api = influx_client.write_api(
    write_options=SYNCHRONOUS
)


# =========================================================
# VALIDATE DATA
# =========================================================

def validate_data(data):

    required_fields = [
        "device_id",
        "temperature",
        "humidity",
        "distance_cm",
        "rssi",
        "sequence",
        "uptime_s"
    ]

    # -----------------------------------------------------
    # Kiểm tra field bắt buộc
    # -----------------------------------------------------

    for field in required_fields:

        if field not in data:

            print(
                f"[REJECT] Missing field: {field}"
            )

            return False


    # -----------------------------------------------------
    # Chỉ nhận ESP32 Bài 1
    # -----------------------------------------------------

    if data["device_id"] != ALLOWED_DEVICE_ID:

        print(
            f"[REJECT] Unknown device: "
            f"{data['device_id']}"
        )

        return False


    # -----------------------------------------------------
    # Convert kiểu dữ liệu
    # -----------------------------------------------------

    try:

        temperature = float(
            data["temperature"]
        )

        humidity = float(
            data["humidity"]
        )

        distance = float(
            data["distance_cm"]
        )

        rssi = int(
            data["rssi"]
        )

        sequence = int(
            data["sequence"]
        )

        uptime = float(
            data["uptime_s"]
        )

    except (
        ValueError,
        TypeError
    ):

        print(
            "[REJECT] Invalid numeric value"
        )

        return False


    # -----------------------------------------------------
    # Kiểm tra range
    # -----------------------------------------------------

    if not -40 <= temperature <= 85:

        print(
            "[REJECT] Invalid temperature"
        )

        return False


    if not 0 <= humidity <= 100:

        print(
            "[REJECT] Invalid humidity"
        )

        return False


    if not 2 <= distance <= 400:

        print(
            "[REJECT] Invalid distance_cm"
        )

        return False


    if sequence < 0:

        print(
            "[REJECT] Invalid sequence"
        )

        return False


    if uptime < 0:

        print(
            "[REJECT] Invalid uptime_s"
        )

        return False


    return True


# =========================================================
# MQTT CONNECT
# =========================================================

def on_connect(
    client,
    userdata,
    flags,
    rc
):

    if rc == 0:

        print("[MQTT] Connected")

        client.subscribe(
            MQTT_TOPIC
        )

        print(
            f"[MQTT] Subscribed: {MQTT_TOPIC}"
        )

        print(
            f"[MQTT] Allowed device: "
            f"{ALLOWED_DEVICE_ID}"
        )

    else:

        print(
            f"[MQTT] Connection failed: {rc}"
        )


# =========================================================
# MQTT MESSAGE
# =========================================================

def on_message(
    client,
    userdata,
    msg
):

    # -----------------------------------------------------
    # Decode JSON
    # -----------------------------------------------------

    try:

        data = json.loads(
            msg.payload.decode()
        )

    except json.JSONDecodeError:

        print("[REJECT] Invalid JSON")

        return


    print(
        f"[MQTT] Received: {data}"
    )


    # -----------------------------------------------------
    # Validate
    # -----------------------------------------------------

    if not validate_data(data):

        return


    # -----------------------------------------------------
    # Save to InfluxDB
    # -----------------------------------------------------

    try:

        point = (
            Point("sensor_raw")

            .tag(
                "device_id",
                data["device_id"]
            )

            .tag(
                "location",
                "room01"
            )

            .field(
                "temperature",
                float(data["temperature"])
            )

            .field(
                "humidity",
                float(data["humidity"])
            )

            .field(
                "distance_cm",
                float(data["distance_cm"])
            )

            .field(
                "rssi",
                int(data["rssi"])
            )

            .field(
                "sequence",
                int(data["sequence"])
            )

            .field(
                "uptime_s",
                float(data["uptime_s"])
            )
        )


        write_api.write(
            bucket=INFLUX_BUCKET,
            org=INFLUX_ORG,
            record=point
        )


        print("[INFLUXDB] Saved")


    except Exception as e:

        print(
            f"[INFLUXDB] Error: {e}"
        )


# =========================================================
# MQTT CLIENT
# =========================================================

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message


# =========================================================
# START
# =========================================================

print(
    f"Connecting MQTT: "
    f"{MQTT_BROKER}:{MQTT_PORT}"
)

client.connect(
    MQTT_BROKER,
    MQTT_PORT,
    60
)

client.loop_forever()