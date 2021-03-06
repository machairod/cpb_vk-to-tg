# This Python file uses the following encoding: utf-8
import requests, os, telebot, json, time, configparser


# получаем последние *count постов со стен групп вк
def get_wall_posts(group, count):
    count = count
    if group.isdigit():
        url = 'https://api.vk.com/method/wall.get?owner_id=-' + str(group) + '&count=' + str(
            count) + '&access_token=' + str(token) + '&v=5.131'
    else:
        url = 'https://api.vk.com/method/wall.get?domain=' + str(group) + '&count=' + str(
            count) + '&access_token=' + str(token) + '&v=5.131'
    file = path + '/' + group + '.json'
    req = requests.get(url)
    src = req.json()

    with open(file, 'w+') as file:
        json.dump(src, file, ensure_ascii=False, indent=4)


# проверяем на критерии, сверяем с датой последнего обработанного, готовим под отправку
def check_wall_posts(group, groupname):
    global groupconfig
    file = path + '/' + group + '.json'
    if not os.path.isfile(file):
        err_txt = f'Файл для группы {group} не найден'
        return err_txt

    # приняли из json данные выгрузки
    with open(file, 'r', encoding='utf-8') as file:
        src = json.load(file)

    if 'response' not in src.keys():
        if 'error' in src.keys():
            return src['error']['error_msg']
        else:
            return src.keys()

    posts = reversed(src['response']['items'])

    # дата публикации в юникс последнего обработанного поста, основной идентификатор
    postdate = int(groupconfig[group]['post'])
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
                send_post[date] = {}

                # заносим в словарь, добавляем ссылку на оригинальный пост и подчищаем верстку
                send_post[date]['text'] = groupname + '\n' + 'Ссылка на пост: ' + 'https://vk.com/wall' + str(
                    post['from_id']) + '_' + str(post['id']) + '\n\n\n' + post['text']
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
                            photos.append(add['photo'])

                        # если прикреп видео
                        if add['type'] == 'video':
                            send_post[date]['video'] = []
                            videos.append(add['video'])

                        # если прикреп файл
                        if add['type'] == 'doc':
                            send_post[date]['doc'] = []
                            docs.append(add['doc'])

                        # если прикреп ссылка
                        if add['type'] == 'link':
                            link = add['link']['url']
                            # сократили ссылку
                            data = json.dumps({"long_url": link})
                            bttoken = 'Bearer ' + bitlytoken
                            response = requests.post("https://api-ssl.bitly.com/v4/shorten",
                                                     data=data,
                                                     headers={'Authorization': bttoken})
                            src = response.json()
                            send_post[date]['link'] = src['link']

                    # если прикреп картинка - обработка массива
                    if len(photos) > 0:
                        img = photos[0]
                        addy = 0
                        img_url = ''
                        # ищем ссылку на наибольшее разрешение фото
                        for i in img['sizes']:
                            if 'height' in i:
                                y = i['height']
                                if y > addy:
                                    addy = y
                                    y = 0
                                    img_url = i['url']
                        if addy > 0:
                            trim = img_url.find('?')
                            impg = img_url.find('/imp')
                            img_url = img_url[:impg] + img_url[(impg + 5):trim]
                            send_post[date]['photo'] = img_url

                        # если прикреп видео - обработка массива
                    if len(videos) > 0:
                        video = videos[0]
                        owner_id = str(video['owner_id'])
                        vid_id = str(video['id'])
                        access_key = str(video['access_key'])
                        vid_url = "https://vk.com/video" + owner_id + "_" + vid_id
                        send_post[date]['video'].append(vid_url)

                    # если прикреп файл - обработка массива
                    if len(docs) > 0:
                        for doc in docs:
                            dl = doc['url']
                            send_post[date]['doc'].append(dl)

    # здесь возвращаем док с постами, готовыми к отправке
    file = path + '/' + group + '-posts.json'
    with open(file, 'w+') as file:
        json.dump(send_post, file, ensure_ascii=False, indent=4)

    # #сохраняем в данных группы дату последнего обработанного поста
    olddate = str(postdate)
    if len(new_postdate) > 0:
        newdate = str(max(new_postdate))
    else:
        newdate = olddate

    cpbgroup = path + '/' + 'cpbgroups.py'
    groupconfig.set(group, 'post', newdate)

    with open(cpbgroup, 'w') as vkgroups:
        groupconfig.write(vkgroups)


# отправляем посты в телеграм канал
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
    file = path + '/' + str(group) + '-posts.json'
    with open(file, 'r', encoding='utf-8') as file:
        src = json.load(file)

    for post in src.keys():
        text = src[post]['text']
        for msg in split(text):
            bot.send_message(channel, msg, disable_web_page_preview=True)

        if 'link' in src[post]:
            link = src[post]['link']
            bot.send_message(channel, link, disable_web_page_preview=False)

        if 'photo' in src[post]:
            photo = src[post]['photo']
            bot.send_photo(channel, photo)

        if 'video' in src[post]:
            video = 'Ccылка на видео: ' + src[post]['video'][0]
            bot.send_message(channel, video, disable_web_page_preview=False)

        if 'doc' in src[post]:
            docs = src[post]['doc']
            for doc in docs:
                bot.send_document(channel, doc)

    time.sleep(10)
    # os.remove(f'{group}.json')
    group_src = path + '/' + str(group) + '.json'
    os.remove(group_src)
    # os.remove(f'{group}-posts.json')
    group_posts = path + '/' + str(group) + '-posts.json'
    os.remove(group_posts)


if __name__ == '__main__':
    # print(time.ctime()+" GMT 0")

    path = os.path.dirname(__file__)

    configfile = os.path.join(path, 'settings.ini')
    config = configparser.ConfigParser()
    config.read(configfile)

    bot_token = config['Telegram']['bot_token']
    token = config['VK']['token']
    channel = config['Telegram']['channel']
    bitlytoken = config['bitly']['bitlytoken']

    cpbgroups_file = os.path.join(path, 'cpbgroups.py')
    groupconfig = configparser.ConfigParser()
    groupconfig.read(cpbgroups_file)

    groups = groupconfig.sections()

    # Инициализируем телеграмм бота
    bot = telebot.TeleBot(bot_token)

    for group in groups:
        get_wall_posts(group, 3)
        check_wall_posts(group, groupconfig[group]['name'])
        send_posts(group)
        #print('made for '+group)
        time.sleep(10)
