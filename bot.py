import steam
from decouple import config


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
        # TODO: Get received items and create a metadata from the asset to upload it to IPFS and then mint
        await trade.partner.send("Asset ready to mint")


client = MyClient()
client.run(config("username"), config("password"))
