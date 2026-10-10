---
permalink: /
title: ""
excerpt: "陈志伟，武汉大学博士研究生。研究兴趣：计算机视觉、水下场景的三维重建。"
author_profile: true
analytics: false
redirect_from:
  - /about/
  - /about.html
---

<span class='anchor' id='about-me'></span>

我是 **陈志伟**，目前是 **武汉大学博士研究生**。

我的研究兴趣是 **计算机视觉** 和 **水下场景的三维重建**。

{% for entry in site.data.homepage_sections %}
{% assign section = entry[1] %}
{% assign section_content = section.content | default: "" | strip %}
{% if section_content != "" %}
# {{ section.title }}
{: #{{ section.anchor }}}

{{ section_content }}

{% endif %}
{% endfor %}
