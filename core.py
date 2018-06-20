import asyncio
import re
from aiohttp import web, ClientSession

client_id = '6610748'
client_secret = 'GWE5bmNjlCHchKgbfXgE'

period_time = 5

tt = 'bb15ed29c30ed28ffdb39afe0bf3f9ca6c1ef627585934dc217ffbd2fc01d44de82652d87f6c95ea3a80c'

async def fetch(url, session, id = None):
    async with session.get(url) as response: #Delete proxy
        res_json = await response.json()
        if id: res_json['id'] = id
        return res_json
    
async def a_lot_of(urls, list = True):
    async with ClientSession() as session:
        if list:
            tasks = [asyncio.ensure_future(fetch(url, session)) for url in urls]
        else:
            tasks = [asyncio.ensure_future(fetch(url['url'], session, url['id'])) for url in urls]
        return await asyncio.gather(*tasks)

async def get(url):
    async with ClientSession() as session:
        task = asyncio.ensure_future(fetch(url, session))
        return (await asyncio.gather(task))[0]

async def get_token(url):
    ttoken = re.search(r'code=([a-z0-9]+)', url)
    if ttoken:
        code = ttoken.group(1)
        auth_res = await get('https://oauth.vk.com/access_token?client_id=' + client_id + '&client_secret=' + client_secret + '&code=' + code)
        if 'access_token' in auth_res:
            return auth_res['access_token']
    return None

async def get_feeds():
    feed_url = None

async def get_groups(token, user_id = None):
    if user_id:
        groups_get_url = 'https://api.vk.com/method/groups.get?access_token=' + token + '&user_id=' + user_id + '&extended=1&count=1000&v=5.8'
    else:
        groups_get_url = 'https://api.vk.com/method/groups.get?access_token=' + token + '&extended=1&count=1000&v=5.8'
    res_groups = (await get(groups_get_url))['response']
    return [{'id': gr['id'], 'name': gr['name']} for gr in res_groups['items']]
    
async def get_id(token):
    return (await get('https://api.vk.com/method/users.get?access_token=' + token + '&v=5.8'))['response'][0]['id']

async def inline():
    pass

async def message():
    pass


async def period(app):
    async def check(app):
        while True:
            print(1) #
            await asyncio.sleep(period_time)
    app.loop.create_task(check(app))
    
routes = web.RouteTableDef()

@routes.get('/')
async def hello(request):
    print(request.path_qs) #
    #print(await get_id(tt))
    text = str(await get_groups(tt))
    #text = str(await get_token('https://oauth.vk.com/blank.html#code=399e16b7eb9815633b'))
    return web.Response(text=text)

@routes.post('/hook') #get change
async def webhook(request):
    res_json = await request.json()
    print(res_json)
    if 'inline_query' in res_json:
        await inline()
        print("In")
    elif 'message' in res_json or 'channel_post' in res_json:
        await message()
        print("Msg")
    return web.Response(status=200)

async def web_app():
    app = web.Application()
    app.on_startup.append(period)
    app.add_routes(routes)
    return app

if __name__ == '__main__':
    app = web_app()
    web.run_app(app)

