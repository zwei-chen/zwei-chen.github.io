"""Check built tool routes, language output and local asset/link integrity."""
from html.parser import HTMLParser
from pathlib import Path
import re
import sys

root=Path(sys.argv[1])
class Page(HTMLParser):
    def __init__(self):super().__init__();self.lang=None;self.links=[];self.assets=[];self.text=[];self.skip=0;self.active=0;self.testing=False;self.stack=[];self.primary=[];self.advanced=[];self.names=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag not in ('input','meta','link','br','hr','img'):self.stack.append((tag,a))
        if tag in ('input','select') and a.get('name'):
            self.names.append(a['name'])
            if any('primary-settings' in parent.get('class','') for _,parent in self.stack):self.primary.append(a['name'])
            if any(t=='details' and 'advanced' in parent.get('class','') for t,parent in self.stack):self.advanced.append(a['name'])
            assert not any('hidden' in parent for _,parent in self.stack),a
        if tag=='html':self.lang=a.get('lang')
        if tag in ('script','style'):self.skip+=1
        if tag=='a':self.links.append(a.get('href',''));self.active+=a.get('aria-current')=='page'
        if tag=='script' and a.get('src'):self.assets.append(a['src'])
        if tag=='link' and a.get('rel')=='stylesheet':self.assets.append(a['href'])
        if 'testing-notice' in a.get('class',''):self.testing=True
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:];break
        if tag in ('script','style'):self.skip-=1
    def handle_data(self,data):
        if not self.skip:self.text.append(data)

for language,prefix in [('zh',''),('en','en/')]:
    for tool in ('vision','plan','blend','scr'):
        path=root/prefix/'Diving'/tool/'index.html'
        page=Page();page.feed(path.read_text())
        assert page.lang==('en' if language=='en' else 'zh-CN'),path
        assert page.active==1 and page.testing,path
        for other in ('vision','plan','blend','scr'):
            assert '/'+prefix+'Diving/'+other+'/' in page.links,path
        target=('/Diving/' if language=='en' else '/en/Diving/')+tool+'/'
        assert target in page.links,path
        for url in page.assets:assert (root/url.lstrip('/')).is_file(),(path,url)
        if tool in ('vision','plan'):
            expected=['gfHigh','gfLow']+(['ascentRate','descentRate'] if tool=='plan' else [])+['waterType','sacWork']
            assert page.primary==expected,(path,page.primary)
            assert set(page.advanced)=={'density','surfacePressure','altitude','ppo2Work','reserve','sacDeco','ppo2Deco','lastStop'},(path,page.advanced)
            assert not {'switchTime','safetyStop'} & set(page.names),path
        if language=='en':
            text=''.join(page.text).replace('中文','')
            assert not re.search('[\u4e00-\u9fff]',text),(path,'untranslated Chinese')
print('PASS: 8 bilingual tool routes, navigation, disclaimer, assets, parameter grouping and English copy.')
