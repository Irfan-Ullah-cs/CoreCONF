import asyncio
from aiocoap import Context, Message, Code
import cbor2

async def put_resource(ip, resource, payload):
    # Encode the payload into CBOR format
    cbor_payload = cbor2.dumps(payload)
    
    # Create a CoAP context
    protocol = await Context.create_client_context()
    
    # Create a CoAP PUT request
    request = Message(
        code=Code.PUT,
        payload=cbor_payload,
        uri=f"coap://{ip}/{resource}"
    )
    
    try:
        # Send the request and wait for the response
        response = await protocol.request(request).response
    except Exception as e:
        print(f"Failed to put /{resource}: {e}")
        return
    
    # Print the original raw response (in bytes)
    print(f"Original response for /{resource}: {response.payload}")
    hex_string = " ".join(f"{b:02x}" for b in response.payload)
    print(f"Pure hex string: {hex_string}")
    
    try:
        # Decode the CBOR payload into a Python object using cbor2
        decoded = cbor2.loads(response.payload)
        print(f"Decoded response for /{resource}: {decoded}\n")
    except Exception as e:
        print(f"Error decoding response for /{resource}: {e}\n")

async def main():
    ip = "192.168.4.226"
    
    # Define the sampling interval payload as a Python dictionary
    SamplingPayload = {
        "sampling_interval": 5  # Update the sampling interval to 10 seconds
    }
    
    # Define the LED status payload as a Python dictionary
    LEDPayload = {
        "redLed": False,
        "yellowLed": True,
        "greenLed": False
    }
    
    # Send the PUT request to update the sampling interval
    print("Updating sampling interval...")
    await put_resource(ip, "config", SamplingPayload)
    
    # Send the PUT request to update the LED status
    print("Updating LED status...")
    await put_resource(ip, "leds", LEDPayload)

if __name__ == "__main__":
    asyncio.run(main())