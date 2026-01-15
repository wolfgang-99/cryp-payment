import requests
from logging import getLogger
import os 
from web3 import Web3
from dotenv import load_dotenv

from .database import MongoDB

load_dotenv()
logger = getLogger(__name__)

class Webhook:
    def __init__(self, Alchemy_token:str):
        self.token = Alchemy_token 
        self.url = "https://dashboard.alchemy.com/api"


    def create_webhook(self, webhook_url:str, addresses:list|str, network:str="BNB_MAINNET")->dict:
        """ Create alchemy webhook 
        
        :param network: Check alchemy notify-api-endpoints https://www.alchemy.com/docs/data/webhooks/webhooks-api-endpoints/notify-api-endpoints/create-webhook doc and get a vaild string.
        :type network: str

        :param webhook_url: URL where requests are sent
        :type webhook_url: str

        :return:  json dict | empty dict if error occure

        """
        try:
            url = f"{self.url}/create-webhook"

            # Ensure address is checksummed
            checksummed_address = []
            if isinstance(addresses, str):
                checksummed_address.append(Web3.to_checksum_address(addresses))
            elif isinstance(addresses, list):
                for addr in addresses:
                    checksummed_address.append(Web3.to_checksum_address(addr))

            payload = {
                "network": network,
                "webhook_type": "ADDRESS_ACTIVITY",
                "webhook_url": webhook_url,
                "addresses": checksummed_address,
                "activity_types": [
                    "EXTERNAL",  # External transactions (wallet to wallet)
                    "INTERNAL",  # Internal transactions
                    "TOKEN"      # Token transfers
                ]   

            }
            headers = {
                "X-Alchemy-Token": self.token,
                "Content-Type": "application/json"
            }

            response = requests.post(url, json=payload, headers=headers)
            
            # Check response status 
            if response.status_code != 200:
                logger.error(f"API Error: Status {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {}
            
            res = response.json()
            data = res['data']
            # with open("webhook-info.txt", "w") as file:
            #     file.write(data)

            logger.info(f"Webhook created for {data['network']} network")

            return data
        except Exception as e:
            logger.error("Error while creating webhook " + str(e))
            return{}

    def add_address_to_webhook(self, webhook_id:str, addresses: str|list)->dict:
        """Add address to Alchemy webhook"""
        try:
            url = f"{self.url}/update-webhook-addresses"
            
              # Ensure address is checksummed
            checksummed_address = []
            if isinstance(addresses, str):
                checksummed_address.append(Web3.to_checksum_address(addresses))
            elif isinstance(addresses, list):
                for addr in addresses:
                    checksummed_address.append(Web3.to_checksum_address(addr))

            headers = {
                "X-Alchemy-Token": self.token
            }
            
            data = {
                "webhook_id": webhook_id,
                "addresses_to_add": checksummed_address,
                "addresses_to_remove": []
            }
            
            response = requests.patch(url, json=data, headers=headers)

            # Check response status first
            if response.status_code != 200:
                logger.error(f"API Error: Status {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {}
            
            logger.info(f'Address {checksummed_address} has been added to webhook')
            return True
            
        except Exception as e:
            logger.error("Error occured while adding address " + str(e))
            return False

    def remove_address_to_webhook(self, webhook_id:str, addresses: str|list)->dict:
        """remove address to Alchemy webhook"""
        try:
            url = f"{self.url}/update-webhook-addresses"
            
            # Ensure address is checksummed
            checksummed_address = []
            if isinstance(addresses, str):
                checksummed_address.append(Web3.to_checksum_address(addresses))
            elif isinstance(addresses, list):
                for addr in addresses:
                    checksummed_address.append(Web3.to_checksum_address(addr))

            headers = {
                "X-Alchemy-Token": self.token
            }
            
            data = {
                "webhook_id": webhook_id,
                "addresses_to_add": [],
                "addresses_to_remove": checksummed_address
            }
            
            response = requests.patch(url, json=data, headers=headers)

            # Check response status first
            if response.status_code != 200:
                logger.error(f"API Error: Status {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {}
            
            logger.info(f'Address {checksummed_address} has been removed from webhook')
            return True
            
        except Exception as e:
            logger.error("Error occured while removing address " + str(e))
            return False

# hook = Webhook(Alchemy_token=os.getenv('Alchemy_Auth_Token'))

# data = hook.create_webhook(webhook_url="https://moses-oratorlike-ornamentally.ngrok-free.dev/api/webhook/alchemy",
#                            addresses='0xC206146f964965972D0853aaE1D58793B19DD0ce')
# sample = {'data': {'id': 'wh_wsqfumm7lcinlm02', 'name': '', 'network': 'BNB_TESTNET', 'networks': [], 'webhook_type': 'ADDRESS_ACTIVITY', 'webhook_url': 'https://moses-oratorlike-ornamentally.ngrok-free.dev/api/webhook/alchemy', 'is_active': True, 'time_created': 1767894506000, 'signing_key': 'whsec_S9EBFZGdrBcY9LyR0Cuk2BmC', 'version': 'V2', 'deactivation_reason': 'UNKNOWN'}}

# data= hook.add_address_to_webhook(webhook_id='wh_4pavz4885fd6ruf8', addresses='0x3518781357485f8c4bE88C769DB4487a448dC13e')
# print(data)