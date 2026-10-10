# 陈志伟的个人主页

主页地址：https://zwei-chen.github.io/

使用 [ArabelaTso/jialuncao.github.io](https://github.com/ArabelaTso/jialuncao.github.io) 的 AcadHomepage 模板，保留原有样式、顶部菜单、个人资料栏及全部栏目。未填写的栏目及导航自动隐藏，填写后自动显示。

## 修改内容

| 文件 | 内容 |
| --- | --- |
| `_config.yml` | 姓名、身份、研究方向简介、GitHub、邮箱和学术主页 |
| `_pages/about.md` | 个人介绍 |
| `_data/homepage_sections.yml` | 新闻、论文、教育等栏目内容；留空时自动隐藏正文和导航 |
| `_data/navigation.yml` | 原模板的顶部菜单和锚点 |
| `images/avatar.jpg` | 从 zwei-chen 的 GitHub 账号下载的头像 |

未提供的联系方式使用空值，不显示链接。Google Scholar 引用统计和 Analytics 尚未启用。填写对应信息后再配置。

## 栏目自动显示

在 `_data/homepage_sections.yml` 中填写各栏目的 `content`。内容为空或只有空格时，正文和对应导航都不显示。可以使用 Markdown，例如：

```yaml
news:
  title: "🔥 News"
  anchor: "-news"
  content: |
    - 2026.10：这里填写一条真实的新闻。
```

保留模板原有的栏目标题、顺序和样式。无需单独修改导航的显示状态。

## 本地预览

已在当前电脑安装 Homebrew Ruby 3.3；启动脚本会自动使用它，并检查项目依赖。

```sh
cd /Users/zwei/workspace/zwei-chen.github.io
./run_server.sh
```

打开 http://127.0.0.1:4000/ 。保持终端运行，按 `Ctrl+C` 停止。修改页面内容后刷新浏览器；修改 `_config.yml` 后需重启预览服务。

## 发布

GitHub Pages 使用 `main` 分支的 `/ (root)` 目录。提交并推送修改后，GitHub 自动构建发布。

## 模板与许可

模板的 Sass 样式和顶部菜单内容沿用原版。仅修正了原仓库缺失的父布局、站内跳转的全局新标签设置，并按实际资料配置网站元信息。

保留原 MIT 许可证和源码中的第三方版权说明。
