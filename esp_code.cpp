
#include <ESP32Servo.h>
#include <WiFi.h>

// ===== WiFi Credentials =====
const char* ssid     = "AAAA";      
const char* password = "shivam.s";  

// ===== TCP Server Settings =====
WiFiServer server(1234);   
WiFiClient client;

// ===== PINS =====
const int colorServoPin = 13;
const int hopperServoPin = 12;

Servo colorServo;
Servo hopperServo;

// ===== HOPPER ANGLES =====
const int HOPPER_LOAD    = 60;    
const int HOPPER_DETECT  = 90;    
const int HOPPER_UNLOAD  = 120;   
// ===== COLOR MAPPING =====
struct ColorAngle {
  char color;
  int angle;
};

ColorAngle colorMap[] = {
  {'P', 0},
  {'O', 35},
  {'Y', 85},
  {'G', 135}
};
const int numColors = 4;

// ===== TIMING  =====
const unsigned long LOAD_DELAY      = 3000;
const unsigned long DETECT_SETTLE   = 4000;
const unsigned long SLIDE_MOVE_TIME = 500;
const unsigned long UNLOAD_DELAY    = 500;
const unsigned long COLOR_TIMEOUT   = 3000;

// ===== STATE MACHINE =====
enum State {
  STATE_LOAD_WAIT,
  STATE_MOVE_TO_DETECT,
  STATE_DETECT_WAIT_COLOR,
  STATE_MOVE_SLIDE,
  STATE_WAIT_SLIDE_DONE,
  STATE_UNLOAD,
  STATE_RETURN_TO_LOAD
};

State state = STATE_LOAD_WAIT;
unsigned long stateStartTime = 0;

int targetAngle = -1;
char latestCommand = '\0';

void setup() {
  Serial.begin(9600);  
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);

  colorServo.attach(colorServoPin, 500, 2400);
  hopperServo.attach(hopperServoPin, 500, 2400);

  colorServo.write(90);
  hopperServo.write(HOPPER_LOAD);

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // Start TCP server
  server.begin();
  Serial.println("TCP server started on port 1234");
  Serial.println("Waiting for client...");

  stateStartTime = millis();
}

void loop() {
  // Handle client connection
  if (!client.connected()) {
    client = server.available();
    if (client) {
      Serial.println("Client connected");
    }
  }

  // Read data from WiFi client (same as reading serial)
  if (client.connected() && client.available()) {
    char c = client.read();
    if (c != '?') {
      latestCommand = c;
      Serial.print("Received over WiFi: ");
      Serial.println(c);
    }
  }

  unsigned long now = millis();

  switch (state) {
    case STATE_LOAD_WAIT:
      if (now - stateStartTime >= LOAD_DELAY) {
        Serial.println("Moving hopper to DETECT...");
        hopperServo.write(HOPPER_DETECT);
        state = STATE_MOVE_TO_DETECT;
        stateStartTime = now;
      }
      break;

    case STATE_MOVE_TO_DETECT:
      if (now - stateStartTime >= DETECT_SETTLE) {
        Serial.println("Hopper at DETECT – waiting for color command...");
        state = STATE_DETECT_WAIT_COLOR;
        stateStartTime = now;
      }
      break;

    case STATE_DETECT_WAIT_COLOR:
      if (latestCommand != '\0') {
        targetAngle = -1;
        for (int i = 0; i < numColors; i++) {
          if (latestCommand == colorMap[i].color) {
            targetAngle = colorMap[i].angle;
            break;
          }
        }
        if (targetAngle != -1) {
          Serial.print("Color received: ");
          Serial.print(latestCommand);
          Serial.print(" → moving slide to ");
          Serial.println(targetAngle);
          colorServo.write(targetAngle);
          state = STATE_MOVE_SLIDE;
          stateStartTime = now;
          latestCommand = '\0';
        } else {
          latestCommand = '\0';
        }
      }
      else if (now - stateStartTime >= COLOR_TIMEOUT) {
        Serial.println("No color received – returning to LOAD without unloading.");
        hopperServo.write(HOPPER_LOAD);
        state = STATE_RETURN_TO_LOAD;
        stateStartTime = now;
      }
      break;

    case STATE_MOVE_SLIDE:
      if (now - stateStartTime >= SLIDE_MOVE_TIME) {
        Serial.println("Slide ready – now unloading ball...");
        hopperServo.write(HOPPER_UNLOAD);
        state = STATE_UNLOAD;
        stateStartTime = now;
      }
      break;

    case STATE_UNLOAD:
      if (now - stateStartTime >= UNLOAD_DELAY) {
        Serial.println("Unload done – returning hopper to LOAD.");
        hopperServo.write(HOPPER_LOAD);
        state = STATE_RETURN_TO_LOAD;
        stateStartTime = now;
      }
      break;

    case STATE_RETURN_TO_LOAD:
      Serial.println("Cycle complete. Ready for next ball.\n");
      targetAngle = -1;
      state = STATE_LOAD_WAIT;
      stateStartTime = now;
      break;
  }
}
