import hashlib
import hmac


# Function to create a sha256 signature
def create_sha256_signature(secret_key: str, params: str):

    # Encode the secret key
    byte_secret_key = bytearray()
    byte_secret_key.extend(map(ord, secret_key))

    # Encode the params
    encoded_params = params.encode()

    # Create signature
    return hmac.new(byte_secret_key, encoded_params, hashlib.sha256)\
        .hexdigest()
