import hmac
import hashlib
from datetime import datetime
from web3 import Web3
from logging import getLogger
import types

from .database import MongoDB
from .blockchain import BlockchainService
from .encryption import KeyEncryption
from .webhook import Webhook
from .config import Config

logger = getLogger(__name__)

class Tool:
    """
    Verify and process incoming webhooks from Alchemy service.
    Handles signature verification, payment lookup, confirmation updates,
    and fund sweeping.

    Methods:
    - verify_alchemy_signature: Verify the HMAC signature of the webhook.
    - process_transaction: Process incoming transaction data.
    - parse_token_transfer_amount: Extract token transfer amounts from logs
    - process_successful_payment: Handle actions after payment confirmation.
    - sweep_payment_funds: Sweep funds from payment address to main wallet.

    """
    def __init__(self, db: MongoDB, blockchain: BlockchainService, config:Config,
                  webhook:Webhook, encryption:KeyEncryption, success_func=None):
        """ Initialize tool instance

        :param encryption: encryption instance
        :type encryption: KeyEncryption
        :param db: Database instance
        :type db: MongoDB
        :param blockchain: Blockchain service instance
        :type blockchain: BlockchainService
        """
        self.db = db
        self.webhook = webhook
        self.blockchain = blockchain
        self.encryption = encryption

        self.webhook_signing_key = config.ALCHEMY_WEBHOOK_SIGNING_KEY
        self.confirmations_required = config.CONFIRMATIONS_REQUIRED
        self.webhook_id = config.ALCHEMY_WEBHOOK_ID

        # success function handling
        if success_func is None:
            self.process_successful_payment = self._default_process_successful_payment
        else:
            self.process_successful_payment = types.MethodType(success_func, self)


    def verify_alchemy_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Alchemy webhook signature"""
        try:
            if not self.webhook_signing_key :
                logger.error("Alchemy webhook sigining key not found")
                return False 
            
            computed_signature = hmac.new(
                self.webhook_signing_key.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            logger.info("Alchemy webhook signature verified")
            return hmac.compare_digest(computed_signature, signature)
        
        except Exception as e:
            logger.error("An error occured while verifing Alchemy webhook signature " + str(e))
            return False


    def process_transaction(self, tx_data: dict):
        """Process incoming transaction"""
        try:
            activities = tx_data.get('activity', [])
            if not activities:
                logger.error("No activity in the webhook data")
                return
            
            activity = activities[0]
            
            to_address = activity.get('toAddress', '').lower()
            
            # Find payment by address
            payment = self.db.get_payment_by_address(to_address)
            
            if not payment or payment['status'] not in ['pending', 'confirming']:
                return
            
            tx_hash = activity['hash']
            from_address = activity['fromAddress']
            
            # Get transaction details
            tx_info = self.blockchain.get_transaction(tx_hash)
            
            if not tx_info:
                return
            
            # Determine amount received
            if payment['token_address']:
                # For tokens, parse logs
                amount_received = self.parse_token_transfer_amount(
                    tx_info['receipt'],
                    payment['token_address'],
                    to_address
                )
            else:
                # For BNB
                raw_contract = activity.get('rawContract', {})
                raw_value = raw_contract.get('rawValue', '0x0')
    
                # Convert hex string to integer
                amount_received = int(raw_value, 16)    
            
            # Update payment
            update_data = {
                'tx_hash': tx_hash,
                'from_address': from_address,
                'amount_received': str(amount_received),
                'confirmations': tx_info['confirmations']
            }
            
            logger.info(f"Comparing amounts - received: {amount_received} (type: {type(amount_received)}), expected: {payment['amount_expected']} (type: {type(payment['amount_expected'])})")
            # Check if payment is sufficient
            if amount_received >= int(payment['amount_expected']):
                if tx_info['confirmations'] >= self.confirmations_required:
                    update_data['status'] = 'confirmed'
                    update_data['confirmed_at'] = datetime.now()
                    
                    # Update database
                    self.db.update_payment(to_address, update_data)
                    
                    # Process successful payment
                    payment.update(update_data)
                    self.process_successful_payment(payment)
                    
                    # Sweep funds to main wallet
                    self.sweep_payment_funds(payment)
                else:
                    logger.warning("confirmation not sufficient, updating.... ")
                    update_data['status'] = 'confirming'
                    self.db.update_payment(to_address, update_data)
            else:
                logger.warning("Amount not sufficient")
                self.db.update_payment(to_address, update_data)
        except Exception as e:
            logger.error("An error occured while Process incoming transaction " + str(e))


    def parse_token_transfer_amount(self, receipt: dict, token_address: str, 
                                    to_address: str) -> int:
        """Parse token transfer amount from logs"""
        # Transfer event signature
        transfer_sig = Web3.keccak(text="Transfer(address,address,uint256)").hex()
        
        for log in receipt['logs']:
            if log['address'].lower() == token_address.lower():
                if log['topics'][0].hex() == transfer_sig:
                    # topics[2] is the 'to' address
                    if log['topics'][2][-40:].lower() == to_address[2:].lower():
                        # data is the amount
                        return int(log['data'], 16)
        
        return 0


    def _default_process_successful_payment(self, payment: dict):
        """Handle successful payment confirmation"""
        logger.info(f"Payment confirmed: {payment['order_id']}")
        
        # Your business logic here:
        # - Activate subscription
        # - Send confirmation email
        # - Update order status
        # - Grant access to digital goods
        pass


    def sweep_payment_funds(self, payment: dict):
        """Sweep funds from payment address to main wallet"""
        try:
            logger.info("Starting sweep for payment_address=%s token=%s", payment.get('payment_address'), payment.get('token_address'))

            encrypted_key = self.db.get_payment_key(payment['payment_address'])
            if not encrypted_key:
                logger.info("No private key found for %s", payment['payment_address'])
                return False

            try:
                private_key = self.encryption.decrypt_key(encrypted_key)
            except ValueError as e:
                logger.error(
                    "Failed to decrypt private key for %s: %s. Check ENCRYPTION_KEY and that the encrypted key wasn't corrupted. encrypted_key prefix=%s",
                    payment['payment_address'], str(e), (encrypted_key or '')[:16]
                )
                return False
            except Exception:
                logger.exception("Failed to decrypt private key for %s", payment['payment_address'])
                return False

            if not private_key or not isinstance(private_key, str):
                logger.error("Decrypted private key invalid for %s: %r", payment['payment_address'], private_key)
                return False

            # redact key for logs
            logger.debug("Decrypted private key (redacted): %s", private_key[:6] + "..." + private_key[-4:])

            try:
                tx_hash = self.blockchain.sweep_funds(from_private_key=private_key, token_contract=payment.get('token_address'))
            except Exception:
                logger.exception("blockchain.sweep_funds raised an exception for %s", payment['payment_address'])
                return False

            if not tx_hash:
                # gather diagnostics to see why sweep_funds returned None
                try:
                    if payment.get('token_address'):
                        token_bal = self.blockchain.get_token_balance(payment['token_address'], payment['payment_address'])
                        bnb_bal = self.blockchain.get_bnb_balance(payment['payment_address'])
                        logger.warning("Sweep returned no tx. token_balance=%s bnb_balance=%s", token_bal, bnb_bal)
                    else:
                        bnb_bal = self.blockchain.get_bnb_balance(payment['payment_address'])
                        logger.warning("Sweep returned no tx. bnb_balance=%s", bnb_bal)
                except Exception:
                    logger.exception("Error while fetching balances for diagnostics")
                logger.error("sweeping funds failed: sweep_funds returned no tx hash")
                return False

            logger.info("Swept funds: %s", tx_hash)
            self.db.delete_payment_key(payment['payment_address'])
            self.webhook.remove_address_to_webhook(self.webhook_id, payment['payment_address'])
            return tx_hash

        except Exception:
            logger.exception("Unexpected error sweeping funds for %s", payment.get('payment_address'))
            return False



