块存储系统支持现代云服务中各种类型的应用程序。对其I/O活动进行表征对指导更好的系统设计和优化至关重要。论文通过来自阿里巴巴云的数十亿I/O请求的**块级I/O**跟踪，对生产云块存储工作负载进行了深入分析。

论文研究了负载强度、空间模式和时间模式的特征，提供了15个发现，并讨论它们对云块存储系统中的负载平衡、缓存效率和存储集群管理的影响。

相关的 trace 数据集已经公开：https://github.com/alibaba/block-traces。

块存储上的业务架构：

![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/3841c813-6aff-406c-8c94-6fa3c0018b15/09afdb01-0ed0-4691-96ab-03f2af8b92ed/Untitled.png)

图1 描述了云上块存储系统的架构。块存储系统充当中间件层，连接上层应用程序感知的虚拟磁盘（称为卷，Volume）和提供物理存储空间的存储集群，这些存储集群由云服务提供商拥有。每个应用程序被分配一个专用卷。它通过专用卷向存储集群发出读取或写入请求。每个卷通常在多个存储集群中进行了复制，以实现容错性。为了性能和可靠性考虑，如今的存储集群通常由基于闪存的固态硬盘（SSD）而不是硬盘驱动器支持。在实际生产中，云块存储系统可能管理各种类型的上层云应用（图1）。这些应用的I/O特征通常存在较大差异。

# 关键发现

列举一些笔者觉得比较有价值的发现点。论文跟10年前的微软的测试集做了很多比较，但鉴于微软的数据集已经比较早了，笔者觉得比较的意义没那么大了，我更多以阿里巴巴的数据集为例进行说明。

## 负载强度（Load Intensity）

### Finding 1. Both AliCloud and MSRC have similar load intensities of volumes.

![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/3841c813-6aff-406c-8c94-6fa3c0018b15/5fde442e-e018-40a8-8ca9-649f966d35d9/Untitled.png)

In AliCloud and MSRC, only 1.90% and 2.78% of volumes have average intensities above 100 req/s, while 81.6% and 72.2% of volumes have average intensities lower than 10 req/s, respectively.

阿里云上大量的 Volume 从平均请求上看处于闲置状态。

### Finding 2. Both AliCloud and MSRC have high burstiness in a non-negligible fraction of volumes, but have overall low burstiness.

上面我们提到大量的 Volume 实际上平均请求极低，但是突发的流量（burstiness）却不容忽视。

![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/3841c813-6aff-406c-8c94-6fa3c0018b15/ced22c82-73fb-4f24-abf3-4a587095a52d/Untitled.png)

论文作者定义了 Burstiness ratio = 最高请求率 / 平均请求率。从上图可以看出，阿里云上，Burstiness ratio 超过100的Volume大概有20%左右，是一个不小的值。意味着这20%的云盘可能正在经历负载不均。

### Finding 3. AliCloud has more diverse burstiness across volumes than MSRC

关于突发流量的样例，阿里云比微软的数据集具备更多的多样性。

### Finding 4. Both AliCloud and MSRC have high short-term burstiness from the perspective of inter-arrival times of requests.

### Finding 5. Most of the volumes in both AliCloud and MSRC are active throughout the trace periods, while AliCloud has higher activeness than MSRC.

对于 active 的衡量标准，作者提出每个云盘只要在10分钟内被访问过至少1次，那么这10分钟就算 active。

### Finding 6. Writes are the dominant factor in determining activeness in both AliCloud and MSRC.

卷的写操作占有绝对的主导地位。

### Finding 7. Removing write requests shows drastic decreases in activeness in both AliCloud and MSRC. AliCloud is also less read-active than MSRC.

如果我们移除写请求，仅考虑读活跃卷，特别是在AliCloud 中，活跃卷的数量减少了58.3-73.6%。移除写请求还导致AliCloud和MSRC中的卷具有较低的读活跃时间。在AliCloud中，移除写操作后，一半的卷仅具有不到1.28天的读活跃时间，并且仅有7.9%的卷可以达到30天以上的读活跃时间（图9(a)）。

这表明移除写操作会产生大量的空闲时间，因此我们可以应用写操作卸载来节省云块存储的功率消耗。

## 空间模式（Spatial Patterns）

### Finding 8. Random I/Os are common in both AliCloud and MSRC. The volumes in AliCloud see more random I/Os than those in MSRC.

如何定义 random IO?  We study the randomness of I/O requests by examining the spatial relationships among adjacent requests. To quantify the randomness of a request, we measure the minimum distance between the current offset of the request and the offsets of the previous 32 requests [3], [25]. If the minimum distance exceeds a threshold (e.g., 128 KiB [25]), we regard the request as a random request. We measure the randomness ratio of a volume, defined as the percentage of random requests over all requests.

阿里云 20% 的云盘有超过 50% 的请求是随机 IO。结合前面提到，大部分请求是小 IO 请求，这样小 IO + 随机IO的访问模式，对于 SSD 是十分有害的。

### Finding 9. Reads and writes aggregate in small working sets for a non-negligible fraction of volumes in both AliCloud and MSRC. Writes are more aggregated than reads.

![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/3841c813-6aff-406c-8c94-6fa3c0018b15/6dafb7b0-37f8-4ba1-b1e0-9feb8edd7695/Untitled.png)

图11显示了AliCloud和MSRC所有卷中前1%和前10%块的流量占比的箱线图。我们发现在相当大比例的卷中，读取和写入流量可以在前1%和前10%的块中聚合。

在AliCloud中，至少有75%的卷，被读取次数 TOP 1% 的块，吸引了至少2.5 %的读取流量，被读取次数 TOP 10% 的块中吸引了13.6%的读取流量。

在AliCloud中，箱线图显示有147个卷在前1%读取块中属于异常值（outliers）（图11(a)）。这些异常值卷在其前1%读取块中拥有超过21.3%的读取流量。这意味着一个**小型的读取缓存可以吸收这些卷的大量读取流量**。

与读取相比，写入的聚合性更高，正如图中所示。在AliCloud中，前1%和前10%读取块中的读取流量的25th百分位数分别为2.5%和13.6%，而前1%和前10%写入块中的写入流量25th百分位数分别增加到13.0%和31.2%。

### Finding 10. Reads and writes tend to aggregate in read-mostly and write-mostly blocks in AliCloud, respectively.

### Finding 11. AliCloud generally has higher update coverage than MSRC. The update coverage also varies across volumes.

## 时间模式（Temporal Patterns）

### Finding 12. Both AliCloud and MSRC have large read-afterwrite (RAW) time, but small write-after-write (WAW) time. In AliCloud, the number of WAW requests is larger than that of RAW requests.

AliCloud和MSRC的RAW时间都较长。具体来说，在AliCloud和MSRC中，RAW时间的第50百分位分别为3.0小时和16.2小时。此外，在AliCloud和MSRC中，超过5分钟的RAW请求分别占93.3%和68.8%。

另一方面，AliCloud和MSRC中的WAW请求经过的时间较短。特别是，在AliCloud和MSRC中，WAW时间的第50百分位分别为1.4小时和0.2小时。此外，在AliCloud和MSRC中，分别有22.4%和50.6%的WAW时间少于1分钟。

这表明**写缓存可以有效地吸收对相同数据块的后续写入，从而减少主存储的负载**。

### Finding 13. Most of the read-after-read (RAR) and write-after-read (WAR) requests in AliCloud have large elapsed time, while the RAR and WAR requests in MSRC generally have very small elapsed time. In both traces, the WAR time is much larger than the RAR time, while the numbers of RAR and WAR requests are comparable.

### Finding 14. Written blocks have varying update intervals.

### Finding 15. Some volumes in AliCloud have low miss ratios even under a small cache size. Also, AliCloud shows higher reduction in miss ratios than MSRC when the cache size increases.

# 总结

以上的发现对云块存储设计产生影响，包括负载平衡、缓存效率和存储集群管理。

**负载平衡。** 我们关注卷的平均强度、峰值强度以及活跃性。从发现1中，我们观察到尽管许多应用程序托管在云中，但云块存储中的负载强度与十多年前传统数据中心中的相似。从发现2-4中，我们观察到在相当大比例的卷中存在突发性。虽然总体上突发性仍然较低，但在单个卷中突发性可能严重，因此如果不正确维护负载平衡，就会导致性能下降。工作负载的高度多样性和突发请求的存在使得云块存储的负载平衡比在传统数据中心中更具挑战性。从发现5-7中，我们观察到写入是活跃性的主要因素，而大量卷在读取方面并不活跃。特别是，云块存储中的大部分卷都以写入为主。因此，可以通过卸载写入（例如，将写入重定向到其他存储位置）来为节能创造云块存储工作负载中的空闲时段。在负载平衡的设计中，数据放置策略应该意识到工作负载的多样性和单个卷的突发性。已经证明日志结构设计对于平衡云规模闪存存储中的写入流量非常有用。

**缓存效率。** 我们研究了卷的空间和时间特性，为激发云块存储的新缓存设计提供了指导。从发现9和15中，我们观察到少量数据块的空间和时间流量聚集模式，特别是写入方面。云块存储中的许多卷显示出读取和写入的高聚集，这意味着可以分配有限的缓存资源来吸收大量的读取和写入。从发现10中，我们观察到云块存储中的许多卷在读取大部分和写入大部分的数据块中有读取和写入的聚集。因此，一种可能的缓存准入策略是识别工作负载中的只读块和只写块，因为这些块可以吸收大量的I/O流量。从发现12和13中，已经被写入的数据块倾向于再次被重写，而下一次读取的时间要长于下一次写入。相反，已经被读取的数据块倾向于在很长一段时间后再次被读取或写入。因此，如果我们的目标是通过缓存吸收写入，一种可能的策略是偏好缓存已经被写入的数据块而不是已经被读取的数据块，因为后者可能不太可能生成写入命中。此外，由于从基于磁盘的缓存中有限读取，云块存储可以受益于基于磁盘的写入缓存。

**存储集群管理**。对卷的空间和时间特性进行表征对于存储集群管理也至关重要。在这里，我们专注于基于闪存的存储。

从发现8中，我们观察到云块存储中的上层应用程序会发出大量的小型和随机I/O操作，这些已知会损害基于闪存的存储的性能和耐久性。日志结构化存储设计和I/O聚类可以帮助减轻小型和随机I/O操作的开销。

从发现11和14中，我们发现更新模式在空间和时间上在不同卷之间存在较大变化。这种不同的更新模式可能会损害闪存中垃圾回收和磨损平衡的有效性。因此，云块存储系统在优化基于闪存的存储的更新工作负载时应考虑这种变化的模式。一个可能的方向是在系统级别维护闪存转换层（FTL)，以灵活地协调发往闪存的I/O操作。

# 参考资料

《An In-Depth Analysis of Cloud Block Storage Workloads in Large-Scale Production》

