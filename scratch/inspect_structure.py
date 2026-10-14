import docx

doc = docx.Document('отчет фронтенд.docx')
with open('scratch/docx_structure.txt', 'w', encoding='utf-8') as f:
    for i, p in enumerate(doc.paragraphs):
        runs_info = []
        for r in p.runs:
            runs_info.append(f'(text={repr(r.text)}, bold={r.bold}, italic={r.italic}, size={r.font.size}, name={r.font.name})')
        f.write(f'P{i} [style={p.style.name}]: text="{p.text}" | runs: {" ".join(runs_info)}\n')
print('Structure dumped successfully')
