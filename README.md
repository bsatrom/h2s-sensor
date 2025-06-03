# H₂S Sensor Monitor with Blues Wireless Notecard

A MicroPython application for monitoring hydrogen sulfide (H₂S) gas levels using a Raspberry Pi Pico and Blues Wireless Notecard for cellular IoT connectivity.

## Features

- **Continuous H₂S Monitoring**: Reads analog voltage from H₂S gas sensor and converts to PPM
- **Low Power Operation**: Uses deep sleep mode and reduced CPU frequency for battery efficiency
- **Cellular Connectivity**: Sends data via Blues Wireless Notecard for remote monitoring
- **Offline Buffering**: Stores readings locally when cellular connection is unavailable
- **Error Recovery**: Implements watchdog timer and retry logic for robust operation
- **Sensor Warmup**: Automatic 30-second warmup period for accurate readings

## Hardware Requirements

- Raspberry Pi Pico (or Pico W)
- H₂S Gas Sensor with analog voltage output (0-3.3V)
- Blues Wireless Notecard
- I2C connection cables
- Power supply (battery recommended for field deployment)

## Pin Connections

| Component | Pico Pin | Description |
|-----------|----------|-------------|
| H₂S Sensor Output | GP26 (ADC0) | Analog voltage signal |
| Notecard SDA | GP16 | I2C data line |
| Notecard SCL | GP17 | I2C clock line |
| Notecard GND | GND | Common ground |
| Notecard VIO | 3V3 | 3.3V power |

## Installation

1. **Install MicroPython** on your Raspberry Pi Pico:
   - Download the latest MicroPython UF2 file from [micropython.org](https://micropython.org/download/rp2-pico/)
   - Hold BOOTSEL button while connecting Pico to USB
   - Copy UF2 file to the RPI-RP2 drive

2. **Install Dependencies**:
   ```bash
   # Copy the notecard library to your Pico
   # The lib/notecard/ directory should be copied to the Pico's filesystem
   ```

3. **Configure the Application**:
   - Update `PRODUCT_UID` in `src/code.py` with your Blues Wireless ProductUID
   - Adjust sensor calibration if needed (see Configuration section)

4. **Deploy the Code**:
   - Copy `src/code.py` to the root of your Pico as `main.py`
   - The application will start automatically on power-up

## Configuration

Key parameters in `src/code.py`:

```python
# Measurement Settings
SAMPLE_DURATION = 20          # Seconds to average readings
SAMPLE_INTERVAL = 0.5         # Seconds between samples
READ_INTERVAL = 300           # Seconds between measurements (5 min)

# Sensor Calibration
# Linear mapping: 0V = 0ppm, 3.3V = 100ppm
# Modify convert_voltage_to_ppm() function for your sensor

# Cellular Sync
NOTECARD_OUTBOUND_INTERVAL = 1440  # Minutes (24 hours)
NOTECARD_INBOUND_INTERVAL = 1440   # Minutes (24 hours)

# Power & Reliability
SENSOR_WARMUP_TIME = 30       # Sensor warmup seconds
WATCHDOG_TIMEOUT = 8000       # Watchdog timeout ms
MAX_BUFFER_SIZE = 100         # Max offline readings
```

## Data Format

The application sends JSON data to the Notecard:

```json
{
  "voltage": 1.234,      // Sensor voltage (V)
  "h2s_ppm": 37.39,     // H₂S concentration (PPM)
  "buffered": true,      // If sent from buffer
  "original_time": 123456789  // Unix timestamp (buffered only)
}
```

## Operation

1. **Power On**: Device performs 30-second sensor warmup (LED blinks)
2. **Measurement Cycle**:
   - Takes readings for 20 seconds (40 samples)
   - Calculates average voltage
   - Converts to H₂S PPM
   - Sends to Notecard or buffers locally
   - Enters deep sleep for ~4.5 minutes
3. **Error Handling**:
   - Watchdog timer resets device if frozen
   - Failed readings are buffered locally
   - Buffered data sent when connection restored

## Troubleshooting

### No Readings
- Check sensor power and connections
- Verify ADC pin configuration
- Ensure sensor has completed warmup

### Notecard Communication Issues
- Verify I2C connections (SDA/SCL)
- Check Notecard power supply
- Confirm ProductUID is correct
- Review Notecard debug output

### Inaccurate Readings
- Calibrate sensor for your specific H₂S sensor model
- Ensure adequate sensor warmup time
- Check for stable power supply
- Verify sensor voltage range matches code expectations

## Power Consumption

- Active: ~50mA @ 48MHz (during measurement)
- Deep Sleep: <1mA (between measurements)
- Average: ~2-3mA (with 5-minute intervals)

## License

This project is provided as-is for educational and development purposes.

## Support

For Blues Wireless Notecard support: https://blues.io/support/
For sensor-specific questions, consult your H₂S sensor manufacturer's documentation.