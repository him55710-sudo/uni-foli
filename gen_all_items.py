import random
ts = ['도서 추천', '입시 이슈', '합격 가이드', '탐구 아이디어']
ms = ['의예과','치의예과','약학과','컴공','정외','심리','생명','경영','교육','통계','미디어','법학','전자','도시']
adjs = ['심화', '실전', '혁신', '글로벌']
with open('batch_items.txt', 'w', encoding='utf-8') as f:
    for i in range(121, 421):
        t=random.choice(ts); m=random.choice(ms); a=random.choice(adjs)
        f.write(f'  {{ id: {i}, type: "{t}", icon: Lightbulb, title: "[{m}] {a} 탐구 로드맵", desc: "{m} 지망생을 위한 {a} 핵심 전략 자료입니다." }},\n')
