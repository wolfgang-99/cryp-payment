from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
from typing import Optional, Dict, List
from logging import getLogger

logger = getLogger(__name__)

class MongoDB:
    def __init__(self, uri: str, db_name: str):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self._setup_collections()
    
    def _setup_collections(self):
        """Setup collections and indexes"""
        # Payments collection
        self.payments = self.db.payments
        
        # Create indexes
        self.payments.create_index([("payment_address", ASCENDING)], unique=True)
        self.payments.create_index([("order_id", ASCENDING)], unique=True)
        self.payments.create_index([("user_id", ASCENDING)])
        self.payments.create_index([("tx_hash", ASCENDING)])
        self.payments.create_index([("status", ASCENDING)])
        self.payments.create_index([("created_at", DESCENDING)])
        
        # Payment keys collection (encrypted storage)
        self.payment_keys = self.db.payment_keys
        self.payment_keys.create_index([("payment_address", ASCENDING)], unique=True)
    
    def create_payment(self, payment_data: Dict) -> Optional[str]:
        """Create a new payment"""
        try:
            payment_data['created_at'] = datetime.now()
            payment_data['updated_at'] = datetime.now()
            
            result = self.payments.insert_one(payment_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error('Error creating payment: ' + str(e))
            return None
            
    def get_payment_by_address(self, address: str) -> Optional[Dict]:
        """Get payment by payment address"""
        try:
            payment = self.payments.find_one({'payment_address': address})
            return payment
        except Exception as e:
            logger.error('Error getting payment by address: ' + str(e))
            return None
    
    def get_payment_by_order_id(self, order_id: str) -> Optional[Dict]:
        """Get payment by order ID"""
        try:
            payment = self.payments.find_one({'order_id': order_id})
            return payment
        except Exception as e:
            logger.error(f'Error getting payment by order ID({order_id}): ' + str(e))
            return None
    
    def get_payment_by_tx_hash(self, tx_hash: str) -> Optional[Dict]:
        """Get payment by transaction hash"""
        try:
            payment = self.payments.find_one({'tx_hash': tx_hash})
            return payment
        except Exception as e:
            logger.error('Error getting payment by tx hash: ' + str(e))
            return None
    
    def get_payments_by_user(self, user_id: int, limit: int = 50) -> Optional[List[Dict]]:
        """Get payments by user ID"""
        try:
            payments = self.payments.find({'user_id': user_id}).sort('created_at', DESCENDING).limit(limit)
            return list(payments)
        except Exception as e:
            logger.error('Error getting user payment list: ' + str(e))
            return None
    
    def get_pending_payments(self) -> Optional[List[Dict]]:
        """Get all pending/confirming payments"""
        try:
            pending = self.payments.find({
                'status': {'$in': ['pending', 'confirming']},
                'expires_at': {'$gt': datetime.now()}
            })
            return list(pending)
        except Exception as e:
            logger.error('Error getting all pending/confirming payment : ' + str(e))
            return None
    
    def update_payment(self, payment_address: str, update_data: Dict) -> bool:
        """Update payment"""
        try:
            update_data['updated_at'] = datetime.now()
            
            result = self.payments.update_one(
                {'payment_address': payment_address},
                {'$set': update_data}
            )
            if result.modified_count > 0:
                return True
        except Exception as e:
            logger.error('Error updating payment: ' + str(e))
            return False
    
    def store_payment_key(self, address: str, encrypted_key: str)->bool:
        """Store encrypted private key"""
        try:
            res = self.payment_keys.insert_one({
                'payment_address': address,
                'encrypted_key': encrypted_key,
                'created_at': datetime.now()
            })
            if res:
                return True
        except Exception as e:
            logger.error('Error storing payment key: ' + str(e))
            return False
    
    def get_payment_key(self, address: str) -> Optional[str]:
        """Get encrypted private key"""
        try:
            doc = self.payment_keys.find_one({'payment_address': address})
            if doc:
                return doc['encrypted_key']
            else:
                logger.error("payment key not found in database")
                return None
        except Exception as e:
            logger.error('Error occured while retriving payment key ' +str(e))
            return None
    
    def delete_payment_key(self, address: str) -> bool:
        """Delete private key after sweeping"""
        try:
            result = self.payment_keys.delete_one({'payment_address': address})
            if result.deleted_count > 0:
                return True
        except Exception as e:
            logger.error('Error deleteing payment key: ' + str(e))
            return False
    
    def get_payment_stats(self, user_id: Optional[int] = None) -> Optional[Dict]:
        """Get payment statistics"""
        try:
            pipeline = []
            
            if user_id:
                pipeline.append({'$match': {'user_id': user_id}})
            
            pipeline.extend([
                {
                    '$group': {
                        '_id': '$status',
                        'count': {'$sum': 1},
                        'total_amount': {'$sum': {'$toDouble': '$amount_received'}}
                    }
                }
            ])
            
            results = list(self.payments.aggregate(pipeline))
            
            stats = {
                'total': 0,
                'confirmed': 0,
                'pending': 0,
                'expired': 0,
                'failed': 0
            }
            
            for result in results:
                stats[result['_id']] = result['count']
                stats['total'] += result['count']
            
            return stats
        except Exception as e:
            logger.error('Error getting payment statistics : ' + str(e))
            return None
