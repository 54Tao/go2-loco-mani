# Go2-X5 Loco-Manipulation with SAGE Scenes

基于SAGE-10k数据集和Go2-X5四足机械臂机器人的locomotion-manipulation研究项目。在Isaac Sim仿真环境中部署机器人，通过预训练PPO策略控制行走和机械臂，键盘控制夹爪开合，为后续VLA训练采集数据。

## 技术栈

Isaac Sim 4.5.0 / Isaac Lab 2.1.0 / Python 3.10 / PyTorch 2.5.1+cu124

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
conda activate lab
cd Go2-X5-lab
python -m pip install -e source/robot_lab
```

运行策略控制（键盘操作）：

```bash
cd Go2-X5-lab
conda run -n lab python scripts/reinforcement_learning/rsl_rl/play_cs.py \
  --task RobotLab-Isaac-Velocity-Flat-Go2-X5-v0 \
  --checkpoint /home/tjz/go2_loco_mani/flat/model_8500.pt \
  --keyboard --num_envs 1
```

键盘操作：方向键控制底盘移动，Z/X旋转，I/K/J/L/U/O控制机械臂关节，G/H控制夹爪开合，B复位机械臂。

## 项目结构

```
.
├── Go2-X5-lab/              # Go2-X5机器人Isaac Lab扩展（已修改适配）
├── flat/                    # 18-DOF PPO策略模型
├── sage/                    # SAGE场景生成框架
├── datasets/sage-10k/       # SAGE-10k场景数据集（526个场景）
├── assets/                  # 生成的USD资产
├── scripts/                 # 工具脚本
│   ├── visualize_scene_robot.py   # 场景可视化
│   ├── sage_to_usd.py            # SAGE场景转USD
│   ├── integrate_robot_scene.py   # 场景机器人集成
│   └── batch_process_scenes.py    # 批量场景处理
├── configs/                 # 配置文件
├── kaifa.md                 # 详细开发文档
└── README.md
```

## 当前进展

SAGE-10k数据集已下载（526个场景），Go2-X5 URDF已添加平行夹爪（20 DOF），场景可视化和批量处理已完成。预训练PPO策略已集成到play_cs.py中，机器人可在平地上正常站立行走，底盘和夹爪键盘控制正常工作。机械臂键盘控制和SAGE场景集成仍在调试中。

详细进展请查看 [kaifa.md](./kaifa.md)

## 参考资料

- [SAGE论文](https://arxiv.org/pdf/2602.10116)
- [SAGE-10k数据集](https://huggingface.co/datasets/nvidia/SAGE-10k)
- [Isaac Sim文档](https://docs.isaacsim.omniverse.nvidia.com/)
- [Go2-X5-lab仓库](https://github.com/fan-ziqi/Go2-X5-lab)

