"""Zone name mappings from internal paths to Korean names."""

# Map internal zone path patterns to Korean display names
# Add new mappings as you encounter zones
ZONE_NAMES = {
    # Hideouts / Hubs (은신처)
    "XZ_YuJinZhiXiBiNanSuo": "피난처 - 엠버의 숨결",
    "DD_ShengTingZhuangYuan": "피난처 - 성스러운 궁정 저택",

    # Voidlands / 암흑의 땅 (entries with number suffixes must come before generic ones)
    "DD_ShengTingZhuangYuan000": "암흑의 땅 - 세속의 궁궐",

    # Blistering Lava Sea / 끓어오르는 화염의 바다
    "KD_YuanSuKuangDong": "끓어오르는 화염의 바다 - 원소 광산",
    "DD_ChaoBaiZhiLu": "끓어오르는 화염의 바다 - 헌신의 길",
    "SD_ShouGuSiDi": "끓어오르는 화염의 바다 - 용의 잠든 협곡",
    "JH_ZuiRenMiDian": "끓어오르는 화염의 바다 - 참회의 성전",
    "YJ_LuoRiQiongDi": "끓어오르는 화염의 바다 - 일몰의 천장",
    "SQ_BianChuiZhiDi": "끓어오르는 화염의 바다 - 황야의 들판",
    "JH_MengZhongShengDi": "끓어오르는 화염의 바다 - 잔잔한 빛의 강당",
    "KD_AiRenDiSanCeng": "끓어오르는 화염의 바다 - 산의 마음",
    "JH_ShengDeLanXiuDaoYuan": "끓어오르는 화염의 바다 - 뒤틀린 골짜기",
    "SD_ShouGuLinDi": "끓어오르는 화염의 바다 - 고해의 방",
    "DD_DiDuTingYuan200": "끓어오르는 화염의 바다 - 암흑의 왕정",
    "KD_RongHuoHeXin": "끓어오르는 화염의 바다 - 제련소",
    "YanYuZhiGu": "끓어오르는 화염의 바다 - 지옥불 협곡",

    # Glacial Abyss / 얼어붙은 심연
    "DD_TingYuanMiGong": "얼어붙은 심연 - 홀리 미궁",
    "YJ_XieDuYuZuo": "얼어붙은 심연 - 어둠의 전초전",
    "DD_ZaWuJieQu": "얼어붙은 심연 - 어수선한 거리",
    "SQ_MingShaJuLuo": "얼어붙은 심연 - 울부짖는 모래 마을",
    "SD_GeBuLinShanZhai": "얼어붙은 심연 - 신성 모독의 편전",
    "GeBuLinCunLuo": "아인 마을",
    "KD_AiRenKuangDong": "얼어붙은 심연 - 회선 광장",
    "YL_YinYiZhiDi": "얼어붙은 심연 - 홀리 레거시 우림",
    "KD_WeiJiKuangDong": "얼어붙은 심연 - 소용돌이 광산",
    "YL_BeiFengLinDi": "비극의 숲",
    "SD_ZhongXiGaoQiang": "얼어붙은 심연 - 종식의 벽",
    "SD_GeBuLinYingDi": "얼어붙은 심연 - 바람의 협곡",
    "YongShuangBingPo": "얼어붙은 심연 - 겨울의 왕좌",

    # Vorax / 보락스
    "DiXiaZhenSuo": "미치광이 의사 세리알의 수술실",

    # Steel Forge / 강철의 용광로
    "JH_JueXingMiDian": "강철의 용광로 - 절망의 비밀 성전",
    "JH_TongKuMiDian": "강철의 용광로 - 단죄의 비밀 성전",
    "SD_YuanGuTongDao": "강철의 용광로 - 짐승들의 평원",
    "SQ_JingJiHuiTu": "강철의 용광로 - 가시나무 소굴",
    "KD_AiRenDiErCeng": "강철의 용광로 - 비명의 광구",
    "SD_DuiLongJuQiang": "강철의 용광로 - 하늘로 솟은 장벽",
    "DD_YinYanJieXiang": "강철의 용광로 - 잊혀진 거리",
    "YJ_TaiYangWangTing": "강철의 용광로 - 영광의 궁성",
    "DD_JueWangZhiQiang": "강철의 용광로 - 순수의 벽",
    "YJ_RiXiShenMiao": "강철의 용광로 - 태양의 신전",
    "YJ_YingLingShenDian": "강철의 용광로 - 헤일로의 성전",
    "SQ_ZheFengBiZhang": "강철의 용광로 - 바람이 잠든 절벽",
    "ChiGuiWuShi": "강철의 용광로 - 상상의 기념비",

    # Thunder Wastes / 천둥의 폐허
    "DD_TanXiZhiQiang": "천둥의 폐허 - 슬픈 가락의 장벽",
    "DD_XinTuJieXiang": "천둥의 폐허 - 순례자의 거리",
    "SQ_EWuHuangCun": "천둥의 폐허 - 악마와 폐허의 땅",
    "YJ_ShuXiDaTing": "천둥의 폐허 - 거울 속의 강당",
    "SQ_NvShenQunBai": "천둥의 폐허 - 혼탁한 오아시스",
    "SQ_XiongShiZhiXin": "천둥의 폐허 - 왕의 허브",
    "KD_CangBaoDongKu": "천둥의 폐허 - 메마른 광산",
    "SD_ShengHuoLing": "천둥의 폐허 - 안개비 밀림",
    "JH_JiaoTangDaTing": "천둥의 폐허 - 축원의 성전",
    "DD_DiDuTingYuan000": "천둥의 폐허 - 성스러운 정원",
    "YJ_LiuJinJieQu": "천둥의 폐허 - 초승달의 회랑",
    "LeiYingJiDian": "천둥의 폐허 - 천둥의 정점",

    # Rift of Dimensions / 차원의 균열
    "LieXiKongJing": "차원의 균열",

    # Secret Realms / 비밀 영역
    "HD_YingGuangDianTang": "비밀 영역 - 소중한 시간",

    # Void Sea / 허공의 바다
    "XuHaiZhongGang": "허공의 바다 터미널",

    # Voidlands / 암흑의 땅 (remaining zones without conflicts)
    "DD_QunLangJieXiang": "암흑의 땅 - 어두컴컴한 거리",
    "YL_MaNeiLaYuLin": "암흑의 땅 - 혼탁한 정글",
    "YL_MiWuYuLin": "암흑의 땅 - 꿈을 잃은 숲",
    "JH_ShenHeJuSuo": "암흑의 땅 - 찬란한 성좌",
    "JH_YiWangMiDian": "암흑의 땅 - 고통의 비밀 성전",
    "YL_KuangReYuLin": "암흑의 땅 - 잔잔한 빛의 습지",
    "YL_XiDiChongGu": "암흑의 땅 - 종족 밀림",
    "YJ_YongZhouHuiLang": "암흑의 땅 - 별들의 회랑",
    "JH_YinNiShengTang": "암흑의 땅 - 과거의 방",
    "DiaoLingWangYu": "암흑의 땅 - 꿈 없는 심연",

    # Deep Space / 딥 스페이스
    "KD_DiXinKuangChang": "딥 스페이스 - 코어 광산",
    "SQ_ShaZhongMuYuan": "딥 스페이스 - 모래 속 목축지",
    "YL_WanQingHuangLin": "딥 스페이스 - 만경의 황야",
    "SD_DaHuangZhiYe": "딥 스페이스 - 끝없는 광야",
    "SD_LieChangMang": "딥 스페이스 - 광활한 사냥터",
    "SD_GuangMaoLieChang": "딥 스페이스 - 광활한 사냥터",
}

# Ambiguous zones that appear in multiple regions with same path
AMBIGUOUS_ZONES = {
    "YL_BeiFengLinDi": {
        6: "얼어붙은 심연 - 비극의 숲",
        54: "암흑의 땅 - 비극의 숲",
    },
    "KD_YuanSuKuangDong000": {
        12: "끓어오르는 화염의 바다 - 원소 광산",
        55: "암흑의 땅 - 원소 광산",
    },
    "GeBuLinCunLuo": {
        36: "얼어붙은 심연 - 아인 마을",
    },
}

# Exact LevelId mappings for special zones (bosses, secret realms, etc.)
LEVEL_ID_ZONES = {
    3016: "끓어오르는 화염의 바다 - 지옥불 협곡",
    3006: "얼어붙은 심연 - 겨울의 왕좌",
    3036: "천둥의 폐허 - 천둥의 정점",
    3026: "강철의 용광로 - 상상의 기념비",
    3046: "암흑의 땅 - 꿈 없는 심연",
    234020: "비밀 영역 - 의식의 바다",
}


def get_zone_display_name(zone_path: str, level_id: int | None = None) -> str:
    """
    Get the Korean display name for a zone path.
    """
    if level_id is not None and level_id in LEVEL_ID_ZONES:
        return LEVEL_ID_ZONES[level_id]

    if level_id is not None:
        for zone_pattern, suffix_map in AMBIGUOUS_ZONES.items():
            if zone_pattern in zone_path:
                suffix = level_id % 100
                if suffix in suffix_map:
                    return suffix_map[suffix]

    for internal_name, korean_name in ZONE_NAMES.items():
        if internal_name in zone_path:
            return korean_name

    parts = zone_path.split("/")
    for part in reversed(parts):
        if part and not part.startswith("Game") and not part.startswith("Art"):
            import re
            cleaned = re.sub(r'\d+$', '', part)
            return cleaned if cleaned else part

    return zone_path
