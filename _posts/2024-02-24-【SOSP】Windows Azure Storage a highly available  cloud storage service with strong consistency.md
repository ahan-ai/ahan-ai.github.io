---
layout: post
title: "2011【SOSP】Windows Azure Storage: a highly available cloud storage service with strong consistency"
author: "Ahan"
date: 2024-02-24 21:42:59
header-img: "img/post-bg-2015.jpg"
header-style: text
catalog:      true
tags:
    - storage
---
写在前面：

论文介绍了微软 Azure 存储（Windows Azure Storage，简称 WAS）的整体架构，虽然是2011年写的，但是对于云存储仍然十分具有参考价值。本篇论文的其中一个作者Jiesheng Wu目前正是阿里云的存储负责人。国内的阿里云、字节的存储架构，都很大程度上受到 Azure 存储架构的影响，特别是盘古和 Bytestore，整体架构几乎是照搬 Steam 层。

# 概述

Windows Azure Storage（WAS）是一个可扩展的云存储系统，自2008年11月开始投入生产使用。微软内部使用WAS来支持社交网络搜索、视频、音乐和游戏内容服务、医疗记录管理等应用。此外，还有数千个微软外部的客户在使用WAS，任何人都可以通过互联网注册来使用该系统。

WAS提供以Blob（用户文件）、Table（结构化存储）和Queue（消息传递）的形式的云存储。这三种数据抽象为许多应用程序提供了整体的存储和工作流程。我们经常看到的一种常见用法是通过Blobs传输进出数据，Queues提供处理Blobs的整体工作流程，并且中间服务状态和最终结果保存在Tables或Blobs中。

WAS 的主要特性：

- 强一致性（Strong Consistency - 许多客户都希望获得强一致性，特别是将其业务应用程序迁移到云端的企业客户。他们还希望能够对强一致性数据执行条件读取、写入和删除，以进行乐观并发控制。
- 全局和可扩展的命名空间/存储（Global and Scalable Namespace/Storage –） - 为了方便使用，WAS实现了一个全局命名空间，允许以一致的方式存储和访问数据，无论其位于世界上的哪个位置。由于WAS的一个主要目标是支持海量数据的存储，这个全局命名空间必须能够处理超过艾字节（exabyte）的数据及更多。
- 灾难恢复（Disaster Recovery） - WAS在彼此相距数百英里的多个数据中心中存储客户数据。这种冗余提供了对抗地震、野火、龙卷风、核反应堆熔毁等灾难的重要数据恢复保护。
- 多租户和存储成本（Multi-tenancy and Cost of Storage） - 为了降低存储成本，许多客户都使用相同的共享存储基础设施。WAS将许多不同客户的工作负载与各种资源需求集成在一起，因此相比于这些服务在自己的专用硬件上运行时，任何时刻需要预配的存储要少得多。

# Global Partitioned Namespace

存储系统的一个关键目标是提供一个单一的全局命名空间，允许客户在云中管理其所有存储，并能够根据需要随时间扩展到任意量级的存储空间。为了实现这一能力，WAS 利用DNS作为存储命名空间的一部分，并将存储命名空间分为三个部分：帐户名称、分区名称和对象名称：

http(s)://**AccountName**.<service>.core.windows.net/**PartitionName**/**ObjectName**

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F1ed27b3d-25a1-49ca-9923-452bdb9d0e49%2FUntitled.png?table=block&id=d70cc856-8046-4f0a-b9dc-bf0dc6eafccf&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

**AccountName**是客户选择的用于访问存储的帐户名称，它是DNS主机名的一部分。 AccountName的DNS转换用于定位存储数据的主存储集群和数据中心。这个主要位置是所有请求到达该帐户的数据的地方。一个应用程序可以使用多个AccountNames将其数据存储在不同的位置。

与AccountName配合使用的**PartitionName**用于在请求到达存储集群后定位数据。根据流量需求，PartitionName用于在存储节点之间扩展对数据的访问。

当一个PartitionName包含多个对象时，**ObjectName**用于标识该分区内的单个对象。系统支持具有相同PartitionName值的对象之间的原子事务。ObjectName是可选的，因为对于某些类型的数据，PartitionName可以唯一标识帐户内的对象。

**service**：指定了service type, 可以是 blob, table 或 queue。

这种命名方法使WAS能够灵活地支持其三个数据抽象。对于Blobs，完整的Blob名称是PartitionName。对于Tables，表中的每个实体（行）都有一个由两个属性组成的主键：PartitionName和ObjectName。这种区别允许使用Tables的应用程序将行分组到同一分区以进行跨行的原子事务。对于Queues，队列名称是PartitionName，每个消息都有一个ObjectName来在队列中唯一标识它。

# 整体架构

## WAS Architectural Components

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fs3-us-west-2.amazonaws.com%2Fsecure.notion-static.com%2Fe1b4260e-ab6c-44f9-8b8a-8699f10eb9bd%2FUntitled.png?table=block&id=3a268e81-5aa7-4783-b676-69d4b4e994fa&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1110&userId=&cache=v2)

WAS 的架构整体可以分为两大组件：

- **Storage Stamp**：负责数据存储。包括10到20个机柜，每个机柜18个节点，可存储 2 PB 的数据量。第二次可增加到30PB。
- **Location Service:** 负责管理 Storage Stamp，管理 Account → Storage Stamp 的映射关系。并通过更新 DNS，将 account 相关的请求引入到对应的 Storage Stamp 上。

## Three Layers within a Storage Stamp

Storage Stamp 内部又可以分为3个层次：

- Stream Layer - 该层将位数据存储在磁盘上，并负责将数据分布和复制到许多服务器上，以保持存储集群内的数据持久性。Stream Layer 可以被视为存储集群内的分布式文件系统层。它理解文件，称为“流”（每个流由一系列有序的“extent”组成），以及如何存储它们、复制它们等，但它不理解更高级别的对象构造或其语义。数据存储在Stream Layer 中，但可以从Partition Layer 访问。实际上，partition server（Partition Layer 的守护进程）和 Stream Server 位于存储集群中的每个存储节点上。
- Partition Layer - 分区层用于:
    - 管理和理解更高级别的数据抽象（Blob、Table、Queue）
    - 提供可扩展的对象命名空间，
    - 为对象提供事务排序和强一致性
    - 在流层之上存储对象数据
    - 缓存对象数据以减少磁盘I/O
    - 该层的另一个责任是通过在存储集群内对所有数据对象进行分区来实现可扩展性。如前所述，所有对象都有一个PartitionName；它们基于PartitionName的值被分解为不相交的范围，并由不同的分区服务器提供服务。该层管理哪个分区服务器为Blobs、Tables和Queues提供哪些PartitionName范围的服务。此外，它还提供PartitionNames在分区服务器之间的自动负载平衡，以满足对象的流量需求。
- Front-End (FE) layer - 由一组无状态服务器组成，接收传入请求。接收请求后，FE会查找AccountName、对请求进行身份验证和授权，然后将请求路由到分区层中的一个分区服务器（基于PartitionName）。系统维护一个Partition Map，跟踪PartitionName范围以及哪个分区服务器为哪些PartitionNames提供服务。FE服务器缓存Partition Map，并使用它来确定将每个请求转发到哪个分区服务器。FE服务器还直接从流层流式传输大型对象，并对频繁访问的数据进行缓存，以提高效率。

Stream Layer，笔者理解就是后来阿里云的盘古 1.0 的设计原型。Steam 的设计在盘古中可以看到几乎是1:1的复刻。盘古发展到2.0模型，做了更多的优化（见笔者的另外一篇分享）。

Stream Layer 本质上就是提供一个个分布式的 append-only 的文件，如何组织好这些“文件”，并向上提供更丰富的语义，就是 Partition Layer 的职责了。

## Two Replication Engines —— 两种备份机制

两种副本机制：

1. Stamp内部备份：发生在一个Stamp内部，在用户请求的关键路径上，同步完成后响应用户。用于避免硬盘、节点、机柜故障下的数据丢失。
2. Stamp间备份：发生在Stamp之间，用于更大范围（比如跨 region）的容灾，异步备份。

# Stream Layer

Stream Layer 本质上就是提供一个个分布式的 append-only 的文件，也是阿里云盘古1.0的原型。

阿里在2023 FAST 上发表了《**More Than Capacity: Performance-oriented Evolution of Pangu in Alibaba**》一文，介绍了盘古2.0的架构，更具有现代的参考价值，建议也可以读一下。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F3e886fc1-32d8-47b2-ab42-3f286e7e9c3d%2FUntitled.png?table=block&id=b2ecef95-f0e0-48fa-9549-72e23ef82e3f&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F9f77530f-8f0f-43e0-9f2a-8a15ad82bb6a%2FUntitled.png?table=block&id=36fdfbd0-9580-4e28-8a38-3bdb47210e5c&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1250&userId=&cache=v2)

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F8d1b1276-9dab-4673-be65-74ffad0b09cb%2FUntitled.png?table=block&id=6a5b797b-dbb2-4b1c-9a34-e5bd793f4b0c&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

由于 Stream 是以 block 为粒度，append-only 的，因此只有最后一个 Extent 可以被写入，所有被 sealed 的 extent，长度都不再改变。

创建一个 extent 时，client 向Stream Master 发送消息，Stream Master 分配好一个 replica set，并返回给 client，于是 client 就知道接下来如何读写这个 extent 了（通过 Primary )：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fbeb640bd-6356-4734-9cb6-4312781734c4%2FUntitled.png?table=block&id=c211d848-dc50-4ea8-a70a-4dfcff06e252&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

client 只负责将数据写入 Primary ，由 Primary 将数据同步复制到2个 Secondary 节点，然后再响应 client 写入成功。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fa176e147-ba5b-47cd-8bdb-349516281b42%2FUntitled.png?table=block&id=5edbf99d-5620-44d6-9ba7-e504884dea63&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

（注：写入是3副本的，在后台，会再通过 EC，把原始数据按 EC 重新写入，以减少存储成本。但这样带来的写放大比较大，因而在盘古2.0里，已经不再采用这种方式，而是 client 侧直接以 EC 方式写入。）

只要 ack 成功（数据被写入所有副本），client 一定可以在接下来的读请求里读到对应的数据，除非所有的 extent node 都挂掉。在盘古2.0的设计里，数据并写入超过半数的副本后，即可能返回成功，后台会进行重试。

在故障场景下，通过 seal 来对extent的数据进行冻结，冰结后，这个 extent 的所有副本，最终都将对齐到一样的数据。冻结完成后， client 就可以重新 open 一个新的 extent 进行持续写入，确保写入不要中断。在盘古2.0里称这种设计为 non-stop write。

# Partition Layer

Stream Layer 本质上就是提供一个个分布式的 append-only 的文件，如何组织好这些“文件”，并向上提供更丰富的语义（blob、queue、table），就是 Partition Layer 的职责了。具体地，Partition Layer 负责：

(a) data model for the different types of objects stored, 

(b) logic and semantics to process the different types of objects, 

(c) massively scalable namespace for the objects, 

(d) load balancing to access objects across the available partition servers, and 

(e) transaction ordering and strong consistency for access to objects.

总结来说， Partition Layer 向上提供 Blob 、queue、table 的语义，并管理 object 和 index。

Partition Layer 本质上可以认为提供了以下的 Object Table（基于这个 table 做各种增删改查）：

1. The Account Table stores metadata and configuration for each storage account assigned to the stamp. 
2. The Blob Table stores all blob objects for all accounts in the stamp. 
3. The Entity Table stores all entity rows for all accounts in the stamp; it is used for the
public Windows Azure Table data abstraction. 
4. The Message Table stores all messages for all accounts’ queues in the stamp.
5. The Schema Table keeps track of the schema for all OTs. 
6. The Partition Map Table keeps track of the current RangePartitions for all Object Tables and what partition server is serving each RangePartition. This table is used by the Front-End servers to route requests to the corresponding partition servers.
7. Each of the above OTs has a fixed schema stored in the Schema Table. 

The primary key for the Blob Table, Entity Table, and Message Table consists of three properties: AccountName,
PartitionName, and ObjectName. These properties provide the indexing and sort order for those Object Tables.

由于每个 table 可能会非常巨大，因此，Partition Layer 把每个 table，按 index 分拆成一个个的 RangePartition，并把RangePartition分配给指定的 PS。 如果RangePartition 过大或过小，过冷或过热，PM 还会负责整合（merge）或分拆（split）RangePartition。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fd44d5c69-c46b-4c3a-9434-30426ee0f820%2FUntitled.png?table=block&id=88781af1-5e9d-47b1-a320-dd18e88241fc&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

在数据组织上，每个 RangePartition 都可以被当成一个 LSM tree（比例适配底层的 append-only 语义）：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fa7242abe-3731-4300-8647-d6c1b2eb2299%2FUntitled.png?table=block&id=c3fef447-f374-4426-90ae-326970717a6a&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

# 思考&启发

1.关于分布式锁的多主问题：

Partition Server 通过Lock Service 获取锁，可能会有“多主”问题，即同一时间有多个 Partition Server 处理同一个 RangePartition，论文中说用 Lock Service 可以保证“no two partition servers
can serve the same RangePartition at the same ” ，个人认为是不严谨的，分布式锁都是有问题的，具体可以参考：[https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)。

但实际上，这个问题可以在 Stream Layer 解决，即使两个 PartitionServer 打开同一个commit log Stream 用于写，新 PS 实际在上写入 Stream 之前，可以先通过 seal，将之前的 Extent 冻结，从而旧的 PS 就无法再写入了，因此实际上即使 PS 同时操作同一个 commit log，也是没有问题的。

论文在4.3.3部分提到了类似的做法，但是文中提到 PS 是检查不同的副本是否有同一个length，如果 length 不同，就发起 seal。而笔者认为，新的 PS 开始 load commit log 前都应该确保之前的 log 全 seal。

[2.Stream](http://2.Stream) layer 的设计影响很大，阿里云盘古，字节跳动 bytestore，全部都是按这个模式来实现：最底层实现一个**分布式**的 **append-only** **blob** 语义的底座。

3.Partition Layer 本质是实现一个分布式的 LSM tree，本质上是一个 key-value 的语义（key = account + partition + object，value 是 blob、msg、record），但这样的设计目前看来并没有在其它厂商推广开。

参考资料：

paper：[https://www.cs.purdue.edu/homes/csjgwang/CloudNativeDB/AzureStorageSOSP11.pdf](https://www.cs.purdue.edu/homes/csjgwang/CloudNativeDB/AzureStorageSOSP11.pdf)
PPT：[https://sigops.org/s/conferences/sosp/2011/current/2011-Cascais/10-adya.pptx](https://sigops.org/s/conferences/sosp/2011/current/2011-Cascais/10-adya.pptx)

Youtube：[https://www.youtube.com/watch?v=QnYdbQO0yj4&t=109s&ab_channel=sosp2011](https://www.youtube.com/watch?v=QnYdbQO0yj4&t=109s&ab_channel=sosp2011)
