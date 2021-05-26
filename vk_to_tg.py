# This Python file uses the following encoding: utf-8
import requests, os, telebot, json, time
from settings import token, bot_token, bitlytoken
from cpbgroups import groups, channel

# Инициализируем телеграмм бота
bot = telebot.TeleBot(bot_token)


# получаем последние 5 постов со стен групп вк
def get_wall_posts(group,count):
    count=count
    if group.isdigit():
        url = f"https://api.vk.com/method/wall.get?owner_id=-{group}&count={count}&access_token={token}&v=5.52"
    else:
        url = f"https://api.vk.com/method/wall.get?domain={group}&count={count}&access_token={token}&v=5.52"

    req = requests.get(url)
    src = req.json()

    with open(f'{group}.json', 'w+') as file:
        json.dump(src, file, ensure_ascii=False, indent=4)


# проверяем на критерии, сверяем с датой последнего обработанного, готовим под отправку
def check_wall_posts(group):
    # приняли из json данные выгрузки
    with open(f'{group}.json', 'r', encoding='utf-8') as file:
        src = json.load(file)
    posts = reversed(src['response']['items'])

    # дата публикации в юникс последнего обработанного поста, основной идентификатор
    postdate = groups[group]

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
                            data = json.dumps({"long_url": f'{link}'})
                            response = requests.post("https://api-ssl.bitly.com/v4/shorten",
                                                     data=data,
                                                     headers={'Authorization': f'Bearer {bitlytoken}'})
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
                            vid='http://vk.com/video'+str(video['video']['owner_id'])+"_"+str(video["video"]['id'])+"?access_key="+str(video['video']['access_key'])
                            send_post[date]['video'].append(vid)

                        # если прикреп файл - обработка массива
                        for doc in docs:
                            dl = doc['doc']['url']
                            send_post[date]['doc'].append(dl)

    # здесь возвращаем док с постами, готовыми к отправке
    with open(f'{group}-posts.json', 'w+') as file:
        json.dump(send_post, file, ensure_ascii=False, indent=4)


    # #сохраняем в данных группы дату последнего обработанного поста
    olddate = str(postdate)
    if len(new_postdate)>0:
        newdate = str(max(new_postdate))
    else:
        newdate = olddate
    with open('cpbgroups.py', 'r') as vkgroups:
        inst = vkgroups.read()
    inst = inst.replace(olddate,newdate)

    with open('cpbgroups.py', 'w') as vkgroups:
        vkgroups.write(inst)

#отправляем посты в телеграм канал
def send_posts(group):

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
    with open(f'{group}-posts.json', 'r', encoding='utf-8') as file:
        src = json.load(file)
    for post in src.keys():

        # В телеграмме есть ограничения на длину одного сообщения в 4091 символ, разбиваем длинные сообщения на части
        text = src[post]['text']
        for msg in split(text):
            continue
            #bot.send_message(channel, msg, disable_web_page_preview=True)

        if 'link' in src[post]:
            link = src[post]['link']
            #bot.send_message(channel,link, disable_web_page_preview=False)

        if 'photo' in src[post]:
            photo = src[post]['photo'][0]
            #bot.send_photo(channel, photo)

        if 'video' in src[post]:
            video = src[post]['video'][0]
            try:
                bot.send_video(channel, video)
            except:
                print(Exception)
            finally: continue

        if 'doc' in src[post]:
            docs = src[post]['doc']
            # for doc in docs:
            #     bot.send_document(channel, doc)
    time.sleep(10)
    os.remove(f'{group}.json')
    os.remove(f'{group}-posts.json')


if __name__ == '__main__':
    print(time.ctime()+" GMT 0")

    for group in groups:
        get_wall_posts(group,10)
        check_wall_posts(group)
        send_posts(group)
        print(f'made for {group}')
        time.sleep(10)


    # with open('cpbgroups.py', 'w') as vkgroups:
    #     vkgroups.write("channel ='@zmeeust_python'\ngroups ={'spb_cpb': 1523272395, 'msk_cpb': 1523272391, 'cpb_vl':1523272392,'cpb_corp':1523272393,'cpb_krasnodar':1523272394,'irk_cpb': 1523272396,'krim_cpb': 1523272397, '189820518': 1523272398,'102325800': 1523272397}")
