---
layout: post
title: "2019 QZFS: QAT Accelerated Compression in File System for Application Agnostic and Cost Efficient Data Storage"
author:       "Ahan"
date: 2024-02-11 00:00:00
header-img: "img/post-bg-2015.jpg"
header-style: text
catalog:      true
tags:
    - Architecture
    - Storage
---
# 问题背景

本文介绍了一种名为QZFS的文件系统，它集成了**Intel R© QAT**加速器，用于在ZFS文件系统中进行**数据压缩**，以提供应用无关和成本高效的数据存储。文章的背景是，在大数据处理和云计算等领域，**高存储I/O性能**和**低总成本**是两个重要的优化目标，但这两个目标往往难以同时实现。数据压缩被认为是一种有效的解决方案，但压缩任务会消耗大量的计算资源，可能会影响应用程序的运行。因此，本文提出了在文件系统级别进行数据压缩的方法，以提高存储效率和性能。通过实验验证，QZFS可以有效地**节省CPU资源**，并进一步提高大数据处理工作负载的性能。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F55ac561c-b2e3-4958-b3b3-0004638b448b%2FUntitled.png?table=block&id=11c26ad6-4fcf-4a2e-9f85-4384f763d428&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

# 效果

在不同的操作下，使用QAT加速的gzip在QZFS中能够实现显著的性能提升和成本效率。例如，在三个节点的集群中，平均执行时间减少了63.10%，成本效率提高了6倍以上。在四个节点的集群中，平均执行时间减少了63.14%，成本效率提高了6.26倍。同时，在实际的基因组数据处理中，使用QAT加速的QZFS能够提供65.83%的平均执行时间减少和75.58%的CPU资源消耗减少。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F0f380ebe-ea31-47c3-8ca3-43d178902e6b%2FUntitled.png?table=block&id=389857c0-a926-4e8f-ba4d-f5cd86fa89cd&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

# 启发

- Again，硬件加速在存储系统将会越来越大规模使用。
- 硬件压缩、解压缩将会是高性能存储系统的标配。
- 不同的压缩算法具有不同的压缩比和CPU资源消耗。gzip算法具有高压缩比，但CPU资源消耗也较高；LZ4算法具有较低的CPU资源消耗，但压缩比也较低。但是在硬件加解密的场景下，使用 gzip 来获取更高的压缩比，可能会让整体的成本更低。

参考资料：

论文链接：https://www.usenix.org/system/files/atc19-hu.pdf

视频：https://www.youtube.com/watch?v=OVBQVEEIFVE&t=149s&ab_channel=USENIX
