# Go2-X5 Loco-Manipulation with SAGE Scenes

基于SAGE-10k数据集和Go2-X5四足机械臂机器人的locomotion-manipulation研究项目。在Isaac Sim仿真环境中部署机器人，通过预训练PPO策略控制行走和机械臂，键盘控制夹爪开合，在SAGE室内场景中进行物品抓取，为后续VLA训练采集数据。

## 技术栈

Isaac Sim 5.1.0 / Isaac Lab / Python 3.11 / Conda环境 isaac

## Go2-X5 机器人规格

| 参数 | 值 |
|------|-----|
| 总可动关节 | 20个（策略控制18个，夹爪独立控制） |
| 腿部关节 | 12个（4腿 x 3关节：hip, thigh, calf） |
| 机械臂关节 | 6个（arm_joint1~6，revolute） |
| 夹爪关节 | 2个（arm_joint7~8，prismatic，开合0~0.044m） |
| 夹爪控制 | arm_joint7为主动关节，arm_joint8通过mimic对称跟随 |

## 快速开始

环境配置：

```bash
conda activate isaac
cd Go2-X5-lab
python -m pip install -e source/robot_lab
```

运行策略控制（带SAGE场景，键盘操作）：

```bash
cd Go2-X5-lab
conda run -n isaac python scripts/reinforcement_learning/rsl_rl/play_cs.py \
  --task RobotLab-Isaac-Velocity-Flat-Go2-X5-ArmUnlock-v0 \
  --checkpoint /home/tjz/go2_loco_mani/flat/model_8500.pt \
  --map /home/tjz/go2_loco_mani/datasets/sage-10k/scenes/<scene>.zip \
  --keyboard --num_envs 1
```

键盘操作：
- 方向键：底盘前后左右，Z/X旋转
- I/K：arm_joint1，J/L：arm_joint2，U/O：arm_joint3
- Y/P：arm_joint4，T/[：arm_joint5，R/]：arm_joint6
- G/H：夹爪开合，B：机械臂复位

## 推荐场景（适合抓取任务）

| 场景文件 | 房间类型 | 可抓取物品 |
|---------|---------|-----------|
| 20251213_051113_layout_05646dc7.zip | 车库 5x6m | 钢笔、笔记本、扳手、胶带 |
| 20251213_051404_layout_234eec7.zip | 厨房 4x5m | 杯子、盘子、餐具 |
| 20251213_101034_layout_0c657c6.zip | 医院病房 5x5m | 注射器、药瓶、马克杯 |
| 20251213_112335_layout_e3553fe.zip | 游戏室 5x4m | 钢笔、笔记本、眼镜、马克杯 |
| 20251213_090413_layout_d59e4e4.zip | 游戏室 5x6m | 游戏手柄、马克杯、遥控器 |

## 项目结构

```
.
├── Go2-X5-lab/              # Go2-X5机器人Isaac Lab扩展（已修改适配）
├── Go2-X5-lab-base/         # 原始base代码（sim 5.1版本，参考用）
├── flat/                    # 18-DOF PPO策略模型（ArmUnlock，model_8500.pt）
├── sage/                    # SAGE场景生成框架
├── datasets/sage-10k/       # SAGE-10k场景数据集（526个场景）
├── assets/                  # 生成的USD资产
├── scripts/                 # 工具脚本
│   ├── visualize_scene_robot.py   # 场景可视化
│   ├── sage_to_usd.py            # SAGE场景转USD（支持ZIP输入）
│   ├── integrate_robot_scene.py   # 场景机器人集成
│   └── batch_process_scenes.py    # 批量场景处理
├── configs/                 # 配置文件
├── kaifa.md                 # 详细开发文档
└── README.md
```

## 当前进展

- SAGE-10k数据集已下载（526个场景）
- Go2-X5 URDF已添加平行夹爪（20 DOF）
- 已迁移到Isaac Sim 5.1（conda env: isaac）
- 预训练PPO策略（ArmUnlock，model_8500.pt）已集成
- 机器人可在平地上正常站立行走
- SAGE场景可通过pxr API直接加载到stage（墙壁/地板有碰撞，物品有刚体物理）
- 键盘控制：底盘移动、机械臂6关节、夹爪开合
- 待完善：物理交互稳定性、VLA数据采集流程

详细进展请查看 [kaifa.md](./kaifa.md)

## 参考资料

- [SAGE论文](https://arxiv.org/pdf/2602.10116)
- [SAGE-10k数据集](https://huggingface.co/datasets/nvidia/SAGE-10k)
- [Isaac Sim文档](https://docs.isaacsim.omniverse.nvidia.com/)
- [Go2-X5-lab仓库](https://github.com/fan-ziqi/Go2-X5-lab)


  ┌───────┬────────────┬────────────────────────────┐
  │ 按键  │    关节    │            动作            │
  ├───────┼────────────┼────────────────────────────┤
  │ I / K │ arm_joint1 │ 基座偏摆（左/右）          │
  ├───────┼────────────┼────────────────────────────┤
  │ J / L │ arm_joint2 │ 大臂俯仰（上/下）          │
  ├───────┼────────────┼────────────────────────────┤
  │ U / O │ arm_joint3 │ 小臂俯仰（上/下）          │
  ├───────┼────────────┼────────────────────────────┤
  │ Y / P │ arm_joint4 │ 腕部滚转（正/反）          │
  ├───────┼────────────┼────────────────────────────┤
  │ T / [ │ arm_joint5 │ 腕部俯仰（上/下）          │
  ├───────┼────────────┼────────────────────────────┤
  │ R / ] │ arm_joint6 │ 腕部偏摆（左/右）          │
  ├───────┼────────────┼────────────────────────────┤
  │ B     │ —          │ 复位所有臂关节             │
  ├───────┼────────────┼────────────────────────────┤
  │ G / H │ 夹爪       │ 打开 / 关闭（步长 0.005m） │
  └───────┴────────────┴────────────────────────────┘

