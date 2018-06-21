import asyncio
import aiosqlite
import re
import simplejson as json
from aiohttp import web, ClientSession

client_id = '6610748'
client_secret = 'GWE5bmNjlCHchKgbfXgE'
bot_id = '344603315:AAHs9sHfDvoYpWFAqLqQiUAJ03xEyi8DdHM'
database = 'db.db'
period_time = 10

tt = 'bb15ed29c30ed28ffdb39afe0bf3f9ca6c1ef627585934dc217ffbd2fc01d44de82652d87f6c95ea3a80c'

main_url = 'https://api.telegram.org/bot' + bot_id

async def fetch(url, session, id = None):
    async with session.get(url) as response: #Delete proxy proxy="http://129.213.76.9:3128"
        res_json = await response.json()
        if id: res_json['id'] = id
        return res_json

async def msg(text, chat_id):
    return main_url + '/sendMessage?chat_id=' + str(chat_id) + '&text=' + text

async def del_msg(mess_id, chat_id):
    return main_url + '/deleteMessage?chat_id=' + str(chat_id) + '&message_id=' + str(mess_id)

async def buttonbar(text, buttons, one_time, chat_id):
    buttonb = {'keyboard': buttons, 'one_time_keyboard': one_time, 'force_reply': True}
    return main_url + "/sendMessage?chat_id=" + str(chat_id) + "&text=" + text + "&reply_markup=" + json.dumps(buttonb)

async def inline_keyboard(text, buttons, chat_id):
    inline_k = {'inline_keyboard': buttons}
    return main_url + "/sendMessage?chat_id=" + str(chat_id) + "&text=" + text + "&reply_markup=" + json.dumps(inline_k)

async def update_inline_keyboard(text, buttons, mess_id, chat_id):
    inline_k = {'inline_keyboard': buttons}
    return main_url + "/editMessageText?chat_id=" + str(chat_id) + "&message_id=" + str(mess_id) + "&text=" + text + "&reply_markup=" + json.dumps(inline_k)

async def inline_button(text, callback_data=None, url=None):
    if callback_data:
        return {'text': text, 'callback_data': callback_data}
    elif url:
        return {'text': text, 'url': url}
    else: None

async def make_sup(sup):
    return lambda s: ''.join([' ' if c in sup else c for c in s])

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
        groups_get_url = 'https://api.vk.com/method/groups.get?access_token=' + token + '&user_id=' + str(user_id) + '&extended=1&count=1000&v=5.8'
    else:
        groups_get_url = 'https://api.vk.com/method/groups.get?access_token=' + token + '&extended=1&count=1000&v=5.8'
    res_groups = (await get(groups_get_url))['response']
    return [{'id': gr['id'], 'name': gr['name']} for gr in res_groups['items']]
    
async def get_id(token):
    return (await get('https://api.vk.com/method/users.get?access_token=' + token + '&v=5.8'))['response'][0]['id']

async def add_group(group, chat_id):
    async with aiosqlite.connect(database) as db:
        await db.execute('insert or ignore into groups (group_id, id) values (?, ?)', [int(group), int(chat_id)])
        await db.commit()

async def del_group(group, chat_id):
    async with aiosqlite.connect(database) as db:
        await db.execute('delete from groups where group_id = ? and id = ?', [int(group), int(chat_id)])
        await db.commit()

async def update(mess_id, chat_id):
    async with aiosqlite.connect(database) as db:
        norm = [oth[0] for oth in await (await db.execute('select group_id from groups where id = ?', [int(chat_id)])).fetchall()]
        temp = await (await db.execute('select group_id, name from temp_groups where id = ?', [int(chat_id)])).fetchall()
        btns = []
        sup = await make_sup('&')
        for te in temp:
            if te[0] in norm:
                btns.append([await inline_button('✔ ' + sup(te[1]),'del_group ' + str(te[0]))])
            else:
                btns.append([await inline_button('✖ ' + sup(te[1]),'add_group ' + str(te[0]))])
        while len(str(btns)) > 4000: #Max 4096
            btns = btns[:-1]
        await get(await update_inline_keyboard('Choose groups', btns, mess_id, chat_id))
    

c_commands = {'add_group': add_group,
              'del_group': del_group}

async def callback(info):
    mess = info['message']
    chat_id = mess['chat']['id']
    mess_id = mess['message_id']
    command = info['data'].split()
    for com in c_commands:
        if com == command[0]:
            await c_commands[com](command[1], chat_id)
            await update(mess_id, chat_id)

async def make_token(w, chat_id):
    token = await get_token(w[1])
    if token:
        async with aiosqlite.connect(database) as db:
            await db.execute('insert into users (id, token, last_call) values (?, ?, 0)', [chat_id, token]) ##
            await db.commit()
        await get(await msg('Succefull registered!' , chat_id))
    else:
        await get(await msg('Error...' , chat_id))

async def choose_groups(w, chat_id):
    async with aiosqlite.connect(database) as db:
        resp = await (await db.execute('select token, last_call from users where id = ?', [int(chat_id)])).fetchone()
        if resp:
            if resp[1] != 0:
                await get(await del_msg(resp[1], chat_id))
            token = resp[0]
            if await (await db.execute('select * from temp_groups where id = ?', [int(chat_id)])).fetchone():
                await db.execute('delete from temp_groups where id = ?', [int(chat_id)])
            groups = await get_groups(token)
            if len(groups) >= 99: groups = groups[:100]
            other = [oth[0] for oth in await (await db.execute('select group_id from groups where id = ?', [int(chat_id)])).fetchall()]
            btns = []
            sup = await make_sup('&')
            for gr in groups:
                await db.execute('insert into temp_groups (group_id, name, id) values (?, ?, ?)', [int(gr['id']), gr['name'], int(chat_id)])
                if gr['id'] in other:
                    btns.append([await inline_button('✔ ' + sup(gr['name']),'del_group ' + str(gr['id']))])
                else:
                    btns.append([await inline_button('✖ ' + sup(gr['name']),'add_group ' + str(gr['id']))])
            while len(str(btns)) > 4000: #Max 4096
                btns = btns[:-1]
            await db.execute('update users set last_call = ? where id = ?',[(await get(await inline_keyboard('Choose groups', btns, chat_id)))['result']['message_id'], chat_id])
            await db.commit()
            
                        
            
            
commands = {'/url': make_token,
            '/groups': choose_groups}

async def message(info):
    chat_id = info['chat']['id']
    if 'text' in info:
        words = info['text'].split()
        command = words[0].split('@')[0]
        for com in commands:
            if com == command:
                await commands[com](words, chat_id)
                break

async def period(app):
    async def check(app):
        while True:
            print(1) #
            await asyncio.sleep(period_time)
    app.loop.create_task(check(app))
    
routes = web.RouteTableDef()

t = {'update_id': 183002059, 'message': {'message_id': 16, 'from': {'id': 361959653, 'is_bot': False,
                                                                    'first_name': 'DALOR', 'username': 'dalor_dandy', 'language_code': 'ru-RU'},
                                         'chat': {'id': 361959653, 'first_name': 'DALOR', 'username': 'dalor_dandy', 'type': 'private'},
                                         'date': 1529529738, 'text': '/groups', 'entities': [{'offset': 0, 'length': 7, 'type': 'bot_command'}]}}

q = {'update_id': 183002060, 'callback_query': {'id': '1554604873915593667', 'from': {'id': 361959653, 'is_bot': False, 'first_name': 'DALOR',
                                                                                      'username': 'dalor_dandy', 'language_code': 'ru-RU'},
                                                'message': {'message_id': 39, 'from': {'id': 344603315, 'is_bot': True, 'first_name': 'VK feed',
                                                                                       'username': 'vkfeeddbot'}, 'chat': {'id': 361959653, 'first_name': 'DALOR',
                                                                                                                           'username': 'dalor_dandy', 'type': 'private'},
                                                            'date': 1529525191, 'text': 'Control'}, 'chat_instance': '-6570528492679530023', 'data': 'add_group 101550564'}}
@routes.get('/')
async def hello(request):
    print(request.path_qs) #
    #print(await get_id(tt))
    #text = str(await get_groups(tt))
    #text = str(await get_token('https://oauth.vk.com/blank.html#code=399e16b7eb9815633b'))
    #btn = [[await inline_button(i,i)] for i in range(1,5)]
    #text = await get(await inline_keyboard('Control',btn,361959653))
    #await message(t['message'])
    #await callback(q['callback_query'])
    return web.Response(text='123')

@routes.post('/hook') #get change
async def webhook(request):
    res_json = await request.json()
    print(res_json)
    if 'callback_query' in res_json:
        await callback(res_json['callback_query'])
    elif 'message' in res_json:
        await message(res_json['message'])
    elif 'channel_post' in res_json:
        await message(res_json['channel_post'])
    return web.Response(status=200)

async def create_database(app):
    async with aiosqlite.connect(database) as db:
        await db.execute('create table if not exists users (id integer not null, token text not null, last_call integer not null)')
        await db.execute('create table if not exists groups (group_id integer not null, id integer not null)')
        await db.execute('create table if not exists temp_groups (group_id integer not null, name text not null, id integer not null)')
        await db.commit()


async def web_app():
    app = web.Application()
    app.on_startup.append(create_database)
    app.on_startup.append(period)
    app.add_routes(routes)
    return app

if __name__ == '__main__':
    app = web_app()
    web.run_app(app)

