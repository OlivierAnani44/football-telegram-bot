from pyrogram import Client

API_ID = 1234567       # ton API_ID
API_HASH = "abcdef..." # ton API_HASH

app = Client("user_session", api_id=API_ID, api_hash=API_HASH)

app.run()
