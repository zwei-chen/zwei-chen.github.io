"""Check the real Jekyll output, including locale-specific empty sections."""
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.lang = None
        self.ids = set()
        self.links = []
        self.assets = []
        self.text = []
        self.in_nav = False
        self.current_link = None
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'html': self.lang = attrs.get('lang')
        if attrs.get('id'): self.ids.add(attrs['id'])
        if tag == 'nav': self.in_nav = attrs.get('id') == 'site-nav'
        if tag == 'a':
            self.current_link = dict(attrs, text='', nav=self.in_nav)
            self.links.append(self.current_link)
        if tag in ('img', 'script') and attrs.get('src'):
            self.assets.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') in ('icon', 'stylesheet'):
            self.assets.append(attrs['href'])

    def handle_endtag(self, tag):
        if tag == 'nav': self.in_nav = False
        if tag == 'a': self.current_link = None

    def handle_data(self, data):
        self.text.append(data)
        if self.current_link is not None: self.current_link['text'] += data


def check(build, fixture=False):
    for path, language, switch_to, name, university in [
        ('index.html', 'zh-CN', '/en/', '陈志伟', '武汉大学'),
        ('en/index.html', 'en', '/', 'Zhiwei Chen', 'Wuhan University'),
    ]:
        page = Page(build / path)
        assert page.lang == language, f'{path}: incorrect document language'
        switches = [link for link in page.links if 'language-switch' in link.get('class', '').split()]
        assert len(switches) == 1 and switches[0]['href'] == switch_to, f'{path}: missing working language switch'
        assert name in ''.join(page.text) and university in ''.join(page.text), f'{path}: untranslated profile'
        for link in [link for link in page.links if link['nav']]:
            url = urlsplit(link['href'])
            expected_path = '/en/' if language == 'en' else '/'
            assert url.path == expected_path, f'{path}: navigation leaves the selected language'
            assert url.fragment in page.ids, f'{path}: navigation points to a hidden/missing section'
        for asset in page.assets:
            url = urlsplit(asset)
            if url.netloc: continue
            assert url.path.startswith('/'), f'{path}: relative asset breaks the English route: {asset}'
            assert (build / url.path.lstrip('/')).is_file(), f'{path}: missing asset: {asset}'
        if fixture:
            assert '-teaching' not in page.ids, f'{path}: blank teaching section should stay hidden'
            expected_news = language == 'en'
            assert ('-news' in page.ids) == expected_news, f'{path}: section visibility uses the wrong language'
            nav_news = [link for link in page.links if link['nav'] and urlsplit(link['href']).fragment == '-news']
            assert bool(nav_news) == expected_news, f'{path}: empty section has a visible navigation link'
    print(f'PASS: both languages, switching, navigation, profiles and assets ({"partial translations" if fixture else "homepage"}).')


build = Path(sys.argv[1])
check(build)
if '--exercise-sections' in sys.argv:
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='zwei-bilingual-') as temporary:
        source = Path(temporary).resolve() / 'source'
        def ignore(directory, names):
            if Path(directory) == project:
                return set(names) & {'.git', '_site', 'vendor', '.jekyll-cache', '.sass-cache'}
            return set()
        shutil.copytree(project, source, ignore=ignore)
        data = source / '_data/homepage_sections.yml'
        content = data.read_text()
        content = re.sub(r'^news:.*?(?=^\w+:|\Z)', """news:
  title: "News"
  title_zh: "最新动态"
  anchor: "-news"
  content: ""
  content_en: "A news item for the English test fixture."

""", content, count=1, flags=re.M | re.S)
        content = re.sub(r'^teaching:.*?(?=^\w+:|\Z)', """teaching:
  title: "Teaching"
  title_zh: "教学经历"
  anchor: "-teaching"
  content: ""
  content_en: "   "

""", content, count=1, flags=re.M | re.S)
        data.write_text(content)
        fixture_build = Path(temporary).resolve() / 'build'
        subprocess.run(['bundle', 'exec', 'jekyll', 'build', '--source', str(source), '--destination', str(fixture_build)], cwd=project, check=True)
        check(fixture_build, fixture=True)
