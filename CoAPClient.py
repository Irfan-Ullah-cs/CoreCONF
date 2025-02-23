import asyncio
from aiocoap import Context, Message, GET
import cbor2

async def get_resource(ip, resource):
    # Create the CoAP client context
    protocol = await Context.create_client_context()
    request = Message(code=GET, uri=f"coap://{ip}/{resource}")
    
    try:
        response = await protocol.request(request).response
    except Exception as e:
        print(f"Failed to fetch /{resource}: {e}")
        return
    
    # Print the original raw CBOR response (in bytes)
    print(f"Original response for /{resource}: {response.payload}")
    hex_string = " ".join(f"{b:02x}" for b in response.payload)
    print(f"Pure hex string: {hex_string}")

    
    try:
        # Decode the CBOR payload into a Python object
        decoded = cbor2.loads(response.payload)
        print(f"Decoded response for /{resource}: {decoded}\n")
    except Exception as e:
        print(f"Error decoding CBOR for /{resource}: {e}\n")

async def main():
    ip = "192.168.4.226"
    await get_resource(ip, ".well-known/core")
    # await get_resource(ip, "capabilities")
    # await get_resource(ip, "sensors")
    await get_resource(ip, "config")

if __name__ == "__main__":
    asyncio.run(main())

