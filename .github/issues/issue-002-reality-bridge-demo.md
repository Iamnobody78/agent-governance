# Good First Issue #2: 扩展 DEMO 示例

## 任务描述
在 `examples/` 中创建一个新的使用案例，展示 `ExtendedRealityBridgeRouter` 的 TaG 钩子功能。

## 预期产出
- 新建 `examples/reality_bridge_governance_demo.py`
- 展示完整工作流：
  1. 注册自定义 TaG 钩子（如"禁止午夜执行"）
  2. 提交正常命题 → 路由通过
  3. 提交危险命题（含 "password"） → 被 credential_leak_guard 拦截
  4. 提交自修改命题 → 被 self_modification_safety 拦截
  5. 输出仪表盘 `get_state()`

## 技术栈
- Python 3.10+
- agent-governance 现有模块

## 相关文件
- `examples/chat_agent_with_governance.py` — 参考风格
- `governance/meta/reality_bridge.py` — ExtendedRealityBridgeRouter
- `governance/meta/reality_bridge.py` — TaGHook, TaGHookType

## 详细步骤
1. Fork 本仓库
2. 创建分支: `git checkout -b demo/reality-bridge`
3. 创建 `examples/reality_bridge_governance_demo.py`
4. 实现 5 个演示场景（见预期产出）
5. 运行 `python examples/reality_bridge_governance_demo.py` 验证
6. 提交: `git commit -m "demo: add RealityBridge governance demo"`
7. 发起 PR

## 难度
🟢 新手友好（有现成例子可参考）

## 预计耗时
2-3 小时
