## 改动

<!-- 一两句话：做了什么、为什么。标题用 <type>(<scope>): <summary>，见 docs/collaboration.md -->

## 负责模块

- [ ] YHT 剧本格式/加载/校验
- [ ] ZQO 运行时核心/插件接口
- [ ] ZRS 解析/界面/道具插件
- [ ] ZC 推理插件/剧本A/整合
- [ ] LJ 存档/回放/剧本B

## 验证

```text
python -B -m unittest discover -s tests/<缩写> -t .   # 本模块
python -B -m unittest discover -s tests -t .          # 全部
python main.py validate
```

<!-- 粘贴实际运行结果的最后几行 -->

## 检查清单

- [ ] 新功能有对应测试（正常、边界、异常输入各至少一例）
- [ ] 改了 `taleloom/model.py` 或引擎公开接口？若是，已加 `contract` 标签并更新 `docs/contracts.md`
- [ ] 改了剧本？`python main.py replay <剧本>` 通过，新结局有通关脚本
- [ ] `docs/requirements.md` 中对应需求的状态已更新
- [ ] 交接记录 `docs/handoffs/<缩写>.md` 已更新
- [ ] 用了 AI？已在 `docs/ai-usage.md` 记一行
- [ ] 已请审阅人：<!-- 见 docs/team-tasks.md 第 6 节的审阅轮换 -->
