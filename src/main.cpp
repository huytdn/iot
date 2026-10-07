#include <WiFi.h>
#include <PubSubClient.h>
#include <DHTesp.h>

const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

// ==============================
// MQTT - BÀI 2
// ==============================
const char* MQTT_SERVER = "172.18.15.153";
const int MQTT_PORT = 1883;

const char* MQTT_TOPIC = "iot/lab01/room01/sensor";

// ==============================
// SENSOR PINS
// ==============================
const int DHT_PIN = 15;
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;
const int LED_PIN = 2;

// Gửi dữ liệu mỗi 5 giây
const unsigned long SEND_INTERVAL_MS = 5000;

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
DHTesp dht;

unsigned long lastSend = 0;
unsigned long sequenceNo = 0;


// ==============================
// WIFI
// ==============================
void connectWiFi() {

  Serial.println();
  Serial.println("==============================");
  Serial.println("BAT DAU KET NOI WIFI");
  Serial.println("==============================");

  WiFi.mode(WIFI_STA);

  WiFi.begin(
    WIFI_SSID,
    WIFI_PASSWORD,
    6
  );

  Serial.print("Connecting WiFi");

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connected!");

  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  Serial.print("RSSI: ");
  Serial.println(WiFi.RSSI());
}


// ==============================
// MQTT
// ==============================
void connectMQTT() {

  while (!mqttClient.connected()) {

    Serial.println();
    Serial.print("Connecting MQTT to ");
    Serial.print(MQTT_SERVER);
    Serial.print(":");
    Serial.println(MQTT_PORT);

    String clientId =
      "ESP32-Bai2-" +
      String((uint32_t)ESP.getEfuseMac(), HEX);

    // Mosquitto đang allow_anonymous=true
    // nên KHÔNG cần TOKEN
    if (mqttClient.connect(clientId.c_str())) {

      Serial.println("MQTT connected!");

    } else {

      Serial.print("MQTT FAILED, rc = ");
      Serial.println(mqttClient.state());

      Serial.println("Retry in 2 seconds...");

      delay(2000);
    }
  }
}


// ==============================
// HC-SR04
// ==============================
float readDistanceCm() {

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);

  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration =
    pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0) {

    Serial.println("HC-SR04: TIMEOUT");

    return NAN;
  }

  float distance =
    duration * 0.0343f / 2.0f;

  Serial.print("HC-SR04 raw distance: ");
  Serial.print(distance);
  Serial.println(" cm");

  if (distance < 2.0f || distance > 400.0f) {

    Serial.println("HC-SR04: OUT OF RANGE");

    return NAN;
  }

  return distance;
}


// ==============================
// SETUP
// ==============================
void setup() {

  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("=================================");
  Serial.println("ESP32 START");
  Serial.println("WOKWI + MOSQUITTO + INFLUXDB");
  Serial.println("=================================");

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);

  digitalWrite(LED_PIN, LOW);

  dht.setup(
    DHT_PIN,
    DHTesp::DHT22
  );

  Serial.println("DHT22 initialized");

  connectWiFi();

  mqttClient.setServer(
    MQTT_SERVER,
    MQTT_PORT
  );

  mqttClient.setBufferSize(256);

  Serial.println("Setup completed!");
}


// ==============================
// LOOP
// ==============================
void loop() {

  // Kiểm tra WiFi
  if (WiFi.status() != WL_CONNECTED) {

    Serial.println("WiFi disconnected!");

    connectWiFi();
  }

  // Kiểm tra MQTT
  if (!mqttClient.connected()) {

    connectMQTT();
  }

  mqttClient.loop();

  unsigned long now = millis();

  // Chưa đến thời gian gửi
  if (now - lastSend < SEND_INTERVAL_MS) {

    return;
  }

  lastSend = now;


  // ============================
  // READ SENSOR
  // ============================

  TempAndHumidity data =
    dht.getTempAndHumidity();

  float distance =
    readDistanceCm();


  // Kiểm tra dữ liệu
  if (!isfinite(data.temperature) ||
      !isfinite(data.humidity) ||
      !isfinite(distance)) {

    Serial.println(
      "Invalid sensor data - skip publish"
    );

    return;
  }


  // Tăng sequence
  sequenceNo++;


  // ============================
  // CREATE JSON
  // ============================

  char payload[256];

  snprintf(
    payload,
    sizeof(payload),

    "{"
    "\"device_id\":\"esp32-bai1\","
    "\"temperature\":%.2f,"
    "\"humidity\":%.2f,"
    "\"distance_cm\":%.2f,"
    "\"rssi\":%d,"
    "\"sequence\":%lu,"
    "\"uptime_s\":%lu"
    "}",

    data.temperature,
    data.humidity,
    distance,
    WiFi.RSSI(),
    sequenceNo,
    millis() / 1000
  );


  // ============================
  // PUBLISH MQTT
  // ============================

  bool ok =
    mqttClient.publish(
      MQTT_TOPIC,
      payload
    );


  // ============================
  // SERIAL LOG
  // ============================

  Serial.println();
  Serial.println("------------------------------");

  Serial.print("Temperature : ");
  Serial.print(data.temperature);
  Serial.println(" C");

  Serial.print("Humidity    : ");
  Serial.print(data.humidity);
  Serial.println(" %");

  Serial.print("Distance    : ");
  Serial.print(distance);
  Serial.println(" cm");

  Serial.print("RSSI        : ");
  Serial.println(WiFi.RSSI());

  Serial.print("Sequence    : ");
  Serial.println(sequenceNo);

  Serial.print("Uptime      : ");
  Serial.print(millis() / 1000);
  Serial.println(" s");

  Serial.print("Topic       : ");
  Serial.println(MQTT_TOPIC);

  Serial.print("JSON        : ");
  Serial.println(payload);

  Serial.print("Publish     : ");

  if (ok) {

    Serial.println("OK");

  } else {

    Serial.println("FAILED");
  }

  Serial.println("------------------------------");


  // Nháy LED nếu publish thành công
  if (ok) {

    digitalWrite(LED_PIN, HIGH);

    delay(80);

    digitalWrite(LED_PIN, LOW);
  }
}