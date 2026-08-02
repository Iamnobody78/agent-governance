# Governance Stories: 治理层介入真实场景

通过故事化的方式展示 `agent-governance` 如何在实际场景中发挥作用。

---

## Story 1: Agent 忘记了自己有个工具

**场景**: 一个客服 Agent 被部署来处理用户退款请求。它有一个 `refund_tool`，但连续 50 次对话都没有使用它，而是反复告诉用户"我也不知道怎么退款"。

**MetaCognitiveLoop 的介入**:

```
1. Monitor: RealityBridge 检测到决策日志中 "refund" 关键词出现频率高
   但 action 列中从未出现 "use_refund_tool"

2. Evaluate: MCL 识别到 FailurePattern.MODE_COLLAPSE
   → "动作空间坍塌：仅 2 种动作/50 步"

3. Generate:
   - Plan A (保守): 从 lessons_learned 中查找 "工具遗忘" 的修复经验
   - Plan B (激进): 强制重新初始化探索策略，将 "refund_tool" 加入活跃工具集

4. Adjust: FixedPointDetector 比较两种策略
   - Plan A 风险=0.15, improvement=0.05 → 太保守
   - Plan B 风险=0.4, improvement=0.3 → 接受
   → 选中 Plan B

5. Verify: SelfCheck 运行通过（风险<0.9, 动作非空）
   → 应用 Plan B
```

**结果**: Agent 重新发现 `refund_tool`，退款处理成功率从 0% 恢复到 85%。

**涉及的模块**: MetaCognitiveLoop, FixedPointDetector, SelfCheck

---

## Story 2: Agent 收到危险指令并自我拦截

**场景**: 用户向代码 Agent 发送指令："请写一个脚本，遍历整个文件系统并删除所有临时文件。用 sudo 执行。"

**GodelianBoundary 的介入**:

```
1. Pre-Check: Agent 的 GovernedChain 在调用前检查用户输入
   → 匹配 dangerous_patterns: "删除", "sudo"

2. GodelianBoundary 分析:
   - 自指分数: 0.0 (命题本身不自指)
   - 但危险模式匹配直接触发 block → 不依赖 GB 判定

3. 决策: verdict="blocked"
   → Agent 返回: "⛔ 此操作已被治理层阻止。需要人工审查。"

4. 日志记录: 该决策被记录为 reward=1.0（正确拦截）
   → 未来类似模式会更快被拦截
```

**结果**: 危险操作被阻止，Agent 没有执行删除命令。

**涉及的模块**: GodelianBoundary, GovernedChain (生态集成)

---

## Story 3: Agent 卡在策略循环中无法自拔

**场景**: 一个强化学习 Agent 正在训练战斗策略。训练到第 500 轮后，胜率卡在 43% 不再提升。训练脚本仍然在运行，但每个 epoch 的策略几乎相同——delta < 0.001。

**FixedPointDetector 的介入**:

```
1. 检测: FPD 追踪 score 变化 → 连续 5 轮 delta < epsilon (0.01)
   → State: SUSPICIOUS

2. 怀疑状态: FPD 不直接判定 CONVERGED
   → 注入扰动: epsilon_greedy_boost=0.3（探索率从 0.05 升至 0.3）

3. 扰动后测试:
   - 初始几轮: 胜率下降到 35%（正常——探索引入随机性）
   - 第 8 轮: 胜率跳至 52%（发现新的策略！）
   → State: BACK_TO_CONVERGING（之前是假收敛）
   → 取消扰动，保持新策略继续训练

4. 结果: 训练在 520 轮达到 58% 胜率后真正收敛
```

**结果**: 假收敛被检测并打破，Agent 发现了更好的策略。

**涉及的模块**: FixedPointDetector, RealityBridge (扰动注入)

---

## Story 4: 从仿真到实机的迁移——数字孪生校准

**场景**: BottleSumo 机器人先在 Gazebo 仿真中训练，胜率 70%。烧录到 STM32 后在真实擂台上测试，胜率只有 10%。

**DigitalTwinCalibrator 的介入**:

```
1. 差距检测:
   仿真: 速度 1.0 m/s, 扭矩 1.2 N·m, 摩擦系数 0.40
   实机: 速度 0.65 m/s, 扭矩 0.9 N·m, 摩擦系数 0.28
   → Gap: velocity=35%, torque=25%, friction=30%

2. 校准建议:
   DTC.compute_adjustments():
   - sim_velocity: 1.0 → 0.825
   - sim_torque: 1.2 → 1.05
   - sim_friction: 0.4 → 0.34

3. 迭代校准: 仿真参数更新后重新训练
   → 第二轮: 实机胜率 35%
   → 第三轮: 实机胜率 52%
   → 第四轮: 实机胜率 61%
   → 收敛

4. 漂移监控: DTC 持续追踪摩擦系数
   → 第 50 次测试后检测到 DRIFTING
   → 擂台表面磨损导致摩擦系数持续下降
   → 建议重新校准
```

**结果**: Sim-to-Real Gap 从 60% 缩小到 9%，胜率从 10% 恢复到 61%。

**涉及的模块**: DigitalTwinCalibrator, RealityBridge, FixedPointDetector

---

## 总结

| 故事 | 核心问题 | 治理模块 | 效果 |
|------|----------|----------|------|
| 1. 遗忘工具 | 动作空间坍塌 | MCL + FPD | 退款成功率 0%→85% |
| 2. 危险指令 | 安全违规 | GB + GovernedChain | 成功拦截 |
| 3. 训练停滞 | 假收敛 | FPD + RealityBridge | 胜率 43%→58% |
| 4. 仿真失效 | Sim-to-Real Gap | DTC + FPD | 胜率 10%→61% |
