---
layout: post
title: "2022[FAST]Separating Data via Block Invalidation Time Inference for Write Amplification Reduction in Log-Structured Storage"
author:       "Ahan"
date: 2024-06-30 00:00:00
header-img: "img/post-bg-2015.jpg"
header-style: text
catalog:      true
tags:
    - Architecture
    - FAST
    - Storage
    - Write Amplification
---
# 背景和问题

1. 云上块存储，通常是基于append-only的底层存储实现的，数据以block为单位被append到segment中。
2. segment 中包含多个block，其中一部分是有效的，一部分是无效的。
3. 需要通过 GC 来回收无效的block，并把segment中有效的block重新写入新的segment，以回收旧的segment。
4. GC的过程，会带来写放大（write amplification）WA不仅会导致后台有额外IO负载，还会减少闪存寿命以及数据中心不必要的能源消耗。
5. 大量研究集中于data placement策略，本文提出data placement的策略应该通过block invalidation time(**BIT**)将blocks聚集从而实现最小WA。现有temperature-based(write/update频率)data placement策略经常诟病于获取BIT pattern不准确并无法有效将拥有相似BIT的blocks聚集。

基于这个背景，本文作者提出了一种全新的data placement方案——**SepBIT，**根据现有存储负载推测写入blocks的BITs，并将其分散放置于不同groups，每个group保存有相似BITs的blocks**。**该方案基于skewed write patterns云存储负载，它将写入的blocks划分为**user-written** blocks和**GC-rewritten** blocks，同时根据每个block的BIT进行进一步细粒度划分。

作者基于Zoned Storage/ZenFs 做了一些模拟实验，但似乎没有在阿里云上实际落地。

# 解决方案

首先定义每个block的 lifespan：number of bytes written from when a block is written until it is
invalidated (or until the end of the trace)

**在放置block的时候，最理想的情况，是把寿命相近的block，放在同一个segment中，这样当我们回收一个 segment的时候，当中大部分的block由于寿命相近，就都一起无效了，也就不需要再被写入新的segment了，于是 WA 就降低了**。

然后作者根据阿里云跟踪到的数据，得到3个结论：

- Observation 1：User-written blocks通常寿命较短，GC-rewritten blocks有较长的寿命
- Observation 2：频繁更新的blocks，其寿命偏差较大
- Observation 3：不常被更新的blocks的寿命偏差同样很大。

基于以上3个observations推断出，当前**temperature-based** (eg. 访问频率) data placement 方法无法有效将拥有相似 BITs 的blocks聚集在一起，因此WA无法有效缓解。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F4f2ded50-1a7f-4397-ab08-c85d788d9526%2FUntitled.png?table=block&id=e03147fa-666b-4b79-affb-549bc21cd73e&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=800&userId=&cache=v2)

首先，由于用户写入的数据块，和GC写入的数据块，其寿命有明显的不同，作者将两种数据块做了显式的分流。用户写入的数据块，又细分为2个类型。

其次，由于GC写入的数据块，其寿命差别较大，因此作者将GC写入的数据块，又根据 BIT inference 细分为4个类型。

**SepBIT，Sep = Separate，意思就是本质上是根据block 的 BIT 的推断（因为不可能准确预估 BIT）来将 block separate 到不同的 segment 上**。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F7b106a71-1ef7-45c0-9fe6-b5dc412e37f3%2FUntitled.png?table=block&id=b78cdc8c-8496-4186-a72d-00bf07c51ccd&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

如上图所示：

- User-written blocks
    - 类型1：存放用户写入的短期 block
    - 类型2：存放用户写入的除类型1之外的 block
- GC-rewritten blocks
    - 类型3：当类型1的  segment 发生 GC 时，其有效数据被写入类型3
    - 类型4~类型6：来自类型2~6的数据

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fe828c36f-3230-4f23-9c36-10cccb802610%2FUntitled.png?table=block&id=e9b042c6-85a4-4328-a8f0-0b81fc0651ed&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

那如何来判断一个用户写入的数据，将会是短期(short-lived) block 呢？如上图所示，通过数据分析，作者发现，如果一个 block 在无效时，其 lifespan 很短，那么新写入的 block，其 lifespan 通常也很短。并且基于阿里云上观察到的数据集，发现这个结论很大程度上是正确的。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F0138bcc9-313d-48cf-ba92-4a1081e18f68%2FUntitled.png?table=block&id=25840e1b-649c-4235-873f-cf18fb5702de&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1150&userId=&cache=v2)

对于 GC-rewritten Block，类似的，作者认为，block 将会继续存活的时间（Residual lifespan）大概率等同于已经存在的时间（age）。基于这个结论，作者将被 GC 写入的 block，按其 age 再次分为4个档次，分别写入4种不同的 segment中。

# 实验

实验上，作者采用的是仿真实验，并没有在阿里云的实际场景中落地。从仿真实验看来，SepBIT 在减少写放大上的效果几乎是最好的。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F504dd55c-2de2-4f71-89ff-546d2f0b1a60%2FUntitled.png?table=block&id=5ffa570f-fbed-4f56-a25a-d5f011680ebe&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

在吞吐量上，也是最好的：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fa1c75ca0-3301-495b-8348-e0e57caef584%2FUntitled.png?table=block&id=754926e6-a341-42ef-be42-f3a5e7955e69&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1420&userId=&cache=v2)
