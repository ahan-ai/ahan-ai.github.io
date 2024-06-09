---
layout: post
title: "FAST '20 - HotRing: A Hotspot-Aware In-Memory Key-Value Store"
author:       "Ahan"
date: 2024-06-09 00:00:00
header-img: "img/post-bg-2015.jpg"
header-style: text
catalog:      true
tags:
    - Architecture
    - FAST
    - Storage
    - Key-value
---
# 问题背景

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F6e7d6bd0-ccae-4d3b-9400-ba3dec4fa505%2FUntitled.png?table=block&id=7a178843-024d-4aaf-9d46-b5e45d7f99ef&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1130&userId=&cache=v2)

数据热点：热点问题在in-memory KVS中被忽视了。从阿里巴巴生产环境的in-memory KVS中，本文发现50%～90%的请求只访问了1%的items。

为了解决热点问题，有以下的思路：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F57542b9f-d745-427e-9509-d389261271d1%2FUntitled.png?table=block&id=f67b1087-7143-4058-9f46-9cb8fa23b0f6&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1110&userId=&cache=v2)

文章提出了一种HotRing的热点感知KV数据结构，它具有以下特性：

- ordered-ring hash。把热点数据靠近头节点以快速访问
- 提供轻量级、运行态的热点迁移检测策略
- Lock-free设计
- read 565M ops，2.58X性能提升

# 解决方案

## Ordered-ring hash index

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F91aa76e8-d046-4149-af74-1174e49121a5%2FUntitled.png?table=block&id=62fb52db-2d04-428c-b467-ac722d350018&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1110&userId=&cache=v2)

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F1acbe06b-2732-44db-a96b-5c7a3227aad3%2FUntitled.png?table=block&id=3466d26b-c2c8-49e9-99fb-63c4f08dcdfa&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

关键设计点：

1. 顺序 - ring：为了在查询ring时，可以及时找到 key ，或及时退出（找不到key）

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F7245237c-2d06-4243-a10f-eee880019df5%2FUntitled.png?table=block&id=98f7dc49-4513-423e-9d81-6e7e255de2eb&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1110&userId=&cache=v2)

hash(key) 的值，被分为两个部分，前 k 位被用于定位这个 key 所在的 hash 桶，后(n-k) 位被认为是 key 的 tag。这样是为了避免比较两个比较大的 Key。

并且作者定位了一个顺序：order_k = (tag_k, key_k)，就是先比较 tag，然后才是 key。并且给出找到 key 和没有找到 key 的判断标准：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fe4c3e3fa-f050-4f47-a986-9e5dec4fc8d2%2FUntitled.png?table=block&id=fc430bd8-9827-40e8-a253-5a1d8faecee9&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1420&userId=&cache=v2)

其中 （5） 的后面两个不等式，考虑的是一个环上，首尾相接的位置。因为一般来说，环上的后一个 order 总是大于前一个 key 的 order，但在环的首尾相接的位置，会发生一个“突变”，例如下图中，F 的后续是 I，但是 I 的 order < F 的 order

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F5274ddca-b6d9-4edb-90bc-12c836d2929a%2FUntitled.png?table=block&id=a55a1cb0-9272-4345-9ec0-81e34cb29b93&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1920&userId=&cache=v2)

## Hotspot Shift Identification

热点可能会发生变化，论文提出两种更新热点的方式。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F62093941-b006-493a-9e84-4dca35f56bc1%2FUntitled.png?table=block&id=c08c4897-b1a4-4071-a7fb-60ebb7ac69ab&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1420&userId=&cache=v2)

### **Random Movement Strategy**

这种方案比较简单，每 R 次访问，尝试更新一下 head 指针，指向第 R 次访问的”热点“。

这种方式带有一定随机性，如果数据访问足够倾斜的话，效果不错，否则可能准确率不高。

### **Statistical Sampling Strategy**

从名称可以看出来，这种方案下，需要利用一定的统计数据来做出判断。

由于每个环中，既保留了环的整体访问次数，又保留了每个 item 的访问次数，由此我们可以计算出每个 item 的访问比例，并且定义一个 imcome 值，代表将头指针指向位置 t 的平均内存访问次数：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F3bff8880-a99b-4619-ac4a-04d7934aea36%2FUntitled.png?table=block&id=293b7cbf-9a52-4afd-96d5-795f01ba9223&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

最终选择能让 W_t 最小的头指针位置。

### 并发控制

具体见论文，主要是一些lock free的技巧，这里不再详细展开。

# 参考资料

https://www.usenix.org/system/files/fast20-chen_jiqiang.pdf

https://developer.aliyun.com/article/746727
