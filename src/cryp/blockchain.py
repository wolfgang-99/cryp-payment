from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from typing import Optional, Dict
from logging import getLogger
import os

logger = getLogger(__name__)

class BlockchainService:
    def __init__(self, rpc_url: str, payment_private_key: str = None):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        chain_id = self.w3.eth.chain_id
        logger.info(f"Connected to chain ID: {chain_id}")
        
        # BSC uses PoS, need this middleware
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        self.main_account = Web3.to_checksum_address(os.getenv('MAIN_WALLET'))
            
        # ERC-20 ABI (minimal for our needs)
        self.erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
    
    def generate_payment_address(self) -> tuple[str, str]:
        """Generate a new payment address"""
        account = Account.create()
        return account.address, account.key.hex()
    
    def get_bnb_balance(self, address: str) -> int:
        """Get BNB balance in Wei"""
        return self.w3.eth.get_balance(Web3.to_checksum_address(address))
    
    def get_token_balance(self, token_contract: str, address: str) -> int:
        """Get ERC-20 token balance"""
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_contract),
            abi=self.erc20_abi
        )
        return contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
    
    def get_token_decimals(self, token_contract: str) -> int:
        """Get token decimals"""
        try:

            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_contract),
                abi=self.erc20_abi
            )
            logger.info(f"Fetching decimals for token contract: {token_contract}")
            return contract.functions.decimals().call()
        except Exception as e:
            logger.error(f"Error fetching token decimals: {e}")
    
    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        """Get transaction details"""
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return {
                'transaction': tx,
                'receipt': receipt,
                'confirmations': self.w3.eth.block_number - receipt['blockNumber']
            }
        except Exception as e:
            print(f"Error getting transaction: {e}")
            return None
    
    def sweep_funds(self, from_private_key: str, token_contract: str = None) -> Optional[str]:
        """Sweep funds from payment address to main wallet"""
        try:
            logger.info("Starting sweep from address derived from provided private key (token_contract=%s)", token_contract)
            from_account = Account.from_key(from_private_key)

            if token_contract:
                # Sweep ERC-20 tokens
                contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(token_contract),
                    abi=self.erc20_abi
                )

                token_balance = self.get_token_balance(token_contract, from_account.address)
                logger.info("Token balance for %s: %s", from_account.address, token_balance)

                if token_balance <= 0:
                    logger.info("No token balance to sweep for %s", from_account.address)
                    return None

                # Ensure there's enough BNB to pay token transfer gas
                gas_price = self.w3.eth.gas_price
                gas_limit = 100000
                gas_cost = gas_price * gas_limit
                bnb_balance = self.get_bnb_balance(from_account.address)
                logger.info("BNB balance for gas check: %s, required gas: %s", bnb_balance, gas_cost)

                if bnb_balance < gas_cost:
                    logger.error("Insufficient BNB to pay token transfer gas (have: %s, need: %s)", bnb_balance, gas_cost)
                    return None

                transaction = contract.functions.transfer(
                    self.main_account,
                    token_balance
                ).build_transaction({
                    'from': from_account.address,
                    'gas': gas_limit,
                    'gasPrice': gas_price,
                    'nonce': self.w3.eth.get_transaction_count(from_account.address),
                    'chainId': self.w3.eth.chain_id
                })

                signed = from_account.sign_transaction(transaction)
                tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
                tx_hex = tx_hash.hex()
                logger.info("Token sweep tx sent: %s", tx_hex)
                return tx_hex
            else:
                # Sweep BNB
                balance = self.get_bnb_balance(from_account.address)
                gas_price = self.w3.eth.gas_price
                gas_limit = 21000
                gas_cost = gas_price * gas_limit

                logger.info("BNB balance: %s, gas_cost: %s", balance, gas_cost)

                if balance <= gas_cost:
                    logger.info("Not enough BNB to sweep (balance <= gas_cost) for %s", from_account.address)
                    return None

                transaction = {
                    'to': self.main_account,
                    'value': balance - gas_cost,
                    'gas': gas_limit,
                    'gasPrice': gas_price,
                    'nonce': self.w3.eth.get_transaction_count(from_account.address),
                    'chainId': self.w3.eth.chain_id
                }

                signed = from_account.sign_transaction(transaction)
                tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                tx_hex = tx_hash.hex()
                logger.info("BNB sweep tx sent: %s", tx_hex)
                return tx_hex
        except Exception as e:
            logger.exception('Error occured while sweeping funds to main wallet: %s', e)
            return None

    def to_human_readable(self, amount: int, decimals: int = 18) -> float:
        """Convert Wei/smallest unit to human readable"""
        return amount / (10 ** decimals)
    
    def to_wei(self, amount: float, decimals: int = 18) -> int:
        """Convert human readable to Wei/smallest unit"""
        return int(amount * (10 ** decimals))
