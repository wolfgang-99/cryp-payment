import ngrok
import time
from logging import getLogger
import os
from dotenv import load_dotenv

load_dotenv()

logger = getLogger(__name__)

def setup_ngrok_url(addr:int):
    """ This setup ngrok for webhook testing with same port number of your server
    :param addr: The same port number of your server
    :type addr: int
    """
    listener = ngrok.forward(addr=addr, authtoken=os.getenv('NGROK_AUTHTOKEN'))

    # Output the public ngrok URL
    print(f"Ingress established at {listener.url()}")

    # Keep the listener alive until manually interrupted (e.g., Ctrl+C)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Closing listener")
        ngrok.kill() # Stop the ngrok process cleanly

setup_ngrok_url(5000)