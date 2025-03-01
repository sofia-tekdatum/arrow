"""
parquet_playground.py

Use dummy encryption keys to test out parquet formats and encryption options.
Important!! Using the write/read functions in parquet that receive the encryption and
decryption properties, as this is where the new code will be called, within the pyarrow
libraries that receive parquet column chunks and *then* encrypt/decrypt.

TODO!! Define location and behavior of new call. What args will it have? How will we auth the
caller can decrypt the file contents?

@author sbrenes
"""

import base64
import datetime
import pyarrow
import pyarrow.parquet as pp
import pyarrow.parquet.encryption as ppe


class FooKmsClient(ppe.KmsClient):

    def __init__(self, kms_connection_config):
        ppe.KmsClient.__init__(self)
        self.master_keys_map = kms_connection_config.custom_kms_conf
    
    def wrap_key(self, key_bytes, master_key_identifier):
        master_key_bytes = self.master_keys_map[master_key_identifier].encode('utf-8')
        joint_key = b"".join([master_key_bytes, key_bytes])
        return base64.b64encode(joint_key)

    def unwrap_key(self, wrapped_key, master_key_identifier):
        expected_master = self.master_keys_map[master_key_identifier]
        decoded_key = base64.b64decode(wrapped_key)
        master_key_bytes = decoded_key[:16]
        decrypted_key = decoded_key[16:]
        if (expected_master == master_key_bytes.decode('utf-8')):
            return decrypted_key
        raise ValueError(f"Bad master key used [{master_key_bytes}] - [{decrypted_key}]")



def kms_client_factory(kms_connection_config):
    return FooKmsClient(kms_connection_config)


def write_parquet(table, location, encryption_config=None):
    encryption_properties = None

    if encryption_config:
        crypto_factory = ppe.CryptoFactory(kms_client_factory)
        encryption_properties = crypto_factory.file_encryption_properties(
            get_kms_connection_config(), encryption_config)

    writer = pp.ParquetWriter(location, table.schema, encryption_properties=encryption_properties)
    writer.write_table(table)


def encrypted_data_and_footer_sample(data_table):
    parquet_path = "sample.parquet"
    encryption_config = get_encryption_config()
    write_parquet(data_table, parquet_path,
                  encryption_config=encryption_config)
    print(f"Written to [{parquet_path}]")


def create_and_encrypt_parquet():
    sample_data = {
        "orderId": [1001, 1002, 1003],
        "productId": [152, 268, 6548],
        "price": [3.25, 6.48, 2.12],
        "vat": [0.0, 0.2, 0.05]
    }    
    data_table = pyarrow.Table.from_pydict(sample_data)

    print("\nPyarrow table created. Writing parquet.")

    encrypted_data_and_footer_sample(data_table)

    print("\nPlayground finished!\n")


def get_kms_connection_config():
    return ppe.KmsConnectionConfig(
        custom_kms_conf={
            "footer_key": "012footer_secret",
            "orderid_key": "column_secret001",
            "productid_key": "column_secret002"
        }
    )


def get_encryption_config(plaintext_footer=False):
    return ppe.EncryptionConfiguration(
        footer_key = "footer_key",
        column_keys = {
            "orderid_key": ["orderId"],
            "productid_key": ["productId"]
        },
        encryption_algorithm = "AES_GCM_V1",
        cache_lifetime=datetime.timedelta(minutes=2.0),
        data_key_length_bits = 128,
        plaintext_footer=plaintext_footer
    )


if __name__ == "__main__":
    create_and_encrypt_parquet()
