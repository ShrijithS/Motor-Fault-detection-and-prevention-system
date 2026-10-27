#include <Servo.h>
#include <SoftwareSerial.h>

// ---------- HC-05 ----------
SoftwareSerial BT(2, 3);   // Arduino RX, TX
// HC-05 TX -> D2
// HC-05 RX -> D3 through 1k/2k voltage divider

// ---------- Ultrasonic sensors ----------
const int TRIG1 = 4;
const int ECHO1 = 7;

const int TRIG2 = 8;
const int ECHO2 = 9;






























































































































































































































const int MOISTURE = A0;
const int SERVO_PIN = A1;
const int BUZZER = A2;
const int WET_LED = A3;
const int DRY_LED = 5;

Servo flapServo;

// ---------- Distance function ----------
long getDistance(int trigPin, int echoPin)
{
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);

  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);

  if (duration == 0)
    return -1;

  return duration * 0.0343 / 2;
}

// ---------- Servo test ----------
void testServo()
{
  Serial.println("Testing Servo...");

  flapServo.write(0);
  delay(700);

  flapServo.write(90);
  delay(700);

  flapServo.write(180);
  delay(700);

  flapServo.write(90);
  delay(700);

  Serial.println("Servo test complete.");
}

// ---------- LED test ----------
void testLEDs()
{
  Serial.println("Testing LEDs...");

  digitalWrite(WET_LED, HIGH);
  digitalWrite(DRY_LED, LOW);
  delay(500);

  digitalWrite(WET_LED, LOW);
  digitalWrite(DRY_LED, HIGH);
  delay(500);

  digitalWrite(WET_LED, HIGH);
  digitalWrite(DRY_LED, HIGH);
  delay(500);

  digitalWrite(WET_LED, LOW);
  digitalWrite(DRY_LED, LOW);

  Serial.println("LED test complete.");
}

// ---------- Buzzer test ----------
void testBuzzer()
{
  Serial.println("Testing Buzzer...");

  tone(BUZZER, 1000);
  delay(300);
  noTone(BUZZER);

  Serial.println("Buzzer test complete.");
}

// ---------- Setup ----------
void setup()
{
  Serial.begin(9600);
  BT.begin(9600);

  // Ultrasonic pins
  pinMode(TRIG1, OUTPUT);
  pinMode(ECHO1, INPUT);

  pinMode(TRIG2, OUTPUT);
  pinMode(ECHO2, INPUT);


+


































































-+-
-*******inMode(TRIG3, OUTPUT);
  pinMode(ECHO3, INPUT);

  // Other components
  pinMode(BUZZER, OUTPUT);
  pinMode(WET_LED, OUTPUT);
  pinMode(DRY_LED, OUTPUT);

  flapServo.attach(SERVO_PIN);
  flapServo.write(90);

  digitalWrite(WET_LED, LOW);
  digitalWrite(DRY_LED, LOW);

  Serial.println("--------------------------------");
  Serial.println("SMART DUSTBIN TEST PROGRAM");
  Serial.println("--------------------------------");
  Serial.println("Commands:");
  Serial.println("s = Servo test");
  Serial.println("b = Buzzer test");
  Serial.println("l = LED test");
  Serial.println("--------------------------------");

  BT.println("Smart Dustbin Test Ready");
}

// ---------- Main loop ----------
void loop()
{
  // Read ultrasonic sensors
  long frontDistance = getDistance(TRIG1, ECHO1);
  delay(50);

  long wetDistance = getDistance(TRIG2, ECHO2);
  delay(50);

  long dryDistance = getDistance(TRIG3, ECHO3);

  // Read moisture
  int moistureValue = analogRead(MOISTURE);

  // Display readings
  Serial.print("Front: ");
  Serial.print(frontDistance);
  Serial.print(" cm | Wet bin: ");
  Serial.print(wetDistance);
  Serial.print(" cm | Dry bin: ");
  Serial.print(dryDistance);
  Serial.print(" cm | Moisture: ");
  Serial.println(moistureValue);

  // Send readings to HC-05
  BT.print("Front: ");
  BT.print(frontDistance);
  BT.print(" | Wet: ");
  BT.print(wetDistance);
  BT.print(" | Dry: ");
  BT.print(dryDistance);
  BT.print(" | Moisture: ");
  BT.println(moistureValue);

  // Simple moisture LED test
  // Adjust threshold after checking your actual sensor values
  if (moistureValue < 500)
  {
    digitalWrite(WET_LED, HIGH);
    digitalWrite(DRY_LED, LOW);
  }
  else
  {
    digitalWrite(WET_LED, LOW);
    digitalWrite(DRY_LED, HIGH);
  }

  // Check Serial Monitor commands
  if (Serial.available())
  {
    char command = Serial.read();

    if (command == 's')
    {
      testServo();
    }

    else if (command == 'b')
    {
      testBuzzer();
    }

    else if (command == 'l')
    {
      testLEDs();
    }
  }

  // Check Bluetooth commands
  if (BT.available())
  {
    char command = BT.read();

    if (command == 's')
    {
      testServo();
      BT.println("Servo test complete");
    }

    else if (command == 'b')
    {
      testBuzzer();
      BT.println("Buzzer test complete");
    }

    else if (command == 'l')
    {
      testLEDs();
      BT.println("LED test complete");
    }
  }

  delay(500);
}