from cryp import Cryp

from flask import Flask, request, jsonify, render_template
import os
import logging
import sys
from pathlib import Path

app = Flask(__name__)


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

cryp = Cryp(mode='mainnet')

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
        res = cryp.create_payment(data)
        if res['success']:
            return jsonify(res), 201

    except Exception as e:
        logger.error(f"Error creating payment:{e}")
        return jsonify({'error': str(e)}), 500
    

@app.route('/api/webhook/alchemy', methods=['POST'])
def alchemy_webhook():
    """Handle Alchemy webhook notifications"""
    try:
        # Verify webhook signature
        signature = request.headers.get('X-Alchemy-Signature')
        
        if not cryp.tools.verify_alchemy_signature(request.data, signature):
            return jsonify({'error': 'Invalid signature'}), 401
        
        data = request.json
        print(data)
        
        # Process webhook event
        if data['type'] == 'ADDRESS_ACTIVITY':
            cryp.tools.process_transaction(data['event'])
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/payment/status/<order_id>', methods=['GET'])
def get_payment_status(order_id):
    """Get payment status"""
    try:
        res = cryp.get_payment_status(order_id)
        if res['success']:
            return jsonify(res['payment']), 200 
    except Exception as e:
        logger.error(f"Error getting payment status: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    cryp.scheduler.start()
    try:
        app.run(debug=True, port=5000)
    except (KeyboardInterrupt, SystemExit):
        cryp.scheduler.stop()