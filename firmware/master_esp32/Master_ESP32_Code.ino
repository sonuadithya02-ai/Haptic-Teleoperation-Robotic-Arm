#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_ADS1115 ads;
Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver(0x40);

// ---------------- PINS ----------------
#define TOUCH_PIN 12
#define GRIP_PIN  14

// ---------------- STATES ----------------
bool blocked = false;
bool lastTouchState = HIGH;

// ---------------- STRUCT ----------------
struct Ranges {
  long in_min, in_max, out_min, out_max;
};

// ----------- CALIBRATED RANGES ----------
const Ranges r_step = {902, 2657, 130, 0};
const Ranges r_s0   = {119, 1194, 115, 520};
const Ranges r_s1   = {-2, 1130, 75, 520};
const Ranges r_s2   = {-1, 1193, 75, 520};
const Ranges r_s3   = {3134, 0, 200, 520};

// ----------- SERVO PULSES ---------------
int blocked_pulses[4]   = {315, 160, 320, 325};
int unblocked_pulses[4] = {420, 280, 400, 230};

// ----------- LAST VALUES ----------------
long last_step = 0;
long last_s0 = 250, last_s1 = 250, last_s2 = 250, last_s3 = 250;

// ---------------- HELPERS ----------------
long mapSafe(long x, const Ranges &r) {
  if (r.in_min < r.in_max) {
    x = constrain(x, r.in_min, r.in_max);
  } else {
    x = constrain(x, r.in_max, r.in_min);
  }

  float t = float(x - r.in_min) / float(r.in_max - r.in_min);
  return r.out_min + t * (r.out_max - r.out_min);
}

long readSafeADS(int ch, long lastValue, const Ranges &r) {
  long raw = ads.readADC_SingleEnded(ch);

  // allow small tolerance to avoid edge noise
  const int margin = 30;

  bool valid;
  if (r.in_min < r.in_max) {
    valid = (raw >= r.in_min - margin && raw <= r.in_max + margin);
  } else {
    valid = (raw >= r.in_max - margin && raw <= r.in_min + margin);
  }

  if (!valid) {
    return lastValue;   // 🔒 HOLD LAST VALUE
  }

  return mapSafe(raw, r);
}

long readSafeAnalog(int pin, long lastValue, const Ranges &r) {
  long raw = analogRead(pin);

  const int margin = 30;
  bool valid;
  if (r.in_min < r.in_max) {
    valid = (raw >= r.in_min - margin && raw <= r.in_max + margin);
  } else {
    valid = (raw >= r.in_max - margin && raw <= r.in_min + margin);
  }

  if (!valid) {
    return lastValue;
  }

  return mapSafe(raw, r);
}


// ---------------- SERIAL RX ----------------
void handleIncoming() {
  if (!Serial.available()) return;

  String msg = Serial.readStringUntil('\n');
  msg.trim();

  if (msg == "BLOCK") {
    blocked = true;

    // Move feedback servos immediately
    for (int i = 0; i < 4; i++) {
      pca.setPWM(i, 0, blocked_pulses[i]);
    }
  }
}

// ---------------- SETUP ----------------
void setup() {
  Serial.begin(115200);
  Wire.begin();

  ads.begin();
  pca.begin();
  pca.setPWMFreq(50);

  pinMode(TOUCH_PIN, INPUT_PULLUP);
}

// ---------------- LOOP ----------------
void loop() {
  handleIncoming();

  bool touchNow = digitalRead(TOUCH_PIN);

  // -------- UNBLOCK EDGE DETECT --------
  if (blocked && lastTouchState == HIGH && touchNow == LOW) {
    blocked = false;
    Serial.println("UNBLOCK");

    for (int i = 0; i < 4; i++) {
      pca.setPWM(i, 0, unblocked_pulses[i]);
    }
  }

  lastTouchState = touchNow;

  // -------- BLOCKED STATE (FREEZE) ------
if (blocked) {
  Serial.print("P,");
  Serial.print(last_step); Serial.print(",");
  Serial.print(last_s0);   Serial.print(",");
  Serial.print(last_s1);   Serial.print(",");
  Serial.print(last_s2);   Serial.print(",");
  Serial.println(last_s3);
  delay(25);
  return;
}

  // -------- NORMAL OPERATION ------------
  long a0 = ads.readADC_SingleEnded(0);
  long a1 = ads.readADC_SingleEnded(1);
  long a2 = ads.readADC_SingleEnded(2);
  long a3 = ads.readADC_SingleEnded(3);
  long grip = analogRead(GRIP_PIN);

last_step = readSafeADS(0, last_step, r_step);
last_s0   = readSafeADS(1, last_s0,   r_s0);
last_s1   = readSafeADS(2, last_s1,   r_s1);
last_s2   = readSafeADS(3, last_s2,   r_s2);
last_s3   = readSafeAnalog(GRIP_PIN, last_s3, r_s3);


  Serial.print("P,");
  Serial.print(last_step); Serial.print(",");
  Serial.print(last_s0); Serial.print(",");
  Serial.print(last_s1); Serial.print(",");
  Serial.print(last_s2); Serial.print(",");
  Serial.println(last_s3);

  delay(25);
}
