# 陈志伟的个人主页

主页地址：https://zwei-chen.github.io/

基于 [ArabelaTso/jialuncao.github.io](https://github.com/ArabelaTso/jialuncao.github.io) 的 AcadHomepage 模板配置。采用顶部导航、左侧个人信息、右侧正文的布局。

## 修改内容

| 文件 | 内容 |
| --- | --- |
| `_config.yml` | 姓名、身份、GitHub、邮箱、Google Scholar、头像路径 |
| `_pages/about.md` | 个人介绍、研究兴趣、教育经历、联系信息 |
| `_data/navigation.yml` | 顶部导航名称与锚点 |
| `images/avatar.jpg` | 配置时下载的 GitHub 头像；换头像时替换此文件 |
| `_sass/_custom.scss` | 少量布局和字体显示调整 |

邮箱和 Google Scholar 留空时不会显示。新增栏目时，为标题配置 id，并在导航文件中添加相应的 `#id` 链接。

## 本地预览

安装 Ruby 和 Bundler 后，在项目目录运行：

```sh
bundle install
bundle exec jekyll serve
```

打开 http://127.0.0.1:4000/ 。修改 `_config.yml` 后需重启预览服务。

## 发布

GitHub 仓库 Settings → Pages 中选择从分支发布（Deploy from a branch），分支为 `main`，目录为 `/ (root)`。提交并推送修改后，GitHub Pages 会自动构建网站。

## 致谢与许可

模板源自 AcadHomepage，并使用 Minimal Mistakes、Font Awesome 等组件。保留原模板 MIT 许可证及源码中的第三方版权说明。
