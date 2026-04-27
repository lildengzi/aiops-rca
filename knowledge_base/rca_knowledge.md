# AIOps 根因分析知识库

## 一、指标关联规则

### CPU 异常排查流程

1. 发现服务 CPU 使用率 > 80%
2. 检查该服务的线程数、GC 频率
3. 检查该服务依赖的下游服务（数据库连接数、慢查询）
4. 检查是否有近期代码变更或配置修改
5. 常见根因：死循环、正则回溯、GC 风暴、连接池耗尽

### 内存异常排查流程

1. 发现服务内存使用率持续上升或突增
2. 检查 JVM 堆内存、非堆内存使用情况
3. 检查是否存在内存泄漏（对象未释放）
4. 检查缓存策略是否合理
5. 常见根因：内存泄漏、缓存未设上限、大对象分配

### 延迟异常排查流程

1. 发现服务 P99 延迟 > 正常基线的 3 倍
2. 检查调用链中的慢 Span
3. 检查数据库慢查询、缓存命中率
4. 检查网络延迟和丢包率
5. 常见根因：慢 SQL、缓存穿透、下游服务降级、GC 暂停

### 错误率异常排查流程

1. 发现服务错误率 > 1%
2. 分析错误类型分布（5xx vs 4xx）
3. 检查日志中的异常堆栈
4. 检查依赖服务的健康状态
5. 常见根因：下游服务不可用、配置错误、代码 Bug

## 二、Online Boutique 架构知识

### 服务依赖关系

- frontend → {adservice, cartservice, checkoutservice, currencyservice, productcatalogservice, recommendationservice, shippingservice}
- cartservice → {redis}
- checkoutservice → {cartservice, currencyservice, emailservice, paymentservice, productcatalogservice, shippingservice}
- recommendationservice → {productcatalogservice}

### 关键业务流程

1. 浏览商品: frontend → productcatalogservice → recommendationservice
2. 加入购物车: frontend → cartservice → redis
3. 结算下单: frontend → checkoutservice → {cartservice, paymentservice, shippingservice, emailservice, currencyservice}

### 常见故障模式

- redis 故障 → cartservice 报错 → checkoutservice 失败 → frontend 5xx
- 数据库慢查询 → productcatalogservice 延迟 → recommendationservice 超时 → frontend 延迟
- 网络分区 → 多个服务间通信中断 → 级联故障



## 自动注入的故障案例 (来自实验数据)

### 案例 adservice_cpu_1
- **故障类型**: cpu
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 35 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_cpu_2
- **故障类型**: cpu
- **注入服务**: adservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 4 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_cpu_3
- **故障类型**: cpu
- **注入服务**: adservice
- **观测错误**:
  - frontend_error: 2 次
  - frontend-external_error: 3 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_cpu_4
- **故障类型**: cpu
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 4 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_cpu_5
- **故障类型**: cpu
- **注入服务**: adservice
- **观测错误**:
  - frontend_error: 39 次
  - frontend-external_error: 66 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_delay_1
- **故障类型**: delay
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_delay_2
- **故障类型**: delay
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 2 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_delay_3
- **故障类型**: delay
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_delay_4
- **故障类型**: delay
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_delay_5
- **故障类型**: delay
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 2 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:44

### 案例 adservice_loss_2
- **故障类型**: loss
- **注入服务**: adservice
- **观测错误**:
  - frontend_error: 2 次
  - frontend-external_error: 2 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 adservice_mem_1
- **故障类型**: mem
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 58 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 adservice_mem_2
- **故障类型**: mem
- **注入服务**: adservice
- **观测错误**:
  - frontend_error: 3 次
  - frontend-external_error: 6 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 adservice_mem_3
- **故障类型**: mem
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 8 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 adservice_mem_4
- **故障类型**: mem
- **注入服务**: adservice
- **观测错误**:
  - frontend-external_error: 6 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 adservice_mem_5
- **故障类型**: mem
- **注入服务**: adservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 6 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_cpu_1
- **故障类型**: cpu
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 8 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_cpu_2
- **故障类型**: cpu
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 10 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_cpu_3
- **故障类型**: cpu
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 5 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_cpu_4
- **故障类型**: cpu
- **注入服务**: cartservice
- **观测错误**:
  - frontend_error: 4 次
  - frontend-external_error: 8 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_cpu_5
- **故障类型**: cpu
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 4 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_delay_1
- **故障类型**: delay
- **注入服务**: cartservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_delay_3
- **故障类型**: delay
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 37 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_delay_4
- **故障类型**: delay
- **注入服务**: cartservice
- **观测错误**:
  - frontend_error: 3 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_delay_5
- **故障类型**: delay
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_loss_2
- **故障类型**: loss
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 5 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_loss_5
- **故障类型**: loss
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_mem_1
- **故障类型**: mem
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 2 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_mem_2
- **故障类型**: mem
- **注入服务**: cartservice
- **观测错误**:
  - frontend-external_error: 6 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_mem_3
- **故障类型**: mem
- **注入服务**: cartservice
- **观测错误**:
  - frontend_error: 4 次
  - frontend-external_error: 7 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_mem_4
- **故障类型**: mem
- **注入服务**: cartservice
- **观测错误**:
  - frontend_error: 2 次
  - frontend-external_error: 6 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 cartservice_mem_5
- **故障类型**: mem
- **注入服务**: cartservice
- **观测错误**:
  - frontend_error: 3 次
  - frontend-external_error: 2 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_cpu_2
- **故障类型**: cpu
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend_error: 2 次
  - frontend-external_error: 2 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_cpu_3
- **故障类型**: cpu
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 4 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_cpu_4
- **故障类型**: cpu
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 2827 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_cpu_5
- **故障类型**: cpu
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 8 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_delay_2
- **故障类型**: delay
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_delay_3
- **故障类型**: delay
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_delay_4
- **故障类型**: delay
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 3 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_delay_5
- **故障类型**: delay
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_disk_2
- **故障类型**: disk
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_loss_1
- **故障类型**: loss
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 2 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_loss_2
- **故障类型**: loss
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 7 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_loss_3
- **故障类型**: loss
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 2 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:45

### 案例 checkoutservice_loss_5
- **故障类型**: loss
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 checkoutservice_mem_1
- **故障类型**: mem
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend-external_error: 5 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 checkoutservice_mem_2
- **故障类型**: mem
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 4 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 checkoutservice_mem_3
- **故障类型**: mem
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 4 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 checkoutservice_mem_4
- **故障类型**: mem
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 6 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 checkoutservice_mem_5
- **故障类型**: mem
- **注入服务**: checkoutservice
- **观测错误**:
  - frontend_error: 2 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_cpu_1
- **故障类型**: cpu
- **注入服务**: currencyservice
- **观测错误**:
  - frontend_error: 2 次
  - frontend-external_error: 6 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_cpu_2
- **故障类型**: cpu
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 5 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_cpu_3
- **故障类型**: cpu
- **注入服务**: currencyservice
- **观测错误**:
  - frontend_error: 2 次
  - frontend-external_error: 2 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_cpu_4
- **故障类型**: cpu
- **注入服务**: currencyservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 3 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_cpu_5
- **故障类型**: cpu
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 2 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_delay_2
- **故障类型**: delay
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_delay_4
- **故障类型**: delay
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_delay_5
- **故障类型**: delay
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 2 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_disk_1
- **故障类型**: disk
- **注入服务**: currencyservice
- **观测错误**:
  - adservice_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_loss_1
- **故障类型**: loss
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_loss_2
- **故障类型**: loss
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 2 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_loss_3
- **故障类型**: loss
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 2 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_loss_5
- **故障类型**: loss
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_mem_1
- **故障类型**: mem
- **注入服务**: currencyservice
- **观测错误**:
  - frontend-external_error: 3 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_mem_2
- **故障类型**: mem
- **注入服务**: currencyservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 2 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_mem_3
- **故障类型**: mem
- **注入服务**: currencyservice
- **观测错误**:
  - frontend_error: 2 次
  - frontend-external_error: 3 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 currencyservice_mem_5
- **故障类型**: mem
- **注入服务**: currencyservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 3 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_cpu_1
- **故障类型**: cpu
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 6 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_cpu_2
- **故障类型**: cpu
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 4 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_cpu_3
- **故障类型**: cpu
- **注入服务**: productcatalogservice
- **观测错误**:
  - carts_error: 25 次
  - orders_error: 28 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_cpu_4
- **故障类型**: cpu
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend_error: 38 次
  - frontend-external_error: 43 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_cpu_5
- **故障类型**: cpu
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 21 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_delay_2
- **故障类型**: delay
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_delay_3
- **故障类型**: delay
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_disk_4
- **故障类型**: disk
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_loss_1
- **故障类型**: loss
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 2 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_loss_2
- **故障类型**: loss
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 4 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_loss_3
- **故障类型**: loss
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_loss_4
- **故障类型**: loss
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 1 次
- **数据时长**: 721 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_mem_1
- **故障类型**: mem
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 7 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:46

### 案例 productcatalogservice_mem_2
- **故障类型**: mem
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 6 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:47

### 案例 productcatalogservice_mem_3
- **故障类型**: mem
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend_error: 1 次
  - frontend-external_error: 11 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:47

### 案例 productcatalogservice_mem_4
- **故障类型**: mem
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend-external_error: 5 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:47

### 案例 productcatalogservice_mem_5
- **故障类型**: mem
- **注入服务**: productcatalogservice
- **观测错误**:
  - frontend_error: 4 次
  - frontend-external_error: 2 次
- **数据时长**: 4201 步
- **提取时间**: 2026-04-25T17:37:47


## 三、历史故障案例

### 案例1: CPU 飙升导致服务降级

- 现象: frontend CPU 突增至 95%，延迟从 200ms 升至 5s
- 根因: adservice 接口响应变慢，导致 frontend 线程池积压
- 解决: 限流 adservice 调用，增加超时设置

### 案例2: 内存泄漏引起 OOM

- 现象: cartservice 内存持续增长，最终 OOM 重启
- 根因: redis 连接池配置不当，连接对象未正确释放
- 解决: 修复连接池配置，添加连接泄漏检测

### 案例3: 网络丢包导致级联超时

- 现象: 多个服务同时出现超时错误
- 根因: 底层网络设备故障导致间歇性丢包
- 解决: 切换网络链路，增加重试和熔断机制
