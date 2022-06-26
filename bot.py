import steam
from decouple import config
import requests
import json
import ipfshttpclient
import os
import web3
from eth_abi import is_encodable
from eth_abi.packed import encode_single_packed
from eth_account.messages import defunct_hash_message
from eth_account.account import Account
import eth_utils
from datetime import timedelta
import time


# Insert your own https://steamapis.com API key
steam_apikey = config("steam_apikey")

# Insert your own private key to sign messages
privatekey = config("private_key")


def create_metadata(data, asset_link, cooldown):
    metadata = {}
    attributes = []
    print('Creating metadata')
    print(data)

    # Fetches the correct description of asset in JSON data
    metadata['description'] = data['assets']['descriptions'][0]['value']
    for text in data['assets']['descriptions'][:-1]:
        value = text['value']
        if len(value) > len(metadata['description']):
            metadata['description'] = value

    metadata['external_url'] = asset_link
    metadata['image'] = data['image']
    metadata['name'] = data['market_hash_name']

    # Append the asset type
    attributes.append({"trait_type": "Asset Type", "value": data['assetInfo']['type']})

    # Attributes nested
    for tag in data['assetInfo']['tags']:
        attribute = {}
        attribute['trait_type'] = str(tag['category_name'])
        attribute['value'] = str(tag['name'])
        attributes.append(attribute)

    # Cooldown attribute
    attributes.append({"display_type": "date", "trait_type": "Cooldown", "value": cooldown})

    # Game attribute
    attributes.append({"trait_type": "Game", "value": data['description']})

    metadata['attributes'] = attributes

    # TODO: Improve upload of metadata without creating "data.json" file
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)

    # In order to make the ipfshttpclient packet work with new versions of ipfs:
    # go to __init__.py and change VERSION_MAXIMUM to "0.14.0"
    client = ipfshttpclient.connect()  # Connects to: /dns/localhost/tcp/5001/http
    res = client.add('data.json')
    os.remove('data.json')
    hash = res['Hash']

    return hash


def sign_confirmation(cooldown, uri):
    hash = solidityKeccak(abi_types=['uint256', 'string'], values=[cooldown, uri], validity_check=True)
    test = "0x" + hash.hex()
    signed_msg_hash = Account.signHash(test, privatekey)
    return signed_msg_hash.signature.hex()


def solidityKeccak(abi_types, values, validity_check=False):
    """
    Executes keccak256 exactly as Solidity does.
    Takes list of abi_types as inputs -- `[uint24, int8[], bool]`
    and list of corresponding values  -- `[20, [-1, 5, 0], True]`

    Adapted from web3.py
    """
    if len(abi_types) != len(values):
        raise ValueError(
            "Length mismatch between provided abi types and values.  Got "
            "{0} types and {1} values.".format(len(abi_types), len(values))
        )
    if validity_check:
        for t, v in zip(abi_types, values):
            if not is_encodable(t, v):
                print(f'Value {v} is not encodable for ABI type {t}')
                return False
    hex_string = eth_utils.add_0x_prefix(''.join(
        encode_single_packed(abi_type, value).hex()
        for abi_type, value
        in zip(abi_types, values)
    ))
    # hex_string = encode_abi_packed(abi_types, values).hex()
    return eth_utils.keccak(hexstr=hex_string)


class MyClient(steam.Client):
    market_hash_name = ""

    async def on_ready(self) -> None:
        print("Logged in as", self.user)

    async def on_trade_receive(self, trade: steam.TradeOffer) -> None:
        # Make sure trade is a gift, only one item and address in message is valid
        if trade.is_gift() and len(trade.items_to_receive) == 1:
            print(f"Accepting trade: #{trade.id}")
            self.market_hash_name = str(trade.items_to_receive[0].name)
            await trade.accept()
        else:
            print(f"Rejecting trade: #{trade.id}")
            await trade.decline()

    async def on_trade_accept(self, trade: steam.TradeOffer):  # we accepted a trade
        print(f"Accepted trade: #{trade.id}")
        items_received = trade.items_to_receive
        appid = items_received[0].game.id
        contextid = items_received[0].game.context_id
        asset_id = items_received[0].asset_id
        asset_link = 'https://steamcommunity.com/profiles/{}/inventory/#{}_{}_{}'.format(self.user.id64, appid, contextid, asset_id)

        url = 'https://api.steamapis.com/market/item/{}/{}?api_key={}'.format(appid, self.market_hash_name, steam_apikey)
        data = requests.get(url=url).json()

        cooldown_url = 'https://api.steamapis.com/steam/inventory/{}/{}/{}?api_key={}'.format(self.user.id64, appid, contextid, steam_apikey)
        cooldown_data = requests.get(url=cooldown_url).json()
        cooldown_fetch = cooldown_data['descriptions'][0]['market_tradable_restriction'] + 1
        cooldown = round(time.time() + (86400 * cooldown_fetch))

        ipfs_hash = create_metadata(data, asset_link, cooldown)

        signature = sign_confirmation(cooldown, ipfs_hash)
        mint_link = "http://localhost:8080/?name={}&hash={}&cooldown={}&signature={}".format(self.market_hash_name, ipfs_hash, cooldown, signature)
        print(mint_link)
        await trade.partner.send("Asset ({}) ready to mint: {}".format(self.market_hash_name, mint_link))


client = MyClient()
client.run(config("steam_username"), config("steam_password"))
