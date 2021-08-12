# This Python file uses the following encoding: utf-8
import requests, os, telebot, json, time, configparser

path = os.path.dirname(__file__)


config = configparser.ConfigParser()

configfile = os.path.join(path, 'settings.ini')
config.read(configfile)

bot_token = config['Telegram']['bot_token']
token = config['VK']['token']
channel = config['Telegram']['channel']
bitlytoken = config['bitly']['bitlytoken']

cpbgroups_file = os.path.join(path, 'cpbgroups.py')

config.read(cpbgroups_file)
groups = config.options('groups')

# Инициализируем телеграмм бота
bot = telebot.TeleBot(bot_token)

# получаем последние *count постов со стен групп вк
def get_wall_posts(group,count):
    count = count
    if group.isdigit():
        url = 'https://api.vk.com/method/wall.get?owner_id=-'+str(group)+'&count='+str(count)+'&access_token='+str(token)+'&v=5.52'
    else:
        url = 'https://api.vk.com/method/wall.get?domain='+str(group)+'&count='+str(count)+'&access_token='+str(token)+'&v=5.52'
    file = path + '/' + group + '.json'
    req = requests.get(url)
    src = req.json()

    with open(file, 'w+') as file:
        json.dump(src, file, ensure_ascii=False, indent=4)

# проверяем на критерии, сверяем с датой последнего обработанного, готовим под отправку
def check_wall_posts(group):
    file = path + '/' + group + '.json'
    # приняли из json данные выгрузки
    with open(file, 'r', encoding='utf-8') as file:
        src = json.load(file)
    if 'response' not in src.keys():

        if 'error' in src.keys():
            return src['error']['error_msg']
        else: return src.keys()

    posts = reversed(src['response']['items'])

    # дата публикации в юникс последнего обработанного поста, основной идентификатор
    postdate = int(config['groups'][group])
    # список дат публикации новых постов
    new_postdate = []
    # словарь готовых к отправке постов
    send_post = {}

    for post in posts:
        date = post['date']

        # если проверяемый пост моложе последнего проверенного поста
        if date > postdate:
            new_postdate.append(date)

            # если он еще и не репост
            if 'copy_history' not in post:
                send_post[date]={}

                # заносим в словарь, добавляем ссылку на оригинальный пост и подчищаем верстку
                send_post[date]['text'] = 'Ссылка на пост: '+'https://vk.com/wall' + str(post['from_id']) + '_' + str(post['id'])+'\n\n\n'+post['text']
                send_post[date]['text'] = (send_post[date]['text'].replace('\n \n', '\n')).replace('\n\n', '\n')

                # Проверяем есть ли что-то прикрепленное к посту
                if 'attachments' in post:
                    photos = []
                    videos = []
                    docs = []

                    for add in post['attachments']:

                        # если прикреп картинка
                        if add['type'] == 'photo':
                            send_post[date]['photo'] = []
                            photos.append(add)

                        # если прикреп видео
                        if add['type'] == 'video':
                            send_post[date]['video'] = []
                            videos.append(add)

                        # если прикреп файл
                        if add['type'] == 'doc':
                            send_post[date]['doc'] = []
                            docs.append(add)

                        # если прикреп ссылка
                        if add['type'] == 'link':
                            link = add['link']['url']
                            # сократили ссылку
                            data = json.dumps({"long_url": link})
                            bttoken='Bearer '+ bitlytoken
                            response = requests.post("https://api-ssl.bitly.com/v4/shorten",
                                                     data=data,
                                                     headers={'Authorization': bttoken})
                            src = response.json()
                            send_post[date]['link'] = src['link']

                        # если прикреп картинка - обработка массива
                        if len(photos) > 0:
                            img = photos[0]['photo']
                            addy = []
                            # ищем ссылку на наибольшее разрешение фото
                            for i in img:
                                if 'photo_' in i:
                                    y = i.lstrip('photo_')
                                    addy.append(y)
                            y = 'photo_'+ max(addy)
                            photo = img[y]
                            send_post[date]['photo'].append(photo)

                        # если прикреп видео - обработка массива
                        if len(videos) > 0:
                            video = videos[0]
                            owner_id = str(video['video']['owner_id'])
                            vid_id = str(video["video"]['id'])
                            access_key = str(video['video']['access_key'])
                            url = "https://vk.com/video"+owner_id+"_"+vid_id
                            send_post[date]['video'].append(url)

                        # если прикреп файл - обработка массива
                        for doc in docs:
                            dl = doc['doc']['url']
                            send_post[date]['doc'].append(dl)

    # здесь возвращаем док с постами, готовыми к отправке
    file = path + '/' + group + '-posts.json'
    with open(file, 'w+') as file:
        json.dump(send_post, file, ensure_ascii=False, indent=4)


    # #сохраняем в данных группы дату последнего обработанного поста
    olddate = str(postdate)
    if len(new_postdate)>0:
        newdate = str(max(new_postdate))
    else:
        newdate = olddate

    cpbgroup = path + '/' + 'cpbgroups.py'
    with open(cpbgroup, 'r') as vkgroups:
        inst = vkgroups.read()
    inst = inst.replace(olddate,newdate)

    with open(cpbgroup, 'w') as vkgroups:
        vkgroups.write(inst)

#отправляем посты в телеграм канал
def send_posts(group):

# В телеграмме есть ограничения на длину одного сообщения в 4091 символ, разбиваем длинные сообщения на части
    def split(text):
        message_breakers = ['\n']
        max_message_length = 4091

        if len(text) >= max_message_length:
            last_index = max(map(lambda separator: text.rfind(separator, 0, max_message_length), message_breakers))
            good_part = text[:last_index]
            bad_part = text[last_index + 1:]
            return [good_part] + split(bad_part)
        else:
            return [text]

    global channel

    # приняли из json данные выгрузки
    file = path + '/' + str(group)+'-posts.json'
    with open(file, 'r', encoding='utf-8') as file:
        src = json.load(file)

    for post in src.keys():
        text = src[post]['text']
        for msg in split(text):
            bot.send_message(channel, msg, disable_web_page_preview=True)

        if 'link' in src[post]:
            link = src[post]['link']
            bot.send_message(channel,link, disable_web_page_preview=False)

        if 'photo' in src[post]:
            photo = src[post]['photo'][0]
            bot.send_photo(channel, photo)

        if 'video' in src[post]:
            video = src[post]['video'][0]
            bot.send_message(channel,video, disable_web_page_preview=False)

        if 'doc' in src[post]:
            docs = src[post]['doc']
            for doc in docs:
                bot.send_document(channel, doc)

    time.sleep(10)
    #os.remove(f'{group}.json')
    group_src = path + '/' + str(group)+'.json'
    os.remove(group_src)
    #os.remove(f'{group}-posts.json')
    group_posts = path + '/' + str(group)+'-posts.json'
    os.remove(group_posts)


if __name__ == '__main__':
    print(time.ctime()+" GMT 0")

    for group in groups:
        get_wall_posts(group,3)
        check_wall_posts(group)
        send_posts(group)
        print('made for '+group)
        time.sleep(10)
