import network
import utime
import microcoapy
from coap_macros import COAP_METHOD
from machine import Pin, ADC
from dht import DHT22
from hcsr04 import HCSR04
import uasyncio as asyncio
import cbor
import json

# Pin Definitions
class PinConfig:
    DHT_PIN = 21
    LIGHT_SENSOR_PIN = 34
    LED1_PIN = 13  # Red
    LED2_PIN = 12  # Yellow
    LED3_PIN = 27  # Green
    TRIG_PIN = 32
    ECHO_PIN = 15
    BUTTON_PIN = 32
    MAX_BIN_HEIGHT = 100  # cm
    LIGHT_THRESHOLD = 250

class NetworkConfig:
    WIFI_SSID = "Galaxy A06 0a23"
    WIFI_PASSWORD = "12345678"
    
# Network Configuration
class SensorManager:
    def __init__(self):
        # Initialize sensors
        self.dht_sensor = DHT22(Pin(PinConfig.DHT_PIN))
        self.light_sensor = ADC(Pin(PinConfig.LIGHT_SENSOR_PIN))
        self.light_sensor.atten(ADC.ATTN_11DB)
        self.ultrasonic_sensor = HCSR04(trigger_pin=PinConfig.TRIG_PIN, echo_pin=PinConfig.ECHO_PIN)
        
        # Initialize LEDs
        self.led1 = Pin(PinConfig.LED1_PIN, Pin.OUT)  # Red LED
        self.led2 = Pin(PinConfig.LED2_PIN, Pin.OUT)  # Yellow LED
        self.led3 = Pin(PinConfig.LED3_PIN, Pin.OUT)  # Green LED
        
        # Initialize Button (Connected Between GND and GPIO 32)
        self.button = Pin(PinConfig.BUTTON_PIN, Pin.IN, Pin.PULL_UP)  # Use internal pull-up resistor
        
        # LED states
        self.led_states = {
            "redLed": False,
            "yellowLed": False,
            "greenLed": False
        }
        self.last_data = None

        # Set up the button interrupt
        self.setup_button_interrupt()

    def get_light_level(self):
        return self.light_sensor.read()

    def update_led_states(self, new_states):
        """Update LED states and physical LED outputs"""
        self.led_states = new_states
        self.led1.value(new_states["redLed"])
        self.led2.value(new_states["yellowLed"])
        self.led3.value(new_states["greenLed"])

    def toggle_red_led(self):
        """Toggle the state of the red LED"""
        self.led_states["redLed"] = not self.led_states["redLed"]
        self.update_led_states(self.led_states)

    def handle_button_press(self, pin):
        """Interrupt Service Routine (ISR) for Button Press"""
        self.toggle_red_led()

    def setup_button_interrupt(self):
        """Set up the button to trigger on a falling edge (button press)"""
        self.button.irq(trigger=Pin.IRQ_FALLING, handler=self.handle_button_press)

    def get_distance(self):
        """Get distance measurement and calculate fill percentage"""
        try:
            distance = self.ultrasonic_sensor.distance_cm()
            if distance is not None and distance <= PinConfig.MAX_BIN_HEIGHT:
                fill_percentage = ((PinConfig.MAX_BIN_HEIGHT - distance) / PinConfig.MAX_BIN_HEIGHT) * 100
                return round(fill_percentage, 2)
            return None
        except OSError as e:
            print("Ultrasonic sensor error:", str(e))
            return None

    def get_sensor_data(self):
        """Get data from all sensors"""
        try:
            self.dht_sensor.measure()
            temperature = self.dht_sensor.temperature()
            humidity = self.dht_sensor.humidity()
            light_level = self.light_sensor.read()
            bin_level = self.get_distance()

            current_time = utime.localtime()
            timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                current_time[0], current_time[1], current_time[2],
                current_time[3], current_time[4], current_time[5]
            )

            data = {
                "timestamp": timestamp,
                "temperature": temperature,
                "humidity": humidity,
                "lightLevel": light_level,
                "binLevel": bin_level,
                "ledStates": self.led_states  # Include LED states in sensor data
            }
            self.last_data = data
            return data
        except Exception as e:
            print("Error reading sensors:", str(e))
            return None

# CORECONF Management Endpoints
class CoreconfManager:
    def __init__(self):
        # A minimal YANG-like structure for demonstration
        self.yang_model = {
            "module": "sensor-data",
            "namespace": "urn:example:sensor-data",
            "container": "sensor-data",
            "leaves": {
                "temperature": {"type": "decimal64", "description": "Temperature in Celsius"},
                "humidity": {"type": "decimal64", "description": "Humidity in percentage"},
                "timestamp": {"type": "string", "description": "Time of measurement"},
                "lightLevel": {"type": "decimal64", "description": "Light level in lux"},
                "binLevel": {"type": "decimal64", "description": "Bin fill percentage"},
                "ledStates": {
                    "type": "container",
                    "description": "LED states",
                    "leaves": {
                        "redLed": {"type": "boolean", "description": "Red LED state"},
                        "yellowLed": {"type": "boolean", "description": "Yellow LED state"},
                        "greenLed": {"type": "boolean", "description": "Green LED state"}
                    }
                }
            }
        }

    def get_capabilities(self):
        """Return the YANG model (capabilities) encoded in CBOR."""
        return cbor.dumps(self.yang_model)

# Simple Configuration Example
class ConfigManager:
    """
    Stores and updates device configuration.
    The sampling_interval parameter (in seconds) indicates how often the sensor should be sampled.
    """
    def __init__(self):
        self.config = {
            "sampling_interval": 10  # default sampling every 10 seconds
        }

    def get_config(self):
        return self.config

    def update_config(self, new_config):
        if "sampling_interval" in new_config:
            self.config["sampling_interval"] = new_config["sampling_interval"]

# Network Manager
class NetworkManager:
    @staticmethod
    async def connect_wifi():
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            print('Connecting to network...')
            wlan.connect(NetworkConfig.WIFI_SSID, NetworkConfig.WIFI_PASSWORD)
            start_time = utime.time()
            while not wlan.isconnected():
                if utime.time() - start_time > 20:
                    raise Exception("WiFi connection timeout")
                await asyncio.sleep_ms(100)
        print('Network config:', wlan.ifconfig())
        return wlan

# CoAP Server with CORECONF and Light Control
class SensorServer:
    def __init__(self, sensor_manager, coreconf_manager, config_manager):
        self.sensor_manager = sensor_manager
        self.coreconf_manager = coreconf_manager
        self.config_manager = config_manager
        self.server = microcoapy.Coap()

    def setup(self):
        """
        Setup CoAP server and register endpoints:
        1) /sensors (CBOR-encoded sensor data)
        2) /capabilities (CBOR-encoded YANG model)
        3) /.well-known/core (CBOR-encoded resource discovery)
        4) /config (CBOR-encoded GET/PUT for device configuration)
        5) /leds (CBOR-encoded GET/PUT for LED control)
        """

        # /sensors endpoint: returns latest sensor data in CBOR
        def sensor_handler(packet, sender_ip, sender_port):
            print(f'/sensors endpoint accessed from: {sender_ip}:{sender_port}')
            data = self.sensor_manager.last_data  # use last cached value
            if data:
                response = cbor.dumps(data)
                self.server.sendResponse(
                    sender_ip,
                    sender_port,
                    packet.messageid,
                    response,
                    0x45,  # 2.05 Content
                    0,     # Default content format (e.g., application/cbor)
                    packet.token
                )

        # /capabilities endpoint: returns YANG model in CBOR
        def capabilities_handler(packet, sender_ip, sender_port):
            print(f'/capabilities endpoint accessed from: {sender_ip}:{sender_port}')
            if packet.method == COAP_METHOD.COAP_GET:
                response = self.coreconf_manager.get_capabilities()
                self.server.sendResponse(
                    sender_ip,
                    sender_port,
                    packet.messageid,
                    response,
                    0x45,  # 2.05 Content
                    0,     # Use appropriate content format for CBOR
                    packet.token
                )

        # Well-Known Resource: /.well-known/core
        def well_known_handler(packet, sender_ip, sender_port):
            print(f'/.well-known/core endpoint accessed from: {sender_ip}:{sender_port}')
            if packet.method == COAP_METHOD.COAP_GET:
                # Create a simple resource list in CBOR format
                resources = {
                    "resources": [
                        {"path": "/sensors", "rt": "sensors"},
                        {"path": "/capabilities", "rt": "capabilities"},
                        {"path": "/config", "rt": "config"},
                        {"path": "/leds", "rt": "leds"}
                    ]
                }
                response = cbor.dumps(resources)
                self.server.sendResponse(
                    sender_ip,
                    sender_port,
                    packet.messageid,
                    response,
                    0x45,  # 2.05 Content
                    0,     # CBOR content format
                    packet.token
                )

        # /config endpoint: handles GET/PUT in CBOR
        def config_handler(packet, sender_ip, sender_port):
            print(f'/config endpoint accessed from: {sender_ip}:{sender_port}')
            if packet.method == COAP_METHOD.COAP_GET:
                cfg = self.config_manager.get_config()
                response = cbor.dumps(cfg)
                self.server.sendResponse(
                    sender_ip,
                    sender_port,
                    packet.messageid,
                    response,
                    0x45,  # 2.05 Content
                    0,
                    packet.token
                )
            elif packet.method == COAP_METHOD.COAP_PUT:
                try:
                    # Decode the CBOR payload into a Python dictionary
                    new_cfg = cbor.loads(packet.payload)  # Use cbor.loads() instead of json.loads()
                    self.config_manager.update_config(new_cfg)
                    response_data = {
                        "status": "updated",
                        "config": self.config_manager.get_config()
                    }
                    response = cbor.dumps(response_data)
                    self.server.sendResponse(
                        sender_ip,
                        sender_port,
                        packet.messageid,
                        response,
                        0x44,  # 2.04 Changed
                        0,
                        packet.token
                    )
                except Exception as e:
                    print("Error updating config:", e)
                    error_resp = cbor.dumps({"status": "error", "message": str(e)})
                    self.server.sendResponse(
                        sender_ip,
                        sender_port,
                        packet.messageid,
                        error_resp,
                        0x50,  # 5.00 Internal Server Error
                        0,
                        packet.token
                    )
        # /leds endpoint: handles GET/PUT for LED control
        def leds_handler(packet, sender_ip, sender_port):
            print(f'/leds endpoint accessed from: {sender_ip}:{sender_port}')
            if packet.method == COAP_METHOD.COAP_GET:
                # Return current LED states
                led_states = self.sensor_manager.led_states
                response = cbor.dumps(led_states)
                self.server.sendResponse(
                    sender_ip,
                    sender_port,
                    packet.messageid,
                    response,
                    0x45,  # 2.05 Content
                    0,
                    packet.token
                )
            elif packet.method == COAP_METHOD.COAP_PUT:
                try:
                    # Update LED states
                    new_led_states = cbor.loads(packet.payload)
                    self.sensor_manager.update_led_states(new_led_states)
                    response_data = {
                        "status": "updated",
                        "ledStates": self.sensor_manager.led_states
                    }
                    response = cbor.dumps(response_data)
                    self.server.sendResponse(
                        sender_ip,
                        sender_port,
                        packet.messageid,
                        response,
                        0x44,  # 2.04 Changed
                        0,
                        packet.token
                    )
                except Exception as e:
                    print("Error updating LED states:", e)
                    error_resp = cbor.dumps({"status": "error", "message": str(e)})
                    self.server.sendResponse(
                        sender_ip,
                        sender_port,
                        packet.messageid,
                        error_resp,
                        0x50,  # 5.00 Internal Server Error
                        0,
                        packet.token
                    )

        # Register endpoints
        self.server.addIncomingRequestCallback('sensors', sensor_handler)
        self.server.addIncomingRequestCallback('capabilities', capabilities_handler)
        self.server.addIncomingRequestCallback('.well-known/core', well_known_handler)
        self.server.addIncomingRequestCallback('config', config_handler)
        self.server.addIncomingRequestCallback('leds', leds_handler)

        self.server.start()
        print('CoAP CORECONF server started. Waiting for requests...')

    async def run(self):
        self.setup()
        while True:
            try:
                self.server.poll(1000)
                await asyncio.sleep_ms(100)
            except Exception as e:
                print("Server error:", str(e))
                await asyncio.sleep_ms(100)

# Background task: Periodically sample the sensor using the current sampling interval
async def sensor_sampling_loop(sensor_manager, config_manager):
    while True:
        data = sensor_manager.get_sensor_data()
        if data:
            print("Sampled sensor data:", data)
        # Get the current sampling interval (in seconds)
        cfg = config_manager.get_config()
        interval = cfg.get("sampling_interval", 1)
        await asyncio.sleep(interval)

# Main Application
class CoAPApplication:
    def __init__(self):
        self.sensor_manager = SensorManager()
        self.coreconf_manager = CoreconfManager()
        self.config_manager = ConfigManager()
        self.sensor_server = SensorServer(
            self.sensor_manager,
            self.coreconf_manager,
            self.config_manager
        )

    async def run(self):
        try:
            await NetworkManager.connect_wifi()
            # Create tasks for the CoAP server and the sensor sampling loop
            server_task = asyncio.create_task(self.sensor_server.run())
            sampling_task = asyncio.create_task(sensor_sampling_loop(self.sensor_manager, self.config_manager))
            await asyncio.gather(server_task, sampling_task)
        except Exception as e:
            print("Application error:", str(e))

# Entry point
if __name__ == '__main__':
    app = CoAPApplication()
    asyncio.run(app.run())