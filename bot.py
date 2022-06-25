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


# Insert your own https://steamapis.com API key
steam_apikey = config("steam_apikey")

# Insert your own private key to sign messages
privatekey = config("private_key")


def create_metadata(data, asset_link, escrow):
    metadata = {}
    attributes = []

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

    # Escrow attribute
    attributes.append({"display_type": "date", "trait_type": "Escrow", "value": escrow})

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


def sign_confirmation(escrow, uri):
    hash = solidityKeccak(abi_types=['uint256', 'string'], values=[escrow, uri], validity_check=True)
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


async def process_escrow(resp):
    their_escrow = resp["response"].get("their_escrow")
    if their_escrow is None:  # private
        return None
    seconds = their_escrow["escrow_end_duration_seconds"]
    return timedelta(seconds=seconds) if seconds else None


class MyClient(steam.Client):
    async def on_ready(self) -> None:
        print("Logged in as", self.user)

    async def on_trade_receive(self, trade: steam.TradeOffer) -> None:
        # <Item name='UMP-45 | Mudder (Field-Tested)' amount=1 class_id=3035567899 asset_id=17467254332 instance_id=302028390 owner=<User name='OnlyDallas' state=<PersonaState.Online: 1> id=126126521 type=<Type.Individual: 1> universe=<Universe.Public: 1> instance=1> game=StatefulGame(name=None, id=730, context_id=2)>

        # Make sure trade is a gift, only one item and address in message is valid
        # if trade.is_gift() and len(trade.items_to_receive) == 1:
        if len(trade.items_to_receive) == 1:
            print(f"Accepting trade: #{trade.id}")
            await trade.accept()
        else:
            print(f"Rejecting trade: #{trade.id}")
            await trade.decline()

    async def on_trade_accept(self, trade: steam.TradeOffer):  # we accepted a trade
        print(f"Accepted trade: #{trade.id}")
        # TODO: Test if it works!
        escrow = process_escrow(self.user._state.http.get_user_escrow(self.user.id64, trade.token))
        items_received = trade.items_to_receive
        market_hash_name = items_received[0].name
        appid = items_received[0].game.id
        contextid = items_received[0].game.context_id
        asset_id = items_received[0].asset_id
        asset_link = 'https://steamcommunity.com/id/{}/inventory/#{}_{}_{}'.format(self.user, appid, contextid, asset_id)
        url = 'https://api.steamapis.com/market/item/{}/{}?api_key={}'.format(appid, market_hash_name, steam_apikey)
        print(url)
        data = requests.get(url=url).json()

        ipfs_hash = create_metadata(data, asset_link, escrow)

        signature = sign_confirmation(escrow, ipfs_hash)
        mint_link = "http://localhost:8080/?name={}&hash={}&escrow={}&signature={}".format(market_hash_name, ipfs_hash, escrow, signature)

        await trade.partner.send("Asset ({}) ready to mint: {}".format(market_hash_name, mint_link))


client = MyClient()
client.run(config("steam_username"), config("steam_password"))
