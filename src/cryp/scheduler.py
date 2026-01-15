from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from logging import getLogger

from .database import MongoDB
from .blockchain import BlockchainService
from .tool import Tool
from .config import Config

logger = getLogger(__name__)

class Scheduler:
    def __init__(self, config:Config, blockchain:BlockchainService, database:MongoDB, tool:Tool):
        self.blockchain = blockchain
        self.db = database
        self.tool = tool
        self.config = config
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            func= self.check_confirming_payments,
            trigger=IntervalTrigger(seconds=15),  # Run every 15 seconds
            id='confirmation_checker',
            name='Check payment confirmations',
            replace_existing=True
            )
    
    def check_confirming_payments(self):
        """Check all confirming payments for sufficient confirmations"""
        try:
            print("check confirming payment ....")
            confirming_payments = list(self.db.payments.find({
                    'status': 'confirming',
                    'tx_hash': {'$ne': None}
                }).limit(50))
                
            for payment in confirming_payments:
                    tx_info = self.blockchain.get_transaction(payment['tx_hash'])
                    
                    
                    if not tx_info:
                        continue
                    
                    confirmations = tx_info['confirmations']
                    
                    update_data = {'confirmations': confirmations}
                    
                    if confirmations >= self.config.CONFIRMATIONS_REQUIRED:
                        update_data['status'] = 'confirmed'
                        update_data['confirmed_at'] = datetime.now()
                        
                        self.db.update_payment(payment['payment_address'], update_data)
                        payment.update(update_data)
                        
                        logger.info('processing successful payment')
                        self.tool.process_successful_payment(payment)
                        self.tool.sweep_payment_funds(payment)
                    else:
                        self.db.update_payment(payment['payment_address'], update_data)
                        
        except Exception as e:
            logger.error(f"Error in confirmation checker: {e}")

    def start(self):
        self.scheduler.start()
        logger.info(" APScheduler started - checking confirmations every 15 seconds")

    
    def stop(self):
        self.scheduler.shutdown()
        logger.info("Shutting down scheduler.....")



