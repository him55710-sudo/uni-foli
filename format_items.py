import json

items = []
icon_map = {
    '도서 추천': 'BookOpen',
    '입시 이슈': 'Newspaper',
    '합격 가이드': 'GraduationCap',
    '탐구 아이디어': 'Lightbulb'
}

with open('batch_items.txt', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            # Simple splitter to avoid complex regex or eval
            id_val = line.split('id: ')[1].split(',')[0]
            type_val = line.split('type: "')[1].split('"')[0]
            title_val = line.split('title: "')[1].split('"')[0]
            desc_val = line.split('desc: "')[1].split('"')[0]
            icon_val = icon_map.get(type_val, 'Lightbulb')
            
            items.append(f'  {{ id: {id_val}, type: "{type_val}", icon: {icon_val}, title: "{title_val}", desc: "{desc_val}" }},')
        except:
            continue

with open('final_items.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(items))
