// ================= SLAVE_ESP32 (FINAL – SIGNAL-ONLY FSR) =================

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver(0x40);

// ---------------- Pins ----------------
#define FSR_PIN   34
#define STEP_PIN  2    // PUL+
#define DIR_PIN   5    // DIR+

// ---------------- FSR CONFIG ----------------
#define FSR_THRESHOLD       100
#define FSR_CONFIRM_COUNT   5
#define FSR_SAMPLE_DELAY    10
#define UNBLOCK_IGNORE_MS   2000

// ---------------- State ----------------
enum State { NORMAL, BLOCKED, IGNORE_FSR };
State state = NORMAL;

unsigned long ignoreUntil = 0;
int fsrHitCount = 0;

// ---------------- Stepper ----------------
long lastP = 0;
bool firstPacket = true;
const float STEPS_PER_DEG = 480.0;
const float DEG_PER_INDEX = 1.0;

// ---------------- Servo Smoothing ----------------
float s0_f = 0, s1_f = 0, s2_f = 0, s3_f = 0;
float alpha_fast = 0.35;
float alpha_slow = 0.12;

int smoothServo(float &state, int target) {
  state += alpha_fast * (target - state);
  state += alpha_slow * (target - state);
  return (int)state;
}

// ---------------- UART Packet ----------------
void processPacket(String s) {

  // -------- UNBLOCK --------
  if (s == "UNBLOCK") {
    state = IGNORE_FSR;
    ignoreUntil = millis() + UNBLOCK_IGNORE_MS;
    fsrHitCount = 0;
    Serial.println("UNBLOCK_ACK");
    return;
  }

  // -------- P,x,x,x,x,x --------
  if (!s.startsWith("P,")) return;

  int v[5];
  int idx = 0;
  int start = 2;

  while (idx < 5) {
    int comma = s.indexOf(",", start);
    if (comma == -1) {
      v[idx++] = s.substring(start).toInt();
      break;
    }
    v[idx++] = s.substring(start, comma).toInt();
    start = comma + 1;
  }

long currentP = v[0];

if (firstPacket) {
  lastP = currentP;

  // Initialize smoothing states to first real values
  s0_f = v[1];
  s1_f = v[2];
  s2_f = v[3];
  s3_f = v[4];

  // Apply directly once (NO smoothing)
  pca.setPWM(0, 0, v[1]);
  pca.setPWM(1, 0, v[2]);
  pca.setPWM(2, 0, v[3]);
  pca.setPWM(3, 0, v[4]);

  firstPacket = false;
  return;
}

long delta = currentP - lastP;

if (delta != 0) {
  digitalWrite(DIR_PIN, delta > 0 ? HIGH : LOW);

  long steps = abs(delta) * DEG_PER_INDEX * STEPS_PER_DEG;
  for (long i = 0; i < steps; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(80);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(80);
  }
}

lastP = currentP;


  pca.setPWM(0, 0, smoothServo(s0_f, v[1]));
  pca.setPWM(1, 0, smoothServo(s1_f, v[2]));
  pca.setPWM(2, 0, smoothServo(s2_f, v[3]));
  pca.setPWM(3, 0, smoothServo(s3_f, v[4]));
}

// ---------------- Setup ----------------
void setup() {
  Serial.begin(115200);

  pinMode(FSR_PIN, INPUT);
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);

  Wire.begin();
  pca.begin();
  pca.setPWMFreq(50);

  // ---- SERVO SAFE START ----
int SAFE_SERVO = 350;   // adjust if needed

for (int i = 0; i < 4; i++) {
  pca.setPWM(i, 0, SAFE_SERVO);
}
// --------------------------

  digitalWrite(STEP_PIN, LOW);
  digitalWrite(DIR_PIN, LOW);
}

// ---------------- Loop ----------------
void loop() {

  // ---------- UART ----------
  if (Serial.available()) {
    String s = Serial.readStringUntil('\n');
    s.trim();
    if (s.length()) processPacket(s);
  }

  // ---------- FSR (SIGNAL ONLY) ----------
int fsr = analogRead(FSR_PIN);

// Ignore window after UNBLOCK
if (state == IGNORE_FSR) {
  if (millis() > ignoreUntil) {
    state = NORMAL;
    fsrHitCount = 0;
  }
  return;
}

// Fully blocked until UNBLOCK arrives
if (state == BLOCKED) {
  return;
}

// Normal detection
if (fsr > FSR_THRESHOLD) {
  fsrHitCount++;
  if (fsrHitCount >= FSR_CONFIRM_COUNT) {
    Serial.println("BLOCK");
    state = BLOCKED;
    fsrHitCount = 0;
  }
} else {
  fsrHitCount = 0;
}

  delay(FSR_SAMPLE_DELAY);
}
