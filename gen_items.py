import random
ts = ['도서 추천', '입시 이슈', '합격 가이드', '탐구 아이디어']
ms = ['의예과', '컴공', '경영', '미디어', '정외', '생명', '심리', '수교']
adjs = ['심화', '실전', '혁신', '글로벌']
with open('items.txt', 'w', encoding='utf-8') as f:
    for i in range(121, 421):
        t = random.choice(ts)
        m = random.choice(ms)
        a = random.choice(adjs)
        f.write(f"  {{ id: {i}, type: '{t}', icon: Lightbulb, title: '[{m}] {a} 탐구 및 입시 전략', desc: '{m} 지망생을 위한 {a} 핵심 로드맵 자료입니다.' }},\n")
