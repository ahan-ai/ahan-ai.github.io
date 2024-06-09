#!/usr/bin/env python3
# This is a sample Python script.
from typing import List
import argparse
import requests  # type: ignore
from selenium import webdriver # type: ignore
import time
import re
import os
from datetime import datetime


def get_page_content(url) -> str:
    # 创建 Chrome WebDriver
    driver = webdriver.Chrome()

    # 打开网页
    driver.get(url)

    # 等待一定时间，确保动态内容加载完成（或者根据需要使用显式等待方法）
    time.sleep(30)
    # 获取动态生成的内容
    dynamic_content = driver.page_source
    # 关闭浏览器
    driver.quit()
    return dynamic_content


def get_notion_content(url: str) -> str:
    return get_page_content(url)


def get_notion_image_url(notion_content: str) -> List[str]:
    pattern = r'src="(/image/https.*?spaceId=.*?)"'
    matches = re.findall(pattern, notion_content)
    web_site = "https://ahan-ai.notion.site"

    image_url_list = []
    for match in matches:
        # image_url = match[0] + match[1]
        image_url = match
        # 去掉 "amp;"
        modified_string = image_url.replace("&amp;", "&")
        image_url_list.append(web_site + modified_string)
    return image_url_list


def gen_github_content(image_url_list: List[str]) -> str:
    return ""


def gen_github_file(content: str) -> None:
    temp = """
    
    """
    pass


def replace_image_url_in_original_md(
    md_content: str, real_image_url_list: List[str]
) -> str:
    pattern = r"!\[.*?\]\((.*?)\)"
    matches = re.findall(pattern, md_content)
    new_text = md_content
    if len(matches) != len(real_image_url_list):
        raise Exception(
            f"length does not match:{len(matches)},{len(real_image_url_list)}"
        )

    for i, match in enumerate(matches):
        print(f"match:{match}")
        new_text = new_text.replace(match, real_image_url_list[i])
    return new_text


blog_post_template = """---
layout: post
title: "{title}"
author: "Ahan"
date: {date}
header-img: "img/post-bg-2015.jpg"
header-style: text
catalog:      true
tags:
{tags}
---
{md_text}
"""


def gen_md(md_path: str, real_image_url_list: List[str], key_words: List[str]) -> None:
    """替换 image 地址，并在 markdown 头部加上关键字，生成最终的markdown"""

    new_md_text = ""
    with open(md_path) as f:
        md_text = f.read()
        md_text = replace_image_url_in_original_md(md_text, real_image_url_list)
        if not md_text.startswith("---"):
            # 去掉文件名前面的一串日期
            first_line = md_text.split("\n")[0]
            title = first_line[2:]
            md_text = "\n".join(md_text.split("\n")[2:])
            tags = "\n".join(["    - {keyword}".format(keyword=k) for k in key_words])
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"tags:{tags}")
            print(f"======\n{md_text}")
            md_text = blog_post_template.format(
                title=title, date=current_time, tags=tags, md_text=md_text
            )
        new_md_text = md_text
    with open(md_path, "w") as f:
        f.write(new_md_text)


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="Process notion URL and keywords")
    parser.add_argument(
        "--md", required=True, type=str, help="original markdown file path"
    )
    parser.add_argument(
        "--notion_url", required=True, type=str, help="URL for my Notion page"
    )
    parser.add_argument(
        "--keywords",
        required=False,
        help="Keywords of the markdown file, separated by commas",
    )

    args = parser.parse_args()

    # 拉取 notion 内容
    notion_content = get_notion_content(args.notion_url)

    # print(notion_content)
    # 获取 notion 里的 image 列表
    image_url_list = get_notion_image_url(notion_content)
    keywords = []
    if args.keywords:
        keywords = args.keywords.split(",")
    gen_md(args.md, image_url_list, keywords)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
