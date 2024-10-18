---
layout: post
title: "2012 [HotStorage] Delta Compressed and Deduplicated Storage Using Stream-Informed Locality"
author: "Ahan"
date: 2024-10-18 20:32:00
header-img: "img/post-bg-2015.jpg"
header-style: text
catalog:      true
tags:
    - storage dedup compression
---
![image.png](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F53604aeb-ad5f-4dad-9e0b-5d1f68812db8%2Fimage.png?table=block&id=11feda9f-236a-8025-8a04-e2c7bc6aec0b&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1420&userId=&cache=v2)

结合了两种 data reduce 技术：

1. Deduplication：重删
2. Delta Compression：先 delta，再压缩（LZ 算法）。

核心思路：

1. 先做重删，对于重复的数据块，直接引用。
2. 对于没有重复的数据块，通过 Sketch 找到类似的数据块：
    1. 如果找不到，说明是全新的块，直接压缩。
    2. 如果找到类似的，那么就可以计算出 delta。
        1. delta 部分压缩存储。

实验结果：

![image.png](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F2f82dff1-81e4-4484-96a6-a3be6661f49c%2Fimage.png?table=block&id=11feda9f-236a-8073-91ad-f1287eea31eb&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1420&userId=&cache=v2)

Delta Compression 大概能提升 1.4~3.5 倍的整体压缩率。

参考资料：[https://www.usenix.org/conference/hotstorage12/workshop-program/presentation/shilane](https://www.usenix.org/conference/hotstorage12/workshop-program/presentation/shilane)
