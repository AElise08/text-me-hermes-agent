#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,uuid
from datetime import datetime
from pathlib import Path
CATS=('work','life'); QS=('Q1','Q2','Q3','Q4')
def home(): return Path(os.environ.get('HERMES_HOME','/var/lib/hermes'))
def path(): return home()/'.matriz'/'state.json'
def blank(): return {'goals':{'work':'','life':''},'tasks':[],'language':''}
def load():
 try:d=json.loads(path().read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError): return blank()
 if 'goals' not in d:d['goals']={'work':d.pop('goal',''),'life':''}
 d.setdefault('language','')
 for t in d.setdefault('tasks',[]):t.setdefault('category','work')
 return d
def save(d):
 p=path();p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix('.tmp');q.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.chmod(q,0o600);q.replace(p)
def yn(v):return {'yes':True,'no':False}[v]
def quad(i,u):return 'Q1' if i and u else 'Q2' if i else 'Q3' if u else 'Q4'
def public(t):return {k:t[k] for k in ('id','text','category','quadrant','reason','done')}
def grouped(tasks):return {c:{q:[public(t) for t in tasks if t['category']==c and t['quadrant']==q] for q in QS} for c in CATS}
def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
 g=s.add_parser('goal');gs=g.add_subparsers(dest='action',required=True);showg=gs.add_parser('show');showg.add_argument('--category',choices=CATS);st=gs.add_parser('set');st.add_argument('--category',choices=CATS,required=True);st.add_argument('--text',required=True)
 lang=s.add_parser('language');ls=lang.add_subparsers(dest='action',required=True);ls.add_parser('show');lset=ls.add_parser('set');lset.add_argument('value',choices=('en','pt'))
 a=s.add_parser('add');a.add_argument('--text',required=True);a.add_argument('--category',choices=CATS,required=True);a.add_argument('--important',choices=['yes','no'],required=True);a.add_argument('--urgent',choices=['yes','no'],required=True);a.add_argument('--reason',default='')
 sh=s.add_parser('show');sh.add_argument('--include-done',action='store_true');s.add_parser('morning');d=s.add_parser('done');d.add_argument('id')
 u=s.add_parser('update');u.add_argument('id');u.add_argument('--category',choices=CATS);u.add_argument('--important',choices=['yes','no']);u.add_argument('--urgent',choices=['yes','no']);u.add_argument('--reason');u.add_argument('--text')
 x=p.parse_args();data=load()
 if x.cmd=='goal':
  if x.action=='set':data['goals'][x.category]=x.text.strip();save(data)
  print(json.dumps({'goals':data['goals']} if not getattr(x,'category',None) else {'category':x.category,'goal':data['goals'][x.category]},ensure_ascii=False));return
 if x.cmd=='language':
  if x.action=='set':data['language']=x.value;save(data)
  print(json.dumps({'language':data['language']}));return
 if x.cmd=='add':
  i,u=yn(x.important),yn(x.urgent);t={'id':uuid.uuid4().hex[:8],'text':x.text.strip(),'category':x.category,'important':i,'urgent':u,'quadrant':quad(i,u),'reason':x.reason.strip(),'done':False,'created_at':datetime.now().astimezone().isoformat()};data['tasks'].append(t);save(data);print(json.dumps({'created':public(t)},ensure_ascii=False));return
 if x.cmd in ('done','update'):
  t=next((z for z in data['tasks'] if z['id']==x.id),None)
  if not t:raise SystemExit('task not found')
  if x.cmd=='done':t['done']=True
  else:
   for k in ('category','reason','text'):
    v=getattr(x,k,None)
    if v is not None:t[k]=v.strip()
   if x.important:t['important']=yn(x.important)
   if x.urgent:t['urgent']=yn(x.urgent)
   t['quadrant']=quad(t['important'],t['urgent'])
  save(data);print(json.dumps({'updated':public(t)},ensure_ascii=False));return
 active=[t for t in data['tasks'] if not t.get('done')]
 if x.cmd=='show':
  tasks=data['tasks'] if x.include_done else active;print(json.dumps({'goals':data['goals'],'categories':grouped(tasks)},ensure_ascii=False));return
 print(json.dumps({'goals':data['goals'],'categories':{'work':{'do_now':[public(t) for t in active if t['category']=='work' and t['quadrant']=='Q1'][:3],'protect_next':[public(t) for t in active if t['category']=='work' and t['quadrant']=='Q2'][:3]},'life':{'do_now':[public(t) for t in active if t['category']=='life' and t['quadrant']=='Q1'][:3],'protect_next':[public(t) for t in active if t['category']=='life' and t['quadrant']=='Q2'][:3]}},'active_count':len(active),'language':data['language']},ensure_ascii=False))
if __name__=='__main__':main()
