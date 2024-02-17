---
layout: post
title: "2023【FAST】PERSEUS: A Fail-Slow Detection Framework for Cloud Storage Systems"
author: "Ahan"
date: 2024-02-17 21:28:25
header-img: "img/post-bg-2015.jpg"
header-style: text
catalog:      true
tags:
    - storage
    - AI
---
# 摘要

**Fast'23 Best Paper**：https://www.usenix.org/conference/fast23/presentation/lu

# 背景

What is Fail-Slow？——Still functioning bug with **lower-than-expected** performance **设备可用但是远低于预期的性能**

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fbee18a97-053f-410a-9391-179a6af3241a%2FUntitled.png?table=block&id=6e8df1d1-dd8b-4616-9662-6cce6ead5e05&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

以SSD为例，SSD有读写寿命，但当一块SSD盘完全不能用之前，往往会有一个中间状态（Fail-Slow），处于Fail-Slow状态的盘，会发现读写都能正常进行，但其latency p99或p999会比其他新盘慢很多倍。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F614033c8-5e6e-4d3f-a8b8-e2766ac6e760%2FUntitled.png?table=block&id=9b8b537e-99a4-482f-924e-fc0c70fea6e4&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

Fail-slow 会对系统造成比较大的负面影响：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F7e752eb2-480f-445c-830f-0468705fd1e8%2FUntitled.png?table=block&id=e15d8335-cc36-4cb2-9b60-9f01250adfa1&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1250&userId=&cache=v2)

当我们把 fail-slow 设备移除后，可以看到写入长尾有明显的改善：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fbb898eec-eb7e-4d78-875a-714a650d2e1d%2FUntitled.png?table=block&id=3c7d26a5-1c35-4357-af38-93e6e7bd40cf&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

## 本文的贡献

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F8b6c6566-b5ee-482e-8e18-6a78ca37e030%2FUntitled.png?table=block&id=8251f925-8686-4610-8622-a6f794623c12&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

- 我们分享了在大规模数据中心中检测故障缓慢失败的三次不成功尝试的经验教训。
- 我们提出了PERSEUS的设计，这是一个**非侵入式**、**细粒度**且**通用**的 fail-slow 检测框架。
- 我们收集了一个大规模的fail-slow[数据集](https://tianchi.aliyun.com/dataset/144479)，并建立了一个故障缓慢测试基准。
- 我们从各种因素的角度提供了故障缓慢失败的深入根本原因分析。

# Unsuccessful Attempts & Lessons

## Design Goals

1. Non-intrusive. 作为云供应商，我们既不能更改用户的软件，也不能要求他们运行特定修改版本的软件堆栈。因此，我们只能依赖外部性能统计数据（例如磁盘延迟）进行检测。
2. Fine-grained. 故障缓慢根本原因的诊断往往是耗时的（例如，可能需要数天甚至数周）。我们期望该框架能够准确定位问题的罪魁祸首。
3. Accurate. 该框架应当有较高的精准性
4. General. 该架构可以部署到SSD/HDD集群，并快速应用到不同的服务（块/对象存储和数据库）

## Attempt 1：Threshold Filtering

- 方法：可以通过SLOs设置设备时延阈值来识别fail-slow设备。为避免SSD内部GC引起误判，同样设置了最小slowdown范围。
- 限制：这种方法易受到workloads影响，精确度比较低。以块存储服务中NVME的吞吐为例，写时延会因为workload burst超过阈值导致误判。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F9db9ad33-2023-4f01-97e5-247e8ea41c73%2FUntitled.png?table=block&id=deb43064-ec33-4bd5-8209-b565a56cb48d&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=990&userId=&cache=v2)

## Attempt 2：Peer Evaluation

- 方法：前面的问题在于没有自适应的阈值，为了解决该问题，采用peer evaluation方法，即随着分布式系统的负载均衡，相同节点的设备应当有相似的负载压力。可以通过比较相同节点设备的性能来识别fail-slow设备。
    - 每隔15s计算节点内各设备的中间值时延
    - 查看是否有设备在一个时间窗内(5min)连续出现异常性能——超过50%的时间其时延超过中间值的2倍。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F0bec7839-79ce-4c73-8518-9609b6bca381%2FUntitled.png?table=block&id=29144fb5-3e8e-4172-af31-0677583081e1&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=960&userId=&cache=v2)

- 限制：对于不同类型的设备需要评估不同的参数，可拓展性差。

## Guidelines for PERSEUS

1.What metrics should we use？

选择 Write performance（latency/throughput of write）作为评估 fail-slow 的指标，原因如下：

- 在已知的fail-slow cases中，超过一半的都只对write有显著影响
- fail-slow失败对于写的影响更大。例如：大部分集群要求强一致性，写请求三副本都成功才返回，而读只需一个副本返回即可，fail-slow failures对于写请求的影响更频繁。

2.How to model workload pressure？

通过 throughput 或IOPS。通过[SRCC](https://en.wikipedia.org/wiki/Spearman%27s_rank_correlation_coefficient)的方法，将每个设备的latency与throughput/IOPS相关联。SRCC越高，则关联性越强。从下图可以看出latency与throughput的关联更高。因此我们决定使用throughput来对workload压力建模。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F1ef64028-73d7-49d5-8a18-2e18f805728f%2FUntitled.png?table=block&id=6775d7dc-0065-4cc9-8f3a-f66ec1b53571&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=940&userId=&cache=v2)

3.How to automatically derive adaptive thresholds？

通过多项式回归模型构建latency-vs-throughput分布，下图展示了latency-vs-throughput(LvT)在不同情况的分布

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fc0e4ce9b-dbf3-4750-a513-3ba2bcc470b8%2FUntitled.png?table=block&id=8945c1e9-67a1-4562-8cf7-b4ade4118b64&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

- Service-wise（三个集群，数据库服务）

相同service在不同cluster的LvT分布鲜有重叠

- Cluster-wise（相同集群、相同服务，不同节点）

相同cluster在不同node的LvT相差较大

- Node-wise（相同节点，不同设备）

相同node的不同drives有相似的LvT分布

因此，**采用node-wise的样本来构建LvT分布**

4.How to identify fail-slow without a criterion？

fail-slow不像fail-stop，没有明确的标准，因此检测工具并不是直接确认设备fail-slow或者normal，而是描述其fail-slow的可能性。

# 解决方案

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F30f241c5-f78d-4f79-b329-b701c92ef0b4%2FUntitled.png?table=block&id=9930d2ce-a3f3-45dc-8954-65784b14cf1b&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1960&userId=&cache=v2)

1. 异常值检测。对于每个节点，PERSEUS首先收集所有条目。然后，我们使用主成分分析（PCA ）和基于密度的带噪声空间聚类（DBSCAN）的组合来识别并丢弃异常条目。
2. 构建回归模型。基于清理后的数据集（即不包括异常值），PERSEUS执行多项式回归以获得模型，并使用预测上限作为故障缓慢检测阈值。然后，PERSEUS将该模型应用于原始数据集（即包括异常值），以识别超出界限的条目，并标记它们为缓慢条目。
3. 识别故障缓慢事件。PERSEUS使用滑动窗口和减速比率来识别连续的缓慢条目，并制定相应的故障缓慢事件。
4. 评估风险。基于风险评分机制，PERSEUS估计故障缓慢事件的持续时间和程度，并根据每日累积的故障缓慢事件为每个驱动器分配风险评分。然后，现场工程师可以根据严重程度进行调查。

## 异常点检测（Outlier Detection）

在应用回归模型之前，一个必要的预处理工作是排除噪声样本（即异常值）。尽管LvT样本（即<延迟，吞吐量>对）通常在节点内聚集在一起（参见第3.5节的RQ3），但来自故障缓慢驱动器或正常性能变化（例如内部GC）的条目仍可能出现偏差。因此，在构建多项式回归模型之前，我们首先筛选出异常值。采用[DBSCAN](https://zh.wikipedia.org/wiki/DBSCAN)和[PCA](https://en.wikipedia.org/wiki/Principal_component_analysis)的方法可以有效检测92.55%的slow entries。

## 建立回归模型（Regression Model）

由于节点内的正常驱动器可能具有类似的延迟-吞吐量映射（聚集在一起），我们可以使用回归模型描述“正常”驱动器的行为，并勾勒出故障缓慢检测的变异范围。经典的回归模型包括线性、多项式和高级模型，如核回归。我们不使用线性回归，因为延迟对吞吐量的依赖显然是非线性的（例如，参见图8）。此外，高级模型（例如核回归）是不必要的，因为延迟与吞吐量的映射主要是单调的（即，延迟随着吞吐量增加而增加）。多项式回归是首选的，因为它处理非线性同时保持模型的简约性（即，用足够少的参数实现所需的拟合效果）。

## 识别 fail-slow 事件（Identifying Fail-Slow Event）

在得到回归模型后，可以通过计算预测上限(upper bound)来识别slow entries并检测fail-slow事件

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F4cc02a65-ed07-431f-a739-4347c6cd7f93%2FUntitled.png?table=block&id=eac7ae3b-3c48-493e-9801-0252ff9dea79&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

以下图为例：

- 灰线：drive latency
- 蓝线：fitted values
- 绿线：99.9% upper bound
- 识别 slow entry：每15s作为1个entry，假设一个设备的latency entries为[15, 20, 25, 10, 5]，相应的upper bound为[5, 5, 5, 5, 5]，则对应Slowdown Ratio(SR)为[3, 4, 5, 2, 1]。Slowdown Ratio (SR) = latency / upper bound.
- 识别 slow 事件：设定一个滑动窗口，若该范围内一定比例的SR中间值大于阈值，则认定为fail-slow事件。例如滑动窗口大小为1min，比例设置为50%，阈值设置为1。则[3, 4, 5, 2]内超过50%的SR（i.e. 3，4，5，2）中位数为3.5 > 1，认定窗口[3,4,5,2]为fail-slow事件。根据类似的方式，可以判断下一个窗口，是否有发生 fail-slow 事件。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fc1165411-3cf1-41e4-9438-0d724295af3d%2FUntitled.png?table=block&id=1f422ac3-9491-4a50-a444-c75b626a57a7&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=980&userId=&cache=v2)

## 记分板

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fdde0f839-730e-4fc2-8c38-8e6a868335c0%2FUntitled.png?table=block&id=65744abb-fa2d-47f1-909e-b80ab8cc4ab2&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=940&userId=&cache=v2)

每个设备的risk score是通过不同risk level的权重计算得到的：

Risk Score = N(extreme) * 100 + N(high) * 25 + N(moderate) * 10 + N(low) * 5 + N(minor) * 1

N(extreme) refers to #days at extreme risk level.

如果一个设备其risk score在最近N天内超过了**min_score，**则该设备将被推荐立即隔离。

# 效果

## Fail-slow Benchmark

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fb538d84d-2f01-4a54-8c9b-8e6075f89df0%2FUntitled.png?table=block&id=4292bc43-39cc-414f-8fec-cfb28cf6af96&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1000&userId=&cache=v2)

PERSEUS在以上fail-slow case中检测出了304个，所有fail-slow设备的根因包括软件bug、硬件影响、环境因素等。

## 与其它算法对比

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fea53fb5e-ece8-4954-81be-a78ecd482059%2FUntitled.png?table=block&id=3a6f56e7-9ecd-4aa0-9d8d-7e2e6db4132a&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F0d70303e-b84a-4b79-9519-b800ed00184b%2FUntitled.png?table=block&id=8409ff4d-323c-4504-b463-7e40062e7275&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

表5显示了PERSEUS优于以往的所有尝试。高精度和召回率表明，PERSEUS能够成功检测所有的fail-slow驱动器，同时很少将正常驱动错误地标记为fail-slow。因此，我们得出结论，PERSEUS作为一种精细化（每个驱动器）、非侵入性（无代码更改）、通用（相同的参数设置适用于不同的环境）和准确的（高精度和召回率）fail-slow检测框架实现了我们的设计目标。

## 性能收益

最终效果来看，部署PERSEUS的最直接好处是减少尾延迟。通过隔离故障缓慢，节点级别的第95、99和99.99百分位写入延迟分别减少了30.67%（±10.96%）、46.39%（±14.84%）和48.05%（±15.53%）。

## Root Cause Analysis

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F4c0ac849-4191-488a-a5da-de5bd49614b9%2FUntitled.png?table=block&id=73919eb6-4102-42cb-9eb2-98264493e574&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

分析其中315个已确认的 fail-slow 设备，其中252个都是由于受到不合理的调度的影响。

# 限制

- 多次 fail-slow 发生。PERSEUS 利用一个重要的先决条件，即在现场 fail-slow 失败应该是罕见的。然而，如果关键组件（例如 HBA 卡）在关键数据路径上发生故障，所有驱动器都会受到影响并导致严重延迟。在这种情况下，PERSEUS 可能无法检测性能异常，因为 LvT 分布可能对所有驱动器产生偏斜。目前，我们正在调查进行节点间 LvT 分布以增强 PERSEUS 在同一节点内发现多个 fail-slow 发生的可能性。
- 泛化性。利用 LvT 分布来识别 fail-slow 驱动器还取决于节点内所有驱动器具有相同的驱动器型号和类似的工作负载。在我们的存储系统中，驱动器具有相同的配置，并且多级负载平衡确保了同一节点内每个驱动器的工作负载相似。尽管这是大规模存储系统的常见做法，但对于小规模服务器（例如私有云），情况可能并非如此，同一节点中的驱动器可能具有截然不同的工作负载和配置。在这种情况下，PERSEUS 的准确性可能会受到影响。
- 全面性。PERSEUS 目前每天使用从晚上9点到12点的跟踪数据来减少干扰。一些 fail-slow 失败可能仅在特定时间窗口或在较重工作负载下触发。我们正致力于设计一个更有效的守护程序，在忙时收集 PERSEUS 的跟踪数据。此外，我们正在探索其他设备级指标，以丰富 PERSEUS 可以作为关键输入的内容。

# 给我们的启发

这篇论文是FAST 2023 年的 best paper，本质上是一种工程上的创新，并且在实践上也有比较好的效果。

论文中涉及到的算法主要有：

- SRCC
- DBSCAN
- PCA
- 多项式回归

核心是利用 DBSCAN和PCA，先尽可能过滤出异常的数据点，然后利用多项式回归，对正常的数据点建模，得到模型后，就可以根据模型来找出异常的数据点。并且在统计出一段时间内异常的数据点后，对设备做出打分判断。

这是创新法则中的“组合法”，通过组合不同的已有知识解决一个复杂的工程问题。
