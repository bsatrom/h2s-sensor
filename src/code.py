import machine
import time
import json
from notecard import Notecard

# === CONFIGURATION ===
ADC_PIN = 26                      # GP26 / ADC0
I2C_SDA_PIN = 20                  # Connect to Notecard SDA
I2C_SCL_PIN = 21                  # Connect to Notecard SCL
NOTECARD_I2C_ADDRESS = 0x17
SAMPLE_DURATION = 20              # in seconds
SAMPLE_INTERVAL = 0.5             # in seconds
READ_INTERVAL = 300               # in seconds (5 minutes)
PRODUCT_UID = "com.your-company.your-product"  # Replace with your ProductUID

NOTECARD_OUTBOUND_INTERVAL = 1440 # in minutes (24 hours = 1440 minutes)
NOTECARD_INBOUND_INTERVAL = 1440  # in minutes (24 hours = 1440 minutes)

# === POWER SAVING ===
machine.freq(48000000)            # Lower CPU frequency for battery life

# === SETUP ===
led = machine.Pin(25, machine.Pin.OUT)
led.value(0)                      # Turn off onboard LED

i2c = machine.I2C(0,
                 scl=machine.Pin(I2C_SCL_PIN),
                 sda=machine.Pin(I2C_SDA_PIN),
                 freq=100_000)

adc = machine.ADC(machine.Pin(ADC_PIN))

# === INITIALIZE NOTECARD ===
card = Notecard(i2c, 0, debug=True)

# === NOTECARD INITIALIZATION ===
def notecard_init():
  card.Transaction({
    "req": "hub.set",
    "product": "com.your-company.your-product",  # Replace with your ProductUID
    "mode": "periodic",
    "outbound": NOTECARD_OUTBOUND_INTERVAL,
    "inbound": NOTECARD_INBOUND_INTERVAL,
    "align": True
  })


# === TEMPLATE SETUP ===
def template_setup():
  card.Transaction({
    "req": "template.add",
    "file": "h2s.qo",
    "body": {
      "voltage": 0.0,
      "h2s_ppm": 0.0
    }
  })


# === SENSOR LOGIC ===
def read_average_voltage():
    readings = []
    start = time.time()
    while time.time() - start < SAMPLE_DURATION:
        raw = adc.read_u16()
        voltage = (raw / 65535.0) * 3.3
        readings.append(voltage)
        time.sleep(SAMPLE_INTERVAL)
    return sum(readings) / len(readings)


def convert_voltage_to_ppm(voltage):
    # Linear mapping: 0V = 0ppm, 3.3V = 100ppm
    ppm = (voltage / 3.3) * 100
    return round(ppm, 2)


def send_to_notecard(voltage, ppm):
  card.Transaction({
    "req": "note.add",
    "file": "h2s.qo",
    "body": {
      "voltage": round(voltage, 3),
      "h2s_ppm": ppm
    }
  })
  print(f"Sent -> Voltage: {voltage:.3f} V | H₂S: {ppm:.2f} ppm")


# === MAIN LOOP ===
notecard_init()
template_setup()

while True:
    print("Waking up. Sampling sensor...")
    avg_voltage = read_average_voltage()
    h2s_ppm = convert_voltage_to_ppm(avg_voltage)
    print("Voltage:", avg_voltage, "V | H₂S:", h2s_ppm, "ppm")

    send_to_notecard(avg_voltage, h2s_ppm)

    print("Sleeping for", READ_INTERVAL - SAMPLE_DURATION, "seconds...\n")
    time.sleep(READ_INTERVAL - SAMPLE_DURATION)