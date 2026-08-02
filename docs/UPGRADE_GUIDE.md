# Upgrade Guide

**从旧版本升级到最新版本的操作指南。**

---

## v1.0 → v1.5

### 破坏性变更

**None.** v1.5 是 v1.0 的纯增量升级，保持完全向后兼容。所有 v1.0 的 API 调用方式在 v1.5 中仍然可以正常工作。

### 新增能力

| 新增 | 说明 |
|------|------|
| MetaCognitiveLoop A/B 双轨策略 | 策略生成从单轨改为 A(保守)+B(激进) 双轨并行 |
| 配置参数化 | 硬编码阈值迁移到 `meta_modules_config.yaml` |
| 可观测性 | 所有模块新增 `get_state()` 方法 + MCL 新增 `get_dashboard()` |
| SelfCheckEngine (P3) | 三层自验证：矛盾检测 + 完备性分析 + 信任根管理 |
| DigitalTwinCalibrator (P4) | Sim-to-Real Gap 量化 + 参数校准 + 漂移检测 |
| 标准审计日志格式 | `GovernanceAuditLog` schema 定义 |

### 升级步骤

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 运行现有测试，确认兼容性
pytest tests/ -q
# Expected: 284 passed

# 3. (可选) 复制配置文件
cp governance/meta/meta_modules_config.yaml your_project/config/

# 4. (可选) 尝试新功能
python -c "
from governance.meta import SelfCheckEngine, DigitalTwinCalibrator
engine = SelfCheckEngine()
report = engine.run_full_check()
print(f'SelfCheck score: {report.overall_score}')
"

# 5. 如果使用环境变量覆盖配置
export META_FPD_EPSILON=0.02
export META_GB_SELF_REF_THRESHOLD=0.30
```

### 兼容性矩阵

| 你的代码 (v1.0) | v1.5 中的行为 |
|-----------------|--------------|
| `FixedPointDetector()` | ✅ 完全相同 |
| `GodelianBoundary()` | ✅ 完全相同 (阈值从 0.5→0.25，可配置) |
| `MetaCognitiveLoop()` | ✅ 向后兼容，新增 A/B 策略 |
| `MetaCognitiveLoop().run_cycle()` | ✅ 返回结构增加了字段 |
| `loop.export_history(path)` | ✅ 完全相同 |

---

## 未来的 v1.5 → v2.0（规划中）

### 预计的破坏性变更

| 变更 | 影响 | 迁移路径 |
|------|------|----------|
| 审计日志格式统一为 `GovernanceAuditLog` | `get_state()` 返回格式变化 | v1.5 提前引入，v2.0 强制 |
| 配置路径标准化 | `meta_modules_config.yaml` 位置可能变化 | 支持从旧路径自动迁移 |
| 插件接口定义 | 新增插件加载机制 | 现有模块自动成为内置插件 |

### 提前准备

```python
# 如果要在 v1.5 中提前适配 v2.0 的审计日志格式:
from governance.meta import MetaCognitiveLoop

loop = MetaCognitiveLoop()
# ... feed decisions ...
trace = loop.run_cycle()

# v1.5: 使用 dashboard（兼容）
dashboard = loop.get_dashboard()

# v2.0: 将支持标准审计日志
# audit_logs = loop.get_audit_logs()  # planned
```

---

## 版本生命周期

| 版本 | 状态 | 安全补丁 | 新功能 |
|------|:----:|:--------:|:------:|
| v1.0 | 维护中 | ✅ | ❌ |
| v1.5 | **当前** | ✅ | ✅ |
| v2.0 | 规划中 | — | — |

---

## 常见问题

### Q: 升级后测试失败怎么办？

```bash
# 1. 确认 PYTHONPATH 正确
export PYTHONPATH=$PWD

# 2. 检查 Python 版本
python --version  # 需要 3.10+

# 3. 重新安装依赖
pip install -r requirements.txt

# 4. 运行隔离的故障测试
pytest tests/test_fixed_point.py -v
```

### Q: 我的自定义模块引用了旧的 `__init__.py` 导出

v1.5 的 `governance/meta/__init__.py` 导出了所有旧模块，并新增了新模块。不需要修改 import 语句。

### Q: 配置文件的阈值和之前不同怎么办？

v1.5 默认使用 `meta_modules_config.yaml` 中的值。如果你需要自定义：

```bash
# 方法 1: 环境变量（推荐用于 CI/CD）
export META_FPD_EPSILON=0.05

# 方法 2: 修改 YAML 文件
vim governance/meta/meta_modules_config.yaml

# 方法 3: 代码中覆盖
from governance.meta.config_loader import ConfigLoader
config = ConfigLoader().load()
config.fpd.epsilon = 0.05
```
