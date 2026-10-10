# 前端设计体系：三层

这套体系分三层，**三层一起进模板**，缺一层就会退化成「没有抓手的设计规范」。

## ① 规则层：`.codebuddy/rules/design-skills.md`

**开工前看的那张表**：什么时候用哪个设计 skill、以及唯一硬禁区。

- 调度表：定方向 → `impeccable`；细节工艺 → `make-interfaces-feel-better`；
  无障碍与规范审查 → `web-design-guidelines`；查色板资料 → `ui-ux-pro-max`；
  用 shadcn-vue 组件 → `shadcn-vue`。
- ⚠️ **硬禁区**：`ui-ux-pro-max` **禁用 `--persist` / `--force`**。
  它的 `--persist` 会往仓库根写一份自称 "Global Source of Truth" 的 `MASTER.md`，
  那等于塞进**第二份设计真相**，与「真相源 = `tokens.css`」正面冲突。只当查询台用。
- 「本机没装某个 skill 就跳过它，别停下来等安装」——这条是模板加的，避免新机器上的死等。

## ② 档案层：`docs/design/设计skill清单.md`

**为什么只用这些、装到哪一步、哪部分被舍弃**。它是档案，不是速查——速查在规则层。
列出每个 skill 的角色、安装完整性（哪些组件没装）、舍弃了什么及原因，末尾留一节
「本项目的调整记录」供新项目追加。

## ③ 真相源层：`frontend/src/styles/tokens.css` + `docs/design/前端.md`

**唯一真相源是 `tokens.css`**——改颜色 / 间距 / 圆角只改它，组件不许写死值。
根 `DESIGN.md` 是它的**可读快照**，由 impeccable 从实现派生，**不手写**。

### tokens.css 的默认值：只搬口径与结构，不搬色值

⚠️ **绝不搬源项目的具体色值**（那是它的产品身份，硬搬会让所有项目长一个样）。
模板给的是**中性灰阶占位** + 一个标了 TODO 的主色，并把「口味规格」写成注释里的说明：

| 口味规格（写进文件头注释） | 含义 |
|---|---|
| 冷中性底色 | 面走**冷调**（色相约 250–265），不要暖灰 |
| 宽松 | 字阶**配行高**（中文正文 1.75），圆角整体偏大一档 |
| **L3 大面积彩色面** | 页面底 / 区块 / 卡片**都带一点颜色**，但保持高亮度低彩度 |
| **留一处近白** | `--color-reader` 专门给读长文字的那块，**有意命名、以后谁也别给它上色** |
| 柔和阴影 | 不透明度提高、扩散加大，且用**冷调色相**而不是纯黑 |
| 浮层用玻璃拟态 | 弹窗 / 下拉走 `.glass`；铺底（页面 / 卡片 / 表格 / 表单）一律实底面 |

保留下来的**结构**（这部分是通用的）：
- 分两节：第一节 `@theme static` 放真值，第二节 `:root` + `@theme inline` **只做映射**给 shadcn 组件；
  在第二节写死颜色 = 又造一份真相。
- 变量命名结构：`--color-canvas` / `--color-surface` / `--color-surface-2` / `--color-tint-*` /
  `--color-reader` / `--color-line` / `--color-ink-*` / `--color-brand{,-soft,-ink}` /
  `--color-{ok,warn,danger}{,-soft}` / `--color-focus` / `--radius-*` / `--font-*` / `--text-*`（带行高）/ `--shadow-*`。
- 三条硬规矩（写进注释）：① 玻璃背后必须有内容可透；② **玻璃上不许放长正文**；③ 减少透明度时退化成实底。
- ⚠️ 滚动条**只能用标准属性** `scrollbar-color` / `scrollbar-width`——Windows 11 的 Chrome 默认
  Fluent overlay 滚动条，此模式下 Chrome **直接忽略所有 `::-webkit-scrollbar-*`**。

### `docs/design/前端.md` 骨架化

保留结构（页面流 / 路由 / 状态 / API 边界 / 真相源在哪 / 材质语言表），内容换占位。
里面留了几条**通用硬教训**（这些换项目照样成立）：

- 写弹窗宽度时 `sm:max-w-*` 必须一起覆盖（shadcn 的 `DialogContent` 内置 `sm:max-w-sm`，
  与 `max-w-3xl` 不同组，`twMerge` 不会帮你合并 → 实际只有 384px）。
- 可点元素一律真按钮（键盘用户要有焦点指示）。
- 数组参数不能直接交给 axios（会序列化成 `tagIds[]=1`，后端认的是重复参数名 → 筛选**静默失效**）。
- 列表页筛选状态放网址不放 Store；默认值不进网址；用 `replace` 不用 `push`。
