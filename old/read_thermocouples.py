import time
import board
import busio
import digitalio
import adafruit_max31856

# Define SPI bus
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

# Define chip select pins as DigitalInOut objects
cs_pins = [digitalio.DigitalInOut(board.CE0), digitalio.DigitalInOut(board.CE1)]

# Initialize MAX31856 thermocouple sensors
sensors = [adafruit_max31856.MAX31856(spi, cs) for cs in cs_pins]

print("Reading temperatures from thermocouples...")
while True:
    for i, sensor in enumerate(sensors):
        try:
            temp = sensor.temperature
            print(f"Thermocouple {i+1}: {temp:.2f}°C")
        except Exception as e:
            print(f"Error reading sensor {i+1}: {e}")
    time.sleep(2)
