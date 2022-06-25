import steam
from decouple import config
import requests
from datetime import timedelta


# Insert your own https://steamapis.com API key
steam_apikey = config("steam_apikey")


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

    return metadata


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
        # Make sure trade is a gift, only one item and address in message is valid
        if trade.is_gift() and len(trade.items_to_receive) == 1:
            print(f"Accepting trade: #{trade.id}")
            await trade.accept()
        else:
            print(f"Rejecting trade: #{trade.id}")
            await trade.decline()

    async def on_trade_accept(self, trade: steam.TradeOffer):  # we accepted a trade
        print(f"Accepted trade: #{trade.id}")
        await trade.accept()
        # TODO: Test if it works!
        escrow = process_escrow(self.user._state.http.get_user_escrow(self.user.id64, trade.token))
        items_received = trade.items_to_receive
        market_hash_name = items_received[0].name
        appid = items_received[0].game.id
        contextid = items_received[0].game.context_id
        asset_id = items_received[0].asset_id
        asset_link = 'https://steamcommunity.com/id/{}/inventory/#{}_{}_{}'.format(self.user, appid, contextid, asset_id)

        url = 'https://api.steamapis.com/market/item/{}/{}?api_key={}'.format(appid, market_hash_name, steam_apikey)
        data = requests.get(url=url).json()

        ipfs_hash = create_metadata(data, asset_link, escrow)

        await trade.partner.send("Asset ready to mint")


client = MyClient()
client.run(config("username"), config("password"))
