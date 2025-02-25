
# MicroPython CoAP CORECONF IoT Project

This project is a MicroPython-based IoT application that leverages the CoAP protocol with CORECONF (a minimal YANG-based resource description) to manage sensor data and control LEDs. It implements resource discovery using the CoRE Link Format (RFC 6690) and conforms to OCF Specification 2.2.7 by announcing appropriate resource types and interfaces. 

## Features

- **CoAP Communication**: Uses [microCoAPy](https://github.com/insighio/microCoAPy) for handling CoAP messages.
- **Resource Discovery**: Implements `/.well-known/core` to expose all hosted resources in the CoRE Link Format. Resources are tagged with:
  - **Resource Types (`rt`)**: e.g., `oic.r.sensor`, `oic.r.coreconf`, `oic.r.configuration`, and `oic.r.led`
  - **Interfaces (`if`)**: e.g., `oic.if.baseline` for sensor and configuration resources and `oic.if.a` for actuators.
- **Sensor Data Collection**: Gathers data from:
  - **DHT22**: Temperature and humidity.
  - **Light Sensor**: Analog light level.
  - **HCSR04**: Ultrasonic sensor for bin fill percentage.
- **LED Control & Observation**: 
  - Controls three LEDs (red, yellow, green).
  - Provides a `/leds` endpoint that supports GET/PUT operations.
- **Configuration Management**: Exposes a `/config` endpoint for GET/PUT operations (e.g., to change sensor sampling interval).
- **CORECONF Capabilities**: The `/capabilities` endpoint returns a minimal YANG model (encoded in CBOR) describing the device’s capabilities.
- **Robust Error Handling**: Every sensor reading, CoAP message, and network operation includes error handling and logging.
- **Asynchronous Operation**: Uses `uasyncio` for nonblocking multitasking.

## Requirements

- **Hardware**:
  - A MicroPython-capable microcontroller (e.g., ESP32)
  - Sensors: DHT22, ultrasonic sensor (HCSR04), and an analog light sensor.
  - LEDs and a button.
- **Software**:
  - MicroPython firmware.
  - Required libraries:
    - `microcoapy`
    - `dht`
    - `hcsr04`
    - `cbor` (e.g., [alexmrqt/micropython-cbor](https://github.com/alexmrqt/micropython-cbor) or [agronholm/cbor2](https://github.com/agronholm/cbor2))
    - `uasyncio`

## Setup

1. **Clone the Repository**

    ```bash
    git clone https://github.com/Irfan-Ullah-cs/CoreCONF.git
    cd yourrepository
    ```

2. **Configure WiFi**

   Edit the `NetworkConfig` class in your code to include your WiFi credentials:

    ```python
    class NetworkConfig:
        WIFI_SSID = "Your_WiFi_SSID"
        WIFI_PASSWORD = "Your_WiFi_Password"
    ```

3. **Connect Sensors and Actuators**

   - **DHT22**: Connect the data pin to `GPIO21`.
   - **Light Sensor**: Connect to `ADC34`.
   - **Ultrasonic Sensor**: Connect the trigger to `GPIO32` and echo to `GPIO15`.
   - **LEDs**: Connect red LED to `GPIO13`, yellow LED to `GPIO12`, and green LED to `GPIO27`.
   - **Button**: Connect to `GPIO32` (using internal pull-up).

4. **Upload Code to the Device**

   Use a tool like ampy or rshell to upload the MicroPython code to your device.

## Usage

1. **Starting the Application**

   Once your device is powered on and connected to WiFi, it will:
   - Start the CoAP server.
   - Begin sampling sensor data periodically.
   - Listen for incoming CoAP requests.

2. **Interacting with the Device**

   - **Resource Discovery**:  
     Send a GET request to:  
     `coap://<device_ip>/.well-known/core`  
     You will receive a response in the CoRE Link Format such as:

     ```
     </sensors>;rt="oic.r.sensor";if="oic.if.baseline";ct=60,
     </capabilities>;rt="oic.r.coreconf";if="oic.if.baseline";ct=60,
     </config>;rt="oic.r.configuration";if="oic.if.baseline";ct=60,
     </leds>;rt="oic.r.led";if="oic.if.a";ct=60
     ```

   - **Sensor Data**:  
     GET `coap://<device_ip>/sensors` to retrieve the latest sensor readings.

   - **Device Capabilities**:  
     GET `coap://<device_ip>/capabilities` to obtain the YANG model (CORECONF) in CBOR.

   - **Configuration Management**:  
     - **GET**: Retrieve current configuration from `coap://<device_ip>/config`
     - **PUT**: Update configuration (e.g., sampling interval) by sending a CBOR payload to `coap://<device_ip>/config`

   - **LED Control & Observation**:  
     - **GET**: Retrieve current LED states from `coap://<device_ip>/leds`
     - **PUT**: Update LED states by sending a CBOR payload to `coap://<device_ip>/leds`
the observe option) to get notified when the red LED toggles.

## Resource Discovery & OCF Compliance

The `/.well-known/core` endpoint provides a list of resources formatted according to RFC 6690. For example:


</sensors>;rt="oic.r.sensor";if="oic.if.baseline";ct=60, 
</capabilities>;rt="oic.r.coreconf";if="oic.if.baseline";ct=60, 
</config>;rt="oic.r.configuration";if="oic.if.baseline";ct=60, 
</leds>;rt="oic.r.led";if="oic.if.a";ct=60

This format ensures that resource types (`rt`) and interfaces (`if`) are set to values required for OCF Specification 2.2.7, allowing OCF-compliant clients to correctly identify and interact with your device.

## Debugging & Logs

The application logs key events such as:
- WiFi connection status
- Sensor sampling outputs
- CoAP request handling and responses (including hex and decoded CBOR data)
- Observe notifications for LED state changes

Use these logs (viewable via a serial console) to diagnose issues during development.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions and improvements are welcome! Please submit issues or pull requests on the [GitHub repository](https://github.com/Irfan-Ullah-cs/CoreCONF.git).

## Acknowledgements

- [microCoAPy](https://github.com/insighio/microCoAPy) for the CoAP stack.
- The MicroPython community for ongoing support and development.
- OCF and CoRE specifications for providing the standards that guide this project.

---

For further details and updates, please visit the [GitHub repository](https://github.com/Irfan-Ullah-cs/CoreCONF.git).
