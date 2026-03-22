# Go2-X5 Loco-Manipulation 项目开发文档

## 项目概述

目标是将SAGE-10k数据集中的室内场景导入Isaac Sim仿真环境，在场景中部署Go2-X5四足机械臂机器人，通过预训练的PPO策略实现locomotion-manipulation控制，并为后续VLA训练采集数据。

开发环境：Isaac Sim 4.5.0 / Isaac Lab 2.1.0 / Python 3.10 / PyTorch 2.5.1+cu124 

GitHub仓库：https://github.com/54Tao/go2-loco-mani

基于的开源项目：[SAGE](https://github.com/NVlabs/SAGE)（场景生成）、[Go2-X5-lab](https://github.com/fan-ziqi/Go2-X5-lab)（四足机械臂Isaac Lab扩展）、[SAGE-10k](https://huggingface.co/datasets/nvidia/SAGE-10k)（场景数据集）

---

## 目录结构

```
/home/tjz/go2_loco_mani/
├── Go2-X5-lab/              # Go2-X5机器人Isaac Lab扩展（已修改适配）
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
| 6 | 策略控制+夹爪键盘控制 | 进行中 | 机器人可站立行走，夹爪可控 |

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

开发过程中经历了三次迭代：第一版只有灰色立方体且墙体变形严重；第二版修复了墙体旋转顺序并加载了PLY mesh；第三版修复了numpy.float32与Gf.Vec3f的类型兼容问题。

---

## 阶段4：批量场景处理

编写了 `scripts/batch_process_scenes.py`，直接读取ZIP文件中的JSON（无需解压），提取房间元数据并为每个房间生成4个候选spawn位置。处理了50个场景，全部成功，结果保存在 `configs/batch_scene_configs.yaml`。

---

## 阶段5：修改URDF添加平行夹爪

在Go2-X5的URDF中为机械臂末端添加了平行夹爪。主要改动包括：重新标定arm_base_link到arm_link6的inertial数据和joint origin偏移，修正joint3的rpy方向，将collision从简化cylinder改为实际STL mesh，新增arm_link7/arm_link8（夹爪手指）和对应的prismatic关节，arm_eef_link重定位到夹爪中心。

arm_joint7为主动关节（axis Y，range 0~0.044m），arm_joint8通过mimic标签跟随arm_joint7对称运动。夹爪dynamics设为damping=0.1、friction=0.05。同时更新了mesh文件（旧mesh备份在meshes/X5_backup/），新增link7.STL和link8.STL。

修改后通过USD转换验证：51个joint prims，其中6个RevoluteJoint（arm_joint1~6）、2个PrismaticJoint（arm_joint7~8），总可动关节20个。

---

## 阶段6：策略控制与键盘操作

### 策略模型

使用预训练的PPO策略 `flat/model_8500.pt`，基于RSL-RL框架训练8500次迭代。Actor网络接收259维观测（基座速度、重力、关节位置/速度、动作历史、187维零填充height scan、6维臂关节命令），输出18维动作（12腿+6臂）。策略不控制夹爪，夹爪通过键盘独立控制。

### 执行器配置修改

原始 `go2_x5.py` 中arm执行器的正则 `"arm_joint.*"` 会匹配到夹爪关节，导致执行器组有8个关节而非6个。修改为 `"arm_joint[1-6]"` 并新增独立的gripper执行器组（ImplicitActuatorCfg，stiffness=40，damping=1）。同时设置 `merge_fixed_joints=False` 以保留foot link，确保 `.*_foot` 正则能正确匹配。

### isaaclab版本兼容性修复

Go2-X5-lab代码针对更新版本的isaaclab编写，与当前安装的2.1.0存在多处不兼容。逐一修复了以下问题：

| 问题 | 修复方式 |
|------|----------|
| DistillationRunner不存在 | try/except导入 |
| Se2KeyboardCfg不存在 | 直接传参给Se2Keyboard() |
| RslRlBaseRunnerCfg不存在 | 改为RslRlOnPolicyRunnerCfg |
| quat_apply_inverse不存在 | 在rewards.py中本地实现并patch |
| RayCasterCfg缺少attach_yaw_only | 添加attach_yaw_only=True |
| randomize_rigid_body_com不存在 | 注释掉该EventTerm及引用 |
| actor_obs_normalization参数不存在 | 从PPO配置中删除 |
| hydra配置加载失败 | 绕过hydra，直接实例化配置类 |

### 观测维度匹配

策略期望259维输入，但flat_env_cfg默认只产生69维。差异来自：base_lin_vel（3维，被rough_env_cfg禁用）、height_scan（187维，flat模式下禁用）。在play_cs.py中恢复了base_lin_vel观测，并用 `_zero_height_scan` 函数填充187维零向量。同时修复了critic观测组的joint_pos/joint_vel匹配所有20个关节（含夹爪）导致多4维的问题，限制为18个关节。

### 键盘控制

在play_cs.py中实现了完整的键盘控制：

底盘移动：方向键Up/Down前进后退，Left/Right左右平移，Z/X左右旋转

机械臂关节：I/K控制joint1，J/L控制joint2，U/O控制joint3，Y/P控制joint4，T/[控制joint5，R/]控制joint6，B复位

夹爪：G打开（+0.005，上限0.044），H关闭（-0.005，下限0.0）

臂关节命令通过覆盖 `arm_joint_command` 观测项实现，用lambda返回键盘设定的目标偏移量，替代原来的随机采样命令。

### 当前状态

机器人可以在平地上正常站立行走，底盘和夹爪的键盘控制正常工作。机械臂的初始位置和键盘控制还有小问题待调整。SAGE场景集成因PLY mesh内存占用过大（16个物体导致OOM被系统杀掉）暂未完成，需要优化场景加载方式或简化mesh。

---

## 踩坑记录

### Isaac Sim模块导入顺序

Isaac Sim的omni模块通过Kit框架动态加载，必须在AppLauncher启动后才能导入。在AppLauncher之前导入pxr或omni模块会导致ModuleNotFoundError。

### URDF转USD时merge-joints的影响

`--merge-joints` 参数会合并所有固定关节。对于Go2-X5这种通过固定关节连接机械臂的复合机器人，合并会导致机械臂link消失。但 `merge_fixed_joints=True` 也会合并foot link到calf link，导致 `.*_foot` 正则匹配失败。最终选择 `merge_fixed_joints=False` 保留所有link。

### USD xform操作顺序

USD的xform操作按添加顺序执行。创建墙体时必须按translate-rotate-scale顺序，否则scale在世界坐标系下执行后rotate会导致尺寸变形。

### Gf.Vec3f类型要求

pxr的Gf.Vec3f只接受Python原生float，不接受numpy.float32。从trimesh加载的顶点数据需要显式转换。

### URDF中文材质名称

USD路径不支持中文字符，URDF中的中文材质名称（如"深色橡胶"）会被Isaac Sim自动替换为下划线，不影响功能。

### SAGE场景内存占用

将包含大量PLY mesh的SAGE场景作为sublayer加载到Isaac Sim时，内存占用过大可能导致OOM。需要考虑简化mesh或分批加载。

---

## 修改的文件清单

| 文件 | 改动说明 |
|------|----------|
| `Go2-X5-lab/.../assets/go2_x5.py` | arm执行器正则改为[1-6]，新增gripper组，merge_fixed_joints=False，新增arm_joint7初始状态 |
| `Go2-X5-lab/.../go2_x5/go2_x5.urdf` | 更新inertial/joint origin，新增夹爪link和joint，arm_joint8添加mimic |
| `Go2-X5-lab/.../go2_x5/meshes/X5/` | 更新STL文件，新增link7.STL和link8.STL |
| `Go2-X5-lab/.../rsl_rl/play_cs.py` | 绕过hydra，修复导入兼容性，添加键盘控制（底盘+臂+夹爪），恢复观测维度 |
| `Go2-X5-lab/.../velocity_env_cfg.py` | attach_yaw_only，注释randomize_com_positions |
| `Go2-X5-lab/.../rough_env_cfg.py` | 注释randomize_com_positions引用 |
| `Go2-X5-lab/.../rsl_rl_ppo_cfg.py` | 删除actor_obs_normalization参数 |
| `Go2-X5-lab/.../mdp/rewards.py` | 本地实现quat_apply_inverse |
| `scripts/sage_to_usd.py` | 新建，SAGE场景JSON+PLY转USD |
