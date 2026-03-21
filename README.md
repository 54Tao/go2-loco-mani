# Go2-X5 Loco-Manipulation with SAGE Scenes

基于SAGE-10k数据集和Go2-X5四足机械臂机器人的locomotion-manipulation研究项目。

## 项目目标

复现SAGE场景生成工作，将SAGE-10k数据集中的场景导入Isaac Sim，并在场景中放置Go2-X5四足机械臂机器人，为后续的VLA训练做准备。

## 技术栈

- Isaac Sim: 4.5.0
- Isaac Lab: 2.1.0
- Python: 3.10.19
- PyTorch: 2.5.1+cu124
- CUDA: 可用

## 快速开始

### 1. 环境配置

```bash
# 激活conda环境
conda activate lab

# 安装Go2-X5扩展
cd Go2-X5-lab
python -m pip install -e source/robot_lab
```

### 2. 下载SAGE-10k数据集

```bash
cd datasets/sage-10k
huggingface-cli download nvidia/SAGE-10k --repo-type dataset --local-dir ./
```

### 3. 转换机器人模型

```bash
cd Go2-X5-lab
python scripts/tools/convert_urdf.py \
  source/robot_lab/data/Robots/go2_x5/go2_x5.urdf \
  ../assets/go2_x5.usd \
  --headless
# 注意：不要加 --merge-joints，会导致机械臂消失
```

### 4. 可视化验证

```bash
python scripts/visualize_scene_robot.py
```

### 5. 批量处理场景

```bash
python scripts/batch_process_scenes.py \
  --scenes_dir datasets/sage-10k/scenes \
  --max_scenes 50
```

## Go2-X5 机器人规格

| 参数 | 值 |
|------|-----|
| 总可动关节 | 20个 |
| 腿部关节 | 12个（4腿 × 3关节：hip, thigh, calf） |
| 机械臂关节 | 6个（arm_joint1~6，revolute） |
| 夹爪关节 | 2个（arm_joint7~8，prismatic，开合范围0~0.044m） |
| 夹爪控制 | arm_joint7为主动关节，arm_joint8通过mimic对称跟随 |
| 基座高度 | ~0.4m |

## 项目结构

```
.
├── Go2-X5-lab/              # Go2-X5机器人Isaac Lab扩展
├── X5/                      # 机械臂参考资料
├── sage/                    # SAGE场景生成框架
├── datasets/                # 数据集目录
│   └── sage-10k/            # SAGE-10k场景数据集
├── assets/                  # 生成的资产
│   └── go2_x5.usd           # Go2-X5机器人USD文件
├── scripts/                 # 工具脚本
│   ├── visualize_scene_robot.py
│   ├── integrate_robot_scene.py
│   └── batch_process_scenes.py
├── configs/                 # 配置文件
│   ├── scene_robot_configs.yaml
│   └── batch_scene_configs.yaml
├── kaifa.md                 # 详细开发文档
└── README.md                # 本文件
```

## 当前进展

- ✅ 环境配置完成
- ✅ SAGE-10k数据集下载（526个场景）
- ✅ Go2-X5 URDF到USD转换
- ✅ 修改URDF添加平行夹爪（mimic对称开合）
- ✅ 场景与机器人集成（PLY mesh + 纹理）
- ✅ 批量场景处理（50个场景）
- ⏳ 任务设计与奖励函数
- ⏳ VLA训练准备

详细进展请查看 [kaifa.md](./kaifa.md)

## 参考资料

- [SAGE论文](https://arxiv.org/pdf/2602.10116)
- [SAGE-10k数据集](https://huggingface.co/datasets/nvidia/SAGE-10k)
- [Isaac Sim文档](https://docs.isaacsim.omniverse.nvidia.com/)
- [Go2-X5-lab仓库](https://github.com/fan-ziqi/Go2-X5-lab)

## License

本项目基于多个开源项目，请参考各子项目的许可证。
