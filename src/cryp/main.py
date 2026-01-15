
from datetime import datetime, timedelta
import logging
import sys
from pathlib import Path
from typing import Optional, Dict

from .config import Config
from .database import MongoDB
from .blockchain import BlockchainService
from .encryption import KeyEncryption
from .tool import Tool
from .scheduler import Scheduler
from .webhook import Webhook




log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)

log_file = log_dir / "main.log"

# Configure logging to write to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a'),  # Write to file
        logging.StreamHandler(sys.stdout)          # Write to console
    ]
)
logger = logging.getLogger(__name__)


class Cryp:
    """
    Main Cryp Payment Processing Class
    
    This class handles cryptocurrency payment creation and status tracking
    for Binance Smart Chain (BSC) tokens.
    
    Attributes:
        db: MongoDB database connection
        blockchain: Blockchain service for interacting with BSC
        encryption: Key encryption service
        webhook: Webhook service for payment notifications
        tools: Additional tools for payment processing
        scheduler: Scheduler for background tasks
    """
    def __init__(self, mode:str='testnet', success_func=None):
        self.config = Config()

        # check mode 
        if mode == "testnet":
            rpc_url = self.config.BSC_TESTNET_RPC_URL
            self.mode ="testnet"
        elif mode == "mainnet":
            rpc_url = self.config.BSC_RPC_URL
            self.mode ="mainnet"
        else:
            logger.error("Invalid mode type. Mode type should be either Testnet OR  Mainnet")
            raise ValueError("Invalid mode type")
        
        
        # Initialize services
        self.db = MongoDB(
            uri=self.config.MONGODB_URI,
            db_name=self.config.MONGODB_DB
        )

        self.blockchain = BlockchainService(
            rpc_url=rpc_url,
            payment_private_key=self.config.PAYMENT_PRIVATE_KEY
        )

        # Initialize encryption 
        self.encryption = KeyEncryption(self.config.ENCRYPTION_KEY)

        # Initialize webhook
        self.webhook = Webhook(Alchemy_token=self.config.ALCHEMY_AUTH_TOKEN)

        # Initialize tool
        self.tools = Tool(self.db, self.blockchain, self.config, self.webhook, self.encryption, success_func)

        # Initialize scheduler
        self.scheduler = Scheduler(self.config, self.blockchain, self.db, self.tools)

    def create_payment(self, data: dict) -> Optional[Dict]:
        """
        Create a new payment request
        
        Args:
            data: Payment data dictionary containing:
                - amount: Payment amount (float)
                - currency: Currency code (e.g., 'BNB', 'USDT', 'BUSD')
                - user_id: User identifier
                - order_id: Order identifier
                - metadata: Optional metadata dictionary
        
        Returns:
            Dictionary containing payment information if successful, None otherwise
            {
                'success': bool,
                'payment': {
                    'id': str,
                    'payment_address': str,
                    'amount': float,
                    'amount_wei': str,
                    'currency': str,
                    'order_id': str,
                    'expires_at': str,
                    'qr_data': str
                }
            }
        
        Example:
            >>> cryp = Cryp()
            >>> payment_data = {
            ...     'amount': 100.0,
            ...     'currency': 'USDT',
            ...     'user_id': 'user123',
            ...     'order_id': 'order456'
            ... }
            >>> result = cryp.create_payment(payment_data)
            >>> print(result['payment']['payment_address'])
        """
        try:
            # Validate input
            required_fields = ['amount', 'currency', 'user_id', 'order_id']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                logger.error(f'Missing required fields: {", ".join(missing_fields)}')
                return {
                    'success': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }
                
            
            # Get token contract if not BNB
            token_contract = None
            decimals = 18
            
            currency = data['currency'].upper()
            
            if currency != 'BNB':
                if self.mode == "testnet":
                    currency_map = self.config.BSC_TESTNET_TOKENS
                elif self.mode == "mainnet":
                    currency_map = self.config.BSC_MAINNET_TOKENS
                else:
                    logger.error(f"Mode {self.mode} is not allowed")
                    raise ValueError("Invalid mode type")
                
                token_contract = currency_map.get(currency)
                if not token_contract:
                    logger.error(f'Unsupported currency: {currency}')
                    return {
                        'success': False,
                        'error': f'Unsupported currency: {currency}'
                    }
                
                decimals = self.blockchain.get_token_decimals(token_contract)
            
            # Generate unique payment address
            payment_address, private_key = self.blockchain.generate_payment_address()
            
            # Encrypt and store private key
            encrypted_key = self.encryption.encrypt_key(private_key)
            self.db.store_payment_key(payment_address.lower(), encrypted_key)
            
            # Convert amount to Wei/smallest unit
            amount_wei = self.blockchain.to_wei(float(data['amount']), decimals)
            
            # Create payment document
            payment_data = {
                'payment_address': payment_address.lower(),
                'user_id': data['user_id'],
                'order_id': data['order_id'],
                'amount_expected': str(amount_wei),
                'amount_received': '0',
                'token_address': token_contract,
                'currency': currency,
                'tx_hash': None,
                'from_address': None,
                'confirmations': 0,
                'status': 'pending',
                'confirmed_at': None,
                'expires_at': datetime.now() + timedelta(
                    minutes=self.config.PAYMENT_TIMEOUT_MINUTES
                ),
                'metadata': data.get('metadata', {})
            }
            
            # Store payment in database
            payment_id = self.db.create_payment(payment_data)
            
            if not payment_id:
                logger.error('Failed to store payment in database')
                return {
                    'success': False,
                    'error': 'Database error: Could not create payment'
                }
            
            # Add address to webhook for notifications
            webhook_added = self.webhook.add_address_to_webhook(
                self.config.ALCHEMY_WEBHOOK_ID,
                payment_address
            )
            
            if not webhook_added:
                logger.warning(f'Failed to add address to webhook: {payment_address}')
            
            logger.info(f"Created payment {payment_id} for order {data['order_id']}")
            
            return {
                'success': True,
                'payment': {
                    'id': payment_id,
                    'payment_address': payment_address,
                    'amount': data['amount'],
                    'amount_wei': str(amount_wei),
                    'currency': currency,
                    'order_id': data['order_id'],
                    'expires_at': payment_data['expires_at'].isoformat(),
                    'qr_data': f"{payment_address}?amount={amount_wei}"
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating payment: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Internal error: {str(e)}'
            }
    
    def get_payment_status(self, order_id: str) -> Optional[Dict]:
        """
        Get payment status for a specific order
        
        Args:
            order_id: Order identifier
        
        Returns:
            Dictionary containing payment status information if found, None otherwise
        
        Example:
            >>> cryp = Cryp()
            >>> status = cryp.get_payment_status('order456')
            >>> print(status['status'])
        """
        try:
            payment = self.db.get_payment_by_order_id(order_id)
            
            if not payment:
                logger.warning(f'Payment not found for order_id: {order_id}')
                return {
                    'success': False,
                    'error': f'Payment not found for order_id: {order_id}'
                }
            
            # Check if expired
            if payment['status'] == 'pending' and datetime.now() > payment['expires_at']:
                self.db.update_payment(payment['payment_address'], {'status': 'expired'})
                payment['status'] = 'expired'
                logger.info(f"Payment {order_id} marked as expired")
            
            # Get current balance if still pending or confirming
            if payment['status'] in ['pending', 'confirming']:
                try:
                    if payment['token_address']:
                        balance = self.blockchain.get_token_balance(
                            payment['token_address'],
                            payment['payment_address']
                        )
                    else:
                        balance = self.blockchain.get_bnb_balance(payment['payment_address'])
                    
                    self.db.update_payment(payment['payment_address'], {
                        'amount_received': str(balance)
                    })
                    payment['amount_received'] = str(balance)
                except Exception as e:
                    logger.error(f"Error fetching balance for {order_id}: {e}")
            
            # Convert MongoDB ObjectId to string
            payment['_id'] = str(payment['_id'])
            
            # Convert datetime objects to ISO format strings
            if 'expires_at' in payment and payment['expires_at']:
                payment['expires_at'] = payment['expires_at'].isoformat()
            if 'confirmed_at' in payment and payment['confirmed_at']:
                payment['confirmed_at'] = payment['confirmed_at'].isoformat()
            
            return {
                'success': True,
                'payment': payment
            }
            
        except Exception as e:
            logger.error(f"Error getting payment status for order_id {order_id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Internal error: {str(e)}'
            }
        
    def manual_check_payment(self, order_id)->Optional[Dict]:
        """Manually check payment status on blockchain"""
        try:
            payment = self.db.get_payment_by_order_id(order_id)
            
            if not payment:
                logger.error("Payment not found")
                return {
                    'success': False,
                    'error': 'Payment not found'
                }
            
            
            # Check balance
            if payment['token_address']:
                balance = self.blockchain.get_token_balance(
                    payment['token_address'],
                    payment['payment_address']
                )
                decimals = self.blockchain.get_token_decimals(payment['token_address'])
            else:
                balance = self.blockchain.get_bnb_balance(payment['payment_address'])
                decimals = 18
            
            update_data = {'amount_received': str(balance)}
            
            # Update status if sufficient
            if balance >= int(payment['amount_expected']):
                if payment['status'] == 'pending':
                    update_data['status'] = 'confirming'
                
                # If we have a tx_hash, check confirmations
                if payment.get('tx_hash'):
                    tx_info = self.blockchain.get_transaction(payment['tx_hash'])
                    if tx_info:
                        update_data['confirmations'] = tx_info['confirmations']
                        
                        if tx_info['confirmations'] >= self.config.CONFIRMATIONS_REQUIRED:
                            update_data['status'] = 'confirmed'
                            update_data['confirmed_at'] = datetime.now()
                            
                            self.db.update_payment(payment['payment_address'], update_data)
                            payment.update(update_data)
                            
                            self.tools.process_successful_payment(payment)
                            self.tools.sweep_payment_funds(payment)
            
            self.db.update_payment(payment['payment_address'], update_data)
            payment.update(update_data)
            
            # Convert MongoDB ObjectId to string
            payment['_id'] = str(payment['_id'])
            
            return {
                'success': True,
                'payment': payment,
                'balance_human': self.blockchain.to_human_readable(balance, decimals)
            }
        except Exception as e:
            logger.error(f"Error in manually checking payment for order_id {order_id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Internal error: {str(e)}'
            }

    # def process_webhook(self, request):
    #     try:
    #         signature = request.headers.get('X-Alchemy-Signature')

    #         if not self.tools.verify_alchemy_signature(request.data, signature):
    #             return {
    #                 'success': False,
    #                 'error': 'Invalid signature'
    #             }
            
    #         data = request.json
            
    #         # Process webhook event
    #         if data['type'] == 'ADDRESS_ACTIVITY':
    #             self.tools.process_transaction(data['event'])
    #             return{'success': True}
    #     except Exception as e:
    #         logger.error(f"Error in processing webhook event: {e}", exc_info=True)
    #         return {
    #             'success': False,
    #             'error': f'Internal error: {str(e)}'
    #         }
