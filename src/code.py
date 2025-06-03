import machine
import time
import json
import gc
import notecard

# === CONFIGURATION ===
ADC_PIN = 26                      # GP26 / ADC0
I2C_SDA_PIN = 16                  # Connect to Notecard SDA
I2C_SCL_PIN = 17                  # Connect to Notecard SCL
NOTECARD_I2C_ADDRESS = 0x17
SAMPLE_DURATION = 20              # in seconds
SAMPLE_INTERVAL = 0.5             # in seconds
READ_INTERVAL = 300               # in seconds (5 minutes)
PRODUCT_UID = "com.blues.h2s_sensor"  # Replace with your ProductUID

NOTECARD_OUTBOUND_INTERVAL = 1440 # in minutes (24 hours = 1440 minutes)
NOTECARD_INBOUND_INTERVAL = 1440  # in minutes (24 hours = 1440 minutes)

SENSOR_WARMUP_TIME = 30           # Sensor warmup time in seconds
MAX_RETRIES = 3                   # Max retries for failed operations
BUFFER_FILE = "sensor_buffer.txt" # Local buffer file
MAX_BUFFER_SIZE = 100             # Max buffered readings
WATCHDOG_TIMEOUT = 8000           # Watchdog timeout in ms

# === POWER SAVING ===
machine.freq(48000000)            # Lower CPU frequency for battery life

# === SETUP ===
led = machine.Pin(25, machine.Pin.OUT)
led.value(0)                      # Turn off onboard LED

# Initialize watchdog timer
wdt = machine.WDT(timeout=WATCHDOG_TIMEOUT)

# Initialize I2C with error handling
try:
    i2c = machine.I2C(0,
                     scl=machine.Pin(I2C_SCL_PIN),
                     sda=machine.Pin(I2C_SDA_PIN),
                     freq=100_000)
except Exception as e:
    print(f"Failed to initialize I2C: {e}")
    machine.reset()

adc = machine.ADC(machine.Pin(ADC_PIN))

# === INITIALIZE NOTECARD ===
card = None
for retry in range(MAX_RETRIES):
    try:
        card = notecard.OpenI2C(i2c, 0, 0, debug=True)
        break
    except Exception as e:
        print(f"Failed to initialize Notecard (attempt {retry + 1}): {e}")
        time.sleep(2)
        if retry == MAX_RETRIES - 1:
            print("Notecard initialization failed. Running in offline mode.")
            card = None

# === LOCAL BUFFER MANAGEMENT ===
def save_to_buffer(voltage, ppm):
    try:
        with open(BUFFER_FILE, 'a') as f:
            timestamp = time.time()
            f.write(f"{timestamp},{voltage},{ppm}\n")
    except Exception as e:
        print(f"Failed to save to buffer: {e}")

def load_and_clear_buffer():
    readings = []
    try:
        with open(BUFFER_FILE, 'r') as f:
            lines = f.readlines()
            for line in lines[-MAX_BUFFER_SIZE:]:  # Keep only last MAX_BUFFER_SIZE readings
                parts = line.strip().split(',')
                if len(parts) == 3:
                    readings.append({
                        'timestamp': float(parts[0]),
                        'voltage': float(parts[1]),
                        'ppm': float(parts[2])
                    })
        # Clear the buffer file
        with open(BUFFER_FILE, 'w') as f:
            f.write('')
    except Exception as e:
        print(f"Failed to load buffer: {e}")
    return readings

# === NOTECARD INITIALIZATION ===
def notecard_init():
    if card is None:
        return False
    try:
        card.Transaction({
            "req": "hub.set",
            "product": PRODUCT_UID,
            "mode": "periodic",
            "outbound": NOTECARD_OUTBOUND_INTERVAL,
            "inbound": NOTECARD_INBOUND_INTERVAL,
            "align": True
        })
        return True
    except Exception as e:
        print(f"Failed to initialize Notecard hub: {e}")
        return False


# === TEMPLATE SETUP ===
def template_setup():
    if card is None:
        return False
    try:
        card.Transaction({
            "req": "note.template",
            "file": "h2s.qo",
            "body": {
                "voltage": 14.1,
                "h2s_ppm": 14.1
            }
        })
        return True
    except Exception as e:
        print(f"Failed to setup template: {e}")
        return False


# === SENSOR LOGIC ===
def read_average_voltage():
    readings = []
    start = time.time()
    while time.time() - start < SAMPLE_DURATION:
        try:
            wdt.feed()  # Feed watchdog during long sampling
            raw = adc.read_u16()
            voltage = (raw / 65535.0) * 3.3
            readings.append(voltage)
            time.sleep(SAMPLE_INTERVAL)
        except Exception as e:
            print(f"ADC read error: {e}")
            continue

    if not readings:
        raise Exception("No valid ADC readings obtained")

    return sum(readings) / len(readings)


def convert_voltage_to_ppm(voltage):
    # Linear mapping: 0V = 0ppm, 3.3V = 100ppm
    ppm = (voltage / 3.3) * 100
    return round(ppm, 2)


def send_to_notecard(voltage, ppm):
    if card is None:
        print("Notecard not available, saving to buffer")
        save_to_buffer(voltage, ppm)
        return False

    try:
        card.Transaction({
            "req": "note.add",
            "file": "h2s.qo",
            "body": {
                "voltage": round(voltage, 3),
                "h2s_ppm": ppm
            }
        })
        print(f"Sent -> Voltage: {voltage:.3f} V | H₂S: {ppm:.2f} ppm")

        # Try to send buffered readings
        send_buffered_readings()
        return True
    except Exception as e:
        print(f"Failed to send to Notecard: {e}")
        save_to_buffer(voltage, ppm)
        return False

def send_buffered_readings():
    if card is None:
        return

    buffered = load_and_clear_buffer()
    if not buffered:
        return

    print(f"Sending {len(buffered)} buffered readings...")
    for reading in buffered:
        try:
            card.Transaction({
                "req": "note.add",
                "file": "h2s.qo",
                "body": {
                    "voltage": round(reading['voltage'], 3),
                    "h2s_ppm": reading['ppm'],
                    "buffered": True,
                    "original_time": reading['timestamp']
                }
            })
            time.sleep(0.1)  # Small delay between sends
        except Exception as e:
            print(f"Failed to send buffered reading: {e}")
            save_to_buffer(reading['voltage'], reading['ppm'])
            break


# === SENSOR WARMUP ===
def sensor_warmup():
    print(f"Warming up sensor for {SENSOR_WARMUP_TIME} seconds...")
    start_time = time.time()
    while time.time() - start_time < SENSOR_WARMUP_TIME:
        wdt.feed()
        led.value(int(time.time() * 2) % 2)  # Blink LED during warmup
        time.sleep(0.5)
    led.value(0)  # Turn off LED
    print("Sensor warmup complete")

# === POWER MANAGEMENT ===
def enter_deep_sleep(duration_ms):
    print(f"Entering sleep for {duration_ms/1000} seconds...")
    wdt.feed()
    gc.collect()

    # Note: Raspberry Pi Pico doesn't support true deep sleep with RTC wake
    # Using lightsleep instead for lower power consumption
    machine.lightsleep(duration_ms)

# === MAIN LOOP ===
# Perform sensor warmup on boot
sensor_warmup()

# Initialize Notecard if available
if card:
    notecard_init()
    template_setup()

# Main measurement loop
while True:
    try:
        wdt.feed()
        print("Waking up. Sampling sensor...")

        avg_voltage = read_average_voltage()
        h2s_ppm = convert_voltage_to_ppm(avg_voltage)
        print("Voltage:", avg_voltage, "V | H₂S:", h2s_ppm, "ppm")

        send_to_notecard(avg_voltage, h2s_ppm)

        # Calculate sleep duration
        sleep_duration = READ_INTERVAL - SAMPLE_DURATION
        print(f"Sleeping for {sleep_duration} seconds...\n")

        # Use deep sleep for power saving
        enter_deep_sleep(sleep_duration * 1000)

    except Exception as e:
        print(f"Error in main loop: {e}")
        time.sleep(5)  # Brief pause before retry
        continue
