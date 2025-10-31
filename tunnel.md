the server should be able to create an ssh tunnel to an external server to be accessable from public URL

Additional config section for that:

```yaml
tunnel:
  - server: external-domain.com
  - public_key: path/to/public/key
  - private_key: path/to/private/key
```

If the config exist, during the launch, the first check is keys:

* checks if private and public files are exist. show the error in admin panel if only one exist
* if both does not exist - generate two ssh keys using cryptography module (without passphrasse). I think It should be something like that:

```python
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# Згенерувати пару
private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Приватний ключ у OpenSSH форматі (можна захистити passphrase)
private_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,  # або Encoding.OpenSSH
    format=serialization.PrivateFormat.OpenSSH,
    encryption_algorithm=serialization.BestAvailableEncryption(b"my-passphrase")  # або NoEncryption()
)

# Публічний ключ у OpenSSH форматі (рядок як в id_ed25519.pub)
public_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.OpenSSH,
    format=serialization.PublicFormat.OpenSSH
)

# Зберегти в файли
with open("id_ed25519", "wb") as f:
    f.write(private_bytes)
with open("id_ed25519.pub", "wb") as f:
    f.write(public_bytes + b" your_email@example.com\n")
```

* save those keys in the passed path (make sure you apply the special logic with binaries)
* if server do not pass - show the error in admin panel

Where everything is fine, and tunnel-config correct:

* show in admin panel in the list of connections server-name and connect button.
* start admin web socket - which mill be used to transmit ssh connection status

By clicking on connect button:
* in changes to "disconnect"
* download config from the server (the config includes instruction of how to connect) https://{server_name}/tunnel_config.yaml
* the config contains the followinf information:
  * username: SSH user for tunnel connections (tunneluser)
  * socket_directory: Path where socket files are stored (/var/run/tunnels)
  * base_url: HTTPS URL prefix for access local server. for example https://external-domain.com/tests/ (which means when the ssh connection is established wuth the filesocker fff123, then the URL for access is https://external-domain.com/tests/fff123/)
* create a filesocket connection using asyncio, asyncssh
* when the connection successfuly established - show the URL in the list of available URLs
