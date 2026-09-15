#!/usr/bin/env python3
import json,os,subprocess
from pathlib import Path
home=Path(os.environ.get('HERMES_HOME','/var/lib/hermes'))
script=home/'scripts'/'matriz.py'
if not script.exists(): script=Path(__file__).with_name('matriz.py')
data=json.loads(subprocess.check_output(['python3',str(script),'morning'],text=True))
lang=data.get('language') or ''; cats=data['categories']; goals=data['goals']
def pick(c):return (cats[c]['do_now']+cats[c]['protect_next'])[:1]
work,life=pick('work'),pick('life')
if not lang:
 print("Good morning. What's the most important - not necessarily urgent - thing today? / Bom dia. Qual é a coisa mais importante - não necessariamente urgente - de hoje?")
 raise SystemExit
if lang=='pt':
 if not work and not life and not any(goals.values()):print('Bom dia. Qual é a coisa mais importante - não necessariamente urgente - de hoje?')
 else:
  parts=[]
  if work:parts.append('Trabalho: '+work[0]['text'])
  elif goals.get('work'):parts.append('Trabalho: avance '+goals['work'])
  if life:parts.append('Vida: '+life[0]['text'])
  elif goals.get('life'):parts.append('Vida: avance '+goals['life'])
  print('Bom dia. Foco de hoje: '+'; '.join(parts)+'. O que é importante, mesmo sem urgência, que precisa de espaço hoje?')
else:
 if not work and not life and not any(goals.values()):print("Good morning. What's the most important - not necessarily urgent - thing today?")
 else:
  parts=[]
  if work:parts.append('Work: '+work[0]['text'])
  elif goals.get('work'):parts.append('Work: move '+goals['work'])
  if life:parts.append('Life: '+life[0]['text'])
  elif goals.get('life'):parts.append('Life: move '+goals['life'])
  print("Good morning. Today's focus: "+'; '.join(parts)+". What important, even if not urgent, thing needs space today?")
