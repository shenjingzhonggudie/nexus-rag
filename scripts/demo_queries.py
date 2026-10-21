"""临时：把人工写的示范 query 填入骨架（其余留空待 LLM 出题 + 人工筛选）。

示范只覆盖 direct 前 16 条与 cross_doc 全部 6 条——够展示"什么算合格的题"，
剩下的交给 scripts/gen_queries.py 出 prompt。
"""

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PATH = Path("data/eval/qrels.skeleton.json")
rows = json.loads(PATH.read_text(encoding="utf-8"))

# direct：必须能由该小节**单独**回答，且不照抄标题
DIRECT_DEMO = [
    "Node 对象会跟踪节点上的哪些资源容量信息？",
    "创建表时表名应该遵循什么规范？",
    "v-model 的 .lazy 修饰符改变了什么更新时机？",
    "React 项目里根组件文件通常放在哪里？",
    "Kubernetes 的网络模型是由谁来实现的？",
    "用 Go 语言连接 TiDB 有哪些可选的驱动？",
    "Vue 是怎么防止模板内容被注入脚本的？",
    "什么情况下需要用 ref 直接操作 DOM？",
    "启用对等聚合发现后，发现请求会默认返回什么？",
    "TiDB 里主键的定义和 InnoDB 有什么不同？",
    "Web 无障碍访问相关的 W3C 标准有哪些？",
    "JSX 和普通 HTML 在写法上有什么区别？",
    "自定义工作负载可以用 Lease 来做什么？",
    "TiDB 怎么决定多表 Join 的执行顺序？",
    "同一个页面里可以创建多个 Vue 应用实例吗？",
    "什么样的 React 组件才算得上是纯组件？",
]

# cross_doc：必须真的需要**两篇文档**才能回答（对比题）
CROSS_DOC_DEMO = [
    "Vue 的生命周期钩子和 React 的 Effect 在触发时机上有什么区别？",
    "Vue 和 React 在给元素绑定事件处理函数的方式上有什么不同？",
    "Vue 的 v-if 和 React 的条件渲染在写法上有什么差异？",
    "Vue 和 React 对 props 单向数据流的约束分别是什么？",
    "Vue 和 React 在区分开发环境与生产环境上的做法有什么不同？",
    "Vue 和 React 在优化首屏加载上都提供了哪些手段？",
]

# paraphrase：换说法、不照抄原文术语；None 表示该小节不适合出题（导航页/纯示例）
PARAPHRASE_DEMO = [
    "已经有一个别的后端渲染的老网站，想只把其中一段页面换成 React 该从哪下手？",
    "集群怎么知道某个工作节点还活着？",
    "想让查询直接在索引上拿到全部数据、不用回表，索引该怎么建？",
    "想先搞清楚页面到底慢在哪，有哪些现成的检测工具可用？",
    "在 JSX 里怎么把变量的值渲染到页面上？",
    "怎么限制不同角色只能操作设备分配相关的部分接口？",
    "主键和数据的物理存放顺序绑在一起有什么好处？",
    "过渡效果能不能跟着状态变化动态切换？",
    "写 reducer 时最基本的几条纪律是什么？",
    "每台机器上都有哪些进程在维持 Pod 运行？",
    "给表加索引时有哪些要注意的地方？",
    "组件有多个根元素时，外部传进来的属性还会自动挂到根上吗？",
    "组件层级很深时，一层层往下传参数会带来什么麻烦？",
    "云控制器管理器在设计上是怎样部署的？",
    None,  # '下一步' 是导航页，不适合出题
    "子组件怎么把内部发生的事情通知给父组件？",
    "属性很多时，怎么把一整个对象一次性拆开传给组件？",
    "能不能让控制面假装成更早的版本对外提供服务？",
    None,  # '执行 CREATE TABLE 语句' 是示例代码页
    "想在组件刚渲染完成、DOM 已经可用时跑一段代码，应该挂在哪里？",
]

singles = [r for r in rows if r["type"] == "direct"]
for row, query in zip(singles, DIRECT_DEMO):
    row["query"] = query

crosses = [r for r in rows if r["type"] == "cross_doc"]
for row, query in zip(crosses, CROSS_DOC_DEMO):
    row["query"] = query

paras = [r for r in rows if r["type"] == "paraphrase" and not r["query"].strip()]
for row, query in zip(paras, PARAPHRASE_DEMO):
    if query:
        row["query"] = query

# 第二批 paraphrase（同样：None = 该小节不适合出题）
PARAPHRASE_DEMO_2 = [
    None,  # '下一步' 导航页
    None,  # '执行 CREATE TABLE 语句' 示例页
    "父组件没传某个属性时，怎么让组件用上一个兜底值？",
    "主键设成随机生成之后，插入数据时还能自己指定主键吗？",
    "在模板里直接写事件处理代码时，怎么拿到原生的事件对象？",
    None,  # 'Try React' 试用页
    "TiDB 里表是什么？它和数据库是什么关系？",
    "自己写的输入组件能不能也支持双向绑定？",
    "父组件怎么把数据交给子组件？",
    "执行删除之后磁盘空间为什么没有马上变小？",
    "同一套过渡动画怎么在多个地方重复使用？",
    "React 项目构建报错时应该按什么顺序排查？",
    "给表起名时有哪些约定俗成的规则？",
    "想一次性切换一组元素而不是单个元素，该怎么做？",
    "只想让某几个目录用上新编译器，怎么配置？",
    "删除大量数据时为什么不应该一条语句删完？",
    "模板里调用方法和用计算属性，结果一样但有什么区别？",
    "几个总是一起变化的 state 应该合并成一个吗？",
    "大量写入时怎么防止所有请求都压到同一处？",
    "怎么给整个应用统一设置一个错误处理函数？",
    "想在不推倒重来的前提下逐步用上新编译器，有哪几种做法？",
]

paras2 = [r for r in rows if r["type"] == "paraphrase" and not r["query"].strip()]
for row, query in zip(paras2, PARAPHRASE_DEMO_2):
    if query:
        row["query"] = query

# direct 第二批
DIRECT_DEMO_2 = [
    "Kubernetes 的自动扩缩容相关有哪些辅助组件？",
    "TiDB 从哪个版本开始支持非事务的批量删除？",
    "在 script setup 里怎么拿到父组件传下来的透传属性？",
    "想让一个值变化时不触发重新渲染，应该用什么？",
    "kubelet 对 apiserver 的健康检查请求怎么避免被限流？",
    "报错 Lost connection to MySQL server during query 应该怎么处理？",
    "Suspense 的后备插槽在什么时候显示？",
    "哪些情况下其实不该用 Effect？",
    "Kubernetes 怎么保证控制面组件同一时间只有一个实例在跑？",
    "TiDB 里优化 SQL 性能要遵循哪些原则？",
    "v-if 和 v-show 在渲染行为上有什么本质区别？",
    "React 官方文档里提到了哪些全栈框架？",
    "Kubernetes 的控制器遵循什么设计原则？",
    "TiDB 支持哪几种表连接算法？",
    "组件被 KeepAlive 缓存后是卸载还是变成其他状态？",
    "在 React 组件里怎么让界面随着数据变化而更新？",
    "怎么检查集群里有没有启用准入 Webhook？",
    "创建数据库时有哪些命名规则要遵守？",
    "为了无障碍访问，页面顶部应该放一个什么链接？",
    "React 应用的基本组成单位是什么？",
    "Kubernetes 内置的控制器运行在哪里？",
    "TiDB 的二级索引是对什么进行排序？",
    "想让离开动画先播完再播进入动画，该怎么设置？",
]

directs2 = [r for r in rows if r["type"] == "direct" and not r["query"].strip()]
for row, query in zip(directs2, DIRECT_DEMO_2):
    row["query"] = query

# multi_block：必须综合两个小节才能回答；None 表示这对不适合（FAQ + 导航 / 框架列表）
MULTI_BLOCK_DEMO = [
    "TiDB 里主键的选择会影响数据的物理存储方式吗？",
    "想优化 Vue 应用的性能，第一步该做什么？",
    "React 从状态变化到页面更新，中间经历了哪几个阶段？",
    None,  # '常见问题' + '下一步' 不是同一主题
    "Vue 项目部署到生产环境时，用不用构建工具分别要注意什么？",
    "设计组件的 state 结构时，应该遵循哪些原则？",
    "TiDB 执行多表 Join 时，算法和顺序分别是怎么决定的？",
    "Vue 在安全上做了哪些防护，还需要开发者自己注意什么？",
    None,  # '其他框架' + '从零开始' 不构成综合题
    "KeepAlive 怎么控制哪些组件被缓存、最多缓存多少个？",
    "在 React 里怎么定义一个组件并从别的文件引入它？",
    "KeepAlive 缓存满了之后，被淘汰的实例会经历什么？",
    "把一个组件拆到单独文件后，它的标签怎么写？",
    "Suspense 在等待异步依赖时，默认插槽和后备插槽怎么切换？",
    "JSX 里怎么把 JavaScript 表达式的值嵌进标签？",
    "Suspense 和 Transition、KeepAlive 一起用，或者嵌套多层时要注意什么？",
    "在 JSX 里怎么把从父组件拿到的值渲染出来？",
    "多个 Teleport 指向同一个目标，或者想延迟渲染内容时该怎么做？",
]

multis = [r for r in rows if r["type"] == "multi_block" and not r["query"].strip()]
for row, query in zip(multis, MULTI_BLOCK_DEMO):
    if query:
        row["query"] = query

PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

filled = sum(1 for r in rows if r["query"].strip())
print(f"已填 {filled} / {len(rows)} 条（direct 16 + cross_doc 6），其余待填")
