import asyncio
import aiosqlite
import re
import simplejson as json
from aiohttp import web, ClientSession

client_id = '6610748'
client_secret = 'GWE5bmNjlCHchKgbfXgE'
bot_id = '344603315:AAHs9sHfDvoYpWFAqLqQiUAJ03xEyi8DdHM'
database = 'db.db'
period_time = 180
per_page = 10
max_groups = 100

main_url = 'https://api.telegram.org/bot' + bot_id

async def fetch(url, session, id = None):
    async with session.get(url) as response:
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

async def media_group(media, chat_id):
    return main_url + "/sendMediaGroup?chat_id=" + str(chat_id) + "&media=" + json.dumps(media)

async def update_inline_keyboard(text, buttons, mess_id, chat_id):
    inline_k = {'inline_keyboard': buttons}
    return main_url + "/editMessageText?chat_id=" + str(chat_id) + "&message_id=" + str(mess_id) + "&text=" + text + "&reply_markup=" + json.dumps(inline_k)

async def send_photo(url, chat_id, text=None):
    url_ = main_url + '/sendPhoto?chat_id=' + str(chat_id) + '&photo=' + url
    if text:
        url_ += ('&caption=' + text)
    return url_

async def input_media(media, type_='photo', text=None):
    if text:
        return {'type': type_, 'media': media, 'caption': text}
    else:
        return {'type': type_, 'media': media}

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

async def get_token_from_url(url):
    ttoken = re.search(r'access_token=([a-z0-9]+)', url)
    if ttoken:
        return ttoken.group(1)
    else:
        None

async def get_token_from_code(url):
    ttoken = re.search(r'code=([a-z0-9]+)', url)
    if ttoken:
        code = ttoken.group(1)
        auth_res = await get('https://oauth.vk.com/access_token?client_id=' + client_id + '&client_secret=' + client_secret + '&code=' + code)
        if 'access_token' in auth_res:
            return auth_res['access_token']
    return None

async def get_vk_users():
    async with aiosqlite.connect(database) as db:
        users = await (await db.execute('select * from users')).fetchall()
        feed_u = {}
        for user in users:
            groups = [str(-gr[0]) for gr in await (await db.execute('select group_id from groups where id = ?', [user[0]])).fetchall()]
            if len(groups) > 0:
                feed_u[user[0]] = {'token': user[1], 'start_time': user[3], 'groups': ','.join(groups)}
        return feed_u

async def get_feeds():
    users = await get_vk_users()
    urls = [{'url': 'https://api.vk.com/method/newsfeed.get?access_token=' + users[user]['token'] + '&filters=post&start_time=' + str(users[user]['start_time'] + 1) + '&source_ids=' + users[user]['groups'] + '&count=100&v=5.8', 'id': user} for user in users]
    resps = await a_lot_of(urls, list=False)
    all_ = []
    async with aiosqlite.connect(database) as db:
        for resp in resps:
            user = resp['id']
            other = resp['response']
            groups = {gr['id']: {'name': gr['name'], 'login':gr['screen_name']} for gr in other['groups']}
            if len(other['items']) > 0:
                date = other['items'][0]['date']
                await db.execute('update users set last_time = ? where id = ?',[date, user])
                await db.commit()
            for item in other['items']:
                source = -item['source_id']
                attach = []
                print(item)
                for att in item['attachments']:
                    if att['type'] == 'photo':
                        max_res = 0
                        best_ = ''
                        for r in att['photo']:
                            if 'photo_' in r:
                                res = int(r.split('_')[1])
                                if res > max_res:
                                    max_res = res
                                    best_ = r
                        attach.append(att['photo'][best_])
                if len(attach) > 0:
                    all_.append({'id': user, 'pics': attach, 'group': groups[source]['name'], 'url': 'https://vk.com/' +  groups[source]['login'] + '?w=wall-' + str(source) + '_' + str(item['post_id'])})
    return all_

async def send_feeds():
    feeds = await get_feeds()
    urls = []
    for feed in feeds:
        if len(feed['pics']) > 1:
            media = [await input_media(pic, text='[' + feed['group'] + '](' + feed['url'] + ')') for pic in feed['pics']]
            urls.append(await media_group(media, feed['id']))
        else:
            urls.append(await send_photo(feed['pics'][0], feed['id'], text='[' + feed['group'] + '](' + feed['url'] + ')'))
    await a_lot_of(urls)
    
async def get_groups(token, user_id = None):
    if user_id:
        groups_get_url = 'https://api.vk.com/method/groups.get?access_token=' + token + '&user_id=' + str(user_id) + '&extended=1&count=' + str(max_groups) + '&v=5.8'
    else:
        groups_get_url = 'https://api.vk.com/method/groups.get?access_token=' + token + '&extended=1&count=' + str(max_groups) + '&v=5.8'
    res_groups = (await get(groups_get_url))['response']
    return [{'id': gr['id'], 'name': gr['name']} for gr in res_groups['items']]
    
async def get_id(token):
    resp = await get('https://api.vk.com/method/users.get?access_token=' + token + '&v=5.8')
    if 'response' in resp:
        return resp['response'][0]['id']
    else:
        None

async def add_group(group, chat_id):
    async with aiosqlite.connect(database) as db:
        await db.execute('insert into groups(group_id, id) select ?, ? where not exists(select 1 from groups where group_id = ? and id =?)', [int(group), int(chat_id), int(group), int(chat_id)])
        await db.commit()

async def del_group(group, chat_id):
    async with aiosqlite.connect(database) as db:
        await db.execute('delete from groups where group_id = ? and id = ?', [int(group), int(chat_id)])
        await db.commit()

async def update(page, mess_id, chat_id):
    async with aiosqlite.connect(database) as db:
        norm = [oth[0] for oth in await (await db.execute('select group_id from groups where id = ?', [int(chat_id)])).fetchall()]
        temp = await (await db.execute('select group_id, name from temp_groups where id = ? limit ? offset ?', [int(chat_id), per_page + 1, per_page * page])).fetchall()
        btns = []
        sup = await make_sup('&')
        for te in temp:
            if te[0] in norm:
                btns.append([await inline_button('✔ ' + sup(te[1]),'del_group ' + str(te[0]) + ' ' + str(page))])
            else:
                btns.append([await inline_button('✖ ' + sup(te[1]),'add_group ' + str(te[0]) + ' ' + str(page))])
        line = []
        if page > 0:
            line.append(await inline_button('<','page 0 ' + str(page - 1)))
        if len(btns) > per_page:
            btns = btns[:-1]
            line.append(await inline_button('>','page 0 ' + str(page + 1)))
        btns.append(line)
        await get(await update_inline_keyboard('Choose groups (page ' + str(page + 1) + ')', btns, mess_id, chat_id))

async def go_to_page(a,b):
    pass

c_commands = {'add_group': add_group,
              'del_group': del_group,
              'page': go_to_page}

async def callback(info):
    mess = info['message']
    chat_id = mess['chat']['id']
    mess_id = mess['message_id']
    command = info['data'].split()
    for com in c_commands:
        if com == command[0]:
            await c_commands[com](command[1], chat_id)
            await update(int(command[2]), mess_id, chat_id)

async def make_token(w, chat_id):
    if len(w) < 2: return
    token = await get_token_from_url(w[1])
    if token and await get_id(token):
        async with aiosqlite.connect(database) as db:
            await db.execute('insert or replace into users (id, token, last_call, last_time) values (?, ?, 0, 0)', [chat_id, token]) ##
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
            other = [oth[0] for oth in await (await db.execute('select group_id from groups where id = ?', [int(chat_id)])).fetchall()]
            btns = []
            sup = await make_sup('&')
            for gr in groups:
                await db.execute('insert into temp_groups (group_id, name, id) values (?, ?, ?)', [int(gr['id']), gr['name'], int(chat_id)])
                if gr['id'] in other:
                    btns.append([await inline_button('✔ ' + sup(gr['name']),'del_group ' + str(gr['id']) + ' 0')])
                else:
                    btns.append([await inline_button('✖ ' + sup(gr['name']),'add_group ' + str(gr['id']) + ' 0')])
            if len(btns) > per_page:
                btns = btns[:per_page]
                btns.append([await inline_button('>','page 0 1')])
            await db.execute('update users set last_call = ? where id = ?',[(await get(await inline_keyboard('Choose groups', btns, chat_id)))['result']['message_id'], chat_id])
            await db.commit()
            
async def start_text(q, chat_id):
    butn = [[await inline_button('Register url', url='oauth.vk.com/authorize?client_id=6610748?scope=wall,friends,offline,groups?response_type=token')]]
    await get(await inline_keyboard('Go to this link,\nafter passing on this page,\ncopy url and write command:\n/url COPIED_URL', butn, chat_id))
            
            
commands = {'/url': make_token,
            '/groups': choose_groups,
            '/start': start_text}

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
            await send_feeds() #
            await asyncio.sleep(period_time)
    app.loop.create_task(check(app))

routes = web.RouteTableDef()

@routes.get('/')
async def hello(request):
    print(request.path_qs)
    text = await send_feeds()
    return web.Response(text=str(text))

@routes.post('/hook')
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
        await db.execute('create table if not exists users (id integer primary key not null, token text not null, last_call integer not null, last_time integer not null)')
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

