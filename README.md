# Cryp Payment

A cryptocurrency payment processing system for Binance Smart Chain (BSC).

## Features

- 🔐 Secure payment address generation
- 💰 Multi-token support (BNB, USDT, BUSD, USDC)
- 📊 Real-time payment tracking
- ⏰ Automatic payment expiration
- 🔔 Webhook notifications via Alchemy
- 🔒 Encrypted private key storage

## Installation

### From PyPI (once published)
```bash
pip install cryp-payment
```

### From source
```bash
git clone https://github.com/wolfgang-99/cryp-payment.git
cd cryp-payment
pip install -e .
```

## Quick Start

```python
from cryp import Cryp

# Initialize Cryp
cryp = Cryp()

# Create a payment
payment_data = {
    'amount': 100.0,
    'currency': 'BNB',
    'user_id': 'user123',
    'order_id': 'order456'
}

result = cryp.create_payment(payment_data)
if result['result']:
    print(f"Payment address: {result['payment']['payment_address']}")

# Check payment status
status = cryp.get_payment_status('order456')
print(f"Payment status: {status}")
```

## Configuration

Create a `.env` file in your project root:

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=cryp-payment
BSC_TESTNET_RPC_URL=https://data-seed-prebsc-1-s1.bnbchain.org:8545
BSC_RPC_URL=https://bsc-dataseed.binance.org/
MAIN_WALLET=your-BSC-wallet address
PAYMENT_PRIVATE_KEY=your-wallet-private-key
ENCRYPTION_KEY=your-32-byte-encryption-key
ALCHEMY_AUTH_TOKEN=your-alchemy-token
ALCHEMY_WEBHOOK_ID=your-webhook-id
PAYMENT_TIMEOUT_MINUTES=30
```

## Generating ENCRYPTION KEY
create an `ENCRYPTION_KEY` by entering the promot in your terminal:

#### Linux
```bash
python3 -c "import base64; from cryptography.fernet import Fernet; print(base64.b64encode(Fernet.generate_key()).decode())"
```
#### Windows
```bash
python -c "import base64; from cryptography.fernet import Fernet; print(base64.b64encode(Fernet.generate_key()).decode())"
```

## Documentation

Full documentation is available at [Read the Docs](https://cryp-payment.readthedocs.io).

## Development

### Setup Development Environment

```bash
git clone https://github.com/wolfgang-99/cryp-payment.git
cd cryp-payment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/cryp tests
flake8 src/cryp tests
mypy src/cryp
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions, please open an issue on [GitHub](https://github.com/wolfgang-99/cryp-payment/issues).
