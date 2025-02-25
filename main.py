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

# -------------------------------
# Pin and Network Configuration
# -------------------------------
class PinConfig:
    DHT_PIN = 21
    LIGHT_SENSOR_PIN = 34
    LED1_PIN = 13  # Red LED
    LED2_PIN = 12  # Yellow LED
    LED3_PIN = 27  # Green LED
    TRIG_PIN = 32
    ECHO_PIN = 15
    BUTTON_PIN = 32
    MAX_BIN_HEIGHT = 100  # cm
    LIGHT_THRESHOLD = 250

class NetworkConfig:
    WIFI_SSID = "Galaxy A06 0a23"
    WIFI_PASSWORD = "12345678"

# -------------------------------
# Sensor Manager
# -------------------------------
class SensorManager:
    def __init__(self):
        # Initialize sensors
        try:
            self.dht_sensor = DHT22(Pin(PinConfig.DHT_PIN))
        except Exception as e:
            print("Error initializing DHT22 sensor:", e)
            self.dht_sensor = None
        try:
            self.light_sensor = ADC(Pin(PinConfig.LIGHT_SENSOR_PIN))
            self.light_sensor.atten(ADC.ATTN_11DB)
        except Exception as e:
            print("Error initializing light sensor:", e)
            self.light_sensor = None
        try:
            self.ultrasonic_sensor = HCSR04(trigger_pin=Pin(PinConfig.TRIG_PIN), echo_pin=Pin(PinConfig.ECHO_PIN))
        except Exception as e:
            print("Error initializing ultrasonic sensor:", e)
            self.ultrasonic_sensor = None
        
        # Initialize LEDs
        self.led1 = Pin(PinConfig.LED1_PIN, Pin.OUT)  # Red LED
        self.led2 = Pin(PinConfig.LED2_PIN, Pin.OUT)  # Yellow LED
        self.led3 = Pin(PinConfig.LED3_PIN, Pin.OUT)  # Green LED
        
        # Initialize Button (using internal pull-up)
        self.button = Pin(PinConfig.BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        
        # LED states
        self.led_states = {
            "redLed": False,
            "yellowLed": False,
            "greenLed": False
        }
        self.last_data = None

        # Set up the button interrupt to toggle red LED
        self.setup_button_interrupt()

    def get_light_level(self):
        try:
            return self.light_sensor.read() if self.light_sensor else None
        except Exception as e:
            print("Error reading light sensor:", e)
            return None

    def update_led_states(self, new_states):
        """Update LED states and physical LED outputs"""
        try:
            self.led_states = new_states
            self.led1.value(new_states.get("redLed", 0))
            self.led2.value(new_states.get("yellowLed", 0))
            self.led3.value(new_states.get("greenLed", 0))
        except Exception as e:
            print("Error updating LED states:", e)

    def toggle_red_led(self):
        """Toggle the state of the red LED"""
        try:
            self.led_states["redLed"] = not self.led_states["redLed"]
            self.update_led_states(self.led_states)
        except Exception as e:
            print("Error toggling red LED:", e)

    def handle_button_press(self, pin):
        """ISR for Button Press (kept short)"""
        try:
            self.toggle_red_led()
        except Exception as e:
            print("Error in button ISR:", e)

    def setup_button_interrupt(self):
        """Set up the button to trigger on a falling edge (button press)"""
        try:
            self.button.irq(trigger=Pin.IRQ_FALLING, handler=self.handle_button_press)
        except Exception as e:
            print("Error setting up button interrupt:", e)

    def get_distance(self):
        """Get distance measurement and calculate fill percentage"""
        try:
            if self.ultrasonic_sensor:
                distance = self.ultrasonic_sensor.distance_cm()
                if distance is not None and distance <= PinConfig.MAX_BIN_HEIGHT:
                    fill_percentage = ((PinConfig.MAX_BIN_HEIGHT - distance) / PinConfig.MAX_BIN_HEIGHT) * 100
                    return round(fill_percentage, 2)
            return None
        except OSError as e:
            print("Ultrasonic sensor error:", str(e))
            return None
        except Exception as e:
            print("Error in get_distance:", e)
            return None

    def get_sensor_data(self):
        """Get data from all sensors"""
        try:
            if self.dht_sensor:
                self.dht_sensor.measure()
                temperature = self.dht_sensor.temperature()
                humidity = self.dht_sensor.humidity()
            else:
                temperature, humidity = None, None
            light_level = self.get_light_level()
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
            print("Error reading sensors:", e)
            return None

# -------------------------------
# CORECONF Management Endpoints
# -------------------------------
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
        try:
            return cbor.dumps(self.yang_model)
        except Exception as e:
            print("Error encoding YANG model:", e)
            return cbor.dumps({"error": "encoding failed"})

# -------------------------------
# Configuration Manager
# -------------------------------
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
        try:
            if "sampling_interval" in new_config:
                self.config["sampling_interval"] = new_config["sampling_interval"]
        except Exception as e:
            print("Error updating configuration:", e)

# -------------------------------
# Network Manager
# -------------------------------
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

# -------------------------------
# CoAP Server with CORECONF, LED Control, and Observe Support
# -------------------------------
class SensorServer:
    def __init__(self, sensor_manager, coreconf_manager, config_manager):
        self.sensor_manager = sensor_manager
        self.coreconf_manager = coreconf_manager
        self.config_manager = config_manager
        self.server = microcoapy.Coap()
        # Observers: key is resource path (e.g., '/leds') and value is list of (sender_ip, sender_port, token)
        self.observers = {}
        # Keep track of the last LED state to detect changes
        self.last_led_state = sensor_manager.led_states.copy()

    def notify_observers(self, resource, payload):
        """Notify all registered observers for the given resource"""
        if resource in self.observers:
            try:
                response = cbor.dumps(payload)
            except Exception as e:
                print("Error encoding notification payload:", e)
                return
            message_id = int(utime.time()) & 0xFFFF  # simple message ID generation
            for (ip, port, token) in self.observers[resource]:
                try:
                    self.server.sendResponse(ip, port, message_id, response, 0x45, 0, token)
                    print(f"Notified observer at {ip}:{port} for {resource} with payload: {payload}")
                except Exception as e:
                    print("Error notifying observer:", e)

    def setup(self):
        """Setup CoAP server and register endpoints:
        1) /sensors (CBOR-encoded sensor data)
        2) /capabilities (CBOR-encoded YANG model)
        3) /.well-known/core (CBOR-encoded resource discovery)
        4) /config (CBOR-encoded GET/PUT for device configuration)
        5) /leds (CBOR-encoded GET/PUT for LED control and observe)
        """
        # /sensors endpoint: returns latest sensor data in CBOR
        def sensor_handler(packet, sender_ip, sender_port):
            print(f'/sensors endpoint accessed from: {sender_ip}:{sender_port}')
            data = self.sensor_manager.last_data  # use last cached value
            if data:
                try:
                    response = cbor.dumps(data)
                except Exception as e:
                    print("Error encoding sensor data:", e)
                    response = cbor.dumps({"error": "encoding failed"})
                try:
                    self.server.sendResponse(sender_ip, sender_port, packet.messageid,
                                             response, 0x45, 0, packet.token)
                except Exception as e:
                    print("Error sending sensor response:", e)

        # /capabilities endpoint: returns YANG model in CBOR
        def capabilities_handler(packet, sender_ip, sender_port):
            print(f'/capabilities endpoint accessed from: {sender_ip}:{sender_port}')
            if packet.method == COAP_METHOD.COAP_GET:
                try:
                    response = self.coreconf_manager.get_capabilities()
                except Exception as e:
                    print("Error encoding capabilities:", e)
                    response = cbor.dumps({"error": "encoding failed"})
                try:
                    self.server.sendResponse(sender_ip, sender_port, packet.messageid,
                                             response, 0x45, 0, packet.token)
                except Exception as e:
                    print("Error sending capabilities response:", e)

        # Well-Known Resource: /.well-known/core
        def well_known_handler(packet, sender_ip, sender_port):
            print(f'/.well-known/core endpoint accessed from: {sender_ip}:{sender_port}')
            if packet.method == COAP_METHOD.COAP_GET:
                resources = {
                    "resources": [
                        {"path": "/sensors", "rt": "sensors"},
                        {"path": "/capabilities", "rt": "capabilities"},
                        {"path": "/config", "rt": "config"},
                        {"path": "/leds", "rt": "leds"}
                    ]
                }
                try:
                    response = cbor.dumps(resources)
                except Exception as e:
                    print("Error encoding resource list:", e)
                    response = cbor.dumps({"error": "encoding failed"})
                try:
                    self.server.sendResponse(sender_ip, sender_port, packet.messageid,
                                             response, 0x45, 0, packet.token)
                except Exception as e:
                    print("Error sending resource list response:", e)

        # /config endpoint: handles GET/PUT in CBOR
        def config_handler(packet, sender_ip, sender_port):
            print(f'/config endpoint accessed from: {sender_ip}:{sender_port}')
            if packet.method == COAP_METHOD.COAP_GET:
                try:
                    cfg = self.config_manager.get_config()
                    response = cbor.dumps(cfg)
                except Exception as e:
                    print("Error encoding config:", e)
                    response = cbor.dumps({"error": "encoding failed"})
                try:
                    self.server.sendResponse(sender_ip, sender_port, packet.messageid,
                                             response, 0x45, 0, packet.token)
                except Exception as e:
                    print("Error sending config response:", e)
            elif packet.method == COAP_METHOD.COAP_PUT:
                try:
                    new_cfg = cbor.loads(packet.payload)
                    self.config_manager.update_config(new_cfg)
                    response_data = {
                        "status": "updated",
                        "config": self.config_manager.get_config()
                    }
                    response = cbor.dumps(response_data)
                    self.server.sendResponse(sender_ip, sender_port, packet.messageid,
                                             response, 0x44, 0, packet.token)
                except Exception as e:
                    print("Error updating config:", e)
                    error_resp = cbor.dumps({"status": "error", "message": str(e)})
                    self.server.sendResponse(sender_ip, sender_port, packet.messageid,
                                             error_resp, 0x50, 0, packet.token)

        # /leds endpoint: handles GET/PUT for LED control and supports observe
        def leds_handler(packet, sender_ip, sender_port):
            print(f'/leds endpoint accessed from: {sender_ip}:{sender_port}')
            if packet.method == COAP_METHOD.COAP_GET:
                # Check if this GET request is for observation.
                # (Assuming the CoAP packet has an 'observe' attribute per RFC 7641.)
                if hasattr(packet, 'observe') and packet.observe == 0:
                    print(f"Registering observer for /leds from: {sender_ip}:{sender_port}")
                    self.observers.setdefault('leds', [])
                    # Avoid duplicate registrations based on (sender, token)
                    if (sender_ip, sender_port, packet.token) not in self.observers['leds']:
                        self.observers['leds'].append((sender_ip, sender_port, packet.token))
                try:
                    led_states = self.sensor_manager.led_states
                    response = cbor.dumps(led_states)
                except Exception as e:
                    print("Error encoding LED states:", e)
                    response = cbor.dumps({"error": "encoding failed"})
                try:
                    self.server.sendResponse(sender_ip, sender_port, packet.messageid,
                                             response, 0x45, 0, packet.token)
                except Exception as e:
                    print("Error sending LED response:", e)
            elif packet.method == COAP_METHOD.COAP_PUT:
                try:
                    new_led_states = cbor.loads(packet.payload)
                    self.sensor_manager.update_led_states(new_led_states)
                    response_data = {
                        "status": "updated",
                        "ledStates": self.sensor_manager.led_states
                    }
                    response = cbor.dumps(response_data)
                    self.server.sendResponse(sender_ip, sender_port, packet.messageid,
                                             response, 0x44, 0, packet.token)
                except Exception as e:
                    print("Error updating LED states:", e)
                    error_resp = cbor.dumps({"status": "error", "message": str(e)})
                    self.server.sendResponse(sender_ip, sender_port, packet.messageid,
                                             error_resp, 0x50, 0, packet.token)

        # Register endpoints with the microCoAPy server
        try:
            self.server.addIncomingRequestCallback('sensors', sensor_handler)
            self.server.addIncomingRequestCallback('capabilities', capabilities_handler)
            self.server.addIncomingRequestCallback('.well-known/core', well_known_handler)
            self.server.addIncomingRequestCallback('config', config_handler)
            self.server.addIncomingRequestCallback('leds', leds_handler)
        except Exception as e:
            print("Error registering endpoints:", e)
        
        try:
            self.server.start()
            print('CoAP CORECONF server started. Waiting for requests...')
        except Exception as e:
            print("Error starting CoAP server:", e)

    async def run(self):
        self.setup()
        while True:
            try:
                self.server.poll(1000)
            except Exception as e:
                print("Server polling error:", e)
            # Check for LED state changes (e.g., from button presses)
            current_led_state = self.sensor_manager.led_states
            if current_led_state != self.last_led_state:
                print("LED state changed. Notifying observers...")
                self.notify_observers('leds', current_led_state)
                self.last_led_state = current_led_state.copy()
            await asyncio.sleep_ms(100)

# -------------------------------
# Background Sensor Sampling Loop
# -------------------------------
async def sensor_sampling_loop(sensor_manager, config_manager):
    while True:
        data = sensor_manager.get_sensor_data()
        if data:
            print("Sampled sensor data:", data)
        # Use the current sampling interval from configuration
        cfg = config_manager.get_config()
        interval = cfg.get("sampling_interval", 1)
        await asyncio.sleep(interval)

# -------------------------------
# Main Application
# -------------------------------
class CoAPApplication:
    def __init__(self):
        self.sensor_manager = SensorManager()
        self.coreconf_manager = CoreconfManager()
        self.config_manager = ConfigManager()
        self.sensor_server = SensorServer(self.sensor_manager, self.coreconf_manager, self.config_manager)

    async def run(self):
        try:
            await NetworkManager.connect_wifi()
            # Create tasks for the CoAP server and the sensor sampling loop
            server_task = asyncio.create_task(self.sensor_server.run())
            sampling_task = asyncio.create_task(sensor_sampling_loop(self.sensor_manager, self.config_manager))
            await asyncio.gather(server_task, sampling_task)
        except Exception as e:
            print("Application error:", e)

# -------------------------------
# Entry Point
# -------------------------------
if __name__ == '__main__':
    app = CoAPApplication()
    asyncio.run(app.run())
