#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <utility/imumaths.h>

#define BUTTON_PIN 26
uint16_t SAMPLE_DELAY = 15;

Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28, &Wire);

bool recording = false;

/* Motion accumulation in WORLD frame */
float sumX = 0;
float sumY = 0;
float sumZ = 0;

float maxX = -1000, minX = 1000;
float maxY = -1000, minY = 1000;
float maxZ = -1000, minZ = 1000;

unsigned long startTime;

void setup()
{
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLDOWN);

  while (!Serial) delay(10);

  Serial.println("Wand Gesture System");

  if(!bno.begin())
  {
    Serial.println("BNO055 not detected!");
    while(1);
  }

  delay(1000);
  startTime = millis();  // store startup time
}

void loop()
{
  bool buttonPressed = digitalRead(BUTTON_PIN) == HIGH;

  sensors_event_t accelData;
  bno.getEvent(&accelData, Adafruit_BNO055::VECTOR_LINEARACCEL);

  /* Orientation quaternion */
  imu::Quaternion quat = bno.getQuat();

  /* Body-frame acceleration */
  imu::Vector<3> accel(
    accelData.acceleration.x,
    accelData.acceleration.y,
    accelData.acceleration.z
  );

  /* Rotate into world frame */
  imu::Vector<3> worldAccel = quat.rotateVector(accel);

  float ax = worldAccel.x();
  float ay = worldAccel.y();
  float az = worldAccel.z();

  if(buttonPressed)
  {
    if(!recording)
    {
      recording = true;

      sumX = sumY = sumZ = 0;
      maxX = maxY = maxZ = -1000;
      minX = minY = minZ = 1000;
    }

    sumX += ax;
    sumY += ay;
    sumZ += az;

    if(ax > maxX) maxX = ax;
    if(ax < minX) minX = ax;

    if(ay > maxY) maxY = ay;
    if(ay < minY) minY = ay;

    if(az > maxZ) maxZ = az;
    if(az < minZ) minZ = az;
  }
  else
  {
    if(recording)
    {
      recording = false;

      float motionX = maxX - minX;
      float motionY = maxY - minY;
      float motionZ = maxZ - minZ;

      /* Determine dominant motion axis */

      unsigned long currentTime = millis();
      unsigned long elapsedTime = currentTime - startTime;
      Serial.print(elapstedTime);
      if(motionZ > motionX)
      {
        if(sumZ > 0)
          Serial.println(",UP");
        else
          Serial.println(",DOWN");
      }
      else
      {
        if(sumX > 0)
          Serial.println(",RIGHT");
        else
          Serial.println(",LEFT");
      }
      uint8_t sys, gyro, accel, mag;
      bno.getCalibration(&sys, &gyro, &accel, &mag);

    }
  }

  delay(SAMPLE_DELAY);
}
