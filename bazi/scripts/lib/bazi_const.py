# -*- coding: utf-8 -*-
"""
八字排盘核心库（陆致极体系技能用）

设计原则：
  1. 四柱/大运/藏干/十神/纳音/空亡等"硬计算"全部交给 lunar-python（6tail），
     它按节气精确时刻（非按天）换年换月，这一点已用 2000 年立春案例验证。
  2. 本库只补 lunar-python 不提供的部分：真太阳时、神煞、双引擎交叉校验、输出。
  3. 日界与时辰用"真太阳时"判定；年月柱用北京时间判定——因为节气是全中国同一
     瞬间的天文事件，与出生地经度无关。两者若出现分歧，会写进 warnings。

术语约定：
  - 时柱的"子时"分早子（00:00-00:59）与晚子（23:00-23:59）。
  - school="sect1" 晚子时日柱算次日；school="sect2"（默认）晚子时日柱算当日。
    时干一律按"次日日干"起五鼠遁，这是通行的夜子时处理。
"""
import math
import datetime

# ---------------------------------------------------------------- 基础常量

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

GAN_WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
GAN_YINYANG = {
    "甲": "阳", "乙": "阴", "丙": "阳", "丁": "阴", "戊": "阳",
    "己": "阴", "庚": "阳", "辛": "阴", "壬": "阳", "癸": "阴",
}
ZHI_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}
ZHI_YINYANG = {
    "子": "阳", "丑": "阴", "寅": "阳", "卯": "阴", "辰": "阳", "巳": "阴",
    "午": "阳", "未": "阴", "申": "阳", "酉": "阴", "戌": "阳", "亥": "阴",
}

# 地支藏干（本气、中气、余气）；顺序即"本气优先"
CANG_GAN = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

# 五行生克
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}   # 我生
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}      # 我克

# 五鼠遁：日干 -> 子时的天干
WUSHU = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊",
         "辛": "戊", "丁": "庚", "壬": "庚", "戊": "壬", "癸": "壬"}

# 十二长生（阳干顺行、阴干逆行，起点为长生）
CHANGSHENG_START = {
    "甲": "亥", "乙": "午", "丙": "寅", "丁": "酉", "戊": "寅",
    "己": "酉", "庚": "巳", "辛": "子", "壬": "申", "癸": "卯",
}
CHANGSHENG_NAMES = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰",
                    "病", "死", "墓", "绝", "胎", "养"]

# 六十甲子纳音
NAYIN_TABLE = """甲子乙丑海中金 丙寅丁卯炉中火 戊辰己巳大林木 庚午辛未路旁土
壬申癸酉剑锋金 甲戌乙亥山头火 丙子丁丑涧下水 戊寅己卯城头土 庚辰辛巳白蜡金
壬午癸未杨柳木 甲申乙酉泉中水 丙戌丁亥屋上土 戊子己丑霹雳火 庚寅辛卯松柏木
壬辰癸巳长流水 甲午乙未沙中金 丙申丁酉山下火 戊戌己亥平地木 庚子辛丑壁上土
壬寅癸卯金箔金 甲辰乙巳覆灯火 丙午丁未天河水 戊申己酉大驿土 庚戌辛亥钗钏金
壬子癸丑桑柘木 甲寅乙卯大溪水 丙辰丁巳沙中土 戊午己未天上火 庚申辛酉石榴木
壬戌癸亥大海水"""


def _build_nayin():
    """
    每段格式：干支(2字) + 干支(2字) + 纳音(3字)，例如 "甲子乙丑海中金"。
    纳音名一律三字（海中金/炉中火/大林木…），据此切分。
    """
    table = {}
    for line in NAYIN_TABLE.split("\n"):
        for seg in line.split():
            seg = seg.strip()
            if len(seg) < 7:
                continue
            name = seg[4:7]          # 纳音名恒为三字
            table[seg[0:2]] = name   # 前一个干支
            table[seg[2:4]] = name   # 后一个干支，与前者同纳音
    return table


NAYIN = _build_nayin()


# ---------------------------------------------------------------- 十神

def shishen(day_gan, target_gan):
    """以日干为我，求 target_gan 的十神"""
    if target_gan == day_gan:
        return "比肩"
    me_wx, me_yy = GAN_WUXING[day_gan], GAN_YINYANG[day_gan]
    t_wx, t_yy = GAN_WUXING[target_gan], GAN_YINYANG[target_gan]
    same = (me_yy == t_yy)
    if me_wx == t_wx:
        return "比肩" if same else "劫财"
    if SHENG[me_wx] == t_wx:      # 我生
        return "食神" if same else "伤官"
    if KE[me_wx] == t_wx:         # 我克
        return "偏财" if same else "正财"
    if KE[t_wx] == me_wx:         # 克我
        return "七杀" if same else "正官"
    return "偏印" if same else "正印"   # 生我


# ---------------------------------------------------------------- 神煞

TIANYI = {"甲": "丑未", "戊": "丑未", "庚": "丑未", "乙": "子申", "己": "子申",
          "丙": "亥酉", "丁": "亥酉", "壬": "卯巳", "癸": "卯巳", "辛": "午寅"}
WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
            "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
YANGREN = {"甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
           "己": "巳", "庚": "酉", "辛": "申", "壬": "子", "癸": "亥"}
HONGYAN = {"甲": "午", "乙": "申", "丙": "寅", "丁": "未", "戊": "辰",
           "己": "辰", "庚": "戌", "辛": "酉", "壬": "子", "癸": "申"}
JINYU = {"甲": "辰", "乙": "巳", "丙": "未", "丁": "申", "戊": "未",
         "己": "申", "庚": "戌", "辛": "亥", "壬": "丑", "癸": "寅"}

# 三合局 -> (驿马, 桃花, 将星, 华盖)
SANHE = {"申子辰": ("寅", "酉", "子", "辰"),
         "寅午戌": ("申", "卯", "午", "戌"),
         "巳酉丑": ("亥", "午", "酉", "丑"),
         "亥卯未": ("巳", "子", "卯", "未")}

GUCHEN = {"亥子丑": ("寅", "戌"), "寅卯辰": ("巳", "丑"),
          "巳午未": ("申", "辰"), "申酉戌": ("亥", "未")}

# 月德（按月支三合局）
YUEDE = {"寅午戌": "丙", "申子辰": "壬", "亥卯未": "甲", "巳酉丑": "庚"}
TIANDE = {"寅": "丁", "卯": "申", "辰": "壬", "巳": "辛", "午": "亥", "未": "甲",
          "申": "癸", "酉": "寅", "戌": "丙", "亥": "乙", "子": "巳", "丑": "庚"}

KUIGANG = {"庚辰", "庚戌", "壬辰", "戊戌"}


def _sanhe_key(zhi):
    for key in SANHE:
        if zhi in key:
            return key
    return None


def shensha(pillars, day_gan, year_gan, month_zhi):
    """pillars: [(干,支), ...] 年月日时。返回 {柱名: [神煞...]}"""
    zhis = [p[1] for p in pillars]
    names = ["年", "月", "日", "时"]
    result = {n: [] for n in names}
    day_zhi = pillars[2][1]

    def mark(char, label):
        for i, (g, z) in enumerate(pillars):
            if z == char:
                result[names[i]].append(label)

    def mark_gan(char, label):
        for i, (g, z) in enumerate(pillars):
            if g == char:
                result[names[i]].append(label)

    # 天乙贵人、文昌、羊刃、红艳、金舆：以日干查
    for ch in TIANYI.get(day_gan, ""):
        mark(ch, "天乙贵人")
    if WENCHANG.get(day_gan) in zhis:
        mark(WENCHANG[day_gan], "文昌")
    if YANGREN.get(day_gan) in zhis:
        mark(YANGREN[day_gan], "羊刃")
    if HONGYAN.get(day_gan) in zhis:
        mark(HONGYAN[day_gan], "红艳")
    if JINYU.get(day_gan) in zhis:
        mark(JINYU[day_gan], "金舆")

    # 三合局系：以年支与日支双查
    for base in (pillars[0][1], day_zhi):
        k = _sanhe_key(base)
        if not k:
            continue
        yima, taohua, jiangxing, huagai = SANHE[k]
        for ch, lab in ((yima, "驿马"), (taohua, "桃花"),
                        (jiangxing, "将星"), (huagai, "华盖")):
            if ch in zhis:
                mark(ch, lab)

    # 孤辰寡宿：以年支查
    k = _sanhe_key(pillars[0][1])
    if k:
        for grp, (gu, gua) in GUCHEN.items():
            if pillars[0][1] in grp:
                if gu in zhis:
                    mark(gu, "孤辰")
                if gua in zhis:
                    mark(gua, "寡宿")
                break

    # 天德月德
    k = _sanhe_key(month_zhi)
    if k and YUEDE.get(k):
        mark_gan(YUEDE[k], "月德贵人")
    td = TIANDE.get(month_zhi)
    if td and td in zhis:
        mark(td, "天德贵人")

    # 魁罡：日柱
    if pillars[2][0] + pillars[2][1] in KUIGANG:
        result["日"].append("魁罡")

    # 改序：去重保序
    for n in names:
        seen, out = set(), []
        for x in result[n]:
            if x not in seen:
                seen.add(x)
                out.append(x)
        result[n] = out
    return result


# ---------------------------------------------------------------- 真太阳时

def equation_of_time_minutes(dt):
    """均时差（分钟）。近似公式，全年误差 < 30 秒，足够定时辰。"""
    n = dt.timetuple().tm_yday
    b = 2 * math.pi * (n - 81) / 364.0
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def true_solar_time(beijing_dt, longitude):
    """
    由北京时间求当地真太阳时。
    经度差：(经度 - 120) * 4 分钟；再加均时差。
    返回 (datetime, 明细dict)
    """
    lon_delta = (longitude - 120.0) * 4.0
    eot = equation_of_time_minutes(beijing_dt)
    total = lon_delta + eot
    return beijing_dt + datetime.timedelta(minutes=total), {
        "经度差(分)": round(lon_delta, 2),
        "均时差(分)": round(eot, 2),
        "总校正(分)": round(total, 2),
    }


# 常用城市经度（东经为正）
CITY_LONGITUDE = {
    "北京": 116.41, "上海": 121.47, "天津": 117.20, "重庆": 106.55,
    "广州": 113.26, "深圳": 114.06, "杭州": 120.15, "南京": 118.80,
    "武汉": 114.31, "成都": 104.07, "西安": 108.95, "沈阳": 123.43,
    "哈尔滨": 126.63, "长春": 125.32, "大连": 121.61, "济南": 117.00,
    "青岛": 120.38, "郑州": 113.62, "长沙": 112.94, "南昌": 115.89,
    "合肥": 117.28, "福州": 119.30, "厦门": 118.09, "昆明": 102.83,
    "贵阳": 106.63, "南宁": 108.37, "海口": 110.20, "兰州": 103.83,
    "西宁": 101.78, "银川": 106.23, "乌鲁木齐": 87.62, "拉萨": 91.14,
    "呼和浩特": 111.75, "太原": 112.55, "石家庄": 114.51, "苏州": 120.62,
    "无锡": 120.30, "宁波": 121.55, "温州": 120.70, "佛山": 113.12,
    "东莞": 113.75, "珠海": 113.58, "汕头": 116.68, "桂林": 110.29,
    "香港": 114.17, "澳门": 113.55, "台北": 121.52, "高雄": 120.30,
    "新加坡": 103.82, "吉隆坡": 101.69, "曼谷": 100.50, "东京": 139.69,
    "首尔": 126.98, "纽约": -74.01, "洛杉矶": -118.24, "旧金山": -122.42,
    "伦敦": -0.13, "巴黎": 2.35, "悉尼": 151.21, "多伦多": -79.38,
    "温哥华": -123.12, "墨尔本": 144.96, "奥克兰": 174.76, "迪拜": 55.27,
}


def resolve_longitude(city=None, longitude=None):
    if longitude is not None:
        return float(longitude), "explicit"
    if city:
        if city in CITY_LONGITUDE:
            return CITY_LONGITUDE[city], f"city:{city}"
        # 前缀匹配，如 "哈尔滨市"
        for k, v in CITY_LONGITUDE.items():
            if city.startswith(k) or k in city:
                return v, f"city:{k}"
    return None, "none"
