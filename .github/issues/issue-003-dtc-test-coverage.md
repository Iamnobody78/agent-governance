# Good First Issue #3: 完善数字孪生校准器测试覆盖率

## 任务描述
为 `DigitalTwinCalibrator` 补充边界测试和异常场景测试，提升测试覆盖率到 95%+。

## 预期产出
- 在 `tests/test_digital_twin.py` 中新增 10+ 个测试用例
- 覆盖场景：
  - 极端漂移速率（斜率 > 10.0）
  - 空锚点列表
  - 重复校准周期
  - 传感器空读数
  - 全维度对比（10 个 GapDimension）
  - 锚点容差边界值
  - 大量历史数据（1000+ 样本）

## 技术栈
- Python 3.10+
- pytest

## 相关文件
- `governance/meta/digital_twin_calibrator.py` — 被测模块
- `tests/test_digital_twin.py` — 现有测试（44 个）
- `tests/test_fixed_point.py` — 测试风格参考

## 详细步骤
1. Fork 本仓库
2. 创建分支: `git checkout -b test/dtc-coverage`
3. 在 `tests/test_digital_twin.py` 末尾添加新测试类
4. 运行 `pytest tests/test_digital_twin.py -v` 验证全部通过
5. 提交: `git commit -m "test: add boundary cases for DigitalTwinCalibrator"`
6. 发起 PR

## 难度
🟢 新手友好

## 预计耗时
2-4 小时
