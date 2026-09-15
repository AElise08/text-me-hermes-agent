import json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SCRIPT=ROOT/'scripts'/'matriz.py'; NUDGE=ROOT/'scripts'/'morning_nudge.py'
class MatrixTests(unittest.TestCase):
 def cli(self,h,*a):return json.loads(subprocess.check_output(['python3',str(SCRIPT),*a],env={**os.environ,'HERMES_HOME':h},text=True))
 def test_life_work_quadrants_goals_and_morning(self):
  with tempfile.TemporaryDirectory() as h:
   self.cli(h,'goal','set','--category','work','--text','Ship');self.cli(h,'goal','set','--category','life','--text','Sleep')
   w=self.cli(h,'add','--text','report','--category','work','--important','yes','--urgent','yes')['created'];l=self.cli(h,'add','--text','walk','--category','life','--important','yes','--urgent','no')['created']
   show=self.cli(h,'show');self.assertEqual(show['goals'],{'work':'Ship','life':'Sleep'});self.assertEqual(show['categories']['work']['Q1'][0]['id'],w['id']);self.assertEqual(show['categories']['life']['Q2'][0]['id'],l['id'])
   m=self.cli(h,'morning');self.assertEqual(m['categories']['work']['do_now'][0]['text'],'report');self.assertEqual(m['categories']['life']['protect_next'][0]['text'],'walk')
 def test_nudge_empty_and_pt(self):
  with tempfile.TemporaryDirectory() as h:
   e={**os.environ,'HERMES_HOME':h};out=subprocess.check_output(['python3',str(NUDGE)],env=e,text=True);self.assertIn('most important',out);self.assertIn('mais importante',out)
   self.cli(h,'language','set','pt');out=subprocess.check_output(['python3',str(NUDGE)],env=e,text=True);self.assertIn('mais importante',out)
 def test_update_category(self):
  with tempfile.TemporaryDirectory() as h:
   x=self.cli(h,'add','--text','x','--category','work','--important','no','--urgent','yes')['created'];y=self.cli(h,'update',x['id'],'--category','life','--important','yes','--urgent','no')['updated'];self.assertEqual((y['category'],y['quadrant']),('life','Q2'))
if __name__=='__main__':unittest.main()
