import hashlib, binascii

data = (str(22) + str("asd"))
if type(data) is not bytes:
    data = data.encode()

yes_link_hash = hashlib.pbkdf2_hmac('sha256', data, b"satisfaction", 100000)
yes_link = binascii.hexlify(yes_link_hash).decode()
print(len(yes_link))