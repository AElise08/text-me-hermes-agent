---
name: matriz
description: "Prioriza tarefas por importância e urgência, protege metas de vida e trabalho e devolve um próximo passo claro."
version: 1.0.0
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [eisenhower, priorities, time, plow-chat]
---

# Matriz

Use quando a pessoa despejar tarefas, perguntar o que fazer primeiro, disser que está sobrecarregada ou quiser revisar a semana.

Antes de classificar, leia as metas de vida e trabalho com `python3 /var/lib/hermes/scripts/matriz.py goal show`. Importância significa contribuição para objetivo, responsabilidade ou valor real. Urgência exige prazo próximo ou consequência. Se um dos critérios estiver incerto, pergunte em vez de adivinhar.

Comandos:
```bash
python3 /var/lib/hermes/scripts/matriz.py goal set --category work --text "meta"
python3 /var/lib/hermes/scripts/matriz.py add --text "tarefa" --category work --important yes --urgent no --reason "move a meta semanal"
python3 /var/lib/hermes/scripts/matriz.py show
python3 /var/lib/hermes/scripts/matriz.py morning
python3 /var/lib/hermes/scripts/matriz.py done TASK_ID
python3 /var/lib/hermes/scripts/matriz.py update TASK_ID --important no --urgent yes --reason "prazo hoje, não move a meta"
```

Apresente poucos itens, preserve descanso intencional e escolha um começo. Q1 = fazer; Q2 = planejar/proteger; Q3 = reduzir/recusar/delegar se houver alguém adequado; Q4 = eliminar/limitar ou assumir como lazer consciente. Pareto é bússola, não regra. Brechas de 10-15 minutos servem para passos que caibam, não para colonizar descanso.

Separe sempre Vida e Trabalho na apresentação. Classifique pelo contexto e só pergunte quando a ambiguidade puder mudar a ordem. O serviço `matriz-nudge` envia o resumo diário às 09:00 usando `morning_nudge.py`.
