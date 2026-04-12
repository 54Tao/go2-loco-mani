# Go2-X5 Loco-Manipulation 项目开发文档

## 项目概述

目标是将SAGE-10k数据集中的室内场景导入Isaac Sim仿真环境，在场景中部署Go2-X5四足机械臂机器人，通过预训练的PPO策略实现locomotion-manipulation控制，并为后续VLA训练采集数据。

开发环境：Isaac Sim 5.1.0 / Isaac Lab / Python 3.11 / PyTorch / Conda环境 isaac

GitHub仓库：https://github.com/54Tao/go2-loco-mani

基于的开源项目：[SAGE](https://github.com/NVlabs/SAGE)（场景生成）、[Go2-X5-lab](https://github.com/fan-ziqi/Go2-X5-lab)（四足机械臂Isaac Lab扩展）、[SAGE-10k](https://huggingface.co/datasets/nvidia/SAGE-10k)（场景数据集）

---

## 目录结构

```
/home/tjz/go2_loco_mani/
├── Go2-X5-lab/              # Go2-X5机器人Isaac Lab扩展（已修改适配）
├── Go2-X5-lab-base/         # 原始base代码（sim 5.1版本，参考用）
├── flat/                    # 18-DOF PPO策略模型（model_8500.pt）
├── sage/                    # SAGE场景生成框架
├── datasets/sage-10k/       # SAGE-10k场景数据集（526个场景）
├── assets/                  # 生成的USD资产
├── scripts/                 # 工具脚本（可视化、场景转换、批量处理）
├── configs/                 # 场景配置文件
├── kaifa.md                 # 本文档
└── README.md
```

---

## 机器人规格

| 参数 | 值 |
|------|-----|
| 总可动关节 | 20个（策略控制18个，夹爪独立控制） |
| 腿部关节 | 12个（4腿 x 3关节：hip, thigh, calf） |
| 机械臂关节 | 6个（arm_joint1~6，revolute） |
| 夹爪关节 | 2个（arm_joint7~8，prismatic，开合0~0.044m） |
| 夹爪控制 | arm_joint7为主动关节，arm_joint8通过mimic对称跟随 |
| 基座高度 | ~0.4m |

---

## 实施进度

| 阶段 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 1 | SAGE-10k数据集获取 | 完成 | 526个场景 |
| 2 | Isaac Sim环境验证 | 完成 | headless模式初始化慢 |
| 3 | 场景可视化与机器人集成 | 完成 | PLY mesh加载+纹理+自动spawn |
| 4 | 批量场景处理 | 完成 | 50个场景配置生成 |
| 5 | 修改URDF添加夹爪 | 完成 | 6旋转+2棱柱关节 |
| 6 | 迁移到Isaac Sim 5.1 | 完成 | 用原base覆盖，修复所有兼容性问题 |
| 7 | 策略控制+SAGE场景+键盘控制 | 进行中 | 机器人可站立行走，场景可加载，物理交互待完善 |

---

## 阶段1：SAGE-10k数据集

从HuggingFace下载了SAGE-10k数据集，共526个场景ZIP文件，总数据量约35GB。每个场景包含一个布局JSON文件、PLY格式的3D物体及其纹理PNG、房间材质贴图。

场景JSON的关键字段：
- `rooms[].room_type` — 房间类型（如bedroom, kitchen, living room）
- `rooms[].dimensions` — 房间尺寸（width, length, height）
- `rooms[].walls[]` — 墙体定义（start_point, end_point, height, thickness）
- `rooms[].objects[]` — 物体列表（position, rotation, dimensions, source_id）
- `rooms[].objects[].source_id` — 对应objects/目录下的PLY文件名

对前50个场景的统计显示共26种房间类型，其中master bedroom最多（7个），其次是living room（5个）、kitchen和warehouse（各4个）。

---

## 阶段2-3：场景可视化与机器人集成

编写了 `scripts/visualize_scene_robot.py`，在Isaac Sim中加载SAGE场景并放置Go2-X5机器人。使用trimesh库加载PLY文件为USD Mesh，支持顶点颜色和纹理贴图。墙体通过Cube几何体创建，按translate-rotate-scale顺序设置xform避免变形。实现了自动寻找空旷spawn位置的算法，避免机器人卡在物体中。

---

## 阶段4：批量场景处理

编写了 `scripts/batch_process_scenes.py`，直接读取ZIP文件中的JSON（无需解压），提取房间元数据并为每个房间生成4个候选spawn位置。处理了50个场景，全部成功，结果保存在 `configs/batch_scene_configs.yaml`。

---

## 阶段5：修改URDF添加平行夹爪

在Go2-X5的URDF中为机械臂末端添加了平行夹爪。主要改动包括：重新标定arm_base_link到arm_link6的inertial数据和joint origin偏移，修正joint3的rpy方向，将collision从简化cylinder改为实际STL mesh，新增arm_link7/arm_link8（夹爪手指）和对应的prismatic关节，arm_eef_link重定位到夹爪中心。

arm_joint7为主动关节（axis Y，range 0~0.044m），arm_joint8通过mimic标签跟随arm_joint7对称运动。夹爪dynamics设为damping=0.1、friction=0.05。

---

## 阶段6：迁移到Isaac Sim 5.1

原来为了兼容 Isaac Sim 4.5 对 Go2-X5-lab 做了若干 hack，现在安装了 Isaac Sim 5.1（conda env: `isaac`），直接用原始 base 代码（`Go2-X5-lab-base`）覆盖，去掉所有兼容性 hack。

主要操作：
- 用 `rsync` 将 `Go2-X5-lab-base/source/robot_lab/robot_lab/` 覆盖到 `Go2-X5-lab/source/robot_lab/robot_lab/`，恢复所有 sim 5.1 正确代码
- 重新应用夹爪功能改动（`go2_x5.py`：`merge_fixed_joints=False`，arm执行器正则改为 `arm_joint[1-6]`，新增 gripper ImplicitActuatorCfg）
- 修复 `play_cs.py` 的 sim 5.1 API 差异（`Se2Keyboard` 需要 `Se2KeyboardCfg` 对象，`get_observations()` 返回 TensorDict 不是元组）

恢复的 sim 5.1 正确代码：
- `velocity_env_cfg.py`：`ray_alignment="yaw"`（而非 `attach_yaw_only=True`）
- `mdp/rewards.py`：直接 `from isaaclab.utils.math import quat_apply_inverse`（而非本地实现）
- `agents/rsl_rl_ppo_cfg.py`：恢复 `actor_obs_normalization=False` 参数
- `velocity_env_cfg.py`：恢复完整的 `randomize_com_positions` EventTerm

---

## 阶段7：策略控制 + SAGE场景集成 + 键盘控制

### 策略模型

使用预训练的PPO策略 `flat/model_8500.pt`，基于RSL-RL框架，对应任务 `RobotLab-Isaac-Velocity-Flat-Go2-X5-ArmUnlock-v0`（`Go2X5ArmUnlockFlatEnvCfg`）。

关键参数（来自 `flat/params/env.yaml`）：
- `decimation=8, dt=0.0025`（控制频率50Hz）
- `sim2sim_obs_delay_steps=0`（无延迟）
- 观测：base_lin_vel（scale=2.0）、base_ang_vel（scale=0.25）、joint_pos/vel（18关节）、height_scan（187维零填充）、arm_joint_command（6维）
- 动作：18维（12腿+6臂），不含夹爪

### SAGE场景加载方案

经过多次尝试，最终采用**在 `gym.make()` 之后直接用 pxr API 在 stage 上创建几何体**的方案：
- 不使用 sublayer（会破坏 physx tensors view，导致 `env.step()` 崩溃）
- 不使用 `AssetBaseCfg` 动态属性（configclass 不处理动态属性，场景不显示）
- 不使用 `terrain_type="usd"`（`visual_material` 默认黑色覆盖原始颜色）
- 直接读取 SAGE ZIP 中的 JSON 和 PLY，用 `UsdGeom.Mesh.Define`、`UsdGeom.Cube.Define` 等 API 创建几何体，只添加渲染 prim，不影响已初始化的物理视图

物理交互：
- 墙壁和地板：`UsdPhysics.CollisionAPI`（静态碰撞）
- 可抓取物品：`UsdPhysics.RigidBodyAPI` + `CollisionAPI` + `MassAPI`（动态刚体，质量根据体积估算）

### 键盘控制

运行命令：
```bash
cd /home/tjz/go2_loco_mani/Go2-X5-lab
conda run -n isaac python scripts/reinforcement_learning/rsl_rl/play_cs.py \
  --task RobotLab-Isaac-Velocity-Flat-Go2-X5-ArmUnlock-v0 \
  --checkpoint /home/tjz/go2_loco_mani/flat/model_8500.pt \
  --map /home/tjz/go2_loco_mani/datasets/sage-10k/scenes/<scene>.zip \
  --keyboard --num_envs 1
```

键盘操作：
- 方向键：底盘前后左右，Z/X旋转
- I/K：arm_joint1（基座偏摆），J/L：arm_joint2（大臂俯仰），U/O：arm_joint3（小臂俯仰）
- Y/P：arm_joint4，T/[：arm_joint5，R/]：arm_joint6
- G/H：夹爪开合（步长0.005m，上限0.044m）
- B：机械臂复位

### 推荐场景

经过对526个场景的分析，以下场景适合抓取任务：

| 场景文件 | 房间类型 | 尺寸 | 可抓取物品 |
|---------|---------|------|-----------|
| 20251213_051113_layout_05646dc7.zip | 车库 | 5x6m | 钢笔、笔记本、扳手、胶带 |
| 20251213_051404_layout_234eec7.zip | 厨房 | 4x5m | 杯子、盘子、餐具、书 |
| 20251213_101034_layout_0c657c6.zip | 医院病房 | 5x5m | 注射器、药瓶、眼镜、马克杯 |
| 20251213_112335_layout_e3553fe.zip | 游戏室 | 5x4m | 钢笔、笔记本、眼镜、马克杯 |
| 20251213_090413_layout_d59e4e4.zip | 游戏室 | 5x6m | 游戏手柄、马克杯、书、遥控器 |

---

## 踩坑记录

### Isaac Sim模块导入顺序

Isaac Sim的omni模块通过Kit框架动态加载，必须在AppLauncher启动后才能导入。

### URDF转USD时merge-joints的影响

`merge_fixed_joints=True` 会合并foot link到calf link，导致 `.*_foot` 正则匹配失败。最终选择 `merge_fixed_joints=False` 保留所有link。

### USD xform操作顺序

创建墙体时必须按translate-rotate-scale顺序，否则scale在世界坐标系下执行后rotate会导致尺寸变形。

### Gf.Vec3f类型要求

pxr的Gf.Vec3f只接受Python原生float，不接受numpy.float32。

### SAGE场景加载方式选择

sublayer加载会永久破坏physx tensors view（`env.step()` 崩溃）。正确方式是在 `gym.make()` 之后直接用 pxr API 创建几何体，只添加渲染prim，不影响物理视图。

### 相机跟随穿墙

`rl_utils.py` 的 `camera_follow` 默认把相机放在机器人后方3m，对于小房间（3-5m）会穿出墙外。改为后方1m、高0.8m。

### 策略对应的env_cfg

`flat/model_8500.pt` 对应 `Go2X5ArmUnlockFlatEnvCfg`（不是 `Go2X5FlatEnvCfg`），使用 `decimation=8, dt=0.0025`，无观测延迟。用错 env_cfg 会导致观测维度不匹配或机器人站不稳。

---

## 修改的文件清单

| 文件 | 改动说明 |
|------|----------|
| `Go2-X5-lab/source/robot_lab/robot_lab/` | rsync 覆盖原 base（sim 5.1 正确代码） |
| `Go2-X5-lab/.../assets/go2_x5.py` | merge_fixed_joints=False，arm执行器[1-6]，新增gripper组 |
| `Go2-X5-lab/.../go2_x5/go2_x5.urdf` | 更新inertial/joint origin，新增夹爪link和joint |
| `Go2-X5-lab/.../rsl_rl/play_cs.py` | 使用ArmUnlockFlatEnvCfg，键盘控制（底盘+臂+夹爪），SAGE场景直接加载 |
| `Go2-X5-lab/.../rsl_rl/rl_utils.py` | camera_follow 距离从3m改为1m |
| `scripts/sage_to_usd.py` | 支持ZIP输入，mesh简化，设置default prim |
