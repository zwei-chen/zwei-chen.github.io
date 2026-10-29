# 陈志伟的个人主页

主页地址：https://zwei-chen.github.io/

使用 [ArabelaTso/jialuncao.github.io](https://github.com/ArabelaTso/jialuncao.github.io) 的 AcadHomepage 模板，保留原有样式、顶部菜单、个人资料栏及全部栏目。未填写的栏目及导航自动隐藏，填写后自动显示。

## 修改内容

| 文件 | 内容 |
| --- | --- |
| `_config.yml` | 站点标题、GitHub、邮箱和学术主页等公共设置 |
| `_data/languages.yml` | 中英文姓名、身份、研究方向和个人介绍 |
| `_pages/about.md`、`_pages/about-en.md` | 中文和英文页面入口 |
| `_data/homepage_sections.yml` | 新闻、论文、教育等栏目内容；留空时自动隐藏正文和导航 |
| `_data/navigation.yml` | 原模板的顶部菜单和锚点 |
| `images/avatar.jpg` | 从 zwei-chen 的 GitHub 账号下载的头像 |

未提供的联系方式使用空值，不显示链接。Google Scholar 引用统计和 Analytics 尚未启用。填写对应信息后再配置。

## 栏目自动显示

在 `_data/homepage_sections.yml` 中填写各栏目的 `content`（中文）和 `content_en`（英文）。各语言独立判断：内容为空或只有空格时，该版正文和对应导航都不显示。可以使用 Markdown，例如：

```yaml
news:
  title: "🔥 News"
  anchor: "-news"
  content: |
    - 2026.10：这里填写一条真实的新闻。
  content_en: |
    - Oct 2026: Add the English translation here.
```

保留模板原有的栏目标题、顺序和样式。无需单独修改导航的显示状态。

## 中英文版本

中文首页位于 `/`，英文首页位于 `/en/`。右上角的「English / 中文」链接切换语言，刷新页面后仍保持当前语言。切换无需 JavaScript；两版共用头像、模板和样式。

在 `_data/languages.yml` 修改两种语言的个人资料和介绍。栏目标题的 `title_zh` 为中文，`title` 为英文；在 `_data/navigation.yml` 对应修改菜单名称。

## 本地预览

已在当前电脑安装 Homebrew Ruby 3.3；启动脚本会自动使用它，并检查项目依赖。

```sh
cd /Users/zwei/workspace/zwei-chen.github.io
./run_server.sh
```

打开 http://127.0.0.1:4000/ 。保持终端运行，按 `Ctrl+C` 停止。修改页面内容后刷新浏览器；修改 `_config.yml` 后需重启预览服务。

## 验证

```sh
export PATH="/opt/homebrew/opt/ruby@3.3/bin:$PATH"
bundle exec jekyll build --destination /private/tmp/zwei-homepage-check
python3 tests/check_bilingual.py /private/tmp/zwei-homepage-check --exercise-sections
```

检查中英文链接、个人资料、资源路径，以及只填写一种语言或只填写空格时的栏目显示。测试数据仅在临时目录中使用。

## 发布

GitHub Pages 使用 `main` 分支的 `/ (root)` 目录。提交并推送修改后，GitHub 自动构建发布。

## 模板与许可

模板的 Sass 样式和顶部菜单内容沿用原版。仅修正了原仓库缺失的父布局、站内跳转的全局新标签设置，并按实际资料配置网站元信息。

保留原 MIT 许可证和源码中的第三方版权说明。

## Dive Vision

四个独立工具均有中文、英文页面，外观默认为跟随系统，也可手动选择明亮或暗色。

| 工具 | 中文 | English |
|---|---|---|
| 潜水可视化：逐段独立速度、停留时长、组织腔隔、GF99、时间播放 | `/Diving/vision/` | `/en/Diving/vision/` |
| 潜水计划：ZHL-16C + GF 自动上升、换气、减压、耗气与氧暴露 | `/Diving/plan/` | `/en/Diving/plan/` |
| 潜水混气：分压法补气步骤与不可行原因 | `/Diving/blend/` | `/en/Diving/blend/` |
| SCR 小工具：水面等效 L/min 与气瓶相关 bar/min | `/Diving/scr/` | `/en/Diving/scr/` |

计算在 `Diving/vision/planner.py`，通过 `worker.mjs` 与 Pyodide 在浏览器内运行；
`engine.js` 处理加载、取消、超时与重试。`vision.js` 管理剖面工具，`utilities.js` 管理混气和 SCR，
`charts.js` 只负责图形与格式化。`_layouts/diving.html` 与 `_includes/diving/` 为共享双语页面，
`app.js` 管理外观偏好，`tools.css` 提供主题与响应式样式。

无需 Python 后端，可部署到 GitHub Pages。首次访问需联网加载固定版本 Pyodide CDN。
四种工具各自保存草稿，中英文版本共享同一份工具草稿。主题设置也保存在本机；选择“跟随系统”时响应系统主题变化。
所有工具页显示测试阶段免责声明。模型、混气压力定义和验证边界见 `Diving/vision/MODEL.md`。

本地运行 `./run_server.sh`，访问 <http://127.0.0.1:4000/Diving/vision/>。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_diving*.py'
# 在 Jekyll 构建完成后检查八个路由
python3 tests/check_diving_pages.py /path/to/build
```

CSV/SVG 导出代码保留；浏览器下载测试曾被用户拒绝，本次没有再次发起下载。

主要参数与高级参数在两页完整保留；可视化的上升/下潜速度放在各分段中，Python 自动计算分段耗时。两页不再提供换气耗时或自动安全停留设置。水体密度支持海水/淡水预设和自定义。
