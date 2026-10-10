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
