---
layout: post
title: "2023【FAST】More Than Capacity: Performance-oriented Evolution of Pangu in Alibaba"
author:       "Ahan"
date: 2024-02-12 00:00:00
header-img: "img/post-bg-2015.jpg"
header-style: text
catalog:      true
tags:
    - Storage
    - Distributed
---
paper 总结了**阿里云盘古2.0**的性能优化的演进和方案，对我们设计一个存储基座有非常好的参考价值。

# 背景

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fbcd2547a-4f47-42b3-a25a-bcdb54466b4c%2FUntitled.png?table=block&id=f5385e26-3a9d-4c38-9cec-c709ba79f028&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

盘古1.0：主要面向容量，以 HDD 为主，基于 ext4文件系统、kernel TCP；

面对新硬件的高性能，例如 nvme SSD、RDMA 网卡等新硬件，传统的软件无法充分发挥出新硬件的性能优势，因此有了盘古2.0.

盘古的架构：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fcaf404c9-3aa7-49c2-a0c9-9cb604153a7f%2FUntitled.png?table=block&id=e40ad130-171d-4e5f-b3b5-b5c471c62d7a&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

盘古2.0的核心优化：**Low latency** → **100us**。

# 解决方案

## 阶段一：拥抱 SSD 和 RDMA

### Bypass 内核

通过自研 user-space storage operating System，做了各项优化，核心是 **bypass 内核**。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F34e19f40-3020-4b43-91e5-1a6ea98d4f0b%2FUntitled.png?table=block&id=5c628f0f-c56a-4767-ae57-98dfd6df298b&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

降低延迟，4个手段，包括：

- Run-to-Complete Thread Model：同一个请求会在同一个线程里完成，避免切线程后的上下文切换的开销，同步的开销、通信的开销。
- User-Level Memory Management：线程申请 huge page 供存储和网络共同使用，数据从 RDMA 接收到数据后存储到 huge page 里，然后通过 SPDK 直接写入存储，做到 ZeroCopy。
- User-Level Task Scheduling：不同请求区别优先级，区别对待。比较常规，不展开讨论。
- User-space Storage File System

### 如何在故障场景下尽可能减少长尾延迟

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fd146ed96-5495-4bf3-833f-76bdc81f6ada%2FUntitled.png?table=block&id=743ef927-c3fc-4b72-85b0-5ad7f472f88a&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

故障场景下，盘古仍然保证了P999的延迟可以控制在 ms 级别，因为客户端对于故障场景做了很多特殊处理。总结下来是4个手段：

1. Chasing：客户端在向 ChunkServer 写入多副本数据时，**超过半数副本成功**，即被认为写入成功。具体地，客户端会设置 MaxCopy 和 MinCopy 数（2 × MinCopy > MaxCopy，本质就是超过半数写成功），一旦副本写入达到 MinCopy，客户端即可向上层返回写入成功，同时客户端会在后台保持重试，并在重试失败后进行处理，确保数据最终能补齐到 MaxCopy 的副本数。
2. Non-stop write：当发生写入失败时，客户端会封存（seal）该块并向主节点报告成功写入的数据长度。然后，它会使用一个新的块来继续写入未完成的数据。如果写入到封存块的数据损坏了，会利用其他副本在后台流量中将该数据复制到新的块中。如果没有可用的副本，客户端会再次将这些数据写入新的块中。
3. Backup Read：笔者没有特别看懂这个机制。似乎是针对同一个请求，发出多个读请求，看哪个 ChunkServer 先返回结果。但是这样一来，读的开销也会变大。
4. Blacklist：为了避免向服务质量不佳的块服务器发送I/O请求，Pangu引入了两个黑名单，确定性黑名单和非确定性黑名单。当Pangu确定一个块服务器无法提供服务（例如，块服务器的固态硬盘（SSD）受损）时，该服务器将被添加到确定性黑名单中。如果一个块服务器可以提供服务，但其延迟超过了一定阈值，它将以一定的概率被添加到非确定性黑名单中，该概率随着其服务延迟的增加而增加。如果服务器的延迟超过所有服务器的中位数延迟的几倍，它将直接以概率为1被添加到非确定性黑名单中。为了从这些黑名单中释放服务器，客户端定期向这些服务器发送I/O探测（例如，每秒一次）。如果确定性黑名单中的服务器成功返回此请求的响应，它将从该黑名单中删除。对于非确定性黑名单中的服务器，Pangu根据接收到此请求的响应所需要的时间来决定是否将服务器从黑名单中移除。

阿里采用了 non-stop write 的设计，尽最大可能，确保写入不要停。例如：

1. 3份数据成功2份后，对上响应成功，client 侧后台保持重试；
2. 写入失败，倒换 chunk server 继续写。

### 阶段一效果

通过对 OTS（表格存储）的性能测试，升级到Pangu2.0后，延迟上有数量级的减少。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F4aba4e56-e1ff-4e01-8df1-ece1745fdfc8%2FUntitled.png?table=block&id=63ba8346-8b27-45bc-91e7-3c67f4e6d805&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1800&userId=&cache=v2)

并且在实际的 EBS 和搜索业务上，P999的控制和平均时延也都表现出色：

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F86292328-0606-41a7-ab76-ddd07b511ea5%2FUntitled.png?table=block&id=ac8e7024-2007-4c02-b4eb-29f6c79e83a4&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=1520&userId=&cache=v2)

对EBS 来说，平均时延可以控制在**100us** 以下。

## 阶段二：适应以性能为导向的商业模式

从2018年开始，盘古逐渐从容量型存储转向性能型存储。盘古做了一系列性能上的优化，包括网络、内存、CPU，以充分压榨物理机的性能。

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2Fe97f4516-d48b-4a15-8ee8-381bba80c44b%2FUntitled.png?table=block&id=3e0111d5-0fd5-4109-a7a7-4dcc7352a46f&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

### 网络优化

![Untitled](https://ahan-ai.notion.site/image/https%3A%2F%2Fprod-files-secure.s3.us-west-2.amazonaws.com%2F3841c813-6aff-406c-8c94-6fa3c0018b15%2F23e47774-edca-48fb-a777-082d0aedc0ce%2FUntitled.png?table=block&id=d7490e94-eec8-4815-95c2-52666709c912&spaceId=3841c813-6aff-406c-8c94-6fa3c0018b15&width=2000&userId=&cache=v2)

网络部分主要有3项优化：

1. 升级硬件：25Gbs → 100Gbps。这部分的优化，阿里云有另外一篇[paper](https://www.usenix.org/conference/nsdi21/presentation/gao)来说明；
2. （核心）在 EC 和压缩的加持下，把网络的放大比**从6.3减少到2.9；**
3. 动态调整前后台流量阈值。例如，如果整个存储集群中有足够的空闲空间，会临时降低阈值来限制后台流量（例如垃圾回收流量）的带宽，并让前端流量使用更多的带宽。对于淘宝来说，Pangu在白天到午夜期间设置较低的阈值，以应对大量的前端访问请求。午夜后，Pangu会增加阈值，因为前端流量减少了。

### 内存优化

1. 提升内存带宽：使用16GB 的小容量内存条，提升内存 Channel。这部分笔者没有特别看懂，听起来是在控制内存总量的情况下，每条内存的容量减少，增加内存的条数；
2. 后台流量从 TCP 切换到 RDMA，减少75%的后台流量对内存带宽占用；
3. 利用 Intel 的 **DDIO** 技术，直接将数据发送到对端处理器的最后一级缓存（LLC），绕过主内存的访问（bypass DDR memory）。这样可以降低网络数据包的延迟，并减少了从主内存到处理器缓存的数据传输。

### CPU 优化

1. Hybrid RPCs：部分请求的 Protobuf 的序列化和反序列太耗 CPU，因此盘古将数据通路上的通信协议采用类似 FlatBuffer 的格式来替代（Raw-structure，不需要序列化/反序列化），单个 CPU 产生的网络吞吐提升了59%，有非常好的效果。管控通路仍然保留 Protobuffer 协议。
2. CRC offload 到硬件上（不过这个优化据说没有实际落地）。

# 启发

- Bypass Kernel。相信后续的新的存储系统，利用 SPDK、RDMA等技术 bypass kernel 几乎会成为一个必选项。
- 硬件 offload 会成为高性能存储的标配，专业的硬件做专业的事。
