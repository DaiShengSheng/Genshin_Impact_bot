from PIL import Image
from io import BytesIO
from nonebot import MessageSegment

import os
import json
import random
import math
import base64

FILE_PATH = os.path.dirname(__file__)
ICON_PATH = os.path.join(FILE_PATH,'icon')



DEFAULT_POOL = "角色up池" # 默认卡池

POOL_PROBABILITY  = {
    # 所有卡池的4星和5星概率,由于判断出货的时候是先判断5星，所以4星概率是4星原概率加上5星的概率，这里的4星概率已经加上5星概率了
    "角色up池":{"5" : 0.006 , "4" : 0.057 },
    "武器up池":{"5" : 0.007 , "4" : 0.067 },
    "常驻池" : {"5" : 0.006 , "4" : 0.057 }
}

UP_PROBABILITY = {
    # 这里保存的是当UP池第一次抽取到或上次已经抽取过UP时，本次出现UP的概率有多大，常驻池不受影响
    "角色up池":0.5,
    "武器up池":0.75
}


ROLE_ARMS_LIST = {
    # 所有卡池数据

    "5星up角色": [],
    "4星up角色": [],
    "5星up武器": [],
    "4星up武器": [],
    "5星常驻角色": [],
    "4星常驻角色": [],
    "4星白给角色": [],
    "5星非up武器": [],
    "4星非up武器": [],
    "3星武器": [],

    "空":[], #这个列表是留空占位的，不会有任何数据

    '5星全角色武器':[],
    
    '5星常驻池':[],
    '4星常驻池':[],

    '5星角色up池全角色':[],
    '4星角色up池全物品':[],

    '5星武器up池全武器':[],
    '4星武器up池全物品':[]
}


CORRESPONDENCE = {
    # 这里记录的是ROLE_ARMS_LIST最后7个列表与其他列表的包含关系
    '5星全角色武器':["5星常驻角色","5星up角色","5星非up武器","5星up武器"],

    '5星常驻池':["5星常驻角色","5星非up武器","5星up武器"],
    '4星常驻池':["4星常驻角色","4星白给角色","4星up角色","4星up武器","4星非up武器"],

    '5星角色up池全角色':["5星up角色","5星常驻角色"],
    '4星角色up池全物品':["4星up角色","4星常驻角色","4星非up武器","4星up武器"],

    '5星武器up池全武器':["5星up武器","5星非up武器"],
    '4星武器up池全物品':["4星up武器","4星非up武器","4星常驻角色","4星up角色"]
}


POOL = {
    # 这个字典记录的是3个不同的卡池，每个卡池的抽取列表的value是ROLE_ARMS_LIST的哪个列表的key

    '角色up池':{
        '5星up':"5星up角色",
        '随机全5星':'5星角色up池全角色',
        '4星up':"4星up角色",
        '随机全4星':'4星角色up池全物品'
    },

    '武器up池':{
        '5星up':"5星up武器",
        '随机全5星':'5星武器up池全武器',
        '4星up':"4星up武器",
        '随机全4星':'4星武器up池全物品'
    },

    '常驻池':{
        '5星物品':'5星常驻池',
        '4星物品':'4星常驻池',
        '5星up':'空',
        '4星up':'空'
    }
}







def init_role_arms_list():
    # 初始化卡池数据
    with open(os.path.join(FILE_PATH,'config.json'),'r', encoding='UTF-8') as f:
        data = json.load(f)
        for key in data.keys():
            ROLE_ARMS_LIST[key] = data[key]

    for key in CORRESPONDENCE.keys():
        for i in CORRESPONDENCE[key]:
            ROLE_ARMS_LIST[key].extend(ROLE_ARMS_LIST[i]) # 对后7个列表填充数据
        ROLE_ARMS_LIST[key] = list(set(ROLE_ARMS_LIST[key])) # 去除重复数据

init_role_arms_list()








class Gacha(object):

    def __init__(self,_pool = DEFAULT_POOL):
        # 实例化的时候就要传进来字符串表明要抽哪个卡池
        self.pool = _pool

        self.last_time_5 = "" # 记录上一次抽卡的5星是什么
        self.last_time_4 = "" # 记录上一次抽卡的4星是什么

        # 保底计数,注意这个计数是从0开始的，每一次抽卡（包括第一次）之前都得+1
        self.distance_5_star = 0
        self.distance_4_star = 0

        # 需要生成图片的抽卡结果列表
        self.gacha_list = []

        # 记录多少抽第一次出现UP
        self.last_4_up = 0
        self.last_5_up = 0

        self.gacha_statistics = {
            # 这个列表记录的是本轮抽卡，每种稀有度各抽到了多少
            '3星': 0,
            '4星': 0,
            '5星': 0
        }


    @staticmethod
    def get_png_path(name):
        # 获取png文件路径，传入的参数是角色或武器名字，会自动在角色和武器文件夹搜索，找不到抛出异常

        role_name_path = os.path.join(ICON_PATH, "角色", str(name) + ".png")
        arms_name_path = os.path.join(ICON_PATH, "武器", str(name) + ".png")
        if os.path.exists(role_name_path):
            return role_name_path

        if os.path.exists(arms_name_path):
            return arms_name_path

        raise FileNotFoundError(f"找不到 {name} 的图标，请检查图标是否存在")

    @staticmethod
    def is_up(name):
        # 检查角色是否在UP里
        # 如果name是一个空字符串表示是第一次抽到4星或5星
        if name == "":
            return True
        if name in ROLE_ARMS_LIST["5星up角色"]:
            return True
        if name in ROLE_ARMS_LIST["4星up角色"]:
            return True
        if name in ROLE_ARMS_LIST["5星up武器"]:
            return True
        if name in ROLE_ARMS_LIST["4星up武器"]:
            return True
        return False

    @staticmethod
    def is_4_star(name):
        # 判断角色是不是4星
        if name in ROLE_ARMS_LIST['4星常驻池']:
            return True
        return False

    @staticmethod
    def is_5_star(name):
        # 判断角色是不是5星
        if name in ROLE_ARMS_LIST['5星全角色武器']:
            return True
        return False

    @staticmethod
    def is_star(name):
        # 检查角色或物品是几星的
        # 返回对应的星星数
        if name in ROLE_ARMS_LIST['5星全角色武器']:
            return "★★★★★"
        if name in ROLE_ARMS_LIST['4星常驻池']:
            return "★★★★"
        return "★★★"

    @staticmethod
    def pic2b64(pic):
        buf = BytesIO()
        pic.save(buf, format='PNG')
        base64_str = base64.b64encode(buf.getvalue()).decode()
        return 'base64://' + base64_str

    def concat_pic(self, border=5):
        # name_list是一个列表，这个函数找到列表中名字的图片，然后拼接成一张大图返回
        num = len(self.gacha_list)
        # w, h = pics[0].size
        w, h = [125, 130]
        des = Image.new('RGBA', (w * min(num, border), h * math.ceil(num / border)), (255, 255, 255, 0))

        for i in range(num):
            im = Image.open(self.get_png_path(self.gacha_list[i]))

            pixel_w_offset = (125 - im.size[0]) / 2
            pixel_h_offset = (130 - im.size[1]) / 2  # 因为角色和武器大小不一样，小的图像设置居中显示

            w_row = (i % border) + 1
            h_row = math.ceil((i + 1) / border)

            pixel_w = (w_row - 1) * w + pixel_w_offset
            pixel_h = (h_row - 1) * h + pixel_h_offset

            des.paste(im, (int(pixel_w), int(pixel_h)))

        return des

    def is_guaranteed(self,frequency):
        if frequency == 90 :
            if self.gacha_statistics['5星'] == 1  and self.gacha_statistics['4星'] == 8:
                return True
        if frequency == 180 :
            if self.gacha_statistics['5星'] == 2  and self.gacha_statistics['4星'] == 16:
                return True
        return False

    def get_5_star(self):
        # 先检查上次5星是否是UP，不是UP本次抽取必定是UP，
        # 如果上次是UP，角色UP池本次有50%的概率还是UP，50%概率所有5星随机，
        # 武器UP池本次有75%的概率还是UP，25%概率所有5星随机，详情看UP_PROBABILITY

        # 先看是不是常驻池
        if self.pool ==  '常驻池':
            key = POOL['常驻池']['5星物品'] # 先获取常驻池的5星保存在ROLE_ARMS_LIST的哪个列表
            return random.choice(ROLE_ARMS_LIST[key])

        # 下边是角色或武器的UP
        # 先获取5星UP和全5星保存在ROLE_ARMS_LIST的哪个列表
        # up_5_star和all_5_star是ROLE_ARMS_LIST的key
        # UP武器和UP角色对应的列表是不一样的，详情看POOL
        up_5_star = POOL[self.pool]['5星up']
        all_5_star = POOL[self.pool]['随机全5星']
        if self.is_up(self.last_time_5):

            if random.random() < UP_PROBABILITY[self.pool]:
                return random.choice(ROLE_ARMS_LIST[up_5_star])
            else:
                return random.choice(ROLE_ARMS_LIST[all_5_star])
        else:
            return random.choice(ROLE_ARMS_LIST[up_5_star])



    def get_4_star(self):
        # 先检查上次4星是否是UP，不是UP本次抽取必定是UP，
        # 如果上次是UP，角色UP池本次有50%的概率还是UP，50%概率所有4星随机，
        # 武器UP池本次有75%的概率还是UP，25%概率所有4星随机，详情看UP_PROBABILITY

        # 先看是不是常驻池
        if self.pool ==  '常驻池':
            key = POOL['常驻池']['4星物品'] # 先获取常驻池的4星保存在ROLE_ARMS_LIST的哪个列表
            return random.choice(ROLE_ARMS_LIST[key])

        # 下边是角色或武器的UP
        # 先获取4星UP和全4星保存在ROLE_ARMS_LIST的哪个列表
        # up_4_star和all_4_star是ROLE_ARMS_LIST的key
        # UP武器和UP角色对应的列表是不一样的，详情看POOL
        up_4_star = POOL[self.pool]['4星up']
        all_4_star = POOL[self.pool]['随机全4星']
        if self.is_up(self.last_time_4):
            if random.random() < UP_PROBABILITY[self.pool]:
                return random.choice(ROLE_ARMS_LIST[up_4_star])
            else:
                return random.choice(ROLE_ARMS_LIST[all_4_star])
        else:
            return random.choice(ROLE_ARMS_LIST[up_4_star])



    def gacha_one(self):
        # last_4表示上一个4星角色
        # last_5表示上一个5星角色
        # distance_4_star是4星保底计数
        # distance_5_star是5星保底计数
        self.distance_4_star += 1
        self.distance_5_star += 1

        r = random.random()

        # 先检查是不是保底5星
        if self.distance_5_star % 90 == 0:
            self.gacha_statistics["5星"] += 1
            self.distance_5_star = 0 # 重置保底计数
            self.last_time_5 = self.get_5_star() # 抽一次卡，把结果赋值留给下一次抽卡判断
            return self.last_time_5 # 返回刚抽出的卡

        # 检查是不是概率5星
        if r < POOL_PROBABILITY[self.pool]["5"]:
            self.gacha_statistics["5星"] += 1
            self.distance_5_star = 0
            self.last_time_5 = self.get_5_star()  # 抽一次卡，把结果赋值留给下一次抽卡判断
            return self.last_time_5  # 返回刚抽出的卡

        # 检查是不是保底4星
        if self.distance_4_star % 10 == 0:
            self.gacha_statistics["4星"] += 1
            self.distance_4_star = 0
            self.last_time_4 = self.get_4_star()
            return self.last_time_4

        # 检查是不是概率4星
        if r < POOL_PROBABILITY[self.pool]["5"]:
            self.gacha_statistics["4星"] += 1
            self.distance_4_star = 0
            self.last_time_4 = self.get_4_star()
            return self.last_time_4

        # 以上都不是返回3星
        self.gacha_statistics["3星"] += 1
        return random.choice(ROLE_ARMS_LIST["3星武器"])




    def gacha_10(self):
        # 抽10连

        gacha_txt = ""

        for i in range(10):

            new_gacha = self.gacha_one()
            self.gacha_list.append(new_gacha)
            gacha_txt += new_gacha
            gacha_txt += self.is_star(new_gacha)

            if (i + 1) % 5 == 0:
                gacha_txt += '\n'

            if not self.last_4_up:
                up_4_star = POOL[self.pool]['4星up']
                if new_gacha in ROLE_ARMS_LIST[up_4_star]:
                    self.last_4_up = i + 1

            if not self.last_5_up:
                up_5_star = POOL[self.pool]['5星up']
                if new_gacha in ROLE_ARMS_LIST[up_5_star]:
                    self.last_5_up = i + 1

        mes = '本次祈愿得到以下角色装备：\n'
        res = self.concat_pic()
        res = self.pic2b64(res)
        mes += str(MessageSegment.image(res))
        mes += '\n'
        mes += gacha_txt

        if self.last_4_up:
            mes += f'第 {self.last_4_up} 抽首次出现4★UP!\n'
        if self.last_5_up:
            mes += f'第 {self.last_5_up} 抽首次出现5★UP!\n'

        mes += f"\n* 本次抽取卡池为 {self.pool} \n* 发送 原神卡池切换 可切换卡池"

        return mes

    def gacha_90(self,frequency=90):
        # 抽一井

        gacha_txt = ""


        for i in range(frequency):

            new_gacha = self.gacha_one()

            if not (new_gacha in ROLE_ARMS_LIST["3星武器"]):
                self.gacha_list.append(new_gacha)

            if not self.last_4_up:
                up_4_star = POOL[self.pool]['4星up']
                if new_gacha in ROLE_ARMS_LIST[up_4_star]:
                    self.last_4_up = i + 1

            if not self.last_5_up:
                up_5_star = POOL[self.pool]['5星up']
                if new_gacha in ROLE_ARMS_LIST[up_5_star]:
                    self.last_5_up = i + 1

        gacha_txt += f"★★★★★×{self.gacha_statistics['5星']}    ★★★★×{self.gacha_statistics['4星']}    ★★★×{self.gacha_statistics['3星']}\n"

        mes = '本次祈愿得到以下角色装备：\n'
        res = self.concat_pic()
        res = self.pic2b64(res)
        mes += str(MessageSegment.image(res))
        mes += '\n'
        mes += gacha_txt

        if self.last_4_up:
            mes += f'第 {self.last_4_up} 抽首次出现4★UP!\n'
        if self.last_5_up:
            mes += f'第 {self.last_5_up} 抽首次出现5★UP!\n'

        if self.is_guaranteed(frequency):
            mes += "居然全是保底，你脸也太黑了\n"

        mes += f"\n* 本次抽取卡池为 {self.pool} \n* 发送 原神卡池切换 可切换卡池"
        return mes






def gacha_info(pool = DEFAULT_POOL):
    # 重载卡池数据，然后返回UP角色信息
    init_role_arms_list() # 重新载入config.json的卡池数据
    info_txt = f'当前卡池为 {pool} ，UP信息如下：\n'

    _5_star_up_info = POOL[pool]["5星up"]
    _4_star_up_info = POOL[pool]["4星up"]
    up_info = ""

    for _5_star in ROLE_ARMS_LIST[_5_star_up_info]:
        im = Image.open(Gacha.get_png_path(_5_star))
        im = Gacha.pic2b64(im)
        up_info += str(MessageSegment.image(im))
        up_info += "\n"
        up_info += f"{_5_star} ★★★★★"

    for _4_star in ROLE_ARMS_LIST[_4_star_up_info]:
        im = Image.open(Gacha.get_png_path(_4_star))
        im = Gacha.pic2b64(im)
        up_info += str(MessageSegment.image(im))
        up_info += "\n"
        up_info += f"{_4_star} ★★★★"

    if up_info == "":
        # 如果up_info是空的，表示当前是常驻池没有UP
        up_info += "常驻池没有UP"

    info_txt += up_info
    return info_txt





