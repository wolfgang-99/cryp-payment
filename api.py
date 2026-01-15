from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta
import os
import logging
import sys
from pathlib import Path

from src.cryp.config import Config
from src.cryp.database import MongoDB
from src.cryp.blockchain import BlockchainService
from src.cryp.encryption import KeyEncryption
from src.cryp.tool import Tool
from src.cryp.scheduler import Scheduler
from src.cryp.webhook import Webhook

app = Flask(__name__)
app.config.from_object(Config)


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

# Initialize services
db = MongoDB(
    uri=app.config['MONGODB_URI'],
    db_name=app.config['MONGODB_DB']
)

blockchain = BlockchainService(
    rpc_url=app.config['BSC_RPC_URL'],
    payment_private_key=app.config['PAYMENT_PRIVATE_KEY']
)

# Initialize encryption 
encryption = KeyEncryption(app.config['ENCRYPTION_KEY'])

# Initialize webhook
webhook = Webhook(Alchemy_token=app.config['ALCHEMY_AUTH_TOKEN'])

# Initialize tool
tools = Tool(db, blockchain, app, webhook)

# Initialize scheduler
scheduler = Scheduler(app, blockchain, db, tools)



@app.route('/')
def home():
    """Home page"""
    return render_template('index.html')

@app.route('/crypto-payments')
def crypto_payments_info():
    """Crypto payments info page"""
    return render_template('crypto-payments.html')

@app.route('/api/payment/create', methods=['POST'])
def create_payment():
    """Create a new payment request"""
    try:
        data = request.json
        
        # Validate input
        required_fields = ['amount', 'currency', 'user_id', 'order_id']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Get token contract if not BNB
        token_contract = None
        decimals = 18
        
        if data['currency'].upper() != 'BNB':
            # currency_map = {
            #     'USDT': app.config['USDT_CONTRACT'],
            #     'USDC': app.config['USDC_CONTRACT'],
            #     'BUSD': app.config['BUSD_CONTRACT']
            # }
            
            currency_map = app.config['BSC_TESTNET_TOKENS'] # use testnet tokens

            token_contract = currency_map.get(data['currency'].upper())
            if not token_contract:
                return jsonify({'error': 'Unsupported currency'}), 400
            
            decimals = blockchain.get_token_decimals(token_contract)
        
        # Generate unique payment address
        payment_address, private_key = blockchain.generate_payment_address()
        
        # Encrypt and store private key
        encrypted_key = encryption.encrypt_key(private_key)
        db.store_payment_key(payment_address, encrypted_key)
        
        # Convert amount to Wei/smallest unit
        print(f"Converting amount: {data['amount']} with decimals: {decimals}")
        amount_wei = blockchain.to_wei(float(data['amount']), decimals)
        
        # Create payment document
        payment_data = {
            'payment_address': payment_address.lower(),
            'user_id': data['user_id'],
            'order_id': data['order_id'],
            'amount_expected': str(amount_wei),
            'amount_received': '0',
            'token_address': token_contract,
            'currency': data['currency'].upper(),
            'tx_hash': None,
            'from_address': None,
            'confirmations': 0,
            'status': 'pending',
            'confirmed_at': None,
            'expires_at': datetime.now() + timedelta(
                minutes=app.config['PAYMENT_TIMEOUT_MINUTES']
            ),
            'metadata': data.get('metadata', {})
        }
        
        payment_id = db.create_payment(payment_data)
        if payment_id:
            webhook.add_address_to_webhook(app.config['ALCHEMY_WEBHOOK_ID'], payment_address)

        logger.info(f"Created payment {payment_id} for order {data['order_id']}")
        return jsonify({
            'success': True,
            'payment': {
                'id': payment_id,
                'payment_address': payment_address,
                'amount': data['amount'],
                'amount_wei': str(amount_wei),
                'currency': data['currency'].upper(),
                'order_id': data['order_id'],
                'expires_at': payment_data['expires_at'].isoformat(),
                'qr_data': f"{payment_address}?amount={amount_wei}"
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating payment:{e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/webhook/alchemy', methods=['POST'])
def alchemy_webhook():
    """Handle Alchemy webhook notifications"""
    try:
        # Verify webhook signature
        signature = request.headers.get('X-Alchemy-Signature')
        
        if not tools.verify_alchemy_signature(request.data, signature):
            return jsonify({'error': 'Invalid signature'}), 401
        
        data = request.json
        print(data)
        
        # Process webhook event
        if data['type'] == 'ADDRESS_ACTIVITY':
            tools.process_transaction(data['event'])
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 500
    

@app.route('/api/payment/status/<order_id>', methods=['GET'])
def get_payment_status(order_id):
    """Get payment status"""
    payment = db.get_payment_by_order_id(order_id)
    
    if not payment:
        return jsonify({'error': 'Payment not found'}), 404
    
    # Check if expired
    if payment['status'] == 'pending' and datetime.now() > payment['expires_at']:
        db.update_payment(payment['payment_address'], {'status': 'expired'})
        payment['status'] = 'expired'
    
    # Get current balance if still pending
    if payment['status'] in ['pending', 'confirming']:
        if payment['token_address']:
            balance = blockchain.get_token_balance(
                payment['token_address'],
                payment['payment_address']
            )
        else:
            balance = blockchain.get_bnb_balance(payment['payment_address'])
        
        db.update_payment(payment['payment_address'], {
            'amount_received': str(balance)
        })
        payment['amount_received'] = str(balance)
    
    # Convert MongoDB ObjectId to string
    payment['_id'] = str(payment['_id'])
    
    return jsonify(payment), 200


@app.route('/api/payment/check-manual/<order_id>', methods=['POST','GET'])
def manual_check_payment(order_id):
    """Manually check payment status on blockchain"""
    payment = db.get_payment_by_order_id(order_id)
    
    if not payment:
        return jsonify({'error': 'Payment not found'}), 404
    
    # Check balance
    if payment['token_address']:
        balance = blockchain.get_token_balance(
            payment['token_address'],
            payment['payment_address']
        )
        decimals = blockchain.get_token_decimals(payment['token_address'])
    else:
        balance = blockchain.get_bnb_balance(payment['payment_address'])
        decimals = 18
    
    update_data = {'amount_received': str(balance)}
    
    # Update status if sufficient
    if balance >= int(payment['amount_expected']):
        if payment['status'] == 'pending':
            update_data['status'] = 'confirming'
        
        # If we have a tx_hash, check confirmations
        if payment.get('tx_hash'):
            tx_info = blockchain.get_transaction(payment['tx_hash'])
            if tx_info:
                update_data['confirmations'] = tx_info['confirmations']
                
                if tx_info['confirmations'] >= app.config['CONFIRMATIONS_REQUIRED']:
                    update_data['status'] = 'confirmed'
                    update_data['confirmed_at'] = datetime.now()
                    
                    db.update_payment(payment['payment_address'], update_data)
                    payment.update(update_data)
                    
                    tools.process_successful_payment(payment)
                    tools.sweep_payment_funds(payment)
    
    db.update_payment(payment['payment_address'], update_data)
    payment.update(update_data)
    
    # Convert MongoDB ObjectId to string
    payment['_id'] = str(payment['_id'])
    
    return jsonify({
        'success': True,
        'payment': payment,
        'balance_human': blockchain.to_human_readable(balance, decimals)
    }), 200


@app.route('/api/payments/user/<int:user_id>', methods=['GET'])
def get_user_payments(user_id):
    """Get all payments for a user"""
    limit = request.args.get('limit', 50, type=int)
    payments = db.get_payments_by_user(user_id, limit)
    
    # Convert ObjectIds to strings
    for payment in payments:
        payment['_id'] = str(payment['_id'])
    
    return jsonify({
        'success': True,
        'payments': payments,
        'count': len(payments)
    }), 200


@app.route('/api/payments/stats', methods=['GET'])
def get_payment_stats():
    """Get payment statistics"""
    user_id = request.args.get('user_id', type=int)
    stats = db.get_payment_stats(user_id)
    
    return jsonify({
        'success': True,
        'stats': stats
    }), 200


@app.route('/api/payments/pending', methods=['GET'])
def get_pending_payments():
    """Get all pending payments (admin endpoint)"""
    # Add authentication middleware in production
    payments = db.get_pending_payments()
    
    # Convert ObjectIds to strings
    for payment in payments:
        payment['_id'] = str(payment['_id'])
    
    return jsonify({
        'success': True,
        'payments': payments,
        'count': len(payments)
    }), 200



if __name__ == '__main__':
    scheduler.start()
    try:
        app.run(debug=True, port=5000)
    except (KeyboardInterrupt, SystemExit):
        scheduler.stop()