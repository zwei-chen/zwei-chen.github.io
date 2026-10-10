# 陈志伟的个人主页

主页地址：https://zwei-chen.github.io/

使用 [ArabelaTso/jialuncao.github.io](https://github.com/ArabelaTso/jialuncao.github.io) 的 AcadHomepage 模板，保留原有样式、顶部菜单、个人资料栏及全部栏目。未提供的经历和成果标为“待补充”。

## 修改内容

| 文件 | 内容 |
| --- | --- |
| `_config.yml` | 姓名、身份、研究方向简介、GitHub、邮箱和学术主页 |
| `_pages/about.md` | 个人介绍、新闻、论文、教育等各栏目内容 |
| `_data/navigation.yml` | 原模板的顶部菜单和锚点 |
| `images/avatar.jpg` | 从 zwei-chen 的 GitHub 账号下载的头像 |

未提供的联系方式使用空值，不显示链接。Google Scholar 引用统计和 Analytics 尚未启用。填写对应信息后再配置。

## 本地预览

使用新版 Ruby 和 Bundler；macOS 自带的 Ruby 2.6 无法解析当前依赖。

```sh
bundle install
bundle exec jekyll serve
```

打开 http://127.0.0.1:4000/ 。修改 `_config.yml` 后需重启预览服务。

## 发布

GitHub Pages 使用 `main` 分支的 `/ (root)` 目录。提交并推送修改后，GitHub 自动构建发布。

## 模板与许可

模板的 Sass 样式和顶部菜单内容沿用原版。仅修正了原仓库缺失的父布局、站内跳转的全局新标签设置，并按实际资料配置网站元信息。

保留原 MIT 许可证和源码中的第三方版权说明。
